# Q16: How do I run all three analyses (Piping, Seismic, Architecture) on the same model?

## The Question

> "We have one federated IFC for the whole building — architecture, structure and
> MEP. Do I upload it three times, once per analysis? And when I get three sets
> of findings back, how do I stop the design team drowning in three separate
> reports that all point at the same ceiling void?"

## The Answer

Upload once. The three analyses are three *runs* against one uploaded model, not
three uploads. Each analysis is identified by a slug — `corrosion`, `seismic`,
`architecture` — and each reads the same file from the same project.

A federated model containing all three disciplines is in fact the ideal input,
and for one of the analyses it is a requirement rather than a preference. The
seismic check compares MEP services against structural elements; if the structure
is not in the model, there is nothing for a pipe to be too close to, and the run
will come back near-empty for the wrong reason. Corrosion needs the MEP
distribution with materials and connectivity. Architecture needs the spaces,
doors, windows, stairs and walls. A model with only one discipline gives you one
useful analysis and two misleading ones.

Each run produces the same `AnalysisResult` shape — a flat list of findings plus
aggregate `issue_stats` — because the issue schema is deliberately
mechanism-agnostic. A seismic finding, a corrosion finding and an architecture
finding are the same shape to everything downstream, which is what lets one
exporter serve all three and what makes combining them practical rather than a
merge exercise.

## The Sequence That Works

1. **Upload the federated IFC once**, to one project.
2. **Run architecture first.** It is usually the fastest, and its
   model-completeness findings tell you whether the model is in a state worth
   analysing at all. If `IsExternal`, `PredefinedType` and `OccupancyType` are
   missing everywhere, the other two analyses are likely reading a similarly thin
   model and you will save time fixing the export before running them.
3. **Run corrosion next.** This is the longest run, because extracting the piping
   network — materials, media, diameters, joint types and the full connectivity
   graph — is the most expensive parsing step in the system (see Q19).
4. **Run seismic last**, once the MEP routing is stable. Running it against a
   model that is still being coordinated generates findings against routes that
   are going to change anyway.
5. **Export each result separately**, then combine at the coordination level
   rather than in the tool.

Results are cached per analysis, keyed on project, slug and the model's SHA-256 —
so re-running the same analysis on the same model returns the cached result
rather than recomputing, and exporting CSV then JSON then BCF does not re-run the
engines three times. Change the model and the digest changes, so the next run
recomputes. The cache holds a bounded number of recent results for a limited
period; a miss is never an error, it just means the run takes longer.

## Interpreting Combined Findings

This is the real question, and the answer is that you should not issue three
reports. You should issue one coordination package organised by **who acts**, not
by which engine found it. The three analyses overlap physically far more than
they overlap organisationally:

- A ceiling void with a seismic clearance breach and a galvanic couple 300 mm
  away is **one visit** by the MEP coordinator, not two.
- A `data_quality` finding from the corrosion engines and an `informational`
  completeness finding from the architecture pack are **the same problem** — an
  under-specified model — and they go to the same person in one list.
- A re-route that clears a seismic finding can create a new dissimilar-metal
  junction. Running corrosion again after seismic re-routing is not paranoia; it
  is the normal consequence of the two analyses looking at the same pipes.

A practical merge:

| Recipient | What they get |
| --- | --- |
| **BIM modeller** | Every `data_quality` finding from all three, plus the `informational` architecture findings. One list. This is usually the highest-value package. |
| **MEP coordinator** | Seismic Critical/High, plus corrosion findings that are routing- or junction-located. Grouped by zone. |
| **MEP designer** | Corrosion GC/XM/MM specification decisions, grouped by mitigation. |
| **Water safety / authorising engineer** | MC-001 findings. |
| **Architect** | Architecture `mandatory` findings that are genuine design issues, grouped by rule. |
| **Structural engineer** | Only the seismic findings that cannot be resolved by moving the service. Usually a small minority. |

Sort each package by location, not by band, once the bands have been used for
triage. A coordinator working a zone wants everything in that zone.

## When This Analysis Applies

At any design-stage quality gate on a project with MEP distribution in a seismic
jurisdiction — which is when all three are relevant simultaneously. On projects
outside a seismic zone, architecture and corrosion still pair naturally.

## What the Report Contains

Three `AnalysisResult` payloads with identical structure. Each carries its own
`audit_issues` list and `issue_stats` totals — four risk bands plus a separate
`data_quality` count, kept out of the band totals so an unassessed element is
never counted as low-risk.

Two behavioural differences worth knowing. The corrosion run reports live
progress through the pipeline tracker — validation, parsing, engine run, scoring,
reporting — streamed over server-sent events. The seismic and architecture runs
do not bind to that tracker, deliberately: binding them would reset a corrosion
run's stages for the same project. Their results are complete; only the live
stage display is absent.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "From ISO 19650-1 and ISO 19650-2, extract the requirements governing federated
> information models and the coordination of information from multiple task
> teams. Specifically: what the standards require of a federation strategy, how
> responsibility for information is allocated between task teams, what the
> information delivery plan must record about model checking, and what
> verification and validation activities are required before an information
> exchange. Give clause references. Then list what ISO 19650 requires to be
> recorded about a model check that a findings list alone does not capture."

**Purpose.** Align the multi-analysis workflow with the project's BIM Execution
Plan, and establish what the check record needs to contain beyond the findings
themselves — the model revision, the ruleset version, the analysis scope and the
declared exclusions.

**Not for.** Determining which analyses your project needs. That follows from the
building type, the jurisdiction and the client's requirements.

## Export Options

Each analysis exports independently as **BCF 2.1**, **CSV** or **JSON**. Merging
is done downstream — the CSVs concatenate cleanly because the column order is
fixed, and BCF archives merge in any coordination tool. There is no single
combined export, which is deliberate: the three analyses have different scopes,
different rulesets and different declared exclusions, and a single merged report
would obscure all three.

## Next Steps for Your Project

1. Upload the federated model once and run architecture first as a model-quality
   gate.
2. Fix the export if the completeness findings are widespread, before spending
   time on corrosion and seismic results computed from thin data.
3. Run all three, export all three, then reorganise by recipient rather than by
   engine.
4. Give the modeller the combined `data_quality` and `informational` list first.
   It is the package that most improves the next run.
5. Re-run corrosion after any seismic-driven re-routing. Moving pipes changes
   which metals meet.
