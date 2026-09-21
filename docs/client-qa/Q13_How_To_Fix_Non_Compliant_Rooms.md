# Q13: How do I fix non-compliant rooms?

## The Question

> "I have a finding that says a space failed the habitable room ceiling height
> rule — 2400 mm required, and it is reporting 2380. I have looked at the room in
> Revit and the ceiling is at 2400. Is the rule wrong, is my model wrong, or am I
> reading it wrong? And once I do fix something, how do I confirm it is actually
> cleared?"

## The Answer

Almost certainly the model, and specifically the *property*, rather than the
geometry. This is the single most common architecture finding and it is worth
walking through carefully, because the same reasoning applies to most of them.

The rule reads a named property from the element — for habitable ceiling height,
`Height` on an `IfcSpace` — and compares it to 2400 mm. It does not measure the
distance from your floor slab to your ceiling. If the space object's `Height`
parameter says 2380, the rule reports 2380, regardless of where you have modelled
the ceiling. That divergence has a few usual causes: the space object was created
before the level heights were finalised and never regenerated; the space is
bounded by the structural slab soffit rather than the finished ceiling; the space
height is computed to an unbounded limit; or the export mapped a different
parameter into `Height` than you expect.

So the first question on any dimensional finding is not "is the design wrong" but
"does the property the rule read match the thing I think it measured". That is a
five-minute check and it resolves a large proportion of architecture findings
without touching the design.

## The Remediation Workflow

**1. Read the finding properly.** It names the element `GlobalId`, the rule and
its clause reference, the property that was read, the value found and the value
required. Those five things together tell you what kind of problem it is.

**2. Classify the finding into one of three kinds.** They have entirely different
remedies and different owners:

- **A property problem.** The geometry is right, the parameter is wrong or stale.
  Owner: the modeller. This is the majority of dimensional findings, and it is
  fixed by regenerating spaces, correcting the parameter, or correcting the IFC
  export mapping.
- **A model completeness problem.** The property is absent entirely — the
  `informational` rules in the extended pack are all of this kind (`LongName`,
  `OccupancyType`, `NetFloorArea`, `IsExternal`, `PredefinedType`). Owner: the
  modeller. These matter more than their severity suggests, because several other
  rules cannot produce a verdict without them.
- **A genuine design problem.** The property is correct and the design does not
  meet the requirement. Owner: the architect. This is the one that costs
  something.

**3. Fix at the right level.** For a genuine design problem — say a habitable
room genuinely at 2380 mm — the options in ascending order of cost are: reduce
the ceiling zone (services coordination), raise the floor-to-floor (structural
and cost implication across the whole building), reduce the floor build-up, or
reclassify the room's function if it is not in fact habitable (a store or a
plant space carries a different requirement, and the bathroom/utility rule
permits 1950 mm). Reclassification is legitimate where the room genuinely is not
habitable, and it is a `LongName`/`OccupancyType` correction, not a fudge — but
it must reflect the actual design intent, and the planning consultant needs to
agree it.

**4. Fix once, not forty times.** On a repeated residential layout, one failing
rule is one design decision replicated across every unit. Group findings by
`rule_id` before doing anything. Forty findings of the same rule against forty
identical units is one fix.

**5. Regenerate and re-export the IFC.** A property fix in the authoring tool is
invisible to BIMGUARD until the model is re-exported. This is the step most often
missed — people fix the parameter, re-run, and see the same finding, because the
uploaded IFC has not changed.

**6. Re-upload and re-run.** The result cache is keyed on the model's SHA-256, so
a changed model always misses the cache and recomputes. A model that has *not*
changed will serve the cached result — which is the correct behaviour, and also a
useful diagnostic: if you believe you fixed something and the results are
byte-identical, the file you uploaded is the same file.

**7. Compare `issue_stats`, not finding counts.** Export the JSON before and
after and compare the band totals. That difference is the real progress measure.
Counting closed items in a tracker measures activity; comparing band totals
measures outcome.

## A Worked Example: "Room too small for function"

Take the accessible corridor rule — `IfcSpace`, `Width` ≥ 1100 mm — failing on a
circulation space reporting 1050 mm.

1. **Check the property.** Is `Width` on that space actually the clear width, or
   is it a bounding-box dimension that includes a recess? If the space is
   irregular, a single `Width` value may not represent the constrained dimension
   at all. This determines whether the finding is meaningful.
2. **If the property is right and the design is 1050 mm**, this is a real
   accessibility exceedance and there is no property fix. The corridor widens, or
   the wall it is bounded by moves, or the layout changes.
3. **Look at what else is on that wall** before moving it — a 50 mm move is often
   free on one side and expensive on the other, and the finding does not know
   that. This is the judgement the tool cannot make.
4. **Apply the fix across every instance** of the repeated layout.
5. **Re-export, re-upload, re-run**, and confirm the rule now returns nothing for
   those elements.

## When This Analysis Applies

Whenever architecture findings are being cleared: design-stage quality gates,
pre-submission checking, model quality audits before an IFC issue, and handover
validation.

## What the Report Contains

Per finding: element `GlobalId`, rule id and clause reference, the property name
read, the value found, the value required, the operator, the severity
(`mandatory` / `recommended` / `informational`), the risk band, and the
mitigation text. Findings adapt into the same issue shape as the corrosion and
seismic results, so they export identically.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "From [the governing code], extract the full definition of a habitable room and
> every room classification the code distinguishes, together with the minimum
> ceiling height, minimum floor area and minimum dimension applying to each
> classification. Give the clause reference for each. Then list every stated
> exception, reduction or relief — sloped ceilings, partial-height areas, ancillary
> spaces, existing buildings — and quote the conditions on each exception
> verbatim. State which classifications the code leaves undefined."

**Purpose.** Room rules are where a single threshold most often hides a
classification question. Encoding "2400 mm for habitable rooms" without encoding
what makes a room habitable, and without the sloped-ceiling relief, produces
findings that are technically correct and practically wrong. This prompt sources
the classification and the exceptions so the rule pack can carry `applies_when`
conditions rather than a bare threshold.

**Not for.** Deciding whether your 2380 mm room is acceptable. That is a matter
for the code, the building control officer, and whether a relief clause applies —
and the first step is establishing what the room's height actually is.

## Export Options

- **CSV** — best for the grouping exercise. Pivot by `rule_id` to collapse
  repeated findings into decisions, and by severity to separate model-quality from
  design issues.
- **BCF 2.1** — for issuing genuine design findings to the architect with a
  viewpoint on the space.
- **JSON** — for the before/after `issue_stats` comparison.

## Next Steps for Your Project

1. Split the findings three ways — property problems, completeness problems,
   design problems — before assigning anything. Two of those three go to the
   modeller.
2. Clear the `informational` completeness findings first. They are quick and each
   one unblocks a rule that currently cannot produce a verdict.
3. Group the design findings by `rule_id` and take them to the architect as a
   short list of decisions, not a long list of elements.
4. Re-export the IFC after every fix round — a parameter change in the authoring
   tool does not reach BIMGUARD until the model is re-exported and re-uploaded.
5. Keep the before/after JSON. The band-total delta is the evidence that the
   round of work achieved something.
