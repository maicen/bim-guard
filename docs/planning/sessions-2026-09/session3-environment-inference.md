# TASK: Infer Environment Classification — MM-001 Gate #2

## Context
MM-001 requires three gates to fire. Session 3 fixed Gate 1 (Material). Gates 2 & 3 remain:

1. **Material** ✓ Fixed (33.9% coverage)
2. **Environment class** ✗ 0% classified (all elements)
3. **Operating temperature** ✗ 0% present

Currently: MM-001 hits the environment gate and returns 0 findings even when material is present.

**Goal:** Infer environment class from system type and design context (EN ISO 15329 wetting classes T0–T5), with same rigor and provenance as material inference.

---

## Background: Environment Classification (EN ISO 15329)

EN ISO 15329 defines wetting classes for stainless steel in corrosive environments:

| Class | Condition | Example |
|-------|-----------|---------|
| T0 | No wetting | Air, dry storage |
| T1 | Low frequency | Indoor unheated spaces |
| T2 | Occasional wetting | Roofs, outdoor with rain-off |
| T3 | Frequent wetting | Cooling water, condensation zones |
| T4 | Continuous wetting, moderate chloride | Coastal spray, potable water |
| T5 | Continuous wetting, high chloride | Sea water, de-icing salt, pools |

**For MM-001:** Each material (steel grade) has a PREN (Pitting Resistance Equivalent Number). The engine compares PREN against environment severity. If PREN too low → failure mode → finding.

Current state: Every element is "environment_unclassified" → MM-001 skips scoring.

---

## STEP 1: Audit Current Environment Extraction

**File:** `app/modules/module2_ifc_read/piping_producer.py`

Find the environment extraction code:

```bash
grep -n "environment_class\|extract.*environment\|wetting" app/modules/module2_ifc_read/piping_producer.py | head -20
```

You should see something like:

```python
def extract_environment_class(element, ifc_file):
    # Try to find environment from IFC metadata
    env = element.get_property("Environment")
    return env if env in VALID_ENVIRONMENTS else None
```

**Measure baseline:**

```bash
python -c "
from app.modules.module2_ifc_read.piping_producer import extract_piping_network
from pathlib import Path

models = Path('test-models/models').glob('*.ifc')
for model_path in sorted(models)[:3]:
    network = extract_piping_network(model_path)
    with_env = sum(1 for e in network.elements if e.environment_class is not None)
    print(f'{model_path.name}: {with_env}/{len(network.elements)} ({100*with_env/len(network.elements):.1f}%)')
"
```

Record the baseline % (likely 0–2%).

---

## STEP 2: Design Inference Function

**File:** `app/modules/module2_ifc_read/piping_producer.py`

Add a new function that maps system type → environment class:

```python
def infer_environment_from_system(system_type: PipingSystem) -> Optional[str]:
    """
    Infer environment wetting class (EN ISO 15329) from piping system type.
    
    Returns one of: T0, T1, T2, T3, T4, T5
    None if the system type doesn't clearly map to an environment class.
    
    Rationale per EN ISO 15329:
    - Potable/domestic water systems → T4 (continuous wetting, moderate chloride)
    - Chilled water → T3 (frequent wetting, condensation risk in summer)
    - Hot water → T4 (continuous, dissolved oxygen lower than potable)
    - Fire protection → T3 (occasional/periodic wetting, stagnation risk)
    - Drainage → N/A (not stainless-based; excluded by system type)
    - Process water (pools, medical) → T5 (chloride addition, continuous)
    """
    if not system_type:
        return None
    
    # Map PipingSystem enum values to wetting classes
    mapping = {
        PipingSystem.DOMESTIC_COLD_WATER: "T4",      # Potable, continuous
        PipingSystem.DOMESTIC_HOT_WATER: "T4",       # Hot potable, lower O2
        PipingSystem.CHILLED_WATER: "T3",            # Frequent wetting, condensation
        PipingSystem.CONDENSE_WATER: "T3",           # Acidic condensate, frequent
        PipingSystem.HEATING_WATER: "T4",            # Closed loop, continuous
        PipingSystem.FIRE_PROTECTION: "T3",          # Infrequent spray, stagnation
        PipingSystem.POOL_WATER: "T5",               # Chlorinated, continuous
        PipingSystem.PROCESS_COOLING: "T4",          # Industrial process water
        # Explicitly excluded (no environment classification):
        PipingSystem.RAINWATER: None,                # Usually PVC/cast iron
        PipingSystem.DRAINAGE: None,                 # Not stainless
        PipingSystem.COMPRESSED_AIR: None,           # Non-wetting
        PipingSystem.MEDICAL_GAS_VACUUM: None,       # Non-wetting
    }
    
    return mapping.get(system_type)
```

---

## STEP 3: Add Provenance Tracking

Environment inference must be tagged like material inference. Add to the element tracking:

**File:** `app/modules/module2_ifc_read/piping_producer.py`

In the `PipingElement` class (or data structure), add a field:

```python
@dataclass
class PipingElement:
    # ... existing fields ...
    environment_class: Optional[str]
    environment_source: str  # "from_ifc", "inferred", "unknown"
    environment_confidence: str  # "high", "provisional", "low"
```

When assigning environment:

```python
def extract_piping_element(...):
    # Try direct extraction first
    env_class = extract_environment_class(element, ifc_file)
    if env_class:
        source, confidence = "from_ifc", "high"
    else:
        # Try inference
        env_class = infer_environment_from_system(element.system_type)
        source = "inferred"
        confidence = "provisional" if env_class else "unknown"
    
    return PipingElement(
        ...,
        environment_class=env_class,
        environment_source=source,
        environment_confidence=confidence
    )
```

---

## STEP 4: Add Diagnostic Logging

Match material's logging pattern:

```python
import logging

logger = logging.getLogger(__name__)

def extract_piping_element(...):
    env_class = extract_environment_class(element, ifc_file)
    if env_class:
        logger.info(f"Environment found via IFC: {element.ifc_id} → {env_class}")
        source, confidence = "from_ifc", "high"
    else:
        inferred = infer_environment_from_system(element.system_type)
        if inferred:
            logger.info(f"Environment inferred from system: {element.ifc_id} (sys={element.system_type.name}) → {inferred}")
            source, confidence = "inferred", "provisional"
        else:
            logger.warning(f"Environment unclassified: {element.ifc_id} (sys={element.system_type.name if element.system_type else 'unknown'})")
            source, confidence = "unknown", "unknown"
        env_class = inferred
    
    return PipingElement(..., environment_class=env_class, environment_source=source, environment_confidence=confidence)
```

---

## STEP 5: Update Compliance Runner

**File:** `app/services/compliance_orchestrator.py` (or wherever MM-001 is called)

Verify that MM-001 receives environment_class and checks it:

```bash
grep -n "environment_class\|MM-001\|material_media" app/services/compliance_orchestrator.py | head -20
```

The runner should pass environment to MM-001. If it doesn't, wire it:

```python
# When calling MM-001:
mm_001_findings = run_mm_001(
    elements=piping_elements,
    materials=[e.material for e in piping_elements],
    environments=[e.environment_class for e in piping_elements],  # Add this
)
```

---

## STEP 6: Measure Coverage

Create a tracing script (same pattern as material):

```bash
cat > scripts/trace_environment_coverage.py << 'EOF'
#!/usr/bin/env python
"""Audit piping environment classification across IFC models.

Reports per model and overall: how many elements have environment classified,
and where the classification came from (IFC vs. inferred vs. unknown).
"""
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(name)s: %(message)s')

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.modules.module2_ifc_read.piping_producer import extract_piping_network

test_models_dir = Path("test-models/models")

coverage = {}
for ifc_file in sorted(test_models_dir.glob("*.ifc")):
    print(f"\n=== {ifc_file.name} ===")
    
    try:
        network = extract_piping_network(ifc_file)
        
        total = len(network.elements)
        from_ifc = sum(1 for e in network.elements if e.environment_source == "from_ifc")
        inferred = sum(1 for e in network.elements if e.environment_source == "inferred")
        unknown = sum(1 for e in network.elements if e.environment_source == "unknown")
        
        coverage[ifc_file.name] = (from_ifc + inferred, total, (from_ifc + inferred) / total if total else 0)
        
        print(f"Coverage: {from_ifc + inferred}/{total} ({coverage[ifc_file.name][2]:.1%})")
        print(f"  - from_ifc: {from_ifc}")
        print(f"  - inferred: {inferred}")
        print(f"  - unknown: {unknown}")
    
    except Exception as e:
        print(f"ERROR: {e}")

print(f"\n=== SUMMARY ===")
total_els = sum(c[1] for c in coverage.values())
classified = sum(c[0] for c in coverage.values())
print(f"Overall coverage: {classified}/{total_els} ({classified/total_els:.1%})")
EOF

python scripts/trace_environment_coverage.py
```

Run before and after to measure improvement.

---

## STEP 7: Add Tests

**File:** `tests/test_piping_producer.py`

Add test suite for environment inference:

```python
import pytest
from app.modules.module2_ifc_read.piping_producer import (
    infer_environment_from_system,
    PipingSystem,
)

class TestEnvironmentInferenceFromSystem:
    """Environment class should infer correctly from system type."""
    
    def test_potable_water_maps_to_t4(self):
        env = infer_environment_from_system(PipingSystem.DOMESTIC_COLD_WATER)
        assert env == "T4", "Potable water should be T4 (continuous wetting)"
    
    def test_hot_water_maps_to_t4(self):
        env = infer_environment_from_system(PipingSystem.DOMESTIC_HOT_WATER)
        assert env == "T4"
    
    def test_chilled_water_maps_to_t3(self):
        env = infer_environment_from_system(PipingSystem.CHILLED_WATER)
        assert env == "T3", "Chilled water should be T3 (condensation risk)"
    
    def test_fire_protection_maps_to_t3(self):
        env = infer_environment_from_system(PipingSystem.FIRE_PROTECTION)
        assert env == "T3", "Fire protection should be T3 (infrequent spray)"
    
    def test_pool_water_maps_to_t5(self):
        env = infer_environment_from_system(PipingSystem.POOL_WATER)
        assert env == "T5", "Pools should be T5 (chloride + continuous)"
    
    def test_excluded_systems_return_none(self):
        assert infer_environment_from_system(PipingSystem.RAINWATER) is None
        assert infer_environment_from_system(PipingSystem.DRAINAGE) is None
        assert infer_environment_from_system(PipingSystem.COMPRESSED_AIR) is None
    
    def test_none_input_returns_none(self):
        assert infer_environment_from_system(None) is None

class TestEnvironmentCoverage:
    """Environment should be tracked with provenance across real models."""
    
    def test_coverage_metric_on_real_model(self):
        """Measure coverage on a real model — should be > 30% after inference."""
        from pathlib import Path
        from app.modules.module2_ifc_read.piping_producer import extract_piping_network
        
        test_model = Path("test-models/models/plumb_ifc4.ifc")
        if not test_model.exists():
            pytest.skip("Test model not available")
        
        network = extract_piping_network(test_model)
        classified = sum(1 for e in network.elements if e.environment_class is not None)
        total = len(network.elements)
        coverage = classified / total if total else 0
        
        assert coverage >= 0.30, f"Coverage {coverage:.1%} below 30% target"
    
    def test_provenance_tracked(self):
        """Environment source and confidence should be recorded."""
        from app.modules.module2_ifc_read.piping_producer import extract_piping_network
        from pathlib import Path
        
        test_model = Path("test-models/models/plumb_ifc4.ifc")
        if not test_model.exists():
            pytest.skip("Test model not available")
        
        network = extract_piping_network(test_model)
        
        for element in network.elements:
            if element.environment_class:
                # Should have source tracked
                assert element.environment_source in ("from_ifc", "inferred", "unknown")
                assert element.environment_confidence in ("high", "provisional", "low", "unknown")
```

Run:

```bash
pytest tests/test_piping_producer.py::TestEnvironmentInferenceFromSystem -v
pytest tests/test_piping_producer.py::TestEnvironmentCoverage -v
```

---

## STEP 8: End-to-End Validation

Once environment is wired, MM-001 should fire:

```bash
python -c "
from pathlib import Path
from app.modules.module2_ifc_read.piping_producer import extract_piping_network
from app.modules.module6_compliance.mm_corrosion_engine import run_material_media_check

model = Path('test-models/models/plumb_ifc4.ifc')
network = extract_piping_network(model)

findings = run_material_media_check(network.elements)

print(f'Elements: {len(network.elements)}')
print(f'With material: {sum(1 for e in network.elements if e.material)}')
print(f'With environment: {sum(1 for e in network.elements if e.environment_class)}')
print(f'MM-001 findings: {len(findings)}')

if findings:
    for finding in findings[:3]:
        print(f'  - {finding}')
"
```

Expected: Findings > 0 (previously was 0).

---

## STEP 9: Lint & Test

```bash
cd D:\Zigurat Masters\bim-guard

# Lint the modified file
uvx ruff check app/modules/module2_ifc_read/piping_producer.py --fix

# Run all piping producer tests
pytest tests/test_piping_producer.py -v

# Run MM-001 tests
pytest tests/test_mm_corrosion_engine.py -v
```

---

## STEP 10: Commit

```bash
git add app/modules/module2_ifc_read/piping_producer.py tests/test_piping_producer.py scripts/trace_environment_coverage.py

git commit -m "Feat: Environment classification inference via EN ISO 15329 mapping

- Infer wetting class (T0-T5) from piping system type
- Add provenance tracking: from_ifc vs. inferred vs. unknown
- Add confidence levels: high/provisional/unknown
- Map 6 key systems (potable, chilled, hot, fire, pool, process)
- Explicitly exclude non-wetting systems (drainage, air, vacuum)
- Add 9 unit tests + coverage validation on real models
- Diagnostic logging at INFO (summary) and DEBUG (per-element)
- Coverage: 1.9% → 33.9% on real MEP models
- MM-001 now fires on properly classified elements"
```

---

## Verification Checklist

- [ ] `infer_environment_from_system()` added and tested
- [ ] Environment provenance tracked (source + confidence)
- [ ] Mapping covers at least 6 piping system types
- [ ] Explicitly excluded systems return None
- [ ] Diagnostic logging added (summary + detail)
- [ ] `trace_environment_coverage.py` runs and shows coverage improvement
- [ ] Coverage improved from baseline to 30%+ on at least one real model
- [ ] Unit tests pass (9+ tests)
- [ ] End-to-end: MM-001 produces findings (not 0) on a classified model
- [ ] `pytest tests/` passes (all relevant tests)
- [ ] ruff clean

---

## When Done

Report back with:
1. Coverage % before and after (e.g., "1.9% → 33.9%")
2. MM-001 finding count on a test model (should be > 0)
3. pytest output (test count before/after, all passing)
4. Commit hash

Then all three sessions complete:
- Session 1: Results panel rendering fixed
- Session 2: Demo block generators use fixed GUID helpers
- Session 3: Environment classification enables MM-001 to fire
- **Tool is submission-ready with all gates working.**
