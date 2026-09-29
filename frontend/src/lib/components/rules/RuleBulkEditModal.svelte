<script lang="ts">
  import { Pencil } from "lucide-svelte";
  import Modal from "../Modal.svelte";
  import Select, { type SelectOption } from "../ui/Select.svelte";
  import Alert from "../Alert.svelte";
  import { ARCH_CATEGORY_OPTIONS, ARCH_MECHANISM_OPTIONS } from "../../analysisDomain";
  import { rulesApi } from "../../api";
  import { checkCategoryFromOption, checkCategoryOptions } from "../../checkCategories";
  import type { RuleCheckCategory, RuleFolder } from "../../types";
  import { toErrorLogEntry, type ErrorLogEntry } from "../../utils/errorLog";

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
      check_category_id?: number;
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
  let checkCategory = $state("__keep__");
  let checkCategories = $state.raw<RuleCheckCategory[]>([]);
  let isUpdating = $state(false);
  let errorMessage = $state("");
  let errorLog: ErrorLogEntry[] = $state([]);

  $effect(() => {
    if (isOpen) {
      rulesetId = "__keep__";
      category = "__keep__";
      mechanism = "__keep__";
      severity = "__keep__";
      needsReview = "__keep__";
      checkCategory = "__keep__";
      errorMessage = "";
      errorLog = [];
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
    ...ARCH_CATEGORY_OPTIONS,
  ];

  let checkCategorySelectOptions: SelectOption[] = $derived([
    { value: "__keep__", label: "— Keep current —" },
    ...checkCategoryOptions(checkCategories),
  ]);

  async function loadCheckCategories() {
    try {
      checkCategories = await rulesApi.listCheckCategories();
    } catch (err: any) {
      errorMessage = `Could not load check categories: ${err?.message || err}`;
    }
  }

  $effect(() => {
    if (isOpen) loadCheckCategories();
  });

  const mechanismOptions: SelectOption[] = [
    { value: "__keep__", label: "— Keep current —" },
    ...ARCH_MECHANISM_OPTIONS,
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
    errorLog = [];
    try {
      const payload: {
        ruleset_id?: string;
        category?: string;
        mechanism?: string;
        severity?: string;
        needs_review?: number;
        check_category_id?: number;
      } = {};
      if (rulesetId !== "__keep__") payload.ruleset_id = rulesetId;
      if (category !== "__keep__") payload.category = category;
      if (mechanism !== "__keep__") payload.mechanism = mechanism;
      if (severity !== "__keep__") payload.severity = severity;
      if (needsReview !== "__keep__") payload.needs_review = parseInt(needsReview, 10);
      if (checkCategory !== "__keep__") payload.check_category_id = checkCategoryFromOption(checkCategory);

      await onUpdate(payload);
      onClose();
    } catch (err: any) {
      errorMessage = err?.message || "Failed to update selected rules.";
      errorLog = [toErrorLogEntry(err, `${selectedCount} rule(s)`)];
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
      <Alert
        type="error"
        message={errorMessage}
        errors={errorLog}
        logTitle="Rule Bulk Edit Error Log"
        logContext={{ "Rule count": selectedCount }}
      />
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

    <div class="space-y-1.5">
      <span class="block font-semibold text-fg-secondary">Check Category</span>
      <Select
        options={checkCategorySelectOptions}
        value={checkCategory}
        onValueChange={(v) => (checkCategory = v)}
        ariaLabel="Check Category"
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
