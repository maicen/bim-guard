# Q10: Can I export seismic findings to Revit or other BIM tools?

## The Question

> "Our structural engineer works in Tekla, the MEP designer works in Revit, and
> the coordination model lives in Navisworks with the client reviewing in
> Solibri. That is four tools and none of them is BIMGUARD. If I send them a PDF
> they will ignore it. Can the seismic findings get into their tools in a form
> they can act on and send back?"

## The Answer

Yes — BCF 2.1 is precisely the answer to that problem, and it is why the format
exists. BCF (BIM Collaboration Format) is a buildingSMART OpenBIM standard for
exchanging issues between authoring and review tools without exchanging models.
A BCF file carries the *issue*, not the geometry: a title, a description, a
priority, a status, an assignee, comments, and — the part that makes it work — a
**viewpoint**, which is a saved camera position plus the set of element GUIDs the
issue concerns. When your structural engineer opens the BCF in Tekla, the tool
resolves those GUIDs against their own model, flies the camera to the saved
position, and highlights the elements. They are looking at the problem in their
own environment within a couple of clicks.

Every tool you listed supports it. Solibri and Navisworks read and write BCF
natively. ARCHICAD has native BCF support. Revit reads and writes BCF through
add-ins — BIMcollab ZOOM and the BCF Manager family are the common ones, and most
practices already have one installed. Tekla Structures supports BCF import.
BIMcollab, Trimble Connect, Dalux and Revizto all consume it as their native
issue currency. The point of the standard is that none of them need to know
BIMGUARD exists.

The seismic export uses a dedicated Blue Halo BCF exporter that renders each
clearance intrusion into the standard archive layout — `bcf.version`,
`project.bcfp`, then one folder per finding containing `markup.bcf`,
`viewpoint.bcfv` and `snapshot.png`. Risk bands map onto BCF priority values, so
Critical findings sort to the top of the receiving tool's list using that tool's
own filtering. Due dates are derived from severity, so the issue list arrives
already prioritised rather than as an undifferentiated dump.

## How Structural Engineers Collaborate on the Fixes

The workflow that actually works on a seismic clearance package, given that most
of these findings are resolved by the MEP side rather than the structural side:

1. **Export the seismic findings as BCF** and grouped by zone or level, not as
   one 300-topic archive. A reviewer opening a file with three hundred topics
   closes it.
2. **Assign in the receiving tool, not in BIMGUARD.** Assignment is a BCF field
   and it round-trips. The MEP coordinator takes routing changes; the structural
   engineer takes only the findings that genuinely cannot be resolved by moving
   the service — the ones needing a designed detail. On a typical package that
   is a small minority.
3. **The MEP designer re-routes in Revit** and marks the topic resolved with a
   comment. The comment stays on the topic.
4. **The structural engineer reviews the residual cases in Tekla**, using the
   viewpoint to see exactly which member the service is against, and either
   confirms the re-route is acceptable or issues a designed detail.
5. **The coordinator merges the returned BCF** back into Navisworks or Solibri
   to see the closure state across the whole package.
6. **Re-run BIMGUARD on the revised model** and compare band totals. This is the
   step people skip, and it is the only one that actually verifies the fix —
   a closed BCF topic records that somebody said it was fixed, not that the
   clearance now exists.

That last point is worth emphasising for seismic work in particular. A re-routed
pipe frequently consumes another service's clearance, so closing ten topics can
open six new ones. The BCF loop tracks intent; the re-run establishes fact.

## The Other Export: Reservations Back Onto the Model

There is a second export for seismic work that is more useful than the issue list
in some workflows. The halo volumes themselves can be rendered as a
`Pset_HaloReservation` property set, in the standard `{pset_name: {property:
value}}` shape, for round-tripping the reserved clearance volume back onto the
IFC model.

That turns clearance from a report into a modelled constraint. Once the
reservations are in the federated model, the next trade routing through the zone
sees the reserved volume in their own clash detection and does not consume it.
This is materially more effective than re-checking after the fact, because the
constraint is visible at the moment the routing decision is made rather than two
weeks later in a report.

## When This Analysis Applies

Whenever seismic findings need to leave BIMGUARD and become somebody's action:
issuing a coordination package, a design-team review, a structural sign-off on
restraint feasibility, an insurer or lender evidence pack, or a client quality
gate.

## What the Report Contains

Each BCF topic carries: the finding title and description including the mechanism
and the clearance shortfall, the mapped priority, the topic status, a severity-
derived due date, the viewpoint with camera position and element GUIDs, a
snapshot image, and the EN 1998-1 / DIN 4149 citation in the description. The CSV
and JSON exports carry the same finding set — CSV with a fixed column order for
tracking, JSON with full envelope geometry and aggregate `issue_stats`.

`data_quality` findings are included in the export by default. An export that
silently dropped elements whose geometry could not be read would let a partial
analysis read as a complete one.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "Summarise the buildingSMART BCF 2.1 specification's viewpoint model:
> `viewpoint.bcfv` structure, how camera position and orientation are expressed,
> how component GUIDs are associated with a viewpoint, what visibility and
> colouring information a viewpoint may carry, and what the specification says
> about snapshot images. Then summarise what ISO 19650-2 requires of an
> information exchange between task teams, and which of those requirements a BCF
> exchange satisfies and which it does not."

**Purpose.** Keep the exporter's viewpoint construction demonstrably conformant
so topics resolve correctly in every receiving tool, and identify what a BCF
exchange does *not* cover under ISO 19650 — which is what the project's BEP has
to cover instead.

**Not for.** Deciding which findings to issue, to whom, or on what programme.
That is information-management governance, made by the information manager.

## Export Options

- **BCF 2.1** — the answer to this question. Universal tool support.
- **CSV** — for the coordination tracker and the commercial record.
- **JSON** — for a dashboard or the project information platform.
- **`Pset_HaloReservation`** — reserved volumes onto the model, which is the
  preventive version of the same information.

## Next Steps for Your Project

1. Export BCF split by level or zone. Do not issue one archive of everything.
2. Confirm your Revit users have a BCF add-in installed before you issue —
   this is the single most common cause of a BCF package going unread.
3. Route findings to the MEP coordinator by default and to the structural
   engineer only by exception. Most seismic clearance findings are resolved by
   moving the service.
4. Publish the halo reservations into the federated model so the clearance is
   visible during routing rather than only in the next report.
5. Re-run after the revisions and compare band totals. Closed topics record
   intent; the re-run establishes whether the clearance exists.
