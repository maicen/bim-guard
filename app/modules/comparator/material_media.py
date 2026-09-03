"""
MM-001: Material-Media Compatibility comparator.

Scores the degradation risk of a piping material carrying a given medium,
modified by environment severity and operating temperature.

    composite = w_mm * compatibility_cell
              + w_env * environment_severity
              + w_t  * temperature_stress

Every term, weight, threshold and citation is read from the rule pack
(`data/rulesets/mm_001_material_media.json`). This module carries no
compatibility values, no severity ladder and no band thresholds of its own:
a pack edit changes the verdicts without a code change.

Elements that cannot be scored — unidentified material, unclassified
environment, an unmapped material/media pairing, a missing temperature —
produce a data-quality Issue rather than a silent pass. Reporting an
unassessed pairing as compliant would state something the engine does not
know.

Entry point: compare(network, rule_pack, id_allocator=None) -> list[Issue]
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from app.modules.ifc_reader.piping_producer import media_for_system
from app.modules.ifc_reader.piping_schema import (
    CANONICAL_MATERIALS,
    EnvironmentClass,
    PipingElement,
    PipingSystem,
)
from app.modules.comparator.issue_schema import (
    Issue,
    RiskBand,
    band_from_score,
    make_issue,
)

MM_PACK_PATH = Path("data/rulesets/mm_001_material_media.json")

MECHANISM = "MM-001 material-media"
DATA_QUALITY = "data_quality"
RULE_ID = "MM-001"
ID_PREFIX = "MM"

#: Pack keys the comparator cannot score without. `kinetics_guard` is
#: deliberately absent — a pack may omit it, and the guard then does not apply.
REQUIRED_PARAMETER_KEYS = frozenset(
    {
        "compatibility_matrix",
        "environment_severity",
        "temperature_stress",
        "risk_band_thresholds",
        "weights",
    }
)


# ---------------------------------------------------------------------------
# Rule pack loading
# ---------------------------------------------------------------------------


def load_rule_pack(*, path: Path | None = None) -> dict:
    """Load the MM-001 material-media rule pack from disk.

    Args:
        path: Optional override. Defaults to MM_PACK_PATH.

    Returns:
        The rule pack dict.

    Raises:
        FileNotFoundError: If the pack file does not exist.
        ValueError: If parameters.* is missing a key the comparator needs.
    """
    pack_path = path or MM_PACK_PATH
    if not pack_path.exists():
        raise FileNotFoundError(f"MM-001 rule pack not found: {pack_path}")
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    _require_parameters(pack)
    return pack


def _require_parameters(rule_pack: dict) -> dict:
    """Return parameters, raising if any key the comparator relies on is absent."""
    parameters = (rule_pack or {}).get("parameters") or {}
    missing = REQUIRED_PARAMETER_KEYS - set(parameters)
    if missing:
        raise ValueError(
            f"MM-001 rule pack missing required keys: {sorted(missing)}"
        )
    return parameters


# ---------------------------------------------------------------------------
# Issue id allocation
# ---------------------------------------------------------------------------


def _allocator(id_allocator: Any) -> Callable[[], str]:
    """Adapt an allocator to a zero-argument id factory.

    Accepts an IssueIdAllocator (anything exposing ``.next(prefix)``), a bare
    callable, or None. None gives a run-local counter so the comparator stays
    usable standalone while still honouring a run-wide allocator when the
    orchestrator supplies one.
    """
    if id_allocator is None:
        counter = itertools.count(1)
        return lambda: f"{ID_PREFIX}-{next(counter):04d}"
    if hasattr(id_allocator, "next"):
        return lambda: id_allocator.next(ID_PREFIX)
    if callable(id_allocator):
        return lambda: id_allocator(ID_PREFIX)
    raise TypeError(f"Unusable id_allocator: {type(id_allocator).__name__}")


# ---------------------------------------------------------------------------
# Term resolution
# ---------------------------------------------------------------------------


def _environment_entry(parameters: dict, element: PipingElement) -> Optional[dict]:
    """Return the severity row for an element's environment, or None.

    None means the environment cannot carry a numeric severity — either the
    class is absent from the table or the pack pins it to null, as it does for
    `unclassified`.
    """
    table = parameters["environment_severity"]
    key = _environment_key(element)
    entry = table.get(key)
    if not isinstance(entry, dict) or entry.get("severity") is None:
        return None
    return entry


def _environment_key(element: PipingElement) -> str:
    """Return the element's environment class as its pack key.

    Read defensively: the orchestrator hands Path B whatever Path A was given,
    which is not always a fully populated PipingElement. An element missing the
    field is unclassified, which the comparator already reports rather than
    scores.
    """
    environment = getattr(element, "environment_class", None)
    if environment is None:
        return EnvironmentClass.UNCLASSIFIED.value
    return environment.value if isinstance(environment, EnvironmentClass) else str(environment)


def _temperature_band(parameters: dict, temperature_c: float) -> Optional[dict]:
    """Return the temperature-stress band containing a temperature.

    Bands are inclusive of their lower bound and exclusive of their upper, per
    the pack's own `_basis` note.
    """
    for band in parameters["temperature_stress"].get("bands", []):
        low, high = band.get("min_c"), band.get("max_c")
        if (low is None or temperature_c >= low) and (high is None or temperature_c < high):
            return band
    return None


# ---------------------------------------------------------------------------
# Issue construction
# ---------------------------------------------------------------------------


def _data_quality(
    element: PipingElement,
    *,
    next_id: Callable[[], str],
    check: str,
    title: str,
    description: str,
    mitigation: str,
) -> Issue:
    """Build a data-quality Issue for an element MM-001 cannot score."""
    return make_issue(
        id=next_id(),
        element_id=getattr(element, "id", "") or "",
        rule_id=f"{RULE_ID}.DQ",
        title=title,
        mechanism=DATA_QUALITY,
        band=RiskBand.LOW,
        score=0.0,
        mitigation=mitigation,
        description=description,
        metadata={
            "check": check,
            "material": getattr(element, "material", None) or "Unknown",
            "system": getattr(getattr(element, "system", None), "value", None),
            "environment_class": _environment_key(element),
        },
        citations=[
            {
                "standard": "BIMGUARD-MM-001",
                "clause": "unmapped_pairing_policy",
                "reason": "Element cannot be scored; reporting it compliant would assert "
                "an unverified pairing.",
            }
        ],
    )


def _assess(
    element: PipingElement,
    parameters: dict,
    next_id: Callable[[], str],
) -> Optional[Issue]:
    """Score one element, returning its Issue or None when it bands Low."""
    material = getattr(element, "material", None) or "Unknown"
    medium = media_for_system(getattr(element, "system", PipingSystem.UNKNOWN))

    # --- Scoreability gates. Each returns a finding, never a silent pass. ---
    if material == "Unknown" or material not in CANONICAL_MATERIALS:
        return _data_quality(
            element,
            next_id=next_id,
            check="material_normalisation",
            title=f"MM-001 not assessed: material not identified on {getattr(element, 'id', '?')}",
            description=(
                f"Material '{material}' was not normalised to a canonical key, so no "
                "compatibility cell can be selected. The element is unassessed, not compliant."
            ),
            mitigation="Set the element material to a canonical key in the IFC model or "
            "extend the material normalisation table.",
        )

    environment = _environment_entry(parameters, element)
    if environment is None:
        return _data_quality(
            element,
            next_id=next_id,
            check="environment_unclassified",
            title=f"MM-001 not assessed: environment unclassified on {getattr(element, 'id', '?')}",
            description=(
                f"Environment class '{_environment_key(element)}' carries no severity, so the "
                "environment term cannot be evaluated. Scoring it as benign would suppress "
                "findings on every element the producer could not classify."
            ),
            mitigation="Classify the containing space so an environment severity can be "
            "resolved.",
        )

    cell = (parameters["compatibility_matrix"].get(material) or {}).get(medium)
    if not isinstance(cell, dict):
        return _data_quality(
            element,
            next_id=next_id,
            check="unmapped_pairing",
            title=f"MM-001 not assessed: {material} / {medium} is unmapped",
            description=(
                f"The pairing {material} / {medium} has no cell in the MM-001 matrix. "
                "Per unmapped_pairing_policy an absent cell must not be scored as compliant."
            ),
            mitigation=f"Add an MM-001 matrix cell for {material} / {medium}, or confirm the "
            "system classification is correct.",
        )

    temperature_c = getattr(element, "operating_temperature_c", None)
    if temperature_c is None:
        return _data_quality(
            element,
            next_id=next_id,
            check="temperature_missing",
            title=f"MM-001 not assessed: no operating temperature on {getattr(element, 'id', '?')}",
            description=(
                "operating_temperature_c is absent, so the temperature term cannot be "
                "evaluated. A default would be a fabricated input to a compliance verdict."
            ),
            mitigation="Populate operating_temperature_c from the system design data.",
        )

    band_row = _temperature_band(parameters, temperature_c)
    if band_row is None:
        return _data_quality(
            element,
            next_id=next_id,
            check="temperature_unbanded",
            title=f"MM-001 not assessed: {temperature_c} C falls outside every band",
            description=(
                f"Operating temperature {temperature_c} C matches no band in the MM-001 "
                "temperature_stress table, so the temperature term cannot be evaluated."
            ),
            mitigation="Extend the temperature_stress bands to cover this service.",
        )

    # --- Scoring ---
    cell_score = float(cell["score"])
    environment_severity = float(environment["severity"])
    temperature_stress = float(band_row["stress"])

    guard = parameters.get("kinetics_guard")
    guard_applied = False
    if isinstance(guard, dict) and cell_score < float(guard["cell_below"]):
        cap = float(guard["cap_temperature_stress_at"])
        if temperature_stress > cap:
            temperature_stress = cap
        guard_applied = True

    weights = parameters["weights"]
    composite = (
        float(weights["material_media"]) * cell_score
        + float(weights["environment_severity"]) * environment_severity
        + float(weights["temperature_stress"]) * temperature_stress
    )

    band = band_from_score(composite, parameters["risk_band_thresholds"])
    if band is RiskBand.LOW:
        # Compliant elements must not generate noise.
        return None

    displayed = round(composite, 3)
    citations = [
        {
            "standard": str(cell["cite"]),
            "clause": f"{material} / {medium}",
            "reason": f"compatibility cell {cell_score} ({cell.get('mech', 'unspecified')})",
        },
        {
            "standard": str(environment["cite"]),
            "clause": _environment_key(element),
            "reason": f"environment severity {environment_severity}",
        },
        {
            "standard": str(band_row["cite"]),
            "clause": f"{temperature_c} C",
            "reason": f"temperature stress {temperature_stress}",
        },
    ]
    if guard_applied:
        citations.append(
            {
                "standard": str(guard["cite"]),
                "clause": "kinetics_guard",
                "reason": (
                    f"cell {cell_score} is below {guard['cell_below']}, so temperature stress "
                    f"is capped at {guard['cap_temperature_stress_at']}"
                ),
            }
        )

    description = (
        f"{material} carrying {medium} in {_environment_key(element)} at {temperature_c} C "
        f"scores {displayed} ({band.value}). Terms: compatibility {cell_score}, environment "
        f"{environment_severity}, temperature {temperature_stress}"
        f"{' (kinetics guard applied)' if guard_applied else ''}. "
        f"Dominant mechanism: {cell.get('mech', 'unspecified')}."
    )

    return make_issue(
        id=next_id(),
        element_id=getattr(element, "id", "") or "",
        rule_id=f"{RULE_ID}.01",
        title=f"{material} in {medium} - {cell.get('mech', 'material-media risk')}",
        mechanism=MECHANISM,
        band=band,
        score=composite,
        mitigation=(
            f"Review the {material} specification for {medium} service, or reduce exposure "
            f"in {_environment_key(element)}. Predicted lifespan at this pairing alone: "
            f"{cell.get('years', 'unstated')} years."
        ),
        description=description,
        metadata={
            "material": material,
            "medium": medium,
            "environment_class": _environment_key(element),
            "environment_severity": environment_severity,
            "operating_temperature_c": temperature_c,
            "temperature_stress": temperature_stress,
            "compatibility_score": cell_score,
            "composite_score_exact": composite,
            "kinetics_guard_applied": guard_applied,
            "predicted_lifespan_years": cell.get("years"),
            "failure_mechanism": cell.get("mech"),
            "confidence": cell.get("conf"),
        },
        citations=citations,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def compare(
    network: Iterable[PipingElement],
    rule_pack: dict,
    id_allocator: Any = None,
) -> list[Issue]:
    """Assess a piping network for material-media compatibility.

    Args:
        network: The elements to assess. An empty network is not an error.
        rule_pack: The MM-001 pack, as returned by load_rule_pack().
        id_allocator: Optional run-wide IssueIdAllocator. When omitted, ids
            are minted from a run-local counter.

    Returns:
        One Issue per element that bands Medium or above, plus one
        data-quality Issue per element that cannot be scored. Elements that
        band Low produce nothing.

    Raises:
        ValueError: If the rule pack is missing a required parameter key.
    """
    parameters = _require_parameters(rule_pack)
    next_id = _allocator(id_allocator)

    issues: list[Issue] = []
    for element in network:
        issue = _assess(element, parameters, next_id)
        if issue is not None:
            issues.append(issue)
    return issues
