# Q17: Which IFC versions does BIMGUARD support?

## The Question

> "Our architect is on ARCHICAD exporting IFC4, the structural engineer is on
> Tekla, and the MEP subcontractor is still exporting IFC2x3 out of an old Revit
> because that is what their client template says. Is that going to be a problem?
> And someone mentioned IFC4.3 — do we need to worry about that?"

## The Answer

**IFC2x3 and IFC4 are both supported**, and mixed-schema federation across
disciplines is a normal case rather than a problem. The parser reads either
schema regardless of the authoring tool — that is the point of an OpenBIM format,
and the implementation is written to that principle rather than to a particular
vendor's export.

There is one asymmetry worth knowing about, and it lands exactly on your MEP
subcontractor. Some MEP classes were introduced or renamed between the two
schemas. A parser looking for IFC4 class names in an IFC2x3 file will not find
them — not because the data is missing, but because that schema version does not
define those classes. The code handles this explicitly: class lookups that fail
on a schema that does not define the class are skipped safely rather than
raising, and the piping producer carries both the IFC4 and the IFC2X3 names for
each distribution element class it recognises. Connectivity is read through
`IfcRelConnectsPortToElement` in IFC2X3 and `IfcRelNests` in IFC4, so the
cross-material engine's network walk works in both.

When an IFC2X3 model is loaded, the parser emits a **schema compatibility note**
flagging that the model may not carry IFC4-only MEP classes. Read that note if it
appears. It is not an error and it does not stop the analysis; it is telling you
that a class absent from the results may be absent from the schema rather than
absent from the design.

## IFC4.3 and Newer

IFC4.3 (ISO 16739-1:2024) is the current buildingSMART release, and it is
primarily an infrastructure extension — alignment, roads, rail, ports and
waterways — added on top of the IFC4 building schema. The behaviour to expect:

- A **4.3 file that uses only building entities** will generally read, because
  those entities are the IFC4 ones.
- A **4.3 file using infrastructure entities** — alignments, linear placements —
  contains classes the parser does not recognise, and those elements will not
  appear in the results. They will not crash the run; they will simply not be
  seen.
- **IFC4.1 and 4.2** are intermediate infrastructure releases and behave the same
  way.

If your project is a building, exporting IFC4 (the 4.0 ADD2 / Reference View
flavour that most tools default to) is the reliable choice, and there is no
benefit in reaching for 4.3. If your project is infrastructure, this is not
currently the right tool for the infrastructure portion — and that is a scope
statement rather than a workaround.

## Exporting Well From Each Tool

The schema version is rarely what causes a poor result. Export *settings* are.
The three analyses each need particular data, and the default coordination export
in most tools is tuned for geometry:

**Revit.** Export IFC4 Reference View or IFC2x3 Coordination View 2.0 — either
works. What matters: enable **export of IFC property sets** and **base
quantities** (architecture rules read `Pset_*` properties and
`Qto_SpaceBaseQuantities`); enable **spaces / rooms** (`IfcSpace` — several
architecture rules target it and it is off in some templates); ensure **materials
are assigned and named meaningfully**, because "Default" or "Material 3" resolves
to no galvanic series entry and produces a `data_quality` finding rather than a
verdict; and confirm **MEP system and connector information** is exported, since
the cross-material engine walks the connectivity graph and cannot see a tee that
is not described.

**ARCHICAD.** Use an IFC4 translator with property mapping enabled. Confirm zones
export as `IfcSpace` with `LongName` populated — the architecture pack has a rule
specifically for missing `LongName` because it is so often absent.

**Tekla.** Structural export is generally clean for the seismic check, which
needs the structural elements as clash candidates rather than as property-bearing
objects. Confirm the geometry exports as solids — the seismic engine reads a real
bounding box per element and raises a `data_quality` finding rather than
synthesising one from a position and a length.

**Any tool.** Export the whole model rather than a filtered view where possible.
The seismic check compares services against structure, so a services-only export
has nothing to clash against and will come back near-empty for the wrong reason.

## Diagnosing a Thin Result

If a run returns far fewer findings than expected, work through this in order —
it is almost always one of the first three:

1. **Count the `data_quality` findings.** A high count means elements were seen
   but could not be assessed: missing materials, missing connectivity, unreadable
   geometry. Fix the export, not the design.
2. **Check the schema compatibility note** if the model is IFC2X3.
3. **Check the model actually contains the discipline** the analysis needs.
4. **Check property sets and quantities were exported.** Architecture rules read
   properties; without them the rules cannot evaluate, and — importantly — an
   element that could not be evaluated is not reported as compliant.
5. **Check spaces exported**, if architecture results look thin.

## When This Analysis Applies

Every run. Schema and export quality are upstream of all three analyses, and a
model exported without properties, materials or connectivity limits every one of
them regardless of how good the rules are.

## What the Report Contains

`data_quality` findings are the schema and export diagnostic. They carry the
element and a `metadata["check"]` key naming what could not be resolved, and they
are counted separately from the four risk bands — deliberately, so an unassessed
element is never mistaken for a low-risk one. On a first run against a new
export, read these before reading any verdict.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "From ISO 16739-1 (IFC4) and the IFC2x3 specification, list the entity names
> for distribution and MEP elements — pipe segments, duct segments, cable carrier
> segments, flow segments, fittings and terminals — in both schemas, identifying
> which entities exist in one schema and not the other, and which were renamed.
> Then describe how port-based connectivity is expressed in each schema, naming
> the relationship entities. Finally, list the standard property sets and base
> quantity sets that carry material, dimension, system assignment and operating
> parameters for these elements."

**Purpose.** Keep the parser's class name tables and property lookup paths
complete and current across both schemas, and produce an authoritative export
checklist to give to modelling teams — which is the highest-leverage document in
this whole workflow, because export quality gates every analysis.

**Not for.** Diagnosing your specific export. Run the model and read the
`data_quality` findings; they name what is actually missing from your file.

## Export Options

Export formats are independent of the input schema. **BCF 2.1** viewpoints
reference `GlobalId`s, which are stable across schema versions, so a BCF generated
from an IFC2x3 analysis resolves correctly against an IFC4 model of the same
project provided the GUIDs were preserved through the re-export. That proviso is
real — some export workflows regenerate GUIDs, which breaks the link.

## Next Steps for Your Project

1. Let the MEP subcontractor stay on IFC2x3 if their template requires it. It
   works. Check the schema compatibility note on the first run.
2. Give all three teams the export checklist — properties, quantities, spaces,
   materials, MEP connectivity — before the next issue. This matters far more
   than the schema version.
3. Run once and read the `data_quality` count before reading any verdict. That
   number tells you whether the export is fit for analysis.
4. Confirm GUID stability across re-exports if you intend to reuse BCF viewpoints
   between model revisions.
5. If any part of the project is infrastructure in IFC4.3, scope it out
   explicitly rather than assuming a low finding count means it is clean.
