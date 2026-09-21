# Q11: What does ARCH Compliance check?

## The Question

> "We are doing a 40-unit residential scheme and the planning consultant wants a
> pre-submission check that we have not made any obvious code mistakes in the
> layouts. I know BIMGUARD does corrosion and seismic. What does the architecture
> analysis actually look at — is it checking rooms, or doors, or what?"

## The Answer

It checks elements against a rule pack, and the pack is deliberately
element-oriented rather than room-oriented, because that is the level at which an
IFC carries reliable data. Each rule names an IFC class it targets
(`IfcStairFlight`, `IfcDoor`, `IfcWindow`, `IfcWall`, `IfcRailing`, `IfcRamp`,
`IfcSlab`, `IfcSpace`, `IfcAlarm`, `IfcSanitaryTerminal`), a property to read,
an operator, and a threshold — and the engine evaluates every instance of that
class in the model against it. So a "room too small" finding is really an
`IfcSpace` whose `Height` or `Width` property failed a numeric comparison, and a
"stair non-compliant" finding is an `IfcStairFlight` whose `RiserHeight` fell
outside a permitted range.

The baseline shipped ruleset is **47 rules** across two packs:
`BUILDING-CODE-PART9` (31 rules) covering the dimensional and life-safety
requirements, and `BUILDING-CODE-PART9-EXT` (16 rules) covering property
completeness and classification. Your project's live rule count will be higher if
rules have been extracted from project-specific documents or a custom ruleset has
been added — the rules live in the database, not in the code, so the pack is a
starting point rather than a ceiling.

What the baseline pack covers, concretely:

**Vertical circulation** — minimum stair width (860 mm), headroom over flights
and landings (1950 mm), riser height range (125–200 mm), tread run range
(255–355 mm), maximum flight height (3700 mm), maximum risers and treads per
flight (21), landing width and landing slope (max 1:50), winder set turn angle
(max 90°), individual winder tread angles (30°–45°), and minimum plan separation
between winder sets (1200 mm).

**Egress and life safety** — egress door clear width (800 mm) and height
(1980 mm), bedroom egress window clear opening area (0.35 m²), height (380 mm)
and width (450 mm), guard height at floor edges, stairs, landings and balconies
(900 mm), handrail height above nosings (865–1070 mm), fire and CO alarm
`PredefinedType` declaration.

**Fire separation** — garage-to-dwelling separation walls must declare a
`FireRating`, party walls between dwelling units must declare one and must meet a
minimum 45-minute resistance, and limiting distance from exterior wall face to
property line must be calculated.

**Accessibility** — accessible ramp slope (max 1:12), ramp clear width
(1100 mm), accessible corridor and aisle clear width (1100 mm), non-skid ramp
surface declaration.

**Room specification** — habitable room minimum ceiling height (2400 mm),
bathroom and utility room minimum ceiling height (1950 mm), space occupancy type
and net floor area declaration.

**Model quality** — the extended pack is largely about whether the model can be
checked at all: doors must declare `Width`, `IsExternal` and `OperationType`;
spaces must declare `LongName`, `OccupancyType` and `NetFloorArea`; walls and
slabs must declare `IsExternal`; interior doors must connect exactly two modelled
spaces and exterior doors exactly one; plumbing fixtures and alarms must declare
`PredefinedType`. These are graded `informational` rather than `mandatory`, and
they are the ones worth fixing first — every one of them is a property some other
rule needs in order to produce a verdict rather than silence.

## Rule Types and Severities

Each rule declares a `rule_type`, which determines how it is evaluated:
`numeric_comparison` (a threshold and an operator), `numeric_range` (a min and a
max), `spatial_clearance` (a geometric dimension), `prohibition` (a property must
exist, or a condition must not occur), `standard_conformance`,
`deemed_to_comply`, `table_lookup` and `tiered`. Rules can also carry an
`applies_when` condition — the interior/exterior door rules use it — so one class
can carry different requirements by context.

Severity is `mandatory`, `recommended` or `informational`. That distinction is
the first filter to apply when reading a report: `mandatory` findings are code
exceedances, `recommended` are good-practice, and `informational` are almost
always model-completeness rather than design defects.

## Building Type

The baseline pack is written for a Part 9-style residential and small-building
scope — the stair, egress window, party wall and dwelling-unit separation rules
make that explicit. It is a reasonable default for your 40-unit residential
scheme. It is **not** a hospital, office or industrial pack, and applying it
unchanged to those programmes produces both false confidence (no rules for the
things that matter in that programme) and noise (dwelling-unit rules firing on a
building with no dwelling units). See Q15 for how coverage varies by building
type, and Q14 for adding a programme-specific ruleset.

## When This Analysis Applies

- Pre-submission checking on residential and small-building schemes, which is
  your case.
- Design-stage quality gates, particularly at the point where layouts stabilise
  and before the model is issued for coordination.
- Model quality auditing before an IFC is issued to another party — the extended
  pack is effectively an IFC completeness check with code references attached.
- Handover and asset-information validation, where property completeness is
  contractually required.

## What the Report Contains

Findings share the same shape as the corrosion and seismic results, so one
exporter and one issue schema serve all three. Per finding: the element
`GlobalId`, the rule id and its clause reference, the property that was read, the
value found against the value required, the risk band, and the mitigation text.

Architecture findings reach the report through the orchestrator's Architecture
theme rather than through the corrosion pipeline, and they arrive as flat
dictionaries which are adapted into the common issue shape. The practical
consequence is that the progress stages you see for a corrosion run do not appear
for an architecture run — it reports progress through its own logging instead.
Nothing is missing from the result; the live stage display simply does not apply.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "From [the applicable building code and its current amendments — name it
> explicitly, e.g. the Bauordnung and Musterbauordnung for a German scheme],
> extract every quantitative requirement applying to multi-unit residential
> buildings for: stair width, riser and tread dimensions, headroom, guard and
> handrail heights, egress door and window dimensions, corridor widths, minimum
> habitable room ceiling heights and floor areas, and fire resistance periods for
> dwelling-unit separating construction. For each, give the exact clause number,
> the value with its unit, the operator (minimum, maximum, range), and the
> occupancy or building class the requirement is conditioned on. List separately
> any requirement expressed as a table lookup rather than a single value."

**Purpose.** Produce a sourced table that maps directly onto the rule schema —
`target`, `property_name`, `operator`, `check_value`/`value_min`/`value_max`,
`unit`, `ref`, `severity` — so a reviewer can author a jurisdiction-specific pack
without re-reading the code from scratch.

**Not for.** Asking whether a specific room in your model complies. NotebookLM
does not see the model, and a compliance statement without a traceable rule and a
measured property value is not evidence of anything.

## Export Options

- **BCF 2.1** — one topic per finding with a viewpoint on the element. The right
  format for the design team.
- **CSV** — the most useful format for architecture work, because findings group
  by rule far more than by element, and a pivot by `rule_id` turns a long list
  into a short list of decisions.
- **JSON** — full result with `issue_stats`, for a quality dashboard.

## Next Steps for Your Project

1. Fix the `informational` model-completeness findings first. They are cheap, and
   each one unblocks a rule that currently cannot produce a verdict.
2. Then read the `mandatory` findings, grouped by `rule_id`. Forty units means
   the same layout repeated, so one failing rule is one design decision.
3. Confirm the pack matches your jurisdiction before treating any finding as a
   code position. The baseline pack's clause references are its own; your
   planning consultant needs to see rules referenced to the code that actually
   governs your scheme.
4. Re-run after revisions and compare `issue_stats` totals by band.
