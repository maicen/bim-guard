# BIMGUARD AI — Project Continuity Prompt (Updated September 2026)
## Copy and paste this entire document into a new chat to continue the project

---

## Project Status Summary

**BIMGUARD AI** is an OpenBIM corrosion compliance checker for MEP (Mechanical, Electrical, Plumbing) building services. The Masters FMP (Final Masters Project, Module 10) submission deadline is **27 September 2026** (24 days away).

**Current Status: TOOL COMPLETE FOR SUBMISSION**

All five compliance engines (GC-001, CC-001, MC-001, MM-001, XM-001) are implemented, tested, and production-ready. Three critical parallel development sessions (Sessions 1-3) were just completed:

- **Session 1 (Results Panel):** ✓ COMPLETE — Bug was already fixed in prior merge (`e83b3ca`). Results render correctly in browser.
- **Session 2 (BCF Generators):** ✓ COMPLETE — All 138 BCF test archives valid against XSD. Commit `c6a4960` + `e5477ea`.
- **Session 3 (MM-001 Three Gates):** ✓ COMPLETE — All three gates (material, environment, temperature) now open. MM-001 produces 13,069 real findings on real MEP models. Commits: `344772c` (environment), `1285570` (temperature).

**Tool is ready to demo and submit.** Remaining work is documentation, thesis compilation, and presentation.

---

## Critical Sessions 1-3 Findings

### Session 1: Results Panel Rendering Bug

**Premise in original brief:** Results panel never renders; data arrives but DOM unchanged.

**Actual finding:** Bug was already fixed in commit `e83b3ca` (frontend modernization merge). The issue was Svelte 5 runes: plain `let` declarations are not reactive in runes mode. Current code uses `$state()` correctly.

**Verification:** Tested on two models:
- Hospital MEP scenario (322): 12 findings render, stat cards visible, MM-001 findings show
- Clinic Plumbing (119): 22,827 findings render, full pagination, 4-second warm-cache render

**Action taken:** None (already fixed). Verifying existing code is the right approach when briefs have stale assumptions.

### Session 2: BCF Generator GUID Violations

**Premise in original brief:** Six structural violations in `bcf_generator.py`.

**Actual finding:** All six were already fixed in commit `f446d6b`. However, three corrosion engines (GC/CC/MC) had their own demo writers that hand-wrote XML with GUID typing violations:
- `Component/@IfcGuid` as random UUIDs or labels
- `Topic/@Guid` as finding IDs (not hyphenated UUIDs)

**Fix applied:** Updated all three engine writers to delegate to `generate_bcf()` helper, use fixed GUID handlers (`bcf_topic_guid()` and `is_ifc_guid()`). Added `related_component_guids` support for anode/cathode pairs.

**Result:** 
- Before: 11 violations per engine (GC/CC/MC)
- After: 0 violations per engine
- All 138 demo archives validate against buildingSMART XSD
- 139 tests pass
- Commits: `c6a4960` + `e5477ea`

**Key learning:** Always inspect actual code before implementing. The brief's premise was wrong (violations were in demos, not main generator).

### Session 3: MM-001 Three-Gate Implementation

**Premise:** MM-001 needed all three gates open (material, environment, temperature) to fire. All three were at 0% coverage.

**Gate 1 — Material (Sessions 1-2 work):**
- Coverage: 1.9% → 33.9%
- Sources: IFC metadata + system-type inference (PipingSystem enum)
- Provenance: `material_source` (from_ifc vs. inferred) + `material_confidence` (high/low)
- No fallback to carbon_steel (honest tri-state: None when unclassified)

**Gate 2 — Environment (Critical architectural correction discovered):**
- Coverage: 0% → 100%
- **Key finding:** EnvironmentClass in BIMGUARD models *atmospheric conditions* (T0-T5 per EN ISO 15329), NOT fluid wetting (potable/chilled/hot water).
- **Brief was wrong:** Brief suggested mapping "potable water → T4_MARINE", which would score ALL indoor hospital plumbing as T4 severity 1.00 → false positives at scale.
- **Decision made:** Use T1_indoor_damp (severity 0.20) as default for all MEP systems (honest signal; MEP models lack atmospheric metadata).
- Sources: IFC property (rare, high confidence) → spatial name inference (medium confidence, 0.8% of elements) → T1 default (low confidence, 99.5%)
- Prevents false positives, respects tri-state logic
- Commit: `344772c`

**Gate 3 — Temperature (Just completed):**
- Coverage: 0% → 32.1% (29,966 elements)
- Sources: IFC property (rare) → system-type inference (32.1% coverage)
- Design temperatures per industry standard (DHW 60°C, CHW 6°C, heating 82°C, pool 27°C, etc.)
- **Critical design point:** 60°C is load-bearing (zinc polarity reversal on galvanised steel). DHW correctly scores on the physically correct side of the band edge.
- Provenance: `temperature_source` + `temperature_confidence`
- Temperature term capped at 0.35 by `kinetics_guard` (inference can't invent findings on compatible materials)
- Commit: `1285570`

**MM-001 Result:**
- Before gates: 0 findings
- After all three gates: 13,069 findings
- 13,068 are galvanised steel in stagnant water (textbook zinc-depletion failure mode, not noise)
- Copper in potable water correctly produces 0 findings (compliant spec)
- Tests: 1,365 passing (was 1,302 before Session 3)

**XM-001 structural limitation discovered:**
- XM-001 (cross-material contamination) requires dissimilar materials at junctions
- System-type inference makes materials uniform within systems → no couples within systems
- XM-001 will only fire where:
  - Real material metadata exists (not inferred), OR
  - Cross-system material heterogeneity is detected
- This is architectural, not a bug
- Documented for post-FMP work

---

## Key Architectural Decisions (Do Not Reverse)

### 1. Tri-State Fail-Safe Logic
- Every decision: Pass / Fail / Undetermined
- Missing data returns `None`, never assumptions or defaults
- Exceptions: Environment (T1 default for MEP) and temperature inference (system-type mapping) — both justified by lack of design metadata in MEP discipline

### 2. Provenance Tracking on All Inference
- Every inferred value tagged with `_source` (from_ifc vs. inferred vs. default) and `_confidence` (high/medium/low)
- Enables users to distinguish facts from assumptions
- Prevents merged headlines from hiding uncertainty

### 3. No False Positives via System-Type Mapping
- Material inference: PipingSystem → CANONICAL_MATERIALS (safe, material names are stable)
- Environment inference: Deliberately NOT mapped "potable → marine" (would cause false positives)
- Temperature inference: System → design temperature (industry standard, verified safe)

### 4. OpenBIM Only
- IFC, BCF, IDS, ISO 19650 — no Revit API, no proprietary formats
- FastHTML backend (Python) + Svelte 5 frontend
- All compliance logic is White Box (traceable to published standards), never black-box AI for scoring

### 5. Module Restructuring (Sept 2026)
- Modules moved from `app/modules/module2_ifc_read/` to `app/modules/ifc_reader/`
- Comparators moved to `app/modules/comparator/`
- Engine files remain at `app/engines/bimguard_*_engine.py`
- Update import paths if continuing development

---

## Current Codebase State

### Repository
- Primary repo: `maicen/bim-guard` 
- Desktop: `D:\Zigurat Masters\bim-guard`
- Work laptop: `C:\dev\bim-guard`
- Remote: `origin/main` on GitHub (requires `markshanehaines-ZIG` auth in Git Bash)

### Recent Commits (Sessions 1-3)
- `1285570` — Gate 3 (temperature inference, system-type mapping, 13,069 findings)
- `344772c` — Gate 2 (environment T1 default + spatial inference, 100% coverage)
- `e5477ea` — BCF demo generators updated, README note
- `c6a4960` — BCF generator GUID fixes (all violations resolved)
- `4b98fd4` — MM/XM UI gating (prior session)
- `ca264e8` — Point-to-triangle geometry upgrade (prior, retired blind-spot test correctly)

### Test Status
- `uv run pytest tests/` → **1,365 passed, 2 skipped, 4 xfailed**
- No regressions introduced
- All Session 3 additions (42 new tests in test_piping_producer.py) passing

### Frontend Status
- Svelte 5, runes mode enabled
- `npm run build` succeeds in ~43 seconds
- Only warning: chunk-size advisory (informational)
- `svelte-check` reports 0 errors, 0 warnings (not 51 as earlier believed; that was tooling artifact)
- Results render correctly on browser at localhost:5173
- Warm-cache for 22,827-issue model: 4 seconds

### Backend Status
- FastAPI at port 8000
- Supabase database (postgres)
- Caching working correctly (verified by performance: cold ~7 min, warm ~4 sec)
- `cached` flag always reports `false` (known bug in `analysis_runner.py:411`, low priority)

### Known Limitations (Not Blocking)
1. **Cold-cache compute:** ~7 minutes for Clinic Plumbing model (server-side, not UI)
2. **Response size:** 19.3 MB for 22,827 issues (no server-side pagination yet)
3. **System classification:** 62,235 elements still have `system = unknown` (next performance lever)
4. **XM-001:** Returns 0 findings (architectural: needs cross-system material heterogeneity)
5. **Third gate for MM-001:** Operating temperature still missing on 67.9% of elements (acceptable; gates work with inference)

---

## What Still Needs to Be Done (24 Days to Submission)

### Critical (Submission-Blocking)
1. **Thesis compilation** — Chapters 1-11 exist as separate .docx files, need to be compiled into master document with:
   - Cover page (formal institutional format)
   - Abstract (not yet written)
   - Executive summary (not yet written)
   - Table of contents with proper numbering
   - Consistent formatting and headers/footers
   - Full bibliography

2. **FMP Presentation Deck** — Unified deck covering:
   - Problem statement (MEP corrosion compliance gap)
   - Solution architecture (five engines, OpenBIM, White Box)
   - Implementation (material/environment/temperature inference)
   - Results (13,069 findings on real models)
   - MM-001 demo walkthrough

### Important (Strengthens Submission)
3. **Demo walkthrough documentation** — How to:
   - Upload a test IFC file
   - Run analysis (Material, Environment, Temperature gates explained)
   - Interpret findings (confidence levels, provenance tracking)
   - Export BCF for Navisworks/Revit
   - Screenshot showing MM-001 findings in results table

4. **Validation report** — Document that proves:
   - All five engines work on real MEP models
   - MM-001 gates are closed (material 33.9%, environment 100%, temperature 32.1%)
   - BCF archives are schema-valid
   - No false positives on indoor pipework
   - Results match expected failure modes (galvanised in stagnant water)

5. **Material coverage analysis** — Explain:
   - Why material is 33.9% (not 0%)
   - Where coverage comes from (IFC vs. inferred)
   - Why inference is safe (PipingSystem enum stable)
   - What "unknown" means (honest signal, not a bug)

### Nice-to-Have (Quality Polish)
6. **Client Q&A scripts** — 20 questions + answers previously identified
7. **NotebookLM setup** — Test the LLM-based question generation with full sources
8. **Navisworks/Revit import test** — Verify BCF opens in industry tools (if access available)

---

## Important Notes for Continuation

### Measurement Before Change
- Always inspect actual code first; briefs have stale assumptions
- Measure baseline coverage/behavior before implementing changes
- Document what was expected vs. what was found (like Gate 2's environment axis mismatch)

### Provenance Is Non-Negotiable
- Every inferred value has `_source` and `_confidence` fields
- This is not optional; it's how MM-001 avoids false positives
- Merged headline numbers hide uncertainty; always track separately

### EnvironmentClass Trap (Won't Happen Again)
- EnvironmentClass = atmosphere around pipe (rooftop/coastal/indoor), NOT fluid wetting
- Fluid wetting (potable/chilled/hot) is handled by separate `media_for_system()` axis
- Mapping system type → marine environment would cause false positives at scale
- T1_indoor_damp default is the correct choice for MEP discipline models

### System Classification Is The Next Lever
- 62,235 elements currently have `system = unknown`
- Fixing this would boost material + temperature gates from 33% → ~45–50%
- This is post-FMP work (not needed for submission)

### No Temp Fixes
- All code committed is production-ready
- No workarounds, no scaffolding
- If a fix isn't complete, document it as future work and move on

---

## Standards and Sources Used

| Standard | Application |
|----------|-------------|
| EN ISO 15329 | Environmental wetting classes (T0-T5) for stainless steel |
| ASTM G48 | Critical Crevice Corrosion Temperature (CCT) values |
| NASA-STD-6012 | Galvanic corrosion voltage thresholds |
| CIRIA C692 | Stainless steel in construction |
| IMOA Design Manual | PREN formula and material selection |
| ISO 19650 | BIM information management, property sets |
| buildingSMART BCF 2.1 | Issue tracking specification, XSD validation |

---

## File Structure (Key Paths)

```
D:\Zigurat Masters\bim-guard/
├── app/
│   ├── engines/
│   │   ├── bimguard_gc_corrosion_engine.py
│   │   ├── bimguard_cc_corrosion_engine.py
│   │   ├── bimguard_mc_corrosion_engine.py
│   │   ├── bimguard_mm_corrosion_engine.py
│   │   └── bimguard_xm_corrosion_engine.py
│   ├── modules/
│   │   ├── ifc_reader/
│   │   │   ├── piping_producer.py (material + environment + temperature inference)
│   │   │   ├── piping_schema.py (PipingElement dataclass)
│   │   │   └── geometry.py
│   │   ├── comparator/
│   │   │   └── (material/media compatibility matrices)
│   │   └── phase_6/
│   │       └── bcf_generator.py (fixed GUID helpers)
│   ├── services/
│   │   ├── compliance_orchestrator.py
│   │   ├── analysis_runner.py
│   │   └── analysis_cache.py
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── routes/
│   │   │   └── AnalyzeView.svelte (results render inline, $state() reactive)
│   │   └── lib/components/
│   │       └── (various UI components)
│   └── svelte.config.js (runes: true)
├── tests/
│   ├── test_piping_producer.py (163 tests, +42 new from Session 3)
│   ├── test_*_engine.py
│   └── test_engine_bcf_export.py
├── scripts/
│   ├── trace_material_coverage.py
│   ├── trace_environment_coverage.py
│   ├── trace_temperature_coverage.py
│   └── regenerate_demo_bcf.py
├── docs/
│   ├── validation/
│   │   ├── bcf21-guid-typing-validation.md (validation report)
│   │   └── data/
│   │       ├── material-coverage.json
│   │       ├── environment-coverage.json
│   │       └── temperature-coverage.json
│   ├── bcf_exports/ (gitignored, demo archives)
│   └── CLAUDE.md (dev guidelines, no AI attribution in commits)
└── test-models/
    └── models/ (21 real MEP IFC files for validation)
```

---

## How to Continue

### For Thesis Compilation
1. Open `BIMGUARD_AI_Thesis_Chapters.docx` and `BIMGUARD_Crevice_Thesis_Extension.docx`
2. Compile chapters 1-11 into single master document
3. Add cover page, abstract, executive summary
4. Use docx skill with proper heading styles, TOC generation
5. Ensure consistent formatting per institutional guidelines

### For FMP Presentation Deck
1. Create unified deck (consolidate existing two decks into one)
2. Focus on problem → solution → results → demo
3. Screenshot showing MM-001 findings (proof it's working)
4. Navy/blue professional palette (per prior design notes)

### For Continued Development (Post-FMP)
1. System classification fix (boost gates to 45–50% coverage)
2. XM-001 enablement (cross-system junction detection)
3. Cold-cache optimization (if time permits)
4. Navisworks/Revit import validation (if access available)

### To Run/Verify Current State
```bash
cd D:\Zigurat Masters\bim-guard

# Start backend
python main.py

# In another terminal, start frontend
cd frontend && npm run dev

# Run tests
uv run pytest tests/ -v

# Verify MM-001 fires
python -c "
from pathlib import Path
from app.modules.ifc_reader.piping_producer import extract_piping_network
from app.modules.module6_compliance.mm_corrosion_engine import run_material_media_check

model = Path('test-models/models/west_riverside_hospital_plumb_ifc4.ifc')
network = extract_piping_network(model)
findings = run_material_media_check(network.elements)
print(f'MM-001 findings: {len(findings)}')  # Should be > 0
"
```

---

## Important: Do Not Reverse These Decisions

1. **T1_indoor_damp default for environment** — This prevents false positives and is the correct choice for MEP models
2. **System-type inference for material + temperature** — Stable, PE-designed, safe
3. **No system-type inference for environment** — The brief was wrong; this would cause false positives
4. **Provenance tracking on all inference** — Non-negotiable for preventing false confidence
5. **OpenBIM only, no proprietary APIs** — This is the thesis's academic innovation

---

## Timeline: 24 Days to Submission (27 Sep 2026)

- **Days 1-3:** Thesis compilation (merge chapters, write abstract/summary)
- **Days 4-5:** FMP presentation deck (unified, demo-ready)
- **Days 6-10:** Validation documentation (prove all gates work, no false positives)
- **Days 11-20:** Final review, ruff/pytest sweep, demo walkthrough recording
- **Days 21-24:** Buffer for emergencies, final submission package assembly

---

## Questions for the Next Session

1. **Do you want to continue with thesis compilation?** (Yes → start with docx skill, master document setup)
2. **Should we focus on FMP presentation deck?** (Yes → what format/length is required by institution?)
3. **Any backend optimizations before submission?** (System classification fix? Navisworks testing?)
4. **Client Q&A scripts still needed?** (Yes → generate with documented framework)

**State your priority and I'll queue the next work.**
