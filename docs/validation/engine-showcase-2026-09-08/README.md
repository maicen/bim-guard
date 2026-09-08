# What each engine finds on real IFC models

**2026-09-08.** Every engine run on its own, then all five piping engines
together, then the seismic engine on a federated pair. Thirty-one runs over five
models. Everything here was produced offline by calling the analysis code
directly — no demo server was contacted and nothing was uploaded.

## The short version

On this corpus of 34 real IFC models, **the corrosion engines cannot assess real
pipework, because no real pipework model in the corpus records what material its
pipes are made of.** West Riverside's plumbing model — 8,539 pipe segments and
fittings — produced **29,181 findings and not one verdict**. All of it is the
engines saying "I was not given enough to judge this."

The models that *do* carry materials are architectural. Their materials belong to
curtain-wall mullions and glazing panels, not pipes. So every corrosion verdict
in this report that came from a real model was scored against a window frame.

That is the finding. The numbers below are not adjusted to soften it.

---

## What was run

| Model | Why it is here | Elements | Material coverage |
| --- | --- | ---: | ---: |
| `west_riverside_hospital_str_ifc4.ifc` | Highest material coverage in the corpus | 5 | 100.0% |
| `west_riverside_hospital_arc_ifc4.ifc` | 2nd highest material coverage | 9,333 | 71.0% |
| `Clinic_Architectural.ifc` | 3rd highest material coverage | 808 | 64.6% |
| `west_riverside_hospital_plumb_ifc4.ifc` | The model project **1540** uses | 8,539 | **0.0%** |
| `data/test_hospital_mep_demo.ifc` | Synthetic control (SHA-256 verified) | 420 | 90.0% |
| `plumb_ifc4` + `str_ifc4` | The federated pair project **1542** uses | — | — |

Selection rule, applied exactly as specified: the three real models with the
highest material coverage (ties broken by element count), plus 1540's model,
plus the synthetic control. **The rule selects no piping model.** The full
ranking of all 34 files is in `01_inventory.md`.

### What the parser actually accepted

This is why the three "best" models are architectural:

| Model | Accepted element types |
| --- | --- |
| `west_riverside_hospital_arc_ifc4` | 7,122 `IfcMember`, 2,211 `IfcPlate` — **no pipes** |
| `Clinic_Architectural` | 534 `IfcMember`, 172 `IfcPlate`, 102 `IfcDistributionElement` |
| `west_riverside_hospital_str_ifc4` | 5 `IfcMember` |
| `west_riverside_hospital_plumb_ifc4` | 4,308 `IfcPipeSegment`, 4,231 `IfcPipeFitting` — **all pipes, no materials** |

The parser accepts curtain-wall members and plates as service elements, so the
corrosion engines score them. Reported, not repaired.

### What each engine looks for

- **GC-001 — galvanic corrosion.** Two different metals in contact in a wet
  environment: the less noble one corrodes. It compares the pair's potential gap
  against a threshold for the environment (NASA-STD-6012) and weighs the
  anode/cathode area ratio. Ruleset `BIMGUARD-GC-001 v1.0.0`.
- **CC-001 — crevice corrosion.** Tight gaps — flanges, lap joints, compression
  fittings — where stagnant liquid attacks a stainless grade beyond its critical
  crevice temperature. Standards: EN ISO 15329:2007, ASTM G48 Method B, CIRIA
  C692, IMOA Design Manual 4th Ed. (`app/engines/bimguard_crevice_engine.py:1-13`).
  Ruleset `BIMGUARD-CC-001 v1.0.0`.
- **MC-001 — microbiologically influenced corrosion.** Bacteria in water systems,
  driven by flow velocity, dead-leg length and operating temperature; the
  Legionella danger band sits at 25–45 °C. Standards: CIBSE TM13:2013, HSE
  HSG274, BS 8552:2012, ASTM G-187
  (`app/engines/bimguard_mic_engine.py:1-13`). Ruleset `BIMGUARD-MC-001 v1.0.0`.
- **MM-001 — material–media compatibility.** Whether the material of a run suits
  the fluid it carries (`phase_6c_corrosion_ui.py:153`). Runs over the network,
  not element by element.
- **XM-001 — cross-material compatibility.** Whether two materials joined along a
  connected run are compatible with each other
  (`phase_6c_corrosion_ui.py:154`). Also a network check.
- **SB-001 — seismic bracing clearance (Blue Halo).** Generates a clearance
  envelope around each braced element and reports anything intruding into it,
  reading real geometry rather than assuming it
  (`app/modules/phase_6/phase_6d_seismic.py:1-27`).

---

## Results

`include_low=True` on every corrosion run, so Low-band verdicts are counted
rather than suppressed.

| Model | Engine set | Elements | Findings | Verdicts | Data-quality | Critical | High | Medium | Low | Seconds |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `test_hospital_mep_demo` | GC-001 | 420 | 420 | 378 | 42 | 0 | 0 | 56 | 322 | 4.3 |
| `test_hospital_mep_demo` | CC-001 | 420 | 420 | 378 | 42 | 0 | 70 | 308 | 0 | 0.7 |
| `test_hospital_mep_demo` | MC-001 | 420 | 420 | 294 | 126 | 10 | 64 | 220 | 0 | 0.7 |
| `test_hospital_mep_demo` | MM-001 | 420 | 182 | 146 | 36 | 0 | 0 | 146 | 0 | 0.7 |
| `test_hospital_mep_demo` | XM-001 | 420 | 546 | 510 | 36 | 0 | 34 | 476 | 0 | 0.7 |
| `test_hospital_mep_demo` | ALL5 | 420 | 1,988 | 1,706 | 282 | 10 | 168 | 1,206 | 322 | 0.8 |
| `west_riverside_hospital_plumb_ifc4` | GC-001 | 8,539 | 8,539 | 0 | 8,539 | 0 | 0 | 0 | 0 | 22.7 |
| `west_riverside_hospital_plumb_ifc4` | CC-001 | 8,539 | 8,539 | 0 | 8,539 | 0 | 0 | 0 | 0 | 22.8 |
| `west_riverside_hospital_plumb_ifc4` | MC-001 | 8,539 | 8,539 | 0 | 8,539 | 0 | 0 | 0 | 0 | 24.6 |
| `west_riverside_hospital_plumb_ifc4` | MM-001 | 8,539 | 3,563 | 0 | 3,563 | 0 | 0 | 0 | 0 | 23.4 |
| `west_riverside_hospital_plumb_ifc4` | XM-001 | 8,539 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 34.0 |
| `west_riverside_hospital_plumb_ifc4` | ALL5 | 8,539 | 29,181 | 0 | 29,181 | 0 | 0 | 0 | 0 | 33.5 |
| `west_riverside_hospital_arc_ifc4` | GC-001 | 9,333 | 9,333 | 6,630 | 2,703 | 0 | 0 | 0 | 6,630 | 20.3 |
| `west_riverside_hospital_arc_ifc4` | CC-001 | 9,333 | 9,333 | 6,630 | 2,703 | 0 | 0 | 6,630 | 0 | 19.4 |
| `west_riverside_hospital_arc_ifc4` | MC-001 | 9,333 | 9,333 | 0 | 9,333 | 0 | 0 | 0 | 0 | 19.9 |
| `west_riverside_hospital_arc_ifc4` | MM-001 | 9,333 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 19.8 |
| `west_riverside_hospital_arc_ifc4` | XM-001 | 9,333 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 16.5 |
| `west_riverside_hospital_arc_ifc4` | ALL5 | 9,333 | 27,999 | 13,260 | 14,739 | 0 | 0 | 6,630 | 6,630 | 23.0 |
| `Clinic_Architectural` | GC-001 | 808 | 808 | 522 | 286 | 0 | 0 | 0 | 522 | 6.8 |
| `Clinic_Architectural` | CC-001 | 808 | 808 | 522 | 286 | 0 | 0 | 522 | 0 | 3.7 |
| `Clinic_Architectural` | MC-001 | 808 | 808 | 0 | 808 | 0 | 0 | 0 | 0 | 3.8 |
| `Clinic_Architectural` | MM-001 | 808 | 102 | 10 | 92 | 0 | 0 | 10 | 0 | 3.5 |
| `Clinic_Architectural` | XM-001 | 808 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3.9 |
| `Clinic_Architectural` | ALL5 | 808 | 2,526 | 1,054 | 1,472 | 0 | 0 | 532 | 522 | 7.5 |
| `west_riverside_hospital_str_ifc4` | GC-001 | 5 | 5 | 5 | 0 | 0 | 0 | 0 | 5 | 0.7 |
| `west_riverside_hospital_str_ifc4` | CC-001 | 5 | 5 | 5 | 0 | 0 | 0 | 5 | 0 | 0.8 |
| `west_riverside_hospital_str_ifc4` | MC-001 | 5 | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 0.6 |
| `west_riverside_hospital_str_ifc4` | MM-001 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.7 |
| `west_riverside_hospital_str_ifc4` | XM-001 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.7 |
| `west_riverside_hospital_str_ifc4` | ALL5 | 5 | 15 | 10 | 5 | 0 | 0 | 5 | 5 | 0.7 |
| `SEISMIC-1542-federation` | SB-001 | 2,937 | 2,937 | 2,937 | 0 | 783 | 314 | 1,840 | 0 | 198.7 |


Three cross-checks against the frozen demo, which the offline path reproduces
exactly: the synthetic control's five-engine run gives **1,988 findings, bands
10 / 168 / 1,206 / 322**; 1540's model gives **29,181, all data-quality**; the
1542 federation gives **2,937 clashes at 783 / 314 / 1,840**. All three match
`docs/demo/RUNBOOK.md`.

---

## Per engine, ten real findings

Element name and material are **joined from the parsed model**, because a
finding does not carry them — a verdict's metadata records `material_source`
(where the material came from) but neither the material value nor the element
name. See `00_entry_points.md` §4. Every other column, including the explanation,
is copied verbatim from `findings.json`.

### GC-001 — galvanic

Most verdicts on a real model: **`west_riverside_hospital_arc_ifc4`, 6,630
verdicts**, every one Low at score 0.0.

| GUID | Element name (joined) | IFC type | Material (joined) | material_source | System | Band | Score | ruleset_version | Explanation (verbatim from findings.json) |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| `0CI16guz9FqRmU7SKySHK5` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.0 | BIMGUARD-GC-001 v1.0.0 | Aluminium alloys coupled to Aluminium alloys gives a 0 V potential gap against the 0.25 V threshold for Normal heated indoor (E2_NORMAL, NASA-STD-6012); anode/cathode area ratio 0.1 bands as Unfavourable. Coup… |
| `0CI16guz9FqRmU7SKySHK6` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.0 | BIMGUARD-GC-001 v1.0.0 | Aluminium alloys coupled to Aluminium alloys gives a 0 V potential gap against the 0.25 V threshold for Normal heated indoor (E2_NORMAL, NASA-STD-6012); anode/cathode area ratio 0.1 bands as Unfavourable. Coup… |
| `0CI16guz9FqRmU7SKySHK7` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.0 | BIMGUARD-GC-001 v1.0.0 | Aluminium alloys coupled to Aluminium alloys gives a 0 V potential gap against the 0.25 V threshold for Normal heated indoor (E2_NORMAL, NASA-STD-6012); anode/cathode area ratio 0.1 bands as Unfavourable. Coup… |
| `0CI16guz9FqRmU7SKySHK8` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.0 | BIMGUARD-GC-001 v1.0.0 | Aluminium alloys coupled to Aluminium alloys gives a 0 V potential gap against the 0.25 V threshold for Normal heated indoor (E2_NORMAL, NASA-STD-6012); anode/cathode area ratio 0.1 bands as Unfavourable. Coup… |
| `0CI16guz9FqRmU7SKySHK9` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.0 | BIMGUARD-GC-001 v1.0.0 | Aluminium alloys coupled to Aluminium alloys gives a 0 V potential gap against the 0.25 V threshold for Normal heated indoor (E2_NORMAL, NASA-STD-6012); anode/cathode area ratio 0.1 bands as Unfavourable. Coup… |
| `0CI16guz9FqRmU7SKySHPJ` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.0 | BIMGUARD-GC-001 v1.0.0 | Aluminium alloys coupled to Aluminium alloys gives a 0 V potential gap against the 0.25 V threshold for Normal heated indoor (E2_NORMAL, NASA-STD-6012); anode/cathode area ratio 0.1 bands as Unfavourable. Coup… |
| `0CI16guz9FqRmU7SKySHPK` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.0 | BIMGUARD-GC-001 v1.0.0 | Aluminium alloys coupled to Aluminium alloys gives a 0 V potential gap against the 0.25 V threshold for Normal heated indoor (E2_NORMAL, NASA-STD-6012); anode/cathode area ratio 0.1 bands as Unfavourable. Coup… |
| `0CI16guz9FqRmU7SKySHPL` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.0 | BIMGUARD-GC-001 v1.0.0 | Aluminium alloys coupled to Aluminium alloys gives a 0 V potential gap against the 0.25 V threshold for Normal heated indoor (E2_NORMAL, NASA-STD-6012); anode/cathode area ratio 0.1 bands as Unfavourable. Coup… |
| `0CI16guz9FqRmU7SKySHPM` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.0 | BIMGUARD-GC-001 v1.0.0 | Aluminium alloys coupled to Aluminium alloys gives a 0 V potential gap against the 0.25 V threshold for Normal heated indoor (E2_NORMAL, NASA-STD-6012); anode/cathode area ratio 0.1 bands as Unfavourable. Coup… |
| `0CI16guz9FqRmU7SKySHQ5` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.0 | BIMGUARD-GC-001 v1.0.0 | Aluminium alloys coupled to Aluminium alloys gives a 0 V potential gap against the 0.25 V threshold for Normal heated indoor (E2_NORMAL, NASA-STD-6012); anode/cathode area ratio 0.1 bands as Unfavourable. Coup… |


Read what this says: these are curtain-wall glazing mullions. GC-001 is scoring
aluminium against aluminium — a self-couple with a 0 V potential gap — and
banding it Low. It is behaving correctly on input that is not pipework.

### CC-001 — crevice

Most verdicts on a real model: **`west_riverside_hospital_arc_ifc4`, 6,630
verdicts**, every one Medium at score 0.37.

| GUID | Element name (joined) | IFC type | Material (joined) | material_source | System | Band | Score | ruleset_version | Explanation (verbatim from findings.json) |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| `0CI16guz9FqRmU7SKySHK5` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | medium | 0.37 | BIMGUARD-CC-001 v1.0.0 | Joint Unknown / unclassified classifies as Tight geometry (Weld neck flanges, compression fittings, lap joints — significant restriction, EN ISO 15329:2007); critical crevice temperature material grade not rec… |
| `0CI16guz9FqRmU7SKySHK6` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | medium | 0.37 | BIMGUARD-CC-001 v1.0.0 | Joint Unknown / unclassified classifies as Tight geometry (Weld neck flanges, compression fittings, lap joints — significant restriction, EN ISO 15329:2007); critical crevice temperature material grade not rec… |
| `0CI16guz9FqRmU7SKySHK7` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | medium | 0.37 | BIMGUARD-CC-001 v1.0.0 | Joint Unknown / unclassified classifies as Tight geometry (Weld neck flanges, compression fittings, lap joints — significant restriction, EN ISO 15329:2007); critical crevice temperature material grade not rec… |
| `0CI16guz9FqRmU7SKySHK8` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | medium | 0.37 | BIMGUARD-CC-001 v1.0.0 | Joint Unknown / unclassified classifies as Tight geometry (Weld neck flanges, compression fittings, lap joints — significant restriction, EN ISO 15329:2007); critical crevice temperature material grade not rec… |
| `0CI16guz9FqRmU7SKySHK9` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | medium | 0.37 | BIMGUARD-CC-001 v1.0.0 | Joint Unknown / unclassified classifies as Tight geometry (Weld neck flanges, compression fittings, lap joints — significant restriction, EN ISO 15329:2007); critical crevice temperature material grade not rec… |
| `0CI16guz9FqRmU7SKySHPJ` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | medium | 0.37 | BIMGUARD-CC-001 v1.0.0 | Joint Unknown / unclassified classifies as Tight geometry (Weld neck flanges, compression fittings, lap joints — significant restriction, EN ISO 15329:2007); critical crevice temperature material grade not rec… |
| `0CI16guz9FqRmU7SKySHPK` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | medium | 0.37 | BIMGUARD-CC-001 v1.0.0 | Joint Unknown / unclassified classifies as Tight geometry (Weld neck flanges, compression fittings, lap joints — significant restriction, EN ISO 15329:2007); critical crevice temperature material grade not rec… |
| `0CI16guz9FqRmU7SKySHPL` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | medium | 0.37 | BIMGUARD-CC-001 v1.0.0 | Joint Unknown / unclassified classifies as Tight geometry (Weld neck flanges, compression fittings, lap joints — significant restriction, EN ISO 15329:2007); critical crevice temperature material grade not rec… |
| `0CI16guz9FqRmU7SKySHPM` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | medium | 0.37 | BIMGUARD-CC-001 v1.0.0 | Joint Unknown / unclassified classifies as Tight geometry (Weld neck flanges, compression fittings, lap joints — significant restriction, EN ISO 15329:2007); critical crevice temperature material grade not rec… |
| `0CI16guz9FqRmU7SKySHQ5` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | medium | 0.37 | BIMGUARD-CC-001 v1.0.0 | Joint Unknown / unclassified classifies as Tight geometry (Weld neck flanges, compression fittings, lap joints — significant restriction, EN ISO 15329:2007); critical crevice temperature material grade not rec… |


Same elements. The joint type is `Unknown / unclassified`, which CC-001 treats as
tight geometry, and the grade is unrecognised — so a Medium band on 6,630
curtain-wall members rests on two unknowns rather than on the building.

### MC-001 — microbiological

**MC-001 produced zero verdicts on every real model.** Its ten most common
data-quality notes come from the model with the most of them —
`west_riverside_hospital_arc_ifc4`, 9,333 notes:

| GUID | Element name (joined) | IFC type | Material (joined) | material_source | System | Band | Score | ruleset_version | Explanation (verbatim from findings.json) |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| `0CI16guz9FqRmU7SKySHK5` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.1 | BIMGUARD-MC-001 v1.0.0 | MC-001 did not produce a result for this element. |
| `0CI16guz9FqRmU7SKySHK6` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.1 | BIMGUARD-MC-001 v1.0.0 | MC-001 did not produce a result for this element. |
| `0CI16guz9FqRmU7SKySHK7` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.1 | BIMGUARD-MC-001 v1.0.0 | MC-001 did not produce a result for this element. |
| `0CI16guz9FqRmU7SKySHK8` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.1 | BIMGUARD-MC-001 v1.0.0 | MC-001 did not produce a result for this element. |
| `0CI16guz9FqRmU7SKySHK9` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.1 | BIMGUARD-MC-001 v1.0.0 | MC-001 did not produce a result for this element. |
| `0CI16guz9FqRmU7SKySHPJ` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.1 | BIMGUARD-MC-001 v1.0.0 | MC-001 did not produce a result for this element. |
| `0CI16guz9FqRmU7SKySHPK` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.1 | BIMGUARD-MC-001 v1.0.0 | MC-001 did not produce a result for this element. |
| `0CI16guz9FqRmU7SKySHPL` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.1 | BIMGUARD-MC-001 v1.0.0 | MC-001 did not produce a result for this element. |
| `0CI16guz9FqRmU7SKySHPM` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.1 | BIMGUARD-MC-001 v1.0.0 | MC-001 did not produce a result for this element. |
| `0CI16guz9FqRmU7SKySHQ5` | Curtain Wall:Exterior Glazing:813… | IfcMember | Aluminum_alloy_6063 | ifc_metadata | Unassigned | low | 0.1 | BIMGUARD-MC-001 v1.0.0 | MC-001 did not produce a result for this element. |


Its verdicts therefore have to come from the synthetic control, **labelled as
synthetic** — this is authored data, not found in the wild:

| GUID | Element name (joined) | IFC type | Material (joined) | material_source | System | Band | Score | ruleset_version | Explanation (verbatim from findings.json) |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| `00DXjXflHIA8cDDRFYOSGE` | COND-064 Condensate External Roof… | IfcPipeFitting | Unknown | absent | Condensate Drain | critical | 0.958 | BIMGUARD-MC-001 v1.0.0 | Flow velocity 0 m/s classifies as stagnant / dead-leg (FV0_STAGNANT, at or below the 0 m/s threshold, CIBSE TM13:2013); operating temperature 30 °C lies in the 25–45°C band (T2_DANGER, CIBSE TM13:2013 — Legion… |
| `0etgMFfPnHDgJVm_W26arx` | COND-044 Condensate External Roof… | IfcPipeFitting | Unknown | absent | Condensate Drain | critical | 0.958 | BIMGUARD-MC-001 v1.0.0 | Flow velocity 0 m/s classifies as stagnant / dead-leg (FV0_STAGNANT, at or below the 0 m/s threshold, CIBSE TM13:2013); operating temperature 30 °C lies in the 25–45°C band (T2_DANGER, CIBSE TM13:2013 — Legion… |
| `0g9DJwi2zTDgwlt7eWLEtB` | COND-024 Condensate External Roof… | IfcPipeFitting | Unknown | absent | Condensate Drain | critical | 0.958 | BIMGUARD-MC-001 v1.0.0 | Flow velocity 0 m/s classifies as stagnant / dead-leg (FV0_STAGNANT, at or below the 0 m/s threshold, CIBSE TM13:2013); operating temperature 30 °C lies in the 25–45°C band (T2_DANGER, CIBSE TM13:2013 — Legion… |
| `0hJhQ0hGbHzu6LUAvkg0Ho` | COND-012 Condensate External Roof… | IfcPipeSegment | Copper | ifc_metadata | Condensate Drain | critical | 0.777 | BIMGUARD-MC-001 v1.0.0 | Flow velocity 0 m/s classifies as stagnant / dead-leg (FV0_STAGNANT, at or below the 0 m/s threshold, CIBSE TM13:2013); operating temperature 30 °C lies in the 25–45°C band (T2_DANGER, CIBSE TM13:2013 — Legion… |
| `0i5FpphgDSJvwpsgN2Gkwm` | COND-052 Condensate External Roof… | IfcPipeSegment | SS_316_passive | ifc_metadata | Condensate Drain | critical | 0.814 | BIMGUARD-MC-001 v1.0.0 | Flow velocity 0 m/s classifies as stagnant / dead-leg (FV0_STAGNANT, at or below the 0 m/s threshold, CIBSE TM13:2013); operating temperature 30 °C lies in the 25–45°C band (T2_DANGER, CIBSE TM13:2013 — Legion… |
| `17L9yUJMzVYgaDfT19TQbF` | COND-056 Condensate External Roof… | IfcPipeSegment | HDPE | ifc_metadata_unmapped | Condensate Drain | critical | 0.814 | BIMGUARD-MC-001 v1.0.0 | Flow velocity 0 m/s classifies as stagnant / dead-leg (FV0_STAGNANT, at or below the 0 m/s threshold, CIBSE TM13:2013); operating temperature 30 °C lies in the 25–45°C band (T2_DANGER, CIBSE TM13:2013 — Legion… |
| `20KeDvTYrO59MhDS4MnkZ9` | COND-004 Condensate External Roof… | IfcPipeFitting | Unknown | absent | Condensate Drain | critical | 0.958 | BIMGUARD-MC-001 v1.0.0 | Flow velocity 0 m/s classifies as stagnant / dead-leg (FV0_STAGNANT, at or below the 0 m/s threshold, CIBSE TM13:2013); operating temperature 30 °C lies in the 25–45°C band (T2_DANGER, CIBSE TM13:2013 — Legion… |
| `3$WXMGna1KFuaRc16OfXd8` | COND-016 Condensate External Roof… | IfcPipeSegment | SS_316_passive | ifc_metadata | Condensate Drain | critical | 0.814 | BIMGUARD-MC-001 v1.0.0 | Flow velocity 0 m/s classifies as stagnant / dead-leg (FV0_STAGNANT, at or below the 0 m/s threshold, CIBSE TM13:2013); operating temperature 30 °C lies in the 25–45°C band (T2_DANGER, CIBSE TM13:2013 — Legion… |
| `32C_8cP2jGt9ZujVOrZBY0` | COND-036 Condensate External Roof… | IfcPipeSegment | Copper | ifc_metadata | Condensate Drain | critical | 0.777 | BIMGUARD-MC-001 v1.0.0 | Flow velocity 0 m/s classifies as stagnant / dead-leg (FV0_STAGNANT, at or below the 0 m/s threshold, CIBSE TM13:2013); operating temperature 30 °C lies in the 25–45°C band (T2_DANGER, CIBSE TM13:2013 — Legion… |
| `3lY2vDeLvSKeq_ZOGrvi1w` | COND-032 Condensate External Roof… | IfcPipeSegment | HDPE | ifc_metadata_unmapped | Condensate Drain | critical | 0.814 | BIMGUARD-MC-001 v1.0.0 | Flow velocity 0 m/s classifies as stagnant / dead-leg (FV0_STAGNANT, at or below the 0 m/s threshold, CIBSE TM13:2013); operating temperature 30 °C lies in the 25–45°C band (T2_DANGER, CIBSE TM13:2013 — Legion… |


### MM-001 — material–media

Most verdicts on a real model: **`Clinic_Architectural`, 10 verdicts**. That is
the entire real-model yield for this engine across the corpus.

Note the `material_source` column below before reading the bands: it says
`system_inference:fire_sprinkler`, not `ifc_metadata`. The model records the
material as `Unknown`; the `GalvanisedSteel` these verdicts are scored against
was inferred from the system name. The elements are fire extinguisher cabinets.
These ten Mediums describe an inference, not a reading.

| GUID | Element name (joined) | IFC type | Material (joined) | material_source | System | Band | Score | ruleset_version | Explanation (verbatim from findings.json) |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| `03rpEGmyXBBPmFR6GIBLiq` | M_Fire Extinguisher Cabinet:305 x… | IfcDistributionElement | Unknown | system_inference:fire_sprinkler | Unassigned | medium | 0.4 | BIMGUARD-MM-001 v1.0.0 | GalvanisedSteel carrying stagnant_water in T1_indoor_damp at 20.0 C scores 0.4 (medium). Terms: compatibility 0.7, environment 0.2, temperature 0.2. Dominant mechanism: zinc_depletion_then_substrate_pitting. |
| `0tIhQ6hmz02e5gznEed7ES` | M_Fire Extinguisher Cabinet:305 x… | IfcDistributionElement | Unknown | system_inference:fire_sprinkler | Unassigned | medium | 0.4 | BIMGUARD-MM-001 v1.0.0 | GalvanisedSteel carrying stagnant_water in T1_indoor_damp at 20.0 C scores 0.4 (medium). Terms: compatibility 0.7, environment 0.2, temperature 0.2. Dominant mechanism: zinc_depletion_then_substrate_pitting. |
| `0tIhQ6hmz02e5gznEed7H7` | M_Fire Extinguisher Cabinet:305 x… | IfcDistributionElement | Unknown | system_inference:fire_sprinkler | Unassigned | medium | 0.4 | BIMGUARD-MM-001 v1.0.0 | GalvanisedSteel carrying stagnant_water in T1_indoor_damp at 20.0 C scores 0.4 (medium). Terms: compatibility 0.7, environment 0.2, temperature 0.2. Dominant mechanism: zinc_depletion_then_substrate_pitting. |
| `0tIhQ6hmz02e5gznEed7Lo` | M_Fire Extinguisher Cabinet:305 x… | IfcDistributionElement | Unknown | system_inference:fire_sprinkler | Unassigned | medium | 0.4 | BIMGUARD-MM-001 v1.0.0 | GalvanisedSteel carrying stagnant_water in T1_indoor_damp at 20.0 C scores 0.4 (medium). Terms: compatibility 0.7, environment 0.2, temperature 0.2. Dominant mechanism: zinc_depletion_then_substrate_pitting. |
| `1CU3Pa7ALAQOW5yxokoHTD` | M_Fire Extinguisher Cabinet:305 x… | IfcDistributionElement | Unknown | system_inference:fire_sprinkler | Unassigned | medium | 0.4 | BIMGUARD-MM-001 v1.0.0 | GalvanisedSteel carrying stagnant_water in T1_indoor_damp at 20.0 C scores 0.4 (medium). Terms: compatibility 0.7, environment 0.2, temperature 0.2. Dominant mechanism: zinc_depletion_then_substrate_pitting. |
| `1WxvZRhNH0OPt6rkEt3L9V` | M_Fire Extinguisher Cabinet:305 x… | IfcDistributionElement | Unknown | system_inference:fire_sprinkler | Unassigned | medium | 0.4 | BIMGUARD-MM-001 v1.0.0 | GalvanisedSteel carrying stagnant_water in T1_indoor_damp at 20.0 C scores 0.4 (medium). Terms: compatibility 0.7, environment 0.2, temperature 0.2. Dominant mechanism: zinc_depletion_then_substrate_pitting. |
| `1uDBQ9y7vCyxXlpVEuenSy` | M_Fire Extinguisher Cabinet:305 x… | IfcDistributionElement | Unknown | system_inference:fire_sprinkler | Unassigned | medium | 0.4 | BIMGUARD-MM-001 v1.0.0 | GalvanisedSteel carrying stagnant_water in T1_indoor_damp at 20.0 C scores 0.4 (medium). Terms: compatibility 0.7, environment 0.2, temperature 0.2. Dominant mechanism: zinc_depletion_then_substrate_pitting. |
| `25QVeOxmX9DQEpjA0wx7Nd` | M_Fire Extinguisher Cabinet:305 x… | IfcDistributionElement | Unknown | system_inference:fire_sprinkler | Unassigned | medium | 0.4 | BIMGUARD-MM-001 v1.0.0 | GalvanisedSteel carrying stagnant_water in T1_indoor_damp at 20.0 C scores 0.4 (medium). Terms: compatibility 0.7, environment 0.2, temperature 0.2. Dominant mechanism: zinc_depletion_then_substrate_pitting. |
| `2d8HbdSu9Fr9Na0iagzMUE` | M_Fire Extinguisher Cabinet:305 x… | IfcDistributionElement | Unknown | system_inference:fire_sprinkler | Unassigned | medium | 0.4 | BIMGUARD-MM-001 v1.0.0 | GalvanisedSteel carrying stagnant_water in T1_indoor_damp at 20.0 C scores 0.4 (medium). Terms: compatibility 0.7, environment 0.2, temperature 0.2. Dominant mechanism: zinc_depletion_then_substrate_pitting. |
| `2d8HbdSu9Fr9Na0iagzNhh` | M_Fire Extinguisher Cabinet:305 x… | IfcDistributionElement | Unknown | system_inference:fire_sprinkler | Unassigned | medium | 0.4 | BIMGUARD-MM-001 v1.0.0 | GalvanisedSteel carrying stagnant_water in T1_indoor_damp at 20.0 C scores 0.4 (medium). Terms: compatibility 0.7, environment 0.2, temperature 0.2. Dominant mechanism: zinc_depletion_then_substrate_pitting. |


### XM-001 — cross-material

**XM-001 produced zero verdicts on every real model**, and on four of the five it
produced no findings at all. Its only real-model output is a single data-quality
note on 1540's plumbing model:

| GUID | Element name (joined) | IFC type | Material (joined) | material_source | System | Band | Score | ruleset_version | Explanation (verbatim from findings.json) |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| `0St58in6H1V81MuS6hDkEp` | M_Transition - Generic:Standard:7… | IfcPipeFitting | Unknown | absent | Sanitary 4 | low | 0.0 | BIMGUARD-XM-001 v1.0.0 | 'Unknown' has no entry in the galvanic series, so no potential gap can be computed. An unlisted material is unassessed, not benign. |


Its verdicts, again from the synthetic control and **labelled as synthetic**:

| GUID | Element name (joined) | IFC type | Material (joined) | material_source | System | Band | Score | ruleset_version | Explanation (verbatim from findings.json) |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| `03fauwKnzIqxVoOKxk989D` | DCW-011 Cold Water Ceiling Void D… | IfcPipeSegment | Galvanized_steel | — | Domestic Cold Water | high | 0.71 | BIMGUARD-XM-001 v1.0.0 | GalvanisedSteel (03fauwKnzIqxVoOKxk989D) sacrifices to SS316 (1N1xy0JarMohOLAEmV5o7v) across a 0.740 V gap in T1_indoor_damp, direct contact. Composite 0.71 (high) from voltage 0.740, separation 1.0, environme… |
| `07yzQd8FfUDQ3nFbxdyHCt` | DCW-055 Cold Water Ceiling Void D… | IfcValve | Galvanized_steel | — | Domestic Cold Water | high | 0.71 | BIMGUARD-XM-001 v1.0.0 | GalvanisedSteel (07yzQd8FfUDQ3nFbxdyHCt) sacrifices to SS316 (2DHGyclBnRc9$qSdcxzCCt) across a 0.740 V gap in T1_indoor_damp, direct contact. Composite 0.71 (high) from voltage 0.740, separation 1.0, environme… |
| `0Fo8OPbR9GuvPyC9MTNd0y` | FIRE-013 Fire Plant Room DN28 | IfcPipeSegment | Galvanized_steel | — | Fire Main | high | 0.71 | BIMGUARD-XM-001 v1.0.0 | GalvanisedSteel (0Fo8OPbR9GuvPyC9MTNd0y) sacrifices to SS316 (1V2$KWaVzJ3Pl0zleJn$nH) across a 0.740 V gap in T1_indoor_damp, direct contact. Composite 0.71 (high) from voltage 0.740, separation 1.0, environme… |
| `0HVPKbCLrHOecYeTjl2T_3` | DCW-035 Cold Water Ceiling Void D… | IfcValve | Galvanized_steel | — | Domestic Cold Water | high | 0.71 | BIMGUARD-XM-001 v1.0.0 | GalvanisedSteel (0HVPKbCLrHOecYeTjl2T_3) sacrifices to SS316 (3oKnw9SvrH7A2IE8HOi0rf) across a 0.740 V gap in T1_indoor_damp, direct contact. Composite 0.71 (high) from voltage 0.740, separation 1.0, environme… |
| `0RkRkFmCjNX9Gb5cOFf3xb` | FIRE-059 Fire Ceiling Void DN54 | IfcPipeFitting | Galvanized_steel | — | Fire Main | high | 0.71 | BIMGUARD-XM-001 v1.0.0 | GalvanisedSteel (0RkRkFmCjNX9Gb5cOFf3xb) sacrifices to SS316 (0uDXmO6qbKqhegCW7Pb$op) across a 0.740 V gap in T1_indoor_damp, direct contact. Composite 0.71 (high) from voltage 0.740, separation 1.0, environme… |
| `0VzBV33ADU8BTaiGwNT7lw` | FIRE-007 Fire Ceiling Void DN22 | IfcPipeSegment | Galvanized_steel | — | Fire Main | high | 0.71 | BIMGUARD-XM-001 v1.0.0 | GalvanisedSteel (0VzBV33ADU8BTaiGwNT7lw) sacrifices to SS316 (0N4g85JWDRRgWo9_HQPP3D) across a 0.740 V gap in T1_indoor_damp, direct contact. Composite 0.71 (high) from voltage 0.740, separation 1.0, environme… |
| `0cuZ_9wdnRTwtOxK$md9U2` | DCW-019 Cold Water Ceiling Void D… | IfcPipeFitting | Galvanized_steel | — | Domestic Cold Water | high | 0.71 | BIMGUARD-XM-001 v1.0.0 | GalvanisedSteel (0cuZ_9wdnRTwtOxK$md9U2) sacrifices to SS316 (1_aRfRjY5HzhjUnK5Hn4Wk) across a 0.740 V gap in T1_indoor_damp, direct contact. Composite 0.71 (high) from voltage 0.740, separation 1.0, environme… |
| `0gERYjJCvJ2wiH8pE_oUd5` | FIRE-049 Fire Plant Room DN54 | IfcPipeFitting | Galvanized_steel | — | Fire Main | high | 0.71 | BIMGUARD-XM-001 v1.0.0 | GalvanisedSteel (0gERYjJCvJ2wiH8pE_oUd5) sacrifices to SS316 (1yIoMuNifKSOJ7W7rENs7E) across a 0.740 V gap in T1_indoor_damp, direct contact. Composite 0.71 (high) from voltage 0.740, separation 1.0, environme… |
| `0ndqWSSpfVAPOKMvUWt05R` | FIRE-025 Fire Plant Room DN108 | IfcValve | Galvanized_steel | — | Fire Main | high | 0.71 | BIMGUARD-XM-001 v1.0.0 | GalvanisedSteel (0ndqWSSpfVAPOKMvUWt05R) sacrifices to SS316 (11W6R7zvPVkQqjqlgrNi$c) across a 0.740 V gap in T1_indoor_damp, direct contact. Composite 0.71 (high) from voltage 0.740, separation 1.0, environme… |
| `0nw3D0vovSxwKpLVGI3bnh` | FIRE-067 Fire Ceiling Void DN22 | IfcPipeSegment | Galvanized_steel | — | Fire Main | high | 0.71 | BIMGUARD-XM-001 v1.0.0 | GalvanisedSteel (0nw3D0vovSxwKpLVGI3bnh) sacrifices to SS316 (3eFsg8a55TJvD5w76myduK) across a 0.740 V gap in T1_indoor_damp, direct contact. Composite 0.71 (high) from voltage 0.740, separation 1.0, environme… |


### SB-001 — seismic bracing clearance

The one engine that worked fully on real models, because it needs geometry rather
than materials: **2,937 verdicts on the 1542 federation, 783 Critical / 314 High
/ 1,840 Medium, zero data-quality notes.**

| GUID | Element name (joined) | IFC type | Material (joined) | material_source | System | Band | Score | ruleset_version | Explanation (verbatim from findings.json) |
| --- | --- | --- | --- | --- | --- | --- | ---: | --- | --- |
| `0Goyr0Pan6wgTPUTJZT10H` | — | — | — | — | — | critical | 0.9 | BIMGUARD-SB-001 v1.0.0 | IfcBeam (3W4UPvPfv6vOSdYhV7_PW$) intrudes into the seismic bracing clearance halo of IfcPipeSegment (0Goyr0Pan6wgTPUTJZT10H) by 131,822,371 mm^3 (100.0% of the halo volume). |
| `0Goyr0Pan6wgTPUTJZT10H` | — | — | — | — | — | critical | 0.9 | BIMGUARD-SB-001 v1.0.0 | IfcBeam (3W4UPvPfv6vOSdYhV7_PWH) intrudes into the seismic bracing clearance halo of IfcPipeSegment (0Goyr0Pan6wgTPUTJZT10H) by 112,590,182 mm^3 (85.4% of the halo volume). |
| `0Goyr0Pan6wgTPUTJZT11I` | — | — | — | — | — | critical | 0.9 | BIMGUARD-SB-001 v1.0.0 | IfcBuildingElementProxy (0Goyr0Pan6wgTPUTJZT10$) intrudes into the seismic bracing clearance halo of IfcPipeSegment (0Goyr0Pan6wgTPUTJZT11I) by 48,624,033 mm^3 (53.5% of the halo volume). |
| `0Goyr0Pan6wgTPUTJZT11I` | — | — | — | — | — | critical | 0.9 | BIMGUARD-SB-001 v1.0.0 | IfcBeam (3W4UPvPfv6vOSdYhV7_PW$) intrudes into the seismic bracing clearance halo of IfcPipeSegment (0Goyr0Pan6wgTPUTJZT11I) by 90,874,000 mm^3 (100.0% of the halo volume). |
| `0Goyr0Pan6wgTPUTJZT11I` | — | — | — | — | — | critical | 0.9 | BIMGUARD-SB-001 v1.0.0 | IfcBeam (3W4UPvPfv6vOSdYhV7_PWH) intrudes into the seismic bracing clearance halo of IfcPipeSegment (0Goyr0Pan6wgTPUTJZT11I) by 90,874,000 mm^3 (100.0% of the halo volume). |
| `0Goyr0Pan6wgTPUTJZT11L` | — | — | — | — | — | critical | 0.9 | BIMGUARD-SB-001 v1.0.0 | IfcBeam (3W4UPvPfv6vOSdYhV7_PW$) intrudes into the seismic bracing clearance halo of IfcPipeSegment (0Goyr0Pan6wgTPUTJZT11L) by 125,097,633 mm^3 (100.0% of the halo volume). |
| `0Goyr0Pan6wgTPUTJZT11L` | — | — | — | — | — | critical | 0.9 | BIMGUARD-SB-001 v1.0.0 | IfcBeam (3W4UPvPfv6vOSdYhV7_PWH) intrudes into the seismic bracing clearance halo of IfcPipeSegment (0Goyr0Pan6wgTPUTJZT11L) by 125,097,633 mm^3 (100.0% of the halo volume). |
| `0Goyr0Pan6wgTPUTJZT11N` | — | — | — | — | — | critical | 0.9 | BIMGUARD-SB-001 v1.0.0 | IfcBeam (3W4UPvPfv6vOSdYhV7_PW$) intrudes into the seismic bracing clearance halo of IfcPipeSegment (0Goyr0Pan6wgTPUTJZT11N) by 36,680,891 mm^3 (35.6% of the halo volume). |
| `0Goyr0Pan6wgTPUTJZT11N` | — | — | — | — | — | critical | 0.9 | BIMGUARD-SB-001 v1.0.0 | IfcBeam (3W4UPvPfv6vOSdYhV7_PWH) intrudes into the seismic bracing clearance halo of IfcPipeSegment (0Goyr0Pan6wgTPUTJZT11N) by 29,841,513 mm^3 (28.9% of the halo volume). |
| `0Goyr0Pan6wgTPUTJZT11O` | — | — | — | — | — | critical | 0.9 | BIMGUARD-SB-001 v1.0.0 | IfcBeam (3W4UPvPfv6vOSdYhV7_PWz) intrudes into the seismic bracing clearance halo of IfcPipeSegment (0Goyr0Pan6wgTPUTJZT11O) by 100,634,000 mm^3 (100.0% of the halo volume). |


---

## What the real models could not tell us

Plain numbers, per model, from the audit's own gates:

| Model | Elements | No material | No system | No hydraulics |
| --- | ---: | ---: | ---: | ---: |
| `west_riverside_hospital_plumb_ifc4` (1540) | 8,539 | **8,539** | 5 | **8,539** |
| `west_riverside_hospital_arc_ifc4` | 9,333 | 2,703 | **9,333** | **9,333** |
| `Clinic_Architectural` | 808 | 286 | **808** | **808** |
| `west_riverside_hospital_str_ifc4` | 5 | 0 | 5 | 5 |
| `test_hospital_mep_demo` (synthetic) | 420 | 42 | 0 | 126 |

What that cost, engine by engine:

- **GC-001 and CC-001 could not assess a single pipe.** Every one of 1540's 8,539
  elements failed the material gate, so both engines declined all 8,539 —
  17,078 `material_unresolved` notes between them.
- **MC-001 could not assess anything, anywhere on a real model.** No real model
  carries flow velocity, dead-leg length or operating temperature, so the
  hydraulics gate refused all 8,539 pipes, all 9,333 curtain-wall members, all
  808 clinic elements and all 5 structural members: `hydraulics_unavailable`
  every time.
- **MM-001 and XM-001 were near-silent.** MM-001 managed 10 verdicts on the whole
  corpus; XM-001 managed none, and produced exactly one finding of any kind.
- **SB-001 was unaffected**, because clearance is a geometry question and the
  geometry is in the models.

### What the model exporter would have had to include

For these engines to say anything about real pipework, the IFC would need, per
element:

1. **A material.** `IfcMaterial` / `IfcMaterialLayerSet` on the pipe, or a
   material name in a property set. This alone unlocks GC-001 and CC-001 —
   8,539 elements on 1540, from silence to assessed.
2. **A second material where two metals meet**, in
   `Pset_BimGuardCouple.SecondaryMaterial`. Without it GC-001 can only score an
   element against itself, which is what produced the 0 V self-couples above.
3. **Flow velocity, dead-leg length and operating temperature** in the piping
   property sets. Any one of the three opens MC-001; all three absent is the only
   case it refuses.
4. **System assignment** — membership of a named `IfcSystem`. 9,333 of 9,333
   curtain-wall elements and 808 of 808 clinic elements are `Unassigned`, which
   is why MM-001 and XM-001 have almost no network to walk.

The synthetic control carries all four, which is exactly why it is the only model
in this report that produces Critical verdicts.

---

## Consistency

For each engine, the findings it produces alone must equal the findings
attributed to it inside the five-engine run. Anything else would mean the analyse
page's engine chips change the answer rather than filter it.

| Model | GC-001 | CC-001 | MC-001 | MM-001 | XM-001 |
| --- | --- | --- | --- | --- | --- |
| `test_hospital_mep_demo` | MATCH (420) | MATCH (420) | MATCH (420) | MATCH (182) | MATCH (214) |
| `west_riverside_hospital_plumb_ifc4` | MATCH (8,539) | MATCH (8,539) | MATCH (8,539) | MATCH (3,563) | MATCH (1) |
| `west_riverside_hospital_arc_ifc4` | MATCH (9,333) | MATCH (9,333) | MATCH (9,333) | MATCH (0) | MATCH (0) |
| `Clinic_Architectural` | MATCH (808) | MATCH (808) | MATCH (808) | MATCH (102) | MATCH (0) |
| `west_riverside_hospital_str_ifc4` | MATCH (5) | MATCH (5) | MATCH (5) | MATCH (0) | MATCH (0) |


**All 25 checks match**, by count and by element GUID. No discrepancies to
report.

---

## Where the full outputs are

Each directory holds `findings.csv`, `findings.json`, `result.json` (the envelope
a real run returns to the SPA), `summary.json`, `sample_50.csv`, and for the
five-engine and seismic runs `findings.bcf`. Only the summaries and 50-row
samples are committed; the rest regenerate with `scripts/showcase_run.py`.

- `test_hospital_mep_demo` / **GC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\test_hospital_mep_demo\GC-001`
- `test_hospital_mep_demo` / **CC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\test_hospital_mep_demo\CC-001`
- `test_hospital_mep_demo` / **MC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\test_hospital_mep_demo\MC-001`
- `test_hospital_mep_demo` / **MM-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\test_hospital_mep_demo\MM-001`
- `test_hospital_mep_demo` / **XM-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\test_hospital_mep_demo\XM-001`
- `test_hospital_mep_demo` / **ALL5** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\test_hospital_mep_demo\ALL5`
- `west_riverside_hospital_plumb_ifc4` / **GC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_plumb_ifc4\GC-001`
- `west_riverside_hospital_plumb_ifc4` / **CC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_plumb_ifc4\CC-001`
- `west_riverside_hospital_plumb_ifc4` / **MC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_plumb_ifc4\MC-001`
- `west_riverside_hospital_plumb_ifc4` / **MM-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_plumb_ifc4\MM-001`
- `west_riverside_hospital_plumb_ifc4` / **XM-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_plumb_ifc4\XM-001`
- `west_riverside_hospital_plumb_ifc4` / **ALL5** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_plumb_ifc4\ALL5`
- `west_riverside_hospital_arc_ifc4` / **GC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_arc_ifc4\GC-001`
- `west_riverside_hospital_arc_ifc4` / **CC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_arc_ifc4\CC-001`
- `west_riverside_hospital_arc_ifc4` / **MC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_arc_ifc4\MC-001`
- `west_riverside_hospital_arc_ifc4` / **MM-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_arc_ifc4\MM-001`
- `west_riverside_hospital_arc_ifc4` / **XM-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_arc_ifc4\XM-001`
- `west_riverside_hospital_arc_ifc4` / **ALL5** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_arc_ifc4\ALL5`
- `Clinic_Architectural` / **GC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\Clinic_Architectural\GC-001`
- `Clinic_Architectural` / **CC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\Clinic_Architectural\CC-001`
- `Clinic_Architectural` / **MC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\Clinic_Architectural\MC-001`
- `Clinic_Architectural` / **MM-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\Clinic_Architectural\MM-001`
- `Clinic_Architectural` / **XM-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\Clinic_Architectural\XM-001`
- `Clinic_Architectural` / **ALL5** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\Clinic_Architectural\ALL5`
- `west_riverside_hospital_str_ifc4` / **GC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_str_ifc4\GC-001`
- `west_riverside_hospital_str_ifc4` / **CC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_str_ifc4\CC-001`
- `west_riverside_hospital_str_ifc4` / **MC-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_str_ifc4\MC-001`
- `west_riverside_hospital_str_ifc4` / **MM-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_str_ifc4\MM-001`
- `west_riverside_hospital_str_ifc4` / **XM-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_str_ifc4\XM-001`
- `west_riverside_hospital_str_ifc4` / **ALL5** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\west_riverside_hospital_str_ifc4\ALL5`
- `SEISMIC-1542-federation` / **SB-001** — `D:\Zigurat Masters\bim-guard-showcase\docs\validation\engine-showcase-2026-09-08\runs\SEISMIC-1542-federation\SB-001`


---

## Glossary

- **Band** — the severity of a verdict: Critical, High, Medium or Low. A Low is
  still an assessed finding, not a near-miss.
- **Score** — a 0.0–1.0 composite the engine computes alongside the band. On
  seismic it is derived from the band rather than measured independently.
- **Verdict** — the engine judged the element and produced a band. It had enough
  input to answer.
- **Data-quality note** — the engine refused to judge, because judging would have
  meant inventing an input. It names the check that failed
  (`material_unresolved`, `hydraulics_unavailable`, …). A note is a modelling gap
  for the BIM coordinator, not a defect in the building.
- **material_source** — where the material came from: `ifc_metadata` (read from
  the model), `ifc_metadata_unmapped` (read but matching no known material),
  `absent` (the model carries none). This is how you tell an assessment of the
  building from an assessment of a default.
- **ruleset_version** — which version of the rules produced the finding, e.g.
  `BIMGUARD-GC-001 v1.0.0`. Present on every one of the findings in this report.
- **Tri-state** — the three-way split behind every count here: assessed and
  banded, refused with a reason, or not applicable to that engine. It is the
  reason "0 findings" and "0 verdicts, 8,539 notes" are different answers.
