# Environment defaults: the two paths a corrosion finding can inherit

*Recorded 2026-09-05. Line references are against `bf54975`.*

BIM-Guard resolves an element's environment class twice over, by two unrelated
code paths, depending on which element shape a mechanism consumes. Each path has
its own default, and the two defaults are different values with different
meanings. A finding that reaches a reviewer carries no trace of which path
produced it unless the provenance fields are read.

This document states both paths, because the distinction matters to any claim
about what a band measures and it was not written down anywhere.

## Path A — `PipingElement` → `T1_indoor_damp` (MM-001, XM-001)

The piping producer resolves an environment class with explicit provenance, and
falls back to a named constant when nothing else answers.

| Step | Location |
| --- | --- |
| Resolver | [`piping_producer.resolve_environment`](../../app/modules/ifc_reader/piping_producer.py#L683) |
| Default constant | [`DEFAULT_ENVIRONMENT_CLASS = EnvironmentClass.T1_INDOOR_DAMP`](../../app/modules/ifc_reader/piping_producer.py#L632) |
| Enum value | [`T1_INDOOR_DAMP = "T1_indoor_damp"`](../../app/modules/ifc_reader/piping_schema.py#L111) — 50–80% RH, indoor unheated |
| Source marker | [`ENVIRONMENT_SOURCE_DEFAULT = "default_indoor"`](../../app/modules/ifc_reader/piping_producer.py#L623) |
| Consumed by | `material_media._environment_key` and `cross_material._environment_key` |

Three outcomes are distinguished and recorded on the element as
`environment_source` / `environment_confidence`: read from an IFC property
(`ifc_property`, high), inferred from spatial names
(`inferred from spatial names`, medium), or defaulted (`default_indoor`, low).
`environment_coverage()` counts the split, and deliberately does not merge the
defaulted count into the classified one.

## Path B — `ServiceElement` → `interior_dry` → `E2_NORMAL` / `BUILDING_SERVICES` (GC-001, CC-001, MC-001)

This path defaults **twice**, in two different modules, and the second default
does not know the first one happened.

**B1 — the parser.** [`resolve_environment_from_space`](../../app/modules/ifc_reader/ifc_parser.py#L239)
keyword-matches the space name plus storey name against `SPACE_TO_ENV`. No match
yields [`DEFAULT_ENVIRONMENT = "interior_dry"`](../../app/modules/ifc_reader/ifc_parser.py#L50),
marked [`ENVIRONMENT_SOURCE_DEFAULT = "default_indoor"`](../../app/modules/ifc_reader/ifc_parser.py#L40)
at low confidence ([the fallback return](../../app/modules/ifc_reader/ifc_parser.py#L258)).
The value lands on `ServiceElement.location_tag`.

**B2 — the engine.** `phase_6c` passes that tag through as `zone_category`
([GC-001](../../app/modules/phase_6/phase_6c_corrosion_ui.py#L235),
[CC-001](../../app/modules/phase_6/phase_6c_corrosion_ui.py#L251)). Each engine
then re-resolves it against its *own* table and falls back again when it
recognises nothing:

- [`classify_environment`](../../app/engines/bimguard_corrosion_engine.py#L220) →
  [`return "E2_NORMAL"`](../../app/engines/bimguard_corrosion_engine.py#L240)
- [`classify_environment_severity`](../../app/engines/bimguard_crevice_engine.py#L235) →
  [`return "BUILDING_SERVICES"`](../../app/engines/bimguard_crevice_engine.py#L242)

MC-001 does not classify an environment at all; it carries `zone` only as a
label on the result.

The consequence: `"interior_dry"` is not a key in either engine's zone table, so
a B1 default reliably becomes a B2 default. A GC-001 band on an element whose
model named no recognisable space is computed against `E2_NORMAL` — a value
chosen by the engine, from a tag chosen by the parser, from a model that said
nothing.

## Why this is not merely cosmetic

Measured over three models on `bf54975`, via
`scripts/batch_corrosion_runs.py`'s in-process path:

| Model | Elements | `environment_source` distribution |
| --- | --- | --- |
| `test_hospital_mep_scenario.ifc` | 4 | 11 spatial-inferred, 3 defaulted |
| `west_riverside_hospital_plumb_ifc4.ifc` | 8,539 | **29,183 findings, 100% `default_indoor`** |
| `Clinic_Plumbing.ifc` | 6,587 | 27,487 defaulted, 234 spatial-inferred |

On `west_riverside_hospital_plumb_ifc4.ifc` every one of 29,183 findings rests
on both an absent material (`material_source: absent`) and a defaulted
environment. The bands are real outputs of the engines; they are not
observations about that building's environment, because that building's IFC
carried none. Any accuracy figure computed over such a model measures the
defaults, not the model.

## Where a reader can check this per finding

Since `cd2764f`, every corrosion Issue carries `material_source`,
`material_confidence`, `environment_source` and `environment_confidence` in its
`metadata` (MM-001 adds `temperature_*`; XM-001 prefixes both ends of a couple
`anode_` / `cathode_`). The distinction above is therefore visible on the
finding itself rather than only in this document.
