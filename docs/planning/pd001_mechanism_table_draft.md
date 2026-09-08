# PD-001 Proximity / Drip-Path — mechanism table (first pass, sourced only)

Draft input for the seventh piping engine, **PD-001 Proximity / Drip-Path**, to be built after
the 11 Sept FMP freeze. Source corpus and its gaps: [pd001_sources.md](../scraped_standards/pd001_sources.md).

**Provenance rule applied to this file.** Every row below is supported by a passage in one of the
`docs/scraped_standards/corrosion_pd001_*.md` files, cited by file and line range. Nothing here
comes from the author's own knowledge, from the existing GC/CC/MC/MM/XM rulesets, or from
`docs/bimguard_corrosion_rules.md`. Mechanisms believed to be missing are listed by name only,
with no data, under [Suspected gaps](#suspected-gaps-not-sourced).

**What the corpus actually yielded.** Ten files were saved; one of them
(`corrosion_pd001_aga_contact_other_metals.md`, the American Galvanizers Association page on
galvanized steel in contact with other metals) carries all of the dissimilar-metal mechanism text.
Three more carry expansion data only. The remaining six carry no citable mechanism passage —
see the MISMATCH log in the manifest. That single-source concentration is a finding about the
capture, not a judgement about the mechanisms.

## Mechanism table

| # | mechanism | source_material (the pipe that causes it) | affected_material | transfer_path | environment_condition | orientation_or_separation_rule (verbatim) | source_file | line_range | primary_standard_named_in_text |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Dissolved copper carried in run-off water from an upstream copper or brass surface causes rapid corrosion of zinc on a galvanized surface it lands on: "Even runoff water from copper or brass surfaces can contain enough dissolved copper to cause rapid corrosion." | Copper or brass | Hot-dip galvanized (zinc-coated) steel | run-off | "in a moist or humid environment" | "The design should ensure water is not recirculated and water flows from the galvanized surface towards the copper or brass surface and not the reverse." | `corrosion_pd001_aga_contact_other_metals.md` | 38 | none — secondary source |
| 2 | Direct contact between galvanized material and copper or brass forms a bimetallic couple: "If an installation requires contact between galvanized materials and copper or brass in a moist or humid environment, rapid corrosion of the zinc may occur." | Copper or brass | Hot-dip galvanized (zinc-coated) steel | support contact (direct metal-to-metal contact) | "in a moist or humid environment" | "The design should ensure water is not recirculated and water flows from the galvanized surface towards the copper or brass surface and not the reverse." | `corrosion_pd001_aga_contact_other_metals.md` | 38 | none — secondary source |
| 3 | Cathode-to-anode area ratio governs penetration rate at the anode, independent of total current: "The rate of penetration from corrosion increases as the ratio of the cathode to anode surface area increases." Stated generally for any bimetallic assembly. | Any metal cathodic to zinc in the galvanic series | Zinc / hot-dip galvanized steel (the anode) | support contact (direct metal-to-metal contact) | Not stated for this passage | qualitative — no figure in source | `corrosion_pd001_aga_contact_other_metals.md` | 24–30 | none — secondary source |
| 4 | Contact between a galvanized surface and aluminium: "unlikely to cause substantial incremental corrosion" in mild-to-moderate conditions, but may need electrical isolation in severe ones. | Aluminium | Hot-dip galvanized (zinc-coated) steel | support contact (direct metal-to-metal contact) | "under very humid conditions or corrosive environments (including atmospheres close to bodies of salt water)"; benign in "mild-to-moderately corrosive environments and/or mild-to-moderate humidity" | qualitative — no figure in source | `corrosion_pd001_aga_contact_other_metals.md` | 50–52 | none — secondary source |
| 5 | Contact between a galvanized surface and stainless steel: "unlikely to cause substantial incremental corrosion" in mild-to-moderate conditions, but may need electrical isolation in severe ones. | Stainless steel | Hot-dip galvanized (zinc-coated) steel | support contact (direct metal-to-metal contact) | "under very humid conditions or corrosive environments (including atmospheres close to bodies of salt water)"; benign in "mild-to-moderately corrosive environments and/or mild-to-moderate humidity" | qualitative — no figure in source | `corrosion_pd001_aga_contact_other_metals.md` | 54–56 | none — secondary source |
| 6 | No galvanic couple between two zinc coatings; the thinner coating governs: "There is no fear of galvanic corrosion when galvanized steel is in contact with other zinc coatings... the component with the thinnest zinc coating will be the first to experience corrosion." (Negative result — a material pair PD-001 should *not* flag.) | Other zinc coating (mechanically galvanized, metallized) | Hot-dip galvanized (zinc-coated) steel | support contact (direct metal-to-metal contact) | Not stated for this passage | qualitative — no figure in source | `corrosion_pd001_aga_contact_other_metals.md` | 42–44 | none — secondary source |
| 7 | Zinc on a galvanized fastener sacrifices itself to adjacent weathering steel until the weathering steel's rust layer forms and insulates the couple: "the zinc will initially sacrifice itself until a protective layer of rust develops on the weathering steel." Time-bounded, "usually several years". | Weathering steel | Hot-dip galvanized (zinc-coated) steel, as bolts | support contact (direct metal-to-metal contact) | Not stated for this passage | qualitative — no figure in source | `corrosion_pd001_aga_contact_other_metals.md` | 58–60 | none — secondary source |
| 8 | Galvanized and black steel connected within concrete: "accelerated corrosion of zinc occurs after depassivation of the galvanized rebar in concrete". Scope note: the source describes reinforcement embedded in concrete, not piping — carried here because it is a sourced dissimilar-metal proximity case, not because it is a pipe pair. | Black (uncoated) steel reinforcement — **not a pipe** | Galvanized steel reinforcement | support contact (connected between mesh layers / embedded in concrete) | "high chloride environments (i.e. heavy road salting or marine environments)" | qualitative — no figure in source | `corrosion_pd001_aga_contact_other_metals.md` | 62–64 | none — secondary source (page carries an unresolved footnote marker "10" at this sentence) |

**Row count: 8.** Verbatim orientation/separation rule: 2 (rows 1–2, the same AGA sentence).
`qualitative — no figure in source`: 6. Rows citing a named primary standard: 0.

### Sourced passages that produced no row

Recorded so the omission is visible rather than silent.

- `corrosion_pd001_aga_contact_other_metals.md:46–48` — HDG combined with painted steel. States a
  coating preference ("It is preferable to paint both metals"), not a corrosion mechanism between
  two materials, so no row was created.

## Expansion coefficients (for gap-closure check)

Transcribed from the one scraped table that gives a coefficient per material,
`corrosion_pd001_et_expansion_coefficients.md` lines 29–42. Both unit columns of that table are
reproduced, one row per material per unit. Nothing is added, converted or interpolated.

| material | coefficient | unit | source_file | line_range |
| --- | --- | --- | --- | --- |
| Aluminum | 12.8 | 10-6 in/in oF | `corrosion_pd001_et_expansion_coefficients.md` | 33 |
| Aluminum | 23.1 | 10-6 m/m oC | `corrosion_pd001_et_expansion_coefficients.md` | 33 |
| Carbon Steel | 6.5 | 10-6 in/in oF | `corrosion_pd001_et_expansion_coefficients.md` | 34 |
| Carbon Steel | 11.7 | 10-6 m/m oC | `corrosion_pd001_et_expansion_coefficients.md` | 34 |
| Cast Iron | 5.9 | 10-6 in/in oF | `corrosion_pd001_et_expansion_coefficients.md` | 35 |
| Cast Iron | 10.6 | 10-6 m/m oC | `corrosion_pd001_et_expansion_coefficients.md` | 35 |
| Copper | 9.3 | 10-6 in/in oF | `corrosion_pd001_et_expansion_coefficients.md` | 36 |
| Copper | 16.8 | 10-6 m/m oC | `corrosion_pd001_et_expansion_coefficients.md` | 36 |
| Stainless Steel | 9.9 | 10-6 in/in oF | `corrosion_pd001_et_expansion_coefficients.md` | 37 |
| Stainless Steel | 17.8 | 10-6 m/m oC | `corrosion_pd001_et_expansion_coefficients.md` | 37 |
| ABS Acrylonitrile butadiene styrene | 35.0 | 10-6 in/in oF | `corrosion_pd001_et_expansion_coefficients.md` | 38 |
| ABS Acrylonitrile butadiene styrene | 63.0 | 10-6 m/m oC | `corrosion_pd001_et_expansion_coefficients.md` | 38 |
| HDPE High density polyethylene | 67.0 | 10-6 in/in oF | `corrosion_pd001_et_expansion_coefficients.md` | 39 |
| HDPE High density polyethylene | 120.0 | 10-6 m/m oC | `corrosion_pd001_et_expansion_coefficients.md` | 39 |
| PE Polyethylene | 83.0 | 10-6 in/in oF | `corrosion_pd001_et_expansion_coefficients.md` | 40 |
| PE Polyethylene | 150.0 | 10-6 m/m oC | `corrosion_pd001_et_expansion_coefficients.md` | 40 |
| CPVC Chlorinated polyvinyl chloride | 44.0 | 10-6 in/in oF | `corrosion_pd001_et_expansion_coefficients.md` | 41 |
| CPVC Chlorinated polyvinyl chloride | 79.0 | 10-6 m/m oC | `corrosion_pd001_et_expansion_coefficients.md` | 41 |
| PVC Polyvinyl chloride | 28.0 | 10-6 in/in oF | `corrosion_pd001_et_expansion_coefficients.md` | 42 |
| PVC Polyvinyl chloride | 50.4 | 10-6 m/m oC | `corrosion_pd001_et_expansion_coefficients.md` | 42 |

**Row count: 20** (10 materials × 2 unit systems).

Two further scraped expansion tables were *not* transcribed here, because neither states a single
coefficient per material and reshaping them would mean adding a judgement the source does not make:

- `corrosion_pd001_et_expansion_formula.md:45–53` — mean expansion coefficients for Alloy Steel
  (1% Cr, 1/2% Mo), Mild Steel (0.1–0.2% C) and Stainless Steel (18% Cr, 8% Ni), each given as a
  row of values across eight temperature ranges from −32 oF to 32–1300 oF.
- `corrosion_pd001_et_expansion_by_material.md:29–58` — linear expansion in in/100 ft against
  temperature change for Copper, Stainless Steel, Carbon Steel, Ductile Iron and Aluminum. This is
  tabulated expansion, not a coefficient.

The expansion formula the coefficients feed, verbatim from
`corrosion_pd001_et_expansion_formula.md:29–39`: *dl = α Lo dt*, where *dl* = expansion, *Lo* =
length of pipe, *dt* = temperature difference, *α* = linear expansion coefficient.

## Suspected gaps (not sourced)

Mechanisms named in the PD-001 brief, or implied by it, for which the captured corpus supplies no
citable passage. One line each, no data — these are questions for the source hunt, not rows.

- Condensation drip from a cold pipe onto a dissimilar pipe or support beneath it.
- Vapour-phase attack on a pipe from a nearby pipe's emissions or leakage.
- Shared or continuous insulation as a transfer path between adjacent dissimilar services.
- Corrosion under insulation where wetting arrives from an adjacent pipe rather than from outside.
- Any numeric separation, clearance or vertical-offset distance between dissimilar-metal services.
- Any rule on which service must be routed above the other where drip paths cross.
- Shared-support / hanger material mismatch treated separately from pipe-to-pipe contact.
- Dezincification of copper-alloy fittings (named on the G12 landing page, no mechanism text).
- Stress-corrosion cracking of 316 stainless from an adjacent chloride source.
- Whether an expansion-driven movement can close a designed separation and create contact.
