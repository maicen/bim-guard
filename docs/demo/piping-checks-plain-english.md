# What BIMGUARD's five piping checks actually do

*Written for someone with no engineering or computing background.*

---

## First, the problem it solves

Big buildings — hospitals, schools, office towers — are full of pipes. Water, heating, cooling, drainage, fire sprinklers. Those pipes are made of metal or plastic, they carry liquids at different temperatures, and they sit in places that range from bone-dry ceiling voids to damp plant rooms.

Metal pipes rust. Not all at once, and not all in the same way. Some combinations of metal, liquid and surroundings are fine for fifty years. Others start leaking in five. The trouble is that these problems are decided at the design stage — when someone picks copper here, steel there, a stainless flange in the plant room — but they only show up years later, hidden behind walls, when it's expensive to fix.

Before a building is built, a 3D computer model of it exists. BIMGUARD reads that model, looks at every pipe, and asks: *is this pipe likely to corrode, and if so, why?* It runs five separate checks, because there are five different ways a pipe can corrode, and each one needs a different question asked.

---

## How to read the results

Every pipe that gets checked comes out with one of these:

- **Low** — nothing to worry about.
- **Medium** — worth a designer's attention.
- **High** — likely to cause a problem; change something.
- **Critical** — this will fail; do not build it like this.
- **Undetermined** — the model didn't contain enough information to say. BIMGUARD refuses to guess.

That last one matters. A lot of software would fill in the blanks with an assumption and give you an answer anyway. BIMGUARD doesn't. If the model doesn't say what a pipe is made of, the check says "I can't tell you" and explains what's missing. A wrong answer that looks confident is worse than an honest "don't know".

Every result also shows its working: which rule was applied, which published engineering standard the rule came from, and where each piece of data came from. Anyone can trace a result back to the page in the standard that justifies it.

---

## Check 1 — Galvanic corrosion (GC-001)

**The everyday version.** If you connect two different metals and get them wet, one of them starts eating the other. That's a battery — a very slow, very weak battery, but a battery. The same thing happens in a pipe system when a copper pipe is bolted to a steel bracket in a damp plant room. The steel is the "loser" in that pairing and slowly dissolves.

**What the check asks.** For each pipe: what metal is it, what metal is it touching, and how wet is the surroundings? Some metal pairs are nearly harmless together; others are a bad idea. The check uses a published ranking of metals (how "hungry" each one is) and a published threshold for how far apart two metals can be before the pairing becomes risky in a given environment. It also looks at the *sizes* of the two parts — a small steel bolt on a big copper pipe corrodes far faster than the other way round, because all the damage is concentrated on the small piece.

**What it needs from the model.** The pipe's material, its partner's material, and the environment (dry indoor, damp indoor, outdoor, marine). If the model only names one material and no partner, the check reports that no pairing could be found rather than inventing one.

**Example.** A copper pipe with a galvanised-steel support bracket in a plant room: **Medium**. A stainless pipe on a stainless bracket: **Low**. A pipe with no material recorded: **Undetermined — material not resolved**.

---

## Check 2 — Crevice corrosion (CC-001)

**The everyday version.** Think of a tiny gap — under a washer, inside a threaded joint, between a flange and its gasket. Water gets into the gap and can't get out. The trapped water goes stale, turns slightly acidic, and starts attacking the metal from inside the gap where nobody can see it. Stainless steel, which people assume never rusts, is especially vulnerable to this — it's fine in open air and in flowing water, but it hates stagnant water in a tight gap.

**What the check asks.** Two things. How tight is the gap? (An open, smooth joint is low risk; a tight threaded joint is high risk.) And is the metal tough enough for the water it's sitting in? Each grade of stainless steel has a published temperature above which crevice corrosion starts in salty water. The check compares that temperature against what the environment demands. A basic stainless grade in a swimming-pool plant room — warm, humid, chlorinated air — is a known disaster.

**What it needs from the model.** The joint type (which the check works out from what kind of component it is — flange, threaded fitting, welded joint), the material grade, and the environment.

**Example.** Standard stainless flanges in a pool plant room: **Critical** — the failure mode the galvanic check can't see at all, because there's no second metal involved. The same flanges in a dry ceiling void: **Low**.

---

## Check 3 — Microbial corrosion (MC-001)

**The everyday version.** Bacteria live in water pipes. Mostly they're harmless. But in warm, slow-moving or stagnant water they multiply, form slime on the pipe wall, and the chemistry underneath that slime eats the metal. This is also the same set of conditions that lets Legionella bacteria grow — the bug behind Legionnaires' disease — which is why hospitals care about it twice over.

**What the check asks.** Three things about the water in each pipe: how fast is it moving (fast water washes bacteria away; stagnant water lets them settle), how warm is it (25–45 °C is the danger zone — warm enough for bacteria, not hot enough to kill them), and is this a *dead leg* — a branch of pipe that goes nowhere, so the water in it never moves at all? A dead leg of warm water is the textbook worst case.

**What it needs from the model.** Flow speed, water temperature, and whether the pipe is a dead leg. Most 3D models don't record any of these — they show *where* the pipe is, not what's happening inside it. So on a typical model this check comes back Undetermined for every pipe, with the reason spelled out. On a model that does carry the data, it scores every pipe that has it and refuses the rest.

**Example.** A condensate drain at 30 °C with no flow: **Critical**. The same pipe carrying water at 65 °C: **Low** — too hot for the bacteria. A pipe with no flow or temperature data: **Undetermined — hydraulic data unavailable**.

---

## Check 4 — Material-against-liquid (MM-001)

**The everyday version.** Some materials just shouldn't carry some liquids. Galvanised steel is fine for cold water, but hot water strips the zinc coating and then the steel underneath rusts. Copper is fine almost everywhere, but in certain water chemistries it pits. Plastic is fine with cold water and hopeless with steam. This isn't about two metals touching or about gaps — it's simply "is this pipe made of something that can live with what's flowing through it?"

**What the check asks.** For each pipe: what's it made of, and what system is it part of — cold water, hot water, chilled water, heating, drainage, fire main? Each system carries a known liquid at a known temperature range. The check looks up the material-and-liquid pairing in a compatibility table and reports whether it's a known problem.

**What it needs from the model.** The material and the system the pipe belongs to. Unlike the first three checks, this one needs to know about the *system* — which pipes belong together — not just the individual pipe. That's why it's built differently under the hood: it looks at the whole network of pipes, not one pipe at a time.

**Example.** Galvanised steel on a hot-water system: **Medium** (zinc coating will fail). Copper on cold water: **Low**. A material the table doesn't cover: **Undetermined — pairing not mapped**.

---

## Check 5 — Cross-material joints (XM-001)

**The everyday version.** Walk along a pipe run and you'll find places where the material changes — copper becomes steel, steel becomes plastic. Every one of those changeovers is a joint between two different materials, and every one is a place where trouble can start: a galvanic pairing, a fitting that expands at a different rate to the pipe it's screwed into, a plastic that softens next to a hot metal. This check finds every changeover in the whole network and flags the ones that are known to cause problems.

**What the check asks.** Where does one material connect directly to a different one? It needs to know the *connections* — which pipe joins which — and then checks each dissimilar pairing against a published list of problematic combinations.

**What it needs from the model.** Materials, and how the pipes connect to each other. Many models don't record the connections properly, in which case the check can't find the joints and reports very little. On a model that does, it finds every changeover.

**Example.** A copper-to-galvanised-steel joint on a wet system: **High**. A copper-to-brass joint: **Medium** or **Low** depending on the environment. No connection data in the model: the check reports what it couldn't see.

---

## Why five checks and not one

Each check looks for a different way of failing, and they don't overlap. The clearest example is stainless steel flanges in a swimming-pool plant room: the galvanic check gives them a perfect **Low** — no second metal, no battery — while the crevice check gives them **Critical**. If you only ran one check, you'd sign off a design that leaks within a few years. Running all five means each failure mode gets the question that actually finds it.

The five checks also fall into two families, which matters for what data they need:

- **Checks 1, 2 and 3 look at one pipe at a time.** They need to know things about that pipe: its material, its surroundings, its water. They work even when the model is patchy, because each pipe is judged on its own.
- **Checks 4 and 5 look at the whole network.** They need to know which pipes belong to which system and which pipes join which. They can see things the single-pipe checks can't, but they go quiet when the model doesn't record those relationships.

Neither family is better; they see different things. Together they cover the five ways an MEP pipe system corrodes.

---

## What comes out the other end

Every pipe scored Medium or worse becomes an *issue* in a standard file format that any building-design program can open. Each issue points at the exact pipe in the 3D model, says which check raised it, gives the score and the reason, names the standard the rule came from, and suggests a fix. The designer opens the file, clicks an issue, and the model jumps to the pipe in question.

Pipes scored Low go into a spreadsheet instead — an asset register — so there's a complete record of everything that was checked, including the ones that passed and the ones the model didn't contain enough data to judge.
