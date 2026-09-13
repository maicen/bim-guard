# Q07: How much clearance does my piping need around beams and columns?

## The Question

> "Straight question. My coordinator wants a number to set as a clearance rule in
> Navisworks so we stop generating findings. What is the number, where does it
> come from, and does it change for the hospital block versus the office block on
> the same campus?"

## The Answer

The number the shipped configuration applies is **200 mm** from a restrained MEP
service to a structural element. Be clear with your coordinator about what that
number is: **BIMGUARD's authored screening value, not a dimension from any code.**

Earlier versions of this answer attributed 200 mm to DIN 4149 and 150 mm to
EN 1998-1. That was wrong. The editions cited (EN 1998-1 dated 2020, DIN 4149
dated 2022) do not exist, DIN 4149 is withdrawn, and neither EN 1998-1:2004+A1:2013 nor its
German National Annex gives a clearance dimension for MEP services. The
configuration was corrected on 2026-09-13 and now records the provenance of every
threshold:

| Parameter | Value | Status | Basis |
| --- | --- | --- | --- |
| Clearance from structure | **200 mm** | authored | No source held gives a braced-service clearance |
| Restraint spacing, transverse | **1.0 m** | authored | Screening value; FEMA E-74's sample spec allows up to 40 ft for ductile pipe |
| Restraint spacing, longitudinal | **1.5 m** | authored | Screening value; FEMA E-74's sample spec allows up to 80 ft for ductile pipe |
| Pipe diameter threshold | **63 mm** | authored | Inside the ~1–3 in exemption band FEMA E-74 reports for ASCE/SEI 7-10 |
| Brace angle range | **40°–65° from horizontal** | authored | No source gives a pipe or duct brace angle |
| Importance factor, hospital | **1.5** | sourced | FEMA E-74 §5.3.1; ASCE/SEI 7-10 §13.1.3 |
| Importance factor, standard | **1.0** | sourced | Same |

The nearest sourced rule to a clearance is narrower than it looks: FEMA E-74's
sample specification (App. A §3.9.D.9) asks for horizontal clearance of at least
two-thirds of the hanger length — but only for **unbraced, exempt** piping, so it
cannot justify a figure for braced services.

The clearance values are the same across all four brace hardware types the
configuration carries — cable, rod, angle for mechanical, angle for fire — because
no source held distinguishes them. If your bracing contractor is working to a
manufacturer's certified system, use its published clearances and treat the
BIMGUARD number as a screening prompt, not a code floor.

## Does It Change for the Hospital Block?

This is the part that surprises people, so the answer is worth stating plainly:
**not in the clearance geometry.**

Hospitals attract stricter *design* requirements, not larger clearances. Under
ASCE/SEI 7-10 §13.1.3, as reported by FEMA E-74 §5.3.1, critical components in
Risk Category IV buildings are designated seismic systems with an importance
factor of **1.5** against 1.0 otherwise — larger design forces, certification, and
an expectation that the service still works after the event. No source held adds
clearance for a hospital or for a higher seismic zone. The configuration sets both
additions to **0 mm** and marks them `authored`, because a zero chosen without a
source is still a choice.

Practically, for your campus: the same 200 mm envelope applies to both blocks.
The difference between them lands on the structural engineer sizing the braces
and anchors, and on the post-event functionality expectation — a hospital's
services are expected to *work* after the event, not merely to not fall.

## Soft Versus Stiff Buildings

The clearance requirement exists because the structure and the suspended services
respond differently to the same ground motion. How much they diverge depends on
the frame:

- **Stiff frames** — concrete shear wall, braced steel, masonry — move less at
  each floor level, so the relative displacement between a slab and a service
  hung from it is smaller. The structure's own drift is not the dominant term.
- **Soft or flexible frames** — moment frames, long-span steel, tall slender
  structures — drift considerably more, and the differential movement between a
  service and the structure it passes is correspondingly larger. This is where a
  clearance that looks generous on paper gets consumed.

The shipped configuration does not vary the clearance by frame stiffness; its
200 mm is a fixed screening value. FEMA E-74's sample specification instead asks
for designs to accommodate relative displacement (0.02 × storey height unless
analysis gives the drift). If your structural engineer's drift analysis indicates
larger relative displacements at particular levels, record a project-specific
value in the configuration with its reasoning in the provenance block.

## When This Analysis Applies

Any project where MEP services are seismically restrained, and any project where
a coordination clearance rule is being set for services against structure —
including non-seismic projects, where 200 mm is a defensible maintenance-access
allowance in its own right.

## What the Report Contains

For each intrusion: the required envelope dimension, the actual measured
clearance, how much of the envelope was lost, the resulting severity and mapped
risk band, both element `GlobalId`s, and a citation to FEMA E-74 and
ASCE/SEI 7-10 §13.6 naming the SB-001 screening calibration. Elements whose
geometry could not be read produce a `data_quality` finding rather than being
silently skipped.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "From ASCE/SEI 7-10 §13.6, EN 1998-1:2004+A1:2013 §4.3.5 and
> DIN EN 1998-1/NA:2018-10, extract every stated minimum clearance between a
> seismically restrained mechanical or electrical service and a structural
> element. For each value give: the document, edition and clause, the service type
> it applies to, whether it varies by importance factor, occupancy or seismic
> zone, and whether it is an absolute dimension or a function of expected relative
> displacement. State explicitly where no clearance is given — do not infer one."

**Purpose.** Find a stated value that could replace the authored 200 mm and the
authored 0 mm additions, and establish whether any source expresses clearance
absolutely or as a displacement function — which would change the parameter's
shape, not just its value.

**Not for.** Setting the clearance rule in your clash detection software. Use the
structural engineer of record's determination for that; this prompt sources the
clause text they will make it against.

## Export Options

- **BCF 2.1** — each intrusion as a topic with a viewpoint at the pinch point.
- **CSV** — a hanger-by-hanger list of what needs to move and by how much.
- **JSON** — full envelope geometry, for feeding back into a coordination model.
- **`Pset_HaloReservation`** — publishes the reserved volume onto the IFC so the
  envelope is visible to every trade coordinating in the same zone, which
  prevents the next package re-consuming the clearance you just cleared.

## Next Steps for Your Project

1. Confirm the governing code and the bracing designer before setting the number.
   200 mm is BIMGUARD's authored screening value, not a code figure; the bracing
   design or certified restraint system governs.
2. Set the coordination clearance rule to match whatever is confirmed, so
   Navisworks and BIMGUARD are not disagreeing with each other.
3. Ask the structural engineer whether their drift analysis justifies an uplift
   at any level. If so, record it in the configuration with the reasoning.
4. Publish the halo reservations into the federated model early — clearance that
   is not visible gets re-consumed by the next trade through the zone.
5. Take the 0 mm hospital and seismic-zone additions to the structural engineer
   as an explicit question. They are authored values with no source, and a
   hospital project is the right place to test them.
