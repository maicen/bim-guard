<script lang="ts">
  import {
    ArrowLeft,
    Plus,
    X,
    Wind,
    DoorOpen,
    Layers,
    Footprints,
    Droplets,
    Flame,
    Car,
    ListChecks,
    Info,
    CheckCircle2,
  } from "lucide-svelte";
  import type { Rule } from "../lib/types";
  import { ARCH_DOMAINS } from "../lib/archDomains";
  import type { ArchDomainTarget } from "../lib/archDomains";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import RuleForm from "../lib/components/RuleForm.svelte";
  import BsddBadge from "../lib/components/BsddBadge.svelte";

  interface Props {
    onBack: () => void;
  }

  let { onBack }: Props = $props();

  const DOMAIN_ICONS: Record<string, any> = {
    windows: Wind,
    doors: DoorOpen,
    stairs: Layers,
    ramps: Layers,
    egress: Footprints,
    washrooms: Layers,
    plumbing: Droplets,
    fire: Flame,
    garage: Car,
  };

  // Only one "Add Rule" form is open across the whole page at a time — the
  // target IFC class doubles as a unique key since every domain's targets
  // are distinct classes.
  let activeTarget: string | null = $state(null);
  let successMessage = $state("");

  function toggleAdd(target: ArchDomainTarget) {
    activeTarget = activeTarget === target.ifcClass ? null : target.ifcClass;
  }

  function handleSaved(target: ArchDomainTarget, rule: Rule) {
    activeTarget = null;
    successMessage = `Rule "${rule.rule_id}" saved for ${target.label}.`;
    setTimeout(() => {
      if (successMessage.includes(rule.rule_id || "")) successMessage = "";
    }, 5000);
  }
</script>

<div class="mx-auto max-w-4xl space-y-5 pb-12">
  <PageHeader
    category="Analysis"
    title="Manual Rule Editor"
    subtitle="Choose a building element category, then add a rule against one of its known properties."
    icon={ListChecks}
  >
    {#snippet actions()}
      <div>
        <button
          type="button"
          onclick={onBack}
          class="inline-flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900/60 px-3.5 py-2 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <ArrowLeft class="h-3.5 w-3.5" />
          <span>Back to Rules Catalog</span>
        </button>
      </div>
    {/snippet}
  </PageHeader>

  {#if successMessage}
    <div
      class="flex items-center gap-2.5 rounded-xl border border-emerald-800 bg-emerald-950/50 p-4 text-xs text-emerald-300"
    >
      <CheckCircle2 class="h-4 w-4 shrink-0 text-emerald-400" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <div class="space-y-3">
    {#each ARCH_DOMAINS as domain (domain.key)}
      {@const domIcon = DOMAIN_ICONS[domain.key] || Layers}

      {@const SvelteComponent = domIcon}
      <div class="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
        <div class="flex items-center gap-2.5">
          <SvelteComponent class="h-4 w-4 text-slate-300" />
          <h3 class="text-sm font-bold text-slate-50">{domain.label}</h3>
          {#if domain.computed}
            <span
              class="rounded-full border border-slate-700 bg-slate-800 px-2 py-0.5 text-micro font-semibold uppercase text-slate-400"
            >
              Computed
            </span>
          {/if}
        </div>

        {#if domain.computed}
          <div
            class="flex items-start gap-2.5 rounded-xl border border-slate-800/80 bg-slate-950/40 p-3 text-xs text-slate-400"
          >
            <Info class="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
            <span>
              {domain.label} is computed automatically by the ARCH engine, not from editable rules — nothing
              to add here.
            </span>
          </div>
        {:else}
          <div class="space-y-2">
            {#each domain.targets as target (target)}
              <div class="overflow-hidden rounded-xl border border-slate-800/80 bg-slate-950/40">
                <div class="flex items-center justify-between p-3">
                  <div class="flex items-center gap-2">
                    <span class="text-xs font-bold text-slate-200">{target.label}</span>
                    <BsddBadge kind="class" value={target.ifcClass} class="font-mono text-micro text-slate-500" />
                  </div>
                  <button
                    type="button"
                    onclick={() => toggleAdd(target)}
                    class="inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-caption font-semibold transition-colors {activeTarget ===
                    target.ifcClass
                      ? 'border border-slate-700 bg-slate-800 text-slate-300'
                      : 'border border-accent/30 bg-accent/15 text-accent hover:bg-accent/25'}"
                  >
                    {#if activeTarget === target.ifcClass}
                      <X class="h-3 w-3" />
                      <span>Cancel</span>
                    {:else}
                      <Plus class="h-3 w-3" />
                      <span>Add Rule</span>
                    {/if}
                  </button>
                </div>

                {#if activeTarget === target.ifcClass}
                  <div class="p-3 pt-0">
                    <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
                      <RuleForm
                        compact
                        lockedTargetIfcClass={target.ifcClass}
                        propertySuggestions={target.properties}
                        onCancel={() => (activeTarget = null)}
                        onSaved={(rule) => handleSaved(target, rule)}
                      />
                    </div>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  </div>
</div>
