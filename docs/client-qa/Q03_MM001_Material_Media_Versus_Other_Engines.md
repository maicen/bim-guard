# Q03: What is the difference between MM-001 (Material-Media) and the other engines?

## The Question

> "I understand galvanic — two metals touching. I understand crevice — a gap
> that traps water. But MM-001 flagged a copper run carrying softened water at
> 60 °C and there is no second metal anywhere near it, and no crevice. What is
> it actually complaining about, and why is that a separate engine rather than
> part of the others?"

## The Answer

Because it is a different physical question. GC-001, CC-001 and XM-001 all ask
about a *relationship*: between two metals, or between a metal and a geometry.
MM-001 asks about the material on its own terms — is this alloy an appropriate
carrier for this fluid, at this temperature, in this environment, for the design
life of the building? A copper run with no dissimilar metal and no crevice can
still fail, and it fails through the medium: soft, aggressive, low-pH or highly
oxygenated water attacks copper directly; ammonia-bearing media stress-crack
brass; chloride-bearing media pit SS304 with no galvanic partner required at
all. That mechanism has no "other metal" to point at, so it needs its own
assessment.

The score is a weighted composite of three terms that sum to 1.0, so the result
stays inside 0.0–1.0:

```
composite = w_material     × cell
          + w_environment  × environment_severity
          + w_temperature  × temperature_stress
```

The `cell` term is the material-media compatibility value looked up from the
pack's matrix — a curated grid of materials (carbon steel, galvanised steel,
cast and ductile iron, copper C12200, brass C46400, 90/10 cupronickel, SS304 and
others) against the media a building services network actually carries.
`environment_severity` comes from the shared T0–T5 ladder — dry, indoor damp,
humid, chloride, marine, industrial — because a pipe's surroundings attack it
from the outside independently of what is inside it. `temperature_stress`
reflects that reaction rates rise with temperature.

That third term is where MM-001 carries a design decision worth understanding.
Arrhenius kinetics *multiply* an existing corrosion rate; an additive score
would instead let temperature act as a hazard in its own right, which is wrong
for a benign pairing — there is no dominant mechanism for heat to accelerate.
The pack therefore carries a **kinetics guard**: below a configured `cell`
value, the temperature term is capped rather than allowed to carry the score
over the Medium floor on its own. The case that forced it is precisely yours.
Copper in 60 °C domestic hot water is not a defect — that storage temperature is
mandated by HSE HSG274 for Legionella control and is *required* by MC-001 in
this same system. Without the guard, MM-001 would flag exactly what MC-001
mandates. The guard caps the temperature term only; environment severity is an
external driver that does not depend on the material-media mechanism, so a
benign pairing in a marine splash zone stays exposed.

So the finding you are looking at is either (a) telling you the copper/softened
water cell itself is unfavourable — check the reported `cell` value in the
finding metadata — or (b) it is an environment-driven finding where the run's
surroundings, not its contents, pushed the score. Those are different remedies,
and the metadata distinguishes them.

## How MM-001 Relates to the Other Four

| Engine | Question it answers | Needs a second material? | Scope |
| --- | --- | --- | --- |
| GC-001 | Two metals in contact — which one sacrifices? | Yes | Element |
| CC-001 | Does this geometry trap electrolyte above the alloy's CCT? | No | Element |
| MC-001 | Will biofilm establish here? | No | Element |
| **MM-001** | **Is this material right for this fluid?** | **No** | **Network** |
| XM-001 | Are dissimilar metals coupled across the network graph? | Yes | Network |

MM-001 and XM-001 run over the network rather than element by element, because
both need the piping graph — MM-001 to resolve which medium a run actually
carries via its system assignment, XM-001 to walk connectivity between elements.

## Why This Matters for Long-Term System Life

Material-media mismatches are the classic "it worked for eight years" failure.
There is no clash, no code violation, and nothing visible at handover. The
system performs, then a cohort of pinhole leaks arrives together because every
run of that material carrying that medium was aging at the same rate. By the
time it shows, the pipework is buried, boxed or above a finished ceiling, and
the remedy is not a fitting change but a distribution replacement.

Catching it at model stage costs a specification line. The mitigations MM-001
returns are correspondingly specification-shaped: change the material, change
the medium treatment regime, or reduce the operating temperature where the
service permits it.

## Avoiding Premature Failures

- **Confirm the water chemistry assumption.** The pack is explicit that chloride
  ppm, pH, hardness and dissolved oxygen are absent from the IFC element data,
  so several cells assume typical potable chemistry. On a project with softened,
  demineralised, borehole or recycled water, that assumption needs checking
  before the scores are trusted.
- **Do not treat a `data_quality` finding as a pass.** An element with no
  resolvable material or no system assignment produces a data-quality Issue with
  mechanism `data_quality`, never silence. Reporting an unassessed pairing as
  clean would state that it is compliant, which is a different claim.
- **Watch the coverage gaps.** The shipped pack documents its own limits: gases
  (oxygen, nitrous oxide, vacuum, compressed air, natural gas), foul water and
  rainwater are deliberately not in the matrix, and several materials — SS304L,
  SS316L, SS316Ti, super duplex 2507, black steel, 70/30 cupronickel, aluminium,
  PEX, HDPE, PPR — are not yet rows. Runs in those categories will come back as
  data-quality findings rather than verdicts. That is by design, and it is why
  the report distinguishes the two.

## When This Analysis Applies

Any project where the medium is not plain treated potable water at ambient
temperature: healthcare (softened and RO water, hot water storage regimes),
laboratories and process, district heating and chilled water, swimming pools and
leisure, industrial washdown, and any building drawing on a private or
non-standard water supply.

## What the Report Contains

Per finding: composite score and band (Medium 0.35, High 0.65, Critical 0.85 —
matched to GC-001 and XM-001 so bands mean the same thing across mechanisms),
the three contributing terms, the resolved material and medium, the environment
class, whether the kinetics guard was applied, and the citation behind the cell
value. `data_quality` findings carry a `metadata["check"]` key naming what could
not be resolved.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "For each of copper C12200, brass C46400, 90/10 cupronickel, SS304, SS316,
> carbon steel, galvanised steel and ductile iron, extract from EN 12952-12,
> BS 8552, CIBSE Guide G, EN ISO 9308-1 and the relevant WRAS / manufacturer
> materials guidance: the media each material is stated to be suitable or
> unsuitable for; every quantitative water-chemistry limit given (chloride ppm,
> pH range, dissolved oxygen, hardness); the maximum continuous operating
> temperature; and the clause reference for each. Flag every case where a limit
> is given as guidance rather than a requirement, and every case where two
> sources disagree."

**Purpose.** Populate `parameters.compatibility_matrix` cells with a sourced
value and a `conf` grading (`established` vs `provisional`), and close the
documented coverage gaps above with reviewed rows rather than guessed ones.

**Not for.** Deciding whether the copper run in your model is acceptable. The
water chemistry on your project is a site fact, not a literature fact — get it
from the supply analysis, then check it against the sourced limits.

## Export Options

- **BCF 2.1** — one topic per affected run, with the material and medium in the
  topic description so the reviewer does not need the CSV alongside.
- **CSV** — the most useful format here, because MM-001 findings cluster by
  (material, medium) pair and a spreadsheet pivot collapses hundreds of elements
  into the handful of specification decisions they actually represent.
- **JSON** — carries the per-term breakdown and the kinetics-guard flag.

## Next Steps for Your Project

1. Pivot the CSV by material and medium. You are looking for decisions, not
   elements.
2. Confirm the water chemistry with the public health engineer before acting on
   any copper or SS304 finding — those cells are the ones most sensitive to it.
3. Send the specification-level findings to the MEP designer and the operating
   temperature findings to whoever owns the water safety plan, since lowering a
   storage temperature is a Legionella decision, not a corrosion one.
4. Treat the documented coverage gaps as scope: if your project is largely
   plastic or gas distribution, say so in the report cover note rather than
   letting a low finding count read as a clean result.
