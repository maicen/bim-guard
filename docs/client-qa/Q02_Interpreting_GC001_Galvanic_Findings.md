# Q02: How do I interpret GC-001 (Galvanic Corrosion) findings?

## The Question

> "My report came back with 63 GC-001 findings. Eleven are Critical, twenty-two
> High. Each one has a score like 0.87 and mentions a voltage gap and an area
> ratio. I am a project manager, not a metallurgist. Which of these actually
> means something is going to leak, and what do I tell the mechanical
> subcontractor on Thursday?"

## The Answer

A GC-001 finding says one thing: two metals are in electrical contact with a
shared electrolyte, and one of them will corrode preferentially to protect the
other. The score is a weighted composite of three measurable terms, and reading
it back into those three terms tells you what the remedy is:

```
Score_GC = (0.50 × voltage_risk)
         + (0.30 × area_ratio_risk)
         + (0.20 × environment_multiplier)
```

**Voltage risk (50%)** is the potential difference between the two materials in
the galvanic series. It is the driving force: no gap, no cell. Copper against
carbon steel is roughly 0.5 V; copper against passive 316 stainless is small
enough that in most environments it falls below the NASA-STD-6012 compatibility
threshold entirely. This term is a **specification** problem — you fix it by
changing what is specified, or by breaking the electrical continuity.

**Area ratio risk (30%)** is the anode-to-cathode area ratio, and it is the term
most people get wrong. A small anode wired to a large cathode concentrates the
entire corrosion current into a small area. A carbon steel *fitting* in a copper
*run* is the dangerous geometry; a copper fitting in a carbon steel run is far
less so, even though the voltage gap is identical. If your score is being driven
by this term, the remedy is often geometric — change which part is the small
one — rather than material.

**Environment multiplier (20%)** is electrolyte severity: how conductive and how
persistently wet the contact is. A dry ceiling void suppresses the cell; a
plantroom floor gully, an external riser, or anything in a chloride or marine
class amplifies it. This term is why the same detail is Low in Munich and
Critical in Rotterdam.

Bands are Low below 0.35, Medium 0.35–0.65, High 0.65–0.85 and Critical above
0.85. Because voltage carries half the weight, a Critical finding almost always
means a large voltage gap, and usually an unfavourable area ratio on top of it.
A finding sitting at 0.66 — just into High — is typically a moderate gap that
the environment pushed over the line, and those are the ones worth a five-minute
conversation about whether the environment class on that zone is right.

## Reading One Finding End to End

A representative Critical finding, and what each part is telling you:

| Field | Value | What it means |
| --- | --- | --- |
| `rule_id` | `GC-001.01` | Galvanic verdict (not `.DATA`, so it was scored) |
| `band` / `score` | `critical` / `0.87` | Above the 0.85 threshold |
| voltage gap | ~0.50 V | Large driving force — a specification problem |
| area ratio | small anode / large cathode | Concentrated attack — accelerates it |
| environment | `T3_chloride` or worse | Conductive, persistently wet |
| `citations` | NASA-STD-6012 + clause | The threshold's source, auditable |
| `mitigation` | `MIT-GC-001` | Dielectric isolation at every contact point |

A `GC-001.DATA` finding is a different animal. It is not a verdict — it means an
element could not be scored, usually because the material name in the IFC did
not resolve to a galvanic series entry. Those go back to the modeller.

## Triage for Thursday's Meeting

1. **Critical, small anode.** Genuine leak risk within the warranty period.
   Dielectric union or flanged isolation kit at the junction, or respecify the
   fitting to match the run. Non-negotiable.
2. **Critical, large anode.** Real, but the failure is distributed thinning
   rather than a pinhole. Isolation is still the answer; the urgency is lower.
3. **High in a wet or external zone.** Treat as Critical. The environment term
   is only 20% of the weight but it is the term that changes over the building's
   life — a "dry" void that later houses a condensate drain is not dry.
4. **High in a controlled internal zone.** Specification review. Often resolved
   by a fitting change at no cost if caught before procurement.
5. **Medium and Low.** Record them. They are the evidence that the detail was
   considered, which is what a client's asset team is actually asking for.
6. **`GC-001.DATA`.** Modeller action. Not an engineering issue.

The one thing not to do is count findings. Sixty-three findings on one riser
detail repeated sixty-three times is one decision, not sixty-three. Sort by
element and by mitigation before you sort by count.

## When This Analysis Applies

Any model with more than one metal in a wetted system: mixed copper/steel
domestic water, stainless plant tied into carbon steel distribution, galvanised
containment penetrating a wet zone, dissimilar valve and pipe bodies, and
practically every refurbishment that ties new work into an existing system.

## What the Report Contains

Per finding: the composite score and band, the three contributing terms in the
finding metadata, the resolved material names on both sides of the couple, the
environment class applied, the standard and clause behind the threshold, and the
catalogued mitigation. Aggregate `issue_stats` give totals per band plus a
separate `data_quality` count, which is deliberately kept out of the band totals
so an unassessed element is never mistaken for a Low-risk one.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "From NASA-STD-6012, EN ISO 12944 and the Euro Inox / WorldStainless galvanic
> corrosion guidance, extract the full anodic index / galvanic series table for
> metals used in building services, and the permitted potential difference for
> each environment class the standard defines (controlled, normal, harsh or the
> standard's own naming). Report the sign convention each source uses explicitly
> — state whether more positive means more anodic or more cathodic in that
> source — and give the clause reference for each value. Where a source gives an
> anode-to-cathode area ratio caveat, quote it verbatim."

**Purpose.** The sign convention is not decoration. Two published series use
opposite conventions for the same numbers, and a pack that guesses gets the
victim of the couple backwards half the time. The prompt asks for the convention
as sourced data so the rule pack can declare it (`series_convention`) rather
than infer it.

**Not for.** Asking whether your 0.87 finding is a real problem. That question is
answered by the engine plus a corrosion engineer looking at the detail, not by a
language model reading a standard.

## Export Options

- **BCF 2.1** — each finding becomes a topic with a viewpoint framed on the
  element, so the mechanical subcontractor opens the junction rather than hunting
  a `GlobalId`.
- **CSV** — best for the triage table above. Sort by mitigation, then by band.
- **JSON** — carries the per-term breakdown in metadata for anyone wanting to
  re-plot the scores or audit the weighting.

## Next Steps for Your Project

1. Group findings by mitigation and by repeated detail before issuing anything.
2. Issue Critical and High as a BCF package to the mechanical designer with the
   junction viewpoints attached.
3. Verify the environment class on each zone with the design team — it moves 20%
   of every score in that zone and is the assumption most often wrong.
4. Send `GC-001.DATA` findings to the modeller as a material-naming task.
5. Re-run after the revision and compare band totals, not finding counts.
