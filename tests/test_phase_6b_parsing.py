"""Contract tests for Session B's IFC parser.

Every test here maps to a rule in ``docs/PHASE_6_DATA_CONTRACTS.md`` §1. The
rules are the specification; these assert the implementation obeys them.

WHY THESE FIXTURES ARE SYNTHESISED

    IFC models are built in memory with ifcopenshell rather than read from
    ``data/cache/``. Those cached files are downloaded Supabase objects — they
    are not guaranteed to be present in a clean checkout, and depending on them
    would make this suite fail for reasons unrelated to the parser. Building
    the model in the test also means the element under test is the element
    asserted, matching the fixture convention in ``tests/conftest.py``.

NO LIVE DATABASE

    Nothing here touches Supabase. The parser is pure read-and-transform by
    contract rule 3, so its tests need no persistence and create no records —
    see data contracts §5.1 on why that matters in this repository.

Run: uv run pytest tests/test_phase_6b_parsing.py -v
"""

from __future__ import annotations

import hashlib

import pytest

from app.modules.module2_ifc_read.ifc_parser import ServiceElement
from app.modules.phase_6.phase_6b_parsing import (
    ParsedIFC,
    elements_by_guid,
    parse_ifc_bytes,
    parse_ifc_file,
    sha256_of,
    summarise,
)

ifcopenshell = pytest.importorskip("ifcopenshell", reason="IFC parsing needs ifcopenshell")


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def build_ifc(schema: str = "IFC4", specs: list[tuple] | None = None) -> bytes:
    """Serialise a minimal IFC model containing the requested entities.

    Args:
        schema: IFC schema name, e.g. ``"IFC4"`` or ``"IFC2X3"``.
        specs: ``(ifc_type, name)`` pairs. ``name`` of ``None`` leaves the
            element unnamed. Defaults to one named pipe segment.

    Returns:
        The model encoded as UTF-8 SPF bytes, as storage would hand them over.
    """
    if specs is None:
        specs = [("IfcPipeSegment", "CHW-Supply-01")]

    model = ifcopenshell.file(schema=schema)
    for ifc_type, name in specs:
        model.create_entity(ifc_type, GlobalId=ifcopenshell.guid.new(), Name=name)
    return model.to_string().encode("utf-8")


@pytest.fixture
def simple_ifc() -> bytes:
    """One IFC4 model with three MEP elements of two types."""
    return build_ifc(
        specs=[
            ("IfcPipeSegment", "CHW-Supply-01"),
            ("IfcPipeSegment", "CHW-Return-01"),
            ("IfcValve", "Isolation-Valve-01"),
        ]
    )


@pytest.fixture
def parsed(simple_ifc: bytes) -> ParsedIFC:
    """The parse result for :func:`simple_ifc`."""
    return parse_ifc_bytes(simple_ifc, source_ref="uploads/ifc/simple.ifc")


# ---------------------------------------------------------------------------
# Envelope shape — data contracts §1
# ---------------------------------------------------------------------------


class TestEnvelopeShape:
    """The result must carry every key the contract names, always."""

    def test_all_contract_keys_present(self, parsed):
        assert set(parsed) == {
            "source_ref",
            "source_sha256",
            "schema",
            "schema_note",
            "elements",
            "element_count",
            "type_counts",
            "quality",
        }

    def test_quality_block_keys_present(self, parsed):
        assert set(parsed["quality"]) == {"valid", "error", "warnings", "improvements"}

    def test_failure_envelope_has_the_same_keys(self):
        """A caller must not need to branch on success to read the result."""
        bad = parse_ifc_bytes(b"this is not an IFC file")
        assert set(bad) == {
            "source_ref",
            "source_sha256",
            "schema",
            "schema_note",
            "elements",
            "element_count",
            "type_counts",
            "quality",
        }
        assert set(bad["quality"]) == {"valid", "error", "warnings", "improvements"}

    def test_source_ref_is_echoed_back(self, parsed):
        assert parsed["source_ref"] == "uploads/ifc/simple.ifc"

    def test_elements_are_service_elements(self, parsed):
        assert parsed["elements"]
        assert all(isinstance(e, ServiceElement) for e in parsed["elements"])

    def test_schema_is_reported(self, parsed):
        assert parsed["schema"].upper().startswith("IFC4")


class TestCountConsistency:
    """``element_count`` and ``type_counts`` must never disagree with elements."""

    def test_element_count_equals_len_elements(self, parsed):
        assert parsed["element_count"] == len(parsed["elements"])

    def test_type_counts_sum_to_element_count(self, parsed):
        assert sum(parsed["type_counts"].values()) == parsed["element_count"]

    def test_type_counts_group_correctly(self, parsed):
        assert parsed["type_counts"]["IfcPipeSegment"] == 2
        assert parsed["type_counts"]["IfcValve"] == 1

    def test_counts_hold_on_failure(self):
        bad = parse_ifc_bytes(b"garbage")
        assert bad["element_count"] == 0
        assert bad["elements"] == []
        assert bad["type_counts"] == {}


# ---------------------------------------------------------------------------
# Rule 2 — a file that cannot be read is not an exception
# ---------------------------------------------------------------------------


class TestFailuresAreValuesNotExceptions:
    """Rule 2. Callers render the message; they never see a traceback."""

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(b"", id="empty"),
            pytest.param(b"not an ifc file", id="plain-text"),
            pytest.param(b"\x00\x01\x02\x03", id="binary-noise"),
            pytest.param("ISO-10303-21; truncated".encode(), id="truncated-header"),
            pytest.param("café not ifc".encode("latin-1"), id="undecodable-bytes"),
        ],
    )
    def test_bad_payload_does_not_raise(self, payload):
        result = parse_ifc_bytes(payload)
        assert result["quality"]["valid"] is False
        assert result["elements"] == []

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(b"", id="empty"),
            pytest.param(b"not an ifc file", id="plain-text"),
        ],
    )
    def test_error_message_is_populated_and_human_readable(self, payload):
        error = parse_ifc_bytes(payload)["quality"]["error"]
        assert error
        assert error[0].isupper(), "error is shown to a user, so it should read as prose"

    def test_missing_file_returns_failure_envelope(self, tmp_path):
        result = parse_ifc_file(tmp_path / "does-not-exist.ifc")
        assert result["quality"]["valid"] is False
        assert "could not be opened" in result["quality"]["error"]

    def test_directory_instead_of_file_returns_failure(self, tmp_path):
        result = parse_ifc_file(tmp_path)
        assert result["quality"]["valid"] is False

    def test_success_leaves_error_none(self, parsed):
        assert parsed["quality"]["valid"] is True
        assert parsed["quality"]["error"] is None


# ---------------------------------------------------------------------------
# Rule 4 — source_sha256 is the cache key
# ---------------------------------------------------------------------------


class TestSourceSha256:
    """Rule 4. The digest must be over the bytes actually parsed."""

    def test_matches_hashlib_over_the_same_bytes(self, simple_ifc, parsed):
        assert parsed["source_sha256"] == hashlib.sha256(simple_ifc).hexdigest()

    def test_is_deterministic_across_calls(self, simple_ifc):
        a = parse_ifc_bytes(simple_ifc)["source_sha256"]
        b = parse_ifc_bytes(simple_ifc)["source_sha256"]
        assert a == b

    def test_differs_for_different_content(self, simple_ifc):
        other = build_ifc(specs=[("IfcValve", "Different-Valve")])
        assert parse_ifc_bytes(simple_ifc)["source_sha256"] != parse_ifc_bytes(other)["source_sha256"]

    def test_is_set_even_when_the_parse_fails(self):
        """A caller must still be able to cache 'these bytes are unparseable'."""
        result = parse_ifc_bytes(b"garbage")
        assert result["source_sha256"] == hashlib.sha256(b"garbage").hexdigest()

    def test_helper_agrees_with_result(self, simple_ifc, parsed):
        assert sha256_of(simple_ifc) == parsed["source_sha256"]

    def test_file_and_bytes_paths_agree(self, tmp_path, simple_ifc):
        path = tmp_path / "model.ifc"
        path.write_bytes(simple_ifc)
        assert parse_ifc_file(path)["source_sha256"] == parse_ifc_bytes(simple_ifc)["source_sha256"]


# ---------------------------------------------------------------------------
# Rule 1 — guid is the join key
# ---------------------------------------------------------------------------


class TestGuidIsTheJoinKey:
    """Rule 1. Every downstream Issue.element_id is a guid from here."""

    def test_every_element_has_a_guid(self, parsed):
        assert all((e.guid or "").strip() for e in parsed["elements"])

    def test_guids_are_unique(self, parsed):
        guids = [e.guid for e in parsed["elements"]]
        assert len(guids) == len(set(guids))

    def test_index_is_keyed_by_guid(self, parsed):
        index = elements_by_guid(parsed)
        assert set(index) == {e.guid for e in parsed["elements"]}
        for guid, element in index.items():
            assert element.guid == guid

    def test_index_of_a_failed_parse_is_empty(self):
        assert elements_by_guid(parse_ifc_bytes(b"garbage")) == {}


class TestHierarchyDeduplication:
    """One entity must yield one element, whatever its IFC class hierarchy.

    ``parse_ifc_model`` calls ``by_type()`` once per class in
    ``IFC_SERVICE_LABELS``, and IFC classes nest: an ``IfcPipeSegment`` is also
    an ``IfcFlowSegment`` and an ``IfcDistributionElement``. Left alone that
    returns one physical element three times under one GlobalId, inflating
    counts and raising triplicate findings. Rule 1 makes that this contract's
    problem to solve.
    """

    def test_one_entity_yields_one_element(self):
        result = parse_ifc_bytes(build_ifc(specs=[("IfcPipeSegment", "P-01")]))
        assert result["element_count"] == 1

    def test_three_entities_yield_three_elements(self, parsed):
        assert parsed["element_count"] == 3

    def test_most_specific_class_is_kept(self):
        """Not IfcFlowSegment or IfcDistributionElement, which also match."""
        result = parse_ifc_bytes(build_ifc(specs=[("IfcPipeSegment", "P-01")]))
        assert result["elements"][0].ifc_type == "IfcPipeSegment"

    def test_collapse_is_reported_not_silent(self):
        result = parse_ifc_bytes(build_ifc(specs=[("IfcPipeSegment", "P-01")]))
        assert any("collapsed" in w for w in result["quality"]["warnings"])

    def test_type_counts_reflect_deduplicated_elements(self, parsed):
        assert parsed["type_counts"] == {"IfcPipeSegment": 2, "IfcValve": 1}

    def test_distinct_entities_are_not_collapsed(self):
        """Deduplication keys on GlobalId, so different entities all survive."""
        result = parse_ifc_bytes(
            build_ifc(specs=[("IfcValve", f"V-{i:02d}") for i in range(5)])
        )
        assert result["element_count"] == 5
        assert len({e.guid for e in result["elements"]}) == 5


# ---------------------------------------------------------------------------
# Quality warnings
# ---------------------------------------------------------------------------


class TestQualityWarnings:
    """Warnings report facts a reviewer would act on — never a verdict."""

    def test_clean_model_warns_about_nothing_structural(self, parsed):
        joined = " ".join(parsed["quality"]["warnings"])
        assert "no GlobalId" not in joined
        assert "more than one element" not in joined

    def test_model_with_no_mep_elements_is_flagged(self):
        empty = build_ifc(specs=[])
        result = parse_ifc_bytes(empty)
        assert result["quality"]["valid"] is True, "an empty model is readable, just uninteresting"
        assert any("No MEP service elements" in w for w in result["quality"]["warnings"])

    def test_unnamed_elements_get_a_synthesised_name(self):
        """``parse_ifc_model`` substitutes ``<IfcType>_<id>`` for a blank Name.

        Recorded because it means a nameless element is never invisible, and a
        warning about unnamed elements would be dead code.
        """
        result = parse_ifc_bytes(build_ifc(specs=[("IfcPipeSegment", None)]))
        assert result["elements"]
        assert result["elements"][0].name.startswith("IfcPipeSegment_")

    def test_unidentified_material_is_flagged(self):
        """Corrosion cannot be evaluated without a material — say so."""
        result = parse_ifc_bytes(build_ifc(specs=[("IfcPipeSegment", "P-01")]))
        assert any("unidentified material" in w for w in result["quality"]["warnings"])

    def test_warnings_are_strings(self, parsed):
        assert all(isinstance(w, str) for w in parsed["quality"]["warnings"])

    def test_improvements_stay_empty(self, parsed):
        """Generating improvements runs the improver, which writes (rule 3)."""
        assert parsed["quality"]["improvements"] == []


# ---------------------------------------------------------------------------
# Rule 3 — parsing never writes
# ---------------------------------------------------------------------------


class TestParsingNeverWrites:
    """Rule 3. No storage mutation, no database write, no disk cache."""

    def test_no_files_are_created_or_modified(self, tmp_path, simple_ifc):
        path = tmp_path / "model.ifc"
        path.write_bytes(simple_ifc)
        before = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*")}

        parse_ifc_file(path)

        after = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*")}
        assert after == before, "parsing must not create, delete or touch files"

    def test_module_imports_no_persistence(self):
        """A parser that cannot reach storage or the database cannot write.

        Inspects the import graph via AST rather than grepping the source, so
        that naming a service in a docstring — to explain why it is *not* used
        — does not fail the test.
        """
        import ast

        import app.modules.phase_6.phase_6b_parsing as mod

        tree = ast.parse(open(mod.__file__, encoding="utf-8").read())
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
                imported.update(f"{node.module}.{a.name}" for a in node.names)

        forbidden = ("persistence", "supabase", "object_storage", "projects_service", "sqlite")
        offenders = [m for m in imported if any(f in m.lower() for f in forbidden)]
        assert not offenders, f"parser must not import persistence: {offenders}"


# ---------------------------------------------------------------------------
# Schema handling
# ---------------------------------------------------------------------------


class TestSchemaHandling:
    """IFC2X3 omits IFC4 MEP classes; the note tells the user why counts differ."""

    def test_ifc4_gets_no_compatibility_note(self, parsed):
        assert parsed["schema_note"] is None

    def test_ifc2x3_gets_a_compatibility_note(self):
        result = parse_ifc_bytes(build_ifc(schema="IFC2X3", specs=[("IfcFlowSegment", "P-01")]))
        assert result["quality"]["valid"] is True
        assert result["schema_note"] is not None
        assert "IFC2X3" in result["schema_note"]

    def test_failed_parse_has_no_schema_note(self):
        assert parse_ifc_bytes(b"garbage")["schema_note"] is None


# ---------------------------------------------------------------------------
# summarise() — the bridge to AnalysisResult (§2)
# ---------------------------------------------------------------------------


class TestSummarise:
    """Keys must match the AnalysisResult names in data contracts §2."""

    def test_keys_match_the_analysis_result_contract(self, parsed):
        assert set(summarise(parsed)) == {
            "ifc_element_count",
            "ifc_type_counts",
            "ifc_error",
            "ifc_quality_warnings",
            "ifc_schema_note",
        }

    def test_values_track_the_parse(self, parsed):
        summary = summarise(parsed)
        assert summary["ifc_element_count"] == parsed["element_count"]
        assert summary["ifc_type_counts"] == parsed["type_counts"]
        assert summary["ifc_error"] is None

    def test_error_surfaces_for_a_failed_parse(self):
        summary = summarise(parse_ifc_bytes(b"garbage"))
        assert summary["ifc_error"]
        assert summary["ifc_element_count"] == 0
