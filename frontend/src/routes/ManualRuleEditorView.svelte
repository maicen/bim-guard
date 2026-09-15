<script lang="ts">
  import { onMount } from "svelte";
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
    FolderOpen,
  } from "lucide-svelte";
  import type { Rule, RuleFolder, RulesetCategory } from "../lib/types";
  import { ARCH_DOMAINS } from "../lib/archDomains";
  import type { ArchDomainTarget } from "../lib/archDomains";
  import { rulesApi } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import RuleForm from "../lib/components/RuleForm.svelte";
  import BsddBadge from "../lib/components/BsddBadge.svelte";
  import { RulesetFolderModal } from "../lib/components/rules";

  interface Props {
    onBack: () => void;
  }

  let { onBack }: Props = $props();

  // Every rule authored on this page is grouped into a named ruleset
  // ("folder") so it can later be selected for a targeted compliance run
  // (RuleService.list_by_ruleset) instead of only ever landing in the
  // hardcoded default. Existing folders are offered as one-click picks;
  // typing a name that doesn't exist yet just creates it on first save.
  let folders: RuleFolder[] = $state([]);
  let folderName = $state("BUILDING-CODE-PART9");
  let isFolderModalOpen = $state(false);
  let isSavingFolder = $state(false);
  let folderSaveError = $state("");

  async function loadFolders() {
    try {
      folders = await rulesApi.folders("Arch", { organization_id: authState.activeOrganizationId });
    } catch {
      // Non-fatal -- the folder field still works as free text without suggestions.
    }
  }

  onMount(loadFolders);

  async function handleCreateFolder(payload: {
    ruleset_id: string;
    display_name: string;
    category: RulesetCategory;
    mechanism_scope: string;
    description: string;
  }) {
    await rulesApi.createFolder(payload);
    folderName = payload.ruleset_id;
    await loadFolders();
  }

  // Confirms/persists whatever was typed directly into the folder field
  // (rather than through the "New Folder" modal) -- an unrecognized name is
  // created as a real ruleset folder right away instead of only implicitly
  // appearing the first time a rule gets saved under it.
  async function handleSaveFolderChanges() {
    const trimmed = folderName.trim();
    if (!trimmed) {
      folderSaveError = "Enter a folder name first.";
      return;
    }
    folderName = trimmed;
    folderSaveError = "";

    if (folders.some((f) => f.ruleset_id === trimmed)) {
      successMessage = `Rules below will be saved to "${trimmed}".`;
      setTimeout(() => {
        if (successMessage.includes(trimmed)) successMessage = "";
      }, 4000);
      return;
    }

    isSavingFolder = true;
    try {
      await rulesApi.createFolder({
        ruleset_id: trimmed,
        display_name: trimmed,
        category: "Arch",
        mechanism_scope: "CODE",
        description: "",
      });
      await loadFolders();
      successMessage = `Created folder "${trimmed}" — rules below will be saved here.`;
      setTimeout(() => {
        if (successMessage.includes(trimmed)) successMessage = "";
      }, 4000);
    } catch (err: any) {
      folderSaveError = err?.message || "Failed to save folder.";
    } finally {
      isSavingFolder = false;
    }
  }

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

  // Only one "Add Rule" panel is open across the whole page at a time — the
  // target IFC class doubles as a unique key since every domain's targets
  // are distinct classes. Saving a rule no longer closes the panel: it stays
  // open with a fresh blank form (remounted via formKeyByTarget) so several
  // rules can be authored against the same element type back-to-back.
  let activeTarget: string | null = $state(null);
  let successMessage = $state("");
  let sessionRulesByTarget: Record<string, Rule[]> = $state({});
  let formKeyByTarget: Record<string, number> = $state({});

  function toggleAdd(target: ArchDomainTarget) {
    if (activeTarget === target.ifcClass) {
      activeTarget = null;
    } else {
      activeTarget = target.ifcClass;
      formKeyByTarget[target.ifcClass] = (formKeyByTarget[target.ifcClass] || 0) + 1;
    }
  }

  function handleSaved(target: ArchDomainTarget, rule: Rule) {
    sessionRulesByTarget[target.ifcClass] = [...(sessionRulesByTarget[target.ifcClass] || []), rule];
    successMessage = `Rule "${rule.rule_id}" saved for ${target.label} in "${folderName}".`;
    setTimeout(() => {
      if (successMessage.includes(rule.rule_id || "")) successMessage = "";
    }, 5000);
    // Keep the panel open with a fresh form, ready for another rule against
    // the same target — closing here is what forced a re-click of "Add Rule"
    // for every single rule before.
    formKeyByTarget[target.ifcClass] = (formKeyByTarget[target.ifcClass] || 0) + 1;
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
          class="inline-flex items-center gap-1.5 rounded-xl border border-border-default bg-surface-card/60 px-3.5 py-2 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
        >
          <ArrowLeft class="h-3.5 w-3.5" />
          <span>Back to Rules Catalog</span>
        </button>
      </div>
    {/snippet}
  </PageHeader>

  {#if successMessage}
    <div
      class="flex items-center gap-2.5 rounded-xl border border-success-border/60 bg-success-bg/40 p-4 text-xs text-success"
    >
      <CheckCircle2 class="h-4 w-4 shrink-0 text-success" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <div class="space-y-2.5 rounded-2xl border border-border-default bg-surface-card/40 p-4">
    <label
      for="rule-folder-name"
      class="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-fg-secondary"
    >
      <FolderOpen class="h-3.5 w-3.5 text-accent" />
      Save rules to folder
    </label>
    <div class="flex flex-wrap items-center gap-2">
      <input
        id="rule-folder-name"
        type="text"
        bind:value={folderName}
        placeholder="e.g. BUILDING-CODE-PART9 — type a new name to create a folder"
        class="w-full max-w-md rounded-xl border border-border-default bg-surface-canvas px-3 py-1.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
      />
      <button
        type="button"
        disabled={isSavingFolder}
        onclick={handleSaveFolderChanges}
        class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-3.5 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
      >
        <CheckCircle2 class="h-3.5 w-3.5" />
        <span>{isSavingFolder ? "Saving..." : "Save Changes"}</span>
      </button>
      <button
        type="button"
        onclick={() => (isFolderModalOpen = true)}
        class="inline-flex items-center gap-1.5 rounded-xl border border-border-default bg-surface-canvas px-3 py-1.5 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
      >
        <Plus class="h-3.5 w-3.5" />
        <span>New Folder</span>
      </button>
    </div>
    {#if folderSaveError}
      <p class="text-caption text-rose-400">{folderSaveError}</p>
    {/if}
    <p class="text-caption text-fg-muted">
      Every rule you add below is saved into this ruleset folder, ready to select later for a targeted
      compliance run. Pick an existing one, type a new name directly, or use "New Folder" to set it up
      with a display name and description first.
    </p>
    {#if folders.length}
      <div class="flex flex-wrap gap-1.5 pt-0.5">
        {#each folders as folder (folder.ruleset_id)}
          <button
            type="button"
            onclick={() => (folderName = folder.ruleset_id)}
            class="rounded-md border px-2 py-0.5 text-micro font-semibold transition-colors {folderName ===
            folder.ruleset_id
              ? 'border-accent bg-accent/15 text-accent'
              : 'border-border-default bg-surface-overlay text-fg-muted hover:text-fg-primary'}"
          >
            {folder.display_name || folder.ruleset_id}
          </button>
        {/each}
      </div>
    {/if}
  </div>

  <div class="space-y-3">
    {#each ARCH_DOMAINS as domain (domain.key)}
      {@const domIcon = DOMAIN_ICONS[domain.key] || Layers}

      {@const SvelteComponent = domIcon}
      <div class="space-y-3 rounded-2xl border border-border-default bg-surface-card/40 p-4">
        <div class="flex items-center gap-2.5">
          <SvelteComponent class="h-4 w-4 text-fg-secondary" />
          <h3 class="text-sm font-bold text-fg-primary">{domain.label}</h3>
          {#if domain.computed}
            <span
              class="rounded-md border border-border-interactive bg-surface-overlay px-2 py-0.5 text-micro font-semibold uppercase text-fg-muted"
            >
              Computed
            </span>
          {/if}
        </div>

        {#if domain.computed}
          <div
            class="flex items-start gap-2.5 rounded-xl border border-border-default bg-surface-canvas/40 p-3 text-xs text-fg-muted"
          >
            <Info class="mt-0.5 h-4 w-4 shrink-0 text-fg-muted" />
            <span>
              {domain.label} is computed automatically by the ARCH engine, not from editable rules — nothing
              to add here.
            </span>
          </div>
        {:else}
          <div class="space-y-2">
            {#each domain.targets as target (target)}
              <div class="overflow-hidden rounded-xl border border-border-default bg-surface-canvas/40">
                <div class="flex items-center justify-between p-3">
                  <div class="flex items-center gap-2">
                    <span class="text-xs font-bold text-fg-secondary">{target.label}</span>
                    <BsddBadge kind="class" value={target.ifcClass} class="font-mono text-micro text-fg-muted" />
                    {#if sessionRulesByTarget[target.ifcClass]?.length}
                      <span
                        class="rounded-md border border-success-border/50 bg-success-bg/30 px-1.5 py-0.5 text-micro font-semibold text-success"
                      >
                        {sessionRulesByTarget[target.ifcClass].length}
                        {sessionRulesByTarget[target.ifcClass].length === 1 ? "rule" : "rules"} added
                      </span>
                    {/if}
                  </div>
                  <button
                    type="button"
                    onclick={() => toggleAdd(target)}
                    class="inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-caption font-semibold transition-colors {activeTarget ===
                    target.ifcClass
                      ? 'border border-border-interactive bg-surface-overlay text-fg-secondary'
                      : 'border border-accent/30 bg-accent/15 text-accent hover:bg-accent/25'}"
                  >
                    {#if activeTarget === target.ifcClass}
                      {#if sessionRulesByTarget[target.ifcClass]?.length}
                        <CheckCircle2 class="h-3 w-3" />
                        <span>Done</span>
                      {:else}
                        <X class="h-3 w-3" />
                        <span>Cancel</span>
                      {/if}
                    {:else}
                      <Plus class="h-3 w-3" />
                      <span>Add Rule</span>
                    {/if}
                  </button>
                </div>

                {#if activeTarget === target.ifcClass}
                  <div class="space-y-2.5 p-3 pt-0">
                    {#if sessionRulesByTarget[target.ifcClass]?.length}
                      <div class="flex flex-wrap items-center gap-1.5">
                        {#each sessionRulesByTarget[target.ifcClass] as saved (saved.id)}
                          <span
                            class="inline-flex items-center gap-1 rounded-md border border-success-border/50 bg-success-bg/30 px-2 py-0.5 text-micro font-semibold text-success"
                          >
                            <CheckCircle2 class="h-3 w-3" />
                            {saved.rule_id}
                          </span>
                        {/each}
                      </div>
                    {/if}
                    <div class="rounded-xl border border-border-default bg-surface-card/60 p-3">
                      {#key formKeyByTarget[target.ifcClass]}
                        <RuleForm
                          compact
                          lockedTargetIfcClass={target.ifcClass}
                          propertySuggestions={target.properties}
                          defaultRulesetId={folderName}
                          onCancel={() => (activeTarget = null)}
                          onSaved={(rule) => handleSaved(target, rule)}
                        />
                      {/key}
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

<RulesetFolderModal
  isOpen={isFolderModalOpen}
  category="Arch"
  onClose={() => (isFolderModalOpen = false)}
  onSave={handleCreateFolder}
/>
