<script lang="ts">
  import { Pencil } from "lucide-svelte";
  import Modal from "../Modal.svelte";
  import Select, { type SelectOption } from "../ui/Select.svelte";
  import type { RuleFolder } from "../../types";

  interface Props {
    isOpen: boolean;
    selectedCount: number;
    folders: RuleFolder[];
    onClose: () => void;
    onUpdate: (payload: {
      ruleset_id?: string;
      category?: string;
      mechanism?: string;
      severity?: string;
      needs_review?: number;
    }) => Promise<void>;
  }

  let {
    isOpen = false,
    selectedCount = 0,
    folders = [],
    onClose,
    onUpdate,
  }: Props = $props();

  let rulesetId = $state("__keep__");
  let category = $state("__keep__");
  let mechanism = $state("__keep__");
  let severity = $state("__keep__");
  let needsReview = $state("__keep__");
  let isUpdating = $state(false);
  let errorMessage = $state("");

  $effect(() => {
    if (isOpen) {
      rulesetId = "__keep__";
      category = "__keep__";
      mechanism = "__keep__";
      severity = "__keep__";
      needsReview = "__keep__";
      errorMessage = "";
      isUpdating = false;
    }
  });

  let folderOptions: SelectOption[] = $derived([
    { value: "__keep__", label: "— Keep current folder —" },
    ...folders.map((f) => ({
      value: f.ruleset_id,
      label: `${f.display_name} (${f.ruleset_id})`,
    })),
  ]);

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
    { value: "SEISMIC", label: "SEISMIC (Clearance)" },
  ];

  const severityOptions: SelectOption[] = [
    { value: "__keep__", label: "— Keep current —" },
    { value: "Critical", label: "Critical" },
    { value: "High", label: "High" },
    { value: "Medium", label: "Medium" },
    { value: "Low", label: "Low" },
  ];

  const reviewOptions: SelectOption[] = [
    { value: "__keep__", label: "— Keep current —" },
    { value: "0", label: "Mark as Approved (0)" },
    { value: "1", label: "Mark as Needs Review (1)" },
  ];

  async function handleUpdate() {
    isUpdating = true;
    errorMessage = "";
    try {
      const payload: {
        ruleset_id?: string;
        category?: string;
        mechanism?: string;
        severity?: string;
        needs_review?: number;
      } = {};
      if (rulesetId !== "__keep__") payload.ruleset_id = rulesetId;
      if (category !== "__keep__") payload.category = category;
      if (mechanism !== "__keep__") payload.mechanism = mechanism;
      if (severity !== "__keep__") payload.severity = severity;
      if (needsReview !== "__keep__") payload.needs_review = parseInt(needsReview, 10);

      await onUpdate(payload);
      onClose();
    } catch (err: any) {
      errorMessage = err?.message || "Failed to update selected rules.";
    } finally {
      isUpdating = false;
    }
  }
</script>

<Modal
  {isOpen}
  title={`Bulk Edit ${selectedCount} Rules`}
  subtitle="Apply batch changes to selected compliance rules"
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
      <label for="bulk-rule-ruleset" class="block font-semibold text-fg-secondary">
        Move to Ruleset Folder
      </label>
      <Select
        options={folderOptions}
        value={rulesetId}
        onValueChange={(v) => (rulesetId = v)}
        ariaLabel="Move to Ruleset Folder"
      />
    </div>

    <div class="grid grid-cols-2 gap-3">
      <div class="space-y-1.5">
        <label for="bulk-rule-category" class="block font-semibold text-fg-secondary">
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
        <label for="bulk-rule-mechanism" class="block font-semibold text-fg-secondary">
          Mechanism
        </label>
        <Select
          options={mechanismOptions}
          value={mechanism}
          onValueChange={(v) => (mechanism = v)}
          ariaLabel="Mechanism"
        />
      </div>
    </div>

    <div class="grid grid-cols-2 gap-3">
      <div class="space-y-1.5">
        <label for="bulk-rule-severity" class="block font-semibold text-fg-secondary">
          Severity
        </label>
        <Select
          options={severityOptions}
          value={severity}
          onValueChange={(v) => (severity = v)}
          ariaLabel="Severity"
        />
      </div>

      <div class="space-y-1.5">
        <label for="bulk-rule-review" class="block font-semibold text-fg-secondary">
          Review Status
        </label>
        <Select
          options={reviewOptions}
          value={needsReview}
          onValueChange={(v) => (needsReview = v)}
          ariaLabel="Review Status"
        />
      </div>
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
      <span>{isUpdating ? "Updating..." : `Update ${selectedCount} Rules`}</span>
    </button>
  {/snippet}
</Modal>
