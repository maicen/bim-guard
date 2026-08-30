# Q20: What does a BCF export contain?

## The Question

> "I have been sent a `.bcf` file and I do not know what it is. My IT team says it
> is just a zip. Can I open it in Solibri? Does it contain our model — is there a
> confidentiality issue sending it to a subcontractor? And what happens to it
> after somebody works through it?"

## The Answer

Your IT team is right that it is a ZIP archive, and that is the reassuring part of
the answer to your confidentiality question: **a BCF file does not contain your
model.** It contains issues *about* a model, referenced by element GUID. Someone
who receives a BCF without the corresponding IFC gets a list of issues with
camera positions and small snapshot images, and cannot reconstruct the building
from it. That is a deliberate property of the format — BCF exists precisely so
that issues can be exchanged between parties without exchanging models.

BCF 2.1 is a buildingSMART OpenBIM standard, and the archive follows a fixed
layout:

```
bcf.version                  ← the BCF schema version
project.bcfp                 ← project identification
{guid}/
    markup.bcf               ← the issue itself: title, description, priority,
                               status, assignee, dates, comments
    viewpoint.bcfv           ← camera position, orientation, and the element
                               GUIDs the issue concerns
    snapshot.png             ← a rendered image of that viewpoint
{guid}/
    ...                      ← one folder per issue
```

## What Each Part Gives the Reader

**Viewpoints (`viewpoint.bcfv`)** are what make BCF worth using rather than
emailing a spreadsheet. Each carries a camera position and orientation plus the
set of element GUIDs the issue concerns. When the recipient opens the file in a
tool that has the model loaded, the tool resolves the GUIDs against its own
model, flies the camera to the saved position, and selects the elements. The
reviewer is looking at the actual junction, room or clearance breach within two
clicks — not searching for a `GlobalId` in a browser tree. For seismic clearance
and cross-material findings in particular this is the difference between a report
that gets acted on and one that gets filed.

**Issue markup (`markup.bcf`)** carries the finding itself. For a BIMGUARD export
that means: the title, a description containing the mechanism, the composite
score, the standard and clause citation, and the recommended mitigation; a
priority mapped from the risk band — Critical, High, Medium, Low — so the
receiving tool's own sorting works without anyone learning BIMGUARD's vocabulary;
a topic status; and, on seismic findings, a due date derived from severity, so
the list arrives prioritised rather than as an undifferentiated dump.

**Assignment and comment history** are also markup fields, and they are what
makes BCF a workflow rather than a report. When your MEP designer reassigns a
topic and adds a comment, that lives in the topic. When they return the file, the
history comes back with it. BIMGUARD does not need to be in that loop at all —
the exchange is between the tools.

**Snapshots (`snapshot.png`)** are a rendered image per viewpoint, so the issue is
readable even by someone with no model and no BIM tool. This is what makes a BCF
usable by a commercial manager or a client representative reviewing on a tablet.

## Opening It

| Tool | Support |
| --- | --- |
| **Solibri** | Native import and export |
| **Navisworks** | Native, via the BCF workflow |
| **ARCHICAD** | Native BCF import and export |
| **Revit** | Via a BCF add-in — BIMcollab ZOOM, BCF Manager and similar |
| **Tekla Structures** | BCF import |
| **BIMcollab / Trimble Connect / Dalux / Revizto** | Native issue currency |

So yes, Solibri opens it directly. The one thing to confirm before issuing to a
Revit-based team is that they have a BCF add-in installed — that is by a wide
margin the most common reason a BCF package goes unread.

## What Is in a BIMGUARD BCF Specifically

All three analyses export to the same archive layout. Corrosion findings and
architecture findings go through the general exporter; seismic clash reports go
through a dedicated Blue Halo exporter that produces the same layout, so a
recipient cannot tell — and does not need to — which pipeline produced a topic.

`data_quality` findings are included by default. That is deliberate: an export
that silently dropped elements the engines could not assess would let a partial
analysis read as a complete one. If you are issuing a package to a designer rather
than to a modeller, filter them out consciously and say so, rather than assuming
they were never there.

## A Note on GUID Stability

The viewpoints reference element GUIDs. If the model is re-exported and the
authoring tool regenerates GUIDs, the topics will still open but will no longer
resolve to elements — the camera will fly to the right place and select nothing.
Some export workflows do regenerate GUIDs, so it is worth confirming stability
across revisions before you rely on BCF viewpoints surviving a model update. This
is not a BIMGUARD behaviour; it is a property of the authoring tool's export.

## When This Analysis Applies

Any time findings need to leave BIMGUARD and become somebody's action —
coordination packages, design team reviews, subcontractor issue lists, client
quality gates, insurer evidence packs.

## What the Report Contains

Beyond BCF, the same result exports as **CSV** (fixed column order, one row per
finding, citations joined into a single cell — best for tracking and pivoting) and
**JSON** (the full result including per-finding metadata and aggregate
`issue_stats` — best for dashboards and for the durable record). All three come
from the same computed result, so exports taken minutes apart describe the same
run.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "Summarise the buildingSMART BCF 2.1 specification in full: the archive
> structure, every element and attribute of `markup.bcf` marking which are
> mandatory, the permitted values for `TopicStatus`, `TopicType` and `Priority`,
> the `viewpoint.bcfv` camera and component model, and the rules governing
> comments and their association with viewpoints. Then describe what the
> specification says about round-tripping topics between tools — what a receiving
> tool must preserve, and what it may discard. Give element names exactly as the
> schema defines them."

**Purpose.** Keep the exporter demonstrably conformant so topics resolve
correctly in every receiving tool, and establish precisely what survives a
round-trip — which determines whether assignment and comment history returned
from a subcontractor can be relied on as a record.

**Not for.** Deciding which findings to issue or how to route them. That is
project governance, made by the information manager and the design team leads.

## Export Options

- **BCF 2.1** — `.bcf` archive, the layout above.
- **CSV** — `text/csv`, UTF-8, fixed header. An empty result still returns the
  header row, so a downstream import never breaks on a clean model.
- **JSON** — `application/json`, indented, the full `AnalysisResult`.

## Next Steps for Your Project

1. Open it in Solibri. It will work, and it contains no model geometry, so there
   is no confidentiality issue in forwarding it to a subcontractor.
2. Confirm any Revit recipients have a BCF add-in before issuing.
3. Split large exports by zone or level. A single archive with three hundred
   topics does not get worked through.
4. Let assignment and status live in the receiving tool. BCF round-trips, and
   BIMGUARD does not need to be in that loop.
5. Re-run BIMGUARD after the fixes and compare `issue_stats` band totals. A
   closed BCF topic records that somebody said it was fixed; the re-run
   establishes whether it was.
