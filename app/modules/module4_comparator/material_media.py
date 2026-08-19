"""
MM-001 Material-Media Compatibility comparator (Path B).

Scores each piping element on the degradation risk of its material carrying
its medium, modified by environmental severity and operating temperature.
Unlike GC-001, which assesses element PAIRS, MM-001 is a per-element check:
a single pipe in the wrong service is a finding on its own.

INPUT
    list[PipingElement] from the Module 2 producer, plus a rule pack.

OUTPUT
    list[Issue] — one Issue per element at Medium band or above, plus one
    data-quality Issue per element that cannot be scored. Compliant elements
    produce no Issue.

COMPOSITE SCORE
    score = 0.40*material_media + 0.35*environment_severity + 0.25*temperature_stress

    Weights come from rule_pack["parameters"]["weights"].

KINETICS GUARD
    When the material-media cell is below the guard threshold the pairing is
    benign and there is no dominant mechanism for temperature to accelerate.
    The temperature term is capped so that operating temperature alone cannot
    escalate a compatible material. Without it, copper in 60 C domestic hot
    water scores Medium — flagging the storage temperature that HSE HSG274
    mandates and that the MC-001 engine requires.

MEDIA DERIVATION
    PipingElement carries no media field; media is derived from `system` via
    piping_producer.media_for_system, keeping system classification
    single-sourced.

WHY UNMAPPED PAIRINGS ARE NOT SCORED
    An absent matrix cell means nobody has assessed that combination. Scoring
    it as benign would report an unverified pairing as compliant, which is the
    failure direction that matters in a compliance tool. Such elements get a
    data-quality Issue instead.

RULE PACK SHAPE (rule_pack["parameters"])
    compatibility_matrix: {material: {media: {score, years, mech, cite, conf}}}
    environment_severity: {EnvironmentClass.value: {severity, cite, ...}}
    temperature_stress: {bands: [{min_c, max_c, stress, cite, ...}], ...}
    kinetics_guard: {cell_below, cap_temperature_stress_at, cite, ...}
    weights: {material_media, environment_severity, temperature_stress}
    risk_band_thresholds: {medium, high, critical}

WHITE BOX AUDIT TRAIL
    Every Issue carries citations[] naming the standard behind each term that
    contributed, so a reviewer can trace the verdict back to its sources.
"""

from __future__ import annotations

from typing import Any, Optional

from ..module2_ifc_read.piping_producer import media_for_system
from ..module2_ifc_read.piping_schema import CANONICAL_MATERIALS, PipingElement
from .issue_schema import Issue, RiskBand, band_from_score, make_issue

MECHANISM = "MM-001 material-media"
RULE_REF_PREFIX = "MM-001"

_REQUIRED_KEYS = {
    "compatibility_matrix",
    "environment_severity",
    "temperature_stress",
    "weights",
    "risk_band_thresholds",
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compare(elements: list[PipingElement], rule_pack: dict) -> list[Issue]:
    """Run MM-001 material-media compliance against piping elements.

    Args:
        elements: Elements to assess.
        rule_pack: Rule pack whose "parameters" carry the matrix and tables.

    Returns:
        Issues for every element scoring Medium or above, plus data-quality
        Issues for elements that could not be scored. Compliant elements
        produce nothing.

    Raises:
        ValueError: If the rule pack is missing a required parameter key.
    """
    params = rule_pack.get("parameters", {})
    missing = _REQUIRED_KEYS - params.keys()
    if missing:
        raise ValueError(f"MM-001 rule pack is missing required keys: {sorted(missing)}")

    issues: list[Issue] = []
    counter = [0]

    for element in elements:
        issues.extend(_assess_element(element, params, counter))

    return issues


# ---------------------------------------------------------------------------
# Per-element assessment
# ---------------------------------------------------------------------------


def _assess_element(element: PipingElement, params: dict, counter: list) -> list[Issue]:
    """Assess one element, returning its Issues (possibly none)."""
    # ── Material must be identifiable ─────────────────────────────────────
    if element.material not in CANONICAL_MATERIALS or element.material == "Unknown":
        return [
            _data_quality(
                element,
                counter,
                check="material_normalisation",
                title=f"Material could not be identified on {_label(element)}",
                detail=(
                    "Review the IFC source and correct the material assignment. "
                    "Material-media compatibility cannot be evaluated until the "
                    "material is identified."
                ),
                metadata={"material_raw": element.material_raw},
            )
        ]

    media = media_for_system(element.system)
    matrix = params["compatibility_matrix"]
    cell = matrix.get(element.material, {}).get(media)

    # ── Unmapped pairing is never scored as benign ────────────────────────
    if cell is None:
        return [
            _data_quality(
                element,
                counter,
                check="unmapped_pairing",
                title=f"No compatibility data for {element.material} in {media}",
                detail=(
                    f"The rule pack holds no cell for {element.material} carrying "
                    f"{media}. This pairing has not been assessed, so no verdict "
                    "can be issued. Extend the matrix or confirm the system "
                    "classification is correct."
                ),
                metadata={"material": element.material, "media": media},
            )
        ]

    # ── Environment severity ──────────────────────────────────────────────
    env_entry = params["environment_severity"].get(element.environment_class.value, {})
    env_severity = env_entry.get("severity")
    if env_severity is None:
        return [
            _data_quality(
                element,
                counter,
                check="environment_unclassified",
                title=f"Environment not classified for {_label(element)}",
                detail=(
                    "Environmental severity could not be determined, so the "
                    "composite score cannot be computed. Scoring an unclassified "
                    "environment as benign would suppress findings on every "
                    "element the producer could not classify."
                ),
                metadata={
                    "environment_class": element.environment_class.value,
                    "environment_source": element.environment_source,
                },
            )
        ]

    # ── Temperature stress ────────────────────────────────────────────────
    stress = _temperature_stress(element.operating_temperature_c, params["temperature_stress"])
    if stress is None:
        return [
            _data_quality(
                element,
                counter,
                check="temperature_missing",
                title=f"Operating temperature missing on {_label(element)}",
                detail=(
                    "operating_temperature_c is absent, so the temperature term "
                    "cannot be evaluated. Substituting a default would put a "
                    "fabricated input into a compliance verdict."
                ),
                metadata={"material": element.material, "media": media},
            )
        ]

    # ── Kinetics guard ────────────────────────────────────────────────────
    guard = params.get("kinetics_guard") or {}
    guard_applied = False
    stress_effective = stress
    threshold = guard.get("cell_below")
    cap = guard.get("cap_temperature_stress_at")
    if threshold is not None and cap is not None and cell["score"] < threshold:
        guard_applied = True
        stress_effective = min(stress, cap)

    # ── Composite ─────────────────────────────────────────────────────────
    weights = params["weights"]
    score = (
        weights["material_media"] * cell["score"]
        + weights["environment_severity"] * env_severity
        + weights["temperature_stress"] * stress_effective
    )
    band = band_from_score(score, params["risk_band_thresholds"])

    if band is RiskBand.LOW:
        return []

    return [
        _finding(
            element,
            counter,
            media=media,
            cell=cell,
            env_entry=env_entry,
            env_severity=env_severity,
            stress=stress,
            stress_effective=stress_effective,
            guard_applied=guard_applied,
            guard=guard,
            score=score,
            band=band,
            params=params,
        )
    ]


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def _temperature_stress(temperature_c: Optional[float], table: dict) -> Optional[float]:
    """Return the stress value for a temperature, or None when unresolvable.

    Bands are inclusive of min_c and exclusive of max_c; a null bound is
    unbounded on that side.
    """
    if temperature_c is None:
        return None
    for band in table.get("bands", []):
        low = band.get("min_c")
        high = band.get("max_c")
        low = float("-inf") if low is None else low
        high = float("inf") if high is None else high
        if low <= temperature_c < high:
            return band.get("stress")
    return None


def _temperature_citation(temperature_c: Optional[float], table: dict) -> Optional[str]:
    """Return the citation of the band a temperature falls in."""
    if temperature_c is None:
        return None
    for band in table.get("bands", []):
        low = band.get("min_c")
        high = band.get("max_c")
        low = float("-inf") if low is None else low
        high = float("inf") if high is None else high
        if low <= temperature_c < high:
            return band.get("cite")
    return None


def _label(element: PipingElement) -> str:
    """Return a short human-readable element label."""
    return element.name or element.id[:8]


# ---------------------------------------------------------------------------
# Issue construction
# ---------------------------------------------------------------------------


def _finding(
    element: PipingElement,
    counter: list,
    *,
    media: str,
    cell: dict,
    env_entry: dict,
    env_severity: float,
    stress: float,
    stress_effective: float,
    guard_applied: bool,
    guard: dict,
    score: float,
    band: RiskBand,
    params: dict,
) -> Issue:
    """Build the Issue for an element that scored Medium or above."""
    counter[0] += 1

    citations: list[dict] = [
        {
            "standard": cell.get("cite", ""),
            "clause": f"{element.material} / {media}",
            "reason": (
                f"material-media compatibility {cell['score']:.2f} "
                f"({cell.get('mech', 'unspecified mechanism')})"
            ),
        },
        {
            "standard": env_entry.get("cite", ""),
            "clause": element.environment_class.value,
            "reason": f"environment severity {env_severity:.2f}",
        },
    ]
    temperature_cite = _temperature_citation(
        element.operating_temperature_c, params["temperature_stress"]
    )
    if temperature_cite:
        citations.append(
            {
                "standard": temperature_cite,
                "clause": f"{element.operating_temperature_c} C",
                "reason": f"temperature stress {stress:.2f}",
            }
        )
    if guard_applied:
        citations.append(
            {
                "standard": guard.get("cite", ""),
                "clause": "kinetics_guard",
                "reason": (
                    f"benign pairing (cell {cell['score']:.2f} below "
                    f"{guard.get('cell_below')}); temperature term capped "
                    f"{stress:.2f} -> {stress_effective:.2f}"
                ),
            }
        )

    weights = params["weights"]
    return make_issue(
        id=f"BGR-{counter[0]:04d}",
        element_id=element.id,
        rule_id=f"{RULE_REF_PREFIX}.{element.material}.{media}",
        title=(
            f"{element.material} in {media.replace('_', ' ')} - "
            f"{cell.get('mech', 'compatibility risk').replace('_', ' ')}"
        ),
        description=(
            f"{_label(element)} carries {media.replace('_', ' ')} in a "
            f"{element.environment_class.value} environment at "
            f"{element.operating_temperature_c} C. Composite "
            # 3 dp to match make_issue's stored precision, so the prose and
            # Issue.score never disagree. Exact terms are in metadata.
            f"{round(score, 3)} = {weights['material_media']}x{cell['score']:.2f} "
            f"+ {weights['environment_severity']}x{env_severity:.2f} "
            f"+ {weights['temperature_stress']}x{stress_effective:.2f}. "
            f"Indicative service life at this pairing alone: "
            f"{cell.get('years', 'unstated')} years."
        ),
        mechanism=MECHANISM,
        band=band,
        # Passed unrounded; make_issue rounds to 3 dp for display. Banding
        # already used the full-precision value.
        score=score,
        mitigation=_mitigation(band, element, cell, media),
        assignee_role="Mechanical engineer",
        metadata={
            "material": element.material,
            "media": media,
            "environment_class": element.environment_class.value,
            "operating_temperature_c": element.operating_temperature_c,
            "material_media_score": cell["score"],
            "environment_severity": env_severity,
            "temperature_stress": stress,
            "temperature_stress_applied": stress_effective,
            # Full precision — Issue.score is rounded to 3 dp for display, and
            # banding used this value, so audits need it unrounded.
            "composite_score_exact": score,
            "kinetics_guard_applied": guard_applied,
            "failure_mechanism": cell.get("mech"),
            "predicted_lifespan_years": cell.get("years"),
            "cell_confidence": cell.get("conf"),
            "cell_note": cell.get("note"),
        },
        citations=citations,
    )


def _mitigation(band: RiskBand, element: PipingElement, cell: dict, media: str) -> str:
    """Return remediation guidance for a finding."""
    mechanism = (cell.get("mech") or "degradation").replace("_", " ")
    years = cell.get("years")
    horizon = f" Indicative service life {years} years at this pairing." if years else ""

    if band is RiskBand.CRITICAL:
        return (
            f"Substitute {element.material} for a grade compatible with "
            f"{media.replace('_', ' ')} before installation. {mechanism.capitalize()} "
            f"is expected to govern.{horizon} Immediate design review required."
        )
    if band is RiskBand.HIGH:
        return (
            f"Review material selection for this run. {mechanism.capitalize()} is "
            f"the governing mechanism for {element.material} in "
            f"{media.replace('_', ' ')}; a higher-alloy or lined alternative should "
            f"be evaluated.{horizon} Resolve before commissioning."
        )
    return (
        f"Record {element.material} in {media.replace('_', ' ')} on the corrosion "
        f"asset register and set an inspection interval appropriate to "
        f"{mechanism}.{horizon} No immediate design change required."
    )


def _data_quality(
    element: PipingElement,
    counter: list,
    *,
    check: str,
    title: str,
    detail: str,
    metadata: dict[str, Any],
) -> Issue:
    """Build a Low-band data-quality Issue for an unscoreable element.

    Follows the schema's NULLABILITY POLICY: a comparator that cannot run
    points at the offending element rather than crashing or guessing.
    """
    counter[0] += 1
    return make_issue(
        id=f"BGR-{counter[0]:04d}",
        element_id=element.id,
        rule_id=f"{RULE_REF_PREFIX}.DATA",
        title=title,
        description=detail,
        mechanism="data_quality",
        band=RiskBand.LOW,
        score=0.10,
        mitigation=detail,
        assignee_role="BIM coordinator",
        metadata={"check": check, "ifc_class": element.ifc_class, **metadata},
    )
