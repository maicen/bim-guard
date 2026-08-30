# Q08: What is the difference between DIN 4149 and EN 1998-1 seismic codes?

## The Question

> "Our German partner keeps referring to DIN 4149 and our internal standards team
> keeps referring to Eurocode 8. I have been told they are the same thing and
> also that they are different. Which one does BIMGUARD apply, and does it matter
> for a project in Cologne?"

## The Answer

They are related but not interchangeable, and the distinction is the ordinary
Eurocode/national relationship rather than a conflict. **EN 1998-1** is Eurocode
8 Part 1 — the pan-European standard for the design of structures for earthquake
resistance, applicable across the EU and EFTA and adopted with a National Annex
in each member state. **DIN 4149** is the German standard for buildings in
German earthquake zones. Historically it was the German national code that
predated Eurocode adoption; in current practice it functions alongside the German
National Annex to EN 1998-1, and German projects routinely reference both. For
your Cologne project — which sits in one of Germany's more significant seismic
zones, in the Lower Rhine Basin — both are live references, and your German
partner is not wrong to name DIN 4149.

Where they differ for the purposes of non-structural MEP restraint, the
differences are real but modest, and they run in a consistent direction: **DIN
4149 is more demanding on clearance, EN 1998-1 is more demanding on restraint
spacing and scope.**

| Parameter | EN 1998-1:2020 | DIN 4149:2022 | Which is stricter |
| --- | --- | --- | --- |
| Minimum clearance from structure | 150 mm | 200 mm | DIN — larger envelope |
| Restraint spacing, transverse | 1.0 m | 1.2 m | EN — more restraints |
| Restraint spacing, longitudinal | 1.5 m | 1.8 m | EN — more restraints |
| Pipe diameter threshold for restraint | 63 mm | 75 mm | EN — more pipes in scope |
| Permitted brace angle | 35°–70° | 40°–65° | DIN — narrower band |

Referenced clauses are EN 1998-1:2020 §5.3.2.3 and DIN 4149:2022-03 §8.2.4.

## How BIMGUARD Handles Both

It does not make you choose. The shipped jurisdiction configuration is a
**combined profile** that takes, for each parameter independently, whichever
standard's value is more onerous — so a model that passes the combined profile
satisfies both. The configuration records the governing logic for every merged
value, in its own words:

- **Clearance takes the maximum** (200 mm) — "larger clearance governs — it
  produces a halo big enough to satisfy both standards."
- **Restraint spacing takes the minimum** (1.0 m / 1.5 m) — "tighter (smaller)
  spacing governs — it requires more restraints, the conservative reading."
- **Diameter threshold takes the minimum** (63 mm) — "lower diameter threshold
  governs — it brings more pipes into scope for bracing."
- **Brace angle takes the intersection** (40°–65°) — "the band any brace
  satisfying both standards must fall in."
- **Importance factors take the per-key maximum** (hospital 1.6, standard 1.0) —
  "higher factor governs — it demands the greater restraint capacity."

The configuration also records two derived values honestly rather than
presenting them as sourced: the ideal brace angle (52.5°) and tolerance (±12.5°)
are computed as the midpoint and half-range of the combined 40°–65° band, not
independently sourced from either standard. That is written into the file's data
gaps list.

This combined-profile approach has a consequence worth being explicit about: on
an EN-only project, the combined profile is **stricter than required**. A 200 mm
clearance finding against a model designed to EN 1998-1's 150 mm is a correct
report of a DIN 4149 exceedance and a false alarm against the governing code.
The configuration is a JSON parameter file, so an EN-only or DIN-only profile is
a straightforward variant — but which profile governs is a determination for the
structural engineer of record against the applicable National Annex, not a
default anyone should change silently.

## When Each Applies

- **Germany** — both. DIN 4149 for the German zoning and detailing tradition,
  EN 1998-1 with the German National Annex as the Eurocode framework. The
  combined profile is the natural default here, and Cologne is exactly the case
  it was built for.
- **Elsewhere in the EU/EFTA** — EN 1998-1 with the relevant National Annex.
  The National Annex sets nationally determined parameters, so the Portuguese,
  Italian, Greek and Romanian readings of the same clause can differ materially
  in hazard terms even where the non-structural clearance clause does not.
- **Projects with a German client, insurer or parent standard** outside Germany —
  DIN 4149 often arrives contractually rather than statutorily. The combined
  profile satisfies that without a separate run.
- **Outside the EU** — neither applies statutorily. IBC/ASCE 7 and their
  non-structural component provisions govern in the US, and other regimes
  elsewhere. The combined EU profile is not a substitute; it would need its own
  jurisdiction configuration.

## What the Report Contains

Every seismic finding carries `standards_cited` naming both standards and the
`standards_full_citations` entries — currently the section references
`EN 1998-1:2020 5.3.2.3` and `DIN 4149:2022-03 8.2.4`. The configuration notes
that these are section references rather than full bibliographic citations, and
that a fuller citation pass is outstanding. For a report that will be read by an
approving authority or an insurer, quote the clause and cite the standard
formally alongside it.

The findings themselves do not currently tell you *which* of the two standards a
given exceedance breached — the profile is merged before the run. If you need
that split (for example, to show an EN-only compliance position and a DIN
exceedance separately), run the analysis twice against two profiles and diff the
results.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "Compare EN 1998-1:2020 and DIN 4149:2022-03 on the seismic restraint of
> non-structural mechanical and electrical components. Produce a clause-by-clause
> table with columns: parameter, EN 1998-1 value and clause, DIN 4149 value and
> clause, and whether the German National Annex to EN 1998-1 modifies the EN
> value. Cover minimum clearance to structure, restraint spacing, diameter and
> duct-area thresholds, brace angle limits and importance factors by occupancy.
> Do not merge or reconcile the two — report both values side by side, and state
> where either standard is silent."

**Purpose.** The National Annex column is the one currently missing. The
configuration merges EN and DIN directly; it does not yet account for the German
NA modifying the EN values before the merge, which could change which value
governs on one or more parameters.

**Not for.** Deciding which code governs your project. That determination belongs
to the structural engineer of record and the building control authority.

## Export Options

- **BCF 2.1**, **CSV** and **JSON** — identical to the other analyses. The JSON
  export carries the full jurisdiction configuration reference, which is the
  right artefact to attach to a compliance submission.

## Next Steps for Your Project

1. Get the structural engineer of record to confirm, in writing, which profile
   governs — combined, EN-only, or DIN-only. Everything downstream depends on it.
2. If EN-only governs, expect the combined profile's 200 mm clearance findings to
   over-report. Run against an EN-only profile before issuing anything to the
   design team.
3. If you need to demonstrate compliance against each standard separately, run
   twice and diff. One merged run cannot tell you which standard a finding came
   from.
4. Ask the structural engineer whether the German National Annex modifies any of
   the EN values you are relying on. That is the known gap in the current profile.
5. Attach the jurisdiction configuration file to any submission. Its documented
   governing logic and data gaps are the audit trail an approving authority will
   want to see.
