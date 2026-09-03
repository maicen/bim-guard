<script lang="ts">
  import { SlidersHorizontal, AlertTriangle } from 'lucide-svelte';
  import { documentsApi } from '../api';
  import { DOCUMENT_TYPES } from '../types';
  import type { DocumentType } from '../types';
  import Modal from './Modal.svelte';

  export let isOpen: boolean = false;
  export let selectedDocIds: number[] = [];
  export let onClose: () => void;
  export let onBulkUpdated: () => void;

  let docType: string = 'no_change';
  let isSaving: boolean = false;
  let errorMessage: string = '';

  $: if (isOpen) {
    docType = 'no_change';
    errorMessage = '';
  }

  $: hasChanges = docType !== 'no_change';

  async function handleSave() {
    if (!selectedDocIds.length || !hasChanges) return;

    isSaving = true;
    errorMessage = '';

    try {
      for (const id of selectedDocIds) {
        await documentsApi.update(id, {
          doc_type: docType as DocumentType,
        });
      }
      onBulkUpdated();
      onClose();
    } catch (err: any) {
      errorMessage = err.message || 'Failed to apply bulk update to documents.';
    } finally {
      isSaving = false;
    }
  }
</script>

<Modal
  {isOpen}
  title={`Bulk Edit (${selectedDocIds.length} Documents)`}
  subtitle="Batch update document classification and specification properties."
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
    Select properties to update across all <strong class="text-slate-50">{selectedDocIds.length}</strong> selected documents.
  </div>

  <!-- Document Type -->
  <div class="space-y-1.5">
    <label for="bulk-doc-type" class="block text-xs font-semibold text-slate-300">
      Document Specification Type
    </label>
    <select
      id="bulk-doc-type"
      bind:value={docType}
      class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-50 focus:outline-none focus:border-accent"
    >
      <option value="no_change">-- Keep Current Type --</option>
      {#each DOCUMENT_TYPES as type}
        <option value={type}>{type}</option>
      {/each}
    </select>
  </div>

  {#snippet footer()}
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
      <span>{isSaving ? 'Applying Changes...' : `Update ${selectedDocIds.length} Documents`}</span>
    </button>
  {/snippet}
</Modal>
