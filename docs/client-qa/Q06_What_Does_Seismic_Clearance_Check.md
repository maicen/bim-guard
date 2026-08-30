# Q06: What does Seismic Clearance (Blue Halo) check?

## The Question

> "We are doing a data centre in the Rhine Graben — low seismicity by global
> standards, but the client's insurer is asking for evidence that the MEP
> distribution has been considered seismically. Our structural engineer has done
> the frame. Nobody has looked at whether the pipework can move. What does the
> Blue Halo check actually do, and is it a substitute for a bracing design?"

## The Answer

It is not a substitute for a bracing design, and it is important to be clear
about that first. What SB-001 checks is the *space* that a braced or restrained
MEP service needs to have around it in order for a bracing design to be
buildable and for the service to survive the differential movement of a seismic
event. In an earthquake, the structural frame and the suspended services move
differently — different masses, different periods, different support conditions.
A pipe that sits 40 mm from a concrete beam has nowhere to go; it impacts the
beam, and the failure is at the joint or the hanger, not in the middle of the
run. Codes therefore require a minimum clearance between restrained services and
structure. SB-001 checks whether your model actually provides it.

Mechanically, the engine generates a **clearance envelope** — the "halo" — around
each braced element, sized from the jurisdiction configuration, and then detects
intrusions into that envelope by anything else in the model: beams, columns,
slabs, walls, other services. Each intrusion becomes a finding with a severity
graded by how much of the envelope is lost, mapped onto the same risk bands the
corrosion engines use — a critical intrusion bands Critical, a major one High, a
minor one Medium. That mapping is a translation, not a score: Blue Halo grades an
intrusion by envelope loss, which is a severity rather than a 0.0–1.0 composite,
so it maps to a band rather than passing through the scoring path.

The elements treated as braced MEP services are `IfcPipeSegment`,
`IfcDuctSegment`, `IfcCableCarrierSegment` and `IfcFlowSegment`. Everything else
in the model is a clash *candidate* rather than a halo source — so a beam does
not get its own envelope, but it will be found intruding into a pipe's.

One thing the engine deliberately does not do: it does not invent geometry. A
halo needs a real bounding box per element, read from the model. Where an
element's geometry cannot be read, the engine raises a `data_quality` finding
rather than synthesising a box from a position and a length. A clash computed
against an invented envelope is not a finding, and presenting it as one would be
a fabrication. There is likewise no demo or synthetic-issue mode in the seismic
path — findings are computed or they are absent, and the result carries an
explicit flag if a run was not genuine.

## Which Standards It Works From

The shipped jurisdiction configuration is a **combined** EN 1998-1:2020 and
DIN 4149:2022 profile, referenced to EN 1998-1:2020 clause 5.3.2.3 and
DIN 4149:2022-03 clause 8.2.4. Combined means every parameter takes whichever of
the two values is more onerous, and the configuration records the reasoning for
each one:

- **Clearance from structure: 200 mm** — the *larger* of EN 1998-1's 150 mm and
  DIN 4149's 200 mm governs, because the larger clearance produces a halo that
  satisfies both.
- **Restraint spacing: 1.0 m transverse / 1.5 m longitudinal** — the *tighter* of
  EN 1998-1's 1.0/1.5 m and DIN 4149's 1.2/1.8 m governs, because tighter spacing
  demands more restraints, which is the conservative reading.
- **Pipe diameter threshold: 63 mm** — the *lower* of EN 1998-1's 63 mm and
  DIN 4149's 75 mm governs, because it brings more pipes into scope for bracing.
- **Brace angle: 40°–65°** — the *intersection* of EN 1998-1's 35°–70° and
  DIN 4149's 40°–65°, which is the band any brace satisfying both must fall in.
- **Importance factor: 1.6 for hospital, 1.0 for standard** — the per-key maximum
  across the two standards, because the higher factor demands greater restraint
  capacity.

The configuration also records its **data gaps** explicitly rather than filling
them with plausible numbers. Seismic-zone and hospital clearance additions are
set to 0 mm because neither standard states a clearance addition — both scale
restraint *capacity* by importance factor, not clearance geometry — and that is
flagged as needing verification against the full clause text. Duct area
thresholds, adjacent-system clearance and the default hazard factor are left null
pending standard-specific research. Brace hardware footprints are marked as
generic placeholders. This matters for your insurer conversation: the
configuration tells you what it knows and what it does not.

## Why This Matters

Seismic damage to non-structural components is, in most recorded events, a larger
share of loss than structural damage — and in a data centre it is essentially the
entire loss, because the frame surviving is irrelevant if the chilled water
distribution has parted. Clearance failures are also cheap to fix in a model and
expensive to fix on site: moving a hanger 150 mm at coordination stage costs
nothing, and doing it after the slab is poured and the containment is installed
costs a week.

For your Rhine Graben project specifically: low seismicity does not remove the
clearance requirement, it changes the restraint capacity. The 200 mm envelope is
a geometric requirement that does not scale down with hazard.

## When This Analysis Applies

- Projects in any declared seismic zone under EN 1998-1 or a national annex.
- German projects where DIN 4149 applies.
- Healthcare, data centres, emergency services and other facilities carrying an
  elevated importance factor — where the requirement is post-event *function*,
  not merely life safety.
- Any project where an insurer, a client asset team or a lender is asking for
  non-structural seismic evidence.
- Coordination generally, even outside seismic regions: a 200 mm services-to-
  structure envelope is good practice for maintenance access regardless.

## What the Report Contains

Every finding carries rule id `SB-001.01`, mechanism `SB-001` labelled "Seismic
bracing clearance", the intruding and intruded element `GlobalId`s, the envelope
geometry, the severity, the mapped risk band, and the standard citation. Findings
share the same `Issue` shape as the corrosion results, so a seismic finding and a
corrosion finding are identical to everything downstream — one exporter, one
report format, one issue schema. `data_quality` findings use the same mechanism
string as the corrosion engines, so one exemption rule and one statistics split
serve both.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "From EN 1998-1:2020 clause 5.3.2.3 and DIN 4149:2022-03 clause 8.2.4, extract
> the full clause text governing the seismic restraint of non-structural
> mechanical and electrical components. Report specifically: minimum clearance
> between restrained services and structural elements; maximum restraint spacing,
> transverse and longitudinal; the pipe diameter and duct area thresholds at
> which restraint becomes required; permitted brace angle ranges; and importance
> factors by occupancy class. Give the clause number for each value, quote the
> conditions on it, and state explicitly where a value the question asks for is
> not present in the clause text."

**Purpose.** The last sentence is the important one. The current configuration
carries several documented nulls and zeros precisely because the source research
did not establish those values, and the honest thing is to keep them null rather
than infer them. This prompt is designed to close those gaps with sourced clause
text, or to confirm that the gap is real.

**Not for.** Determining whether your building needs seismic restraint at all, or
what its importance factor is. That is a determination made by the structural
engineer of record against the applicable national annex and the site hazard.

## Export Options

- **BCF 2.1** — the natural format for clearance findings, since a clearance
  violation is a location. Topics carry a viewpoint framed on the intrusion. A
  dedicated Blue Halo BCF exporter renders clash reports with the same archive
  layout as the corrosion export.
- **CSV** — for tracking which hangers and routes need to move.
- **JSON** — full result including envelope geometry.
- **IFC property set** — the halo reservation can also be rendered as a
  `Pset_HaloReservation` property set for round-tripping the reserved volume back
  onto the model, so the space is visible to everyone coordinating in it.

## Next Steps for Your Project

1. Confirm with your structural engineer which jurisdiction profile applies —
   the shipped configuration is a deliberately conservative EN 1998-1 + DIN 4149
   combination, which may be stricter than your national annex requires.
2. Issue Critical intrusions to the MEP coordinator as a routing change, not to
   the structural engineer. The pipe usually moves; the beam does not.
3. Use the `Pset_HaloReservation` output to publish the reserved volumes into the
   federated model, so the next trade to route through the zone can see them.
4. Give your insurer the configuration file alongside the findings. Its recorded
   data gaps and governing-value reasoning are the audit trail, and a claim
   reviewer will value that more than a finding count.
