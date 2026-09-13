# Defect: CC-001 joint type library never executes

**Status:** Open. Recorded, not fixed. The decision is to document the defect and withdraw the claims, not to fix it.
**Engine:** BIMGUARD-CC-001 (crevice corrosion), ruleset version 1.0.0
**Recorded:** 13 September 2026
**Found by:** A read-only impact analysis carried out on 13 September 2026. No code, data or database row was changed to find or measure it.
**Code references:** `main` at `2e25cf5` unless stated. The frozen demo build `1450960` was checked separately (see "Demo build").

---

CC-001's 14-type joint library is specified, seeded into the database, described in the documentation and claimed in the user interface, but it never runs. Two separate faults stop it: the engine looks up a key the catalogue does not supply, and the pipeline gives the engine a joint code instead of the descriptive text the lookup searches. So every element CC-001 has ever scored was given joint type JT-014, "Unknown / unclassified", Tight geometry, geometry risk 0.75, whatever its real joint. The findings show this: every CC-001 explanation says "Joint Unknown / unclassified classifies as Tight geometry". The geometry term (weight 0.35) is a constant. It has never discriminated between two elements.

## 1. What the library is specified to do

The CC-001 composite score is

    score = 0.35 × geometry risk + 0.40 × CCT adequacy + 0.25 × environment severity

The geometry risk should come from a library of 14 joint types. Each type has a label, a geometry class (Open, Moderate, Tight, Critical) and a list of text keywords. For example, JT-001 is a butt weld (Open, 0.10), JT-005 threaded NPT (Critical, 1.00), JT-012 a pipe clamp under insulation (Critical, 1.00), and JT-014 is "Unknown / unclassified" (Tight, 0.75), used only when nothing else matches. The engine should search the element's joint description for those keywords and use the geometry class of the first type that matches. Seeded definition: `supabase/migrations/20260806180500_seed_static_data_assets.sql:800-817`. Inline copy of the same payload: `:736`.

The seeded description of the library (`:801`) says it maps "IFC element types and joint descriptions to geometry class". It does not.

## 2. Break one: the key names do not match

| Side | Location | Key |
|---|---|---|
| Seeded data | `supabase/migrations/20260806180500_seed_static_data_assets.sql:803-816` (and inline at `:736`) | `ifc_keywords` |
| Catalogue loader (output) | `app/services/corrosion_rule_catalog.py:845` | `ifc_keywords` (it reads `ifc_keywords` or `ifc_types` and always writes `ifc_keywords`) |
| Engine (reader) | `app/engines/bimguard_crevice_engine.py:139` | `ifc_types` |

No code path makes the two sides agree. The loader turns every source into `ifc_keywords`, and that includes the hardcoded offline fallback at `corrosion_rule_catalog.py:162`, which is written with `ifc_types`. The engine then reads `jt.get("ifc_types")`, gets `None`, falls back to an empty list, and skips every type. `classify_joint_type` (`bimguard_crevice_engine.py:130-147`) always reaches its last line and returns `("JT-014", "Tight", GEOMETRY_CLASSES["Tight"]["risk"])`.

This also applies to the engine's own built-in examples (`bimguard_crevice_engine.py:829-855`). Descriptive strings such as `"weld neck flange"` and `"butt weld"` fall through to JT-014 as well.

## 3. Break two: the engine gets a code, not a description

Even with the key corrected, matching would still fail. The keyword search is a substring test against the joint description, but the pipeline never passes a description:

- `app/modules/ifc_reader/ifc_parser.py:628` sets `joint = IFC_TO_JOINT.get(ifc_type, "JT-005")`. The table at `:160-170` assigns a bare code by IFC class, e.g. `IfcPipeSegment` → `"JT-012"`. The synthetic-model generator (`ifc_parser.py:897-1209`) also assigns bare codes.
- That code is stored as `ServiceElement.joint_type` (`ifc_parser.py:645`, `:1238`).
- `app/modules/phase_6/phase_6c_corrosion_ui.py:307` passes it straight through: `joint_description=element.joint_type`.

None of the 41 seeded keywords appears inside any of the 14 strings `JT-001` … `JT-014`. This was checked by direct substring comparison against the seeded payload.

**Measured:** renaming the key alone changes no verdicts. In project 1917, 378 of 378 CC-001 elements still fall through to JT-014.

## 4. Consequence

Every element CC-001 scores gets JT-014 / Tight / geometry risk 0.75. The geometry term adds a fixed 0.35 × 0.75 ≈ 0.26 to every composite score, and the score varies only with CCT adequacy and environment.

Confirmed on live results:

- Working backwards from every frozen project 1917 CC-001 score gives a geometry sub-score of 0.749.
- All 378 CC-001 scores in 1917 can be rebuilt exactly from their stored CCT and environment inputs with geometry fixed at the Tight value: maximum deviation 0.000, 0 band mismatches.
- The defect is visible in the findings. Each explanation reads "Joint Unknown / unclassified classifies as Tight geometry …". See the verbatim rows in `docs/validation/engine-showcase-2026-09-08/README.md:169-181`, where 6,630 curtain-wall members got Medium on exactly this basis.

The specification's own defining example is "SS316 flanges in a pool plant room score Critical; the same flanges in a dry void score Low". That example is not produced by joint classification. A flange, a butt weld and a pipe segment all get the same geometry value.

## 5. Which projects are affected

| Project | Affected? | Reason |
|---|---|---|
| **1917** | **Yes** | 378 CC-001 scores, every one built on the JT-014 / Tight constant (section 4). |
| 1540 | No | Every CC-001 row is a `material_unresolved` data-quality note. No banded crevice score exists, so the geometry term never reaches a verdict. |
| 1542 | No | Only SB-001 (seismic clearance) was run. CC-001 was not run. |

No frozen figure changes because of this record. Every CC-001 number already reported was produced with this defect in place, so it can be reproduced exactly from both `1450960` and `main`. Those numbers measure the software as it is, not the specified library.

## 6. Demo build

The demo build `1450960` has the same defect, line for line. The engine reads `ifc_types` at `bimguard_crevice_engine.py:139`, the loader writes `ifc_keywords` at `corrosion_rule_catalog.py:845`, and `_cc_element` (`phase_6c_corrosion_ui.py:301-311`) passes `joint_description=element.joint_type` and no temperature. Any CC-001 result shown in the demo was scored at JT-014 / Tight.

## 7. A second dead input: operating temperature is dropped

`_cc_element` (`app/modules/phase_6/phase_6c_corrosion_ui.py:301-311`) builds the CC-001 input without `operating_temp_c`, although `ServiceElement` has that field (`ifc_parser.py:129`) and the parser fills it from the `OperatingTemperature` property (`ifc_parser.py:377`, `:500`). So `CCElement.operating_temp_c` always takes its default of 20.0 °C (`bimguard_crevice_engine.py:380`).

In project 1917, **294 elements carry an `OperatingTemperature` property set**, and every one of them was scored for CCT adequacy at 20 °C. CCT adequacy has weight **0.40**, more than geometry's 0.35. So the heaviest term in the score is also not reading the model. Taken together, the two largest of CC-001's three terms do not respond to the element's actual joint or actual temperature.

## 8. Three incompatible JT vocabularies

The repository uses "JT-nnn" codes in three different senses. A code means different things depending on where it appears.

| Vocabulary | Where | JT-001 | JT-003 | JT-014 |
|---|---|---|---|---|
| CC-001 joint library | seeded ruleset (migration `:803-816`) | Butt weld | Slip-on flange | Unknown / unclassified |
| Piping schema `JointType` enum | `app/modules/ifc_reader/piping_schema.py:161-175` | Plain welded | Threaded | Dielectric union |
| Parser `IFC_TO_JOINT` comments | `app/modules/ifc_reader/ifc_parser.py:160-170` | "Flanged connections most common" | — | (assigned to `IfcPlate`) |

- Before this change, `piping_schema.py:158` and `docs/piping_schema_spec.md:118` said the enum keys "match JT-001 through JT-014" in the crevice ruleset. They do not: the numbering is different. Both are corrected by this change to say the enum is a separate vocabulary.
- XM-001 uses `JT-014` to mean a dielectric union and gives it a 0.10 mitigation multiplier (`data/rulesets/xm_001_cross_material.json:149`; explained in `docs/client-qa/Q04_XM001_Cross_Material_Composite_Score.md:47`). CC-001 uses `JT-014` to mean Unknown. So JT-014 means both "we do not know the joint" and "the joint is isolated".
- The parser's `IFC_TO_JOINT` comments `JT-001` as "Flanged". In the CC-001 catalogue JT-001 is a butt weld, the least severe type, while a flange is JT-003, JT-004, JT-010 or JT-011.

The enum is filled by a separate keyword classifier, `piping_producer.classify_joint_type` (`app/modules/ifc_reader/piping_producer.py:997`). That output goes onto `PipingElement` and does not reach CC-001. It is the only joint classifier with tests (`tests/test_piping_producer.py:196-200`).

## 9. Other gaps

- **`ifc_data_sources.joint_type` is never read.** The seeded payload lists where the joint type should come from: `IfcPipeFitting.PredefinedType`, `Pset_PipeFittingOccurrence.ConnectionType`, `IfcPipeSegmentType.ObjectType` (migration `:901`). No code reads `ifc_data_sources`.
- **No test covers the engine's classifier.** No test calls `bimguard_crevice_engine.classify_joint_type`, and neither `ifc_keywords` nor `ifc_types` appears in any test that touches CC-001. So the key mismatch and the code-instead-of-text input have never been caught by a test.

## 10. What a full fix would require

A fix is not being made. For the record, restoring the specified behaviour would need all of the following. Renaming the key alone does nothing (section 3).

1. **Make the key names agree.** Change either the loader output or the engine reader so both use the same key.
2. **Give the engine real joint evidence.** Either (a) pass descriptive text (element name, type name, `PredefinedType`, `Pset_PipeFittingOccurrence.ConnectionType`, as `ifc_data_sources` specifies) and let the keyword search run, or (b) look up the type directly by code. Option (b) depends on a code→geometry mapping that **has never been validated**. `IFC_TO_JOINT` assigns codes by IFC class, with comments from a different vocabulary. Read literally against the catalogue, it would classify every `IfcPipeFitting` as a butt weld (Open) and every `IfcPipeSegment` as a pipe clamp under insulation (Critical). Neither assignment is supported by any source or measurement.
3. **Agree one JT vocabulary**, or rename two of the three so that a code has only one meaning (section 8), including XM-001's use of JT-014.
4. **Pass `operating_temp_c` through `_cc_element`** (section 7).
5. **Add tests** that run `classify_joint_type` on the inputs the real pipeline produces, not only on hand-written descriptions.
6. **Correct the seeded database descriptions** with a new migration (section 11).
7. **Re-baseline.** Any of steps 1–4 moves CC-001 scores, and for 1917 it would move all 378. Every CC-001 figure already reported would then describe the old build. A fix must produce new, separately dated figures and must not overwrite the frozen ones.

## 11. Inaccurate database descriptions: corrective migration (not written)

The applied migration `supabase/migrations/20260806180500_seed_static_data_assets.sql` is not edited. Its seeded text for asset `ruleset:BIMGUARD-CC-001` is inaccurate in three places:

| Line | Field | Current text |
|---|---|---|
| `:801` | `joint_type_library.description` (formatted `content_text`) | "14-type joint library mapping IFC element types and joint descriptions to geometry class. JT-014 (unknown) defaults to Tight — conservative fallback when joint data is absent from IFC model." |
| `:736` | same field, inline `content_json` copy | same text |
| `:885` | `pset_definition` property `CC001_JointTypeCode`, `description` | "Joint type code JT-001 through JT-014" |

A corrective migration, `supabase/migrations/<UTCYYYYMMDDHHMMSS>_correct_cc001_joint_library_description.sql`, would need to:

- Set `joint_type_library.description`, in both `content_json` and `content_text` of the `ruleset:BIMGUARD-CC-001` row in `public.static_data_assets`, to:
  > "14-type joint library specifying a geometry class per joint type. Not currently executed: the engine reads `ifc_types` while this library stores `ifc_keywords`, and the pipeline supplies a joint code rather than descriptive text, so every element is classified JT-014 (Unknown / unclassified, Tight). See docs/defects/CC-001-joint-library-inert.md."
- Set the `CC001_JointTypeCode` description to:
  > "Joint type code. In the current build this is always JT-014; JT-001 to JT-013 are specified but never assigned. See docs/defects/CC-001-joint-library-inert.md."
- Recompute `content_sha256` so it matches the new `content_text`.
- Change descriptive strings only. No key, value, weight, threshold or `risk` figure may change, so that every frozen CC-001 score stays reproducible. Whether to change `ruleset_version` (findings currently record `BIMGUARD-CC-001 v1.0.0`) should be decided in that migration and recorded there.

The `rules` table rows for joint types (`CC-001.JT.*`, written by `app/services/ruleset_seeder.py:543-552`) describe each type's label, geometry and risk. They make no claim about matching and do not need correcting.

## 12. Live claims withdrawn by this change

These places claimed or implied that joint classification runs. Each was corrected to describe what the software actually does. The library is still specified and seeded; only the claim that it runs is withdrawn.

- `frontend/src/lib/components/PipingChecksExplainer.svelte` (CC-001 "What it needs from the model")
- `docs/demo/piping-checks-plain-english.md` (same text)
- `frontend/src/lib/glossary.ts` (CC-001 description)
- `docs/client-qa/Q18_Selecting_Which_Corrosion_Engines_Run.md` (engine table row)
- `scripts/build/build_deck_d.py` (Engine B "Specified" column; the deck file was not rebuilt in this change)
- `app/modules/ifc_reader/piping_schema.py` (joint enum header comment)
- `docs/piping_schema_spec.md` ("Joints and connectivity")
- `app/engines/bimguard_crevice_engine.py` (`classify_joint_type` docstring)
- `app/services/ruleset_seeder.py` (joint-type seeding comment)

Evidence records dated before this change that already describe the defect accurately were left as they are: `docs/validation/engine-showcase-2026-09-08/README.md:169-181` and `docs/validation/data/CC-001_validation_demo_asset_register.csv`.

## 13. Not remediated here

The files below contain inaccurate claims about the joint library. They are left unchanged on purpose: the thesis is out of scope for this change, and the archive, experimental and submission files are historical records. They are listed so that nobody treats them as describing working behaviour.

### Thesis: `docs/thesis/MAICEN_M10_Final_Thesis_Mark_Shane_Haines.docx`

- **§9.3 "Joint type library"**: "CC-001 includes a library of 14 joint types (JT-001 through JT-014) mapping IFC element type classifications to geometry classes. This library provides the mechanism by which the engine assigns a geometry risk multiplier … The IFC element type — IfcPipeFitting.PredefinedType, valve classification, or connection type — is used as the key to look up the corresponding joint type and geometry class." This is inaccurate. No lookup takes place, and `PredefinedType` is never read.
- **Input list**: "Joint type — from element type classification mapped to the GC-001 and CC-001 joint type library". This is inaccurate. The mapped code never reaches a geometry class.
- **Pset description**: "GeometryClass — the joint type library classification (string: JT-001 through JT-014)". In practice this is always JT-014 / Tight.
- **Three-engine discussion**: "Low on CC-001 (butt-welded joints, no crevice geometry)" and "CC-001 will not flag it because butt-welded carbon steel joints do not present significant crevice geometry". CC-001 cannot tell a butt weld from any other joint.
- **Engine summary table**: "Data-quality issues dominant; risk bands only where joint type can be inferred from fitting class". Joint type is never inferred into a geometry class.
- The thesis does describe accurately that "CC-001 reported a crevice geometry of "Tight" and a joint type of JT-014 for an element that declared no joint." What it leaves out is that JT-014 is also given to elements that do declare a joint.

### Second thesis copy: `docs/MAICEN_M10_Final_Thesis_Mark_Shane_Haines.docx`

An earlier copy with the same §9.3 text, the same input-list line, the same "GeometryClass … JT-001 through JT-014" line and the same butt-weld examples. Not remediated.

### Archived, experimental and submission files

- `docs/archive/index.html:604`: "CC-001: implement CCT table …, 14-type joint library (JT-001 to JT-014), 7 environment severity classes", shown as a planned task. Implied complete; not true in behaviour.
- `docs/experimental/bimguard-frontend-prototype-v1.html:916`: ruleset table lists CC-001 with "14 joint types".
- `docs/submissions/BIMGuard_3rd_Submission_REVISED.md:198`: "a 14-member `JointType` enum matching a dedicated `JT-001`–`JT-014` ruleset". False (section 8).

### Generated corpora

`docs/bimguard_corrosion_rules.md` (e.g. `:24047`, `:48425`, `:51156`) contains copies of the pre-correction source text, including the false "Keys match JT-001 through JT-014" claim. It is generated output from `scripts/compile_for_notebooklm.py` and was not hand-edited. It will pick up the corrections the next time it is generated.
