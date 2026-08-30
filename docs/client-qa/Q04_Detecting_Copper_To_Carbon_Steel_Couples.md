# Q04: Can BIMGUARD detect copper-to-carbon-steel couples in my model? How accurate is it?

## The Question

> "This is the specific thing that burned us on the last job — copper branches
> teed into a carbon steel header, nobody caught it, and we were cutting out
> joints eighteen months after handover. Can BIMGUARD find those before we build?
> And be honest with me about accuracy: what does it need from the model, and
> what will it miss?"

## The Answer

Yes, and that pairing is close to the canonical case XM-001 was built for. The
reason it needs its own engine is worth understanding, because it explains both
the capability and the limit. GC-001 assesses an element that carries a declared
material *pairing* — it answers "these two materials are in contact, how bad is
it". But a copper branch teed into a steel header is not one element with two
materials. It is two elements, each with one material, joined by a fitting. From
GC-001's point of view there is nothing to compare. XM-001 solves that by
walking the piping connectivity graph extracted from the IFC — the
`IfcRelConnectsPortToElement` relationships in IFC2X3, `IfcRelNests` in IFC4 —
and comparing the material of every element against the materials of everything
it is connected to. Copper against carbon steel across a tee is exactly the shape
of thing that walk finds.

The scoring is:

```
composite = (0.50 × voltage_risk)
          + (0.30 × separation_factor)
          + (0.20 × environment_severity)
          then × mitigation_factor
```

`voltage_risk` is the potential gap between the two materials, normalised by
1.0 V and clamped — a 1.0 V spread covers the practical range from the most
active to the most noble material in building services, so a copper/carbon steel
gap of roughly 0.5 V lands around 0.5 on that term. `separation_factor` grades
how the two are connected: `direct_contact` (1.0) means they share a joint with
metallic continuity and a shared electrolyte, the full couple;`same_loop` (0.8)
means they are not touching but sit on the same system and are connected through
the piping graph, so a shared electrolyte path exists without direct metallic
contact. `environment_severity` uses the same T0–T5 ladder as MM-001 — one
approved ladder, not a second one that could drift out of step.

Then the mitigation multiplier. A joint recorded as a dielectric union
(`JT-014`) multiplies the composite by 0.10. That residual 0.10 rather than 0.00
is deliberate: the credit depends on the union being installed and remaining
intact, which is a commissioning check, not a design guarantee. So a mitigated
copper/steel junction still appears in the report, banded Low, carrying a
commissioning-verification note instead of a design action. Every dissimilar
couple is reported, including mitigated ones, because the audience is modellers
who do not routinely think about dissimilar metals — showing a mitigated couple
teaches the pattern, hiding it teaches nothing.

## Two Things That Make It More Accurate Than It Sounds

**The single-source rule.** XM-001 embeds no galvanic potentials of its own. The
project has exactly one galvanic series — the GC-001 payload — and one approved
environment ladder — MM-001's. Both are injected into XM-001 when its pack is
loaded, and the on-disk pack is asserted to hold neither. A second copy of the
series cannot drift out of step with the first, which is the usual way two
engines start disagreeing about the same physics.

**The direction problem is data, not inference.** Which material sacrifices is
resolved from the `noble` flags on the two series entries when they disagree,
and only otherwise from the pack's declared `series_convention`. That
declaration is data rather than logic buried in code for a concrete reason: the
two existing engines read the shared series with opposite sign conventions, so
guessing direction from the numbers would be wrong half the time. With neither
discriminator available, the couple becomes a `data_quality` finding rather than
a guess at which pipe is the victim. A wrong anode direction is worse than no
answer, because it sends the remedy to the wrong side of the joint.

## The Compatibility Floor — Why Some Couples Do Not Appear

NASA-STD-6012 defines a pair below the environment's threshold as *compatible*,
not as a mild couple. XM-001 suppresses those entirely rather than banding them
Low, because a Low finding says "we looked and it is minor" where the truth is
"this is not a couple". Naval brass against copper is a 0.05 V gap that is
compatible in every environment NASA-STD-6012 defines; without the floor, the
0.30 separation weight would fire on any direct contact regardless of voltage and
score it into Medium. A mitigated couple is a design decision worth showing; a
compatible material pair is not.

The floor **fails open**. An environment for which no threshold can be resolved
yields a finding, never silence — a mapping gap cannot quietly suppress real
couples.

## What Adjacency Data BIMGUARD Needs

This is where the honest answer about accuracy lives. XM-001 is only as good as
the connectivity and material data in the IFC:

1. **Connectivity.** Ports and connection relationships must be exported. Revit,
   ARCHICAD and Tekla can all do this, but MEP connectivity is frequently lost or
   partial in a coordination export configured for geometry only. If the graph is
   absent, XM-001 cannot see the tee, and the couple is invisible to it. Elements
   whose connectivity cannot be resolved raise a `data_quality` finding — check
   for those first, because their presence is the signal that your export
   settings, not your design, are the problem.
2. **Material names that resolve.** "Copper", "Cu", "C12200" and "Copper - Type
   L" all need to land on the same series entry. There is an alias map that
   handles a wide range of Revit and manufacturer naming conventions, but a
   material called `Default` or `Material 3` resolves to nothing and produces a
   data-quality finding rather than a false verdict.
3. **A system or zone assignment** to resolve the environment class. Without it,
   the environment term cannot be graded — and per the fail-open rule, that
   yields a finding rather than a suppression.
4. **Joint type**, where a dielectric union or isolating flange is designed in.
   Without it, the union gets no credit and the finding is scored unmitigated —
   conservative, but it will read as a false positive to an engineer who knows
   the union is there. Recording the joint type is the fix.

So: it will reliably find copper-to-carbon-steel where the connectivity and
materials are exported. It will not find it where the IFC does not describe the
connection — and in that case it tells you, via `data_quality`, rather than
returning a clean result.

## When This Analysis Applies

Refurbishment and system extension above all — new copper into existing steel is
the classic case. Also: plantroom tie-ins between stainless plant and carbon
steel distribution, mixed-material valve and pipe assemblies, and any project
where more than one subcontractor's package meets at an interface.

## What the Report Contains

Per couple: both element `GlobalId`s, both resolved materials, which side is the
anode, the potential gap in volts, the separation factor applied, the environment
class, any mitigation factor and its label, the composite score and band
(Medium 0.35, High 0.65, Critical 0.85), the citation, and the mitigation action
or the commissioning-verification note.

## NotebookLM Prompt (for rule authoring — NOT compliance decisions)

**Query:**

> "From BS 8539, NASA-STD-6012 and CIRIA C692, extract every stated method of
> electrically separating dissimilar metals in a piped assembly — dielectric
> unions, isolating flange kits, non-metallic gaskets and sleeves, coatings,
> spool pieces. For each: the clause reference, the degree of protection the
> standard claims for it, any stated limits or conditions on that claim, and any
> stated requirement for verification at commissioning or in service. Quote the
> conditions verbatim; do not paraphrase them into a single effectiveness value."

**Purpose.** Populate `parameters.mitigation_factors` with sourced multipliers,
and — more importantly — source the *conditions* on each claim, which is what
justifies a residual factor above zero rather than a clean cancellation.

**Not for.** Concluding that a particular junction in your model is protected.
Whether the union was actually specified, installed and left intact is a project
fact established by the specification and the commissioning record.

## Export Options

- **BCF 2.1** — most useful format for cross-material findings, because a couple
  is a *location* and the viewpoint takes the reviewer to the junction. A CSV row
  naming two `GlobalId`s does not.
- **CSV** — for tracking the commissioning verifications on mitigated couples.
- **JSON** — carries the anode direction and per-term breakdown.

## Next Steps for Your Project

1. Before reading any verdict, count the `data_quality` findings. A high count
   means the export lost connectivity or materials, and the verdicts underneath
   are incomplete.
2. Re-export with MEP connectivity and material assignments enabled if so, and
   re-run. This is usually a five-minute export-settings change.
3. Issue unmitigated Critical and High couples to the mechanical designer as BCF.
4. Take the mitigated Low findings and turn them into a commissioning checklist —
   they are the list of unions someone needs to confirm on site.
5. On a refurbishment, walk the interface locations physically. XM-001 finds what
   the model describes; it cannot see an existing pipe nobody surveyed.
