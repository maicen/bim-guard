# Defect: CC-001's three scoring inputs are inert

**Status:** Open. Recorded, not fixed. The decision was to document the defect, withdraw or correct the claims, and correct one factual error in the findings text. The scoring was not changed (section 12).
**Engine:** BIMGUARD-CC-001 (crevice corrosion), ruleset version 1.0.0
**Recorded:** 13 September 2026. First recorded as the joint-library defect (`docs/defects/CC-001-joint-library-inert.md`), then widened and renamed on the same day when measurement showed that the temperature and environment inputs are inert as well.
**Found by:** Read-only impact analyses carried out on 13 September 2026. No code, data or database row was changed to find or measure the defect.
**Code references:** `main` at `2e25cf5` unless stated. The frozen demo build `1450960` was checked separately (section 11).

---

## Summary

**On project 1917, CC-001's three scoring inputs collapse into a single discriminator: the engine tells SS316 apart from everything else, and does nothing more.**

CC-001 is specified to combine three separate judgements about each element: how tight the joint is, whether the alloy can resist crevice attack at the operating temperature, and how severe the environment is. In the current software none of the three reads what the model says about the element:

| Term | Weight | Specified input | What the pipeline actually gives it | Value on all 378 findings in 1917 |
|---|---|---|---|---|
| Geometry | 0.35 | Joint type, classified from the joint description | A joint code that never matches, so the type is always JT-014 "Unknown / unclassified" | Tight / 0.75 → constant **0.2625** |
| CCT adequacy | 0.40 | Alloy's critical crevice temperature against the element's operating temperature | The alloy, but always a 20 °C default temperature | 0.733 for SS316, 0.05 for any ungraded material → **0.2932 or 0.0200** |
| Environment | 0.25 | Environment severity class | A parser code the engine's English phrases never match | BUILDING_SERVICES / 0.35 → constant **0.0875** |

There are three independent causes:

1. **The joint type library never executes** (section 3). The loader writes `ifc_keywords` but the engine reads `ifc_types`, and the pipeline passes a joint code rather than descriptive text.
2. **The operating temperature is dropped** (section 4). The parser reads it and `ServiceElement` carries it, but `_cc_element` does not pass it, so the engine uses its 20 °C default.
3. **The environment vocabularies do not match** (section 5). The parser emits codes such as `interior_conditioned`, while the engine searches for phrases such as "plant room".

The consequence is that **CC-001 produces exactly two scores on project 1917: 0.370 (Medium) and 0.643 (High).** 60% of the weight is constant. The remaining 40% acts as a switch between stainless steel and not stainless steel.

The findings themselves stated a temperature that was not read from the model. That sentence has been corrected (section 13). No score, band, count or mitigation changes as a result.

## 1. The score as specified

    score = 0.35 × geometry risk + 0.40 × CCT adequacy + 0.25 × environment severity

Composite: `app/engines/bimguard_crevice_engine.py:301`. Bands (`:307-317`): below 0.30 Low, 0.30 to 0.55 Medium, 0.55 to 0.80 High, 0.80 and above Critical.

- **Geometry risk** comes from a 14-type joint library. Each type has a geometry class: Open 0.10, Moderate, Tight 0.75, Critical 1.00.
- **CCT adequacy** (`calculate_cct_adequacy`, `:246-284`) compares the alloy's critical crevice temperature (ASTM G48 Method B) with the operating temperature. It is 0.00 when the element runs more than 20 °C below the CCT, rises linearly to 0.60 at the CCT, and reaches 1.00 at 30 °C above it. Material without a CCT entry scores 0.05 (`:258-259`), or 0.10 if the grade resolves but is not in the table.
- **Environment severity** (`classify_environment_severity`, `:235-242`, table `ZONE_TO_SEVERITY` `:213-232`) maps a zone category and system name to a class from T0_DRY to T5_IMMERSION. Anything unmatched becomes BUILDING_SERVICES at 0.35.

The specification's defining example is "SS316 flanges in a pool plant room score Critical; the same flanges in a dry void score Low". It needs all three terms to respond to the element.

## 2. What CC-001 actually produces

### Project 1917

All 378 CC-001 findings on project 1917 share the same geometry value (JT-014 / Tight / 0.75) and the same environment value (BUILDING_SERVICES / 0.35). Only the CCT term differs, and only by material:

| Material | Geometry | CCT (at 20 °C) | Environment | Composite | Band | Findings |
|---|---|---|---|---|---|---|
| SS316 | 0.35 × 0.75 = 0.2625 | 0.40 × 0.733 = 0.2932 | 0.25 × 0.35 = 0.0875 | **0.643** | High | 70 |
| Any ungraded material | 0.2625 | 0.40 × 0.05 = 0.0200 | 0.0875 | **0.370** | Medium | 308 |

The engine-showcase record for this model shows the same split: 0 Critical, 70 High, 308 Medium, 0 Low (`docs/validation/engine-showcase-2026-09-08/README.md:91`).

### Reachable range on any model

Through the current pipeline, geometry is always 0.2625 and the CCT term is always taken at 20 °C. The only open questions are the alloy and whether the environment code happens to contain a matching word (section 5):

- **Any model: 0.350 to 0.886.** The minimum is a grade 20 °C or more below its CCT (Super Duplex 2507, titanium, Hastelloy C: CCT term 0) in BUILDING_SERVICES. The maximum is SS304 (CCT −5 °C, term 0.933) with the `swimming_pool` code (T5_IMMERSION, 1.0).
- **Within BUILDING_SERVICES: 0.350 to 0.723.**

**No element can score Low through a parser environment code.** The constant geometry term and the lowest environment any parser code reaches (BUILDING_SERVICES) already sum to 0.350, above the 0.30 Low boundary. The specified "dry void → Low" outcome cannot occur from a space name. **Critical is reachable only with the `swimming_pool`, `coastal` or `marine_splash` codes.**

These ranges exclude one side route. The engine also searches the element's *system name*, so a system name that happens to contain an engine phrase changes the class. "office" or "normal" gives T1_OCCASIONAL (0.20), and "cleanroom" or "controlled" gives T0_DRY (0.05). That can lower the floor to 0.275 (Low) or raise an element to Critical. It is incidental matching on a name, not a reading of the environment. It did not occur on 1917, where every finding is BUILDING_SERVICES.

These figures use the database catalogue, which classifies Tight at 0.75. The hardcoded offline fallback catalogue in `app/services/corrosion_rule_catalog.py` classifies Tight at 0.80. A run with no database would therefore produce different numbers (SS316 in BUILDING_SERVICES: 0.661), but the same structure.

### A consequence for mitigations

Mitigations are chosen by `select_cc_mitigation` (`bimguard_crevice_engine.py:335-356`). Every High CC-001 finding receives MIT-CC-002, "Change joint type to reduce geometry class — specify butt weld instead of flanged or threaded connection". The trigger is the Tight geometry class, which is the unclassified-joint constant, so the advice is given without the joint having been identified. MIT-CC-006, "Lower operating temperature below material CCT", is defined but never emitted.

## 3. Cause one: the joint type library never executes

CC-001's 14-type joint library is specified, seeded into the database, described in the documentation and claimed in the user interface, but it never runs. Two separate faults stop it: the engine looks up a key the catalogue does not supply, and the pipeline gives the engine a joint code instead of the descriptive text the lookup searches. So every element CC-001 has ever scored was given joint type JT-014, "Unknown / unclassified", Tight geometry, geometry risk 0.75, whatever its real joint. The findings show this: every CC-001 explanation says "Joint Unknown / unclassified classifies as Tight geometry".

### 3.1 What the library is specified to do

Each of the 14 joint types has a label, a geometry class (Open, Moderate, Tight, Critical) and a list of text keywords. For example, JT-001 is a butt weld (Open, 0.10), JT-005 threaded NPT (Critical, 1.00), JT-012 a pipe clamp under insulation (Critical, 1.00), and JT-014 is "Unknown / unclassified" (Tight, 0.75), used only when nothing else matches. The engine should search the element's joint description for those keywords and use the geometry class of the first type that matches. Seeded definition: `supabase/migrations/20260806180500_seed_static_data_assets.sql:800-817`. Inline copy of the same payload: `:736`.

The seeded description of the library (`:801`) says it maps "IFC element types and joint descriptions to geometry class". It does not.

### 3.2 Break one: the key names do not match

| Side | Location | Key |
|---|---|---|
| Seeded data | `supabase/migrations/20260806180500_seed_static_data_assets.sql:803-816` (and inline at `:736`) | `ifc_keywords` |
| Catalogue loader (output) | `app/services/corrosion_rule_catalog.py:845` | `ifc_keywords` (it reads `ifc_keywords` or `ifc_types` and always writes `ifc_keywords`) |
| Engine (reader) | `app/engines/bimguard_crevice_engine.py:139` | `ifc_types` |

No code path makes the two sides agree. The loader turns every source into `ifc_keywords`, and that includes the hardcoded offline fallback at `corrosion_rule_catalog.py:162`, which is written with `ifc_types`. The engine then reads `jt.get("ifc_types")`, gets `None`, falls back to an empty list, and skips every type. `classify_joint_type` (`bimguard_crevice_engine.py:130-147`) always reaches its last line and returns `("JT-014", "Tight", GEOMETRY_CLASSES["Tight"]["risk"])`.

This also applies to the engine's own built-in examples (`bimguard_crevice_engine.py:829-855`). Descriptive strings such as `"weld neck flange"` and `"butt weld"` fall through to JT-014 as well.

### 3.3 Break two: the engine gets a code, not a description

Even with the key corrected, matching would still fail. The keyword search is a substring test against the joint description, but the pipeline never passes a description:

- `app/modules/ifc_reader/ifc_parser.py:628` sets `joint = IFC_TO_JOINT.get(ifc_type, "JT-005")`. The table at `:160-170` assigns a bare code by IFC class, e.g. `IfcPipeSegment` → `"JT-012"`. The synthetic-model generator (`ifc_parser.py:897-1209`) also assigns bare codes.
- That code is stored as `ServiceElement.joint_type` (`ifc_parser.py:645`, `:1238`).
- `app/modules/phase_6/phase_6c_corrosion_ui.py:307` passes it straight through: `joint_description=element.joint_type`.

None of the 41 seeded keywords appears inside any of the 14 strings `JT-001` … `JT-014`. This was checked by direct substring comparison against the seeded payload.

**Measured:** renaming the key alone changes no verdicts. In project 1917, 378 of 378 CC-001 elements still fall through to JT-014.

### 3.4 Evidence on live results

- Working backwards from every frozen project 1917 CC-001 score gives a geometry sub-score of 0.749.
- All 378 CC-001 scores in 1917 can be rebuilt exactly with geometry fixed at the Tight value (section 10).
- The defect is visible in the findings. Each explanation reads "Joint Unknown / unclassified classifies as Tight geometry …". See the verbatim rows in `docs/validation/engine-showcase-2026-09-08/README.md:169-181`, where 6,630 curtain-wall members got Medium on exactly this basis.

A flange, a butt weld and a pipe segment all get the same geometry value.

### 3.5 Three incompatible JT vocabularies

The repository uses "JT-nnn" codes in three different senses. A code means different things depending on where it appears.

| Vocabulary | Where | JT-001 | JT-003 | JT-014 |
|---|---|---|---|---|
| CC-001 joint library | seeded ruleset (migration `:803-816`) | Butt weld | Slip-on flange | Unknown / unclassified |
| Piping schema `JointType` enum | `app/modules/ifc_reader/piping_schema.py:161-175` | Plain welded | Threaded | Dielectric union |
| Parser `IFC_TO_JOINT` comments | `app/modules/ifc_reader/ifc_parser.py:160-170` | "Flanged connections most common" | — | (assigned to `IfcPlate`) |

- Before the first version of this record, `piping_schema.py:158` and `docs/piping_schema_spec.md:118` said the enum keys "match JT-001 through JT-014" in the crevice ruleset. They do not: the numbering is different. Both now say the enum is a separate vocabulary.
- XM-001 uses `JT-014` to mean a dielectric union and gives it a 0.10 mitigation multiplier (`data/rulesets/xm_001_cross_material.json:149`; explained in `docs/client-qa/Q04_XM001_Cross_Material_Composite_Score.md:47`). CC-001 uses `JT-014` to mean Unknown. So JT-014 means both "we do not know the joint" and "the joint is isolated".
- The parser's `IFC_TO_JOINT` comments `JT-001` as "Flanged". In the CC-001 catalogue JT-001 is a butt weld, the least severe type, while a flange is JT-003, JT-004, JT-010 or JT-011.

The enum is filled by a separate keyword classifier, `piping_producer.classify_joint_type` (`app/modules/ifc_reader/piping_producer.py:997`). That output goes onto `PipingElement` and does not reach CC-001. It is the only joint classifier with tests (`tests/test_piping_producer.py:196-200`).

### 3.6 Other joint-library gaps

- **`ifc_data_sources.joint_type` is never read.** The seeded payload lists where the joint type should come from: `IfcPipeFitting.PredefinedType`, `Pset_PipeFittingOccurrence.ConnectionType`, `IfcPipeSegmentType.ObjectType` (migration `:901`). No code reads `ifc_data_sources`.
- **No test covers the engine's classifier.** No test calls `bimguard_crevice_engine.classify_joint_type`, and neither `ifc_keywords` nor `ifc_types` appears in any test that touches CC-001.

## 4. Cause two: the operating temperature is dropped

CCT adequacy is the heaviest term (0.40), and it is always evaluated at 20 °C.

| Step | Location | What happens |
|---|---|---|
| Parser reads the property | `app/modules/ifc_reader/ifc_parser.py:376-382` (property names, first being `OperatingTemperature`), `:485` (read), `:500` (returned as `operating_temp_c`) | The model's value is read |
| Element carries it | `ifc_parser.py:129` (`ServiceElement.operating_temp_c`), splatted in at `:655` (`**read_hydraulics(el)`) | The value is on the element |
| CC-001 input is built | `app/modules/phase_6/phase_6c_corrosion_ui.py:301-311` (`_cc_element`) | **`operating_temp_c` is not passed** |
| Engine default | `app/engines/bimguard_crevice_engine.py:380` (`operating_temp_c: float = 20.0`) | 20 °C is used |
| Engine use | `bimguard_crevice_engine.py:462` (`calculate_cct_adequacy(mat_key, element.operating_temp_c, …)`) | Every element is assessed at 20 °C |

So the CCT term depends only on the material grade. On 1917 it is 0.733 for SS316 and 0.05 for any ungraded material (`:258-259`).

**What the 1917 model states.** 294 of its 420 elements carry `Pset_PipeSegmentOccurrence.OperatingTemperature`. There are six distinct values, 6, 12, 15, 30, 60 and 80, with 49 elements each. The IFC does not declare units. They are °C according to the generator's own table (`scripts/generate_demo_mep_model.py`) and the parser's assumption (`ifc_parser.py:374-375`).

The findings text also stated this default as though it were the element's temperature (section 13).

## 5. Cause three: the environment vocabularies do not match

This is a third break of the same kind as the joint library. Two components that must agree on vocabulary use different words.

- **The parser emits environment codes.** `SPACE_TO_ENV` (`app/modules/ifc_reader/ifc_parser.py:173-188`) maps space names to `swimming_pool`, `interior_conditioned`, `urban_exterior`, `coastal`, `marine_splash`, `industrial` or `interior_dry`. When no space name matches, it uses `DEFAULT_ENVIRONMENT = "interior_dry"` (`:71`, returned at `:329`). The code is stored as `ServiceElement.location_tag` (`:642`).
- **The pipeline passes the code as the zone.** `_cc_element` sets `zone_category=element.location_tag` and `system_type=element.system` (`phase_6c_corrosion_ui.py:308-309`).
- **The engine matches English phrases.** `classify_environment_severity` (`bimguard_crevice_engine.py:235-242`) joins zone and system name, then searches for the phrases in `ZONE_TO_SEVERITY` (`:213-232`): "pool", "coastal", "marine", "external", "roof", "plant room", "boiler room", "pump room", "mechanical room", "cleanroom", "controlled", "normal", "office", "pharmaceutical", "laboratory" and others.

The parser's own mapping loses the words the engine is looking for. A plant room becomes `interior_conditioned`, a roof or external space becomes `urban_exterior`, and an office becomes `interior_dry`. None of those codes contains any engine phrase.

Every parser code, checked against the engine function:

| Parser code | Engine class | Severity |
|---|---|---|
| `swimming_pool` | T5_IMMERSION (matches "pool") | 1.00 |
| `coastal` | T4_PERSISTENT | 0.80 |
| `marine_splash` | T4_PERSISTENT (matches "marine") | 0.80 |
| `interior_conditioned` | BUILDING_SERVICES (no match) | 0.35 |
| `urban_exterior` | BUILDING_SERVICES (no match) | 0.35 |
| `industrial` | BUILDING_SERVICES (no match) | 0.35 |
| `interior_dry` (also the default) | BUILDING_SERVICES (no match) | 0.35 |

Only the `swimming_pool`, `coastal` and `marine_splash` codes, or a system name that happens to contain an engine phrase, can reach a class other than BUILDING_SERVICES. T0_DRY, T1_OCCASIONAL, T2_INTERMITTENT and T3_FREQUENT cannot be reached from a space name. On 1917, all 378 findings are BUILDING_SERVICES / 0.35.

## 6. Measured impact if the temperature were passed

The impact of passing `operating_temp_c` through `_cc_element`, with nothing else changed, was measured on project 1917:

| Measure | Current | With temperature | Change |
|---|---|---|---|
| CC-001 findings whose CCT term changes | — | 47 | 47 |
| CC-001 findings that change band | — | 17 | all **High → Medium**. These are Chilled Water elements at 6 °C: SS316 CCT term 0.733 → 0.480, composite 0.643 → 0.542. |
| CC-001 findings that rise a band | — | 0 | none |
| Critical findings | 0 | 0 | none appear or disappear |
| CC-001 High / Medium | 70 / 308 | 53 / 325 | −17 / +17 |
| Project 1917 total findings | **1,988** | **1,988** | unchanged |
| Project 1917 High | 168 | 151 | −17 |
| Project 1917 Medium | 1,206 | 1,223 | +17 |
| Findings carrying MIT-CC-001 (grade upgrade) | 70 | 53 | −17 |

Why the changes are so limited:

- An ungraded material scores 0.05 at any temperature.
- SS316 at 12 °C (0.627), 15 °C (0.667), 30 °C (0.867), 60 °C and 80 °C (1.000) all stay High. The maximum is 0.2625 + 0.40 + 0.0875 = 0.750, below the 0.80 Critical boundary, because geometry and environment are still constant.
- Only 6 °C moves SS316 below 0.55.
- MIT-CC-001 is triggered when the CCT term exceeds 0.60 (`select_cc_mitigation`, `:344`), so the 17 elements at 6 °C lose it. Being no longer High, they also lose MIT-CC-002, -003 and -004.

Passing the temperature therefore corrects the CCT term, but on its own it does not restore discrimination. Geometry and environment would still be constant.

## 7. Which projects are affected

| Project | Affected? | Reason |
|---|---|---|
| **1917** | **Yes** | 378 CC-001 scores. All three causes apply to every one of them (section 2). |
| 1540 | No change possible | The model carries no temperature property at all. Every CC-001 row (29,183 findings, all `data_quality`) is a `material_unresolved` note, so no banded crevice score exists for any of the three terms to reach. |
| 1542 | No change possible | The model carries no temperature property at all, and only SB-001 (seismic clearance) was run. CC-001 was not run. |

No frozen figure changes because of this record. Every CC-001 number already reported was produced with these defects in place, so it can be reproduced exactly from both `1450960` and `main`. Those numbers measure the software as it is, not the specified engine.

## 8. Which engines receive a temperature

| Engine | Temperature input | Where |
|---|---|---|
| **CC-001** | **None: the 20 °C default** | `_cc_element`, `phase_6c_corrosion_ui.py:301-311` (section 4) |
| MC-001 | The parser's value. `None` is preserved rather than defaulted, and an absent temperature is reported as missing. | Passed at `phase_6c_corrosion_ui.py:345`, classified at `app/engines/bimguard_mic_engine.py:302` |
| MM-001 | A resolved value: the IFC property, or a system-name inference recorded with source `system_inference` and low confidence | Resolved at `app/modules/ifc_reader/piping_producer.py:1882-1883`, read at `app/modules/comparator/material_media.py:308` |
| GC-001 | No temperature input | — |
| XM-001 | None, by design | `app/modules/comparator/cross_material.py:422` |

CC-001 is the only engine whose specification uses operating temperature but whose pipeline input omits it.

Two other places build a `CCElement` with a temperature. Neither is the analysis pipeline, and neither writes the findings text:

- `app/modules/comparator/compliance_runner.py:33` passes `info["operating_temp_c"]` or the element attribute, falling back to 20.0.
- `app/engines/demo_data.py:572` passes the demo data's own `temp` value.

## 9. Test coverage

**No test covers a temperature reaching CC-001 through `_cc_element`.** Four tests build `CCElement(operating_temp_c=…)` directly and so bypass the defect:

- `tests/test_engine_bcf_export.py:188` and `:198`
- `tests/test_corrosion_fallback_catalog.py:97`
- `tests/test_pipeline_tracker.py:210`

No test calls `classify_joint_type` or `classify_environment_severity` with the inputs the real pipeline produces: a `JT-nnn` code, or a parser environment code. All three breaks have therefore gone undetected by the test suite.

## 10. Verification method

- The 1917 model was rebuilt in memory from `scripts/generate_demo_mep_model.py` using the locked ifcopenshell 0.8.5.
- The rebuilt file hashes to SHA-256 `302dcad174e8b94d7196527365d95aae1596861f90457473ca7d74e451f30b54` (717,766 bytes, CRLF line endings).
- All 378 CC-001 scores were reconstructed from the formula in section 1 with geometry fixed at Tight 0.75, environment at BUILDING_SERVICES 0.35, and the CCT term at the material's 20 °C value. The maximum deviation from the stored scores was 0.000000, with 0 band mismatches.
- The same inputs were then re-evaluated with each element's stated `OperatingTemperature` in place of 20 °C to produce the figures in section 6.
- The joint-library measurements (section 3) were made by substring comparison against the seeded payload and by re-running classification with the key renamed.
- The environment table in section 5 was produced by calling `classify_environment_severity` on every value in `SPACE_TO_ENV` and on `DEFAULT_ENVIRONMENT`.

No backend was started, restarted or queried to produce any of these figures, and no database row was changed.

## 11. Demo build

The demo build `1450960` has all three defects, line for line:

- The engine reads `ifc_types` at `bimguard_crevice_engine.py:139`, and the loader writes `ifc_keywords` at `corrosion_rule_catalog.py:845`.
- `_cc_element` (`phase_6c_corrosion_ui.py:301-311`) is identical to `main`. It passes `joint_description=element.joint_type`, `zone_category=element.location_tag`, and no temperature.
- `CCElement.operating_temp_c` defaults to 20.0 at `bimguard_crevice_engine.py:380`.
- `SPACE_TO_ENV` (`ifc_parser.py:173-188`) and `ZONE_TO_SEVERITY` are identical to `main`.
- `finding_narrative.py:237` prints "against an operating temperature of {temp}".

Every CC-001 result shown in the demo was scored at JT-014 / Tight, 20 °C, and (on 1917) BUILDING_SERVICES. Every CC-001 finding shown there states the 20 °C default as the operating temperature. The demo build is frozen and was not changed.

## 12. Decision: document, do not fix

The scoring defects are recorded, not fixed. The reasons:

- **Passing the temperature alone would not restore the engine.** Geometry and environment would remain constant, so CC-001 would still not discriminate by joint or by environment (section 6).
- **A partial fix would move frozen, reported figures for little gain.** Passing the temperature would:
  - move 17 findings from High to Medium;
  - change the CC-001 showcase row from 70/308 to 53/325;
  - alter 47 finding descriptions and 17 mitigation lists;
  - change the export digests;
  - require a backend restart and a full re-warm of the demo cache, measured at about 2.5 hours from cold.

  All of that for an unchanged project total of 1,988.
- **A full fix would move all 378 scores** and needs design decisions that have not been made, notably an unvalidated joint code → geometry mapping (section 14).

**One factual error was corrected** rather than documented: the findings text asserted a model-derived operating temperature (section 13).

## 13. Correction made: the findings no longer claim a model temperature

`app/modules/phase_6/finding_narrative.py:237` (in `_describe_cc`) wrote every CC-001 finding's explanation as:

> "{material} has a critical crevice temperature of {cct} against an operating temperature of {temp} (ASTM G48 Method B)"

`{temp}` is always 20.0 °C (section 4), including for elements the IFC states at 6, 12, 15, 30, 60 or 80 °C. This was not an unexercised feature. It was a factual statement in every CC-001 finding, in exports and in BCF topics, and the source model contradicts it.

It now reads:

> "{material} has a critical crevice temperature of {cct}, assessed at the engine's default {temp}, not the element's stated temperature (ASTM G48 Method B)"

**This changes output text only.** The narrative is built in `_finding_issue` (`phase_6c_corrosion_ui.py:1128`), after the Issue's score, band and mitigation string have been set from the engine result. The narrative's return value is assigned only to `issue.description`, and no code derives a count, band, identifier or mitigation from `description`. `build_mitigations` reads `issue.mitigation`. The change was verified by an AST comparison of every changed Python file: the only executable difference is this string. Docstrings and comments were stripped before comparing.

Deliberately unchanged:

- **`compliance_runner.py:33` and `demo_data.py:572`** pass a real or demo temperature and do not produce this sentence (section 8).
- **`calculate_cct_adequacy`'s notes** ("Operating temp {operating_temp_c}°C …", `bimguard_crevice_engine.py:270`, `:275`, `:282`) are runtime strings, so they were not edited. They reach only `CCResult.cct_note`. That field is written by the engine's own CLI exporters (`_cc_bcf_issue`, `export_cc_asset_register`, called from its `__main__` demo at `:990-991`), not by the analysis pipeline. The function's docstring now states that the value is the default.
- **MC-001's and MM-001's temperature sentences** (`finding_narrative.py:143`, `:274`) state values those engines actually receive.

## 14. What a full fix would require

A fix is not being made. For the record, restoring the specified behaviour would need all of the following:

1. **Make the joint-library key names agree.** Change either the loader output or the engine reader so both use the same key. Renaming alone does nothing (section 3.3).
2. **Give the engine real joint evidence.** There are two options:
   - (a) Pass descriptive text (element name, type name, `PredefinedType`, `Pset_PipeFittingOccurrence.ConnectionType`, as `ifc_data_sources` specifies) and let the keyword search run.
   - (b) Look up the type directly by code. This depends on a code → geometry mapping that **has never been validated**. `IFC_TO_JOINT` assigns codes by IFC class, with comments from a different vocabulary. Read literally against the catalogue, it would classify every `IfcPipeFitting` as a butt weld (Open) and every `IfcPipeSegment` as a pipe clamp under insulation (Critical). Neither assignment is supported by any source or measurement.
3. **Agree one JT vocabulary,** or rename two of the three so that a code has only one meaning (section 3.5), including XM-001's use of JT-014.
4. **Pass `operating_temp_c` through `_cc_element`,** and decide what an absent temperature means. MC-001 preserves `None` and reports the gap. CC-001 would need an equivalent rather than a silent 20 °C.
5. **Reconcile the environment vocabularies.** Either the engine maps the parser's codes, or the parser passes the space text the engine searches. Then decide whether BUILDING_SERVICES should remain the silent fallback.
6. **Add tests** that run `classify_joint_type`, `classify_environment_severity` and `_cc_element` on the inputs the real pipeline produces, including a temperature reaching the engine.
7. **Correct the seeded database descriptions** with a new migration (section 15).
8. **Re-baseline.** Any of steps 1, 2, 4 or 5 moves CC-001 scores, and for 1917, steps 1 to 5 together would move all 378. Every CC-001 figure already reported would then describe the old build. A fix must produce new, separately dated figures and must not overwrite the frozen ones.

## 15. Inaccurate database descriptions: corrective migration (not written)

The applied migration `supabase/migrations/20260806180500_seed_static_data_assets.sql` is not edited. Its seeded text for asset `ruleset:BIMGUARD-CC-001` is inaccurate in the places below.

A corrective migration, `supabase/migrations/<UTCYYYYMMDDHHMMSS>_correct_cc001_scoring_input_descriptions.sql`, would need to:

- Update each field in both `content_json` and `content_text` of the `ruleset:BIMGUARD-CC-001` row in `public.static_data_assets`.
- Recompute `content_sha256` so it matches the new `content_text`.
- Change descriptive strings only. No key, value, weight, threshold, `risk`, `expected_score` or `typical_temp_c` figure may change, so that every frozen CC-001 score stays reproducible.
- Decide in that migration, and record there, whether to change `ruleset_version` (findings currently record `BIMGUARD-CC-001 v1.0.0`).

### 15.1 Joint library

| Line | Field | Current text | Proposed text |
|---|---|---|---|
| `:801` (formatted `content_text`), `:736` (inline `content_json` copy) | `joint_type_library.description` | "14-type joint library mapping IFC element types and joint descriptions to geometry class. JT-014 (unknown) defaults to Tight — conservative fallback when joint data is absent from IFC model." | "14-type joint library specifying a geometry class per joint type. Not currently executed: the engine reads `ifc_types` while this library stores `ifc_keywords`, and the pipeline supplies a joint code rather than descriptive text, so every element is classified JT-014 (Unknown / unclassified, Tight). See docs/defects/CC-001-scoring-inputs-inert.md." |
| `:885` | `pset_definition` property `CC001_JointTypeCode`, `description` | "Joint type code JT-001 through JT-014" | "Joint type code. In the current build this is always JT-014; JT-001 to JT-013 are specified but never assigned. See docs/defects/CC-001-scoring-inputs-inert.md." |

The `rules` table rows for joint types (`CC-001.JT.*`, written by `app/services/ruleset_seeder.py:543-552`) describe each type's label, geometry and risk. They make no claim about matching and do not need correcting.

### 15.2 Operating temperature and environment

| Line | Field | Current text | Proposed text |
|---|---|---|---|
| `:740` | ruleset `description` | "… Checks Critical Crevice Corrosion Temperature (CCT) adequacy of stainless steel grades against operating temperature, joint geometry class, and environment severity. The defining finding of CC-001: SS316 in a pool plant room scores 0.00 galvanic (GC-001) but 0.89 Critical on CC-001 — demonstrating that galvanic checking alone is insufficient." | "… Specified to check CCT adequacy of stainless steel grades against operating temperature, joint geometry class and environment severity. In the current build the analysis pipeline supplies none of the three from the model: CCT adequacy is assessed at a 20 °C default, joint geometry is always JT-014 (Tight), and environment severity is BUILDING_SERVICES unless the environment code is swimming_pool, coastal or marine_splash. The specified pool-plant-room example (SS316, 0.89 Critical) is not what the pipeline produces; through the pipeline SS316 with the swimming_pool code scores 0.806 Critical and in BUILDING_SERVICES 0.643 High. See docs/defects/CC-001-scoring-inputs-inert.md." |
| `:769` | `scoring_model.rationale` | "CCT adequacy receives highest weight (0.40) as it is the most material-specific determinant — whether the specified grade can resist crevice attack at the operating temperature is the central question. …" | Keep the text and append: "In the current build the pipeline does not pass the operating temperature, so this term is evaluated at a 20 °C default and varies only with material grade." |
| `:770` | `scoring_model.cct_adequacy_calculation` | "Linear interpolation: score 0.00 when operating temp is 20+ degrees below CCT (fully adequate). Score 0.60 when at CCT. Score 1.00 when 30+ degrees above CCT. …" | Keep the formula and append: "The analysis pipeline currently supplies no operating temperature; the engine's 20 °C default is used." |
| `:845`, `:852`, `:859`, `:866` | high-risk configuration `note` entries CC-HRC-002 to CC-HRC-005, each with a `typical_temp_c` of 25, 40, 15 or 45 °C | e.g. "Threaded joint (Critical geometry) combined with operating above CCT"; "CCT +50°C — only 5°C margin at 45°C operating temperature" | Keep each note and append: "(Engine-level scenario. Not reproducible through the analysis pipeline, which passes neither this temperature nor this joint type.)" |
| `:875` | `mitigation_catalogue["MIT-CC-006"]` | "Lower operating temperature below material CCT — review system temperature setpoints" | Keep the text and append: "(Not emitted by the current engine; CC-001 does not assess the element's actual operating temperature.)" |
| `:888` | `pset_definition` property `CC001_OperatingTemp_C`, `description` | "Operating temperature in degrees C" | "Temperature CC-001 assessed at, in degrees C. In the current build this is always the 20 °C default, not the model's operating temperature. See docs/defects/CC-001-scoring-inputs-inert.md." |
| `:902` | `ifc_data_sources.operating_temp` | `["Pset_PipeSegmentOccurrence.OperatingTemperature", "Pset_ZoneCommon.SetPointTemperature"]` | Keep the list and record alongside it: "Specified source. `ifc_data_sources` is not read by any code; the parser reads `OperatingTemperature` into `ServiceElement` but CC-001 does not receive it." |

## 16. Live claims corrected

In each case below, the claim was corrected to describe what the software actually does. Joint type, operating temperature and environment all remain part of CC-001's specification. The correction is that the pipeline does not supply them.

### First version of this record (joint library)

- `frontend/src/lib/components/PipingChecksExplainer.svelte` (CC-001 "What it needs from the model")
- `docs/demo/piping-checks-plain-english.md` (same text)
- `frontend/src/lib/glossary.ts` (CC-001 description)
- `docs/client-qa/Q18_Selecting_Which_Corrosion_Engines_Run.md` (engine table row)
- `scripts/build/build_deck_d.py` (Engine B "Specified" column; the deck file was not rebuilt)
- `app/modules/ifc_reader/piping_schema.py` (joint enum header comment)
- `docs/piping_schema_spec.md` ("Joints and connectivity")
- `app/engines/bimguard_crevice_engine.py` (`classify_joint_type` docstring)
- `app/services/ruleset_seeder.py` (joint-type seeding comment)

### This widening (temperature and environment)

- `app/modules/phase_6/finding_narrative.py:237`: findings text (section 13). This is the only executable change.
- `frontend/src/lib/glossary.ts:215`: the CC-001 description now also says the pipe is assumed to run at 20 °C and most spaces fall into one default environment class.
- `frontend/src/lib/components/PipingChecksExplainer.svelte` ("What the check asks", "What it needs from the model", "Example") and `docs/demo/piping-checks-plain-english.md:49-53` (same text):
  - the check is described as *designed to* compare CCT with operating temperature and environment;
  - the inputs actually used are stated;
  - the dry-void example now says the specified outcome is Low but the flanges score High today, since standard stainless grades score High in BUILDING_SERVICES (section 2).
- `docs/client-qa/Q01_What_Is_Piping_Corrosion_Analysis.md:29`: CC-001 sentence annotated.
- `docs/client-qa/Q03_MM001_Material_Media_Versus_Other_Engines.md:67`: CC-001 table row annotated.
- `docs/client-qa/Q18_Selecting_Which_Corrosion_Engines_Run.md:25`: row extended to temperature and environment.
- `scripts/build/build_deck_d.py:51` ("0.40 × CCT margin"): annotated with a code comment only. The slide text and the deck file were not changed or rebuilt; the next deck rebuild should carry the caveat.
- `app/engines/bimguard_crevice_engine.py`: docstrings only. `calculate_cct_adequacy` now states that the temperature is the default, and `classify_environment_severity` states the vocabulary mismatch. The runtime note strings at `:270`, `:275` and `:282` were not changed (section 13).
- `docs/architecture.md:171`: the "Joint crevice geometries and critical crevice temperatures (CCT)" evaluator bullet annotated.
- `docs/planning/post-fmp-backlog.md:28-31`: the backlog line now names the temperature and environment inputs as well as the joint type.

Evidence records dated before this change that already describe the joint-library defect accurately were left as they are: `docs/validation/engine-showcase-2026-09-08/README.md:169-181` and `docs/validation/data/CC-001_validation_demo_asset_register.csv`.

## 17. Not remediated here

The files below contain inaccurate or incomplete claims about CC-001's inputs. They are left unchanged on purpose: the thesis is out of scope for this change, and the other files are historical records, planning documents or generated output. They are listed so that nobody treats them as describing working behaviour.

### Thesis: `docs/thesis/MAICEN_M10_Final_Thesis_Mark_Shane_Haines.docx`

- **§9.3 "Joint type library"**: "CC-001 includes a library of 14 joint types (JT-001 through JT-014) mapping IFC element type classifications to geometry classes. This library provides the mechanism by which the engine assigns a geometry risk multiplier … The IFC element type — IfcPipeFitting.PredefinedType, valve classification, or connection type — is used as the key to look up the corresponding joint type and geometry class." This is inaccurate. No lookup takes place, and `PredefinedType` is never read.
- **Input list**: "Joint type — from element type classification mapped to the GC-001 and CC-001 joint type library". This is inaccurate. The mapped code never reaches a geometry class.
- **Pset description**: "GeometryClass — the joint type library classification (string: JT-001 through JT-014)". In practice this is always JT-014 / Tight.
- **Three-engine discussion**: "Low on CC-001 (butt-welded joints, no crevice geometry)" and "CC-001 will not flag it because butt-welded carbon steel joints do not present significant crevice geometry". CC-001 cannot tell a butt weld from any other joint, and through a parser environment code no CC-001 element can score Low (section 2).
- **Engine summary table**: "Data-quality issues dominant; risk bands only where joint type can be inferred from fitting class". Joint type is never inferred into a geometry class.
- The thesis does describe accurately that "CC-001 reported a crevice geometry of "Tight" and a joint type of JT-014 for an element that declared no joint." What it leaves out is that JT-014 is also given to elements that do declare a joint.
- Wherever the thesis describes CC-001's CCT term as comparing the alloy against the element's operating temperature, or the environment term as distinguishing plant rooms, roofs or dry voids, that describes the specification, not the pipeline (sections 4 and 5).

### Second thesis copy: `docs/MAICEN_M10_Final_Thesis_Mark_Shane_Haines.docx`

An earlier copy with the same §9.3 text, the same input-list line, the same "GeometryClass … JT-001 through JT-014" line and the same butt-weld examples. Not remediated.

### Project memory, case study, planning and validation records

- `docs/BIMGuard_Project_Memory_v2.md:87`: gives the CC-001 formula `0.35 × geometry_risk + 0.40 × CCT_adequacy + 0.25 × environment_severity` without noting that geometry and environment are constant and CCT is taken at 20 °C. The worked-example placeholder at `:158` asks for "actual component scores"; any such example produced through the pipeline will show these constants.
- `docs/ss316_feedback_loop_case_study.md:150-176`: scores the SS316 plant-room element with `operating_temperature_c` 28.0, `environment_class` T3_CHLORIDE and joint `JT004_FLANGED_FULL_GASKET` on a `PipingElement` fixture, and cites the engine-level scenario CC-VAL-001 (35 °C, Critical). The analysis pipeline does not pass that temperature, joint or environment to CC-001, so the pipeline would not reproduce the case study's inputs.
- `docs/planning/integration_plan_mm_xm.md:275`: lists CC-001 outputs `crevice_geometry`, `cct_adequate` and `joint_type` as meaningful fields. In the current build the first and last are constant, and the second is taken at 20 °C.
- `docs/validation/engine-showcase-2026-09-08/` (README and run records): the CC-001 rows and every `sample_50.csv` explanation under `runs/test_hospital_mep_demo/CC-001/` and `ALL5/` carry the old sentence "against an operating temperature of 20.0 °C". These are dated evidence of the output at the time and are left as recorded.
- `docs/validation/appendix_b_validation.md:131`: lists CC-001's required inputs as `material+joint_type+operating_temperature_c`. The pipeline reads the material only.

### Archived, experimental and submission files

- `docs/archive/index.html:604-605`: "CC-001: implement CCT table …, 14-type joint library (JT-001 to JT-014), 7 environment severity classes" and the weighted composite, shown as planned tasks. They imply completion; in behaviour, neither the joint library nor the environment classes (beyond three codes) are reached.
- `docs/experimental/bimguard-frontend-prototype-v1.html:916`: ruleset table lists CC-001 with "14 joint types".
- `docs/submissions/BIMGuard_3rd_Submission_REVISED.md:187`: gives the CC-001 formula as if every term were live. `:198` says "a 14-member `JointType` enum matching a dedicated `JT-001`–`JT-014` ruleset", which is false (section 3.5).

### Generated corpora

`docs/bimguard_corrosion_rules.md` (e.g. `:24047`, `:48425`, `:51156`) and the other `docs/bimguard_*_rules.md` corpora contain copies of the pre-correction source text, including the false "Keys match JT-001 through JT-014" claim and the old findings sentence. They are generated output from `scripts/compile_for_notebooklm.py` and were not hand-edited or rebuilt. They will pick up the corrections the next time they are generated.
