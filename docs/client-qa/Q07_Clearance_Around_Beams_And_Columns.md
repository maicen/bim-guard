# Q07: How much clearance does my piping need around beams and columns?

## The Question

> "Straight question. My coordinator wants a number to set as a clearance rule in
> Navisworks so we stop generating findings. What is the number, where does it
> come from, and does it change for the hospital block versus the office block on
> the same campus?"

## The Answer

The number the shipped configuration applies is **200 mm** from a restrained MEP
service to a structural element. It is worth understanding how that number was
arrived at, because handing your coordinator a bare 200 mm without the reasoning
will produce an argument the first time someone points at EN 1998-1 and reads
150 mm.

The configuration is a **combined** EN 1998-1:2020 and DIN 4149:2022 profile.
Where the two standards give different values, the configuration takes whichever
is more onerous and records why:

| Parameter | EN 1998-1:2020 | DIN 4149:2022 | Combined | Governing logic |
| --- | --- | --- | --- | --- |
| Clearance from structure | 150 mm | 200 mm | **200 mm** | Larger governs — a halo big enough satisfies both |
| Restraint spacing, transverse | 1.0 m | 1.2 m | **1.0 m** | Tighter governs — more restraints is conservative |
| Restraint spacing, longitudinal | 1.5 m | 1.8 m | **1.5 m** | Same reasoning |
| Pipe diameter threshold | 63 mm | 75 mm | **63 mm** | Lower governs — brings more pipes into scope |
| Brace angle range | 35°–70° | 40°–65° | **40°–65°** | Intersection — the band satisfying both |
| Importance factor, hospital | — | — | **1.6** | Per-key maximum across both |
| Importance factor, standard | — | — | **1.0** | Per-key maximum across both |

So 200 mm is the DIN 4149 value, adopted because a 200 mm envelope also contains
the 150 mm one. If your project sits under EN 1998-1 with a national annex that
does not invoke DIN 4149, 150 mm is defensible and the configuration can be
narrowed to the EN-only profile. That is a decision for your structural engineer
of record, not a default anyone should quietly change.

The clearance values are the same across all four brace hardware types the
configuration carries — cable, rod, angle for mechanical, angle for fire. The
configuration is explicit that this is a limitation rather than a finding: the
source research gives one combined restraint spacing and one minimum clearance
per standard, not values broken out per brace variant, so all four share the same
figures pending brace-specific research. If your bracing contractor is working to
a manufacturer's system with different published clearances, use theirs and treat
the BIMGUARD numbers as the code floor.

## Does It Change for the Hospital Block?

This is the part that surprises people, so the answer is worth stating plainly:
**not in the clearance geometry — but check the clause text before you rely on
that.**

Both standards scale the required *restraint capacity* by importance factor, not
the clearance geometry directly. A hospital carries an importance factor of 1.6
against 1.0 for a standard occupancy, which means the braces and their anchors
must be designed for a larger force. It does not, in the clause text the
configuration was built from, mean the pipe must sit further from the beam. The
configuration therefore sets both the seismic-zone clearance addition and the
hospital clearance addition to **0 mm**, and it records that decision as a data
gap: neither value is present in the source for either standard, so 0 mm was
chosen as the defensible reading rather than a guessed uplift — with an explicit
note to verify against the full clause text before relying on it.

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

The shipped configuration does not vary the clearance by frame stiffness — it
applies the code minimum, which is what the clause text supports. If your
structural engineer's drift analysis indicates larger relative displacements at
particular levels, that is a project-specific uplift on top of the code floor,
and the configuration is the right place to record it: it is a JSON parameter
file, and the value can be raised for a project with the reasoning noted in the
same way the combined values are.

## When This Analysis Applies

Any project where MEP services are seismically restrained, and any project where
a coordination clearance rule is being set for services against structure —
including non-seismic projects, where 200 mm is a defensible maintenance-access
allowance in its own right.

## What the Report Contains

For each intrusion: the required envelope dimension, the actual measured
clearance, how much of the envelope was lost, the resulting severity and mapped
risk band, both element `GlobalId`s, and the EN 1998-1 / DIN 4149 clause
citation. Elements whose geometry could not be read produce a `data_quality`
finding rather than being silently skipped.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "From EN 1998-1:2020 clause 5.3.2.3, DIN 4149:2022-03 clause 8.2.4 and their
> national annexes, extract every stated minimum clearance between a seismically
> restrained mechanical or electrical service and a structural element. For each
> value give: the exact clause, the service type it applies to, whether it varies
> by importance factor, occupancy class or seismic zone, and whether the standard
> expresses it as an absolute dimension or as a function of expected relative
> displacement. State explicitly if the standard gives no clearance uplift for
> importance factor — do not infer one."

**Purpose.** Close the two documented 0 mm gaps in the configuration with sourced
clause text, and establish whether the standards express clearance absolutely or
as a displacement function — which would change the parameter's shape, not just
its value.

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

1. Confirm the governing jurisdiction with the structural engineer before setting
   the number. 200 mm is the conservative combined value; 150 mm may be correct
   for an EN-only project.
2. Set the coordination clearance rule to match whatever is confirmed, so
   Navisworks and BIMGUARD are not disagreeing with each other.
3. Ask the structural engineer whether their drift analysis justifies an uplift
   at any level. If so, record it in the configuration with the reasoning.
4. Publish the halo reservations into the federated model early — clearance that
   is not visible gets re-consumed by the next trade through the zone.
5. Take the 0 mm hospital and seismic-zone additions to the structural engineer
   as an explicit question. They are documented gaps, and a hospital project is
   the right place to close them.
