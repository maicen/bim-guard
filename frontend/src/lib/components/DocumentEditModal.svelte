<script lang="ts">
  import { Pencil } from "lucide-svelte";
  import Modal from "./Modal.svelte";
  import { Select } from "./ui";
  import { documentsApi } from "../api";
  import { DOCUMENT_TYPES } from "../types";
  import type { DocumentItem, DocumentType } from "../types";

  interface Props {
    isOpen: boolean;
    doc: DocumentItem | null;
    onClose: () => void;
    onSaved: (updated: DocumentItem) => void;
  }

  let {
    isOpen,
    doc,
    onClose,
    onSaved,
  }: Props = $props();

  let editFilename = $state("");
  let editDocType = $state<string>("Specification");
  let isSavingEdit = $state(false);
  let editError = $state("");

  $effect(() => {
    if (doc && isOpen) {
      editFilename = doc.filename;
      editDocType = doc.doc_type || "Specification";
      editError = "";
    }
  });

  const docTypeOptions = DOCUMENT_TYPES.map((type) => ({
    value: type,
    label: type,
  }));

  async function handleSaveEdit() {
    if (!doc) return;
    if (!editFilename.trim()) {
      editError = "Filename is required.";
      return;
    }
    isSavingEdit = true;
    editError = "";
    try {
      const updated = await documentsApi.update(doc.id, {
        filename: editFilename.trim(),
        doc_type: editDocType,
      });
      onSaved(updated);
      onClose();
    } catch (err: any) {
      editError = err.message || "Failed to update document.";
    } finally {
      isSavingEdit = false;
    }
  }
</script>

<Modal
  {isOpen}
  title={doc ? `Edit Document #${doc.id}` : "Edit Document"}
  subtitle="Update specification filename and document type"
  icon={Pencil}
  maxWidth="max-w-2xl"
  {onClose}
>
  <div class="space-y-4">
    {#if editError}
      <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300">
        {editError}
      </div>
    {/if}

    <div class="space-y-1.5">
      <label for="edit-doc-filename" class="block text-xs font-semibold text-fg-secondary">
        Filename <span class="text-rose-400">*</span>
      </label>
      <input
        id="edit-doc-filename"
        type="text"
        bind:value={editFilename}
        placeholder="e.g. BuildingCode_Part9_Specifications.pdf"
        class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
      />
    </div>

    <div class="space-y-1.5">
      <label for="edit-doc-type" class="block text-xs font-semibold text-fg-secondary">
        Document Type
      </label>
      <Select
        ariaLabel="Document Type"
        options={docTypeOptions}
        bind:value={editDocType}
        triggerClass="w-full bg-surface-canvas"
      />
    </div>
  </div>

  {#snippet footer()}
    <div class="flex items-center justify-end gap-2">
      <button
        type="button"
        onclick={onClose}
        class="rounded-xl px-4 py-2 text-xs font-semibold text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
      >
        Cancel
      </button>
      <button
        type="button"
        disabled={isSavingEdit || !editFilename.trim()}
        onclick={handleSaveEdit}
        class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:opacity-50"
      >
        <span>{isSavingEdit ? "Saving..." : "Save Changes"}</span>
      </button>
    </div>
  {/snippet}
</Modal>
