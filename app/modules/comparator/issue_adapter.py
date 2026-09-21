"""
app/modules/comparator/issue_adapter.py

Lifts a SHACL validation report, or a registered engine's
``RuleEvaluationResult``, into the shared ``Issue`` contract
(``issue_schema.py``) so BCF/dashboard consumers don't need to know which
evaluator produced a finding.
"""

from __future__ import annotations

from rdflib import RDF, Graph
from rdflib.namespace import SH

from app.modules.comparator.issue_schema import Issue, RiskBand, make_issue
from app.modules.ifc_reader.bot_graph import BIMGUARD

#: Mechanism string marking an Issue as a data gap rather than a verdict.
DATA_QUALITY = "data_quality"


# ── SHACL validation report lift ──────────────────────────────────────────
# Path C: app.engines.bimguard_shacl_engine returns a RuleEvaluationResult
# whose raw_result is a pyshacl sh:ValidationReport graph. This is the only
# function that knows that graph's shape, mirroring how the rest of this
# module is "the only module that knows both [dict] comparator shapes".

_SEVERITY_TO_BAND = {
    SH.Violation: RiskBand.HIGH,
    SH.Warning: RiskBand.MEDIUM,
    SH.Info: RiskBand.LOW,
}

_ELEMENT_PREFIX = f"{BIMGUARD['element/']}"


def _local_id(uri: str, prefix: str) -> str | None:
    text = str(uri)
    return text[len(prefix) :] if text.startswith(prefix) else None


def lift_shacl_report(
    results_graph: Graph, *, shapes_graph: Graph | None = None, mechanism: str = "CODE-SHACL"
) -> list[Issue]:
    """Convert a pyshacl `sh:ValidationReport` graph into `Issue` records.

    Each `sh:ValidationResult` becomes one Issue: `sh:focusNode` (a
    `bot_graph.element_uri()`) resolves to the IFC GlobalId, and the rule id
    comes from `bimguard:ruleId` on `sh:sourceShape`.

    Where that lookup resolves depends on what kind of shape produced the
    violation. For a SHACL Core property constraint, `sh:sourceShape` is the
    *property* shape blank node (`shacl_generator._add_shape()`'s), and
    pyshacl inlines a blank node's own triples into the report graph, so
    `bimguard:ruleId` is already present in `results_graph`. For a `sh:sparql`
    constraint, `sh:sourceShape` is instead the enclosing `sh:NodeShape`'s own
    URI (a named node, never inlined) -- `results_graph` alone has no triples
    about it, so `shapes_graph` (the original compiled shapes, still in scope
    at the caller) is required to resolve `bimguard:ruleId` for that case.

    `sh:resultMessage` is the description, and `sh:resultSeverity` maps onto
    `RiskBand`. A result missing a recognisable focus node or rule id is
    skipped rather than guessed.
    """
    issues: list[Issue] = []

    for result in results_graph.subjects(RDF.type, SH.ValidationResult):
        focus_node = results_graph.value(result, SH.focusNode)
        source_shape = results_graph.value(result, SH.sourceShape)
        element_id = _local_id(focus_node, _ELEMENT_PREFIX) if focus_node else None
        rule_id = results_graph.value(source_shape, BIMGUARD.ruleId) if source_shape else None
        if rule_id is None and source_shape is not None and shapes_graph is not None:
            rule_id = shapes_graph.value(source_shape, BIMGUARD.ruleId)
        rule_id = str(rule_id) if rule_id else None
        if not element_id or not rule_id:
            continue

        message = str(results_graph.value(result, SH.resultMessage) or f"{rule_id} violated")
        severity = results_graph.value(result, SH.resultSeverity)
        band = _SEVERITY_TO_BAND.get(severity, RiskBand.HIGH)

        issues.append(
            make_issue(
                id=f"SHACL-{rule_id}-{element_id}",
                element_id=element_id,
                rule_id=rule_id,
                title=message,
                mechanism=mechanism,
                band=band,
                score=1.0,
                mitigation="",
                assignee_role="Compliance reviewer",
                metadata={"source": "shacl"},
            )
        )

    return issues


# ── engine_registry RuleEvaluationResult lift ─────────────────────────────
# Path D: any RuleEvaluator registered in app.modules.comparator.engine_registry
# (e.g. EgressAnalysisEngine, SpatialDaylightEngine) returns one
# RuleEvaluationResult per record evaluated. This converts a FAIL result into
# the same Issue contract every other path produces, so BCF/dashboard
# consumers don't need to know which engine produced a finding.

_ENGINE_BAND_TO_RISK_BAND = {
    "low": RiskBand.LOW,
    "medium": RiskBand.MEDIUM,
    "high": RiskBand.HIGH,
    "critical": RiskBand.CRITICAL,
}


def lift_engine_result(result, *, mechanism: str) -> Issue | None:
    """Convert one FAIL `RuleEvaluationResult` into an `Issue`, or None.

    Only `status == "FAIL"` becomes a finding -- PASS and NOT_ASSESSED are
    not findings (NOT_ASSESSED is a data-quality/config gap the caller may
    still want to surface separately, but that is not this function's job).
    """
    if result.status != "FAIL":
        return None

    band = _ENGINE_BAND_TO_RISK_BAND.get(str(result.band or "").strip().lower(), RiskBand.HIGH)
    rule_id = str((result.details or {}).get("code_reference") or result.rule_type)
    title = str(result.action or f"{rule_id} violated")

    return make_issue(
        id=f"{result.rule_type}-{result.element_id}",
        element_id=str(result.element_id or "UNKNOWN"),
        rule_id=rule_id,
        title=title,
        mechanism=mechanism,
        band=band,
        score=result.score,
        mitigation=str(result.action or ""),
        assignee_role="Compliance reviewer",
        metadata={"source": "engine_registry", "check_type": (result.details or {}).get("check_type")},
    )
