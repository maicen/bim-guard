<script lang="ts">
  import { Camera } from "lucide-svelte";
  import Modal from "../Modal.svelte";
  import Select, { type SelectOption } from "../ui/Select.svelte";
  import type { RuleSnapshotSourceMode } from "../../types";

  interface Props {
    isOpen: boolean;
    folderId: string;
    onClose: () => void;
    onSave: (payload: {
      name: string;
      source_mode: RuleSnapshotSourceMode;
      notes: string;
    }) => Promise<void>;
  }

  let { isOpen = false, folderId, onClose, onSave }: Props = $props();

  let name = $state("");
  let sourceMode: RuleSnapshotSourceMode = $state("manual");
  let notes = $state("");
  let isSaving = $state(false);
  let errorMessage = $state("");

  $effect(() => {
    if (isOpen) {
      name = "";
      sourceMode = "manual";
      notes = "";
      errorMessage = "";
      isSaving = false;
    }
  });

  const sourceModeOptions: SelectOption[] = [
    { value: "manual", label: "Manual" },
    { value: "pdf", label: "PDF Extraction" },
    { value: "ids", label: "IDS Import" },
    { value: "mixed", label: "Mixed" },
  ];

  async function handleSave() {
    if (!name.trim()) {
      errorMessage = "Snapshot Name is required.";
      return;
    }
    isSaving = true;
    errorMessage = "";
    try {
      await onSave({
        name: name.trim(),
        source_mode: sourceMode,
        notes: notes.trim(),
      });
      onClose();
    } catch (err: any) {
      errorMessage = err?.message || "Failed to save rule snapshot.";
    } finally {
      isSaving = false;
    }
  }
</script>

<Modal
  {isOpen}
  title="Save Rule Snapshot"
  subtitle={`Freeze "${folderId}"'s current rules into a named, downloadable snapshot`}
  icon={Camera}
  maxWidth="max-w-lg"
  {onClose}
>
  <div class="space-y-4 text-xs">
    {#if errorMessage}
      <div class="rounded-xl border border-critical-border bg-critical-bg p-3 text-critical">
        {errorMessage}
      </div>
    {/if}

    <div class="space-y-1.5">
      <label for="snapshot-name" class="block font-semibold text-fg-secondary">
        Snapshot Name <span class="text-rose-400">*</span>
      </label>
      <input
        id="snapshot-name"
        type="text"
        bind:value={name}
        placeholder="e.g. 2026-Q1 Compliance Baseline"
        class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
      />
    </div>

    <div class="space-y-1.5">
      <label for="snapshot-mode" class="block font-semibold text-fg-secondary">Source Mode</label>
      <Select
        options={sourceModeOptions}
        value={sourceMode}
        onValueChange={(v) => (sourceMode = v as RuleSnapshotSourceMode)}
        ariaLabel="Source Mode"
      />
    </div>

    <div class="space-y-1.5">
      <label for="snapshot-notes" class="block font-semibold text-fg-secondary">Notes</label>
      <textarea
        id="snapshot-notes"
        rows="3"
        bind:value={notes}
        placeholder="Optional context for this configuration..."
        class="w-full resize-y rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
      ></textarea>
    </div>
  </div>

  {#snippet footer()}
    <button
      type="button"
      onclick={onClose}
      class="rounded-xl px-4 py-2 text-xs font-semibold text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
    >
      Cancel
    </button>
    <button
      type="button"
      disabled={isSaving || !name.trim()}
      onclick={handleSave}
      class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:opacity-50"
    >
      <span>{isSaving ? "Saving..." : "Save Snapshot"}</span>
    </button>
  {/snippet}
</Modal>
