# Q12: Which building codes and standards does BIMGUARD reference?

## The Question

> "Before I put any of this in front of a building control officer, I need to
> know where the numbers come from. Which codes are you working to, how do I know
> a given rule reflects the current version of that code, and how do I check a
> rule's source myself if I am challenged on it?"

## The Answer

That is the right question to ask first, and the answer differs between the three
analysis domains, so take them separately.

### Piping corrosion — five engines, published materials standards

| Standard | What it supplies | Engine |
| --- | --- | --- |
| **NASA-STD-6012** | Galvanic voltage compatibility thresholds by environment class; the compatibility floor definition | GC-001, XM-001 |
| **BS 8539** | Bi-metallic assemblies; dielectric separation practice | GC-001, XM-001 |
| **EN ISO 15329** | Crevice corrosion testing; wetting classes T0–T5 | CC-001, MM-001, XM-001 |
| **ASTM G48 (Method B)** | Critical crevice temperature values for stainless grades | CC-001 |
| **CIRIA C692** | Stainless steel in construction; CCT data | CC-001 |
| **EN 1993-1-4** | Structural stainless steel | CC-001 |
| **IMOA Design Manual (4th ed.)** | PREN formula and grade selection | GC-001, CC-001 |
| **CIBSE Guide G** | Public health engineering; MEP crevice and materials guidance | CC-001, MC-001, MM-001 |
| **CIBSE TM13:2013** | Minimising the risk of Legionella | MC-001 |
| **HSE HSG274 Parts 1–3** | Legionella control; storage temperature regime | MC-001, MM-001 |
| **BS 8552:2012** | Sampling and monitoring of water | MC-001, MM-001 |
| **EN ISO 9308-1** | Microbiological water quality | MC-001, MM-001 |
| **ASTM G-187** | MIC assessment | MC-001 |
| **WHO Guidelines for Drinking-Water Quality (4th ed.)** | Water quality baseline | MC-001 |
| **EN 12952-12** | Feedwater and boiler water quality | MM-001 |
| **ASTM B117** | Salt spray exposure | GC-001, MM-001 |
| **Euro Inox / WorldStainless; AUCSC** | Galvanic series and corrosion rate data | GC-001 |

### Seismic clearance — one combined jurisdiction profile

**EN 1998-1:2020 §5.3.2.3** and **DIN 4149:2022-03 §8.2.4**, merged into a single
conservative profile. Every merged parameter records which standard's value
governs and why (see Q08 for the full table). The configuration also records its
own **data gaps** explicitly — duct area thresholds, adjacent-system clearance,
default hazard factor and brace hardware sizes are left null or flagged as
placeholders rather than filled with plausible numbers.

### Architecture compliance — a baseline pack plus what you add

This is the domain where you need to be most careful, and the honest answer is
the useful one. The shipped baseline is **47 rules** in two packs —
`BUILDING-CODE-PART9` (31) and `BUILDING-CODE-PART9-EXT` (16) — written to a
Part 9-style residential and small-building scope. Rules carry clause references
in the form the source code uses (`9.8.2.1.(2)`, `Table 9.8.4.1`, `CODE 3.8.3.4`),
and a subset carry `BIMGuard QA` as their reference, which marks them as model-
quality checks rather than code requirements.

Two things follow from that. First, the baseline is a **starting pack, not a
jurisdiction**: it is not the Musterbauordnung, not a Landesbauordnung, not the
IBC and not Part B or Part M of the Approved Documents. Second, the rules live in
the database, not in the code, so a project's live ruleset is whatever has been
seeded plus whatever has been extracted from project documents or authored for
that project — the architectural audit itself is generic and has no built-in
notion of "the" building code; it runs whatever ruleset a project selects,
whether that's the seeded baseline, a jurisdiction pack you've authored, or
rules an LLM extracted from an uploaded regulatory PDF and a reviewer approved.
**Do not put a baseline-pack finding in front of a building control officer as
a code position without first confirming the governing code and authoring
rules against it.** Q14 covers how to do that.

Elsewhere the system references **ISO 16739-1** (IFC), **ISO 19650-1 and -2**
(information management), **buildingSMART BCF 2.1** (issue exchange) and
**ISO 8601** (timestamps). Those govern the data formats rather than the design.

## How Rules Are Sourced and Versioned

Rules are stored in a unified database table with typed fields and a JSON
`parameters` payload, grouped under a `ruleset_id` — `BUILDING-CODE-PART9`,
`BIMGUARD-GC-001`, `BIMGUARD-CC-001`, `BIMGUARD-MC-001`, `BIMGUARD-MM-001`,
`BIMGUARD-XM-001`, or a custom id for a project pack. Each engine's rule pack
carries a `schema_version`, a `status`, and an `approval` block naming who signed
it. Individual parameter entries in the corrosion packs carry their own `cite`
(the source) and `conf` (confidence: `established` or `provisional`) fields, so
the confidence grading is per-value rather than per-pack.

Seeding is idempotent per rule rather than all-or-nothing, so a pack can be
extended or resumed without duplicating what is already loaded, and engine
catalogues are reloaded at the start of each analysis run — a rule edited in the
database takes effect on the next run without a server restart. That is
convenient and it is also a governance obligation: it means the ruleset a report
was produced against is the ruleset at that moment, so the report and the pack
version should be archived together.

## How to Verify a Rule's Source Yourself

1. **Read the citation on the finding.** Every finding carries `citations` — a
   standard, a clause, and the reason that clause applies. That is the claim.
2. **Open the rule in the rules view** and read its `ref` field and its
   `parameters`. For corrosion rules, read the `cite` and `conf` on the specific
   parameter that drove the score, not just the pack-level reference.
3. **Check the `conf` grading.** A `provisional` value is one the authors have
   flagged as not fully established. Several MM-001 and XM-001 parameters are
   graded provisional deliberately, and the packs carry an
   `OPEN_QUESTIONS_FOR_REVIEW` block listing what is unresolved.
4. **Read the pack's data gaps.** The seismic configuration and the MM-001 pack
   both enumerate what they do not know. This is the most valuable page in the
   documentation when someone challenges a number.
5. **Go to the standard.** The clause reference is there so you can. If the
   clause does not say what the rule says it says, that is a defect and it should
   be raised — the citation chain exists to make that check possible.

## When This Analysis Applies

Any time a finding will be relied on externally: a building control submission, a
client quality gate, an insurer or lender evidence pack, a contractual compliance
statement, or an expert report.

## What the Report Contains

Citations are structured, not free text: each carries `standard`, `clause` and
`reason` as separate fields, so they export cleanly to CSV (joined into one cell)
and JSON (as a structured array) and appear in the BCF topic description.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "For [the governing code for this project — name it and its edition], produce a
> clause-by-clause register of every quantitative requirement applying to
> [the building type]. For each requirement give: clause number, requirement
> text quoted verbatim, the numeric value and unit, the operator (minimum,
> maximum, range, existence), the building class or occupancy it is conditioned
> on, and whether it is mandatory or guidance. Separately list every requirement
> that is expressed as a table, a graph, or a performance criterion rather than a
> single number, since those cannot be encoded as a simple threshold. Give the
> edition and amendment date of the document you are reading from."

**Purpose.** Build a jurisdiction-specific pack with a complete, dated, clause-
referenced provenance chain — and identify up front which requirements cannot be
encoded as a threshold rule at all, so they are handled by human review rather
than silently omitted.

**Not for.** Establishing which code governs your project, or making a compliance
determination. The first is a legal and contractual question; the second requires
the model, the rules and a competent reviewer.

## Export Options

- **CSV** — includes a citations column, which makes it the practical format for
  a compliance register.
- **JSON** — citations as a structured array with `standard`, `clause` and
  `reason` fields separately addressable.
- **BCF 2.1** — citations appear in the topic description alongside the finding.

## Next Steps for Your Project

1. Establish the governing code in writing before relying on any architecture
   finding externally. The baseline pack is not a jurisdiction.
2. Archive the ruleset alongside every report you issue. Rules are live and
   reloaded per run, so "the rules at the time" is a real distinction.
3. Read the `OPEN_QUESTIONS_FOR_REVIEW` and data-gap blocks in the packs you rely
   on, and put them in the report's cover note. A reviewer who finds a gap you
   already declared trusts the rest; one who finds a gap you concealed does not.
4. Spot-check three or four citations against the actual standard before your
   first external issue. It takes an hour and it is the cheapest possible
   insurance.
