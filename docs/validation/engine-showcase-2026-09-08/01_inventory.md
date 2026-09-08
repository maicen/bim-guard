# IFC inventory, measured through the audit's own parser

Corpus root: `D:\Zigurat Masters\bim-guard\test-models\models` (main tree, read-only, never copied).
Files found: **34**. Parsed with `parse_ifc_bytes(..., with_piping=True)`, the same call `_run_corrosion_tracked` makes at `app/services/analysis_runner.py:220`.

Coverage columns are not heuristics. **Material %** is the share of elements `_material_gate` lets through, i.e. exactly what GC-001 and CC-001 will score. **Hydraulics %** is the share `_hydraulics_gate` lets through, i.e. exactly what MC-001 will score. **System %** is the share whose element belongs to a named `IfcSystem` rather than `Unassigned`.

| # | File | Dir | MB | Schema | Elements | Material % | System % | Hydraulics % | Parse s |
| ---: | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `west_riverside_hospital_str_ifc4.ifc` | hospital | 6.2 | IFC4 | 5 | 100.0 | 0.0 | 0.0 | 0.7 |
| 2 | `west_riverside_hospital_arc_ifc4.ifc` | hospital | 77.2 | IFC4 | 9,333 | 71.0 | 0.0 | 0.0 | 16.9 |
| 3 | `Clinic_Architectural.ifc` | hospital | 12.4 | IFC2X3 | 808 | 64.6 | 0.0 | 0.0 | 3.5 |
| 4 | `aisc_sculpture_brep.ifc` | industrial | 0.5 | IFC2X3 | 315 | 36.8 | 0.0 | 0.0 | 0.4 |
| 5 | `aisc_sculpture_param.ifc` | industrial | 0.3 | IFC2X3 | 315 | 36.8 | 0.0 | 0.0 | 0.4 |
| 6 | `IFC_Schependomlaan.ifc` | office | 47.0 | IFC2X3 | 82 | 15.9 | 0.0 | 0.0 | 4.7 |
| 7 | `west_riverside_hospital_sprinkle_ifc4.ifc` | hospital | 32.4 | IFC4 | 13,490 | 0.0 | 92.0 | 0.0 | 30.7 |
| 8 | `west_riverside_hospital_mech_ifc2x3.ifc` | schemas | 75.1 | IFC2X3 | 18,488 | 0.0 | 99.1 | 0.0 | 46.1 |
| 9 | `west_riverside_hospital_mech_ifc4.ifc` | hospital | 69.7 | IFC4 | 17,424 | 0.0 | 99.9 | 0.0 | 39.5 |
| 10 | `west_riverside_hospital_plumb_ifc2x3.ifc` | schemas | 23.8 | IFC2X3 | 9,013 | 0.0 | 97.9 | 0.0 | 23.2 |
| 11 | `west_riverside_hospital_plumb_ifc4.ifc` | hospital | 22.7 | IFC4 | 8,539 | 0.0 | 99.9 | 0.0 | 19.2 |
| 12 | `Clinic_Plumbing.ifc` | hospital | 53.2 | IFC2X3 | 6,587 | 0.0 | 0.0 | 26.9 | 37.2 |
| 13 | `wbdg_office_mep.ifc` | office | 40.0 | IFC2X3 | 5,697 | 0.0 | 0.0 | 17.4 | 42.6 |
| 14 | `Clinic_HVAC.ifc` | hospital | 25.7 | IFC2X3 | 3,704 | 0.0 | 0.0 | 36.8 | 17.8 |
| 15 | `Clinic_Electrical.ifc` | hospital | 6.5 | IFC2X3 | 2,089 | 0.0 | 0.0 | 0.0 | 12.6 |
| 16 | `DigitalHub_FM-HZG_v2.ifc` | office | 19.9 | IFC4 | 1,795 | 0.0 | 100.0 | 0.0 | 11.2 |
| 17 | `west_riverside_hospital_elec_ifc4.ifc` | hospital | 4.2 | IFC4 | 1,673 | 0.0 | 77.0 | 0.0 | 5.8 |
| 18 | `DigitalHub_FM-LFT_v2.ifc` | office | 12.1 | IFC4 | 1,310 | 0.0 | 100.0 | 0.0 | 8.2 |
| 19 | `DigitalHub_FM-SAN_v2.ifc` | office | 24.0 | IFC4 | 1,010 | 0.0 | 98.2 | 0.0 | 6.4 |
| 20 | `Duplex_MEP_20110907.ifc` | office | 17.0 | IFC2X3 | 926 | 0.0 | 0.0 | 34.9 | 7.2 |
| 21 | `west_riverside_hospital_fire_ifc4.ifc` | hospital | 0.9 | IFC4 | 861 | 0.0 | 0.0 | 0.0 | 2.3 |
| 22 | `GVA_Sanitario.ifc` | hospital | 6.6 | IFC2X3 | 711 | 0.0 | 0.0 | 0.0 | 1.9 |
| 23 | `Duplex_Plumbing_20121113.ifc` | office | 30.1 | IFC2X3 | 498 | 0.0 | 0.0 | 31.1 | 6.3 |
| 24 | `GVA_Administrativo.ifc` | office | 6.9 | IFC2X3 | 363 | 0.0 | 0.0 | 0.0 | 1.5 |
| 25 | `DigitalHub_FM-ARC_v2.ifc` | office | 8.6 | IFC4 | 105 | 0.0 | 0.0 | 0.0 | 1.0 |
| 26 | `Duplex_Electrical_20121207.ifc` | office | 1.5 | IFC2X3 | 99 | 0.0 | 0.0 | 0.0 | 0.9 |
| 27 | `Molio_with_URIs.ifc` | office | 70.5 | IFC2X3 | 48 | 0.0 | 0.0 | 0.0 | 9.1 |
| 28 | `AC20-FZK-Haus.ifc` | office | 2.5 | IFC4 | 42 | 0.0 | 0.0 | 0.0 | 0.4 |
| 29 | `wbdg_office_arc.ifc` | office | 3.9 | IFC2X3 | 39 | 0.0 | 0.0 | 0.0 | 0.7 |
| 30 | `Duplex_A_20110907.ifc` | office | 2.3 | IFC2X3 | 4 | 0.0 | 0.0 | 0.0 | 0.4 |
| 31 | `Clinic_Structural.ifc` | hospital | 18.2 | IFC2X3 | 0 | 0.0 | 0.0 | 0.0 | 1.7 |
| 32 | `craslabbim.ifc` | industrial | 64.4 | IFC2X3 | 0 | 0.0 | 0.0 | 0.0 | 8.3 |
| 33 | `AC20-Institute-Var-2.ifc` | office | 10.4 | IFC4 | 0 | 0.0 | 0.0 | 0.0 | 1.4 |
| 34 | `wbdg_office_str.ifc` | office | 10.6 | IFC2X3 | 0 | 0.0 | 0.0 | 0.0 | 1.4 |

## Files the seismic step can federate

`run_seismic_analysis` unions the geometry of a primary model and every `extra_models` entry, so any group of models describing one building is federatable. Directory is the only grouping the corpus records:

- **hospital** (13 models): `Clinic_Architectural.ifc`, `Clinic_Electrical.ifc`, `Clinic_HVAC.ifc`, `Clinic_Plumbing.ifc`, `Clinic_Structural.ifc`, `GVA_Sanitario.ifc`, `west_riverside_hospital_arc_ifc4.ifc`, `west_riverside_hospital_elec_ifc4.ifc`, `west_riverside_hospital_fire_ifc4.ifc`, `west_riverside_hospital_mech_ifc4.ifc`, `west_riverside_hospital_plumb_ifc4.ifc`, `west_riverside_hospital_sprinkle_ifc4.ifc`, `west_riverside_hospital_str_ifc4.ifc`
- **industrial** (3 models): `aisc_sculpture_brep.ifc`, `aisc_sculpture_param.ifc`, `craslabbim.ifc`
- **office** (16 models): `AC20-FZK-Haus.ifc`, `AC20-Institute-Var-2.ifc`, `DigitalHub_FM-ARC_v2.ifc`, `DigitalHub_FM-HZG_v2.ifc`, `DigitalHub_FM-LFT_v2.ifc`, `DigitalHub_FM-SAN_v2.ifc`, `Duplex_A_20110907.ifc`, `Duplex_Electrical_20121207.ifc`, `Duplex_MEP_20110907.ifc`, `Duplex_Plumbing_20121113.ifc`, `GVA_Administrativo.ifc`, `IFC_Schependomlaan.ifc`, `Molio_with_URIs.ifc`, `wbdg_office_arc.ifc`, `wbdg_office_mep.ifc`, `wbdg_office_str.ifc`
- **schemas** (2 models): `west_riverside_hospital_mech_ifc2x3.ifc`, `west_riverside_hospital_plumb_ifc2x3.ifc`

### How project 1542's set is identified

The repository records it in two places, both cited rather than guessed:

- `docs/validation/final-audit-2026-09-06.md:135` — attaching all three West Riverside discipline models to project **1542** failed; **2 of 3 attached (plumb IFC4 23.8 MB, str IFC4 6.5 MB)** and the 69.7 MB mech model returned `413 Payload too large`.
- `docs/demo/RUNBOOK.md` (Seismic on 1542) — "The federation is two models, `west_riverside_hospital_plumb_ifc4.ifc` and `west_riverside_hospital_str_ifc4.ifc`".

So 1542 is those two files, and that is what this showcase federates.

### How project 1540's model is identified

`docs/demo/RUNBOOK.md` ("Piping on a real model with no materials (1540)") names it *FINAL AUDIT Piping WR Plumb IFC4* — West Riverside hospital plumbing, IFC4, 23.8 MB, 8,539 piping elements — i.e. `west_riverside_hospital_plumb_ifc4.ifc`.

