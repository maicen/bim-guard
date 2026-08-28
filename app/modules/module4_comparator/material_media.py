"""
MM-001: Material-Media Compatibility engine.

Evaluates whether a piping material is compatible with the carrying medium
(water, steam, chemical, etc.) under the specified environmental conditions.

Entry point: compare(element, rule_pack, id_allocator) -> list[Issue]
"""

from pathlib import Path
from typing import Any
from app.modules.module4_comparator.issue_schema import Issue, RiskBand, make_issue
from app.services.pipeline_tracker import MM_ENGINE, Stage, emit, increment


MM_PACK_PATH = Path("data/rulesets/mm_001_material_media.json")


def load_rule_pack(*, path: Path | None = None) -> dict:
    """Load and validate the MM-001 material-media rule pack.
    
    Args:
        path: Optional override path. Defaults to data/rulesets/mm_001_material_media.json
    
    Returns:
        Validated rule pack dict with material compatibility matrices.
    
    Raises:
        FileNotFoundError: If the pack file does not exist.
        ValueError: If required keys are missing from the pack.
    """
    if path is None:
        path = MM_PACK_PATH
    
    if not path.exists():
        raise FileNotFoundError(f"MM-001 rule pack not found: {path}")
    
    import json
    with open(path) as f:
        pack = json.load(f)
    
    # Validate required structure
    required_keys = {"materials", "media", "environments", "compatibility_matrix"}
    if not all(k in pack for k in required_keys):
        raise ValueError(f"MM-001 rule pack missing keys: {required_keys - set(pack.keys())}")
    
    return pack


def compare(
    element: Any,
    *,
    rule_pack: dict,
    id_allocator: Any,
) -> list[Issue]:
    """
    Evaluate material-media compatibility for a piping element.
    
    Args:
        element: IFC piping element (must have material, medium, environment properties).
        rule_pack: MM-001 rule pack from load_rule_pack().
        id_allocator: IssueIdAllocator for unique issue IDs.
    
    Returns:
        List of Issues (zero if material/medium combo is compatible).

    Reports stage 3 (Engine Execution) and its per-element counters to the bound
    pipeline tracker. The calls are no-ops when nothing is bound, so the tests
    and the CLI paths that call this directly behave exactly as before; the
    caller that loops elements -- ``compliance_orchestrator.orchestrate_workflow``
    -- owns the totals and the later stages.
    """
    emit(MM_ENGINE, Stage.ENGINE_EXECUTION)
    increment(MM_ENGINE, elements_analyzed=1)

    issues = []
    
    # Extract material, medium, environment from element properties
    material = element.get_property("Material", "")
    medium = element.get_property("Medium", "")
    environment = element.get_property("Environment", "")
    
    if not all([material, medium, environment]):
        increment(MM_ENGINE, elements_incomplete=1)
        return issues  # Insufficient data; no finding
    
    # Look up compatibility score in the matrix
    compat_score = rule_pack.get("compatibility_matrix", {}).get(
        f"{material}:{medium}:{environment}", 0.0
    )
    
    # Score 0.0–0.35 = compatible; 0.35+ = at risk
    if compat_score < 0.35:
        return issues  # Compliant
    
    # Determine band from score
    if compat_score < 0.60:
        band = RiskBand.MEDIUM
    elif compat_score < 0.85:
        band = RiskBand.HIGH
    else:
        band = RiskBand.CRITICAL
    
    # Create Issue
    issue = make_issue(
        id=id_allocator.next("MM"),
        element_id=element.GlobalId,
        rule_id="MM-001.01",
        title=f"MM-001 on {element.Name}",
        mechanism=f"MM-001 material-media compatibility",
        band=band,
        score=compat_score,
        mitigation=f"Specify alternative material or isolate {material} from {medium}",
        description=f"{material} in {medium} environment scored {compat_score:.2f}",
        metadata={
            "path": "B",
            "material": material,
            "medium": medium,
            "environment": environment,
            "compatibility_score": compat_score,
            "source_dict_keys": ["material", "medium", "environment"],
        },
        citations=[],
    )
    issues.append(issue)
    increment(MM_ENGINE, findings=1, **{f"band_{band.value}": 1})
    
    return issues
