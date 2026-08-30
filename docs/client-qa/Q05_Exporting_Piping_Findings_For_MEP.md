# Q05: How do I export Piping findings so my MEP engineer can fix them?

## The Question

> "The report is on screen and it looks useful, but my mechanical designer works
> in Revit and my commercial team works in Excel, and neither of them is going to
> log into your tool. How do I get 140 findings out of here and into a form where
> somebody can actually be assigned a fix and be chased on it?"

## The Answer

Three formats, and they exist for three different readers. Pick by who is
receiving it, not by preference.

**BCF 2.1** is for the person who has to *change the model*. It is the
buildingSMART OpenBIM issue-exchange standard, and it is the only one of the
three that carries a location. The export is a ZIP with the standard layout —
`bcf.version`, `project.bcfp`, then one folder per finding containing
`markup.bcf`, `viewpoint.bcfv` and `snapshot.png`. Your designer opens it in
Solibri, BIMcollab, Navisworks, ARCHICAD, or Revit through a BCF add-in, and each
finding becomes a clickable topic that flies the camera to the junction and
selects the element. Risk band maps onto BCF priority — Critical, High, Medium,
Low — so the receiving tool's own sorting and filtering works without anyone
learning BIMGUARD's vocabulary. This is what you send to the MEP engineer.

**CSV** is for the person who has to *track* the fix. Fixed column order, one row
per finding, citations joined into a single cell, everything a pivot table needs.
This is where the real triage work happens on a large piping run, because
corrosion findings cluster: 140 findings very often represent eight repeated
details. Pivot by mitigation and by material pair and the list collapses into the
handful of decisions it actually is. Send this to the commercial team and to
whoever chairs the coordination meeting.

**JSON** is for the person who has to *integrate* it. It is the full
`AnalysisResult` — every finding with its complete metadata, the per-term score
breakdown, and the aggregate `issue_stats` — for a dashboard, a data warehouse,
or a client-side quality system. Send this to whoever owns your project
information platform.

All three come from the same computed result, so a CSV and a BCF pulled minutes
apart describe the same run. Repeated downloads reuse a short-lived cached
result rather than re-running the engines, keyed on the model's SHA-256 — so if
the model changes, the next download recomputes rather than serving stale
findings against a model that has moved on.

## What Goes in Each Format

| | BCF 2.1 | CSV | JSON |
| --- | --- | --- | --- |
| Element location / viewpoint | ✔ | `GlobalId` only | `GlobalId` only |
| Risk band | as BCF priority | column | field |
| Composite score | in description | column | field |
| Per-term breakdown | — | — | ✔ (metadata) |
| Citations | in description | joined cell | structured array |
| Mitigation text | in description | column | field |
| Assignment / status | ✔ (round-trips) | column | field |
| Aggregate statistics | — | — | ✔ (`issue_stats`) |
| Opens without BIMGUARD | ✔ | ✔ | ✔ |

## How to Assign Findings to Teams

There is no single right split, but this one survives contact with a real
coordination meeting:

- **Mechanical designer** — GC-001 and XM-001 findings. These are junction and
  specification decisions: dielectric isolation, fitting material, whether a
  union is designed in at the interface.
- **Mechanical designer, with the public health engineer** — MM-001 findings.
  Material-media mismatches are a specification decision but they depend on the
  water chemistry, which the public health engineer owns.
- **Water safety / authorising engineer** — MC-001 findings. Dead legs, flow
  velocity and storage temperature are Legionella controls before they are
  corrosion controls, and on a healthcare project they belong to the water safety
  group, not the contractor.
- **Detailer or fabricator** — CC-001 findings. Crevice risk is usually resolved
  at joint detail level: gasket material, drainage, weld versus threaded.
- **BIM modeller** — every `data_quality` finding, regardless of engine. These
  are not engineering issues. They are missing material names, missing joint
  types, absent connectivity or missing operating temperatures, and each one is
  an element the engines could not assess. Fixing them converts silence into a
  verdict on the next run, which is often the highest-value hour anyone spends on
  the report.

Assignment travels with the BCF topic, so once assigned in the receiving tool it
round-trips through the normal BCF workflow. BIMGUARD does not need to be in that
loop.

## When This Analysis Applies

Any point at which findings leave the reviewer and become somebody's action:
issuing a coordination package, a design-team review, a client quality gate, a
subcontractor pre-procurement review, or a handover evidence pack.

## What the Report Contains

The export carries the same finding set the interface shows, including
`data_quality` findings by default — deliberately, because an export that
silently dropped unassessed elements would let a partial analysis read as a
complete one. Aggregate `issue_stats` count the four bands and keep
`data_quality` in a separate total for the same reason.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "Summarise the buildingSMART BCF 2.1 specification's required and optional
> elements for a topic: which fields are mandatory in `markup.bcf`, what
> `TopicStatus` and `Priority` values the schema permits, how viewpoints are
> associated with topics, and what the specification says about comment and
> assignment round-tripping between tools. Give the schema element names exactly.
> Then list, from ISO 19650-1 and ISO 19650-2, the information-exchange
> requirements that apply when issue data is transferred between task teams."

**Purpose.** Keep the exporter's field mapping demonstrably conformant, and align
the assignment workflow above with the ISO 19650 information-exchange language
the project's BEP will already be using.

**Not for.** Deciding which findings to issue or to whom. That is a project
governance decision made by the information manager and the design team leads.

## Export Options

- **BCF 2.1** — `bcf` extension, delivered as a binary archive.
- **CSV** — `text/csv`, UTF-8, fixed header row. An empty result still returns the
  header, so a downstream import never breaks on a clean model.
- **JSON** — `application/json`, indented by default.

## Next Steps for Your Project

1. Export CSV first and pivot it. Decide what the findings actually are before
   issuing anything — 140 rows is rarely 140 decisions.
2. Export BCF and issue it as the coordination package, with the Critical and
   High findings assigned per the split above.
3. Split out `data_quality` findings into a separate modeller task list. Do not
   put them in the engineer's package.
4. Keep the JSON with the issue record. It is the machine-readable evidence that
   this revision of the model was assessed, and it carries the score breakdown
   that neither of the other formats does.
5. After the model is revised, re-run and export again. Compare `issue_stats`
   band totals between the two JSON files — that difference is your progress
   report, and it is more honest than a count of closed topics.
