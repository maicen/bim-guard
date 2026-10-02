<script lang="ts">
  import { run } from "svelte/legacy";

  import { SlidersHorizontal } from "lucide-svelte";
  import { documentsApi } from "../api";
  import { DOCUMENT_TYPES } from "../types";
  import type { DocumentType } from "../types";
  import Modal from "./Modal.svelte";
  import Alert from "./Alert.svelte";
  import Select from "./ui/Select.svelte";
  import { toErrorLogEntry, type ErrorLogEntry } from "../utils/errorLog";

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
  let errorLog: ErrorLogEntry[] = $state([]);

  run(() => {
    if (isOpen) {
      docType = "no_change";
      errorMessage = "";
      errorLog = [];
    }
  });

  let hasChanges = $derived(docType !== "no_change");

  async function handleSave() {
    if (!selectedDocIds.length || !hasChanges) return;

    isSaving = true;
    errorMessage = "";
    errorLog = [];

    const failures: ErrorLogEntry[] = [];
    let updated = 0;
    for (const id of selectedDocIds) {
      try {
        await documentsApi.update(id, {
          doc_type: docType as DocumentType,
        });
        updated += 1;
      } catch (err: any) {
        failures.push(toErrorLogEntry(err, `document #${id}`));
      }
    }
    isSaving = false;

    if (failures.length === 0) {
      onBulkUpdated();
      onClose();
      return;
    }
    errorLog = failures;
    errorMessage =
      updated > 0
        ? `Updated ${updated} of ${selectedDocIds.length} documents -- ${failures.length} failed: ${failures[0].message}`
        : failures[0].message || "Failed to apply bulk update to documents.";
    if (updated > 0) onBulkUpdated();
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
    <Alert
      type="error"
      message={errorMessage}
      errors={errorLog}
      logTitle="Document Bulk Edit Error Log"
      logContext={{ "Document count": selectedDocIds.length }}
    />
  {/if}

  <div
    class="rounded-xl border border-border-subtle bg-surface-canvas p-3.5 text-xs leading-relaxed text-fg-muted"
  >
    Select properties to update across all <strong class="text-fg-primary"
      >{selectedDocIds.length}</strong
    > selected documents.
  </div>

  <!-- Document Type -->
  <div class="space-y-1.5">
    <label for="bulk-doc-type" class="block text-xs font-semibold text-fg-secondary">
      Document Specification Type
    </label>
    <Select
 bind:value={docType}
 options={[{ value: "no_change", label: "-- Keep Current Type --" }, ...DOCUMENT_TYPES.map((t) => ({ value: t, label: t }))]}
 ariaLabel="Document type"
 />
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
      <span>{isSaving ? "Applying Changes..." : `Update ${selectedDocIds.length} Documents`}</span>
    </button>
  {/snippet}
</Modal>
