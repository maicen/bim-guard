# Q09: How do I interpret SB-001 findings on my model?

## The Question

> "I have 312 SB-001 findings. Some say Critical, some say Medium, and they all
> look like the same thing to me — a pipe near a beam. What is the difference
> between a Critical and a Medium here, and what am I supposed to do about the
> Criticals? Move the pipe? Move the beam? Nobody is moving the beam."

## The Answer

Nobody is moving the beam, and the engine is not asking you to. Every SB-001
finding says the same structural thing — a clearance envelope around a restrained
MEP service has been intruded upon — and what varies between bands is **how much
of the envelope is lost**. That is the whole of the severity model, and it is
deliberately not a 0.0–1.0 composite score like the corrosion engines produce. An
intrusion is graded by envelope loss, which is a severity rather than a
multi-term score, so it maps directly onto a band rather than passing through the
scoring path:

| Blue Halo severity | Risk band | What it means |
| --- | --- | --- |
| `critical` | **Critical** | The envelope is substantially or entirely consumed |
| `major` | **High** | A significant portion lost; the remaining gap is below code |
| `minor` | **Medium** | A marginal encroachment into the envelope |

There is no Low band for a clearance intrusion, which is itself informative: a
clearance either exists or it does not, and a marginal breach is still a breach.

So the practical reading of a **Critical** is: the pipe is effectively hard
against the structure, and in a seismic event it has nowhere to go. The failure
will be at the hanger or the joint, immediately, and the mode is loss of
containment. On a chilled water or sprinkler main that is a flooding event on top
of a service loss. A **High** means there is a gap but it is short of the code
minimum — survivable in a small event, not in a design event. A **Medium** means
the design is close and the encroachment is likely a modelling or hanger-position
detail rather than a routing decision.

## What a Critical Envelope Breach Actually Means

It is worth separating two things a Critical can be telling you, because they
have different remedies and the finding metadata distinguishes them:

**A routing conflict.** The service genuinely passes too close to structure — it
was routed to the geometric clash tolerance rather than the seismic clearance,
which is the usual cause. Clash detection set to 0 mm hard-clash will pass a pipe
sitting 20 mm from a beam without complaint, and that pipe is a Critical SB-001
finding. This is the most common source, and it is why running the seismic check
after a "clash-free" coordination sign-off is worth doing rather than assuming
the model is clean.

**A restraint feasibility problem.** Even where the pipe clears the structure,
there may be no room to install the brace at a permitted angle — the combined
profile requires 40°–65° — and no room for the brace footprint. A pipe 220 mm
from a beam clears the 200 mm envelope but may still be un-braceable if the only
available anchor point puts the brace at 25°. The engine's envelope is sized to
make bracing feasible, which is why the number is larger than a bare clash
tolerance.

## Remediation, in Order of Cost

1. **Move the service.** Almost always the answer, almost always cheap at model
   stage. Re-route the run, or shift it within the ceiling void. On a
   coordination model this is minutes.
2. **Move the hanger or change the support type.** Where the run cannot move but
   the support point can, relocating the restraint away from the structural
   member often recovers the envelope, because the halo is generated around the
   *braced* element.
3. **Change the brace type.** The configuration carries four hardware types —
   cable, rod, angle-mechanical, angle-fire — with different footprints (cable
   50×50 mm, rod 100×100 mm, angle types 120×120 mm). A cable brace needs
   materially less room than an angle brace. Note that the footprints are
   flagged in the configuration as generic placeholders pending a hardware
   catalogue cross-reference, so confirm against the actual bracing system.
4. **Add a buffer or a designed impact detail.** Where nothing can move, a
   detailed solution — a resilient buffer, an engineered soft-contact detail —
   can be designed, but this is a structural engineer's decision and it takes the
   element out of the standard clearance regime into a specific design case.
5. **Relocate the structure.** Effectively never, and the engine's output should
   not be read as proposing it. If a Critical genuinely cannot be resolved by
   routing, it goes to the structural engineer as a design case, not as a request
   to move a beam.

## Triaging 312 Findings

The count is almost certainly not 312 decisions. Clearance findings cluster hard,
because a single riser passing a floor plate generates a finding at every level,
and a service running parallel to a beam generates a finding at every
intersection along it. Before issuing anything:

1. **Group by intruding element.** One run producing forty findings is one
   routing decision.
2. **Group by intruded element.** Twenty services all breaching the same transfer
   beam is a zone problem, not twenty pipe problems.
3. **Separate the `data_quality` findings.** An element whose geometry could not
   be read raises a data-quality Issue rather than being skipped — the engine
   will not synthesise a bounding box from a position and a length, because a
   clash against an invented envelope is not a finding. These go to the modeller,
   not the coordinator.
4. **Then sort by band.** Criticals first, and within Criticals, by service —
   sprinkler and chilled water before small-bore.

## When This Analysis Applies

After MEP coordination reaches a stable routing, and before hanger and bracing
design is issued for fabrication. Running it earlier produces noise from routes
that were going to change anyway; running it later means the fixes are on site.

## What the Report Contains

Per finding: rule id `SB-001.01`, mechanism `SB-001` ("Seismic bracing
clearance"), the braced element and the intruding element `GlobalId`s, the
envelope geometry and how much of it was lost, the severity and mapped band, and
the EN 1998-1 / DIN 4149 citation. Findings use the same `Issue` shape as the
corrosion results, so they sort, filter and export identically.

There is deliberately no synthetic-issue mode in the seismic path. Findings are
computed from real geometry or they are absent; the result carries an explicit
flag if a run was not genuine, and the interface is required to honour it.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "From EN 1998-1:2020 §5.3.2.3, DIN 4149:2022-03 §8.2.4 and available seismic
> restraint design guidance, extract what the standards state about the
> consequences of insufficient clearance between a restrained service and
> structure. Specifically: is there any stated tolerance or acceptance criterion
> for partial clearance; does either standard grade a deficiency by degree; and
> is any alternative detailed solution — resilient buffer, engineered soft
> contact, flexible connection — recognised in place of the clearance? Give clause
> references and quote any acceptance conditions verbatim."

**Purpose.** The current severity model grades by envelope loss, which is an
engineering-reasonable but internally-derived grading. If either standard defines
a graded acceptance criterion, the severity mapping should be sourced from it
rather than derived. This prompt is written to find out whether it does.

**Not for.** Deciding whether a particular Critical finding is acceptable in your
building. That is a structural engineer's judgement on a specific detail.

## Export Options

- **BCF 2.1** — the format to use here without question. A clearance finding is a
  location, and the viewpoint puts the coordinator at the pinch point. The Blue
  Halo exporter renders clash reports into the standard archive layout.
- **CSV** — for the grouping exercise above. Pivot by intruding element.
- **JSON** — carries the envelope geometry, useful if you want to visualise the
  reserved volumes rather than the violations.
- **`Pset_HaloReservation`** — round-trips the reserved volume back onto the IFC
  so the cleared space stays visible to the next trade.

## Next Steps for Your Project

1. Group before you issue. 312 findings is a routing conversation about perhaps
   fifteen runs.
2. Issue grouped Criticals to the MEP coordinator as routing changes, with the
   BCF viewpoints attached.
3. Send `data_quality` findings to the modeller as a geometry-export task.
4. Take any Critical that genuinely cannot be re-routed to the structural
   engineer as a named design case — with the element, the available clearance
   and the service it carries — rather than as a report line.
5. Re-run after re-routing and compare band totals. Publish the halo reservations
   into the federated model so the clearance you win is not re-consumed.
