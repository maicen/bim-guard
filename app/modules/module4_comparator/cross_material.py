"""
XM-001: Cross-Material Contamination comparator.

Scores galvanic couples formed where dissimilar materials meet, either in
direct contact at a joint or through a shared electrolyte in the same loop.

    raw       = w_v * voltage_risk + w_s * separation_factor + w_e * environment_severity
    composite = raw * mitigation_factor

SINGLE SOURCE OF TRUTH
    This module embeds no galvanic series, no compatibility thresholds and no
    environment severity ladder, and neither does the on-disk pack. The series
    and NASA-STD-6012 thresholds come from the GC-001 catalogue; the
    environment table comes from the approved MM-001 pack. load_rule_pack()
    injects all three at runtime so a second table can never drift from the
    first.

ANODE DIRECTION
    Which material sacrifices is the actionable output, so the comparator will
    not guess it. Direction comes from the `noble` flag each series entry
    carries; when both entries agree, the pack's declared `series_convention`
    breaks the tie. With neither discriminator available the couple yields a
    data-quality Issue — the two engines historically read the shared series
    with opposite sign conventions, so an unaided inference would be wrong
    half the time.

Entry point: compare(network, rule_pack, id_allocator=None) -> list[Issue]
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from app.modules.module2_ifc_read.piping_producer import CONNECTIVITY_SOURCE_KEY
from app.modules.module2_ifc_read.piping_schema import (
    EnvironmentClass,
    JointType,
    PipingElement,
)
from app.modules.module4_comparator.issue_schema import (
    Issue,
    RiskBand,
    band_from_score,
    make_issue,
)

XM_PACK_PATH = Path("data/rulesets/xm_001_cross_material.json")
MM_PACK_PATH = Path("data/rulesets/mm_001_material_media.json")

MECHANISM = "XM-001 cross-material"
DATA_QUALITY = "data_quality"
RULE_ID = "XM-001"
ID_PREFIX = "XM"

SERIES_STANDARD = "GC-001 galvanic series"
INDETERMINABLE = "indeterminable"

DIRECT_CONTACT = "direct_contact"
SAME_LOOP = "same_loop"

#: Pack keys the comparator cannot score without. `series_convention`,
#: `environment_threshold_class` and `compatibility_floor` are deliberately
#: absent: a pack may omit the convention (the comparator then refuses to name
#: an anode) and the floor fails open when its mapping cannot be resolved.
REQUIRED_PARAMETER_KEYS = frozenset(
    {
        "galvanic_series",
        "compatibility_thresholds",
        "environment_severity",
        "weights",
        "separation_factors",
        "mitigation_factors",
        "risk_band_thresholds",
        "voltage_normalisation_v",
    }
)


# ---------------------------------------------------------------------------
# Rule pack loading
# ---------------------------------------------------------------------------


def load_rule_pack(
    galvanic_series: dict | None = None,
    compatibility_thresholds: dict | None = None,
    *,
    path: Path | None = None,
) -> dict:
    """Load the XM-001 pack and inject the tables it deliberately omits.

    Args:
        galvanic_series: Material potentials keyed by canonical material. When
            omitted, the GC-001 catalogue is consulted. Injected by reference so
            callers can assert the pack points at their table.
        compatibility_thresholds: NASA-STD-6012 max safe voltages keyed by
            GC-001 environment class. When omitted, taken from the same
            catalogue.
        path: Optional override for the on-disk pack.

    Returns:
        The rule pack with parameters.galvanic_series,
        parameters.compatibility_thresholds and parameters.environment_severity
        populated.

    Raises:
        FileNotFoundError: If the XM-001 or MM-001 pack file is missing.
    """
    pack_path = path or XM_PACK_PATH
    if not pack_path.exists():
        raise FileNotFoundError(f"XM-001 rule pack not found: {pack_path}")
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    parameters = pack.setdefault("parameters", {})

    if galvanic_series is None or compatibility_thresholds is None:
        catalogue_series, catalogue_thresholds = _catalogue_tables()
        if galvanic_series is None:
            galvanic_series = catalogue_series
        if compatibility_thresholds is None:
            compatibility_thresholds = catalogue_thresholds

    parameters["galvanic_series"] = galvanic_series
    parameters["compatibility_thresholds"] = compatibility_thresholds
    parameters["environment_severity"] = _mm_environment_severity()
    return pack


def _catalogue_tables() -> tuple[dict, dict]:
    """Return (galvanic_series, compatibility_thresholds) from the GC-001 catalogue.

    Returns empty tables when the catalogue is unreachable. An empty series
    yields data-quality Issues rather than silence, so an unavailable database
    never reads as "no galvanic risk".
    """
    try:
        from app.services.corrosion_rule_catalog import load_gc_catalog

        catalogue = load_gc_catalog() or {}
    except Exception:
        return {}, {}

    series = catalogue.get("galvanic_series") or {}
    thresholds = {
        key: {"max_safe_voltage_v": row.get("voltage_threshold")}
        for key, row in (catalogue.get("environment_classes") or {}).items()
        if isinstance(row, dict)
    }
    return series, thresholds


def _mm_environment_severity() -> dict:
    """Return the approved MM-001 environment severity table, unaltered."""
    if not MM_PACK_PATH.exists():
        raise FileNotFoundError(f"MM-001 rule pack not found: {MM_PACK_PATH}")
    mm_pack = json.loads(MM_PACK_PATH.read_text(encoding="utf-8"))
    return mm_pack["parameters"]["environment_severity"]


def _require_parameters(rule_pack: dict) -> dict:
    """Return parameters, raising if any key the comparator relies on is absent."""
    parameters = (rule_pack or {}).get("parameters") or {}
    missing = REQUIRED_PARAMETER_KEYS - set(parameters)
    if missing:
        raise ValueError(
            f"XM-001 rule pack missing required keys: {sorted(missing)}"
        )
    return parameters


# ---------------------------------------------------------------------------
# Issue id allocation
# ---------------------------------------------------------------------------


def _allocator(id_allocator: Any) -> Callable[[], str]:
    """Adapt an allocator to a zero-argument id factory. See material_media."""
    if id_allocator is None:
        counter = itertools.count(1)
        return lambda: f"{ID_PREFIX}-{next(counter):04d}"
    if hasattr(id_allocator, "next"):
        return lambda: id_allocator.next(ID_PREFIX)
    if callable(id_allocator):
        return lambda: id_allocator(ID_PREFIX)
    raise TypeError(f"Unusable id_allocator: {type(id_allocator).__name__}")


# ---------------------------------------------------------------------------
# Series and environment lookups
# ---------------------------------------------------------------------------


def _potential(entry: dict) -> Optional[float]:
    """Return an entry's potential, accepting either key the sources use.

    The test fixtures and the seeded GC-001 payload spell this differently
    (`potential_v` against `potential`); both name the same quantity.
    """
    for key in ("potential_v", "potential"):
        if entry.get(key) is not None:
            return float(entry[key])
    return None


def _environment_key(element: PipingElement) -> str:
    """Return an element's environment class as its pack key."""
    environment = element.environment_class
    return environment.value if isinstance(environment, EnvironmentClass) else str(environment)


def _severity(parameters: dict, environment_key: str) -> Optional[float]:
    """Return the severity for an environment key, or None when unscoreable."""
    entry = parameters["environment_severity"].get(environment_key)
    if not isinstance(entry, dict) or entry.get("severity") is None:
        return None
    return float(entry["severity"])


def _pair_environment(
    parameters: dict,
    left: PipingElement,
    right: PipingElement,
) -> tuple[str, float]:
    """Return the governing (environment_key, severity) for a couple.

    The harsher of the two elements' environments governs: a couple is only as
    protected as its most exposed end.
    """
    candidates = []
    for element in (left, right):
        key = _environment_key(element)
        severity = _severity(parameters, key)
        if severity is not None:
            candidates.append((severity, key))
    if not candidates:
        return _environment_key(left), 0.0
    severity, key = max(candidates)
    return key, severity


# ---------------------------------------------------------------------------
# Anode resolution
# ---------------------------------------------------------------------------


def _resolve_anode(
    parameters: dict,
    left: PipingElement,
    left_entry: dict,
    right: PipingElement,
    right_entry: dict,
) -> Optional[tuple[PipingElement, PipingElement]]:
    """Return (anode, cathode), or None when direction cannot be established.

    The `noble` flag decides whenever the two entries disagree. Otherwise the
    pack's declared series_convention breaks the tie. With neither, the caller
    must emit a data-quality Issue rather than guess which element corrodes.
    """
    left_noble = left_entry.get("noble") if "noble" in left_entry else None
    right_noble = right_entry.get("noble") if "noble" in right_entry else None
    if left_noble is not None and right_noble is not None and bool(left_noble) != bool(right_noble):
        return (right, left) if bool(left_noble) else (left, right)

    convention = (parameters.get("series_convention") or {}).get("value")
    left_potential, right_potential = _potential(left_entry), _potential(right_entry)
    if convention is None or left_potential is None or right_potential is None:
        return None

    if convention == "more_positive_is_anodic":
        return (left, right) if left_potential > right_potential else (right, left)
    if convention == "more_negative_is_anodic":
        return (left, right) if left_potential < right_potential else (right, left)
    return None


# ---------------------------------------------------------------------------
# Adjacency and loop topology
# ---------------------------------------------------------------------------


def _assessable(network: Iterable[PipingElement]) -> tuple[list[PipingElement], list[PipingElement]]:
    """Split a network into assessable elements and those with unknown connectivity.

    An element whose connectivity is indeterminable has joined_to == [] for the
    same reason a genuinely isolated element does, so the tier marker — not the
    empty list — is what separates them.
    """
    assessable: list[PipingElement] = []
    indeterminable: list[PipingElement] = []
    for element in network:
        source = (element.properties or {}).get(CONNECTIVITY_SOURCE_KEY)
        if source == INDETERMINABLE:
            indeterminable.append(element)
        else:
            assessable.append(element)
    return assessable, indeterminable


def _components(elements: list[PipingElement]) -> dict[str, int]:
    """Return element id -> connected-component index, over joined_to."""
    parent: dict[str, str] = {element.id: element.id for element in elements}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    for element in elements:
        for other_id in element.joined_to:
            if other_id in parent:
                union(element.id, other_id)

    roots = {}
    labels: dict[str, int] = {}
    for element in elements:
        root = find(element.id)
        if root not in roots:
            roots[root] = len(roots)
        labels[element.id] = roots[root]
    return labels


def _candidate_pairs(
    elements: list[PipingElement],
) -> list[tuple[PipingElement, PipingElement, str]]:
    """Return every dissimilar-material couple in the network, with its separation.

    Direct contact is a shared joint. Same-loop pairs share a system and a
    connected path but never touch; a same-loop pair whose material combination
    already meets at a joint is dropped, because substituting one of the two
    materials resolves both and a second finding adds no action.
    """
    by_id = {element.id: element for element in elements}
    direct: dict[tuple[str, str], tuple[PipingElement, PipingElement]] = {}

    for element in elements:
        for other_id in element.joined_to:
            other = by_id.get(other_id)
            if other is None or other.material == element.material:
                continue
            key = tuple(sorted((element.id, other.id)))
            if key not in direct:
                direct[key] = (by_id[key[0]], by_id[key[1]])

    joined = set(direct)
    direct_combinations = {
        frozenset((left.material, right.material)) for left, right in direct.values()
    }

    labels = _components(elements)
    same_loop: dict[tuple[str, str], tuple[PipingElement, PipingElement]] = {}
    for left, right in itertools.combinations(elements, 2):
        key = tuple(sorted((left.id, right.id)))
        if key in joined or left.material == right.material:
            continue
        if labels[left.id] != labels[right.id] or left.system != right.system:
            continue
        if frozenset((left.material, right.material)) in direct_combinations:
            continue
        same_loop.setdefault(key, (by_id[key[0]], by_id[key[1]]))

    pairs = [(left, right, DIRECT_CONTACT) for _, (left, right) in sorted(direct.items())]
    pairs += [(left, right, SAME_LOOP) for _, (left, right) in sorted(same_loop.items())]
    return pairs


# ---------------------------------------------------------------------------
# Mitigation
# ---------------------------------------------------------------------------


def _mitigation(
    parameters: dict,
    left: PipingElement,
    right: PipingElement,
) -> tuple[dict, bool]:
    """Return the (mitigation_row, mitigated) for a couple.

    A dielectric union breaks metallic continuity across the joint whichever
    side of the pair records it.
    """
    factors = parameters["mitigation_factors"]
    for element in (left, right):
        joint = element.joint_type
        key = joint.value if isinstance(joint, JointType) else joint
        if key and key in factors and not str(key).startswith("_"):
            return factors[key], True
    return factors.get("_default", {"factor": 1.0, "label": "unmitigated"}), False


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
    metadata: Optional[dict] = None,
) -> Issue:
    """Build a data-quality Issue for a couple or element XM-001 cannot assess."""
    payload = {
        "check": check,
        "material": element.material,
        "environment_class": _environment_key(element),
    }
    payload.update(metadata or {})
    return make_issue(
        id=next_id(),
        element_id=element.id,
        rule_id=f"{RULE_ID}.DQ",
        title=title,
        mechanism=DATA_QUALITY,
        band=RiskBand.LOW,
        score=0.0,
        mitigation=mitigation,
        description=description,
        metadata=payload,
        citations=[
            {
                "standard": "BIMGUARD-XM-001",
                "clause": "ANODE_IDENTIFICATION",
                "reason": "Couple cannot be assessed; silence would read as no galvanic risk.",
            }
        ],
    )


def _couple_issue(
    anode: PipingElement,
    cathode: PipingElement,
    *,
    parameters: dict,
    next_id: Callable[[], str],
    separation: str,
    gap_v: float,
    environment_key: str,
    environment_severity: float,
) -> Issue:
    """Score one resolved couple and build its Issue."""
    weights = parameters["weights"]
    normalisation = float(
        (parameters["voltage_normalisation_v"] or {}).get("value", 1.0)
        if isinstance(parameters["voltage_normalisation_v"], dict)
        else parameters["voltage_normalisation_v"]
    )
    voltage_risk = min(gap_v / normalisation, 1.0) if normalisation else 0.0

    separation_row = parameters["separation_factors"][separation]
    separation_factor = float(separation_row["factor"])

    raw = (
        float(weights["voltage"]) * voltage_risk
        + float(weights["separation"]) * separation_factor
        + float(weights["environment"]) * environment_severity
    )

    mitigation_row, mitigated = _mitigation(parameters, anode, cathode)
    mitigation_factor = float(mitigation_row["factor"])
    composite = raw * mitigation_factor

    band = band_from_score(composite, parameters["risk_band_thresholds"])
    displayed = round(composite, 3)

    description = (
        f"{anode.material} ({anode.id}) sacrifices to {cathode.material} ({cathode.id}) "
        f"across a {gap_v:.3f} V gap in {environment_key}, {separation.replace('_', ' ')}. "
        f"Composite {displayed} ({band.value}) from voltage {voltage_risk:.3f}, separation "
        f"{separation_factor}, environment {environment_severity}, mitigation "
        f"{mitigation_factor}."
    )
    if mitigated:
        description += (
            f" Credit applied for {mitigation_row.get('label', 'mitigation')}: "
            "verify union integrity at commissioning."
        )
        mitigation_text = (
            f"A {mitigation_row.get('label', 'mitigation')} is modelled at this joint. "
            "Confirm it is installed and intact at commissioning; the credit depends on it."
        )
    else:
        mitigation_text = (
            f"Break metallic continuity between {anode.material} and {cathode.material} with a "
            f"dielectric union, or substitute the {anode.material} section."
        )

    return make_issue(
        id=next_id(),
        element_id=anode.id,
        rule_id=f"{RULE_ID}.01",
        title=(
            f"Galvanic couple - {anode.material} sacrifices to {cathode.material} "
            f"({separation.replace('_', ' ')})"
        ),
        mechanism=MECHANISM,
        band=band,
        score=composite,
        mitigation=mitigation_text,
        description=description,
        metadata={
            "anode_id": anode.id,
            "cathode_id": cathode.id,
            "anode_material": anode.material,
            "cathode_material": cathode.material,
            "voltage_gap_v": gap_v,
            "voltage_risk": voltage_risk,
            "separation": separation,
            "separation_factor": separation_factor,
            "environment_class": environment_key,
            "environment_severity": environment_severity,
            "mitigated": mitigated,
            "mitigation_factor": mitigation_factor,
            "raw_score_exact": raw,
            "composite_score_exact": composite,
        },
        citations=[
            {
                "standard": SERIES_STANDARD,
                "clause": f"{anode.material} / {cathode.material}",
                "reason": f"potential gap {gap_v:.3f} V, normalised to {voltage_risk:.3f}",
            },
            {
                "standard": str(separation_row.get("cite", "BS 8539")),
                "clause": separation,
                "reason": f"separation factor {separation_factor}",
            },
            {
                "standard": str(
                    parameters["environment_severity"][environment_key].get("cite")
                    or "EN ISO 15329:2007"
                ),
                "clause": environment_key,
                "reason": f"environment severity {environment_severity}",
            },
            {
                "standard": str(mitigation_row.get("cite", "BS 8539")),
                "clause": str(mitigation_row.get("label", "unmitigated")),
                "reason": f"mitigation factor {mitigation_factor}",
            },
        ],
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def compare(
    network: Iterable[PipingElement],
    rule_pack: dict,
    id_allocator: Any = None,
) -> list[Issue]:
    """Assess a piping network for cross-material galvanic couples.

    Args:
        network: The elements to assess. An empty network is not an error.
        rule_pack: The XM-001 pack, as returned by load_rule_pack().
        id_allocator: Optional run-wide IssueIdAllocator. When omitted, ids
            are minted from a run-local counter.

    Returns:
        One Issue per couple that clears the compatibility floor — mitigated
        couples included, banded Low — plus data-quality Issues for elements
        whose connectivity, material or anode direction cannot be resolved.

    Raises:
        ValueError: If the rule pack is missing a required parameter key.
    """
    parameters = _require_parameters(rule_pack)
    next_id = _allocator(id_allocator)

    elements, indeterminable = _assessable(network)
    issues: list[Issue] = [
        _data_quality(
            element,
            next_id=next_id,
            check="connectivity_indeterminable",
            title=f"XM-001 skipped: connectivity indeterminable on {element.id}",
            description=(
                "No ports, centerline or centroid, so adjacency cannot be established. "
                "An empty joined_to here is absence of evidence, not evidence of isolation."
            ),
            mitigation="Restore geometry or port connectivity for this element so its "
            "neighbours can be resolved.",
        )
        for element in indeterminable
    ]

    series = parameters["galvanic_series"]
    floor_enabled = bool((parameters.get("compatibility_floor") or {}).get("enabled", True))
    threshold_classes = parameters.get("environment_threshold_class") or {}
    thresholds = parameters["compatibility_thresholds"] or {}
    reported: set[tuple[str, str]] = set()

    for left, right, separation in _candidate_pairs(elements):
        left_entry, right_entry = series.get(left.material), series.get(right.material)
        if not isinstance(left_entry, dict) or not isinstance(right_entry, dict):
            missing = left if not isinstance(left_entry, dict) else right
            key = ("material_not_in_series", missing.id)
            if key not in reported:
                reported.add(key)
                issues.append(
                    _data_quality(
                        missing,
                        next_id=next_id,
                        check="material_not_in_series",
                        title=f"XM-001 not assessed: {missing.material} absent from the series",
                        description=(
                            f"'{missing.material}' has no entry in the galvanic series, so no "
                            "potential gap can be computed. An unlisted material is unassessed, "
                            "not benign."
                        ),
                        mitigation=f"Add {missing.material} to the GC-001 galvanic series, or "
                        "confirm the material normalisation is correct.",
                    )
                )
            continue

        resolved = _resolve_anode(parameters, left, left_entry, right, right_entry)
        if resolved is None:
            key = ("anode_unresolvable", left.id)
            if key not in reported:
                reported.add(key)
                issues.append(
                    _data_quality(
                        left,
                        next_id=next_id,
                        check="anode_unresolvable",
                        title=(
                            f"XM-001 not assessed: cannot name the anode between "
                            f"{left.material} and {right.material}"
                        ),
                        description=(
                            "Neither the series 'noble' flags nor a declared series_convention "
                            "resolves which material sacrifices. Naming the wrong one would send "
                            "a substitution to the wrong element."
                        ),
                        mitigation="Declare parameters.series_convention in the XM-001 pack, or "
                        "add 'noble' flags to the galvanic series entries.",
                        metadata={"counterpart_id": right.id, "counterpart_material": right.material},
                    )
                )
            continue

        anode, cathode = resolved
        anode_potential, cathode_potential = (
            _potential(series[anode.material]),
            _potential(series[cathode.material]),
        )
        gap_v = abs(anode_potential - cathode_potential)

        environment_key, environment_severity = _pair_environment(parameters, left, right)

        # Compatibility floor: below the environment's threshold there is no
        # meaningful driving voltage for contact to amplify, so the pair is not
        # a couple at all. An unresolvable threshold fails open.
        if floor_enabled:
            threshold_class = threshold_classes.get(environment_key)
            threshold_row = thresholds.get(threshold_class) if threshold_class else None
            threshold = (
                threshold_row.get("max_safe_voltage_v")
                if isinstance(threshold_row, dict)
                else None
            )
            if threshold is not None and gap_v < float(threshold):
                continue

        issues.append(
            _couple_issue(
                anode,
                cathode,
                parameters=parameters,
                next_id=next_id,
                separation=separation,
                gap_v=gap_v,
                environment_key=environment_key,
                environment_severity=environment_severity,
            )
        )

    return issues
