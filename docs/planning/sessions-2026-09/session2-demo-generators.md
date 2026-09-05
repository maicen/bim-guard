# TASK: Update Demo Block Generators — Use Fixed GUID Helpers

## Context
Three corrosion engines (GC-001, CC-001, MC-001) each have `__main__` blocks that generate BCF test archives for standalone demo/validation. These were written before the GUID fixes in `f446d6b` and still emit the old structural violations:

- `Component/@IfcGuid` as random UUIDs or labels (`COMP-001`)
- `Topic/@Guid` as finding IDs like `BGR-0001` (not hyphenated UUIDs)
- Archives fail XSD validation

**Goal:** Update all three generators to use the new `bcf_topic_guid()` and `is_ifc_guid()` helpers, ensuring 38 test archives validate cleanly.

---

## STEP 1: Locate the Three Generators

```bash
cd D:\Zigurat Masters\bim-guard

find . -name "*.py" -type f | xargs grep -l "if __name__.*==.*__main__" | grep -E "corrosion|engine"
```

You should find (approximately):
- `app/modules/module6_compliance/gc_corrosion_engine.py`
- `app/modules/module6_compliance/cc_corrosion_engine.py`
- `app/modules/module6_compliance/mc_corrosion_engine.py`

Verify each has a `__main__` block:

```bash
grep -n "if __name__.*==.*__main__" app/modules/module6_compliance/*engine.py
```

---

## STEP 2: Inspect One Generator (GC-001)

**File:** `app/modules/module6_compliance/gc_corrosion_engine.py`

Find the `__main__` block (should be at end of file):

```bash
tail -100 app/modules/module6_compliance/gc_corrosion_engine.py
```

You should see a section like:

```python
if __name__ == "__main__":
    # Load test IFC
    ifc_path = "path/to/test.ifc"
    ifc_file = ifcopenshell.open(ifc_path)
    
    # Run analysis, generate BCF
    issues = run_corrosion_check(ifc_file)
    bcf_issues = [create_bcf_issue(issue) for issue in issues]
    
    # Write BCF archive
    write_bcf_archive(bcf_issues, "output.bcf")
```

---

## STEP 3: Identify Old GUID Patterns

Search for GUID creation in each `__main__` block:

```bash
grep -B2 -A2 "guid\|Guid\|GUID" app/modules/module6_compliance/gc_corrosion_engine.py | tail -40
```

You should see patterns like:

```python
# OLD (wrong):
issue['guid'] = str(uuid.uuid4())  # Random UUID
issue['component_guid'] = f"COMP-{i:03d}"  # Label, not GUID
topic['Guid'] = f"BGR-{finding_id}"  # Finding ID as string
```

Note all the places where GUIDs are generated/assigned.

---

## STEP 4: Import the Fixed Helpers

At the top of each `__main__` block (or import section), add:

```python
from app.modules.phase_6.bcf_generator import bcf_topic_guid, is_ifc_guid
```

Verify this import path exists:

```bash
grep -n "def bcf_topic_guid\|def is_ifc_guid" app/modules/phase_6/bcf_generator.py
```

Should return two function definitions.

---

## STEP 5: Understand the Helpers

**From** `app/modules/phase_6/bcf_generator.py`:

```python
def bcf_topic_guid(raw_id: str | None) -> str:
    """
    Convert any ID string to a valid BCF Topic GUID.
    - If raw_id is a real UUID: return verbatim
    - Otherwise: create deterministic UUID5 from raw_id, preserve in comment
    """
    # Implementation details in bcf21-guid-typing-validation.md

def is_ifc_guid(value: str | None) -> bool:
    """
    True if value is a valid 22-char IFC GlobalId (uppercase + digits).
    False for UUIDs, random strings, labels.
    Used to gate IfcProject and IfcGuid fields in BCF.
    """
```

**Usage:**

```python
# Topic GUID (always valid UUID)
topic_guid = bcf_topic_guid("BGR-0001")  # → UUID5 deterministic, comment='BGR-0001'

# IfcGuid (only if real IFC GlobalId)
if is_ifc_guid(component_guid):
    markup['Component']['IfcGuid'] = component_guid
else:
    # Omit IfcGuid, store raw in AuthoringToolId instead
    markup['Component']['AuthoringToolId'] = component_guid
```

---

## STEP 6: Fix GC-001 Generator

**File:** `app/modules/module6_compliance/gc_corrosion_engine.py`

In the `__main__` block, find all GUID assignments and replace:

### Before:

```python
for i, issue in enumerate(issues):
    issue['guid'] = str(uuid.uuid4())  # Random
    issue['component_guid'] = f"COMP-{i:03d}"  # Label
```

### After:

```python
for i, issue in enumerate(issues):
    # Topic GUID: create deterministic UUID from issue ID
    issue['guid'] = bcf_topic_guid(issue.get('finding_id', f'GC-{i:03d}'))
    
    # Component GUID: keep IFC GlobalId if valid, otherwise omit
    component_id = issue.get('component_guid', f"COMP-{i:03d}")
    if is_ifc_guid(component_id):
        issue['component_guid'] = component_id  # Store as-is
    else:
        issue['component_guid'] = None  # Will be handled at BCF write time
        issue['component_authoring_id'] = component_id  # Fallback
```

Then at BCF write time (in the archive creation code), use this pattern:

```python
# When writing to BCF markup:
if component['component_guid'] and is_ifc_guid(component['component_guid']):
    markup['Component']['IfcGuid'] = component['component_guid']
elif component.get('component_authoring_id'):
    markup['Component']['AuthoringToolId'] = component['component_authoring_id']
```

---

## STEP 7: Repeat for CC-001 and MC-001

Apply the same pattern to:
- `app/modules/module6_compliance/cc_corrosion_engine.py`
- `app/modules/module6_compliance/mc_corrosion_engine.py`

Each `__main__` block should:
1. Import the helpers
2. Replace random UUID generation with `bcf_topic_guid()`
3. Validate IfcGuid with `is_ifc_guid()` before assigning

---

## STEP 8: Run Demo Generators

Once all three are updated, run each to regenerate the test archives:

```bash
# GC-001
python -m app.modules.module6_compliance.gc_corrosion_engine

# CC-001
python -m app.modules.module6_compliance.cc_corrosion_engine

# MC-001
python -m app.modules.module6_compliance.mc_corrosion_engine
```

Each should generate a `.bcf` file (name depends on the __main__ implementation).

Verify files are created:

```bash
ls -lh *.bcf
```

---

## STEP 9: Validate Archives Against XSD

```bash
# Use the validation script from Session 2
python docs/validation/bcf21-guid-typing-validation.py --file output.bcf --verbose
```

Or manually with `xmlschema`:

```bash
python -c "
import xmlschema
from zipfile import ZipFile

with ZipFile('output.bcf', 'r') as bcf:
    markup_xml = bcf.read('markup.bcf').decode('utf-8')

schema = xmlschema.XMLSchema('vendor/bcf/bcf-2.1.xsd')
if schema.is_valid(markup_xml):
    print('✓ Valid')
else:
    print('✗ Invalid')
    for error in schema.iter_errors(markup_xml):
        print(f'  {error}')
"
```

---

## STEP 10: Regenerate All 38 Test Archives

If the three generators work, regenerate the full suite:

```bash
# Create a script to batch-run all three
cat > scripts/regenerate_demo_bcf.py << 'EOF'
#!/usr/bin/env python
"""Regenerate all demo BCF archives from engine __main__ blocks."""

import subprocess
import sys
from pathlib import Path

engines = [
    "app.modules.module6_compliance.gc_corrosion_engine",
    "app.modules.module6_compliance.cc_corrosion_engine",
    "app.modules.module6_compliance.mc_corrosion_engine",
]

output_dir = Path("data/validation_bcf")
output_dir.mkdir(parents=True, exist_ok=True)

for engine in engines:
    print(f"Running {engine}...")
    result = subprocess.run([sys.executable, "-m", engine], cwd=output_dir)
    if result.returncode != 0:
        print(f"ERROR: {engine} failed")
        sys.exit(1)
    print(f"✓ {engine} done")

print(f"\n✓ All archives regenerated in {output_dir}")
EOF

python scripts/regenerate_demo_bcf.py
```

---

## STEP 11: Batch Validate

```bash
python -c "
import xmlschema
from zipfile import ZipFile
from pathlib import Path

schema = xmlschema.XMLSchema('vendor/bcf/bcf-2.1.xsd')
output_dir = Path('data/validation_bcf')

valid = 0
invalid = 0

for bcf_file in output_dir.glob('*.bcf'):
    try:
        with ZipFile(bcf_file, 'r') as archive:
            markup_xml = archive.read('markup.bcf').decode('utf-8')
        
        if schema.is_valid(markup_xml):
            print(f'✓ {bcf_file.name}')
            valid += 1
        else:
            print(f'✗ {bcf_file.name}')
            invalid += 1
            for error in list(schema.iter_errors(markup_xml))[:1]:  # First error only
                print(f'    {error.reason}')
    except Exception as e:
        print(f'ERROR {bcf_file.name}: {e}')
        invalid += 1

print(f'\nResult: {valid} valid, {invalid} invalid')
"
```

---

## STEP 12: Commit

```bash
git add app/modules/module6_compliance/ scripts/regenerate_demo_bcf.py data/validation_bcf/
git commit -m "Fix: Demo block generators use bcf_topic_guid & is_ifc_guid helpers

- GC-001, CC-001, MC-001 __main__ blocks now use fixed GUID handlers
- Topic GUIDs created via bcf_topic_guid (deterministic UUID5)
- Component IfcGuid validated with is_ifc_guid before writing
- All 38 test archives regenerated and validate against XSD
- Batch validation script added for future regeneration"
```

---

## Verification Checklist

- [ ] All three engine files updated (GC/CC/MC)
- [ ] Helpers imported correctly
- [ ] Each generator runs without error
- [ ] Output BCF files created in expected location
- [ ] All 38 archives validate against buildingSMART XSD (xmlschema + lxml)
- [ ] No GUID type errors in validation output
- [ ] Batch regeneration script works
- [ ] Commit includes only the engine fixes + archives (not unrelated changes)

---

## When Done

Report back with:
1. Validation results (X/38 archives valid, before/after counts)
2. Sample validation output (first 3 archives' validation status)
3. Commit hash
4. Any errors in generator execution

Then Session 3 moves to environment classification inference.
