"""MC-001 temperature classes: numeric bounds, and what happens without them.

WHY THIS FILE EXISTS

    The six MC-001.TEMP.* rules carried only a human range string ("25-45°C").
    classify_temperature compares against t_min/t_max, and the catalog coerced
    the absent values to 0.0, so ``t_min <= t < t_max`` was false for every
    real temperature and every element fell through to the T4_SAFE_HOT
    fallback -- risk 0.05, the LOWEST of the six. Measured on a 420-element
    demo model: 294 of 294 scored elements classified T4_SAFE_HOT, chilled
    water at 6 °C and domestic hot water at 60 °C alike.

    Nothing looked broken. The scores stayed plausible, the bands stayed
    sensible, and the temperature term had simply stopped contributing. That
    is the failure this file guards: not a crash, a silent zero.

    Two halves, and both matter:

      1. With bounds seeded, each temperature lands in its published class.
      2. Without them, the run says so. A class that cannot be evaluated is
         dropped from the catalog and reported as a run-level data_quality
         issue, rather than silently becoming T4_SAFE_HOT.

NO LIVE DATABASE. Rule rows are synthesised exactly as ruleset_seeder writes
them and fed through the real catalog builder, so the test exercises the
seeder -> catalog -> engine path without touching Supabase. The migration that
puts these bounds into the live rows has deliberately not been run.

Run: uv run pytest tests/test_mc001_temperature_bounds.py -v
"""

from __future__ import annotations

import json

import pytest

from app.engines import bimguard_mic_engine
from app.services import corrosion_rule_catalog
from app.services.ruleset_seeder import _TEMPERATURE_BOUNDS, _temperature_bounds

#: The published range string for each class, as the ruleset states it. Kept
#: here so a bounds change that contradicts the published range fails loudly.
PUBLISHED_RANGES = {
    "T0_COLD": "< 20°C",
    "T1_MARGINAL": "20–25°C",
    "T2_DANGER": "25–45°C",
    "T3_TOLERABLE": "45–55°C",
    "T4_SAFE_HOT": "> 55°C",
    "T5_UNKNOWN": "Unknown",
}

RISKS = {
    "T0_COLD": 0.15,
    "T1_MARGINAL": 0.35,
    "T2_DANGER": 1.0,
    "T3_TOLERABLE": 0.45,
    "T4_SAFE_HOT": 0.05,
    "T5_UNKNOWN": 0.65,
}


def seeder_rows(*, with_bounds: bool) -> list[dict]:
    """Build the MC-001.TEMP.* rows exactly as ruleset_seeder writes them.

    Args:
        with_bounds: Include the numeric t_min/t_max the seeder now emits.
            ``False`` reproduces the rows as they stand in the live database
            today, before the migration.
    """
    rows = []
    for key, published in PUBLISHED_RANGES.items():
        params = {"range": published, "risk": RISKS[key], "class_key": key}
        if with_bounds:
            params.update(_temperature_bounds(key))
        rows.append(
            {
                "rule_type": "temperature_class",
                "reference": f"MC-001.TEMP.{key}",
                "description": f"{key} — {published}: risk {RISKS[key]}",
                "check_value": RISKS[key],
                "unit": "°C",
                "parameters": json.dumps(params),
            }
        )
    return rows


@pytest.fixture
def catalog_from_seeder(monkeypatch):
    """Build a real MC catalog from synthesised seeder rows, no database."""

    def build(*, with_bounds: bool) -> dict:
        monkeypatch.setattr(
            corrosion_rule_catalog, "_rules_for", lambda _id: seeder_rows(with_bounds=with_bounds)
        )
        return corrosion_rule_catalog.load_mc_catalog()

    return build


@pytest.fixture
def classify_with(monkeypatch, catalog_from_seeder):
    """Point the engine's class table at a catalog and return classify_temperature."""

    def use(*, with_bounds: bool):
        catalog = catalog_from_seeder(with_bounds=with_bounds)
        monkeypatch.setattr(
            bimguard_mic_engine, "TEMPERATURE_CLASSES", catalog["temperature_classes"]
        )
        return bimguard_mic_engine.classify_temperature, catalog

    return use


# ---------------------------------------------------------------------------
# 1. With bounds, every temperature lands in its published class
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "temperature, expected",
    [
        (10.0, "T0_COLD"),
        (22.0, "T1_MARGINAL"),
        (35.0, "T2_DANGER"),
        (50.0, "T3_TOLERABLE"),
        (65.0, "T4_SAFE_HOT"),
        (None, "T5_UNKNOWN"),
    ],
)
def test_classify_temperature_lands_in_the_published_class(
    classify_with, temperature, expected
):
    """The six cases from the ruleset's own range strings."""
    classify, _ = classify_with(with_bounds=True)
    assert classify(temperature)[0] == expected


def test_boundary_temperatures_belong_to_the_warmer_class(classify_with):
    """Shared endpoints resolve one way only; no temperature matches two rows.

    The intervals are half-open [t_min, t_max), so 25.0 is T2_DANGER and not
    T1_MARGINAL. Worth pinning: an off-by-one here would put the bottom of the
    Legionella danger zone in the marginal class, at a third of the risk.
    """
    classify, _ = classify_with(with_bounds=True)
    assert classify(20.0)[0] == "T1_MARGINAL"
    assert classify(25.0)[0] == "T2_DANGER"
    assert classify(45.0)[0] == "T3_TOLERABLE"
    assert classify(55.0)[0] == "T4_SAFE_HOT"


def test_the_danger_zone_carries_the_highest_risk(classify_with):
    """35 °C is the worst temperature for MIC, and now scores as such."""
    classify, _ = classify_with(with_bounds=True)
    _, danger = classify(35.0)
    _, safe = classify(65.0)
    assert danger["risk"] == 1.0
    assert safe["risk"] == 0.05
    assert danger["risk"] > safe["risk"]


def test_seeder_bounds_cover_every_class_but_the_unknown_one(classify_with):
    """Five bounded classes reach the catalog; T5_UNKNOWN reaches it unbounded."""
    _, catalog = classify_with(with_bounds=True)
    classes = catalog["temperature_classes"]

    assert set(classes) == set(PUBLISHED_RANGES)
    assert not catalog["temperature_bounds_missing"]
    for key in _TEMPERATURE_BOUNDS:
        assert classes[key]["t_min"] == _TEMPERATURE_BOUNDS[key][0]
        assert classes[key]["t_max"] == _TEMPERATURE_BOUNDS[key][1]
    # The one class selected by name rather than by comparison.
    assert "t_min" not in classes["T5_UNKNOWN"]


def test_the_range_string_survives_the_bounds(classify_with):
    """Bounds are added alongside the published range, not instead of it."""
    _, catalog = classify_with(with_bounds=True)
    for key, published in PUBLISHED_RANGES.items():
        assert catalog["temperature_classes"][key]["range"] == published


# ---------------------------------------------------------------------------
# 2. Without bounds, the run says so instead of scoring everything safe
# ---------------------------------------------------------------------------


def test_a_class_without_bounds_is_dropped_not_zeroed(catalog_from_seeder):
    """The unbounded classes are omitted and named, not given a 0.0..0.0 range."""
    catalog = catalog_from_seeder(with_bounds=False)

    assert sorted(catalog["temperature_bounds_missing"]) == [
        "T0_COLD",
        "T1_MARGINAL",
        "T2_DANGER",
        "T3_TOLERABLE",
        "T4_SAFE_HOT",
    ]
    # T5_UNKNOWN is the exception: no bounds is correct for it.
    assert set(catalog["temperature_classes"]) == {"T5_UNKNOWN"}


def test_missing_bounds_surface_as_a_run_level_data_quality_issue(monkeypatch):
    """phase_6c raises one unattributed data_quality issue naming the classes."""
    from app.modules.phase_6 import phase_6c_corrosion_ui as phase_6c

    monkeypatch.setattr(
        corrosion_rule_catalog,
        "_rules_for",
        lambda _id: seeder_rows(with_bounds=False),
    )
    issues = phase_6c._ruleset_data_quality_issues(
        phase_6c.IssueIdAllocator("TEST")
    )

    assert len(issues) == 1
    issue = issues[0]
    assert issue.mechanism == phase_6c.DATA_QUALITY
    assert issue.metadata["check"] == phase_6c.RULESET_TEMPERATURE_BOUNDS_MISSING
    assert issue.metadata["mechanism_code"] == "MC-001"
    assert "T2_DANGER" in issue.metadata["classes"]
    # Run-level, not attributable to any one element.
    assert issue.element_id == ""


def test_seeded_bounds_raise_no_data_quality_issue(monkeypatch):
    """A correctly seeded ruleset is silent -- the issue reports a real gap."""
    from app.modules.phase_6 import phase_6c_corrosion_ui as phase_6c

    monkeypatch.setattr(
        corrosion_rule_catalog,
        "_rules_for",
        lambda _id: seeder_rows(with_bounds=True),
    )
    assert (
        phase_6c._ruleset_data_quality_issues(phase_6c.IssueIdAllocator("TEST")) == []
    )


def _parsed(elements):
    """Minimal ParsedIFC wrapper for run_corrosion_analysis."""
    return {"quality": {"valid": True}, "elements": elements, "piping_elements": []}


def _element(**overrides):
    """Build a scoreable element: material resolved, hydraulics present."""
    from app.modules.ifc_reader.ifc_parser import ServiceElement

    base = dict(
        guid="GUID-01",
        name="DHW dead leg",
        ifc_type="IfcPipeSegment",
        description="Pipework",
        material_a="carbon_steel",
        material_b=None,
        location_tag="interior_conditioned",
        floor="Level 01",
        system="DOMESTICHOTWATER",
        joint_type="JT-001",
        anode_area_m2=0.05,
        cathode_area_m2=0.50,
        position=(0.0, 0.0, 0.0),
        length_m=1.0,
    )
    base.update(overrides)
    return ServiceElement(**base)


def _bounds_issues(issues):
    """Return the run-level temperature-bounds issues among ``issues``."""
    from app.modules.phase_6 import phase_6c_corrosion_ui as phase_6c

    return [
        i
        for i in issues
        if (i.metadata or {}).get("check") == phase_6c.RULESET_TEMPERATURE_BOUNDS_MISSING
    ]


def _with_hydraulics(monkeypatch, phase_6c, *, velocity, temperature, dead_leg):
    """Make _mic_element supply hydraulics, so MC-001 clears the pre-flight gate.

    ServiceElement on this branch carries no hydraulic fields, so _mic_element
    builds a MICElement with all three None and the gate refuses every element
    — MC-001 scores nothing and the run-level issue could never fire. That is
    the state of main today, not a property of this change; the parser work
    that populates those fields lands separately. Patching the builder here
    stands in for it, so the wiring under test is exercised rather than
    blocked by an unrelated gap.
    """
    original = phase_6c._mic_element

    def build(element):
        base = original(element)
        base.flow_velocity_ms = velocity
        base.operating_temp_c = temperature
        base.dead_leg_length_m = dead_leg
        return base

    monkeypatch.setattr(phase_6c, "_mic_element", build)


def _report_missing_bounds(monkeypatch):
    """Make the catalog report missing bounds without stripping the MC tables.

    Patched at load_mc_catalog rather than at _rules_for: the reporter reads
    the whole catalog, and feeding it temperature rows alone would leave the
    engine with no material or system tables and fail the scoring these tests
    depend on. Only the one key under test is overridden.
    """
    real = corrosion_rule_catalog.load_mc_catalog

    def patched():
        return {**real(), "temperature_bounds_missing": ["T2_DANGER", "T4_SAFE_HOT"]}

    monkeypatch.setattr(corrosion_rule_catalog, "load_mc_catalog", patched)


def test_the_gap_is_reported_once_when_mc001_actually_scores(monkeypatch):
    """One run-level issue per run, not one per element."""
    from app.modules.phase_6 import phase_6c_corrosion_ui as phase_6c

    _report_missing_bounds(monkeypatch)
    _with_hydraulics(monkeypatch, phase_6c, velocity=0.0, temperature=35.0, dead_leg=0.55)

    issues = phase_6c.run_corrosion_analysis(
        _parsed([_element(guid="G1"), _element(guid="G2")]),
        engines=["MC-001"],
        include_low=True,
        run_id="T",
    )["audit_issues"]

    # Two elements scored, one issue: run-level, not per element.
    assert len(_bounds_issues(issues)) == 1
    assert len(issues) > 1, "the MC-001 verdicts themselves should be there too"


def test_the_gap_is_not_reported_when_mc001_scored_nothing(monkeypatch):
    """An all-gated run says nothing about bounds that changed no verdict.

    The refusals are the story on such a run; a rules gap that could not have
    affected anything would only compete with them for attention.
    """
    from app.modules.phase_6 import phase_6c_corrosion_ui as phase_6c

    _report_missing_bounds(monkeypatch)
    # No hydraulics: the pre-flight gate refuses MC-001 on this element.
    issues = phase_6c.run_corrosion_analysis(
        _parsed([_element()]), engines=["MC-001"], include_low=True, run_id="T"
    )["audit_issues"]

    assert _bounds_issues(issues) == []
    assert issues, "the gate's own refusal should still be reported"


def test_without_bounds_every_temperature_collapses_to_safe_hot(classify_with):
    """The defect itself, pinned: this is what the fix has to prevent.

    Kept as a test rather than a comment because it is the only thing that
    shows *why* dropping the class is not enough on its own -- the engine's
    fallback still answers T4_SAFE_HOT, so the data_quality issue above is
    what carries the information, not the classification.
    """
    classify, _ = classify_with(with_bounds=False)
    for temperature in (10.0, 22.0, 35.0, 50.0, 65.0):
        assert classify(temperature)[0] == "T4_SAFE_HOT"
