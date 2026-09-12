<script lang="ts">
  import { ListChecks, Save } from "lucide-svelte";
  import Modal from "./Modal.svelte";
  import { projectsApi } from "../api";
  import { toasts } from "../toast.svelte";
  import { SvelteSet } from "svelte/reactivity";
  import type { Project } from "../types";

  interface Props {
    project: Project | null;
    onClose: () => void;
  }

  let { project, onClose }: Props = $props();

  // "Zero bindings unless assigned": a brand-new project starts with none of
  // these checked, and nothing runs against a ruleset until this list says
  // so (see ArchAnalysisService.run_analysis's gate). `available` is this
  // project's organization's own grant from the superadmin's ruleset-access
  // screen -- a project can only bind a subset of it.
  let available = $state.raw<string[]>([]);
  const selected: Set<string> = new SvelteSet();
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);

  $effect(() => {
    if (project) load(project.id);
  });

  async function load(projectId: number) {
    loading = true;
    error = null;
    try {
      const res = await projectsApi.getRulesetBindings(projectId);
      available = res.available_ruleset_ids;
      selected.clear();
      for (const id of res.ruleset_ids) selected.add(id);
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  function toggle(rulesetId: string) {
    if (selected.has(rulesetId)) selected.delete(rulesetId);
    else selected.add(rulesetId);
  }

  async function save() {
    if (!project) return;
    saving = true;
    try {
      await projectsApi.setRulesetBindings(project.id, Array.from(selected));
      toasts.success("Rule assignments updated.");
      onClose();
    } catch (err) {
      toasts.fromError(err, "Could not save rule assignments.");
    } finally {
      saving = false;
    }
  }
</script>

<Modal
  isOpen={project !== null}
  title="Rule Assignments"
  subtitle={project?.name}
  icon={ListChecks}
  {onClose}
>
  {#if loading}
    <p class="text-xs text-fg-muted">Loading…</p>
  {:else if error}
    <p class="text-xs text-critical">{error}</p>
  {:else if available.length === 0}
    <p class="text-xs text-fg-muted">
      This project's organization hasn't been granted any custom rulesets yet — ask the platform
      superadmin to grant one under Ruleset Access. Built-in code rules still apply regardless.
    </p>
  {:else}
    <p class="mb-3 text-xs text-fg-muted">
      Only rulesets checked here run against this project's analysis. Built-in code rules always
      apply; this controls the custom rulesets your organization has been granted.
    </p>
    <div class="max-h-80 space-y-1 overflow-y-auto">
      {#each available as rulesetId (rulesetId)}
        <label
          class="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-xs text-fg-secondary transition-colors hover:bg-surface-hover"
        >
          <input
            type="checkbox"
            checked={selected.has(rulesetId)}
            onchange={() => toggle(rulesetId)}
            class="h-3.5 w-3.5 rounded border-border-default bg-surface-canvas text-accent focus:ring-1 focus:ring-accent"
          />
          {rulesetId}
        </label>
      {/each}
    </div>
  {/if}

  <div class="flex justify-end gap-2 pt-4">
    <button
      type="button"
      onclick={onClose}
      class="h-9 rounded-xl border border-border-interactive bg-surface-overlay px-4 text-xs font-semibold text-fg-secondary hover:bg-surface-hover"
    >
      Cancel
    </button>
    {#if available.length > 0}
      <button
        type="button"
        disabled={saving}
        onclick={save}
        class="inline-flex h-9 items-center gap-1.5 rounded-xl bg-accent px-4 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
      >
        <Save class="h-3.5 w-3.5" />
        {saving ? "Saving…" : "Save assignments"}
      </button>
    {/if}
  </div>
</Modal>
