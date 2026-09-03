"""Schema-conformance tests for the engine-level BCF writers.

``generate_gc_bcf``, ``generate_cc_bcf`` and ``generate_mic_bcf`` used to
hand-write their own ``markup.bcf`` / ``viewpoint.bcfv`` and failed the
buildingSMART XSDs in several ways (a ``Components`` block inside ``Topic``,
no ``Viewpoints`` link, no ``Visibility``, no ``bcf.version``). They now map
results onto ``BCFIssue`` and delegate to ``bcf_generator.generate_bcf``.
These tests pin that: every archive each writer produces validates against the
vendored BCF 2.1 schemas, with demo-style element ids (``GC-VAL-001A``) and
real IFC GlobalIds alike.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

xmlschema = pytest.importorskip(
    "xmlschema", reason="xmlschema is required for BCF schema validation (dev dependency group)"
)

SCHEMA_DIR = Path(__file__).parent / "schemas" / "bcf21"

ANODE_GUID = "2O2Fr$t4X7Zf8NOew3FLOH"
CATHODE_GUID = "0FQ6pMwzXBJucYaRTqfuw2"


@pytest.fixture(scope="module")
def schemas():
    """Official buildingSMART BCF 2.1 (markup, visinfo) schemas."""
    return (
        xmlschema.XMLSchema(SCHEMA_DIR / "markup.xsd"),
        xmlschema.XMLSchema(SCHEMA_DIR / "visinfo.xsd"),
    )


def _validate_archive(path: Path, schemas) -> list[str]:
    """Return every XSD violation across all XML parts; also asserts the layout."""
    markup_schema, visinfo_schema = schemas
    problems: list[str] = []
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        assert "bcf.version" in names, names
        assert "project.bcfp" in names, names
        topics = [n for n in names if n.endswith("markup.bcf")]
        assert topics, "archive holds no topics"
        for topic in topics:
            folder = topic.split("/")[0]
            assert f"{folder}/viewpoint.bcfv" in names
            assert f"{folder}/snapshot.png" in names
        for name in names:
            schema = (
                markup_schema
                if name.endswith("markup.bcf")
                else visinfo_schema
                if name.endswith("viewpoint.bcfv")
                else None
            )
            if schema is None:
                continue
            problems += [f"{name}: {e.reason}" for e in schema.iter_errors(zf.read(name).decode())]
    return problems


def _components(path: Path) -> list[ET.Element]:
    with zipfile.ZipFile(path) as zf:
        name = next(n for n in zf.namelist() if n.endswith("viewpoint.bcfv"))
        root = ET.fromstring(zf.read(name).decode())
    return root.findall("./Components/Selection/Component")


# ---------------------------------------------------------------------------
# GC-001
# ---------------------------------------------------------------------------


def _gc_elements():
    from app.engines.bimguard_corrosion_engine import GCElement

    return [
        # Demo-style ids: not IFC GlobalIds. Copper on galvanised steel in a
        # humid plant room is the engine's own "expected: Critical" scenario.
        GCElement(
            global_id_anode="GC-VAL-001A",
            global_id_cathode="GC-VAL-001B",
            material_anode="copper",
            material_cathode="galvanised steel",
            anode_area_m2=2.5,
            cathode_area_m2=12.0,
            zone_category="plant room",
            floor="B1",
            system_type="Chilled Water",
        ),
        # Real 22-char GlobalIds on both sides of the couple.
        GCElement(
            global_id_anode=ANODE_GUID,
            global_id_cathode=CATHODE_GUID,
            material_anode="carbon steel",
            material_cathode="aluminium",
            anode_area_m2=5.0,
            cathode_area_m2=1.0,
            zone_category="external",
            floor="RF",
            system_type="Drainage",
        ),
    ]


def test_gc_bcf_validates_against_xsd(tmp_path, schemas):
    from app.engines.bimguard_corrosion_engine import assess_galvanic_batch, generate_gc_bcf

    results = assess_galvanic_batch(_gc_elements())
    out = tmp_path / "gc.bcfzip"
    count = generate_gc_bcf(results, str(out))

    expected = sum(1 for r in results if r.risk_band != "Low")
    assert count == expected >= 1, "the plant-room copper/galvanised couple must raise a topic"
    problems = _validate_archive(out, schemas)
    assert not problems, "GC-001 archive schema violations:\n  " + "\n  ".join(problems)


def test_gc_viewpoint_selects_both_sides_of_the_couple(tmp_path, schemas):
    from app.engines.bimguard_corrosion_engine import assess_galvanic_batch, generate_gc_bcf

    results = assess_galvanic_batch(_gc_elements()[1:])  # real GlobalIds only
    out = tmp_path / "gc.bcfzip"
    if generate_gc_bcf(results, str(out)) == 0:
        pytest.skip("carbon steel / aluminium external scored Low under the live catalog")

    # The engine may swap the sides so the less noble metal is the anode, so
    # follow the result rather than the input order: anode first, then cathode.
    (result,) = results
    assert {result.global_id_anode, result.global_id_cathode} == {ANODE_GUID, CATHODE_GUID}
    assert [c.get("IfcGuid") for c in _components(out)] == [
        result.global_id_anode,
        result.global_id_cathode,
    ]
    assert not _validate_archive(out, schemas)


def test_gc_demo_ids_never_become_ifcguid(tmp_path, schemas):
    from app.engines.bimguard_corrosion_engine import assess_galvanic_batch, generate_gc_bcf

    results = assess_galvanic_batch(_gc_elements()[:1])
    out = tmp_path / "gc.bcfzip"
    assert generate_gc_bcf(results, str(out)) == 1

    components = _components(out)
    assert [c.get("IfcGuid") for c in components] == [None, None]
    # Both demo labels survive in AuthoringToolId (anode first, per the result).
    (result,) = results
    assert [c.find("AuthoringToolId").text for c in components] == [
        result.global_id_anode,
        result.global_id_cathode,
    ]
    assert {result.global_id_anode, result.global_id_cathode} == {"GC-VAL-001A", "GC-VAL-001B"}
    assert not _validate_archive(out, schemas)


def test_gc_writes_nothing_when_everything_is_low(tmp_path):
    from app.engines.bimguard_corrosion_engine import GCResult, generate_gc_bcf

    low = GCResult(
        global_id_anode="a", global_id_cathode="b", material_anode_label="x",
        material_cathode_label="y", material_anode_key="x", material_cathode_key="y",
        floor="", system_type="", voltage_gap_v=0.0, env_threshold_v=0.15, voltage_risk=0.0,
        area_ratio=1.0, area_ratio_band="", area_ratio_risk=0.0, environment_class="",
        environment_label="", environment_multiplier=0.0, pren_adequate=True, pren_note="",
        composite_score=0.0, risk_band="Low", bcf_priority="Minor", mitigations=[],
    )
    out = tmp_path / "gc.bcfzip"
    assert generate_gc_bcf([low], str(out)) == 0
    assert not out.exists()


# ---------------------------------------------------------------------------
# CC-001
# ---------------------------------------------------------------------------


def _cc_elements():
    from app.engines.bimguard_crevice_engine import CCElement

    return [
        CCElement(
            global_id="CC-VAL-001",
            element_type="IfcPipeSegment",
            material="SS 316",
            joint_description="weld neck flange",
            operating_temp_c=35.0,
            zone_category="pool",
            system_type="Pool Plant",
            floor="B1",
        ),
        CCElement(
            global_id=ANODE_GUID,
            element_type="IfcPipeFitting",
            material="SS 316",
            joint_description="threaded",
            operating_temp_c=40.0,
            zone_category="plant room",
            system_type="Hot Water",
            floor="B2",
        ),
    ]


def test_cc_bcf_validates_against_xsd(tmp_path, schemas):
    from app.engines.bimguard_crevice_engine import assess_crevice_batch, generate_cc_bcf

    results = assess_crevice_batch(_cc_elements())
    out = tmp_path / "cc.bcfzip"
    count = generate_cc_bcf(results, str(out))

    assert count == sum(1 for r in results if r.risk_band != "Low") >= 1
    problems = _validate_archive(out, schemas)
    assert not problems, "CC-001 archive schema violations:\n  " + "\n  ".join(problems)

    guids = {c.get("IfcGuid") for c in _components(out)}
    assert "CC-VAL-001" not in guids, "a demo label must not be written as IfcGuid"


# ---------------------------------------------------------------------------
# MC-001
# ---------------------------------------------------------------------------


def _mic_elements():
    from app.engines.bimguard_mic_engine import MICElement

    return [
        MICElement(
            global_id="MIC-VAL-001",
            element_type="IfcPipeSegment",
            system_type="DOMESTICCOLDWATER",
            material="carbon_steel",
            nominal_diameter_m=0.050,
            flow_velocity_ms=0.0,
            operating_temp_c=28.0,
            dead_leg_length_m=2.5,
            insulation_condition="none",
            floor="B1",
            zone="Plant Room",
        ),
        MICElement(
            global_id=CATHODE_GUID,
            element_type="IfcPipeSegment",
            system_type="FIREPROTECTION",
            material="carbon_steel",
            nominal_diameter_m=0.080,
            flow_velocity_ms=0.0,
            operating_temp_c=22.0,
            dead_leg_length_m=8.0,
            insulation_condition="none",
            floor="B2",
            zone="Car Park",
        ),
    ]


def test_mic_bcf_validates_against_xsd(tmp_path, schemas):
    from app.engines.bimguard_mic_engine import assess_mic_batch, generate_mic_bcf

    results = assess_mic_batch(_mic_elements())
    out = tmp_path / "mic.bcfzip"
    count = generate_mic_bcf(results, str(out))

    assert count == sum(1 for r in results if r.risk_band != "Low") >= 1
    problems = _validate_archive(out, schemas)
    assert not problems, "MC-001 archive schema violations:\n  " + "\n  ".join(problems)

    guids = {c.get("IfcGuid") for c in _components(out)}
    assert "MIC-VAL-001" not in guids


# ---------------------------------------------------------------------------
# Demo output locations
# ---------------------------------------------------------------------------


def test_demo_outputs_stay_out_of_the_repo_root():
    """CLAUDE.md forbids files at the repo root; the demos used to write ``output/``."""
    from app.engines import bimguard_corrosion_engine as gc
    from app.engines import bimguard_crevice_engine as cc
    from app.engines import bimguard_mic_engine as mc

    for module in (gc, cc, mc):
        assert module.DEMO_BCF_PATH.startswith("docs/bcf_exports/")
        assert module.DEMO_BCF_PATH.endswith(".bcfzip")
        assert module.DEMO_CSV_PATH.startswith("docs/validation/data/")
