# BIMGUARD AI — ISO 19650 Naming Configuration Implementation
## Corrected Roadmap (FMP Deadline: 27 September 2026)

---

## Overview

**What this adds:** Step 3 of the project wizard for ISO 19650 naming convention configuration.

**Standard Structure:** `PROJ-ORG-PH-LV-TYP-RL-CL-NUM-SUIT-REV.ext`

**Real-world context:** ISO 19650 itself does not mandate a specific naming format. The structure above is a widely-adopted industry interpretation (BIMicon guidelines, UK practice, CDE 19650 Cloud standard). Without automatic validation in the CDE, naming compliance drops to ~40% under deadline pressure. This tool adds validation + enforcement.

**Preset Conventions:** 5 presets covering ISO 19650-1 (standard), ISO 19650-2 (with date), simple, descriptive, and Uniclass 2015.

---

## Files Provided

All files are ready to copy-paste into Claude Code sessions and land on disk at the correct locations.

### **Session 1: Database + Backend (Windows, Desktop/VS Code Claude Code)**

| File | Location | Action |
|------|----------|--------|
| `20260831005000_add_iso19650_naming_config.sql` | Supabase SQL Editor | Copy & run (slot after 20260830004000) |
| `app_api_naming_config.py` | `app/api/naming_config.py` | Create new file, paste content |

### **Session 2: Frontend Part 1 (Windows, VS Code Claude Code)**

| File | Location | Action |
|------|----------|--------|
| `NamingConfigStep.svelte` | `frontend/src/routes/components/NamingConfigStep.svelte` | Create, paste |
| `ProjectMetadataSection.svelte` | `frontend/src/routes/components/naming-config/ProjectMetadataSection.svelte` | Create, paste |

### **Session 3: Frontend Part 2 (Windows, VS Code Claude Code)**

See separate prompt: `CLAUDE_CODE_SESSION_FRONTEND.md` — contains 4 more components.

### **Session 4: Integration (Windows, VS Code Claude Code)**

Update `frontend/src/routes/components/ProjectWizardModal.svelte` to include new step.

---

## Implementation Steps

### **Session 1: Database + Backend (10–15 min)**

**Step 1.1: Apply Supabase migration**

```
1. Open Supabase Dashboard → SQL Editor
2. Create new query
3. Copy content of 20260831005000_add_iso19650_naming_config.sql
4. Click "Run" (top right)
5. Verify success: "Query returned 0 rows"
6. Check table exists: SELECT * FROM project_naming_config LIMIT 1;
   Should return empty result (table exists, no rows yet)
```

**Step 1.2: Add API endpoints**

```
1. In Claude Code, open app/api/__init__.py
2. Look for line 46–52 (router registrations):
   
   from app.api import (
       projects, analysis, ...
   )
   app.include_router(projects.router)
   app.include_router(analysis.router)
   ...

3. Add new import:
   from app.api import naming_config
   
4. Add router registration:
   app.include_router(naming_config.router)

5. Create new file: app/api/naming_config.py
6. Paste content of app_api_naming_config.py (exactly)
7. Save all files
```

**Step 1.3: Restart backend & test**

```powershell
# Kill existing uvicorn (if running)
Get-Process | Where-Object { $_.ProcessName -like "*python*" } | Stop-Process -Force

# Restart
cd "D:\Zigurat Masters\bim-guard"
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# In PowerShell, wait for: "Uvicorn running on http://0.0.0.0:8000"
```

**Step 1.4: Validate endpoints**

```powershell
# Test preset listing (should return 5 presets)
curl http://localhost:8000/api/naming-config/presets

# Test preview generation
curl -X POST "http://localhost:8000/api/naming-config/preview?project_code=A7000&originator_code=BIM&phase_code=SD&level_code=01&type_code=DR&role_code=A&class_code=A01&number=0001&suitability=S1&revision=Rev01&convention=iso19650-1"

# Should return JSON with preview: "A7000-BIM-SD-01-DR-A-A01-0001-S1-Rev01"
```

**Expected output (first test):**
```json
{
  "iso19650-1": {
    "name": "ISO 19650-1:2018",
    "description": "Standard ISO naming convention (no date)",
    "template": "{project}-{originator}-{phase}-{level}-{type}-{role}-{class}-{number}-{suitability}-{revision}",
    "example": "A7000-BIM-SD-01-DR-A-A01-0001-S1-Rev01",
    "tokens": { ... }
  },
  ...
}
```

✅ **Session 1 Complete:** Backend is running, endpoints return 200 OK.

---

### **Session 2: Frontend Part 1 (10–15 min)**

**Step 2.1: Create directory structure**

```powershell
mkdir frontend\src\routes\components\naming-config -Force
```

**Step 2.2: Create parent component**

```
1. Create file: frontend/src/routes/components/NamingConfigStep.svelte
2. Paste content from NamingConfigStep.svelte (in this session's files)
3. Save
```

**Step 2.3: Create first section component**

```
1. Create file: frontend/src/routes/components/naming-config/ProjectMetadataSection.svelte
2. Paste content from ProjectMetadataSection.svelte
3. Save
```

**Step 2.4: Build & validate**

```powershell
cd frontend
npm run build

# Should output:
# ✓ built in XXXms
#
# If errors: read carefully — likely missing import or Svelte syntax issue
```

✅ **Session 2 Complete:** Parent + first section component built.

---

### **Session 3: Frontend Part 2 (15–20 min)**

**Step 3.1: Remaining section components**

Copy the following prompt into a new Claude Code session:

```
CLAUDE_CODE_SESSION_FRONTEND.md

This prompt contains 4 more Svelte components:
- DisciplineCodesSection.svelte (Section 2: Role codes)
- VolumeSystemCodesSection.svelte (Section 3: Type codes)
- LevelLocationCodesSection.svelte (Section 4: Level codes)
- NamingConventionSection.svelte (Section 5: Presets + preview)

Follow inline instructions to create files in:
  frontend/src/routes/components/naming-config/[ComponentName].svelte

Then run: cd frontend && npm run build
```

**Step 3.2: Build all together**

```powershell
cd frontend
npm run build

# Should complete without errors
# All 6 component files now exist
```

✅ **Session 3 Complete:** All frontend components built.

---

### **Session 4: Wizard Integration (10 min)**

**Step 4.1: Update ProjectWizardModal.svelte**

```svelte
// At top of file, add import:
import NamingConfigStep from './NamingConfigStep.svelte';

// Find the steps array definition (around line 30–40)
// Update it to:

const steps = [
  { id: 1, label: 'Jurisdiction', component: JurisdictionStep },
  { id: 2, label: 'IFC Files', component: IFCUploadStep },
  { id: 3, label: 'Naming Config', component: NamingConfigStep },  // NEW STEP
  { id: 4, label: 'Building Code', component: BuildingCodeStep },  // MOVED (was 3)
  { id: 5, label: 'Confirmation', component: ConfirmationStep }     // MOVED (was 4)
];

// In the render section, find the step dispatch logic
// Add case for step 3:

{:else if currentStep.id === 3}
  <NamingConfigStep
    projectId={projectId}
    onSave={(config) => {
      namingConfig = config;
      nextStep();
    }}
  />
```

**Step 4.2: Build & test wizard flow**

```powershell
cd frontend
npm run build

# Start backend (if not running):
# cd "D:\Zigurat Masters\bim-guard"
# uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Navigate to http://localhost:5173 (Svelte dev server)
# or wherever your frontend runs
```

**Step 4.3: Manual test**

```
1. Click "New Project" in wizard
2. Step 1 (Jurisdiction): Select a jurisdiction, click Next
3. Step 2 (IFC Files): Upload or skip, click Next
4. Step 3 (Naming Config): ← NEW STEP
   - Check all 6 tabs appear (Metadata, Disciplines, Volumes, Levels, CDE Status, Convention)
   - Fill in Project Code: "A7000"
   - Fill in Originator Code: "BIM"
   - Click tab "Convention" → verify 5 presets listed
   - Click "Save Configuration"
5. Step 4 (Building Code): Should advance here
6. Step 5 (Confirmation): Should appear
7. Confirm: Project created with naming config in Supabase
```

✅ **Session 4 Complete:** Wizard now has 5 steps, naming configuration is functional end-to-end.

---

## Data Flow Diagram

```
User Input (Step 3)
      ↓
NamingConfigStep.svelte
      ↓
[6 section tabs]
  - Project Code, Originator, Phase
  - Level codes (library)
  - Type codes (library)
  - Role/Discipline codes (library)
  - CDE Status (read-only reference)
  - Naming Convention (preset selector + preview)
      ↓
POST /api/naming-config/projects/{id}
      ↓
Supabase: project_naming_config table
      ↓
Config stored + persisted
      ↓
Next: Step 4 (Building Code)
```

---

## Validation & Error Handling

### **Common Issues**

| Issue | Cause | Fix |
|-------|-------|-----|
| `404 Not Found` on `/api/naming-config/presets` | Router not imported in `app/api/__init__.py` | Check Step 1.2, verify import & registration |
| `no such table: project_naming_config` | Migration not applied | Run SQL in Supabase (Step 1.1) |
| Components not rendering | Missing import in NamingConfigStep | Check all 5 child imports exist |
| Naming preview returns empty | Preview endpoint not responding | Verify backend running on port 8000 |
| Wizard doesn't advance past Step 3 | Navigation logic error | Check `onSave` callback in ProjectWizardModal |

### **Testing Checklist**

- [ ] Supabase migration applied (table exists, RLS enabled)
- [ ] Backend routes respond at `/api/naming-config/*`
- [ ] Wizard Step 3 renders with all 6 tabs
- [ ] Project Metadata tab accepts input
- [ ] Naming Convention tab shows 5 presets
- [ ] Live preview updates when preset changes
- [ ] "Save Configuration" button submits to backend
- [ ] Configuration persists after page reload (GET endpoint works)
- [ ] Wizard navigates: Step 1 → 2 → 3 → 4 → 5
- [ ] No console errors in browser DevTools

---

## Post-FMP Integration Points

Once the naming configuration is saved, the following can reference it:

1. **BCF Export** — use `active_convention` + tokens to generate ISO 19650 filenames
2. **File Validator** — call `GET /api/naming-config/validate/{filename}` on upload
3. **CSV Export** — include naming config metadata in project reports
4. **Audit Trail** — log changes to naming config (who, when, what changed)

---

## Real-World Context (Why This Matters)

<cite index="3-1">ISO 19650 naming compliance is a prerequisite for effective BIM collaboration, but it is complex and error-prone. A major barrier to adoption is the steep learning curve and financial investment in correct naming implementation.</cite>

<cite index="6-1">Testing with automated naming systems shows over 500% increased work efficiency and improved collaboration when naming validation is enforced.</cite>

<cite index="15-1">Without automatic validation in a CDE, naming compliance drops to ~40% under deadline pressure. With validation, it jumps to 100% in less than 2 weeks.</cite>

**BIMGUARD AI's contribution:** The naming configuration step provides both human-readable naming guidance (5 presets) and machine-enforceable validation (regex patterns available for CDE integration post-FMP).

---

## Files Checklist

Before FMP submission (27 Sep 2026):

- [ ] `20260831005000_add_iso19650_naming_config.sql` applied in Supabase
- [ ] `app_api_naming_config.py` created at `app/api/naming_config.py`
- [ ] `app/api/__init__.py` updated with naming_config import + router
- [ ] All 6 Svelte components created in `frontend/src/routes/components/naming-config/`
- [ ] `ProjectWizardModal.svelte` updated with new step order (5 total)
- [ ] Frontend builds: `npm run build` completes without errors
- [ ] Wizard flow tested: all 5 steps work end-to-end
- [ ] Naming config persists in Supabase after creation
- [ ] No browser console errors

---

## Quick Reference: Tokens & Codes

| Field | Token | Example | Length | Notes |
|-------|-------|---------|--------|-------|
| Project | `{project}` | A7000 | 2–8 chars | Must be unique per project |
| Originator | `{originator}` | BIM | 2–8 chars | Usually firm initials |
| Phase | `{phase}` | SD | 2–4 chars | SD=Scheme, DD=Design Dev, CD=Contract |
| Level | `{level}` | 01, GF, RF | 2–3 chars | GF=Ground, RF=Roof, ZZ=all levels |
| Type | `{type}` | DR, M3, RI | 2–3 chars | DR=Drawing, M3=3D Model, RI=RFI |
| Role | `{role}` | A, E, H, S | 1–2 chars | A=Arch, E=Elec, H=HVAC, S=Struct |
| Class | `{class}` | A01, E02 | 3–4 chars | Discipline-specific classification |
| Number | `{number}` | 0001 | 4 digits | Sequential, zero-padded |
| Suitability | `{suitability}` | S1, A | 1–3 chars | CDE status (S0, S1, S2, S3, A, B, S7) |
| Revision | `{revision}` | Rev01 | 3–6 chars | Rev01, PV1, C01, etc. |

Example output: **A7000-BIM-SD-01-DR-A-A01-0001-S1-Rev01**

---

## Questions?

Refer to inline code comments in each Svelte component and the FastAPI endpoints. Test incrementally after each session — don't wait until all 4 sessions are complete.

---

**Ready to begin Session 1? Start with Step 1.1: applying the Supabase migration.**
