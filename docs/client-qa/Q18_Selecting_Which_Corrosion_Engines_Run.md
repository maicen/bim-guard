# Q18: Can I select which corrosion engines to run?

## The Question

> "Early in the job I just want a quick galvanic sweep to see whether we have a
> mixed-metal problem at all — I do not need the microbial analysis yet, and the
> full run takes a while on our model. Can I turn engines on and off? And if I
> run galvanic only now and everything later, am I paying the cost twice?"

## The Answer

Yes to the first, and no to the second — but the mechanism is worth understanding
because it is not quite what most people assume.

The interface offers checkboxes for **all five engines**, each independently
toggleable, and **all five are selected by default**. The interface will not let
you run with nothing selected. Seismic has no equivalent selector because it is a
single engine with no subsets.

The five split into two kinds, and the selector labels them as such:

| Engine | Kind | What it scores |
| --- | --- | --- |
| **GC-001 Galvanic** | Element | Dissimilar metals in contact, scored per element |
| **CC-001 Crevice** | Element | Joint geometry and trapped electrolyte, per element |
| **MC-001 Microbiological** | Element | Flow, temperature and dead legs, per element |
| **MM-001 Material-Media** | Network | The medium each pipe carries against its material, scored across the system |
| **XM-001 Cross-Material** | Network | Dissimilar metals joined across the network — cannot be scored one element at a time |

MM-001 and XM-001 are **network mechanisms**: they analyse the piping system as a
whole rather than individual segments, because the questions they ask do not
exist at the level of a single element. A dissimilar-metal couple is a property
of a *junction between two elements*, and a medium/material mismatch is resolved
through a run's system assignment — neither can be answered by looking at one
segment in isolation. That is a difference in scope, not in status: all five are
equally selectable, and unchecking a network engine works exactly like unchecking
an element one.

> **Note.** Being a network mechanism has one practical consequence worth
> knowing. Because MM-001 and XM-001 need the extracted piping graph, they depend
> on connectivity and system assignments having survived the IFC export. If those
> are missing, the two network engines will return `data_quality` findings rather
> than verdicts even when they are selected — see Q04 and Q17.

This is a recent correction. Previously the selector exposed only the three
element engines while all five executed on every run, and the result filter
dropped MM-001 and XM-001 findings whenever any selection was applied. Since a
selection was always applied by default, those two engines ran on every audit and
their findings were never shown. If you are comparing against a report issued
before this change, that is why the network engines appear absent from it.

## What Selection Actually Does — and Why It Is Not a Speed Optimisation

This is the important part for your second question. Engine selection **filters
the results**; it does not skip the computation. The narrowing is applied to what
the analysis returns, deliberately and for a good reason: the result cache is
keyed on project, analysis slug and the model's SHA-256, with no engine
dimension. Narrowing *before* the cache write would store a partial run under the
key that the next caller asking for everything would hit — and they would silently
receive an incomplete result believing it was complete. Filtering afterwards means
the cache always holds the full run.

Three consequences follow:

1. **A narrowed run costs the same as a full one.** If your motivation for
   selecting GC-only is speed, it will not help. The expensive part of a corrosion
   run is extracting the piping network from the IFC — materials, media,
   diameters, joint types and the connectivity graph — and that happens once
   regardless of which engines you tick.
2. **Running GC-only now and everything later is free the second time**, provided
   the model has not changed. The first run computes and caches the full result;
   the second run reads the cache and simply filters it differently. So you are
   not paying twice — but you also did not save anything the first time.
3. **An empty or unrecognised selection returns the full result untouched.** A
   caller cannot accidentally narrow a run down to nothing.

When a selection is applied, the aggregate `issue_stats` are **recomputed** for
the narrowed set rather than carried across from the full run. A narrowed finding
list sitting under unnarrowed totals would read as data silently going missing,
so the totals always describe what you are actually looking at.

Filtering matches on the `rule_id` prefix, which means an engine's verdicts and
its data-quality notes are selected together — `GC-001.01` and `GC-001.DATA` both
match `GC-001`. That is intentional: selecting an engine and receiving its
verdicts but not its unassessed elements would be the same defect in miniature.

## When to Use a Subset

Given that it does not save time, subsetting is a **reporting** decision rather
than a performance one:

- **Issuing a focused package.** The mechanical designer receiving only GC and XM
  findings has a shorter, more actionable list than one receiving all five
  engines' output.
- **Early-stage triage.** A galvanic-only view answers "do we have a mixed-metal
  problem" without the noise of MIC findings on a model where operating
  temperatures are not yet set.
- **Discipline routing.** MC-001 findings belong to the water safety group rather
  than the design team on a healthcare project (see Q05). A MIC-only export is the
  right package for them.
- **Suppressing engines whose input data is not yet reliable.** If operating
  temperatures and flow velocities have not been modelled, MC-001 findings will be
  largely data-quality noise, and excluding them from an issued report is honest
  provided the exclusion is stated.

That last point carries an obligation: if you issue a narrowed report, **say so
in the cover note**. A report showing only GC findings with no statement of scope
reads as a complete corrosion assessment, and it is not.

## Cache Behaviour on Repeated Runs

- Keyed on **(project, analysis slug, model SHA-256)**. Change the model and the
  digest changes, so the next run recomputes rather than serving stale findings
  against a model that has moved on.
- Bounded and expiring — a limited number of recent results are held, for a
  limited period, evicting least-recently-used.
- **A miss is never an error.** The analysis simply runs. The cache is an
  optimisation and nothing depends on it for correctness — which matters because
  the store is per-process, so under multiple server workers a request can land on
  a worker that has never seen the entry. The only visible consequence is that it
  takes longer.
- Results are **not persisted**. They are derived data, reproducible from the
  model at any time.

The practical upshot: exporting CSV, then JSON, then BCF from one analysis does
not re-run the engines three times. Re-running the same analysis on an unchanged
model is effectively instant. Re-running after a genuine model change always
recomputes.

## When This Analysis Applies

Any corrosion run. Selection is available on corrosion only; seismic and
architecture have no engine subsets.

## What the Report Contains

The narrowed finding list plus recomputed `issue_stats` describing that narrowed
set. The `data_quality` count is kept separate from the four band totals, so an
unassessed element is never counted as low-risk in either the full or the
narrowed view.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "Across NASA-STD-6012, ASTM G48, CIRIA C692, EN ISO 15329, CIBSE TM13 and HSE
> HSG274, identify where the corrosion mechanisms interact: cases where one
> mechanism's recommended mitigation increases the risk of another, and cases
> where a standard states that two mechanisms must be assessed together. Give
> clause references and quote the interaction verbatim. Specifically address
> whether raising water storage temperature for Legionella control affects
> material-media or galvanic corrosion risk, and whether dielectric isolation
> affects crevice or microbial risk at the joint."

**Purpose.** Establish, from source, which engines cannot honestly be run in
isolation. The system already encodes one such interaction — MM-001's kinetics
guard exists precisely because 60 °C storage is mandated by HSG274 and required
by MC-001, and an unguarded MM-001 would flag what MC-001 requires. If other
interactions of that kind exist in the standards, subsetting guidance should name
them, and the selector should probably warn about them.

**Not for.** Deciding which engines to run on your project. That follows from the
system type, the media and the stage of design.

## Export Options

Export reflects whatever selection is applied at the time, in all three formats.
A CSV exported under a GC-only selection contains GC findings and GC-recomputed
totals. Export the unnarrowed JSON alongside it if you need the complete record.

## Next Steps for Your Project

1. Run everything once. It costs the same as running one engine, and the full
   result is what gets cached.
2. Use selection to shape the *packages* you issue — mechanical designer, water
   safety group, modeller — rather than to shape the run.
3. State the scope in the cover note whenever you issue a narrowed report.
4. Leave all five on unless you have a reason to narrow. Unchecking an engine
   removes findings from the report; it does not remove work from the run, and it
   does not make the analysis faster.
5. Re-run after model revisions. An unchanged model returns the cached result,
   which is also a useful signal that the file you uploaded is the file you
   uploaded last time.
