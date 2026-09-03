<script lang="ts">
  import { run } from "svelte/legacy";

  import { SlidersHorizontal, AlertTriangle } from "lucide-svelte";
  import { bcfApi } from "../api";
  import { CDE_STATE_CHOICES } from "../types";
  import Modal from "./Modal.svelte";

  interface Props {
    isOpen?: boolean;
    projectId: number | string;
    selectedTopicGuids?: string[];
    onClose: () => void;
    onBulkUpdated: () => void;
  }

  let {
    isOpen = false,
    projectId,
    selectedTopicGuids = [],
    onClose,
    onBulkUpdated,
  }: Props = $props();

  let topicStatus = $state("no_change");
  let priority = $state("no_change");
  let cdeState = $state("no_change");
  let isSaving = $state(false);
  let errorMessage = $state("");

  run(() => {
    if (isOpen) {
      topicStatus = "no_change";
      priority = "no_change";
      cdeState = "no_change";
      errorMessage = "";
    }
  });

  let hasChanges = $derived(
    topicStatus !== "no_change" || priority !== "no_change" || cdeState !== "no_change",
  );

  async function handleSave() {
    if (!selectedTopicGuids.length || !hasChanges) return;

    isSaving = true;
    errorMessage = "";

    try {
      for (const guid of selectedTopicGuids) {
        await bcfApi.updateTopic(projectId, guid, {
          topic_status: topicStatus !== "no_change" ? topicStatus : undefined,
          priority: priority !== "no_change" ? priority : undefined,
          cde_state: cdeState !== "no_change" ? (cdeState as any) : undefined,
        });
      }
      onBulkUpdated();
      onClose();
    } catch (err: any) {
      errorMessage = err.message || "Failed to apply bulk update to BCF topics.";
    } finally {
      isSaving = false;
    }
  }
</script>

<Modal
  {isOpen}
  title={`Bulk Edit (${selectedTopicGuids.length} BCF Topics)`}
  subtitle="Update status, priority, and CDE state for all selected issues."
  icon={SlidersHorizontal}
  maxWidth="max-w-lg"
  {onClose}
>
  {#if errorMessage}
    <div
      class="flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300"
    >
      <AlertTriangle class="h-4 w-4 shrink-0 text-rose-400" />
      <span>{errorMessage}</span>
    </div>
  {/if}

  <div
    class="rounded-xl border border-slate-800/80 bg-slate-950 p-3.5 text-xs leading-relaxed text-slate-400"
  >
    Fields set to <strong class="text-slate-200">"Keep Current..."</strong> will remain unchanged on all
    selected topics.
  </div>

  <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
    <!-- Status -->
    <div class="space-y-1.5">
      <label for="bulk-bcf-status" class="block text-xs font-semibold text-slate-300">
        Topic Status
      </label>
      <select
        id="bulk-bcf-status"
        bind:value={topicStatus}
        class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
      >
        <option value="no_change">-- Keep Current Status --</option>
        <option value="Open">Open</option>
        <option value="In Progress">In Progress</option>
        <option value="Resolved">Resolved</option>
        <option value="Closed">Closed</option>
      </select>
    </div>

    <!-- Priority -->
    <div class="space-y-1.5">
      <label for="bulk-bcf-priority" class="block text-xs font-semibold text-slate-300">
        Priority
      </label>
      <select
        id="bulk-bcf-priority"
        bind:value={priority}
        class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
      >
        <option value="no_change">-- Keep Current Priority --</option>
        <option value="Critical">Critical</option>
        <option value="High">High</option>
        <option value="Normal">Normal</option>
        <option value="Low">Low</option>
      </select>
    </div>
  </div>

  <!-- CDE State -->
  <div class="space-y-1.5">
    <label for="bulk-bcf-cde" class="block text-xs font-semibold text-slate-300">
      ISO 19650 CDE State
    </label>
    <select
      id="bulk-bcf-cde"
      bind:value={cdeState}
      class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
    >
      <option value="no_change">-- Keep Current CDE State --</option>
      {#each CDE_STATE_CHOICES as state}
        <option value={state}>{state}</option>
      {/each}
    </select>
  </div>

  {#snippet footer()}
    <button
      type="button"
      onclick={onClose}
      class="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
    >
      Cancel
    </button>
    <button
      type="button"
      disabled={isSaving || !hasChanges}
      onclick={handleSave}
      class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:opacity-50"
    >
      <span>{isSaving ? "Applying Changes..." : `Update ${selectedTopicGuids.length} Topics`}</span>
    </button>
  {/snippet}
</Modal>
