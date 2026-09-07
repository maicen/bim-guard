"""A data-quality note must name the ruleset revision that failed to reach a verdict.

MISMATCH 2 of ``docs/validation/final-verification-2026-09-09.md``: 246 of the
282 data-quality notes on project 1917 carried no ``ruleset_version`` at all,
while every verdict finding of the same five engines carried one. A note saying
"GC-001 could not assess this element" is only re-checkable against the ruleset
revision that could not assess it, so the note needs the stamp for the same
reason the verdict does.

The stamp is resolved in orchestration from the engine module or the rule pack
that the run loaded -- never written out here -- so a note and a verdict of the
same engine cannot say different things. These tests assert exactly that
equality, per engine.

Run: uv run pytest tests/test_data_quality_ruleset_version.py -v
"""

from __future__ import annotations

import dataclasses

import pytest

from app.engines import bimguard_corrosion_engine, bimguard_crevice_engine, bimguard_mic_engine
from app.modules.comparator import material_media
from app.modules.ifc_reader import piping_fixtures as fx
from app.modules.ifc_reader.ifc_parser import ServiceElement
from app.modules.phase_6.phase_6c_corrosion_ui import DATA_QUALITY, run_corrosion_analysis

#: Engine code -> (module, result dataclass). The dataclass's
#: ``ruleset_version`` default is what every verdict of that engine carries, so
#: it is the value a data-quality note has to match.
ENGINES = {
    "GC-001": (bimguard_corrosion_engine, bimguard_corrosion_engine.GCResult),
    "CC-001": (bimguard_crevice_engine, bimguard_crevice_engine.CCResult),
    "MC-001": (bimguard_mic_engine, bimguard_mic_engine.MICResult),
}


def _verdict_stamp(result_class) -> str:
    """The ``ruleset_version`` every result of this engine carries by default."""
    for field in dataclasses.fields(result_class):
        if field.name == "ruleset_version":
            return field.default
    raise AssertionError(f"{result_class.__name__} has no ruleset_version field")


def _element(**overrides) -> ServiceElement:
    base = dict(
        guid="GUID-01",
        name="CHW-Supply-01",
        ifc_type="IfcPipeSegment",
        description="Pipework",
        material_a="stainless_316",
        material_b="galvanised_steel",
        location_tag="swimming_pool",
        floor="Level 02",
        system="Chilled water",
        joint_type="JT-001",
        anode_area_m2=0.05,
        cathode_area_m2=0.50,
        position=(1.0, 2.0, 3.0),
        length_m=2.5,
    )
    base.update(overrides)
    return ServiceElement(**base)


@pytest.fixture(scope="module")
def issues() -> list:
    """One run that produces both verdicts and notes for every engine.

    The first element scores; the second carries no material at all, so the
    per-element engines refuse it. The synthetic piping network gives MM-001
    and XM-001 something to run over, which is the only way they produce
    either.
    """
    parsed = {
        "source_ref": "uploads/ifc/test.ifc",
        "source_sha256": "0" * 64,
        "schema": "IFC4",
        "schema_note": None,
        "elements": [
            _element(),
            _element(guid="GUID-02", material_a="Unknown", material_b=None),
        ],
        "piping_elements": fx.generate_synthetic_piping_network(),
        "quality": {"valid": True, "error": None},
    }
    return run_corrosion_analysis(parsed, include_low=True)["audit_issues"]


def _notes(issues: list, code: str) -> list:
    return [
        i
        for i in issues
        if i.mechanism == DATA_QUALITY and str(i.rule_id or "").startswith(code)
    ]


def _verdicts(issues: list, code: str) -> list:
    return [
        i
        for i in issues
        if i.mechanism != DATA_QUALITY and str(i.rule_id or "").startswith(code)
    ]


class TestPerElementEngines:
    """GC-001, CC-001 and MC-001 stamp their notes from the engine's own constant."""

    @pytest.mark.parametrize("code", sorted(ENGINES))
    def test_a_note_carries_the_engines_verdict_stamp(self, issues, code):
        notes = _notes(issues, code)
        assert notes, f"{code} produced no data-quality note to assert on"

        _module, result_class = ENGINES[code]
        expected = _verdict_stamp(result_class)
        assert expected, f"{code} has no default ruleset_version to compare against"

        note = notes[0]
        assert note.metadata.get("ruleset_version") == expected

    @pytest.mark.parametrize("code", sorted(ENGINES))
    def test_the_stamp_is_the_engine_modules_own(self, issues, code):
        """Resolved from the engine, not written out in the orchestration layer."""
        module, _result_class = ENGINES[code]
        assert _notes(issues, code)[0].metadata["ruleset_version"] == module.RULESET_VERSION

    @pytest.mark.parametrize("code", ["GC-001", "CC-001"])
    def test_a_note_and_a_verdict_of_one_engine_agree(self, issues, code):
        """Directly, on two Issues from the same run. GC and CC reach both."""
        verdicts = _verdicts(issues, code)
        assert verdicts, f"{code} produced no verdict to compare against"
        assert (
            _notes(issues, code)[0].metadata["ruleset_version"]
            == verdicts[0].metadata["ruleset_version"]
        )


class TestNetworkComparators:
    """MM-001 stamps its notes from the pack its findings were scored from."""

    def test_an_mm001_note_carries_the_packs_stamp(self, issues):
        notes = _notes(issues, "MM-001")
        assert notes, "MM-001 produced no data-quality note to assert on"
        expected = material_media.ruleset_version(material_media.load_rule_pack())
        assert notes[0].metadata.get("ruleset_version") == expected

    def test_an_mm001_note_and_finding_agree(self, issues):
        verdicts = _verdicts(issues, "MM-001")
        assert verdicts, "MM-001 produced no finding to compare against"
        assert (
            _notes(issues, "MM-001")[0].metadata["ruleset_version"]
            == verdicts[0].metadata["ruleset_version"]
        )


def test_no_issue_of_this_run_is_unstamped(issues):
    """The whole point: not one row leaves without saying what produced it."""
    assert issues, "empty run -- every assertion above would be vacuous"
    unstamped = [i for i in issues if not (i.metadata or {}).get("ruleset_version")]
    assert unstamped == [], [
        (i.id, i.rule_id, i.mechanism) for i in unstamped
    ]
