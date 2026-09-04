# Environment classification: T1 indoor default with provenance

Date: 2026-09-04
Scope: `app/modules/ifc_reader/piping_producer.py`, `app/modules/ifc_reader/piping_schema.py`,
`scripts/trace_environment_coverage.py`, `tests/test_piping_producer.py`,
`docs/piping_schema_spec.md`.
Data: `docs/validation/data/environment-coverage-baseline.json` (reading only) and
`docs/validation/data/environment-coverage.json` (with the default), both over the 34
IFC models under `test-models/models/`.

## What the brief got right and wrong

The brief's correction stands: `EnvironmentClass` is the atmosphere around the pipe, the
media axis is `media_for_system()`, and inferring "potable water, therefore marine" would
have pushed every indoor hospital pipe to `T4_marine` (severity 1.00 in the MM-001 pack).

Two of its premises did not match the code:

* Environment classification already existed. `classify_environment()` maps space,
  storey and system names onto the enum, and `PipingElement.environment_source` was
  already there. What was missing was the default and its provenance.
* MM-001 already gates on environment. Its rule pack pins `unclassified` to a null
  severity, and `material_media._assess` raises an `environment_unclassified`
  data-quality issue for it. Severity values therefore stay in the pack
  (`T1_indoor_damp` = 0.20, the CC-001 ladder); no severity map was added to code.
  CLAUDE.md forbids hard-coding such tables.

## Change

Environment now resolves in three tiers, mirroring material resolution, each tagged on
the element:

| `environment_source` | When | `environment_confidence` |
|---|---|---|
| `ifc_property` | an `EnvironmentClass` / `EnvironmentalClass` / `CorrosivityCategory` / `AtmosphericEnvironment` property parses as a T0–T5 code or enum value | high |
| `inferred from spatial names` | `classify_environment()` matched the space, storey or system name | medium |
| `default_indoor` | nothing else resolved; `T1_indoor_damp` applied, extraction warning added | low |

`resolve_environment()` implements the ladder; `parse_environment_class()` reads the
property; `environment_coverage()` counts the split and one INFO line per model reports
it (per-element detail at DEBUG). The default is switchable off with
`environment_default=False` on both producer entry points, which reproduces the previous
behaviour exactly and is what the baseline below was measured with. A property that
says "unclassified" is not treated as a classification.

## Coverage on the validation models

Reading only (`--no-default`), 34 models:

| | Elements | % |
|---|---|---|
| Total piping elements | 93,457 | |
| From IFC property | 0 | 0.0 |
| From spatial names | 783 | 0.8 |
| Unclassified | 92,674 | 99.2 |

The 783 spatial hits are 352 `T1_indoor_damp`, 305 `T0_dry`, 67 `T2_humid`, 59
`T3_chloride`. No model carries an environment property. The MEP models with the most
elements (West Riverside mechanical, 18,488; Clinic Plumbing, 6,587) have no `IfcSpace`
containment at all, and their storey names are floor ids.

With the default on (`docs/validation/data/environment-coverage.json`):

| | Elements | % |
|---|---|---|
| Total piping elements | 93,457 | |
| From IFC property (high) | 0 | 0.0 |
| From spatial names (medium) | 783 | 0.8 |
| Defaulted to `T1_indoor_damp` (low) | 92,674 | 99.2 |
| Unclassified | 0 | 0.0 |

Coverage is 100 %, but 99.2 % of it is an assumption, and every one of those elements
says so in `environment_source`, `environment_confidence` and its extraction warning.
The class distribution after the default is 93,026 `T1_indoor_damp`, 305 `T0_dry`, 67
`T2_humid`, 59 `T3_chloride`; nothing lands in the marine or industrial classes.

## Effect on the comparators

Measured before (`environment_default=False`) and after on two real models.

**MM-001** (`material_media.compare`, Clinic Plumbing, 6,587 elements):

| Data-quality check | Before | After |
|---|---|---|
| `material_normalisation` | 4,024 | 4,024 |
| `environment_unclassified` | 2,563 | 0 |
| `temperature_missing` | 0 | 1,693 |
| `unmapped_pairing` | 0 | 870 |
| Scored (`MM-001.01`) | 0 | 0 |

The environment gate opened and the next gate caught the same elements: every one of
them lacks an operating temperature, so MM-001 still scores nothing. No false positives
are possible from the default alone; MM-001 fires only where material, environment and
temperature are all present, and temperature coverage is 0 %. The 870 unmapped pairings
(cast iron and similar against cold water) were previously hidden behind the
environment gate and are now visible as their own data-quality finding.

**XM-001** (`cross_material.compare`): unchanged, 3,678 `material_not_in_series` on
Clinic Plumbing before and after; its material gate fires before the environment term.

**Path A engines** (CC-001, MC-001) through `orchestrate_workflow`: unchanged, they
derive their own environment from zone text and do not read `environment_class`.

Spot-check, Clinic Plumbing, first domestic-cold-water element:

```
system=domestic_cold_water  media=cold_water  material=Copper_C12200
environment=T1_indoor_damp  source=default_indoor  confidence=low
operating_temperature_c=None
warnings: material assumed from system (provisional convention);
          environment defaulted to T1_indoor_damp: no atmospheric metadata in model (low confidence)
```

## Tests

`tests/test_piping_producer.py` gains `TestEnvironmentProvenance` (property parsing,
the three tiers, the media-never-drives-atmosphere case, the disable switch) and
`TestEnvironmentCoverageOnModel` on `data/test_hospital_mep_scenario.ifc` (100 %
classified with provenance, defaults are low confidence and warned, switching the
default off reproduces the raw reading, the summary line reports the count).

| Run | Result |
|---|---|
| `tests/test_piping_producer.py` | 121 passed |
| All ten test files importing the producer or comparators | 358 passed |

Ruff reports only pre-existing docstring findings in `piping_schema.py`.

## Tri-state gates for MM-001

| Gate | Coverage on the validation set | Source |
|---|---|---|
| Material | 33.9 % | IFC plus system inference |
| Environment | 100 % classified, 0.8 % read, 99.2 % defaulted | this change |
| Operating temperature | 0 % | not extracted; documented future work |

## Not done

* The evaluation harness moved to `bim-guard-evaluation`; the 38-model sweep was not
  rerun from here. The two-model comparator measurements above stand in for it.
* Operating temperature extraction, without which MM-001 cannot score any element on
  these models.
