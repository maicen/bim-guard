# PD-001 Proximity / Drip-Path — design v0.1

**Status: FOR APPROVAL. Nothing here is built.** This document is the thing Shane approves before
any implementation session is written. No session in [§12](#12-sessions) may start until
[§7](#7-mechanism-table--placeholder) is filled from sourced clauses and this document is signed off.

Read against the working tree at `267554a` (branch `feat/pd-001-sources`). Every line number is
that commit's. Measurements in [§2](#2-candidate-pair-detection) were taken on this branch by
reading the model offline — no server was contacted, nothing under `app/`, `scripts/` or `tests/`
was changed.

**How to read the markers.** `**TBD (source required)**` marks a value that must come from a
sourced clause and has deliberately not been invented. `OPEN QUESTION` marks a decision that is
Shane's, not the author's. Neither is a placeholder for the author to fill in later from memory.

---

## 1. Scope and non-scope

### What PD-001 detects

Corrosion of a pipe caused by a **nearby but unjoined** pipe of another material: water or vapour
leaving one run and arriving on another that it never touches. Whole-network engine over
`PipingElement`, the same family as MM-001 and XM-001 — scored once over the network rather than
element by element (`app/modules/phase_6/phase_6c_corrosion_ui.py:155-162`).

### The physics boundary — one paragraph

Galvanic corrosion needs three things at once: two metals of different potential, metallic
continuity between them, and a shared electrolyte bridging them. Two pipes 40 mm apart in dry air
have none of the three and are not a couple; the same two pipes with water running off the upper
one onto the lower have the third, and the run-off itself carries dissolved metal that does the
work of the first. **PD-001 therefore scores water transfer between unjoined pipes, not distance
alone.** Distance is a necessary condition that gates the search, never a sufficient one that
raises a finding. A pair that is close but has no transfer path — nothing above the other, nothing
condensing, no aggressive medium — is not a PD-001 finding, and the engine must say so rather than
banding it Low. This is the one design constraint that must survive every later simplification:
the sourced mechanism the corpus actually supports is *run-off carrying dissolved copper onto
zinc* (`docs/planning/pd001_mechanism_table_draft.md:23`), which is a statement about transported
water, not about millimetres.

### What XM-001 keeps

XM-001 keeps **contact and shared-loop electrolyte**. It pairs elements two ways
(`app/modules/comparator/cross_material.py:334-374`):

- `direct_contact` — the two share a joint, i.e. one appears in the other's `joined_to`, populated
  by the four-tier resolution in `piping_producer.py:1670-1787` (Tier 1 ports `:1441`, Tier 2
  centreline endpoints `:1503-1511`, Tier 3 tessellated surfaces `:1538-1668`).
- `same_loop` — not touching, but on one connected component of the piping graph and the same
  system, so an electrolyte path exists through the water itself
  (`cross_material.py:361-372`, factor 0.8 at `data/rulesets/xm_001_cross_material.json:141-150`).

PD-001 takes neither. **Every pair XM-001 already reports is excluded from PD-001**
([§2](#2-candidate-pair-detection)), so the two engines never both bill the same physical
relationship.

### What MM-001 keeps

MM-001 keeps **one material against the medium inside its own pipe** — material–media
compatibility, before any second element exists
(`app/modules/comparator/material_media.py:46-56`). PD-001 never re-scores a single element
against its own contents; where a PD-001 mechanism needs to know what the upper pipe carries it
reads `media_for_system` (`piping_producer.py:508-545`) as an *input*, and leaves the verdict
about that medium to MM-001.

### The gap the three leave

| Relationship | Owner today |
| --- | --- |
| Two materials sharing a joint | XM-001 `direct_contact` |
| Two materials on one connected loop | XM-001 `same_loop` |
| One material against its own medium | MM-001 |
| **Two materials near each other, unjoined, on different systems** | **nothing — PD-001** |

On 1540 that gap is the whole model: `west_riverside_hospital_plumb_ifc4.ifc` produced **one**
XM-001 finding across 8,539 elements
(`docs/validation/engine-showcase-2026-09-08/README.md`, branch `docs/engine-showcase-2026-09-08`),
because near-but-unjoined is exactly what nothing looks at.

### Explicitly out of scope for v0.1

- Contact of any kind — XM-001's, whatever tier resolved it.
- Certifying a clearance. `calculate_shortest_distance` is documented as an upper bound in the
  general case and "unsuitable for certifying a precise clearance"
  (`app/modules/ifc_reader/ifc_geometry.py:808-817`). PD-001 asks "is there a transfer path", not
  "is this clearance compliant".
- Any verdict resting on an inferred material without saying so — see [§4](#4-mechanism-families-and-inputs).

---

## 2. Candidate-pair detection

### The rule, not a literal

A pair is a candidate when its surface separation is **at most `D_max`**, where `D_max` is a rule
row read from `public.rules`, not a constant in the engine. Value: **TBD (source required)** —
[§13](#13-open-questions-for-shane) lists what to look for in the five pending PDFs.

There is already a declarative 25 mm in the tree — `DEFAULT_CLEARANCE_MM = 25.0`
(`scripts/seed_galvanic_corrosion_rules.py:96`), carried onto every seeded couple as
`parameters.min_clearance_mm` (`:221`, `:236`) with mitigation `MIT-GC-006` "Increase separation
distance to prevent moisture bridge formation" (`app/engines/bimguard_corrosion_engine.py:340`).
That seeder states plainly that nothing reads it: *"XM-001 v1.0 scores separation categorically
(direct_contact 1.0 / same_loop 0.8) and reads no millimetre geometry, so min_clearance_mm is
declarative until an evaluator consumes it"* (`seed_galvanic_corrosion_rules.py:241-246`, and the
module warning at `:63-70`). **PD-001 is the evaluator that would consume it.** But 25 mm is not
sourced — the seeder's own clause is MIL-STD-889B Table II, which supplies galvanic potentials and
"does not mention clearance" (`:57-59`). Adopting 25 mm as `D_max` because it is already typed
into the repository would be inventing a number. It is a **candidate to look for in the sources**,
not a default.

### How pairs are found

1. **Prune on bounding boxes.** `_bbox_gap_m` (`piping_producer.py:1513-1536`) returns the
   axis-aligned gap between two boxes — a true *lower* bound on surface separation, so a pair whose
   box gap already exceeds `D_max` cannot be within `D_max` and needs no tessellation. Boxes come
   from `_geometry` (`:1332`), which reads local vertices and the placement matrix without invoking
   the mesher at all (`:1519-1523`).
2. **Measure the survivors.** `IFCGeometryExtractor.calculate_shortest_distance`
   (`ifc_geometry.py:775-818`) — cKDTree broad phase, point-to-triangle narrow phase, symmetric,
   in millimetres. It returns `None`, never a number, when separation cannot be established
   (`:797-806`); PD-001 must treat `None` as `geometry_unavailable` and never as "far apart", the
   same contract Tier 3 already honours (`piping_producer.py:1574-1582`).
3. **Exclude what XM-001 owns.** Drop any pair where either element lists the other in
   `joined_to`, and any pair XM-001's `_candidate_pairs` would return as `same_loop` — same
   connected component (`cross_material.py:304-332`) *and* same system (`:361-364`).

### Cost on 1540 — measured, then estimated

Two facts have to be separated. The showcase's XM-001 run on `west_riverside_hospital_plumb_ifc4`
took **34.0 s** for 8,539 elements, but **Tier 3 was off**: it is gated on
`FEATURE_XM_GEOMETRIC_ADJACENCY`, which defaults to `"0"`
(`app/modules/config.py:115-116`, wired at `phase_6b_parsing.py:298-302`). So no published timing
covers a tessellation pass over this model, and the cost below had to be measured directly.

**Measured on this branch** (offline, `produce_piping_elements_from_model` on the 1540 model):

| Quantity | Measured |
| --- | --- |
| Elements produced | 8,539 |
| Elements carrying a bounding box | **4,308** (all `IfcPipeSegment`) |
| Elements with no bounding box | **4,231** (the `IfcPipeFitting`s) |
| Elements with non-empty `joined_to` | 8,536 of 8,539 |
| Material from IFC / inferred / unknown | **0** / 4,976 / 3,563 |
| Environment defaulted to `T1_indoor_damp` | 8,539 of 8,539 |

Bounding-box prune survivors, over the 4,308 elements that have a box (unordered pairs, self-pairs
removed), and the vectorised scan time for the full 4,308 × 4,308 pass:

| `D_max` | Surviving pairs | Prune scan |
| ---: | ---: | ---: |
| 25 mm | 804 | 3.1 s |
| 50 mm | 1,244 | 2.9 s |
| 150 mm | 3,897 | 3.3 s |
| 300 mm | 8,269 | 3.3 s |
| 500 mm | 12,828 | 3.2 s |
| 1000 mm | 29,306 | 3.3 s |

Tessellated distance, timed on 40 real surviving pairs from this model: **≈8–10 ms per pair** on
first touch, **≈2 ms** once both elements' tessellations are cached. 40 of 40 returned a
measurement, none returned `None`.

**The estimate.** Prune ≈ 3 s (vectorised) plus survivors × ≈8 ms:

| `D_max` | Estimated pair-scan cost on 1540 |
| ---: | ---: |
| 25 mm | ≈ 3 s + 6 s = **≈ 9 s** |
| 300 mm | ≈ 3 s + 66 s = **≈ 69 s** |
| 500 mm | ≈ 3 s + 103 s = **≈ 106 s** |

**Basis, and what would make it wrong.** The per-pair figure is a 40-pair sample from one model,
so it carries that sample's variance; tessellation caching means the marginal cost falls as the
scan proceeds, which makes ≈8 ms an upper estimate rather than a mean. Three things could move it:

- **The prune must be vectorised.** The 3 s figure is a NumPy pass. The existing Tier 3 loop is a
  Python double loop over candidates × elements (`piping_producer.py:1626-1662`), which at
  4,308² ≈ 18.6 M iterations would dominate everything else. Reusing that loop shape at this scale
  is a design error; PD-001 needs a vectorised or spatial-index prune. **This is the single
  largest implementation risk in §2.**
- **Half the model cannot be pruned.** 4,231 fittings carry no bounding box, so `_bbox_gap_m`
  returns `None` — "cannot prune, must measure" (`:1524-1526`). Measuring every fitting against
  every element is not affordable. v0.1 should report those pairs as `geometry_unavailable` rather
  than measuring them, and count them; whether that is acceptable is **OPEN QUESTION 4**.
- **Parse cost is separate and larger.** Opening plus producing the network measured 6.4 s + 47.5 s
  here, against the showcase's 34.0 s for the whole XM-001 run — a discrepancy between two
  different machines and cache states that is **reported, not reconciled**. PD-001 adds no parse;
  it consumes the network the parse already produced.

---

## 3. Geometric classification per pair

Every number below comes from `PipingElement` fields the producer already populates. Nothing new
is read from the IFC.

| Datum | How | Source | When absent |
| --- | --- | --- | --- |
| Which element is above | Compare centroid Z. `centroid` is a `Point3D` in metres, from `_centroid` via the placement matrix, unit-scaled (`piping_producer.py:1239-1263`, scale `:1222-1237`) | `element.centroid.z` | `centroid is None` → `geometry_unavailable`; the producer already warns "no placement — element excluded from adjacency detection" (`:1880`) |
| Vertical gap | Difference of bounding-box Z extents: `lower.bbox.max.z` to `upper.bbox.min.z` | `element.bbox` from `_geometry` (`:1332-1385`) | either box `None` → `geometry_unavailable` (4,231 of 8,539 on 1540) |
| Horizontal offset | Axis-aligned XY gap between the two boxes — the same construction `_bbox_gap_m` uses per axis (`:1528-1535`), taken over X and Y only | `element.bbox` | as above |
| Surface separation | `calculate_shortest_distance`, millimetres (`ifc_geometry.py:775-818`) | tessellation | returns `None` → `geometry_unavailable`, never a distance |
| Parallel vs crossing | Angle between centreline direction vectors, from first and last centreline point | `element.centerline.points` (`:1503-1511` shows the same endpoints Tier 2 uses) | no centreline on either → `orientation_unavailable`; classification falls back to bbox overlap in plan |
| Storey agreement | Both elements' `level_id` | `_storey` (`:1387-1397`) | `None` — a pair spanning an unknown storey is still assessable; recorded, not gating |

**Ordering rule.** "Above" is decided on centroid Z alone, and only where both centroids exist. A
pair whose centroids are within **TBD (source required)** of each other in Z has no meaningful
upper element and is classified `coplanar` — no drip path, no finding, recorded as assessed.

**`geometry_unavailable` is a status, not a skip.** It is reported as a data-quality note through
the same path MM-001 and XM-001 use (`cross_material.py:407-446`), so a reviewer can see that a
pair was found and could not be measured. On 1540 this will be the majority status, and that is the
honest answer.

---

## 4. Mechanism families and inputs

Two families. Whether both ship in v0.1 is **OPEN QUESTION 2**.

### (a) Galvanic drip-path

Water leaves an upper metal pipe and lands on a lower pipe of a different metal, carrying dissolved
metal with it. The sourced mechanism: *"Even runoff water from copper or brass surfaces can contain
enough dissolved copper to cause rapid corrosion"* of zinc
(`docs/planning/pd001_mechanism_table_draft.md:23`).

| Input | Field | Where it comes from | Tri-state status when absent |
| --- | --- | --- | --- |
| Upper material | `element.material` | `resolve_material` (`piping_producer.py:1158-1220`) | `"Unknown"` → `material_unresolved` |
| Lower material | `element.material` | as above | `material_unresolved` |
| **Whether each material was read or assumed** | `properties[MATERIAL_SOURCE_KEY]` — `"ifc_metadata"` vs `"system_inference:<system>"` (`:88-97`) | `resolve_material` (`:1195-1220`) | see the warning below |
| Nobility ordering | GC-001 galvanic series, as XM-001 already reads it (`cross_material.py:198-208`, pack `data/rulesets/xm_001_cross_material.json`) | rule pack | material absent from the series → `material_not_in_series`, the status XM-001 already emits (`cross_material.py:625-640`) |
| Upper service condensing or leak-prone | condensation test below; medium via `media_for_system` (`:508-545`) | system classification (`:440-478`) | system `UNKNOWN` → `system_unclassified`; producer already warns (`:1827`) |
| Environment | `element.environment_class` + `environment_source` | `resolve_environment` (`:683-721`) | `UNCLASSIFIED`, or `default_indoor` — see below |

**The material-provenance warning, which is the most important line in this section.** On 1540,
**zero** elements resolved a material from the IFC; 4,976 got one by system inference and 3,563 got
nothing (measured, §2). An inferred material is tagged `system_inference:<system>` and already
carries an element warning saying it was "not read from the IFC"
(`piping_producer.py:101-106`, applied `:1846-1855`). A PD-001 verdict built on two inferred
materials is a verdict about a design convention, not about the model. **v0.1 must either refuse to
band such a pair, or band it and carry the provenance in the finding.** Which of the two is
**OPEN QUESTION 3**. What it must not do is score an inferred pair identically to a read one, which
is the failure `MATERIAL_SOURCE_KEY` was introduced to prevent (`:80-97`).

### (b) Chemical drip / vapour

An upper service carrying an aggressive medium — acid, solvent, chloride — over a metallic pipe.

| Input | Field | Where it comes from | Tri-state status when absent |
| --- | --- | --- | --- |
| Upper medium | `media_for_system(element.system)` | `SYSTEM_TO_MEDIA` (`:508-534`) | `"unknown"` (`:545`) → `media_unresolved` |
| Which media count as aggressive | rule row | to be seeded | list is **TBD (source required)** |
| Lower material susceptibility | material + medium, the MM-001 compatibility matrix (`data/rulesets/mm_001_material_media.json`) | rule pack | unmapped pairing → data-quality Issue, never a default; the pack states this policy explicitly (`mm_001_material_media.json:56`) |
| Environment | as above | `resolve_environment` | as above |

**Note on the corpus.** The captured sources supply *no* citable passage for vapour attack — it is
gap 2 of the ten (`pd001_mechanism_table_draft.md`, "Suspected gaps"). Family (b) therefore has no
sourced row at all today, which is the substance of **OPEN QUESTION 2**.

### The condensation test

An upper line drips when its surface is below the dew point of the air around it.

```
condensing  ⇔  T_surface  <  T_dew(T_ambient, RH)
```

- **`T_surface`** — approximated by `element.operating_temperature_c`
  (`resolve_temperature`, `piping_producer.py:862-910`). Read from the IFC when the model states
  one (`TEMPERATURE_PROPERTY_KEYS`, `:810-816`); otherwise inferred from the system's design
  temperature (`_SYSTEM_TEMPERATURE_INFERENCE`, `:757-808`) and tagged `system_inference` with low
  confidence (`:820-826`). Absent and uninferable → `temperature_unavailable`.
  Whether bare operating temperature is an acceptable stand-in for surface temperature — it ignores
  insulation, which no model in the corpus carries ([§5](#5-shared-support-and-shared-insulation)) —
  is **TBD (source required)**.
- **`T_dew`** — from a standard psychrometric relation. The Magnus–Tetens form is the conventional
  choice; its coefficients and the valid temperature range are **TBD (source required)** and must
  be cited to a psychrometric reference, not typed from memory.
- **`RH`** — from the environment-class ladder. **That ladder lives on the enum members themselves**:
  `app/modules/ifc_reader/piping_schema.py:109-116`, where `T0_DRY = "T0_dry"` carries `# <50% RH,
  indoor heated`, `T1_INDOOR_DAMP` carries `# 50-80% RH, indoor unheated`, and `T2_HUMID` carries
  `# >80% RH or condensing`. **T3, T4 and T5 carry chemistry, not humidity** (`:113-115`) — the
  XM-001 pack records the same asymmetry (`xm_001_cross_material.json:87`). So the ladder supplies
  an RH range for three of six classes and none for the other three, and the RH to use for T3–T5 is
  **TBD (source required)**.
- **`T_ambient`** — not carried by `PipingElement` at all. Sourcing it is **TBD (source required)**.

**The compounding problem, stated plainly.** On 1540 all 8,539 elements had environment
`default_indoor` — not read, not inferred from spatial names, defaulted
(`DEFAULT_ENVIRONMENT_CLASS = T1_INDOOR_DAMP`, `piping_producer.py:632`, applied `:713-720`, tagged
`"low"` confidence `:626-630`). A condensation verdict computed from a defaulted RH band, a
defaulted ambient and an inferred surface temperature is three assumptions deep. **v0.1 must emit
the condensation flag with its three inputs attached** ([§8](#8-finding-shape)) so a reviewer can
see the depth, and must not band a pair on a condensation flag whose inputs were all defaulted.

---

## 5. Shared support and shared insulation

**Neither is in any model in the corpus. Stated plainly, because it determines what v0.1 can do.**

- **Supports.** No `IfcDiscreteAccessory`, hanger, bracket or fixing appears in the accepted class
  list at all: `PIPING_IFC_CLASSES` (`piping_producer.py:118-137`) covers pipes, ducts, fittings,
  valves, pumps, filters, tanks, heat exchangers, air terminals and the generic flow classes, and
  nothing else. An element of any other class "is invisible to the audit entirely — not skipped,
  never seen" (`docs/reference/piping_intake_sources.md` row 1, branch `feat/model-intake-ids`).
  The only route a support material reaches the audit today is as a *declared property* on the pipe
  — `SupportMaterial`, `BracketMaterial`, `FixingMaterial` (`app/modules/ifc_reader/ifc_parser.py:517-522`)
  — and the intake doc records the reason: "there is no buildingSMART property for this — IFC
  models contact through geometry" (row 22).
- **Insulation.** Read only as thickness and material name on the pipe itself
  (`InsulationThickness`, `ThermalInsulationThickness`, `InsulationMaterial`, `InsulationType`,
  `piping_producer.py:1918-1922`), whose recorded consequence is "None" — nothing consumes it
  (intake doc row 31). There is no insulation *element*, so there is no such thing as two pipes
  sharing one.
- **Corpus evidence.** The showcase inventory shows what the parser accepted from 1540: 4,308
  `IfcPipeSegment` and 4,231 `IfcPipeFitting`, nothing else
  (`docs/validation/engine-showcase-2026-09-08/README.md`, "What the parser actually accepted").

### Consequence for v0.1

Two statuses, both **data-quality notes, never defaults**:

| Status | Meaning | Raised when |
| --- | --- | --- |
| `support_unmodelled` | The model carries no support element and no declared support material, so contact at a shared support cannot be assessed for this pair | a candidate pair is otherwise assessable and neither element declares `SupportMaterial` / `BracketMaterial` / `FixingMaterial` |
| `insulation_unmodelled` | The model carries no insulation element, so a shared-insulation transfer path cannot be assessed | a candidate pair is otherwise assessable and neither element carries an insulation thickness |

**These are not findings and must never be banded.** A shared support that is not modelled is
absence of evidence, exactly as XM-001 already treats an empty `joined_to` on an element with no
connectivity source — "An empty joined_to here is absence of evidence, not evidence of isolation"
(`cross_material.py:609`). PD-001 inherits that wording and that discipline. Assuming a steel
hanger because most hangers are steel would fabricate the couple the engine exists to find.

---

## 6. Scoring

A weighted composite in the established style. XM-001's is
`voltage 0.5 / separation 0.3 / environment 0.2`
(`data/rulesets/xm_001_cross_material.json:73-77`); MM-001's is
`0.40*score + 0.35*environment_severity + 0.25*temperature_stress`
(`data/rulesets/mm_001_material_media.json:55`).

### Proposed terms

| Term | What it measures | Weight |
| --- | --- | --- |
| `potential_risk` | Galvanic driving potential between upper and lower material, normalised — the axis XM-001 already normalises at 1.0 V (`xm_001_cross_material.json:128-133`) | **TBD (source required)** |
| `transfer_risk` | Strength of the transfer path: run-off > condensation drip > vapour. This is the term that carries PD-001's physics and has no counterpart in any existing engine | **TBD (source required)** |
| `separation_risk` | Surface separation against `D_max`, and vertical gap. The first millimetre geometry any corrosion engine will have consumed | **TBD (source required)** |
| `environment_risk` | Environment class severity — reusing MM-001's `environment_severity` table so bands mean the same thing across engines | **TBD (source required)** |

Weights must sum to 1.0. **Every weight above is TBD (source required). No number in this section
may be invented, and none has been.**

### Band boundaries

Three boundaries, seeded as rule rows, read from the DB at run time via
`RuleService.list_by_ruleset` (`app/services/rules_service.py:831-836`):

| Band | Boundary |
| --- | --- |
| medium | **TBD (source required)** |
| high | **TBD (source required)** |
| critical | **TBD (source required)** |

**Strong prior, recorded as a prior and not as a value:** XM-001 uses `0.35 / 0.65 / 0.85` and its
pack says they are "Matched to MM-001 and GC-001 so bands mean the same thing across mechanisms"
(`xm_001_cross_material.json:168-173`). Matching PD-001 to the same three is the obvious choice and
is what the author expects to happen — but it is a decision for [§13](#13-open-questions-for-shane),
not an assumption to bake in here.

### Seeding

Rows go into `public.rules` through a `scripts/seed_pd_001_rules.py` in the shape
`seed_galvanic_corrosion_rules.py` already establishes: `rule_category: "threshold_band"`
(`:256`), the scoring detail in `parameters` as JSON (`:274`), `ruleset_id` (`:281`), and a
`source_text` naming the clause (`:277`). Note the two constraints that seeder documents and PD-001
inherits: there is no `mitigation` column on `rules`, so mitigation text lives in
`parameters.mitigation` with `parameters.mitigation_refs` pointing at catalogue codes (`:46-52`);
and the shared mitigation catalogue is never rewritten in place, because that would silently
restate the mitigation on every historical finding (`:54-62`).

---

## 7. Mechanism table — placeholder

**This section is the gate. No session in [§12](#12-sessions) starts until it is filled, and no row
enters a seeder without a clause.**

Column set, fixed:

`mechanism | upper material | lower material | transfer path | environment condition | orientation/separation rule (verbatim) | source | clause`

### The one sourced row

| mechanism | upper material | lower material | transfer path | environment condition | orientation/separation rule (verbatim) | source | clause |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dissolved copper carried in run-off water from an upstream copper or brass surface causes rapid corrosion of zinc on a galvanized surface it lands on: "Even runoff water from copper or brass surfaces can contain enough dissolved copper to cause rapid corrosion." | Copper or brass | Hot-dip galvanized (zinc-coated) steel | run-off | "in a moist or humid environment" | "The design should ensure water is not recirculated and water flows from the galvanized surface towards the copper or brass surface and not the reverse." | `docs/scraped_standards/corrosion_pd001_aga_contact_other_metals.md:38` | none — secondary source |

That is the whole of it. The draft carries eight rows, but seven describe **direct contact**
(`pd001_mechanism_table_draft.md:24-30`), which XM-001 owns and PD-001 excludes by
[§1](#1-scope-and-non-scope). **Exactly one row in the captured corpus describes near-but-unjoined.**
It names no primary standard, and its separation rule is an orientation rule with no figure.

### The ten gaps — empty rows, no data

| # | mechanism | upper material | lower material | transfer path | environment condition | orientation/separation rule (verbatim) | source | clause |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Condensation drip from a cold pipe onto a dissimilar pipe or support beneath it | | | | | | | |
| 2 | Vapour-phase attack on a pipe from a nearby pipe's emissions or leakage | | | | | | | |
| 3 | Shared or continuous insulation as a transfer path between adjacent dissimilar services | | | | | | | |
| 4 | Corrosion under insulation where wetting arrives from an adjacent pipe rather than from outside | | | | | | | |
| 5 | Any numeric separation, clearance or vertical-offset distance between dissimilar-metal services | | | | | | | |
| 6 | Any rule on which service must be routed above the other where drip paths cross | | | | | | | |
| 7 | Shared-support / hanger material mismatch treated separately from pipe-to-pipe contact | | | | | | | |
| 8 | Dezincification of copper-alloy fittings | | | | | | | |
| 9 | Stress-corrosion cracking of 316 stainless from an adjacent chloride source | | | | | | | |
| 10 | Whether an expansion-driven movement can close a designed separation and create contact | | | | | | | |

Gaps 5 and 6 are the ones that block [§2](#2-candidate-pair-detection) and [§6](#6-scoring): without
them there is no sourced `D_max` and no sourced orientation rule.

### The five documents pending

| # | Document | Status |
| --- | --- | --- |
| 1 | NZBC G12/AS1 3rd edition amendment 14 | Incapsula bot-blocked; needs a manual browser download (`docs/scraped_standards/pd001_sources.md`, MISMATCH 1) |
| 2 | NZBC G12/AS3 amendment 14 | the scraped CodeHub page is the superseded edition (MISMATCH 3) |
| 3 | CDA Copper Tube Handbook (A4015) | only the landing page was captured; the handbook itself was not (MISMATCH 6) |
| 4 | AS/NZS 3500.1 | standards.govt.nz login (GAP 12) |
| 5 | Nickel Institute 316 SCC guide | captured file is an email-gated download form, not the publication (MISMATCH 7) |

**Rule: no row enters `scripts/seed_pd_001_rules.py` without a clause in its `source_text`.**

---

## 8. Finding shape

### `AuditIssueContract` fields PD-001 populates

The contract is `app/modules/contracts.py:803-817`; `details` is `dict(issue.metadata)`
(`app/api/analyze.py:209`).

| Field | Value |
| --- | --- |
| `id` | allocated by `IssueIdAllocator` under prefix `PD` |
| `element_id` | **the lower element's GlobalId** — the one at risk. Both GUIDs go in `details` |
| `rule_id` | `PD-001.01` |
| `title` | `f"Proximity / drip-path risk on {name or guid[:8]}"`, matching `phase_6c_corrosion_ui.py:1094` |
| `mechanism` | `"PD-001 proximity / drip-path"` for a verdict; `"data_quality"` for a note (`phase_6c_corrosion_ui.py:130`) |
| `band` | `RiskBand`, through `normalise_band` (`phase_6c_corrosion_ui.py:210`) |
| `score` | composite, 0.0–1.0 |
| `mitigation` | resolved from the catalogue below |
| `assignee_role` | `"BIM coordinator"` |
| `citations` | the clause behind the row that fired |
| `details` | `dict(metadata)`, below |

### New `details` keys

| Key | Meaning |
| --- | --- |
| `upper_element_id` | GUID of the element above |
| `lower_element_id` | GUID of the element below — same value as `element_id` |
| `vertical_gap_mm` | bbox Z separation, or `null` |
| `horizontal_offset_mm` | bbox XY separation, or `null` |
| `surface_separation_mm` | `calculate_shortest_distance`, or `null` when it returned `None` |
| `mechanism_family` | `"galvanic_drip"` or `"chemical_drip"` |
| `transfer_path` | `"run_off"` / `"condensation_drip"` / `"vapour"` |
| `condensation` | `true` / `false` / `null` |
| `condensation_inputs` | `{surface_temp_c, surface_temp_source, ambient_temp_c, ambient_source, rh_band, rh_source, dew_point_c}` — **the flag never travels without its inputs** |
| `upper_material`, `lower_material` | canonical keys |
| `upper_material_source`, `lower_material_source` | `"ifc_metadata"` vs `"system_inference:<system>"` (`piping_producer.py:88-97`) — [§4](#4-mechanism-families-and-inputs) |
| `environment_source`, `environment_confidence` | as `_provenance` already reports (`phase_6c_corrosion_ui.py:857-876`) |
| `ruleset_version` | `"BIMGUARD-PD-001 v0.1.0"` |
| `check` | on a data-quality note: `material_unresolved`, `geometry_unavailable`, `support_unmodelled`, `insulation_unmodelled`, `temperature_unavailable`, `media_unresolved` |

`ruleset_version` is stamped on **verdicts and data-quality notes alike** — "A note about an element
that could not be assessed is still a statement made under a particular ruleset revision"
(`phase_6c_corrosion_ui.py:919-925`).

### Mitigation catalogue

New codes, **not** edits to existing ones — rewriting a catalogue entry in place restates the
mitigation on every historical finding (`seed_galvanic_corrosion_rules.py:54-62`).

| Code | Text | Source |
| --- | --- | --- |
| `MIT-PD-001` | Relocate the lower run out of the upper run's drip path | **TBD (source required)** |
| `MIT-PD-002` | Reorder the two services vertically so run-off flows from the less noble surface toward the more noble one | **TBD (source required)** — the sourced orientation rule ([§7](#7-mechanism-table--placeholder)) supports the principle; the mitigation wording still needs a clause |
| `MIT-PD-003` | Isolate the two services where they meet at a common support | **TBD (source required)** |
| `MIT-PD-004` | Fit a drip tray or shield between the two services | **TBD (source required)** |

`MIT-GC-006` "Increase separation distance to prevent moisture bridge formation"
(`bimguard_corrosion_engine.py:340`) is **referenced, never redefined** — it is already the
separation half of the seeded GC/XM requirement (`seed_galvanic_corrosion_rules.py:112-116`).

---

## 9. Orchestration and UI

### Where it plugs in

| Step | Change |
| --- | --- |
| Spec | `PD = MechanismSpec("PD-001", "PD-001.01", "PD", "Proximity / drip-path")`, beside the five at `phase_6c_corrosion_ui.py:150-154` |
| Set | append to `NETWORK_MECHANISMS` (`:162`) — network, not per-element. `MECHANISMS` composes automatically (`:165`) |
| Dispatch | a branch in `_assess_network` (`:848-854`), beside MM-001 and XM-001 |
| Comparator | `app/modules/comparator/proximity_drip.py`, mirroring `cross_material.py` — `compare(network, rule_pack, id_allocator)` returning finished `Issue`s (`cross_material.py:576-596`) |
| Version stamp | `_pack_ruleset_version` (`:755-770`), the path XM-001 uses (`:839-841`) |

**Canonical engine key: `PD-001`, prefix `PD`.** `resolve_engine_codes` (`:200-207`) canonicalises
`None`, `["pd"]` and `["PD-001"]` to the same tuple, and that tuple is what the cache key stores.

### Cache-key impact — the pre-warm consequence

The cache key is `CacheKey(project_id, slug, source_sha256, engines, include_low)`
(`app/services/analysis_runner.py:418-432`), where `engines` is the canonical tuple. Every distinct
chip selection is therefore a distinct entry, and `scripts/prewarm_demo.py` warms every one:
`PIPING_ENGINES` is currently the five (`prewarm_demo.py:71`) and the script's own docstring records
"For five engines this is 31 selections: 2**5 - 1" (`:224`).

**A sixth piping engine takes that from 31 to 63 — 2⁶ − 1.** The pre-warm run roughly doubles, and
so does the number of entries held per project. Two consequences to decide before building:

- Pre-warm wall-clock on the demo roughly doubles. On 1540, where the five-engine run is ~33.5 s,
  63 combinations is a materially longer freeze-day procedure.
- If `D_max` lands at the high end ([§2](#2-candidate-pair-detection): ~106 s at 500 mm), the
  combinations that include PD-001 are individually much slower than any existing one.

Whether the demo pre-warms all 63 or only the full set — `--combinations full-only` already exists
(`prewarm_demo.py:49`) — is **OPEN QUESTION 5**.

### UI

- **Chip.** `{ id: "PD", label: "PD-001", title: "Proximity / drip-path" }` in `PIPING_ENGINES`,
  `frontend/src/routes/AnalyzeView.svelte:109-115`. The chip list drives the default selection at
  `:116`, so PD-001 is on by default unless deselected.
- **Explainer card.** A section in `frontend/src/lib/components/PipingChecksExplainer.svelte`, and a
  glossary entry in `frontend/src/lib/glossary.ts`.
- **Pipeline label.** `PipelineProgress.svelte:27` names engines in its stage-3 description and
  already omits MM/XM; whether to extend it is cosmetic and out of scope here.

### Export

CSV columns are the module constant `CSV_COLUMNS` (`app/modules/phase_6/phase_6e_export.py:77-105`),
sixteen today. `clearance_mm` already exists and is blank on every non-seismic row — the comment at
`:91-100` explains that it and `overlap_volume_mm3` are SB-001's, and warns about a column that was
blank on every row ever exported. **PD-001 must not quietly borrow `clearance_mm`**: its
`surface_separation_mm` is a different measurement with a different contract (an upper bound, not a
certified clearance — `ifc_geometry.py:808-817`). Whether to add a column or leave the value in the
JSON `details` only is **OPEN QUESTION 6**.

---

## 10. Demo scenarios

Five scenarios for `scripts/generate_demo_mep_model.py`. The generator authors by index, not random
draw, "so the proportions are exact and a test can assert them" (`:121-141`); systems come from the
`SYSTEMS` table (`:205-259`) and zones/storeys from `ZONES` / `STOREYS` (`:263-268`). PD-001
scenarios need **vertical stacking**, which the generator does not currently author — that is the
main new capability.

| # | Scenario | Materials | Why it is here | Expected band |
| --- | --- | --- | --- | --- |
| 1 | Copper DHW above galvanised fire main, upper line condensing | `Copper` over `Galvanised Steel` | The one sourced mechanism ([§7](#7-mechanism-table--placeholder)), in the orientation the AGA sentence warns against | **expected band TBD until rules are sourced** |
| 2 | Galvanised above copper — the reverse | `Galvanised Steel` over `Copper` | The control. The sourced rule says water should flow *from* galvanised *toward* copper, so this orientation is the compliant one and should produce **Low or no finding** | **expected band TBD until rules are sourced** |
| 3 | Chilled-water line over carbon steel | `Stainless Steel 316` or `Carbon Steel` over `Carbon Steel` | Condensation drip with no galvanic driver — tests that the condensation path fires on its own. CHW is 6 °C in the generator (`:230`), well below any plausible dew point | **expected band TBD until rules are sourced** |
| 4 | Acid drain over 316L | aggressive medium over `Stainless Steel 316` | Family (b). Needs a new `SYSTEMS` entry — no chemical/acid system exists in the table today (`:205-259`) | **expected band TBD until rules are sourced** |
| 5 | A pair sharing a modelled common hanger | any dissimilar pair | The only scenario that exercises `support_unmodelled` **not** firing. Requires authoring a support the parser can see, which today means a declared `SupportMaterial` property, since no support class is accepted ([§5](#5-shared-support-and-shared-insulation)) | **expected band TBD until rules are sourced** |

**Every expected band is TBD until [§7](#7-mechanism-table--placeholder) is filled.** Writing
expected bands now would be inventing the rules the scenarios are meant to test.

**The model's SHA-256 will change.** It is asserted in
`tests/test_model_intake_ids.py` and in `docs/demo/RUNBOOK.md`, and the showcase's cross-checks
depend on the current five-engine totals (1,988 findings at 10/168/1,206/322). Adding scenarios
invalidates all three. Whether that happens before or after the defence is **OPEN QUESTION 7**.

---

## 11. Test plan

All count-asserting, in the style the repository already uses.

### Pair detection

| Test | Assertion |
| --- | --- |
| `test_pair_count_on_synthetic_model` | Exact candidate-pair count on the demo model at the seeded `D_max`, derived from the generator's authored geometry the way `DEMO_WITH_MATERIAL = 378` is derived from `has_material` |
| `test_zero_pairs_when_dmax_is_zero` | `D_max = 0` yields **zero** candidate pairs and zero findings — the boundary that proves detection is gated on the rule row and not on a literal |
| `test_xm_pairs_are_excluded` | No pair PD-001 reports appears in `cross_material._candidate_pairs` output for the same network — the two engines never bill one relationship twice |
| `test_bbox_prune_is_a_lower_bound` | For a sample of pairs, `_bbox_gap_m` ≤ `calculate_shortest_distance`/1000. Guards the prune's correctness, since a prune that over-rejects silently loses findings |

### Tri-state on 1540

| Test | Assertion |
| --- | --- |
| `test_1540_all_material_unresolved` | Every PD-001 finding on `west_riverside_hospital_plumb_ifc4.ifc` is data-quality; **zero** verdicts. Measured basis: 0 of 8,539 elements resolve a material from the IFC (§2) |
| `test_1540_geometry_unavailable_count` | The count of `geometry_unavailable` notes matches the 4,231 elements with no bounding box (§2) |
| `test_data_quality_never_masquerades_as_a_verdict` | Extend the existing separation test named at `phase_6c_corrosion_ui.py:889-893` to PD-001 |

### Rules from the database

| Test | Assertion |
| --- | --- |
| `test_band_boundaries_read_from_db` | Band boundaries come from `RuleService.list_by_ruleset` (`rules_service.py:831-836`), not from a module constant. Changing the row changes the band |
| `test_dmax_read_from_db` | Same for `D_max` |

### Consistency with the existing run

| Test | Assertion |
| --- | --- |
| `test_pd001_alone_equals_its_share_of_the_six_engine_run` | Findings from `engines=["PD"]` are exactly the PD-001 subset of `engines=None`. The invariant the showcase already checks for the five |
| `test_five_engine_totals_unchanged` | Adding PD-001 does not move any existing engine's counts on the demo model |

### Export

| Test | Assertion |
| --- | --- |
| `test_bcf_zero_violations` | The BCF 2.1 archive validates against `tests/schemas/bcf21/markup.xsd` with **zero** violations, via `schema.iter_errors(markup)` as `tests/test_phase_6e_export.py:466-475` already does |
| `test_csv_columns_unchanged_or_extended_deliberately` | `CSV_COLUMNS` either unchanged or extended with a named PD-001 column — never silently reusing `clearance_mm` ([§9](#9-orchestration-and-ui)) |

---

## 12. Sessions

Dependency order. **Session 0 is Shane's, and Session 1 cannot start until it is done.**

| # | Session | Done means |
| --- | --- | --- |
| **0** | **Source the mechanisms.** Obtain the five pending documents ([§7](#7-mechanism-table--placeholder)), fill the ten gap rows, and settle the values marked TBD | §7 has ≥1 sourced row per mechanism family shipping in v0.1, every row carries a clause, and `D_max` and the band boundaries have a source. **This document approved.** |
| 1 | **Rule pack and seeder.** `data/rulesets/pd_001_proximity_drip.json` and `scripts/seed_pd_001_rules.py` | Pack loads; seeder dry-runs clean; every row carries `source_text` with a clause; no mitigation catalogue entry redefined; `--apply` writes rows `list_by_ruleset("PD-001")` reads back |
| 2 | **Pair detection.** Vectorised prune + tessellated measure + XM-001 exclusion, in `proximity_drip.py` | Pair-detection tests green; `D_max = 0` yields zero pairs; measured pair-scan cost on 1540 reported against the §2 estimate |
| 3 | **Geometric classification and mechanism (a).** Above/below, gaps, orientation; galvanic drip-path with full provenance | Verdicts on the demo model; every `geometry_unavailable` a data-quality note; no verdict on two inferred materials without provenance in `details` |
| 4 | **Condensation test and mechanism (b).** Dew point, RH ladder, chemical/vapour family — only if OPEN QUESTION 2 says v0.1 | `condensation_inputs` present on every flag; no band from three defaulted inputs |
| 5 | **Orchestration, UI, export.** `MechanismSpec`, `_assess_network` branch, chip, explainer, export decision, pre-warm | Six-engine run green; consistency and BCF tests green; `prewarm_demo.py` updated for 63 combinations |
| 6 | **Demo scenarios.** The five in [§10](#10-demo-scenarios) — **only after OPEN QUESTION 7** | Five scenarios author deterministically; counts asserted; new SHA-256 recorded; RUNBOOK and showcase cross-checks updated |

Sessions 3 and 4 can run in parallel once 2 lands. Session 6 is independent of 5 but invalidates
the demo model's SHA, so it must not run during a freeze.

---

## 13. Open questions for Shane

Verbatim, in the order they block work.

1. **`D_max` — what to look for in the sources.** The repository already carries a declarative
   25 mm (`DEFAULT_CLEARANCE_MM`, `seed_galvanic_corrosion_rules.py:96`) that nothing reads and
   that MIL-STD-889B does not support. Candidates to hunt for in the five pending PDFs: a stated
   separation between dissimilar-metal services; a vertical-offset rule where services cross; a
   drip-path or drip-tray clearance; a "shall not be installed above" clause. **If none of the five
   documents gives a figure, does PD-001 ship with a qualitative transfer test and no distance
   threshold, or does it not ship?**
2. **Is the chemical/vapour family in v0.1 or v0.2?** The captured corpus supplies no citable
   passage for vapour attack (gap 2 of ten), so family (b) has no sourced row today. Shipping it in
   v0.1 means sourcing it first; deferring it makes v0.1 galvanic-drip only.
3. **May a PD-001 verdict rest on inferred materials?** On 1540 zero elements carry an IFC
   material and 4,976 carry one inferred from the system. Either PD-001 refuses to band such a pair
   (and finds nothing on any real model), or it bands and carries the provenance. Which?
4. **What happens to the 4,231 elements with no bounding box?** Half of 1540's model cannot be
   pruned, and measuring every fitting against every element is not affordable. Report them as
   `geometry_unavailable` and move on, or find another prune?
5. **Does the demo pre-warm all 63 combinations, or only the full set?** A sixth engine takes
   `2**n - 1` from 31 to 63 and roughly doubles the pre-warm.
6. **Does PD-001 get its own export column, or stay in the JSON `details`?** `clearance_mm` exists
   but belongs to SB-001 and means something different.
7. **Do the demo scenarios land before or after the defence?** Adding them changes
   `data/test_hospital_mep_demo.ifc`'s SHA-256 and invalidates the RUNBOOK and showcase
   cross-checks that currently pin 1,988 findings at 10/168/1,206/322.

---

## Appendix — what this document did not do

- Did not invent a distance, a weight or a band boundary. Every such value is **TBD (source required)**.
- Did not fill a mechanism row from general knowledge. [§7](#7-mechanism-table--placeholder) carries
  one sourced row and ten empty ones.
- Did not change anything under `app/`, `scripts/` or `tests/`.
- Did not resolve the two discrepancies it found: the ~54 s parse measured here against the
  showcase's 34.0 s run, and the seeded 25 mm that no clause supports. Both are reported.
