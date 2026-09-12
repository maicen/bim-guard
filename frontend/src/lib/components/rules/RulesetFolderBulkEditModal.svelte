<script lang="ts">
  import { Pencil } from "lucide-svelte";
  import Modal from "../Modal.svelte";
  import Select, { type SelectOption } from "../ui/Select.svelte";

  interface Props {
    isOpen: boolean;
    selectedCount: number;
    onClose: () => void;
    onUpdate: (payload: {
      category?: string;
      mechanism_scope?: string;
    }) => Promise<void>;
  }

  let {
    isOpen = false,
    selectedCount = 0,
    onClose,
    onUpdate,
  }: Props = $props();

  let category = $state("__keep__");
  let mechanismScope = $state("__keep__");
  let isUpdating = $state(false);
  let errorMessage = $state("");

  $effect(() => {
    if (isOpen) {
      category = "__keep__";
      mechanismScope = "__keep__";
      errorMessage = "";
      isUpdating = false;
    }
  });

  const categoryOptions: SelectOption[] = [
    { value: "__keep__", label: "— Keep current —" },
    { value: "Arch", label: "Arch (Architectural)" },
    { value: "Piping", label: "Piping (Corrosion)" },
    { value: "seismic", label: "Seismic (Clearance)" },
  ];

  const mechanismOptions: SelectOption[] = [
    { value: "__keep__", label: "— Keep current —" },
    { value: "CODE", label: "CODE (Building Code)" },
    { value: "GC-001", label: "GC-001 (Galvanic)" },
    { value: "CC-001", label: "CC-001 (Crevice)" },
    { value: "MC-001", label: "MC-001 (Microbiological)" },
    { value: "SEISMIC", label: "SEISMIC (Clearance Detection)" },
  ];

  async function handleUpdate() {
    isUpdating = true;
    errorMessage = "";
    try {
      const payload: { category?: string; mechanism_scope?: string } = {};
      if (category !== "__keep__") payload.category = category;
      if (mechanismScope !== "__keep__") payload.mechanism_scope = mechanismScope;

      await onUpdate(payload);
      onClose();
    } catch (err: any) {
      errorMessage = err?.message || "Failed to update selected folders.";
    } finally {
      isUpdating = false;
    }
  }
</script>

<Modal
  {isOpen}
  title={`Bulk Edit ${selectedCount} Folders`}
  subtitle="Apply batch changes to selected ruleset folders"
  icon={Pencil}
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
      <label for="bulk-folder-category" class="block font-semibold text-fg-secondary">
        Domain Category
      </label>
      <Select
        options={categoryOptions}
        value={category}
        onValueChange={(v) => (category = v)}
        ariaLabel="Domain Category"
      />
    </div>

    <div class="space-y-1.5">
      <label for="bulk-folder-mechanism-scope" class="block font-semibold text-fg-secondary">
        Mechanism Scope
      </label>
      <Select
        options={mechanismOptions}
        value={mechanismScope}
        onValueChange={(v) => (mechanismScope = v)}
        ariaLabel="Mechanism Scope"
      />
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
      disabled={isUpdating}
      onclick={handleUpdate}
      class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:opacity-50"
    >
      <span>{isUpdating ? "Updating..." : `Update ${selectedCount} Folders`}</span>
    </button>
  {/snippet}
</Modal>
