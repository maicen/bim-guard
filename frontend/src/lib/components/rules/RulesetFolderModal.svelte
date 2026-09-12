<script lang="ts">
  import { Folder, Pencil } from "lucide-svelte";
  import Modal from "../Modal.svelte";
  import Select, { type SelectOption } from "../ui/Select.svelte";
  import type { RulesetCategory } from "../../types";

  interface Props {
    isOpen: boolean;
    isEditing?: boolean;
    rulesetId?: string;
    displayName?: string;
    category?: RulesetCategory;
    mechanismScope?: string;
    description?: string;
    onClose: () => void;
    onSave: (payload: {
      ruleset_id: string;
      display_name: string;
      category: RulesetCategory;
      mechanism_scope: string;
      description: string;
    }) => Promise<void>;
  }

  let {
    isOpen = false,
    isEditing = false,
    rulesetId = "",
    displayName = "",
    category = "Arch",
    mechanismScope = "CODE",
    description = "",
    onClose,
    onSave,
  }: Props = $props();

  let formRulesetId = $state("");
  let formDisplayName = $state("");
  let formCategory: RulesetCategory = $state("Arch");
  let formMechanismScope = $state("CODE");
  let formDescription = $state("");
  let isSaving = $state(false);
  let errorMessage = $state("");

  $effect(() => {
    if (isOpen) {
      formRulesetId = rulesetId;
      formDisplayName = displayName;
      formCategory = category;
      formMechanismScope = mechanismScope;
      formDescription = description;
      errorMessage = "";
      isSaving = false;
    }
  });

  const categoryOptions: SelectOption[] = [
    { value: "Arch", label: "Arch (Architectural)" },
    { value: "Piping", label: "Piping (Corrosion)" },
    { value: "seismic", label: "Seismic (Clearance)" },
  ];

  const mechanismOptions: SelectOption[] = [
    { value: "CODE", label: "CODE (Building Code)" },
    { value: "GC-001", label: "GC-001 (Galvanic)" },
    { value: "CC-001", label: "CC-001 (Crevice)" },
    { value: "MC-001", label: "MC-001 (Microbiological)" },
    { value: "SEISMIC", label: "SEISMIC (Clearance Detection)" },
  ];

  async function handleSave() {
    if (!formRulesetId.trim()) {
      errorMessage = "Ruleset Identifier (ID) is required.";
      return;
    }
    isSaving = true;
    errorMessage = "";
    try {
      await onSave({
        ruleset_id: formRulesetId.trim(),
        display_name: formDisplayName.trim(),
        category: formCategory,
        mechanism_scope: formMechanismScope,
        description: formDescription.trim(),
      });
      onClose();
    } catch (err: any) {
      errorMessage = err?.message || "Failed to save ruleset folder.";
    } finally {
      isSaving = false;
    }
  }
</script>

<Modal
  {isOpen}
  title={isEditing ? `Edit Folder: ${rulesetId}` : "Create Ruleset Folder"}
  subtitle={isEditing
    ? "Update folder name, category, and scope"
    : "Organize compliance rules under a new domain ruleset"}
  icon={isEditing ? Pencil : Folder}
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
      <label for="folder-ruleset-id" class="block font-semibold text-fg-secondary">
        Ruleset Identifier (ID) <span class="text-rose-400">*</span>
      </label>
      <input
        id="folder-ruleset-id"
        type="text"
        bind:value={formRulesetId}
        disabled={isEditing}
        placeholder="e.g. BUILDING-CODE-PART3 or GC-001"
        class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 font-mono text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden disabled:cursor-not-allowed disabled:opacity-60"
      />
      {#if !isEditing}
        <p class="text-caption text-fg-muted">
          Unique ID used to link member rules (e.g. CODE-2024-STAIRS, GC-001, SEISMIC-CLEARANCE).
        </p>
      {/if}
    </div>

    <div class="space-y-1.5">
      <label for="folder-display-name" class="block font-semibold text-fg-secondary">
        Display Name
      </label>
      <input
        id="folder-display-name"
        type="text"
        bind:value={formDisplayName}
        placeholder="e.g. Building Code Part 3 - Fire Protection & Safety"
        class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
      />
    </div>

    <div class="grid grid-cols-2 gap-3">
      <div class="space-y-1.5">
        <label for="folder-category" class="block font-semibold text-fg-secondary">
          Domain Category
        </label>
        <Select
          options={categoryOptions}
          value={formCategory}
          onValueChange={(v) => (formCategory = v as RulesetCategory)}
          ariaLabel="Domain Category"
        />
      </div>

      <div class="space-y-1.5">
        <label for="folder-mechanism-scope" class="block font-semibold text-fg-secondary">
          Mechanism Scope
        </label>
        <Select
          options={mechanismOptions}
          value={formMechanismScope}
          onValueChange={(v) => (formMechanismScope = v)}
          ariaLabel="Mechanism Scope"
        />
      </div>
    </div>

    <div class="space-y-1.5">
      <label for="folder-desc" class="block font-semibold text-fg-secondary">Description</label>
      <textarea
        id="folder-desc"
        rows="3"
        bind:value={formDescription}
        placeholder="Regulatory standard, scope notes, or compliance criteria..."
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
      disabled={isSaving || !formRulesetId.trim()}
      onclick={handleSave}
      class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:opacity-50"
    >
      <span>{isSaving ? "Saving..." : isEditing ? "Update Folder" : "Create Folder"}</span>
    </button>
  {/snippet}
</Modal>
