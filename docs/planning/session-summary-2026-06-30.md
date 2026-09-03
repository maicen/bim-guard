# Session Summary — 2026-06-30

## What this session covered

Full diagnostic and improvement pass on BIM-Guard's IFC compliance pipeline,
plus design and implementation of a pyRevit direct-sync integration as an
alternative data source.

---

## Bugs Fixed

### 1. Missing `regex_rule_converter.py` (critical)
- **Problem:** `orchestrator.py` imports `RegexRuleConverter` when `USE_GPT4O = False`
  (the default), but the file did not exist — the entire free pipeline was broken.
- **Fix:** Created `app/modules/rule_builder/regex_rule_converter.py`
  with a `RegexRuleConverter` class that matches the same `extract_rules(chunk)`
  interface as the GPT-4o converter.
- **How it works:** Pattern-matches CODE prose phrasings ("not less than X mm",
  "between X and Y mm", "shall not…") on HIGH/MEDIUM confidence paragraphs only.
  Tags results `extraction_method: "regex"`, `confidence: 0.5`, `needs_review: True`.

### 2. Wrong IFC property names in seed rules (8 rules)
- **Problem:** Rules used custom property names that don't exist in standard
  buildingSMART Psets, causing permanent `MISSING_DATA` on every analysis.
- **Fix:** Updated `code_seed_rules.py` and migrated the `public.rules` table via
  `scripts/fix_property_names.py`.

| Old name | New name | Reason |
|---|---|---|
| `TreadDepth` | `TreadLength` | Pset_StairFlightCommon standard name |
| `HeadroomClearance` | `RequiredHeadroom` | Pset_StairFlightCommon standard name |
| `ClearWidth` | `OverallWidth` | IfcDoor direct attribute |
| `ClearOpeningHeight` | `OverallHeight` | IfcWindow direct attribute |
| `ClearOpeningWidth` | `OverallWidth` | IfcWindow direct attribute |
| `ClearOpeningArea` | `Area` | Qto_WindowBaseQuantities |
| `Slope` | `RequiredSlope` | Pset_RampCommon standard name |
| `MaxSlope` | `PitchAngle` | Pset_SlabCommon standard name |

### 3. Missing `.env` file — app wouldn't start
- **Problem:** No `.env` file → startup crash without Supabase credentials.
- **Fix:** Copied `example.env` → `.env` and configured Supabase credentials.

### 4. Compliance results UI — no per-element drill-down
- **Problem:** `MISSING_DATA` rows showed `0 / 0 / 167` but no way to see
  which specific elements were missing the property.
- **Fix:**
  - Added `missing_elements` list to `ComplianceComparator._result()` — tracks
    element name, storey, GUID for every element where `actual_value is None`.
  - Added two collapsibles to `app/routes/analyze.py`:
    - Red: "X failing element(s)" — shows element name, actual value, reason
    - Yellow: "X element(s) missing this property" — shows element name, storey, GUID

### 5. Compliance results UI — flat table, no grouping
- **Problem:** All rules rendered as one flat list — hard to scan across element types.
- **Fix:** Grouped results by IFC class in `_rule_compliance_card()`. Each group
  gets a section header showing human-readable name (e.g. "Stairs"), IFC class
  code, and a group-level status badge ("3 failed", "all pass", etc.).

---

## New Features Built

### 1. IFC Property Diagnostic Script
**File:** `scripts/inspect_ifc_properties.py`

Runs `IFCReader.extract_for_compliance()` against any IFC file and diffs
the results against rules in `public.rules`. Reports per target class:
- `[OK]` — property found (shows which Pset it came from)
- `[NEAR-MISS]` — property not found but a similarly named one exists (fuzzy match)
- `[MISSING]` — property genuinely absent
- `NO ELEMENTS` — IFC class not present in the file at all

```bash
uv run python scripts/inspect_ifc_properties.py path/to/model.ifc
uv run python scripts/inspect_ifc_properties.py path/to/model.ifc --target IfcWall
uv run python scripts/inspect_ifc_properties.py path/to/model.ifc --theme MEP
```

### 2. Property Name Migration Script
**File:** `scripts/fix_property_names.py`

One-time and re-runnable migration that renames `property_name` values in
`public.rules` to match standard IFC Pset names. Supports `--dry-run`.

```bash
uv run python scripts/fix_property_names.py --dry-run
uv run python scripts/fix_property_names.py
```

### 3. BIMGuard IFC4 Export Config for Revit
**File:** `data/BIMGuard_IFC4_Export.json`

Ready-to-import Revit IFC export setup. Load via Revit → File → Export → IFC →
Modify Setup → import icon.

Key settings vs default:
- `ExportInternalRevitPropertySets: true` — exports all Revit parameters
- `ExportMaterialPsets: true` — needed for corrosion rules
- `UseTypePropertiesInInstacePSets: true` — type properties flow to instances
- `Use2DRoomBoundaryForVolume: true` — correct room area for IfcSpace rules
- `StoreIFCGUID: true` — stable GUIDs across re-exports
- `UseVisibleRevitNameAsEntityName: true` — readable names in reports
- `SpaceBoundaries: 1` — first-level space boundaries

### 4. pyRevit Direct Sync Integration
**New files:**
- `app/services/revit_sync_service.py` — converts pyRevit JSON to Module 4 format
- `app/routes/revit_sync.py` — HTTP endpoints for receiving pyRevit data

**Endpoints:**
- `GET  /revit-sync` — landing page with pyRevit script template
- `POST /revit-sync` — receives data, runs compliance check, renders results
- `POST /revit-sync/api` — same but returns JSON (for script debugging)

**pyRevit POST format:**
```json
{
  "project_name": "My Building",
  "theme": "Architecture",
  "elements": [
    {
      "ifc_class": "IfcStairFlight",
      "name": "Stair 1",
      "guid": "abc-123",
      "storey": "Level 1",
      "properties": {
        "Width": 900.0,
        "RiserHeight": 175.0,
        "TreadLength": 280.0
      }
    }
  ]
}
```

IFC parsing path (Module 2) is completely untouched — both paths coexist.

### 5. IFC Property Mapping Reference
**File:** `docs/ifc-property-mapping.md`

Two comprehensive tables:
1. Rule `property_name` → Standard IFC Pset property → Revit export status → Fix
2. Standard Pset property → IFC class → Rule uses → Fix

---

## Key Decisions Made

### pyRevit over Speckle for Revit integration
- Speckle has uncertain pricing as of mid-2026
- pyRevit is free, open-source, Python-native — same language as BIM-Guard
- pyRevit gives full control over property names (no IFC translation layer)
- Speckle would be better for multi-user continuous sync — revisit if team grows

### IFC4 Design Transfer View over Reference View
- Reference View MVD deliberately strips property sets (lightweight viewing)
- Design Transfer View preserves full Psets/Quantities needed for compliance
- The "Unofficial" label just means it's not a ratified buildingSMART MVD —
  it works correctly with ifcopenshell

### Keep IFC path alongside pyRevit
- IFC is already built and working — no reason to remove it
- pyRevit is an additional input source, not a replacement
- Module 4 and 5 are shared by both paths

---

## Still Pending / Known Gaps

### Revit Shared Parameters needed for custom properties
These properties have no standard IFC equivalent — they will always return
`MISSING_DATA` from IFC exports until Shared Parameters are added in Revit
and mapped via a user-defined property sets `.txt` file:

| Property | IFC Class | Why custom |
|---|---|---|
| `Height` | IfcRailing | Not in Pset_RailingCommon |
| `HandrailHeight` | IfcRailing | Not in any standard Pset |
| `HeadroomClearance` | IfcSlab | Not in Pset_SlabCommon |
| `LimitingDistance` | IfcWall | Calculated, not exportable |
| `Width` | IfcStairFlight | Not in standard Pset |
| `Width` | IfcRamp | Not in Pset_RampCommon |
| `Width` | IfcSpace | Not in Pset_SpaceCommon |
| `FlightHeight` | IfcStairFlight | Not standard |
| `WinderTurnAngle` | IfcStairFlight | Not standard |

### IFC Graph visualization disabled
`app/routes/analyze.py:_build_ifc_graph_card()` returns a placeholder.
The PyVis graph (`app/modules/ifc_reader/ifc_graph.py`) is built and
working — re-enable once the analysis UI flow is stable.

### pyRevit extension not yet built
The pyRevit `.extension` folder structure and `script.py` need to be created
by the user in their local Revit environment. Template is at `GET /revit-sync`.

### NO_ELEMENTS for IfcDoor, IfcStairFlight, IfcWindow, IfcRailing
Tested on `Building-Architecture.ifc` — these four classes return no elements.
Root cause: Revit's category-to-IFC-class mapping. Fix via "Entities to Export"
button in Revit's Modify Setup dialog, or by checking the IFC Class Mapping
for those Revit categories.

---

## How to Run

```bash
# Start the web server
cd "c:\Users\Malak\bimguard 30june\bim-guard"
uv run uvicorn main:app --reload
# → http://localhost:8000

# Run IFC diagnostic on an uploaded file
uv run python scripts/inspect_ifc_properties.py data/cache/supabase-storage/uploads/ifc/YOUR_FILE.ifc

# Preview property name DB fixes
uv run python scripts/fix_property_names.py --dry-run
```
