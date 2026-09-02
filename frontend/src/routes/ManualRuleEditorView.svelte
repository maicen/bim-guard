<script lang="ts">
  import { onMount } from "svelte";
  import {
    ArrowLeft,
    ChevronDown,
    ChevronRight,
    Plus,
    Pencil,
    Trash2,
    Wind,
    DoorOpen,
    Layers,
    Footprints,
    Droplets,
    Flame,
    Car,
    ListChecks,
    Info,
  } from "lucide-svelte";
  import { rulesApi } from "../lib/api";
  import type { Rule } from "../lib/types";
  import { ARCH_DOMAINS } from "../lib/archDomains";
  import type { ArchDomainTarget } from "../lib/archDomains";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import RuleForm from "../lib/components/RuleForm.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import SeverityBadge from "../lib/components/SeverityBadge.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";

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

  let rules: Rule[] = [];
  let isLoading = true;
  let error = "";

  let openDomains: Record<string, boolean> = { windows: true };

  // Only one add/edit form is open across the whole page at a time — the
  // target IFC class doubles as a unique key since every domain's targets
  // are distinct classes.
  let activeEditor: { ifcClass: string; rule: Rule | null } | null = null;
  let ruleToDelete: Rule | null = null;
  let isDeleteModalOpen = false;

  async function loadRules() {
    isLoading = true;
    error = "";
    try {
      rules = await rulesApi.list({ category: "Arch" }, { forceRefresh: true });
    } catch (err: any) {
      error = err.message || "Failed to load rules.";
    } finally {
      isLoading = false;
    }
  }

  onMount(loadRules);

  function rulesForTarget(ifcClass: string): Rule[] {
    return rules.filter(
      (r) => (r.target_ifc_class || "").toLowerCase() === ifcClass.toLowerCase(),
    );
  }

  function toggleDomain(key: string) {
    openDomains[key] = !openDomains[key];
  }

  function openAdd(target: ArchDomainTarget) {
    activeEditor = { ifcClass: target.ifcClass, rule: null };
  }

  function openEdit(target: ArchDomainTarget, rule: Rule) {
    activeEditor = { ifcClass: target.ifcClass, rule };
  }

  function closeEditor() {
    activeEditor = null;
  }

  async function handleSaved() {
    activeEditor = null;
    await loadRules();
  }

  function promptDelete(rule: Rule) {
    ruleToDelete = rule;
    isDeleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!ruleToDelete) return;
    const id = ruleToDelete.id;
    try {
      await rulesApi.delete(id);
      rules = rules.filter((r) => r.id !== id);
    } catch (err: any) {
      error = err.message || "Failed to delete rule.";
    } finally {
      ruleToDelete = null;
    }
  }
</script>

<div class="space-y-5 max-w-5xl mx-auto pb-12">
  <PageHeader
    category="Analysis"
    title="Manual Rule Editor"
    subtitle="Add or edit compliance rules per building element category — windows, doors, stairs, and more — with the properties each element type can be checked against."
    icon={ListChecks}
  >
    <div slot="actions">
      <button
        type="button"
        on:click={onBack}
        class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-semibold bg-slate-900/60 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800 transition-colors"
      >
        <ArrowLeft class="w-3.5 h-3.5" />
        <span>Back to Rules Catalog</span>
      </button>
    </div>
  </PageHeader>

  {#if error}
    <div class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
      {error}
    </div>
  {/if}

  {#if isLoading}
    <LoadingState message="Loading rule catalog..." />
  {:else}
    <div class="space-y-3">
      {#each ARCH_DOMAINS as domain}
        {@const domIcon = DOMAIN_ICONS[domain.key] || Layers}
        {@const domainRuleCount = domain.targets.reduce((sum, t) => sum + rulesForTarget(t.ifcClass).length, 0)}
        {@const isOpen = openDomains[domain.key] || false}

        <div class="border border-slate-800 rounded-2xl bg-slate-900/40 overflow-hidden">
          <button
            type="button"
            class="w-full flex items-center justify-between p-4 text-left hover:bg-slate-800/30 transition-colors"
            on:click={() => toggleDomain(domain.key)}
          >
            <div class="flex items-center gap-2.5">
              <svelte:component this={domIcon} class="w-4 h-4 text-slate-300" />
              <h3 class="text-sm font-bold text-white">{domain.label}</h3>
              {#if domain.computed}
                <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase bg-slate-800 text-slate-400 border border-slate-700">
                  Computed
                </span>
              {:else}
                <span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                  {domainRuleCount} rule{domainRuleCount === 1 ? "" : "s"}
                </span>
              {/if}
            </div>
            {#if isOpen}<ChevronDown class="w-4 h-4 text-slate-400" />{:else}<ChevronRight class="w-4 h-4 text-slate-400" />{/if}
          </button>

          {#if isOpen}
            <div class="border-t border-slate-800 p-4 space-y-4">
              {#if domain.computed}
                <div class="flex items-start gap-2.5 text-xs text-slate-400 bg-slate-950/40 border border-slate-800/80 rounded-xl p-3">
                  <Info class="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
                  <span>
                    {domain.label} is computed automatically by the ARCH engine (exit counts, travel distance,
                    fixture counts, etc.) rather than evaluated from editable property_check rules, so there's
                    nothing to add here.
                  </span>
                </div>
              {:else}
                {#each domain.targets as target}
                  {@const targetRules = rulesForTarget(target.ifcClass)}
                  <div class="space-y-2">
                    <div class="flex items-center justify-between">
                      <div class="flex items-center gap-2">
                        <span class="text-xs font-bold text-slate-200">{target.label}</span>
                        <span class="text-[10px] font-mono text-slate-500">{target.ifcClass}</span>
                      </div>
                      <button
                        type="button"
                        on:click={() => (activeEditor?.ifcClass === target.ifcClass && !activeEditor.rule ? closeEditor() : openAdd(target))}
                        class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-[#0071e3]/15 hover:bg-[#0071e3]/25 text-[#0071e3] border border-[#0071e3]/30 transition-colors"
                      >
                        <Plus class="w-3 h-3" />
                        <span>Add Rule</span>
                      </button>
                    </div>

                    {#if targetRules.length === 0}
                      <div class="text-[11px] text-slate-500 italic px-1">No rules defined for {target.label.toLowerCase()} yet.</div>
                    {:else}
                      <div class="border border-slate-800 rounded-xl overflow-hidden divide-y divide-slate-800/80">
                        {#each targetRules as rule}
                          <div class="p-3">
                            {#if activeEditor?.rule?.id === rule.id}
                              <div class="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                                <RuleForm
                                  editingRule={rule}
                                  lockedTargetIfcClass={target.ifcClass}
                                  propertySuggestions={target.properties}
                                  onCancel={closeEditor}
                                  onSaved={handleSaved}
                                />
                              </div>
                            {:else}
                              <div class="flex items-center justify-between gap-3">
                                <div class="min-w-0">
                                  <div class="flex items-center gap-2 flex-wrap">
                                    <span class="text-xs font-mono font-bold text-white">{rule.rule_id}</span>
                                    <SeverityBadge severity={rule.severity} />
                                  </div>
                                  <div class="text-[11px] text-slate-400 mt-0.5 truncate">
                                    {rule.description || "No description"}
                                  </div>
                                  <div class="text-[10px] text-slate-500 font-mono mt-0.5">
                                    {rule.property_set ? `${rule.property_set}.` : ""}{rule.property_name}
                                    {rule.operator}
                                    {rule.check_value ?? `[${rule.value_min ?? "-"}, ${rule.value_max ?? "-"}]`}
                                  </div>
                                </div>
                                <div class="flex items-center gap-1 shrink-0">
                                  <button
                                    type="button"
                                    on:click={() => openEdit(target, rule)}
                                    class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                                    title="Edit rule"
                                  >
                                    <Pencil class="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    type="button"
                                    on:click={() => promptDelete(rule)}
                                    class="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 transition-colors"
                                    title="Delete rule"
                                  >
                                    <Trash2 class="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              </div>
                            {/if}
                          </div>
                        {/each}
                      </div>
                    {/if}

                    {#if activeEditor?.ifcClass === target.ifcClass && !activeEditor.rule}
                      <div class="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                        <RuleForm
                          lockedTargetIfcClass={target.ifcClass}
                          propertySuggestions={target.properties}
                          onCancel={closeEditor}
                          onSaved={handleSaved}
                        />
                      </div>
                    {/if}
                  </div>
                {/each}
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<ConfirmModal
  bind:isOpen={isDeleteModalOpen}
  title="Delete Rule"
  message={`Are you sure you want to delete rule "${ruleToDelete?.rule_id || ""}"? This action cannot be undone.`}
  confirmText="Delete Rule"
  danger={true}
  onConfirm={confirmDelete}
  onCancel={() => (ruleToDelete = null)}
/>
