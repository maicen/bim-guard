"""
Compliance orchestrator: coordinates corrosion engines and Path B (MM/XM) via feature flags.

Entry point: orchestrate_workflow(elements, run_id)
- Runs Path A (GC/CC/MC) always
- Runs MM-001 if FEATURE_PATH_B_MM is enabled
- Runs XM-001 if FEATURE_PATH_B_XM is enabled
- Projects findings onto per-element dicts for UI
"""

from typing import Any

from app.modules.config import FEATURE_PATH_B_MM, FEATURE_PATH_B_XM
from app.modules.module4_comparator.compliance_runner import run_compliance_checks
from app.modules.module4_comparator.cross_material import (
    compare as compare_xm,
)
from app.modules.module4_comparator.cross_material import (
    load_rule_pack as load_xm_pack,
)
from app.modules.module4_comparator.issue_adapter import (
    IssueIdAllocator,
    issues_from_path_a,
    path_a_view,
)
from app.modules.module4_comparator.material_media import (
    compare as compare_mm,
)
from app.modules.module4_comparator.material_media import (
    load_rule_pack as load_mm_pack,
)
from app.services.pipeline_tracker import (
    MM_ENGINE,
    XM_ENGINE,
    Stage,
    Status,
    active,
    complete,
    emit,
    reporting_failures,
)


def orchestrate_workflow(elements: list[Any], run_id: str = "BGR-2026") -> list[dict]:
    """
    Run the full compliance pipeline: Path A + conditional MM-001/XM-001.

    Args:
        elements: IFC elements to check (ifcopenshell.entity_instance objects).
        run_id: Run identifier for issue numbering (default "BGR-2026").

    Returns:
        List of dicts, one per element, with Path A results and optional Path B findings.
    """
    path_a_results = run_compliance_checks(elements)
    id_allocator = IssueIdAllocator(run_id)
    path_b_issues = []

    mm_issues_total = 0
    xm_issues_total = 0

    if FEATURE_PATH_B_MM:
        emit(MM_ENGINE, Stage.ENGINE_EXECUTION, elements_total=len(elements))
        try:
            # reporting_failures marks the engine failed on the way out and
            # re-raises; the handler below is left exactly as it was, because a
            # swallowed Path B failure is a pinned defect (see
            # tests/test_orchestrator.py) that tracking does not fix.
            with reporting_failures(MM_ENGINE):
                mm_pack = load_mm_pack()
                for element in elements:
                    mm_issues = compare_mm(element, rule_pack=mm_pack, id_allocator=id_allocator)
                    path_b_issues.extend(mm_issues)
                    mm_issues_total += len(mm_issues)
        except Exception as exc:
            print(f"MM-001 error: {type(exc).__name__}: {exc}")
        else:
            emit(MM_ENGINE, Stage.RISK_SCORING, findings=mm_issues_total)

    if FEATURE_PATH_B_XM:
        emit(XM_ENGINE, Stage.ENGINE_EXECUTION, elements_total=len(elements))
        try:
            with reporting_failures(XM_ENGINE):
                xm_pack = load_xm_pack()
                for element in elements:
                    xm_issues = compare_xm(element, rule_pack=xm_pack, id_allocator=id_allocator)
                    path_b_issues.extend(xm_issues)
                    xm_issues_total += len(xm_issues)
        except Exception as exc:
            print(f"XM-001 error: {type(exc).__name__}: {exc}")
        else:
            emit(XM_ENGINE, Stage.RISK_SCORING, findings=xm_issues_total)

    path_a_issues = issues_from_path_a(path_a_results, id_allocator=id_allocator, include_low=False)
    all_issues = path_a_issues + path_b_issues
    output = path_a_view(all_issues, path_a_results)

    # Stage 5 and completion are stamped after the merge, because that is where
    # a Path B finding actually becomes part of the report. An engine whose loop
    # raised is left at FAILED -- complete() is only reached for the engines that
    # got through their loop.
    for code, enabled, issue_count in (
        (MM_ENGINE, FEATURE_PATH_B_MM, mm_issues_total),
        (XM_ENGINE, FEATURE_PATH_B_XM, xm_issues_total),
    ):
        if not enabled:
            continue
        tracker = active()
        if tracker is not None and tracker.run(code).status is Status.FAILED:
            continue
        emit(code, Stage.REPORT_ASSEMBLY, issues=issue_count)
        complete(code)

    return output
