"""
XM-001 Cross-Material Contamination comparator (Path B).

Finds galvanic couples where dissimilar materials meet — either in direct
contact at a joint, or through shared media on the same loop. Complements
GC-001, which assesses flange pairs, by working the connectivity graph the
Module 2 producer builds.

INPUT
    list[PipingElement] with joined_to populated, plus a rule pack.

OUTPUT
    list[Issue] — one per dissimilar-material couple, INCLUDING mitigated
    couples banded Low, plus data-quality Issues for elements that cannot be
    assessed.

COMPOSITE SCORE
    raw   = 0.50*voltage_risk + 0.30*separation_factor + 0.20*environment
    score = raw * mitigation_factor

WHY MITIGATED COUPLES STILL REPORT
    A dielectric union scores the couple at 0.10 of raw rather than removing
    it. The audience is modellers who do not routinely think about dissimilar
    metals: a mitigated couple shown at Low band teaches the pattern and tells
    commissioning what to verify. Suppressing it teaches nothing and loses the
    inspection point.

ONE GALVANIC SERIES
    This module holds no potentials. load_rule_pack() injects the GC-001
    series from app.services.corrosion_rule_catalog.load_gc_catalog(), and the
    environment table from the approved MM-001 pack. See the rule pack's
    NO_GALVANIC_SERIES_IN_THIS_FILE note.

ANODE IDENTIFICATION
    The finding names which material sacrifices, since that is what drives a
    substitution decision. Direction comes from each series entry's `noble`
    flag, NOT from the sign of the potential: galvanic.py and
    bimguard_corrosion_engine.py read the same table with opposite sign
    conventions, so one of them names the wrong victim. Magnitude uses
    abs(gap), which is convention-independent. When nobility cannot be
    resolved, XM-001 emits data-quality rather than guessing the victim.

TIER SEMANTICS
    An element whose _connectivity_source is "indeterminable" is skipped WITH
    a data-quality Issue: joined_to == [] means "we could not tell", not
    "isolated". On a Tier 1 or Tier 2 element the same empty list does mean
    genuinely isolated, and produces no Issue and no noise.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..module2_ifc_read.piping_producer import (
    CONNECTIVITY_INDETERMINABLE,
    CONNECTIVITY_SOURCE_KEY,
)
from ..module2_ifc_read.piping_schema import CANONICAL_MATERIALS, EnvironmentClass, PipingElement
from .issue_schema import Issue, RiskBand, band_from_score, make_issue

MECHANISM = "XM-001 cross-material"
RULE_REF_PREFIX = "XM-001"

XM_PACK_PATH = Path("data/rulesets/xm_001_cross_material.json")
MM_PACK_PATH = Path("data/rulesets/mm_001_material_media.json")

_REQUIRED_KEYS = {
    "weights",
    "separation_factors",
    "mitigation_factors",
    "risk_band_thresholds",
    "galvanic_series",
    "environment_severity",
    "compatibility_thresholds",
}


# ---------------------------------------------------------------------------
# Rule pack assembly
# ---------------------------------------------------------------------------


def load_rule_pack(
    *,
    galvanic_series: Optional[dict] = None,
    environment_severity: Optional[dict] = None,
    compatibility_thresholds: Optional[dict] = None,
) -> dict:
    """Assemble the XM-001 rule pack from its single-source components.

    The on-disk XM-001 pack carries no potentials and no environment table.
    This function injects them so there remains exactly one galvanic series
    and one environment table in the project.

    Args:
        galvanic_series: Override the GC-001 series. Provided for tests and
            offline use; production leaves it None so the catalogue is read.
        environment_severity: Override the MM-001 environment table, same
            reasoning.
        compatibility_thresholds: Override the GC-001 environment voltage
            thresholds, same reasoning.

    Returns:
        A rule pack ready for compare().

    Raises:
        RuntimeError: If a component cannot be resolved and no override was
            supplied.
    """
    pack = json.loads(XM_PACK_PATH.read_text(encoding="utf-8"))
    params = pack["parameters"]

    if galvanic_series is None or compatibility_thresholds is None:
        # Imported lazily: the catalogue reaches the database at call time,
        # and this module must stay importable without one.
        from app.services.corrosion_rule_catalog import load_gc_catalog

        catalogue = load_gc_catalog()
        if galvanic_series is None:
            galvanic_series = catalogue.get("galvanic_series") or {}
            if not galvanic_series:
                raise RuntimeError(
                    "GC-001 catalogue returned no galvanic_series. XM-001 will not "
                    "author a substitute table; fix the catalogue instead."
                )
        if compatibility_thresholds is None:
            compatibility_thresholds = catalogue.get("environment_classes") or {}
            if not compatibility_thresholds:
                raise RuntimeError(
                    "GC-001 catalogue returned no environment_classes. XM-001 will "
                    "not author substitute compatibility thresholds."
                )
    params["galvanic_series"] = galvanic_series
    params["compatibility_thresholds"] = compatibility_thresholds

    if environment_severity is None:
        mm_pack = json.loads(MM_PACK_PATH.read_text(encoding="utf-8"))
        environment_severity = mm_pack["parameters"]["environment_severity"]
    params["environment_severity"] = environment_severity

    return pack


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compare(elements: list[PipingElement], rule_pack: dict) -> list[Issue]:
    """Run XM-001 cross-material compliance against piping elements.

    Args:
        elements: Elements with joined_to and connectivity tier markers set.
        rule_pack: Pack from load_rule_pack(), or an equivalent dict.

    Returns:
        One Issue per dissimilar-material couple, plus data-quality Issues.
        Same-material couples and isolated elements produce nothing.

    Raises:
        ValueError: If the rule pack is missing a required parameter key.
    """
    params = rule_pack.get("parameters", {})
    missing = _REQUIRED_KEYS - params.keys()
    if missing:
        raise ValueError(f"XM-001 rule pack is missing required keys: {sorted(missing)}")

    issues: list[Issue] = []
    counter = [0]
    by_id = {e.id: e for e in elements}

    assessable: list[PipingElement] = []
    for element in elements:
        source = element.properties.get(CONNECTIVITY_SOURCE_KEY)
        if source == "indeterminable" or CONNECTIVITY_INDETERMINABLE in element.extraction_warnings:
            issues.append(_indeterminable_issue(element, counter))
            continue
        assessable.append(element)

    for left, right, separation in _couples(assessable, by_id):
        issue = _assess_couple(left, right, separation, params, counter)
        if issue is not None:
            issues.append(issue)

    return issues


# ---------------------------------------------------------------------------
# Couple discovery
# ---------------------------------------------------------------------------


def _couples(
    elements: list[PipingElement],
    by_id: dict[str, PipingElement],
) -> list[tuple[PipingElement, PipingElement, str]]:
    """Find dissimilar-material couples and classify their separation.

    Direct contact comes from joined_to. Same-loop couples are dissimilar
    pairs in the same connected component and on the same system that are not
    directly joined — they share an electrolyte path without metallic contact.

    Args:
        elements: Assessable elements.
        by_id: Lookup for the whole model.

    Returns:
        Sorted (left, right, separation_kind) tuples, each pair once.
    """
    assessable_ids = {e.id for e in elements}
    seen: set[tuple[str, str]] = set()
    couples: list[tuple[PipingElement, PipingElement, str]] = []

    # ── Direct contact ────────────────────────────────────────────────────
    for element in elements:
        for other_id in element.joined_to:
            if other_id not in assessable_ids:
                continue
            other = by_id[other_id]
            if other.material == element.material:
                continue
            key = tuple(sorted((element.id, other.id)))
            if key in seen:
                continue
            seen.add(key)
            left, right = (element, other) if element.id == key[0] else (other, element)
            couples.append((left, right, "direct_contact"))

    # ── Same loop ─────────────────────────────────────────────────────────
    # Only for material pairs that never touch directly inside the component.
    # Where the same two materials already meet at a joint, the extra same-loop
    # pairs carry no additional action: substituting one material resolves
    # every one of them. Reporting them all would emit O(n^2) findings for a
    # single decision — one steel section in a 50-element copper loop would
    # raise 49 issues.
    for component in _components(elements, by_id, assessable_ids):
        members = [by_id[i] for i in sorted(component)]
        direct_material_pairs = {
            tuple(sorted((left.material, right.material)))
            for left, right, kind in couples
            if kind == "direct_contact" and left.id in component and right.id in component
        }
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                if left.material == right.material or left.system is not right.system:
                    continue
                if tuple(sorted((left.material, right.material))) in direct_material_pairs:
                    continue
                key = tuple(sorted((left.id, right.id)))
                if key in seen:
                    continue
                seen.add(key)
                couples.append((left, right, "same_loop"))

    couples.sort(key=lambda c: (c[0].id, c[1].id))
    return couples


def _components(
    elements: list[PipingElement],
    by_id: dict[str, PipingElement],
    assessable_ids: set[str],
) -> list[set[str]]:
    """Return connected components of the adjacency graph."""
    unvisited = {e.id for e in elements}
    components: list[set[str]] = []

    while unvisited:
        start = unvisited.pop()
        component = {start}
        stack = [start]
        while stack:
            current = by_id[stack.pop()]
            for neighbour_id in current.joined_to:
                if neighbour_id in unvisited and neighbour_id in assessable_ids:
                    unvisited.discard(neighbour_id)
                    component.add(neighbour_id)
                    stack.append(neighbour_id)
        components.append(component)

    return components


# ---------------------------------------------------------------------------
# Couple assessment
# ---------------------------------------------------------------------------


def _series_entry(series: dict, material: str) -> Optional[dict]:
    """Return a series entry for a material, tolerating flat float tables."""
    entry = series.get(material)
    if entry is None:
        return None
    if isinstance(entry, (int, float)):
        return {"potential_v": float(entry)}
    if isinstance(entry, dict):
        return entry
    return None


def _resolve_anode(
    left: PipingElement,
    right: PipingElement,
    left_entry: dict,
    right_entry: dict,
    convention: Optional[str],
) -> Optional[tuple[PipingElement, PipingElement]]:
    """Return (anode, cathode), or None when direction is unresolvable.

    Resolution order:

    1. The `noble` flag, when the two entries differ on it. Unambiguous and
       independent of the table's sign convention.
    2. The convention DECLARED in the rule pack, applied to potential_v. This
       is needed because two noble materials still form a couple — copper
       against stainless, brass against copper — so nobility alone leaves the
       commonest pairs unresolved.

    The convention is read from the pack rather than assumed in code because
    galvanic.py and bimguard_corrosion_engine.py disagree about the sign of
    the shared table. Declaring it makes the assumption reviewable; guessing
    it would name the wrong victim half the time.
    """
    left_noble = left_entry.get("noble")
    right_noble = right_entry.get("noble")
    if isinstance(left_noble, bool) and isinstance(right_noble, bool) and left_noble != right_noble:
        return (right, left) if right_noble is False else (left, right)

    left_v = left_entry.get("potential_v")
    right_v = right_entry.get("potential_v")
    if convention is None or left_v is None or right_v is None:
        return None
    if float(left_v) == float(right_v):
        return None

    if convention == "more_negative_is_anodic":
        return (left, right) if float(left_v) < float(right_v) else (right, left)
    if convention == "more_positive_is_anodic":
        return (left, right) if float(left_v) > float(right_v) else (right, left)
    return None


def _assess_couple(
    left: PipingElement,
    right: PipingElement,
    separation: str,
    params: dict,
    counter: list,
) -> Optional[Issue]:
    """Score one dissimilar-material couple.

    Returns None when the pair is galvanically compatible for its environment
    — that is not a finding, it is the absence of a couple.
    """
    series = params["galvanic_series"]

    for element in (left, right):
        if element.material not in CANONICAL_MATERIALS or element.material == "Unknown":
            return _data_quality(
                left,
                right,
                counter,
                check="material_normalisation",
                detail=(
                    f"{element.material!r} on {_label(element)} is not a canonical "
                    "material key, so no galvanic potential can be looked up."
                ),
            )

    left_entry = _series_entry(series, left.material)
    right_entry = _series_entry(series, right.material)
    if left_entry is None or right_entry is None:
        absent = left.material if left_entry is None else right.material
        return _data_quality(
            left,
            right,
            counter,
            check="material_not_in_series",
            detail=(
                f"{absent} has no entry in the GC-001 galvanic series, so this "
                "couple cannot be scored. Extend the series rather than assuming "
                "the pairing is benign."
            ),
        )

    convention = (params.get("series_convention") or {}).get("value")
    ordered = _resolve_anode(left, right, left_entry, right_entry, convention)
    if ordered is None:
        return _data_quality(
            left,
            right,
            counter,
            check="anode_unresolvable",
            detail=(
                "The sacrificing material cannot be named: the series entries do "
                "not differ on 'noble', and the rule pack declares no "
                "series_convention to break the tie on potential. XM-001 will not "
                "infer direction from the potential sign unaided, because "
                "galvanic.py and bimguard_corrosion_engine.py read this table with "
                "opposite conventions and a guess would be wrong half the time."
            ),
        )
    anode, cathode = ordered

    left_v = left_entry.get("potential_v")
    right_v = right_entry.get("potential_v")
    if left_v is None or right_v is None:
        return _data_quality(
            left,
            right,
            counter,
            check="potential_missing",
            detail="A series entry carries no potential_v, so the gap cannot be computed.",
        )

    gap_v = abs(float(left_v) - float(right_v))
    normalisation = params.get("voltage_normalisation_v", {}).get("value", 1.0)
    voltage_risk = min(1.0, gap_v / normalisation) if normalisation else 0.0

    separation_entry = params["separation_factors"][separation]
    separation_factor = separation_entry["factor"]

    environment_class = _worse_environment(left, right)
    env_entry = params["environment_severity"].get(environment_class.value, {})
    env_severity = env_entry.get("severity")
    if env_severity is None:
        return _data_quality(
            left,
            right,
            counter,
            check="environment_unclassified",
            detail=(
                f"Environment {environment_class.value} carries no severity, so the "
                "couple cannot be scored. Treating it as benign would suppress "
                "findings wherever the producer could not classify a space."
            ),
        )

    # ── Compatibility floor ───────────────────────────────────────────────
    # Below the environment's NASA-STD-6012 threshold the pair is compatible:
    # there is no galvanic couple, so nothing for direct contact to amplify.
    # Suppressed entirely rather than banded Low — unlike a mitigated couple,
    # a compatible pair is not a design decision worth showing.
    if _is_compatible(gap_v, environment_class, params):
        return None

    mitigation_key, mitigation_entry = _mitigation_entry(left, right, params)
    mitigation_factor = mitigation_entry["factor"]

    weights = params["weights"]
    raw = (
        weights["voltage"] * voltage_risk
        + weights["separation"] * separation_factor
        + weights["environment"] * env_severity
    )
    score = raw * mitigation_factor
    band = band_from_score(score, params["risk_band_thresholds"])

    return _finding(
        anode=anode,
        cathode=cathode,
        counter=counter,
        gap_v=gap_v,
        voltage_risk=voltage_risk,
        separation=separation,
        separation_entry=separation_entry,
        environment_class=environment_class,
        env_entry=env_entry,
        env_severity=env_severity,
        mitigation_key=mitigation_key,
        mitigation_entry=mitigation_entry,
        raw=raw,
        score=score,
        band=band,
        params=params,
    )


def _is_compatible(gap_v: float, environment: EnvironmentClass, params: dict) -> bool:
    """Return True when the potential gap is below the compatibility threshold.

    The threshold voltages come from the GC-001 catalogue; only the mapping
    from EnvironmentClass onto GC-001's environment classes lives in the
    XM-001 pack. Returns False when the floor is disabled or the threshold
    cannot be resolved, so an unmapped environment fails open into a scored
    finding rather than silently suppressing a real couple.

    Args:
        gap_v: Absolute potential difference in volts.
        environment: The more severe of the couple's two environments.
        params: Rule pack parameters.

    Returns:
        True if the pair should produce no finding.
    """
    floor = params.get("compatibility_floor") or {}
    if not floor.get("enabled"):
        return False

    class_name = (params.get("environment_threshold_class") or {}).get(environment.value)
    if class_name is None:
        return False

    entry = (params.get("compatibility_thresholds") or {}).get(class_name)
    if entry is None:
        return False
    threshold = entry.get("max_safe_voltage_v") if isinstance(entry, dict) else entry
    if threshold is None:
        return False

    return gap_v < float(threshold)


def _worse_environment(left: PipingElement, right: PipingElement) -> EnvironmentClass:
    """Return the more severe of two elements' environments.

    Severity ranks by enum ordering position, with UNCLASSIFIED winning so an
    unknown environment surfaces as data quality rather than being averaged
    away against a known-benign neighbour.
    """
    order = list(EnvironmentClass)
    if EnvironmentClass.UNCLASSIFIED in (left.environment_class, right.environment_class):
        return EnvironmentClass.UNCLASSIFIED
    return max(
        (left.environment_class, right.environment_class),
        key=lambda e: order.index(e),
    )


def _mitigation_entry(
    left: PipingElement,
    right: PipingElement,
    params: dict,
) -> tuple[str, dict]:
    """Return the (key, entry) of the mitigation applying to a couple.

    A mitigating joint on either element counts: a dielectric union breaks
    continuity across the joint regardless of which side carries the record.
    """
    catalogue = params["mitigation_factors"]
    for element in (left, right):
        if element.joint_type is None:
            continue
        entry = catalogue.get(element.joint_type.value)
        if entry is not None:
            return element.joint_type.value, entry
    return "_default", catalogue["_default"]


# ---------------------------------------------------------------------------
# Issue construction
# ---------------------------------------------------------------------------


def _label(element: PipingElement) -> str:
    """Return a short human-readable element label."""
    return element.name or element.id[:8]


def _finding(
    *,
    anode: PipingElement,
    cathode: PipingElement,
    counter: list,
    gap_v: float,
    voltage_risk: float,
    separation: str,
    separation_entry: dict,
    environment_class: EnvironmentClass,
    env_entry: dict,
    env_severity: float,
    mitigation_key: str,
    mitigation_entry: dict,
    raw: float,
    score: float,
    band: RiskBand,
    params: dict,
) -> Issue:
    """Build the Issue for an assessed couple."""
    counter[0] += 1
    mitigated = mitigation_entry["factor"] < 1.0
    weights = params["weights"]

    citations = [
        {
            "standard": "GC-001 galvanic series (single source, see rule pack)",
            "clause": f"{anode.material} / {cathode.material}",
            "reason": f"potential gap {gap_v:.3f} V -> voltage risk {voltage_risk:.2f}",
        },
        {
            "standard": separation_entry.get("cite", ""),
            "clause": separation,
            "reason": f"separation factor {separation_entry['factor']:.2f}",
        },
        {
            "standard": env_entry.get("cite", ""),
            "clause": environment_class.value,
            "reason": f"environment severity {env_severity:.2f}",
        },
        {
            "standard": mitigation_entry.get("cite", ""),
            "clause": mitigation_key,
            "reason": (
                f"{mitigation_entry.get('label', mitigation_key)} - "
                f"score x{mitigation_entry['factor']:.2f}"
            ),
        },
    ]

    description = (
        f"{anode.material} on {_label(anode)} is anodic to {cathode.material} on "
        f"{_label(cathode)}; the {anode.material} sacrifices. Coupled by "
        f"{separation.replace('_', ' ')} in a {environment_class.value} environment. "
        f"Raw {round(raw, 3)} = {weights['voltage']}x{voltage_risk:.2f} "
        f"+ {weights['separation']}x{separation_entry['factor']:.2f} "
        f"+ {weights['environment']}x{env_severity:.2f}; "
        f"x{mitigation_entry['factor']:.2f} ({mitigation_entry.get('label', '')}) "
        f"= {round(score, 3)}."
    )
    if mitigated:
        description += (
            " Mitigated - verify union integrity at commissioning. The couple is "
            "recorded rather than suppressed so the separation remains an "
            "inspectable item."
        )

    return make_issue(
        id=f"BGR-{counter[0]:04d}",
        element_id=anode.id,
        rule_id=f"{RULE_REF_PREFIX}.{anode.material}.{cathode.material}",
        title=(
            f"{anode.material} sacrifices to {cathode.material}"
            f"{' (mitigated)' if mitigated else ''}"
        ),
        description=description,
        mechanism=MECHANISM,
        band=band,
        score=score,
        mitigation=_mitigation_text(band, anode, cathode, mitigated),
        assignee_role="Mechanical engineer",
        metadata={
            "anode_id": anode.id,
            "anode_material": anode.material,
            "cathode_id": cathode.id,
            "cathode_material": cathode.material,
            "voltage_gap_v": round(gap_v, 4),
            "voltage_risk": voltage_risk,
            "separation": separation,
            "separation_factor": separation_entry["factor"],
            "environment_class": environment_class.value,
            "environment_severity": env_severity,
            "mitigation": mitigation_key,
            "mitigation_factor": mitigation_entry["factor"],
            "mitigated": mitigated,
            "raw_score_exact": raw,
            "composite_score_exact": score,
        },
        citations=citations,
    )


def _mitigation_text(
    band: RiskBand,
    anode: PipingElement,
    cathode: PipingElement,
    mitigated: bool,
) -> str:
    """Return remediation guidance for a couple."""
    if mitigated:
        return (
            f"Dielectric separation is present between {anode.material} and "
            f"{cathode.material}. Verify union integrity at commissioning and "
            "record it on the corrosion asset register - the credit depends on the "
            "union being installed and remaining intact."
        )
    if band is RiskBand.CRITICAL:
        return (
            f"Isolate {anode.material} from {cathode.material} with a dielectric "
            "union or insulating flange kit, or substitute one material for a "
            f"compatible grade. The {anode.material} will corrode preferentially. "
            "Immediate design review required."
        )
    if band is RiskBand.HIGH:
        return (
            f"Specify a dielectric union between {anode.material} and "
            f"{cathode.material}, or substitute the {anode.material} for a more "
            "noble grade. Resolve before commissioning."
        )
    return (
        f"Record the {anode.material}/{cathode.material} couple on the corrosion "
        "asset register and set an inspection interval. No immediate design change "
        "required."
    )


def _indeterminable_issue(element: PipingElement, counter: list) -> Issue:
    """Build the Issue for an element whose connectivity could not be resolved.

    joined_to == [] on such an element means "we could not tell", not
    "isolated". Assessing it as having no couples would report an unverified
    element as compliant.
    """
    counter[0] += 1
    return make_issue(
        id=f"BGR-{counter[0]:04d}",
        element_id=element.id,
        rule_id=f"{RULE_REF_PREFIX}.DATA",
        title=f"Connectivity indeterminable on {_label(element)}",
        description=(
            "Neither IFC ports nor centerline geometry could establish what this "
            "element connects to, so no galvanic couple can be assessed. An empty "
            "joined_to here means unknown, not isolated."
        ),
        mechanism="data_quality",
        band=RiskBand.LOW,
        score=0.10,
        mitigation=(
            "Populate IfcRelConnectsPorts in the authoring tool, or supply "
            "geometry for this element, then re-run. XM-001 was skipped."
        ),
        assignee_role="BIM coordinator",
        metadata={
            "check": "connectivity_indeterminable",
            "ifc_class": element.ifc_class,
            "connectivity_source": element.properties.get(CONNECTIVITY_SOURCE_KEY),
        },
    )


def _data_quality(
    left: PipingElement,
    right: PipingElement,
    counter: list,
    *,
    check: str,
    detail: str,
) -> Issue:
    """Build a Low-band data-quality Issue for an unscoreable couple."""
    counter[0] += 1
    return make_issue(
        id=f"BGR-{counter[0]:04d}",
        element_id=left.id,
        rule_id=f"{RULE_REF_PREFIX}.DATA",
        title=f"Couple {_label(left)} / {_label(right)} could not be assessed",
        description=detail,
        mechanism="data_quality",
        band=RiskBand.LOW,
        score=0.10,
        mitigation=detail,
        assignee_role="BIM coordinator",
        metadata={
            "check": check,
            "left_id": left.id,
            "left_material": left.material,
            "right_id": right.id,
            "right_material": right.material,
        },
    )

