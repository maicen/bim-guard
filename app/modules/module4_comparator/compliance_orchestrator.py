"""
Compliance orchestrator: coordinates corrosion engines and Path B (MM/XM) via feature flags.

Entry point: orchestrate_workflow(elements, run_id)
- Runs Path A (GC/CC/MC) always
- Runs MM-001 if FEATURE_PATH_B_MM is enabled
- Runs XM-001 if FEATURE_PATH_B_XM is enabled
- Projects findings onto per-element dicts for UI
"""

import os
from typing import Any

from app.modules.module4_comparator.compliance_runner import run_compliance_checks
from app.modules.module4_comparator.issue_adapter import (
    issues_from_path_a,
    path_a_view,
    IssueIdAllocator,
)
from app.modules.module4_comparator.material_media import load_rule_pack as load_mm_pack, compare as compare_mm
from app.modules.module4_comparator.cross_material import load_rule_pack as load_xm_pack, compare as compare_xm


def orchestrate_workflow(elements: list[Any], run_id: str = "BGR-2026") -> list[dict]:
    """
    Run the full compliance pipeline: Path A + conditional MM-001/XM-001.
    
    Args:
        elements: IFC elements to check (ifcopenshell.entity_instance objects).
        run_id: Run identifier for issue numbering (default "BGR-2026").
    
    Returns:
        List of dicts, one per element, with Path A results and optional Path B findings.
    """
    # Read feature flags from environment (read at call time to avoid config DB dependency)
    feature_mm = os.environ.get("FEATURE_PATH_B_MM", "0") == "1"
    feature_xm = os.environ.get("FEATURE_PATH_B_XM", "0") == "1"
    
    # ========== PATH A: Galvanic / Crevice / MIC ==========
    path_a_results = run_compliance_checks(elements)
    
    # ========== PATH B SETUP ==========
    id_allocator = IssueIdAllocator(run_id)
    path_b_issues = []
    
    # ========== MM-001: Material-Media Compatibility ==========
    if feature_mm:
        try:
            mm_pack = load_mm_pack()
            for element in elements:
                mm_issues = compare_mm(element, rule_pack=mm_pack, id_allocator=id_allocator)
                path_b_issues.extend(mm_issues)
        except Exception as e:
            # Log but don't crash; MM-001 offline fallback
            print(f"MM-001 error: {e}")
    
    # ========== XM-001: Cross-Material Galvanic ==========
    if feature_xm:
        try:
            xm_pack = load_xm_pack()
            for element in elements:
                xm_issues = compare_xm(element, rule_pack=xm_pack, id_allocator=id_allocator)
                path_b_issues.extend(xm_issues)
        except Exception as e:
            # Log but don't crash; XM-001 requires DB
            print(f"XM-001 error: {e}")
    
    # ========== PROJECT: Path A + Path B onto UI dicts ==========
    # Convert Path A results to Issues, then project back with Path B findings merged
    path_a_issues = issues_from_path_a(path_a_results, id_allocator=id_allocator, include_low=False)
    all_issues = path_a_issues + path_b_issues
    
    # Project onto the per-element spine
    output = path_a_view(all_issues, path_a_results)
    
    return output
