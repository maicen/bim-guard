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
run. SB-001 screens whether your model leaves room around braced services. Note
that the clearance it applies is BIMGUARD's authored screening value, not a
dimension stated by any code (see below).

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

SB-001 runs from `data/rulesets/sb001_seismic_clearance.json`. Earlier versions
described it as a combined profile of an EN 1998-1 edition dated 2020 and a
DIN 4149 edition dated 2022; neither edition exists, and the values were not
taken from either standard. It was
corrected on 2026-09-13 (schema 1.1.0) and the brace angle was re-sourced on
2026-09-16 (schema 1.2.0). Every threshold now records its provenance:

- **Clearance from structure: 200 mm** — *authored*. No source held gives a
  clearance dimension for a braced service.
- **Restraint spacing: 1.0 m transverse / 1.5 m longitudinal** — *authored*
  screening values. FEMA E-74's sample specification gives maxima of 40 ft / 80 ft
  for ductile pipe, so BIMGUARD's values are far tighter than that reference.
- **Pipe diameter threshold: 63 mm** — *authored*, inside the roughly 1–3 in
  exemption band FEMA E-74 reports for ASCE/SEI 7-10.
- **Brace angle: 30°–60° from horizontal (45° ± 15°)** — *sourced* to the Hilti
  Seismic Manual (05/2022), Annex A, which states a nominal brace tilt angle of
  45° ± 15° on the horizontal level. A vendor design manual applying EN 1998-1,
  not a code. This replaced a 40°–65° range on 2026-09-16; that range came from an
  unverified AI research summary, not from BIMGUARD calibration as it was labelled.
- **Importance factor: 1.5 for hospital, 1.0 for standard** — *sourced* to FEMA
  E-74 §5.3.1 and ASCE/SEI 7-10 §13.1.3 (corrected from 1.6).
- **Duct area threshold: 0.557 m² (6 sq ft)** — *sourced* to FEMA E-74 §6.4.6.1.
- **Seismic-zone, hospital and adjacent-system clearance additions: 0 mm** —
  *authored*; no source gives a clearance addition.

The governing codes are named accurately in the file: **EN 1998-1:2004+A1:2013**
(non-structural elements, §4.3.5) and **DIN EN 1998-1/NA:2018-10**. Neither gives
MEP brace spacing or clearance dimensions, and DIN 4149 is withdrawn. Brace
hardware footprints remain generic placeholders and the default hazard factor is
unset. This matters for your insurer conversation: the configuration now states
which numbers are sourced and which are BIMGUARD's own.

## Why This Matters

Seismic damage to non-structural components is, in most recorded events, a larger
share of loss than structural damage — and in a data centre it is essentially the
entire loss, because the frame surviving is irrelevant if the chilled water
distribution has parted. Clearance failures are also cheap to fix in a model and
expensive to fix on site: moving a hanger 150 mm at coordination stage costs
nothing, and doing it after the slab is poured and the containment is installed
costs a week.

For your Rhine Graben project specifically: low seismicity changes the restraint
capacity a bracing design needs. SB-001's 200 mm envelope does not scale with
hazard, but it is a screening value, not a code requirement.

## When This Analysis Applies

- Projects in any declared seismic zone under EN 1998-1 and its national annex,
  or under ASCE/SEI 7 — as a screening check ahead of the bracing design.
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

> "From ASCE/SEI 7-10 §13.6, EN 1998-1:2004+A1:2013 §4.3.5 and
> DIN EN 1998-1/NA:2018-10, extract the provisions governing the seismic restraint
> of non-structural mechanical and electrical distribution systems. Report
> specifically: minimum clearance between restrained services and structural
> elements; maximum restraint spacing, transverse and longitudinal; the pipe
> diameter and duct area thresholds at which restraint becomes required; permitted
> brace angle ranges; and importance factors by occupancy. Give the document,
> edition and clause for each value, quote the conditions on it, and state
> explicitly where a value the question asks for is not present."

**Purpose.** The last sentence is the important one. Most SB-001 thresholds are
marked `authored` because no document held states them. This prompt is designed
to find a stated value that could replace an authored one, or to confirm that the
gap is real.

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

1. Confirm with your structural engineer which code governs and who designs the
   bracing — SB-001's thresholds are authored screening calibration, not values
   from EN 1998-1 or its national annex, which give no MEP dimensions.
2. Issue Critical intrusions to the MEP coordinator as a routing change, not to
   the structural engineer. The pipe usually moves; the beam does not.
3. Use the `Pset_HaloReservation` output to publish the reserved volumes into the
   federated model, so the next trade to route through the zone can see them.
4. Give your insurer the configuration file alongside the findings. Its
   per-threshold provenance and `provenance_summary` are the audit trail, and a
   claim reviewer will value that more than a finding count.
