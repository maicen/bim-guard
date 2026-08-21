"""
app/modules/module4_comparator/issue_adapter.py

The only module that knows both Module4 shapes.

Path A (`compliance_runner.run_compliance_checks()`) returns one flat dict per
element carrying three mechanisms at once. Path B (`material_media.compare()`,
`cross_material.compare()`) returns `list[Issue]` — the declared data contract
between Module4 and Module5 (`issue_schema.py`).

This adapter lifts Path A dicts into Issues so both paths speak one language,
and projects Issues back onto the per-element dict spine so the existing
analyze card keeps rendering unchanged.

See docs/integration_plan_mm_xm.md section 4 for the decisions behind this.
"""

from __future__ import annotations

from app.modules.module4_comparator.issue_schema import (
    Issue,
    RiskBand,
    make_issue,
    to_dict,
)

# Mechanism specs: (band_key, score_key, rule_id, metadata_keys_to_lift).
# Keys are exactly those run_compliance_checks() emits; order fixes the
# per-element emission order to galvanic, crevice, MIC.
_MechanismSpec = (
    (
        "galvanic_band",
        "galvanic_score",
        "GC-001.01",
        (
            "voltage_gap_V",
            "voltage_threshold",
            "pren_fail",
            "anodic_material",
            "material_a",
            "material_b",
        ),
    ),
    (
        "crevice_band",
        "crevice_score",
        "CC-001.01",
        ("crevice_geometry", "cct_adequate", "joint_type"),
    ),
    (
        "mic_band",
        "mic_score",
        "MC-001.01",
        ("mic_flow_class", "mic_temperature_class", "mic_dead_leg_class"),
    ),
)

# Severity order for "which band is worse" comparisons. RiskBand values are
# lowercase strings, so comparing them directly would sort alphabetically
# ("critical" < "high" < "low" < "medium") and silently pick the wrong winner.
_BAND_RANK = {
    RiskBand.LOW.value: 0,
    RiskBand.MEDIUM.value: 1,
    RiskBand.HIGH.value: 2,
    RiskBand.CRITICAL.value: 3,
}


class IssueIdAllocator:
    """Run-wide unique Issue ids with a per-mechanism prefix.

    material_media._finding(), cross_material._finding() and
    ComplianceOrchestrator._results_to_issues() each mint 'BGR-%04d' from a
    counter starting at zero, so any run combining two of them produces
    duplicate ids. BCF needs one topic per id and IssueTracker keys on it, so
    allocation belongs to the run rather than to the engine.
    """

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._counters: dict[str, int] = {}

    def next(self, prefix: str) -> str:
        """Return the next id for `prefix`, e.g. 'GC-0001', then 'GC-0002'.

        Counters are independent per prefix, so 'MM-0001' and 'XM-0001' can
        both exist in one run without colliding.
        """
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        return f"{prefix}-{self._counters[prefix]:04d}"


def issues_from_path_a(
    results: list[dict],
    *,
    id_allocator: IssueIdAllocator,
    include_low: bool = False,
) -> list[Issue]:
    """Convert run_compliance_checks() dicts into Issues.

    One Issue per element per mechanism that scored above its own band floor —
    not one per element. A dict carrying galvanic MEDIUM and crevice HIGH is
    two findings to a reviewer and must not collapse into one.

    Args:
        results: Dicts from run_compliance_checks().
        id_allocator: Run-wide id source; see IssueIdAllocator.
        include_low: Emit Issues for LOW-band mechanisms too. Default False,
            matching Path B, where a compliant element produces nothing.

    Returns:
        Issues in input order, mechanism order galvanic, crevice, MIC.

    Raises:
        ValueError: A band string the RiskBand enum does not recognise.
    """
    issues: list[Issue] = []

    for result in results:
        element_id = result["guid"]
        element_name = result["name"]

        for band_key, score_key, rule_id, metadata_keys in _MechanismSpec:
            # Mechanism did not run for this element — nothing to report.
            if band_key not in result:
                continue

            band_str = str(result[band_key])
            score = result[score_key]
            mechanism_code = rule_id.split(".")[0]  # "GC-001" from "GC-001.01"
            mechanism_prefix = mechanism_code.split("-")[0]  # "GC" from "GC-001"

            # Normalise "CRITICAL" -> RiskBand.CRITICAL -> "critical".
            try:
                band = RiskBand(band_str.strip().lower())
            except ValueError:
                raise ValueError(
                    f"Unknown band '{band_str}' for {element_name} / {mechanism_code}"
                ) from None

            if band is RiskBand.LOW and not include_low:
                continue

            # Lift the mechanism-specific keys this dict actually carries, and
            # record exactly which keys were consumed so a reviewer can trace
            # any projected value back to its origin.
            consumed = [band_key, score_key]
            metadata: dict = {
                "path": "A",
                "mechanism_code": mechanism_code,
                "dominant_mechanism": result.get("dominant_mechanism", ""),
                # Path A discards the engine standards references before
                # returning, so there is nothing honest to cite. An empty list
                # is a visible gap; a hardcoded standard is a false audit
                # trail. See integration_plan_mm_xm.md section 4.1.
                "citations_unavailable": "path_a_runner_discards_engine_citations",
            }
            for key in metadata_keys:
                if key in result:
                    metadata[key] = result[key]
                    consumed.append(key)
            metadata["source_dict_keys"] = consumed

            issues.append(
                make_issue(
                    id=id_allocator.next(mechanism_prefix),
                    element_id=element_id,
                    rule_id=rule_id,
                    title=f"{mechanism_code} on {element_name}",
                    mechanism=f"{mechanism_code} {band.value}",
                    band=band,
                    score=score,
                    mitigation=result.get("mitigation", ""),
                    description=result.get("action"),
                    metadata=metadata,
                    citations=[],
                )
            )

    return issues


def path_a_view(issues: list[Issue], base_results: list[dict]) -> list[dict]:
    """Project Issues back onto the per-element dicts the UI renders.

    base_results supplies the one-row-per-element spine, including compliant
    elements that produce no Issue. That spine is what makes "no elements
    flagged" a statement about coverage rather than about silence — building
    the table from Issues alone would lose the denominator.

    Path B findings merge onto the row with the matching guid; Issues with no
    matching row (an XM couple whose anode is not in base_results) are
    appended as their own rows, flagged with path_b_only.

    Adds per row: path_b_issues (list[dict]), path_b_band (str|None),
    path_b_count (int), mm_band, mm_score, xm_band, xm_score.
    Leaves every existing key untouched, and never mutates base_results.
    """
    output = [dict(r) for r in base_results]

    for row in output:
        row["path_b_issues"] = []
        row["path_b_band"] = None
        row["path_b_count"] = 0
        row["mm_band"] = None
        row["mm_score"] = 0.0
        row["xm_band"] = None
        row["xm_score"] = 0.0

    # Template for orphan rows: every spine key, blanked. Captured before the
    # merge loop so an orphan appended earlier cannot become the template.
    orphan_template = {key: None for key in output[0]} if output else {}

    by_guid = {row["guid"]: row for row in output}

    for issue in issues:
        row = by_guid.get(issue.element_id)
        if row is None:
            row = dict(orphan_template)
            row.update(
                {
                    "guid": issue.element_id,
                    "path_b_issues": [],
                    "path_b_band": None,
                    "path_b_count": 0,
                    "mm_band": None,
                    "mm_score": 0.0,
                    "xm_band": None,
                    "xm_score": 0.0,
                    "path_b_only": True,
                }
            )
            output.append(row)
            # Register it so further Issues for the same absent element land
            # on this row instead of spawning a duplicate.
            by_guid[issue.element_id] = row

        row["path_b_issues"].append(to_dict(issue))
        row["path_b_count"] += 1

        # Worst band wins, by severity rank rather than string order.
        current = row["path_b_band"]
        if current is None or _BAND_RANK[issue.band.value] > _BAND_RANK[current]:
            row["path_b_band"] = issue.band.value

        # Track MM and XM separately so the card can show which pack fired.
        # rule_id is "MM-001.<material>.<media>" / "XM-001.<anode>.<cathode>".
        prefix = issue.rule_id.split(".")[0]
        if prefix == "MM-001":
            if row["mm_band"] is None or issue.score > row["mm_score"]:
                row["mm_score"] = issue.score
                row["mm_band"] = issue.band.value
        elif prefix == "XM-001":
            if row["xm_band"] is None or issue.score > row["xm_score"]:
                row["xm_score"] = issue.score
                row["xm_band"] = issue.band.value

    return output
