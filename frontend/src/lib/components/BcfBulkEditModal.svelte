<script lang="ts">
  import { SlidersHorizontal, AlertTriangle } from 'lucide-svelte';
  import { bcfApi } from '../api';
  import { CDE_STATE_CHOICES } from '../types';
  import Modal from './Modal.svelte';

  export let isOpen: boolean = false;
  export let projectId: number | string;
  export let selectedTopicGuids: string[] = [];
  export let onClose: () => void;
  export let onBulkUpdated: () => void;

  let topicStatus = 'no_change';
  let priority = 'no_change';
  let cdeState = 'no_change';
  let isSaving = false;
  let errorMessage = '';

  $: if (isOpen) {
    topicStatus = 'no_change';
    priority = 'no_change';
    cdeState = 'no_change';
    errorMessage = '';
  }

  $: hasChanges = topicStatus !== 'no_change' || priority !== 'no_change' || cdeState !== 'no_change';

  async function handleSave() {
    if (!selectedTopicGuids.length || !hasChanges) return;

    isSaving = true;
    errorMessage = '';

    try {
      for (const guid of selectedTopicGuids) {
        await bcfApi.updateTopic(projectId, guid, {
          topic_status: topicStatus !== 'no_change' ? topicStatus : undefined,
          priority: priority !== 'no_change' ? priority : undefined,
          cde_state: cdeState !== 'no_change' ? (cdeState as any) : undefined,
        });
      }
      onBulkUpdated();
      onClose();
    } catch (err: any) {
      errorMessage = err.message || 'Failed to apply bulk update to BCF topics.';
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
    <div class="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs flex items-center gap-2">
      <AlertTriangle class="w-4 h-4 shrink-0 text-rose-400" />
      <span>{errorMessage}</span>
    </div>
  {/if}

  <div class="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 text-xs text-slate-400 leading-relaxed">
    Fields set to <strong class="text-slate-200">"Keep Current..."</strong> will remain unchanged on all selected topics.
  </div>

  <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
    <!-- Status -->
    <div class="space-y-1.5">
      <label for="bulk-bcf-status" class="block text-xs font-semibold text-slate-300">
        Topic Status
      </label>
      <select
        id="bulk-bcf-status"
        bind:value={topicStatus}
        class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-50 focus:outline-none focus:border-accent"
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
        class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-50 focus:outline-none focus:border-accent"
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
      class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-50 focus:outline-none focus:border-accent"
    >
      <option value="no_change">-- Keep Current CDE State --</option>
      {#each CDE_STATE_CHOICES as state}
        <option value={state}>{state}</option>
      {/each}
    </select>
  </div>

  <div slot="footer">
    <button
      type="button"
      on:click={onClose}
      class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-slate-50 hover:bg-slate-800 transition-colors"
    >
      Cancel
    </button>
    <button
      type="button"
      disabled={isSaving || !hasChanges}
      on:click={handleSave}
      class="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-semibold bg-accent hover:bg-accent-hover text-white shadow-sm shadow-blue-500/20 transition-all disabled:opacity-50"
    >
      <span>{isSaving ? 'Applying Changes...' : `Update ${selectedTopicGuids.length} Topics`}</span>
    </button>
  </div>
</Modal>
