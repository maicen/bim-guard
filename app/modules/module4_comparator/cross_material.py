"""
XM-001: Cross-Material Galvanic Compatibility engine.

Evaluates galvanic couples between dissimilar piping materials in contact,
suppressing false positives below environment-dependent voltage thresholds.

Entry point: compare(element, rule_pack, id_allocator) -> list[Issue]
"""

from pathlib import Path
from typing import Any
from app.modules.module4_comparator.issue_schema import Issue, RiskBand, make_issue


XM_PACK_PATH = Path("data/rulesets/xm_001_cross_material.json")


def load_rule_pack(*, path: Path | None = None) -> dict:
    """Load and validate the XM-001 cross-material rule pack.
    
    Args:
        path: Optional override path. Defaults to data/rulesets/xm_001_cross_material.json
    
    Returns:
        Validated rule pack dict with galvanic couple matrices.
    
    Raises:
        FileNotFoundError: If the pack file does not exist.
        ValueError: If required keys are missing from the pack.
    """
    if path is None:
        path = XM_PACK_PATH
    
    if not path.exists():
        raise FileNotFoundError(f"XM-001 rule pack not found: {path}")
    
    import json
    with open(path) as f:
        pack = json.load(f)
    
    # Validate required structure
    required_keys = {"materials", "couples", "environment_thresholds"}
    if not all(k in pack for k in required_keys):
        raise ValueError(f"XM-001 rule pack missing keys: {required_keys - set(pack.keys())}")
    
    return pack


def compare(
    element: Any,
    *,
    rule_pack: dict,
    id_allocator: Any,
) -> list[Issue]:
    """
    Evaluate cross-material galvanic compatibility for a piping element.
    
    Identifies galvanic couples between dissimilar materials, suppresses findings
    below environment-dependent voltage thresholds (NASA-STD-6012).
    
    Args:
        element: IFC piping element (must have material, adjacent_material, environment).
        rule_pack: XM-001 rule pack from load_rule_pack().
        id_allocator: IssueIdAllocator for unique issue IDs.
    
    Returns:
        List of Issues (zero if couples are below threshold for the environment).
    """
    issues = []
    
    # Extract material pair and environment from element properties
    material_a = element.get_property("Material", "")
    material_b = element.get_property("AdjacentMaterial", "")
    environment = element.get_property("Environment", "")
    
    if not all([material_a, material_b, environment]):
        return issues  # Insufficient data; no finding
    
    if material_a == material_b:
        return issues  # Same material; no galvanic couple
    
    # Normalize material pair for lookup (alphabetical order)
    pair = tuple(sorted([material_a, material_b]))
    
    # Look up galvanic voltage for this couple
    couples = rule_pack.get("couples", {})
    couple_key = f"{pair[0]}:{pair[1]}"
    galvanic_voltage = couples.get(couple_key, 0.0)
    
    if galvanic_voltage == 0.0:
        return issues  # No couple data; assume compatible
    
    # Environment-dependent threshold (NASA-STD-6012)
    thresholds = rule_pack.get("environment_thresholds", {})
    threshold = thresholds.get(environment, 0.25)  # Default 0.25V (normal environment)
    
    # Suppress below threshold
    if galvanic_voltage < threshold:
        return issues  # Below threshold; no finding
    
    # Determine band from voltage
    if galvanic_voltage < 0.50:
        band = RiskBand.MEDIUM
    elif galvanic_voltage < 0.85:
        band = RiskBand.HIGH
    else:
        band = RiskBand.CRITICAL
    
    # Create Issue
    issue = make_issue(
        id=id_allocator.next("XM"),
        element_id=element.GlobalId,
        rule_id="XM-001.01",
        title=f"XM-001 on {element.Name}",
        mechanism=f"XM-001 cross-material galvanic",
        band=band,
        score=galvanic_voltage,
        mitigation=f"Isolate {pair[0]} from {pair[1]} with gasket; add to inspection schedule",
        description=f"{pair[0]}–{pair[1]} couple scored {galvanic_voltage:.3f}V (threshold {threshold:.3f}V in {environment})",
        metadata={
            "path": "B",
            "material_a": pair[0],
            "material_b": pair[1],
            "environment": environment,
            "galvanic_voltage": galvanic_voltage,
            "environment_threshold": threshold,
            "source_dict_keys": ["material_a", "material_b", "environment"],
        },
        citations=[],
    )
    issues.append(issue)
    
    return issues
