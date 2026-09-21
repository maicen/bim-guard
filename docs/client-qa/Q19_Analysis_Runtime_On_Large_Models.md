# Q19: How long does analysis take on a large model?

## The Question

> "Our federated model is about 900 MB and I have no idea how many elements —
> tens of thousands. Is this a coffee-break thing or an overnight thing? I need
> to know whether I can run it in the middle of a coordination meeting or whether
> I have to plan around it."

## The Answer

For a building model of that scale, plan for **minutes, not hours** — but plan for
the first run of a corrosion analysis to be the long one, and know which part of
it is slow.

The dominant cost in a corrosion run is not the engines. It is extracting the
piping network from the IFC: resolving materials, media, diameters, joint types,
system assignments and — most expensively — the connectivity graph between
elements. On a large model, that extraction has been measured at around **82
seconds**. The five corrosion engines then score against that extracted data,
which is fast by comparison because it is arithmetic over a prepared structure
rather than traversal of an IFC file.

So the shape of the timing is: a substantial parsing cost, then a comparatively
cheap scoring cost, and no meaningful additional cost per engine. This is exactly
why engine selection does not speed anything up (Q18) — the expensive work
happens before any engine runs.

Architecture and seismic runs are generally faster than corrosion. Architecture
reads properties off elements and evaluates per-element thresholds; seismic reads
geometry and generates and tests clearance envelopes, which is heavier than
architecture but lighter than piping network extraction.

To answer the practical question directly: **you can run it in a coordination
meeting**, but do not run it during the five minutes before one. Run it before you
walk in.

## What Affects the Time

| Factor | Effect | Notes |
| --- | --- | --- |
| **Piping element count and connectivity density** | Largest single factor on corrosion runs | Network extraction dominates; a dense MEP model costs more than a large but sparse one |
| **Geometry complexity** | Largest factor on seismic runs | Every braced element needs a real bounding box read from the model |
| **Element count overall** | Roughly linear on architecture runs | Per-element property evaluation |
| **IFC schema version** | Marginal | IFC2X3 and IFC4 parse comparably; some class lookups are skipped on schemas that do not define them |
| **File size** | Weak proxy | A 900 MB model of mostly repeated furniture is cheaper than a 200 MB model of dense MEP |
| **Engines selected** | **None** | Selection filters results; it does not skip computation |
| **Cache state** | Very large | A cache hit is effectively instant |

## Caching — the Practical Speed Story

The cache is where the real time savings are, and it is worth understanding
because it changes how you plan a session.

Results are keyed on **(project, analysis slug, model SHA-256)**. The digest is
computed on upload and on parse, so the key reuses an existing value rather than
inventing a second one. The consequences:

- **Repeated exports are free.** Downloading CSV, then JSON, then BCF from one
  analysis re-runs nothing. This was the original reason the cache exists — those
  three downloads used to re-run the analysis three times.
- **Re-running an unchanged model is effectively instant.** The result comes from
  the cache.
- **Changing the model always recomputes.** A cache keyed on project alone would
  go stale the moment someone re-uploads, and the next download would serve
  findings for the previous model while the interface showed the new one. Keying
  on the digest means a changed model cannot hit a stale entry — it simply misses.
- **The cache is bounded and expiring.** A limited number of recent results are
  held for a limited period, evicting least-recently-used. It holds recent work,
  not history.
- **A miss is never an error.** The store is per-process, so under multiple server
  workers a request can land on a worker that has never seen the entry. The only
  visible consequence is that the run takes longer. Nothing depends on the cache
  for correctness.
- **Results are not persisted.** They are derived data, reproducible from the
  model at any time. Persisting them would add a schema, a migration and an
  invalidation problem in exchange for saving a recomputation.

If you need the results after the cache period, export them. The export is the
durable artefact; the cache is not.

## Parallelisation

The engines are not currently parallelised across cores within a single run — the
work is sequential through parsing, then scoring, then reporting. In production
the server runs multiple workers, which parallelises *concurrent requests* rather
than a single analysis. Practically: two people running analyses on different
projects do not queue behind each other, but one large model does not get faster
by having more cores available.

The corollary of per-process caching under multiple workers is worth restating:
the same request twice may hit different workers and recompute the second time.
That is by design, and it is why a cache miss must never be an error.

## Watching a Run in Progress

A corrosion run reports live progress over server-sent events, moving through
validation, parsing, engine run, scoring and reporting. On a large model you will
see it sit in parsing for most of the run — that is the network extraction, and it
is the expected shape rather than a stall.

Seismic and architecture runs do not bind to that tracker, deliberately: binding
them would reset a corrosion run's stages for the same project. Their results are
complete; there is simply no live stage display. A seismic run that appears to be
doing nothing is running.

## When This Analysis Applies

Planning any analysis session, and particularly planning a live demonstration or a
run inside a meeting. The rule of thumb: first run of a corrosion analysis on a
large model, allow a few minutes; everything after that on the same model, near
instant.

## What the Report Contains

Analysis timing is logged per run — project, analysis slug, issue count and
whether the result came from cache. If a run is taking longer than expected, that
log tells you whether it is genuinely recomputing or whether something upstream
is the problem.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "From ISO 16739-1, describe how IFC expresses connectivity between distribution
> elements: the port model, `IfcRelConnectsPortToElement`, `IfcRelNests`,
> `IfcRelConnectsPorts`, and the system assignment relationships. Identify which
> relationships must be traversed to establish that two piping elements are
> physically connected, and whether any of that connectivity can be derived from
> spatial containment or geometric adjacency instead of explicit relationships.
> Give entity names exactly."

**Purpose.** Network extraction is the performance bottleneck, and it is a graph
traversal problem. Understanding precisely which relationships must be walked —
and whether any can be safely derived rather than traversed — is what would make
the traversal cheaper without weakening the cross-material engine's results.

**Not for.** Estimating your own model's runtime. Run it once and measure; the
factors above vary too much between models for a general figure to be useful.

## Export Options

All three export formats read from the cached result, so exporting is fast
regardless of how long the original analysis took. Export before the cache period
elapses if you want to avoid a recomputation.

## Next Steps for Your Project

1. Run once before the meeting, not during it. The first corrosion run on a large
   model is the slow one.
2. Export everything you need while the result is cached — CSV, JSON and BCF
   together — rather than returning to it later.
3. Do not use engine selection as a speed lever. It filters results; it does not
   skip work.
4. Keep the exported JSON as the durable record. Results are not persisted, and
   the cache holds recent work rather than history.
5. If a run is unexpectedly slow, check the piping element and connectivity
   density before suspecting anything else. That is where the time goes.
