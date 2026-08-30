# Q01: What is Piping Corrosion Analysis and why do I need it?

## The Question

> "We are on a 240-bed hospital in Hamburg. The MEP subcontractor has issued the
> services model for coordination, and our client's asset team has started
> asking about a 30-year maintenance liability on the domestic water and heating
> distribution. Somebody mentioned BIMGUARD does corrosion analysis on an IFC.
> What does that actually mean? We have not built anything yet — there is no
> pipe to inspect."

## The Answer

That is exactly the point at which the analysis is worth running. Corrosion is
not something that begins on site; it is designed in. The moment a modeller
draws a copper branch onto a galvanised steel riser, or routes a 22 mm dead leg
to a shower that will be used twice a year, the failure mode is already in the
model. BIMGUARD's Piping Corrosion analysis reads the IFC, extracts the piping
network — materials, media, diameters, joint types, operating temperatures, zone
classifications, and the connectivity graph between elements — and scores each
element and each junction against the corrosion mechanisms that published
standards say will attack it. It is a design-stage review of a maintenance-stage
liability.

Five engines run. Three of them assess **individual elements**. **GC-001**
(galvanic) scores the driving voltage between two materials in contact, weighted
by anode-to-cathode area ratio and electrolyte severity. **CC-001** (crevice)
scores the geometry that traps stagnant electrolyte — flanges, gaskets, threaded
joints, lap joints — against the critical crevice temperature of the alloy
specified. **MC-001** (microbially influenced) scores flow velocity, operating
temperature, dead-leg length and material susceptibility against the Legionella
and biofilm control regime in CIBSE TM13 and HSE HSG274. The other two assess
the **network as a whole**. **MM-001** (material-media) scores how aggressively
the medium a run carries attacks the material carrying it, modified by
environment and operating temperature. **XM-001** (cross-material) walks the
connectivity graph looking for dissimilar-metal couples that GC-001 cannot see,
because they are two separate elements joined by a fitting rather than one
element with a declared material pairing.

Each engine produces a normalised 0.0–1.0 composite score from published
weightings, bands it Critical / High / Medium / Low, and attaches the standard
and clause the threshold came from. Elements the engines cannot score do not
disappear — they raise a `data_quality` finding instead, because "we have not
assessed this" and "this is compliant" are different claims and the report keeps
them apart. On a hospital that distinction matters: an unassessed run in a
plantroom is a coordination action, not a clean bill of health.

## When This Analysis Applies

- **Healthcare and life sciences.** Domestic hot and cold water, medical gases,
  chilled water. Legionella control is a statutory duty, and MC-001 is written
  against the same guidance the estates team will be audited on.
- **Marine, coastal and offshore-adjacent projects.** The `T4_marine` and
  `T3_chloride` environment classes materially change every threshold. A detail
  that is benign inland is a Critical finding 400 m from a splash zone.
- **Industrial and process buildings.** Mixed-metal plant, aggressive media, high
  operating temperature. MM-001 and XM-001 carry most of the weight here.
- **Refurbishment and system extension.** New copper tied into existing
  galvanised or black steel is the single most common way a working system is
  given a five-year life. XM-001 exists for exactly this case.
- **Any project with a long-horizon asset or FM handover obligation**, where the
  client — not the contractor — carries the 25-year replacement cost.

## What the Report Contains

Findings come back as one flat list regardless of which engine raised them, so
nothing downstream needs to know about mechanisms:

| Field | Meaning |
| --- | --- |
| `rule_id` | e.g. `GC-001.01`, `XM-001.01`, `MM-001.DATA` |
| `element_id` | IFC `GlobalId` — resolves directly in any viewer |
| `band` | `critical` / `high` / `medium` / `low` |
| `score` | Normalised composite, 0.0–1.0 |
| `mechanism` | Engine label, or `data_quality` for an unassessed element |
| `citations` | Standard + clause + the reason that clause applies |
| `mitigation` | The engineering action, not a restatement of the problem |

Risk bands are aligned so that Critical means the same thing whichever engine
raised it. GC-001, MM-001 and XM-001 band at 0.35 / 0.65 / 0.85; CC-001 at
0.30 / 0.55 / 0.80; MC-001 at 0.25 / 0.50 / 0.75 — the tighter MIC bands reflect
that a Legionella exposure is a health outcome, not a maintenance cost.

Standards cited across the five engines include NASA-STD-6012 (galvanic voltage
compatibility thresholds by environment class), ASTM G48 and CIRIA C692
(critical crevice temperature data for stainless grades), EN ISO 15329 (wetting
classes T0–T5), EN 1993-1-4 (structural stainless), BS 8539 (bi-metallic
assemblies and dielectric separation), CIBSE TM13 and HSE HSG274 (Legionella
control), BS 8552 (water sampling and monitoring), EN ISO 9308-1 (microbiological
water quality), EN 12952-12 (feedwater quality) and ASTM B117 (salt spray).

Mitigations are catalogued rather than generated per finding. A galvanic couple
returns `MIT-GC-001` — install dielectric isolation at every contact point
between dissimilar metals. A crevice finding returns `MIT-CC-001` — specify a
non-metallic isolation gasket and positive drainage. The wording is fixed so a
subcontractor pricing forty findings prices one remedy, not forty paraphrases.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "Extract, with clause references, every quantitative threshold governing
> dissimilar-metal contact in building services pipework from BS 8539,
> EN ISO 12944, ASTM G48, NASA-STD-6012 and CIRIA C692. For each threshold
> report: (a) the permitted potential difference in volts, (b) the environment or
> exposure class it is conditioned on, (c) the anode-to-cathode area ratio caveat
> if the standard states one, and (d) the exact clause number. Where two
> standards give different values for the same condition, tabulate both side by
> side and state which is more conservative. Do not reconcile them."

**Purpose.** Produce a reviewable table of sourced thresholds that a corrosion
engineer converts into `parameters.compatibility_matrix` entries in a rule pack,
each carrying its own `cite` and `conf` field.

**Not for.** Asking NotebookLM whether a specific junction in your model
complies. It cannot see the model, it does not run the engines, and its answer
would carry no citation chain. Compliance verdicts come from the engines; the
engines take their numbers from packs a named reviewer has signed.

## Export Options

- **BCF 2.1** — `bcf.version`, `project.bcfp`, and one `{guid}/markup.bcf` plus
  `viewpoint.bcfv` and `snapshot.png` per finding. Opens in Solibri, BIMcollab,
  Navisworks, Revit (via a BCF add-in) and ARCHICAD.
- **CSV** — fixed column order, one row per finding, citations joined into a
  single cell. For commercial tracking and subcontractor issue lists.
- **JSON** — the full `AnalysisResult` including `issue_stats` and metadata, for
  dashboards and data pipelines.

## Next Steps for Your Project

1. Filter to Critical and High and send those to the MEP designer first. Medium
   and Low are a specification conversation, not a redesign.
2. Route `data_quality` findings to the **modeller**, not the engineer. They are
   almost always a missing material name, an absent `PredefinedType`, or a
   missing operating-temperature parameter, and fixing them converts silence into
   a verdict on the next run.
3. Export BCF and issue it as a coordination package. Assign galvanic and
   cross-material findings to the mechanical designer; assign MIC findings to
   whoever owns the water safety plan — on a hospital that is usually the estates
   or authorising engineer, not the contractor.
4. Re-run after the model is revised. The result cache is keyed on the model's
   SHA-256, so a genuinely changed model always recomputes.
