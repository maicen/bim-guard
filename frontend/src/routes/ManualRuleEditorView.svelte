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

  export let onBack: () => void;

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
  let activeTarget: string | null = null;
  let successMessage = "";

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

<div class="space-y-5 max-w-4xl mx-auto pb-12">
  <PageHeader
    category="Analysis"
    title="Manual Rule Editor"
    subtitle="Choose a building element category, then add a rule against one of its known properties."
    icon={ListChecks}
  >
    <div slot="actions">
      <button
        type="button"
        on:click={onBack}
        class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-semibold bg-slate-900/60 hover:bg-slate-800 text-slate-300 hover:text-slate-50 border border-slate-800 transition-colors"
      >
        <ArrowLeft class="w-3.5 h-3.5" />
        <span>Back to Rules Catalog</span>
      </button>
    </div>
  </PageHeader>

  {#if successMessage}
    <div class="p-4 rounded-xl bg-emerald-950/50 border border-emerald-800 text-emerald-300 text-xs flex items-center gap-2.5">
      <CheckCircle2 class="w-4 h-4 text-emerald-400 shrink-0" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <div class="space-y-3">
    {#each ARCH_DOMAINS as domain}
      {@const domIcon = DOMAIN_ICONS[domain.key] || Layers}

      <div class="border border-slate-800 rounded-2xl bg-slate-900/40 p-4 space-y-3">
        <div class="flex items-center gap-2.5">
          <svelte:component this={domIcon} class="w-4 h-4 text-slate-300" />
          <h3 class="text-sm font-bold text-slate-50">{domain.label}</h3>
          {#if domain.computed}
            <span class="px-2 py-0.5 rounded-full text-micro font-semibold uppercase bg-slate-800 text-slate-400 border border-slate-700">
              Computed
            </span>
          {/if}
        </div>

        {#if domain.computed}
          <div class="flex items-start gap-2.5 text-xs text-slate-400 bg-slate-950/40 border border-slate-800/80 rounded-xl p-3">
            <Info class="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
            <span>
              {domain.label} is computed automatically by the ARCH engine, not from editable rules — nothing to add here.
            </span>
          </div>
        {:else}
          <div class="space-y-2">
            {#each domain.targets as target}
              <div class="rounded-xl bg-slate-950/40 border border-slate-800/80 overflow-hidden">
                <div class="flex items-center justify-between p-3">
                  <div class="flex items-center gap-2">
                    <span class="text-xs font-bold text-slate-200">{target.label}</span>
                    <span class="text-micro font-mono text-slate-500">{target.ifcClass}</span>
                  </div>
                  <button
                    type="button"
                    on:click={() => toggleAdd(target)}
                    class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-caption font-semibold transition-colors {activeTarget === target.ifcClass
                      ? 'bg-slate-800 text-slate-300 border border-slate-700'
                      : 'bg-accent/15 hover:bg-accent/25 text-accent border border-accent/30'}"
                  >
                    {#if activeTarget === target.ifcClass}
                      <X class="w-3 h-3" />
                      <span>Cancel</span>
                    {:else}
                      <Plus class="w-3 h-3" />
                      <span>Add Rule</span>
                    {/if}
                  </button>
                </div>

                {#if activeTarget === target.ifcClass}
                  <div class="p-3 pt-0">
                    <div class="p-3 rounded-xl bg-slate-900/60 border border-slate-800">
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
