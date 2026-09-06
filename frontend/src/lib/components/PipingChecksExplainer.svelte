<script lang="ts">
  /**
   * Plain-English explainer for the five piping corrosion checks.
   *
   * Sits directly under the Run Audit / ENGINES block on the Piping audit so it
   * reads as part of engine selection rather than page furniture. Collapsed by
   * default. Each check's row is tied to its engine chip: unticking a chip dims
   * that row (the chips' own disabled palette) without making it unreadable, and
   * opening the panel expands the first check whose engine is still ticked.
   *
   * Text is transcribed verbatim from BIMGUARD_Piping_Checks_Plain_English.md —
   * markdown converted to markup by hand, wording untouched.
   */
  import { ChevronDown, BookOpen } from "lucide-svelte";
  import type { Snippet } from "svelte";

  interface Props {
    /** Engine ids currently ticked in the ENGINES chip row, e.g. ["GC", "MC"]. */
    selectedEngines?: string[];
  }

  let { selectedEngines = [] }: Props = $props();

  const CHECKS = [
    { id: "GC", title: "Check 1 — Galvanic corrosion (GC-001)" },
    { id: "CC", title: "Check 2 — Crevice corrosion (CC-001)" },
    { id: "MC", title: "Check 3 — Microbial corrosion (MC-001)" },
    { id: "MM", title: "Check 4 — Material-against-liquid (MM-001)" },
    { id: "XM", title: "Check 5 — Cross-material joints (XM-001)" },
  ] as const;

  let open = $state(false);
  let expanded: string | null = $state(null);

  const isSelected = (id: string) => selectedEngines.includes(id);

  function togglePanel() {
    open = !open;
    // Opening lands the reader on the first check they are actually running.
    if (open) {
      expanded = (CHECKS.find((c) => isSelected(c.id)) ?? CHECKS[0]).id;
    }
  }

  function toggleRow(id: string) {
    expanded = expanded === id ? null : id;
  }
</script>

<div class="rounded-2xl border border-slate-800/80 bg-slate-900/40">
  <button
    type="button"
    onclick={togglePanel}
    aria-expanded={open}
    class="flex w-full items-center gap-2 rounded-2xl px-4 py-3 text-left transition-colors hover:bg-slate-900/60"
  >
    <BookOpen class="h-4 w-4 shrink-0 text-amber-400" />
    <span class="text-sm font-bold text-slate-100">What do these checks do?</span>
    <ChevronDown
      class="ml-auto h-4 w-4 shrink-0 text-slate-400 transition-transform {open
        ? 'rotate-180'
        : ''}"
    />
  </button>

  {#if open}
    <div class="space-y-5 border-t border-slate-800/80 px-4 py-4">
      <!-- How to read the results -->
      <section class="space-y-2">
        <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400">
          How to read the results
        </h3>
        <p class="text-xs text-slate-300 sm:text-sm">
          Every pipe that gets checked comes out with one of these:
        </p>
        <ul class="ml-4 list-disc space-y-1 text-xs text-slate-300 sm:text-sm">
          <li><strong class="text-slate-100">Low</strong> — nothing to worry about.</li>
          <li><strong class="text-slate-100">Medium</strong> — worth a designer's attention.</li>
          <li>
            <strong class="text-slate-100">High</strong> — likely to cause a problem; change something.
          </li>
          <li>
            <strong class="text-slate-100">Critical</strong> — this will fail; do not build it like this.
          </li>
          <li>
            <strong class="text-slate-100">Undetermined</strong> — the model didn't contain enough information
            to say. BIMGUARD refuses to guess.
          </li>
        </ul>
        <p class="text-xs text-slate-300 sm:text-sm">
          That last one matters. A lot of software would fill in the blanks with an assumption and give
          you an answer anyway. BIMGUARD doesn't. If the model doesn't say what a pipe is made of, the
          check says "I can't tell you" and explains what's missing. A wrong answer that looks confident
          is worse than an honest "don't know".
        </p>
        <p class="text-xs text-slate-300 sm:text-sm">
          Every result also shows its working: which rule was applied, which published engineering
          standard the rule came from, and where each piece of data came from. Anyone can trace a result
          back to the page in the standard that justifies it.
        </p>
      </section>

      <!-- One expandable row per check, in chip order -->
      {#snippet row(id: string, title: string, body: Snippet)}
        {@const on = isSelected(id)}
        <div
          class="overflow-hidden rounded-xl border transition-colors {on
            ? 'border-amber-800/80 bg-amber-950/20'
            : 'border-slate-800 bg-slate-900/60'}"
        >
          <button
            type="button"
            onclick={() => toggleRow(id)}
            aria-expanded={expanded === id}
            class="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-slate-800/40"
          >
            <span
              class="font-mono text-caption font-semibold {on ? 'text-amber-300' : 'text-slate-500'}"
            >
              {title}
            </span>
            {#if !on}
              <span class="font-mono text-micro uppercase tracking-wider text-slate-600"
                >not selected</span
              >
            {/if}
            <ChevronDown
              class="ml-auto h-3.5 w-3.5 shrink-0 {on
                ? 'text-amber-400'
                : 'text-slate-600'} transition-transform {expanded === id ? 'rotate-180' : ''}"
            />
          </button>
          {#if expanded === id}
            <div
              class="space-y-2 border-t border-slate-800/80 px-3 py-3 text-xs text-slate-300 sm:text-sm"
            >
              {@render body()}
            </div>
          {/if}
        </div>
      {/snippet}

      {#snippet gc()}
        <p>
          <strong class="text-slate-100">The everyday version.</strong> If you connect two different metals
          and get them wet, one of them starts eating the other. That's a battery — a very slow, very weak
          battery, but a battery. The same thing happens in a pipe system when a copper pipe is bolted to
          a steel bracket in a damp plant room. The steel is the "loser" in that pairing and slowly dissolves.
        </p>
        <p>
          <strong class="text-slate-100">What the check asks.</strong> For each pipe: what metal is it, what
          metal is it touching, and how wet is the surroundings? Some metal pairs are nearly harmless together;
          others are a bad idea. The check uses a published ranking of metals (how "hungry" each one is) and
          a published threshold for how far apart two metals can be before the pairing becomes risky in a given
          environment. It also looks at the <em>sizes</em> of the two parts — a small steel bolt on a big copper
          pipe corrodes far faster than the other way round, because all the damage is concentrated on the small
          piece.
        </p>
        <p>
          <strong class="text-slate-100">What it needs from the model.</strong> The pipe's material, its partner's
          material, and the environment (dry indoor, damp indoor, outdoor, marine). If the model only names one
          material and no partner, the check reports that no pairing could be found rather than inventing one.
        </p>
        <p>
          <strong class="text-slate-100">Example.</strong> A copper pipe with a galvanised-steel support bracket
          in a plant room: <strong class="text-slate-100">Medium</strong>. A stainless pipe on a stainless bracket:
          <strong class="text-slate-100">Low</strong>. A pipe with no material recorded:
          <strong class="text-slate-100">Undetermined — material not resolved</strong>.
        </p>
      {/snippet}

      {#snippet cc()}
        <p>
          <strong class="text-slate-100">The everyday version.</strong> Think of a tiny gap — under a washer,
          inside a threaded joint, between a flange and its gasket. Water gets into the gap and can't get out.
          The trapped water goes stale, turns slightly acidic, and starts attacking the metal from inside the
          gap where nobody can see it. Stainless steel, which people assume never rusts, is especially vulnerable
          to this — it's fine in open air and in flowing water, but it hates stagnant water in a tight gap.
        </p>
        <p>
          <strong class="text-slate-100">What the check asks.</strong> Two things. How tight is the gap? (An open,
          smooth joint is low risk; a tight threaded joint is high risk.) And is the metal tough enough for the
          water it's sitting in? Each grade of stainless steel has a published temperature above which crevice
          corrosion starts in salty water. The check compares that temperature against what the environment demands.
          A basic stainless grade in a swimming-pool plant room — warm, humid, chlorinated air — is a known disaster.
        </p>
        <p>
          <strong class="text-slate-100">What it needs from the model.</strong> The joint type (which the check works
          out from what kind of component it is — flange, threaded fitting, welded joint), the material grade, and the
          environment.
        </p>
        <p>
          <strong class="text-slate-100">Example.</strong> Standard stainless flanges in a pool plant room:
          <strong class="text-slate-100">Critical</strong> — the failure mode the galvanic check can't see at all,
          because there's no second metal involved. The same flanges in a dry ceiling void:
          <strong class="text-slate-100">Low</strong>.
        </p>
      {/snippet}

      {#snippet mc()}
        <p>
          <strong class="text-slate-100">The everyday version.</strong> Bacteria live in water pipes. Mostly they're
          harmless. But in warm, slow-moving or stagnant water they multiply, form slime on the pipe wall, and the
          chemistry underneath that slime eats the metal. This is also the same set of conditions that lets Legionella
          bacteria grow — the bug behind Legionnaires' disease — which is why hospitals care about it twice over.
        </p>
        <p>
          <strong class="text-slate-100">What the check asks.</strong> Three things about the water in each pipe: how
          fast is it moving (fast water washes bacteria away; stagnant water lets them settle), how warm is it
          (25–45 °C is the danger zone — warm enough for bacteria, not hot enough to kill them), and is this a
          <em>dead leg</em> — a branch of pipe that goes nowhere, so the water in it never moves at all? A dead leg
          of warm water is the textbook worst case.
        </p>
        <p>
          <strong class="text-slate-100">What it needs from the model.</strong> Flow speed, water temperature, and
          whether the pipe is a dead leg. Most 3D models don't record any of these — they show <em>where</em> the pipe
          is, not what's happening inside it. So on a typical model this check comes back Undetermined for every pipe,
          with the reason spelled out. On a model that does carry the data, it scores every pipe that has it and refuses
          the rest.
        </p>
        <p>
          <strong class="text-slate-100">Example.</strong> A condensate drain at 30 °C with no flow:
          <strong class="text-slate-100">Critical</strong>. The same pipe carrying water at 65 °C:
          <strong class="text-slate-100">Low</strong> — too hot for the bacteria. A pipe with no flow or temperature
          data: <strong class="text-slate-100">Undetermined — hydraulic data unavailable</strong>.
        </p>
      {/snippet}

      {#snippet mm()}
        <p>
          <strong class="text-slate-100">The everyday version.</strong> Some materials just shouldn't carry some
          liquids. Galvanised steel is fine for cold water, but hot water strips the zinc coating and then the steel
          underneath rusts. Copper is fine almost everywhere, but in certain water chemistries it pits. Plastic is fine
          with cold water and hopeless with steam. This isn't about two metals touching or about gaps — it's simply
          "is this pipe made of something that can live with what's flowing through it?"
        </p>
        <p>
          <strong class="text-slate-100">What the check asks.</strong> For each pipe: what's it made of, and what
          system is it part of — cold water, hot water, chilled water, heating, drainage, fire main? Each system carries
          a known liquid at a known temperature range. The check looks up the material-and-liquid pairing in a
          compatibility table and reports whether it's a known problem.
        </p>
        <p>
          <strong class="text-slate-100">What it needs from the model.</strong> The material and the system the pipe
          belongs to. Unlike the first three checks, this one needs to know about the <em>system</em> — which pipes
          belong together — not just the individual pipe. That's why it's built differently under the hood: it looks at
          the whole network of pipes, not one pipe at a time.
        </p>
        <p>
          <strong class="text-slate-100">Example.</strong> Galvanised steel on a hot-water system:
          <strong class="text-slate-100">Medium</strong> (zinc coating will fail). Copper on cold water:
          <strong class="text-slate-100">Low</strong>. A material the table doesn't cover:
          <strong class="text-slate-100">Undetermined — pairing not mapped</strong>.
        </p>
      {/snippet}

      {#snippet xm()}
        <p>
          <strong class="text-slate-100">The everyday version.</strong> Walk along a pipe run and you'll find places
          where the material changes — copper becomes steel, steel becomes plastic. Every one of those changeovers is
          a joint between two different materials, and every one is a place where trouble can start: a galvanic pairing,
          a fitting that expands at a different rate to the pipe it's screwed into, a plastic that softens next to a hot
          metal. This check finds every changeover in the whole network and flags the ones that are known to cause
          problems.
        </p>
        <p>
          <strong class="text-slate-100">What the check asks.</strong> Where does one material connect directly to a
          different one? It needs to know the <em>connections</em> — which pipe joins which — and then checks each
          dissimilar pairing against a published list of problematic combinations.
        </p>
        <p>
          <strong class="text-slate-100">What it needs from the model.</strong> Materials, and how the pipes connect to
          each other. Many models don't record the connections properly, in which case the check can't find the joints
          and reports very little. On a model that does, it finds every changeover.
        </p>
        <p>
          <strong class="text-slate-100">Example.</strong> A copper-to-galvanised-steel joint on a wet system:
          <strong class="text-slate-100">High</strong>. A copper-to-brass joint:
          <strong class="text-slate-100">Medium</strong> or <strong class="text-slate-100">Low</strong> depending on the
          environment. No connection data in the model: the check reports what it couldn't see.
        </p>
      {/snippet}

      <div class="space-y-2">
        {@render row(CHECKS[0].id, CHECKS[0].title, gc)}
        {@render row(CHECKS[1].id, CHECKS[1].title, cc)}
        {@render row(CHECKS[2].id, CHECKS[2].title, mc)}
        {@render row(CHECKS[3].id, CHECKS[3].title, mm)}
        {@render row(CHECKS[4].id, CHECKS[4].title, xm)}
      </div>

      <!-- Why five checks and not one -->
      <section class="space-y-2 border-t border-slate-800/80 pt-4">
        <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400">
          Why five checks and not one
        </h3>
        <p class="text-xs text-slate-300 sm:text-sm">
          Each check looks for a different way of failing, and they don't overlap. The clearest example is
          stainless steel flanges in a swimming-pool plant room: the galvanic check gives them a perfect
          <strong class="text-slate-100">Low</strong> — no second metal, no battery — while the crevice check
          gives them <strong class="text-slate-100">Critical</strong>. If you only ran one check, you'd sign
          off a design that leaks within a few years. Running all five means each failure mode gets the question
          that actually finds it.
        </p>
        <p class="text-xs text-slate-300 sm:text-sm">
          The five checks also fall into two families, which matters for what data they need:
        </p>
        <ul class="ml-4 list-disc space-y-1 text-xs text-slate-300 sm:text-sm">
          <li>
            <strong class="text-slate-100">Checks 1, 2 and 3 look at one pipe at a time.</strong> They need to
            know things about that pipe: its material, its surroundings, its water. They work even when the model
            is patchy, because each pipe is judged on its own.
          </li>
          <li>
            <strong class="text-slate-100">Checks 4 and 5 look at the whole network.</strong> They need to know
            which pipes belong to which system and which pipes join which. They can see things the single-pipe
            checks can't, but they go quiet when the model doesn't record those relationships.
          </li>
        </ul>
        <p class="text-xs text-slate-300 sm:text-sm">
          Neither family is better; they see different things. Together they cover the five ways an MEP pipe system
          corrodes.
        </p>
      </section>
    </div>
  {/if}
</div>
