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
      class="flex items-center gap-2 rounded-xl border border-critical-border bg-critical-bg p-3 text-xs text-critical"
    >
      <AlertTriangle class="h-4 w-4 shrink-0 text-critical" />
      <span>{errorMessage}</span>
    </div>
  {/if}

  <div
    class="rounded-xl border border-border-subtle bg-surface-canvas p-3.5 text-xs leading-relaxed text-fg-muted"
  >
    Fields set to <strong class="text-fg-primary">"Keep Current..."</strong> will remain unchanged on all
    selected topics.
  </div>

  <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
    <!-- Status -->
    <div class="space-y-1.5">
      <label for="bulk-bcf-status" class="block text-xs font-semibold text-fg-secondary">
        Topic Status
      </label>
      <select
        id="bulk-bcf-status"
        bind:value={topicStatus}
        class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 text-xs text-fg-primary focus:border-accent focus:ring-accent focus:outline-hidden"
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
      <label for="bulk-bcf-priority" class="block text-xs font-semibold text-fg-secondary">
        Priority
      </label>
      <select
        id="bulk-bcf-priority"
        bind:value={priority}
        class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 text-xs text-fg-primary focus:border-accent focus:ring-accent focus:outline-hidden"
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
    <label for="bulk-bcf-cde" class="block text-xs font-semibold text-fg-secondary">
      ISO 19650 CDE State
    </label>
    <select
      id="bulk-bcf-cde"
      bind:value={cdeState}
      class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 text-xs text-fg-primary focus:border-accent focus:ring-accent focus:outline-hidden"
    >
      <option value="no_change">-- Keep Current CDE State --</option>
      {#each CDE_STATE_CHOICES as state (state)}
        <option value={state}>{state}</option>
      {/each}
    </select>
  </div>

  {#snippet footer()}
    <button
      type="button"
      onclick={onClose}
      class="rounded-xl px-4 py-2 text-xs font-semibold text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
    >
      Cancel
    </button>
    <button
      type="button"
      disabled={isSaving || !hasChanges}
      onclick={handleSave}
      class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-xs transition-all hover:bg-accent-hover disabled:opacity-50"
    >
      <span>{isSaving ? "Applying Changes..." : `Update ${selectedTopicGuids.length} Topics`}</span>
    </button>
  {/snippet}
</Modal>
