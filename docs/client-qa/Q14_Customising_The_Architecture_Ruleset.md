# Q14: Can I customise the architecture ruleset?

## The Question

> "The baseline rules are useful but they are not our client's rules. We work for
> a hotel operator with a 90-page brand standard — minimum room dimensions,
> corridor widths, door widths, back-of-house clearances — and it is the brand
> standard, not the building code, that gets us in trouble at handover. Can we
> get those into BIMGUARD, and how do we keep them straight when the operator
> issues version 12?"

## The Answer

Yes, and a brand standard is close to an ideal case for a custom ruleset. It is
prescriptive, quantitative, element-oriented and repeated across many rooms —
which is exactly the shape the rule schema encodes well, and exactly the kind of
checking that is tedious and error-prone by hand.

Rules live in the database, not in the code. Each one is a typed row grouped
under a `ruleset_id`, and a custom ruleset is simply a new id with your rules
under it. Selecting a rule folder queries the rules directly from the database
and executes them against the model immediately, so a custom or extracted
ruleset runs the moment it is saved — no rebuild, no restart. Engine catalogues
reload at the start of each analysis run for the same reason.

A rule needs, at minimum, a `target` (the IFC class it applies to), a
`rule_type`, and a `desc`. Beyond that the required fields depend on the type:

| `rule_type` | What it does | Key fields |
| --- | --- | --- |
| `numeric_comparison` | Threshold with an operator | `property_name`, `operator`, `check_value`, `unit` |
| `numeric_range` | Min and max bounds | `property_name`, `value_min`, `value_max`, `unit` |
| `spatial_clearance` | A geometric dimension | `property_name`, `operator`, `check_value`, `unit` |
| `prohibition` | A property must exist, or a condition must not occur | `property_name`, `operator` |
| `table_lookup` | Value depends on a lookup | lookup parameters |
| `tiered` | Different thresholds by tier | tier definitions |
| `standard_conformance` | Conformance to a named standard | reference |
| `deemed_to_comply` | A deemed-satisfy provision | conditions |

Rules also carry `severity` (`mandatory`, `recommended`, `informational`),
`ref` (the clause or brand-standard section it comes from), an optional
`property_set` to disambiguate which Pset a property is read from, and an
optional `applies_when` condition so one class can carry different requirements
by context — the baseline pack uses this to give interior and exterior doors
different connectivity requirements.

For your hotel operator, the mapping is direct. "Standard king room minimum clear
width 3600 mm" becomes an `IfcSpace` `numeric_comparison` on `Width` with
`check_value` 3600, `unit` mm, `severity` mandatory, `ref` set to the brand
standard section, and an `applies_when` on the room type. "All guest room
entrance doors minimum 900 mm clear" becomes an `IfcDoor` rule with an
`applies_when` on location or occupancy. Rules validate on save, so a malformed
rule is rejected with a message naming the missing field rather than failing
silently at run time.

## Using NotebookLM to Extract Rules from a Brand Standard or Local Code

A 90-page brand standard is a document extraction problem before it is a rule
authoring problem, and this is where NotebookLM earns its place — with a clear
boundary around what it is doing.

**What it is for:** reading a long prescriptive document and producing a
structured, clause-referenced register of every quantitative requirement, in a
shape a reviewer can turn into rules. That is genuinely tedious work and a
language model is good at it.

**What it is not for:** deciding whether your model complies. It never sees the
model. Its output is a *candidate rule register*, and every entry needs a human
reviewer to confirm the value, the unit, the target class and the clause before
it becomes a rule. The distinction matters because an unreviewed extracted rule
produces findings that look exactly like reviewed ones.

The workflow that works:

1. Load the brand standard (and the governing local code, separately) into a
   notebook.
2. Run the extraction prompt below to get a structured register.
3. **Review every row.** Check the value, the unit, the operator and the clause
   against the source. Expect the extraction to be mostly right and occasionally
   confidently wrong — the review is not optional.
4. Map each reviewed row onto the rule schema: `target`, `property_name`,
   `rule_type`, `operator`, `check_value`, `unit`, `ref`, `severity`.
5. Flag the requirements that **cannot** be encoded — performance criteria,
   subjective quality standards, requirements needing information the IFC does
   not carry. These go on a manual review list rather than quietly disappearing.
6. Save under a distinct `ruleset_id` and run against a known model to sanity
   check before relying on it.

## Managing Versioning

The operator's version 12 is the real question, and it needs handling
deliberately because rules are live — edited rules take effect on the next run.

- **Version the `ruleset_id`, not the rules.** `HOTEL-BRAND-V11` and
  `HOTEL-BRAND-V12` as separate rulesets, rather than editing rules in place.
  This keeps a report reproducible against the standard that was current when it
  was issued, and it lets you diff the two versions by running both against the
  same model.
- **Carry the source reference on every rule.** The `ref` field should name the
  brand standard section and its version, so a finding traces to a specific
  clause in a specific edition.
- **Archive the ruleset with every issued report.** Because catalogues reload per
  run, "the rules at the time" is a real distinction, and the report alone does
  not record it.
- **Diff before adopting.** Run V11 and V12 against the same model and compare
  the results. That difference is what changed in the standard, expressed as
  findings, and it is usually more informative than the operator's change log.
- **Grade confidence.** The corrosion packs carry per-value `cite` and `conf`
  fields distinguishing `established` from `provisional`. The same discipline
  applied to extracted rules — marking which have been reviewed against source
  and which have not — prevents an unreviewed extraction being read as settled.

## When This Analysis Applies

- Operator and brand standards (hotels, retail, healthcare networks, data centre
  operators).
- Client-specific employer's requirements and design standards.
- Jurisdiction-specific codes where the baseline pack does not apply.
- Programme-specific requirements the baseline residential pack does not cover —
  hospital, laboratory, education, industrial.
- Internal practice standards and QA checklists.

## What the Report Contains

Custom rules produce findings identical in shape to baseline ones — element
`GlobalId`, rule id, clause reference, property read, value found against value
required, severity, band, mitigation. The `ref` field is what distinguishes a
brand-standard finding from a code finding in the report, which is why populating
it properly matters.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "From the attached [brand standard / local building code], extract every
> quantitative, checkable requirement. Return a table with one row per
> requirement and these columns: section or clause reference; requirement text
> quoted verbatim; the building element the requirement applies to (state it as an
> IFC class where you can — IfcSpace, IfcDoor, IfcWall, IfcStairFlight,
> IfcWindow, IfcRamp, IfcRailing, IfcSlab); the property being constrained; the
> operator (minimum, maximum, range, must exist); the numeric value; the unit;
> the room type, occupancy or condition it applies to; and whether it is
> mandatory or advisory.
>
> Then produce a second table listing every requirement you could NOT express in
> that form, with the reason — performance-based, subjective, requiring
> information not held in a building model, or dependent on a table or graph.
> Do not attempt to convert those into numeric thresholds. Give the document
> edition and revision date you read from."

**Purpose.** The second table is the important one and is the reason the prompt is
written this way. An extraction that silently drops the un-encodable requirements
produces a ruleset that looks complete and is not, and the gap surfaces at
handover — which is exactly the failure mode this project is trying to avoid.

**Not for.** Producing compliance verdicts, or authoring rules without review.
Every extracted row is a candidate that a competent reviewer confirms against the
source before it becomes a rule.

## Export Options

- **CSV** — the natural interchange for a reviewed rule register on its way into
  the rules table.
- **JSON** — for programmatic rule import and for archiving a ruleset version
  alongside a report.
- **BCF 2.1** — for issuing the resulting findings to the design team.

## Next Steps for Your Project

1. Extract the brand standard into a candidate register, then review every row
   against the source before saving anything.
2. Maintain the un-encodable requirements as an explicit manual review list, and
   include it in the handover pack. It is evidence of scope, not an admission.
3. Version the ruleset id per standard edition, and archive the ruleset with each
   issued report.
4. Run the brand ruleset and the code ruleset as separate passes. A brand
   exceedance and a code exceedance are different conversations with different
   people, and merging them obscures both.
5. Sanity-check a new ruleset against a model you already understand before you
   trust it on a live project.
