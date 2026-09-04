# Piping element schema — data contract for Module2 ↔ Module4

**Owner of this doc:** piping compliance team
**Implements:** `app/modules/piping_schema.py`
**Schema version:** 1.0.0

This document is the human-readable companion to `piping_schema.py`. Sam needs this to implement `IFCReader`'s piping extraction path. The piping comparators in `ComplianceComparator` consume the same structure on the other side.

If the code and this doc disagree, the code wins — but flag the drift in a PR so we can fix the doc.

---

## What this is

A single dataclass, `PipingElement`, representing any piping-related IFC entity after normalisation. Pipe segments, fittings, valves, flanges, pumps, tanks, AHUs, strainers — all become `PipingElement` with different `subtype` values.

The schema supports four compliance domains:

1. Corrosion (GC-001 galvanic, CC-001 crevice) — material, environment, joint, area
2. Access and maintenance clearance — subtype, position, orientation, access direction
3. Pipe centre-to-centre spacing — centerline, diameter, insulation, system
4. Seismic bracing reservation — centerline, mass, system

Not every field is populated for every element. The nullability policy is at the end of this doc.

---

## Units

SI throughout, with field name suffixes as the units indicator:

| Suffix | Unit | Example |
|---|---|---|
| *(none)* | metres | `bbox.min.x` |
| `_mm` | millimetres | `nominal_diameter_mm` |
| `_c` | degrees Celsius | `operating_temperature_c` |
| `_kg` | kilograms | `mass_filled_kg` |
| `_bar` | bar | `design_pressure_bar` |
| `_m2` | square metres | `wetted_surface_area_m2` |

If the source IFC uses different units (imperial, mixed, or Revit's internal feet), Module2 converts before populating. No mixed units below this line.

---

## Coordinate system

World coordinates from the IFC file via ifcopenshell. Z is up. Units are metres. If the IFC uses a local coordinate system (common in federated models with linked files), Module2 applies the transformation before populating `bbox`, `centroid`, and `centerline.points`.

Orientation vectors (`orientation_vector`, `access_direction`) are unit vectors in the same world frame. A valve with its handwheel facing the south wall has `access_direction = Point3D(x=0, y=-1, z=0)`.

---

## Material normalisation

`material` must be one of the values in `CANONICAL_MATERIALS` (defined at the top of `piping_schema.py`). Corrosion rule packs key off these strings case-sensitively, so matching matters.

Module2 is responsible for translating messy real-world IFC material strings to canonical keys. Examples of what Module2 should accept:

| IFC `Material.Name` | Normalised `material` |
|---|---|
| "Stainless Steel, Grade 316" | `SS316` |
| "316L Austenitic Stainless" | `SS316L` |
| "SUS316" | `SS316` |
| "Copper C12200" | `Copper_C12200` |
| "Copper — drawn" | `Copper_C12200` |
| "Galvanised Steel, Hot Dip" | `GalvanisedSteel` |
| "Unknown" or empty | `Unknown` + warning |

Store the original string in `material_raw` for debugging. If normalisation is uncertain, use `Unknown` and add a note to `extraction_warnings` — the comparators will emit a data-quality issue rather than silently mis-classify.

Extending the canonical set is fine but must be done by PR to `piping_schema.py` so the corrosion rule packs can be updated in lock-step.

---

## Environment classification

`environment_class` uses the EN ISO 15329 wetting classes, aligned with the existing `crevice_corrosion_ruleset.json`:

| Class | Meaning | Typical space |
|---|---|---|
| `T0_dry` | <50% RH, indoor heated | office, corridor |
| `T1_indoor_damp` | 50–80% RH, indoor unheated | service riser, ceiling void |
| `T2_humid` | >80% RH or condensing | kitchen, laundry |
| `T3_chloride` | pool halls, coastal <5 km | pool plant, swimming hall |
| `T4_marine` | direct spray zone | exposed external, within 500 m of sea |
| `T5_industrial` | aggressive chemical atmosphere | chemical store, dosing room |
| `unclassified` | cannot determine | Module2 fallback |

`environment_class` describes the **atmosphere around the pipe** (rooftop, coastal, pool hall, indoor), not the fluid inside it. The media axis is `media_for_system()`, and the environment is never derived from it: potable water says nothing about the room.

The producer resolves it in three tiers, mirroring material resolution, and records the tier in `environment_source` with a matching `environment_confidence`:

| `environment_source` | Meaning | `environment_confidence` |
|---|---|---|
| `ifc_property` | an `EnvironmentClass` / `EnvironmentalClass` / `CorrosivityCategory` / `AtmosphericEnvironment` property on the element, parsed as a T0–T5 code or enum value | `high` |
| `inferred from spatial names` | `classify_environment()` over the space, storey and system names ("Pool Hall", "Basement Plant Room") | `medium` |
| `default_indoor` | nothing to go on, so `T1_indoor_damp` was applied as the safe indoor default, with an extraction warning | `low` |
| `None` | left `unclassified` — only when the caller passes `environment_default=False` | `None` |

MEP discipline models carry no atmospheric metadata (most have no `IfcSpace` at all and their storey names are floor ids), so on the validation set the reading alone classifies under 1 % of elements and the default carries the rest. A default is an assumption, not a measurement: consumers that need to distinguish the two must check `environment_source`, and `scripts/trace_environment_coverage.py` reports the split per model.

---

## Geometry

`bbox` is the axis-aligned bounding box of the element, always populated. `centroid` is the centre of the bbox. Both use metres in world coords.

`centerline` is the ordered centerline path — populated for `pipe_segment` and `fitting` subtypes only. For straight pipes, two points. For bent or curved runs, additional interior points. The `total_length_m` property computes the polyline length.

`orientation_vector` is a unit vector indicating the principal axis of directional equipment — pump discharge, fan axis, valve stem axis. Populated for subtypes where direction matters.

Equipment subtypes (valve, pump, tank, etc) use `bbox` + `orientation_vector` + `access_direction`. They do not carry centerlines.

---

## Joints and connectivity

`joint_type` identifies the joint at the element's connection (if the element is itself a joint, like a flange or union). Values match `JT-001` through `JT-014` in `crevice_corrosion_ruleset.json`. See that file for the geometry class (open / moderate / tight / critical) of each.

`joined_to` is a list of GUIDs of directly-connected neighbouring elements. A pipe segment typically has two entries (upstream and downstream). A tee has three. A dead-end blind flange has one.

Module2 populates `joined_to` from IFC's `IfcRelConnectsPorts` and `IfcDistributionPort` relationships.

---

## Nullability policy

Fields are Optional where real IFC data is frequently missing. The rule for comparators: handle None gracefully, emit a Low-severity issue with `mechanism="data_quality"`, never crash.

Required for all elements:
- `id`, `ifc_class`, `subtype`, `bbox`, `centroid`

Required for pipe_segment and fitting:
- `centerline`

Required for pipe_segment specifically:
- `nominal_diameter_mm`

Required for corrosion comparators to run:
- `material` (non-`Unknown`), `environment_class` (non-`unclassified` — always satisfied when the T1 default is on; check `environment_source` for whether it was read or assumed)

Required for seismic bracing:
- `centerline`, `mass_filled_kg`, `system`

Required for clearance:
- `bbox`, `requires_operator_access`, `access_direction`, `access_clearance_required_m`

If required fields are missing for a given comparator, the comparator skips the element and emits one data-quality issue pointing at it.

---

## Versioning

`SCHEMA_VERSION = "1.0.0"` at the top of `piping_schema.py`.

Bump rules:
- **Patch** (1.0.0 → 1.0.1): docstring changes, clarifications, example updates
- **Minor** (1.0.0 → 1.1.0): new optional fields, new enum values, new subtype literals
- **Major** (1.0.0 → 2.0.0): renaming, removing, changing types, tightening nullability, reordering enums

Any minor or major bump requires:
- CHANGELOG entry
- Notification to Sam and the piping team in the group channel
- Migration plan if the comparators need updates

Never modify the enum definitions by reordering or deleting — only append. Enums are string-valued so new members won't break old data.

---

## Examples

`piping_schema.py` includes three fixtures at the bottom:

- `example_ss316_pipe_in_plant_room()` — a DN150 stainless header in chlorinated plant room, fully populated for corrosion checking
- `example_valve()` — a DN80 ball valve with operator access requirements
- `example_pump()` — a horizontal centrifugal pump on the plant room floor

Run `python3 -m app.modules.piping_schema` to validate the examples and see a JSON dump. The smoke test will fail loudly if any example violates `validate()`, so the examples serve as tests for schema changes.

---

## Integration notes for Sam

Module2's piping extraction path needs to:

1. Iterate `ifcopenshell.open(path).by_type("IfcFlowSegment") + by_type("IfcFlowFitting") + by_type("IfcValve") + …` (full list of piping-related IFC classes is in the corrosion engine — reuse that)
2. For each entity, build a `PipingElement` by populating the fields above
3. Call `validate(element)` on each; log warnings but don't drop invalid elements — let the comparators decide
4. Return `list[PipingElement]`

Material normalisation and environment classification can live in helper functions inside `app/services/ifc_parser.py` to keep Module2 itself thin.

Questions: piping channel in Slack, or direct message.
