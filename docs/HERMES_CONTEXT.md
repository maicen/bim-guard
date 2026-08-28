# HERMES_CONTEXT.md — Hermes Research Context for BIMGUARD AI Blue Halo Standards Research

**Last Updated:** 22 August 2026  
**Project:** BIMGUARD AI — Blue Halo Seismic Bracing Algorithm  
**Deadline:** 27 September 2026 (FMP submission)  
**Load this file at the start of every Hermes session.**

---

## PROJECT OVERVIEW

### BIMGUARD AI: Two-Track Compliance Platform
- **Track A:** Prescriptive building-code compliance (PDF extraction → LLM rules → scoring)
- **Track B:** Material degradation (five corrosion engines: GC-001, CC-001, MC-001, MM-001, XM-001)
- **Status:** Tracks A & B core complete; **Blue Halo (Track B spatial module) in development**

### Blue Halo Algorithm: Seismic Bracing Clearance Reservation
- **Problem:** Seismic bracing for MEP (pipes/ducts) requires spatial clearance. LOD 200/300 design stage conflicts are caught too late (80% rework).
- **Solution:** Automated algorithm to generate 3D Halo clearance volumes, detect clashes, output BCF 2.1 issues.
- **Innovation:** First open-source algorithm validated by BIMForum 2025 LOD Specification (Part I, non-graphical space reservations at LOD 300).
- **Scope:** 48–60 hours across 5 phases. Phase 1 (algorithm) is generic; Phase 2–3 populate jurisdiction-specific configs.

---

## YOUR TASK: STANDARDS RESEARCH & CONFIG GENERATION

### PRIMARY OBJECTIVE
Extract quantitative data from seismic bracing standards and generate **pluggable JSON configs** that the algorithm loads at runtime.

### RESEARCH PRIORITIES (In Order)

**Priority 1 (Must Have):**
- EN 1998-1:2004+A2:2011 (Eurocode 8: Design of Structures for Earthquake Resistance)
- DIN 4149:2005-04 (German seismic standard — regional applicability)

**Priority 2 (Should Have):**
- NFPA 13-2022 (Fire Sprinkler Systems, Section 18: Seismic Bracing) — international reference

**Priority 3 (Nice to Have):**
- BS 5950-1:2000 or BS 9997:2017 (UK)
- SIA 261:2020 (Switzerland)

**Optional (Only If Time):**
- ASCE 7-22 (US — for comparison/validation)

---

## DATA EXTRACTION TEMPLATE

For **each standard**, extract and return in this exact JSON format:

```json
{
  "standard_name": "EN 1998-1:2004+A2:2011",
  "jurisdiction": "Europe (EU)",
  "publication_year": 2004,
  "amendment_year": 2011,
  
  "key_sections": [
    {
      "section_number": "4.3.1",
      "title": "Non-structural elements",
      "relevance": "Defines restraint requirements for MEP systems",
      "direct_quote": "..."
    }
  ],
  
  "seismic_hazard_factor": {
    "symbol": "Ip or Wp",
    "meaning": "Importance Factor for piping systems",
    "typical_values": {
      "low_risk_building": 0.5,
      "standard_building": 0.75,
      "high_risk_building": 1.0,
      "hospital": 1.5
    },
    "source_section": "Section X.X"
  },
  
  "restraint_spacing": {
    "transverse_m": 30,
    "longitudinal_m": 60,
    "notes": "For circular pipes <50mm; larger pipes may allow wider spacing",
    "source_section": "Section X.X"
  },
  
  "clearance_buffers": {
    "from_structural_elements_mm": 50,
    "from_adjacent_systems_mm": 75,
    "hospital_additional_mm": 25,
    "seismic_zone_additional_mm": 25,
    "notes": "Clearance increases with Importance Factor",
    "source_section": "Section X.X"
  },
  
  "brace_types": {
    "angle_iron": {
      "fire_sprinkler_standard_sizes": ["L50x50x5", "L75x75x6", "L100x100x8"],
      "mechanical_standard_sizes": ["L50x50x5ga", "L75x75x6ga"],
      "spacing_transverse_m": 30,
      "spacing_longitudinal_m": 60
    },
    "cable": {
      "diameter_range_mm": [1.5, 9.5],
      "typical_diameter_mm": 3.2,
      "spacing_transverse_m": 40,
      "spacing_longitudinal_m": 80
    },
    "rod": {
      "diameter_range_mm": [9.5, 22],
      "typical_diameter_mm": 12.7,
      "spacing_transverse_m": 35,
      "spacing_longitudinal_m": 70
    }
  },
  
  "angle_constraints": {
    "min_degrees": 30,
    "ideal_degrees": 45,
    "max_degrees": 60,
    "tolerance_degrees": 15,
    "notes": "Measured from horizontal",
    "source_section": "Section X.X"
  },
  
  "pipe_duct_thresholds": {
    "pipe_diameter_threshold_mm": 50,
    "duct_cross_section_threshold_sqm": 0.56,
    "notes": "Pipes/ducts below threshold may not require bracing",
    "source_section": "Section X.X"
  },
  
  "building_importance_factors": {
    "office": 0.5,
    "residential": 0.5,
    "hospital": 1.5,
    "data_centre": 1.0,
    "industrial": 0.75,
    "laboratory": 1.0,
    "source_section": "Section X.X"
  },
  
  "data_gaps": [
    "No explicit clearance for maintenance access",
    "Tool access clearance not defined",
    "Brace-to-pipe contact area not codified",
    "Example: 'Rectangular duct weight threshold ambiguous (17 lb/ft vs. 20 lb/ft)'"
  ],
  
  "paywalled_sections": [
    "Section 4.3.1 — behind AAFM paywall; sourced from academic secondary reference: Smith et al. (2023)"
  ],
  
  "standards_full_citations": [
    "EN 1998-1:2004+A2:2011. Eurocode 8: Design of Structures for Earthquake Resistance – Part 1: General Rules, Seismic Actions and Rules for Buildings. European Committee for Standardization (CEN), Brussels, 2011."
  ]
}
```

---

## COMPARISON MATRIX OUTPUT

Return a markdown table comparing all researched standards:

```markdown
# Standards Comparison Matrix

| Parameter | EN 1998-1 | DIN 4149 | NFPA 13-2022 | Notes |
|-----------|-----------|----------|--------------|-------|
| Max transverse spacing | 30m | ? | 30ft (9.1m) | EU uses meters; US uses feet |
| Clearance from structure | 50mm | ? | 4in (102mm) | Values vary by importance factor |
| Brace angle range | 30–60° | ? | 30–60° | Consensus across standards |
| Hospital Importance Factor | 1.5 | ? | Special? | Hospitals require stricter limits |
| Pipe threshold for bracing | >50mm | ? | >2in (50mm) | Aligned across standards |
| Base importance factor | 0.75 | ? | Implicit | Standard building baseline |

## Conflict Resolution Needed
- **Issue:** EN 1998-1 uses metric (mm/m); NFPA 13 uses imperial (in./ft)
- **Resolution:** Convert to metric (mm/m) for uniform config files

## Consensus Rules (Acceptable Default)
- Angle range: 30–60° (all standards agree)
- Pipe threshold: >50mm (all standards align)
- Ideal angle: 45° (universally preferred)
```

---

## CASE STUDY RECOMMENDATION OUTPUT

Based on research, recommend:

```markdown
# Recommended Case Study Scenario

## Building Type
**Hospital** — justification:
- Highest Importance Factor (Ip = 1.5 per EN 1998-1)
- Most stringent clearance requirements
- Most academically interesting (demonstrates why dual-track is necessary)

## MEP Systems
- Chilled water (50mm copper pipes, multiple runs)
- Hot water (38mm copper, condensate return)
- Fire sprinkler (DN32 steel, NFPA 13 applies globally)
- Electrical conduit (25mm PVC/steel)

## Seismic Zone
- **Zone 2** (moderate seismic risk) — typical for European locations
- Cs (seismic hazard factor) = 0.35
- Demonstrates meaningful bracing requirement without extreme conservatism

## MEP System Interactions
- Chilled water crosses fire sprinkler riser (clash potential)
- Conduit runs parallel to hot water (clearance interaction)
- Multiple brace types required (angle iron, cable, rod) — shows comparison value

## Expected Algorithm Output
- 3 brace type options (angle, cable, rod)
- Halo volumes for each
- Clash detection report
- Comparison table (size, spacing, cost estimate if available)
- BCF 2.1 file with spatial issues
```

---

## CONFIG TEMPLATE OUTPUT FORMAT

Generate a **populated config file** for your primary standard:

**File:** `en_1998_1_din_4149.json`

```json
{
  "metadata": {
    "jurisdiction": "EN 1998-1:2004+A2:2011 + DIN 4149:2005",
    "region": "Europe",
    "created_by": "Hermes Standards Research",
    "created_date": "2026-08-22",
    "standards_cited": [
      "EN 1998-1:2004+A2:2011",
      "DIN 4149:2005-04"
    ],
    "data_gaps": [
      "No explicit maintenance clearance rule",
      "Tool access clearance deferred to Engineer of Record"
    ],
    "paywalled_sections": [
      "EN 1998-1 Section 4.3.1 (sourced from academic secondary)"
    ]
  },
  
  "seismic_parameters": {
    "hazard_factor_default": 0.35,
    "importance_factors": {
      "office": 0.5,
      "residential": 0.5,
      "hospital": 1.5,
      "data_centre": 1.0,
      "laboratory": 1.0,
      "industrial": 0.75
    }
  },
  
  "thresholds": {
    "pipe_diameter_mm": 50,
    "duct_area_sqm": 0.56
  },
  
  "brace_types": {
    "angle_fire": {
      "standard_sizes": ["L50x50x5", "L75x75x6", "L100x100x8"],
      "spacing_transverse_m": 30,
      "spacing_longitudinal_m": 60,
      "clearance_mm": 50,
      "base_footprint_mm": [120, 120]
    },
    "angle_mechanical": {
      "standard_sizes": ["L50x50x5ga", "L75x75x6ga", "L100x100x8ga"],
      "spacing_transverse_m": 30,
      "spacing_longitudinal_m": 60,
      "clearance_mm": 50,
      "base_footprint_mm": [120, 120]
    },
    "cable": {
      "diameter_range_mm": [1.5, 9.5],
      "typical_mm": 3.2,
      "spacing_transverse_m": 40,
      "spacing_longitudinal_m": 80,
      "clearance_mm": 25,
      "base_footprint_mm": [50, 50]
    },
    "rod": {
      "diameter_range_mm": [9.5, 22],
      "typical_mm": 12.7,
      "spacing_transverse_m": 35,
      "spacing_longitudinal_m": 70,
      "clearance_mm": 40,
      "base_footprint_mm": [100, 100]
    }
  },
  
  "clearance_rules": {
    "base_from_structure_mm": 50,
    "seismic_zone_addition_mm": 25,
    "hospital_addition_mm": 25,
    "adjacent_system_mm": 75
  },
  
  "angle_constraints": {
    "min_degrees": 30,
    "ideal_degrees": 45,
    "max_degrees": 60,
    "tolerance_degrees": 15
  },
  
  "standards_full_citations": [
    "EN 1998-1:2004+A2:2011. Eurocode 8: Design of Structures for Earthquake Resistance – Part 1: General Rules, Seismic Actions and Rules for Buildings. European Committee for Standardization (CEN), Brussels, 2011.",
    "DIN 4149:2005-04. Bauten in deutschen Erdbebengebieten – Seismische Belastungen und Nachweise im Hochbau. Deutsches Institut für Normung e.V., Berlin, 2005."
  ]
}
```

---

## METHODOLOGY: HOW TO RESEARCH

### For Each Standard:

1. **Locate the standard** — use academic databases, paywalled PDFs, or secondary sources
   - If paywalled: Find peer-reviewed papers citing it (e.g., academic PDFs via Google Scholar, ResearchGate)
   - Declare your source clearly in `paywalled_sections`

2. **Extract quantitative data** — numbers only (spacing in meters, clearance in mm, factors as decimals)
   - Ignore narrative explanations
   - Focus on tables, formulas, and requirements sections

3. **Document the source** — every value must trace back to a specific section
   - Example: "Spacing 30m (transverse), Section 4.3.2, EN 1998-1:2004"

4. **Flag data gaps** — if a value is missing or ambiguous:
   - Do NOT guess or interpolate
   - Flag it in `data_gaps` array
   - Suggest how a human should verify it

5. **Unit consistency** — convert everything to **metric (mm/m)** for the config
   - Imperial source? Convert and note the original
   - Example: "4 inches (original NFPA 13) = 102mm"

---

## FORMATTING REQUIREMENTS

### JSON Output
- Valid JSON (test with `jq` or a JSON validator)
- No trailing commas
- Strings quoted with double quotes
- Numbers (not strings) for quantities

### Markdown Output
- GitHub-flavored Markdown (```json, ```markdown blocks)
- Headings use `#`, `##`, `###`
- Tables use pipes `|`
- Bullet lists use `-` or `*`

### Citations
- Full publication details (author, title, year, publisher, location)
- Example: `EN 1998-1:2004+A2:2011. Eurocode 8: Design of Structures for Earthquake Resistance – Part 1: General Rules, Seismic Actions and Rules for Buildings. European Committee for Standardization (CEN), Brussels, 2011.`

---

## DATA QUALITY EXPECTATIONS

### Accuracy Over Completeness
- If you cannot find a specific value, **flag it as a data gap** rather than guessing
- A config with 80% coverage + explicit gaps is better than 100% coverage with hidden uncertainty

### No Hallucination
- Do not invent standards or section numbers
- Do not quote text you didn't verify
- When in doubt, say so

### Transparency
- Declare paywalled sections and your source (secondary reference)
- List data gaps explicitly
- Note unit conversions (original vs. metric)

---

## DELIVERABLES (What I Need)

### 1. Standards Research Summary (`hermes_standards_research.json`)
- All researched standards in the extraction template above
- One JSON object per standard
- Combined into a single array or object

### 2. Comparison Matrix (`hermes_comparison_matrix.md`)
- Markdown table comparing all standards
- Highlight consensus rules
- Flag conflicts requiring jurisdictional choice
- Include "Resolution Strategy" section

### 3. Case Study + Config Template (`hermes_case_study_and_config.md` + `.json`)
- Markdown: Building type recommendation, MEP systems, seismic zone, expected outputs
- JSON: Populated config file for your primary standard (EN 1998-1 + DIN 4149)
- Markdown: Extensibility guide (how to add a new jurisdiction config)

---

## EXTENSIBILITY GUIDE (What to Document)

Include a short markdown section explaining **how users add a new standard:**

```markdown
# Adding a New Seismic Standard to Blue Halo

## Steps
1. Research the target standard (e.g., BS 5950, SIA 261)
2. Extract spacing, clearance, importance factors using the template above
3. Create new JSON: `{country_code}_{standard_code}.json`
4. Populate all fields; flag data gaps explicitly
5. Test: Run `validate_blue_halo.py --config {new_file}`

## Key Data Points to Extract
- Restraint spacing (transverse, longitudinal) in meters
- Clearance from structure (mm)
- Brace angle constraints (min, ideal, max degrees)
- Seismic hazard factors by building type
- Pipe/duct thresholds
- Importance Factor categories

## Common Pitfalls
- Unit confusion (metric vs. imperial)
- Different terminology (strut vs. brace vs. restraint)
- Hospital/critical building modifiers vary by standard
- Some standards reference others (circular dependencies — track these)
```

---

## TIMELINE & EXPECTATIONS

- **Start:** Immediately (parallel with algorithm Phase 1)
- **Deadline:** 48 hours (so configs integrate into Phase 2)
- **Delivery:** 3 files (JSON summary, comparison matrix, config + extensibility guide)

If you cannot complete all research in 48 hours:
- Prioritize EN 1998-1 + DIN 4149 (Priority 1)
- Flag NFPA 13 + other standards as "Researched But Incomplete" with data gaps noted
- Provide what you have, not a partial guess

---

## IMPORTANT CONSTRAINTS FOR THIS PROJECT

1. **This is a real Masters FMP at a real institution** — accuracy matters
2. **Standards must be correctly cited** — no invented references
3. **Academic submission uses this work** — formatting and sources must be publication-ready
4. **OpenBIM tool (international)** — standards must be vendor-neutral and geographically portable
5. **Deadline is firm: 27 September 2026** — research must complete within 48 hours

---

## CONTACT / CLARIFICATION

If you have questions or encounter a data gap:
1. Flag it explicitly in your output
2. Suggest how a human should verify it
3. Do not guess or leave gaps unexplained

---

**Ready to start research. Load this file at the beginning of each Hermes session.**

**End of HERMES_CONTEXT.md**
