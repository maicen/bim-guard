# Q15: How accurate is the room compliance analysis for my building type?

## The Question

> "We ran it on our office refurbishment and it came back with very little —
> eleven findings, mostly informational. My first reaction was that the model is
> clean. My second reaction was that eleven findings on a 14,000 m² office
> sounds too good. How do I tell the difference between a clean model and a
> ruleset that is not looking at anything?"

## The Answer

Your second reaction is the right one, and the distinction you are drawing is the
single most important thing to understand about the architecture analysis: **a
low finding count is not evidence of compliance. It is evidence that few rules
fired.** Those are very different claims, and on an office refurbishment against
the baseline pack, the second is the more likely explanation.

The shipped baseline is 47 rules across `BUILDING-CODE-PART9` (31) and
`BUILDING-CODE-PART9-EXT` (16), written to a Part 9-style residential and
small-building scope. Look at what those rules target: stair dimensions, bedroom
egress windows, party walls between dwelling units, garage-to-dwelling
separation, habitable room ceiling heights. On a 14,000 m² office, the dwelling
rules have nothing to match, the bedroom egress window rule has no bedrooms, and
what remains is the general dimensional set — stairs, doors, ramps, guards,
handrails, corridor widths — plus the model-quality checks. Eleven findings is
consistent with a reasonable model checked against a ruleset that covers perhaps
a third of what an office actually needs checking for.

What the baseline pack does **not** cover for an office: occupancy load and
egress capacity calculations, travel distances to exits, number of exits required,
fire compartment sizes, escape stair capacity, sanitary provision by occupant
count, means-of-escape door swing direction, refuge provision, or any of the
Part M / accessibility provisions beyond ramp slope, ramp width and corridor
width. None of those are in the pack, so none of them can produce a finding.

## Coverage by Building Programme

An honest reading of what the baseline pack gives you:

| Programme | Baseline coverage | What is missing |
| --- | --- | --- |
| **Residential (multi-unit)** | **Good.** The pack was written for this — stairs, egress windows, party wall fire separation, dwelling separation, habitable room heights, guards and handrails all apply | Occupancy-based provisions; jurisdiction-specific amendments; ventilation, daylight and acoustic requirements |
| **Residential (single dwelling)** | **Good.** Same rules, fewer separation cases | As above |
| **Office** | **Partial.** General dimensional and model-quality rules apply; the dwelling-specific set does not | Egress capacity, travel distance, exit counts, compartmentation, sanitary provision, accessibility beyond ramps and corridors |
| **Hospital / healthcare** | **Weak.** General dimensional rules only | Clinical space standards, clearances around beds and equipment, isolation and infection-control requirements, door widths for bed transfer, HTM-equivalent provisions, redundancy requirements |
| **Education** | **Weak.** General dimensional rules only | Occupancy density, classroom area standards, egress capacity, sanitary provision by roll |
| **Industrial / warehouse** | **Weak.** General dimensional rules only | Hazard classification, egress from process areas, plant and equipment clearances, fire compartmentation by risk |
| **Hotel / hospitality** | **Partial.** Corridor, stair and door rules apply; guest room provisions do not | Guest room and bathroom standards, accessible room ratios, operator brand standards |

For anything below "good", the analysis should be read as a **model quality and
general dimensional check**, not as a code compliance position. Q14 covers adding
a programme-specific ruleset, which is what closes the gap.

## Known Limitations and Edge Cases

Beyond coverage, there are structural limits worth knowing:

**Rules read properties, not geometry.** A ceiling height rule reads the `Height`
property on an `IfcSpace`. If the property is stale, absent or mapped from
something other than what you expect, the finding reflects the property rather
than the design. This cuts both ways: it produces false positives on stale
parameters, and false negatives where the property is generous and the built
condition is not. Q13 covers the diagnosis.

**Single-value properties on irregular spaces.** A `Width` on an L-shaped
corridor is a bounding dimension, not the constrained clear width. The rule
compares what it is given.

**No occupancy-load reasoning.** Rules are per-element thresholds. Anything
requiring a computed occupant count, an aggregate capacity, or a path traced
through the building is outside the current rule types.

**No table or graph lookups in the baseline pack.** The schema supports
`table_lookup` and `tiered` rule types, but the shipped baseline is almost
entirely `numeric_comparison`, `numeric_range` and `prohibition`. Requirements
expressed in the code as a table have not been encoded.

**Property completeness gates everything.** If `OccupancyType` is absent, no rule
conditioned on occupancy can fire. If `NetFloorArea` is absent, no area rule can.
This is why the extended pack's `informational` rules exist, and why clearing
them first materially changes what the next run can see.

**Absence is not a pass.** A rule that could not evaluate an element does not
report it as compliant. Findings and silence are different, and silence is not
evidence.

## How to Manually Verify Findings

1. **Count the rules that fired, not the findings.** If your report shows
   findings from six distinct `rule_id`s out of 47 rules, ask why the other 41
   produced nothing. Some genuinely do not apply; some could not evaluate.
2. **Check the model-quality findings first.** A high count of `informational`
   completeness findings tells you a large part of the ruleset could not see the
   data it needs.
3. **Take three rules you know your model should fail and confirm it does.** If
   you know a corridor is 1050 mm, the 1100 mm rule should find it. If it does
   not, the property is not what you think it is. This is the fastest calibration
   available and it takes fifteen minutes.
4. **Spot-check three findings against the model** — open the element, read the
   property, measure the geometry, compare all three.
5. **Compare against a manual check on one sample area.** A single floor plate
   checked by hand against the governing code will tell you what proportion of
   real issues the ruleset caught. That ratio is your actual accuracy figure for
   this project, and no general claim substitutes for it.

## When This Analysis Applies

The baseline pack is appropriate as a code check for residential and
small-building work. For every other programme, treat it as a model quality and
general dimensional check, and add a programme-specific ruleset before treating
any result as a compliance position.

## What the Report Contains

Findings carry the rule id and clause reference, so the set of distinct rule ids
in a report tells you which rules fired. What the report does **not** currently
show is which rules were evaluated and passed, versus which could not evaluate —
so the coverage question above has to be answered by inspecting the ruleset and
the model-quality findings together rather than read off a single number.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "For [the governing code] applied to [office / hospital / education /
> industrial] buildings, produce a complete register of quantitative requirements
> organised by the building element they constrain. For each: clause reference,
> requirement verbatim, element, property, operator, value, unit, and the
> occupancy or condition it applies to.
>
> Then answer separately and explicitly: which of these requirements depend on a
> computed occupant load, an aggregate capacity, a travel distance, or a path
> through the building rather than a single element property? List those
> separately and do not express them as element thresholds."

**Purpose.** Build the programme-specific pack that closes the coverage gap, and
— through the second half of the prompt — produce an explicit register of what
cannot be checked by per-element rules at all. That register is what tells you
honestly how much of the code an automated check can reach for this building
type, which is the real answer to the accuracy question.

**Not for.** Establishing whether your building complies. The register is an
input to rule authoring and to a manual review scope, not a verdict.

## Export Options

- **CSV** — pivot by `rule_id` to see which rules fired and how often. This is
  the coverage diagnostic.
- **JSON** — `issue_stats` for band totals and the `data_quality` count.
- **BCF 2.1** — for issuing the findings that are genuine design issues.

## Next Steps for Your Project

1. Do not report eleven findings as a clean result. Establish first which rules
   fired and which could not.
2. Clear the model-completeness findings and re-run. The delta tells you how much
   the ruleset was previously unable to see.
3. Run the three-known-failures calibration. It is the cheapest confidence check
   available.
4. Author an office-appropriate ruleset (Q14) before treating any architecture
   result on this project as a compliance position.
5. State the coverage explicitly in the report cover note. "Checked against 47
   general and residential rules; egress capacity, compartmentation and sanitary
   provision not assessed" is a defensible statement. "Eleven findings" on its own
   is not.
