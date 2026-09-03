<script lang="ts">
  import { run } from "svelte/legacy";

  import { SlidersHorizontal, AlertTriangle } from "lucide-svelte";
  import { documentsApi } from "../api";
  import { DOCUMENT_TYPES } from "../types";
  import type { DocumentType } from "../types";
  import Modal from "./Modal.svelte";

  interface Props {
    isOpen?: boolean;
    selectedDocIds?: number[];
    onClose: () => void;
    onBulkUpdated: () => void;
  }

  let { isOpen = false, selectedDocIds = [], onClose, onBulkUpdated }: Props = $props();

  let docType: string = $state("no_change");
  let isSaving: boolean = $state(false);
  let errorMessage: string = $state("");

  run(() => {
    if (isOpen) {
      docType = "no_change";
      errorMessage = "";
    }
  });

  let hasChanges = $derived(docType !== "no_change");

  async function handleSave() {
    if (!selectedDocIds.length || !hasChanges) return;

    isSaving = true;
    errorMessage = "";

    try {
      for (const id of selectedDocIds) {
        await documentsApi.update(id, {
          doc_type: docType as DocumentType,
        });
      }
      onBulkUpdated();
      onClose();
    } catch (err: any) {
      errorMessage = err.message || "Failed to apply bulk update to documents.";
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
    Select properties to update across all <strong class="text-slate-50"
      >{selectedDocIds.length}</strong
    > selected documents.
  </div>

  <!-- Document Type -->
  <div class="space-y-1.5">
    <label for="bulk-doc-type" class="block text-xs font-semibold text-slate-300">
      Document Specification Type
    </label>
    <select
      id="bulk-doc-type"
      bind:value={docType}
      class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
    >
      <option value="no_change">-- Keep Current Type --</option>
      {#each DOCUMENT_TYPES as type (type)}
        <option value={type}>{type}</option>
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
      <span>{isSaving ? "Applying Changes..." : `Update ${selectedDocIds.length} Documents`}</span>
    </button>
  {/snippet}
</Modal>
