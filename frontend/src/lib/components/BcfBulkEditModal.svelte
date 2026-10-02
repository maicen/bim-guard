<script lang="ts">
  import { run } from "svelte/legacy";

  import { SlidersHorizontal } from "lucide-svelte";
  import { bcfApi } from "../api";
  import { CDE_STATE_CHOICES } from "../types";
  import Modal from "./Modal.svelte";
  import Alert from "./Alert.svelte";
  import Select from "./ui/Select.svelte";
  import { toErrorLogEntry, type ErrorLogEntry } from "../utils/errorLog";

  interface Props {
    isOpen?: boolean;
    projectId: number | string;
    selectedTopicGuids?: string[];
    onClose: () => void;
    onBulkUpdated: () => void;
  }

  let {
    isOpen = false,
    projectId,
    selectedTopicGuids = [],
    onClose,
    onBulkUpdated,
  }: Props = $props();

  let topicStatus = $state("no_change");
  let priority = $state("no_change");
  let cdeState = $state("no_change");
  const STATUS_OPTIONS = [
    { value: "no_change", label: "-- Keep Current Status --" },
    ...["Open", "In Progress", "Resolved", "Closed"].map((v) => ({ value: v, label: v })),
  ];
  const PRIORITY_OPTIONS = [
    { value: "no_change", label: "-- Keep Current Priority --" },
    ...["Critical", "High", "Normal", "Low"].map((v) => ({ value: v, label: v })),
  ];
  const CDE_OPTIONS = [
    { value: "no_change", label: "-- Keep Current CDE State --" },
    ...CDE_STATE_CHOICES.map((v) => ({ value: v as string, label: v as string })),
  ];
  let isSaving = $state(false);
  let errorMessage = $state("");
  let errorLog: ErrorLogEntry[] = $state([]);

  run(() => {
    if (isOpen) {
      topicStatus = "no_change";
      priority = "no_change";
      cdeState = "no_change";
      errorMessage = "";
      errorLog = [];
    }
  });

  let hasChanges = $derived(
    topicStatus !== "no_change" || priority !== "no_change" || cdeState !== "no_change",
  );

  async function handleSave() {
    if (!selectedTopicGuids.length || !hasChanges) return;

    isSaving = true;
    errorMessage = "";
    errorLog = [];

    const failures: ErrorLogEntry[] = [];
    let updated = 0;
    for (const guid of selectedTopicGuids) {
      try {
        await bcfApi.updateTopic(projectId, guid, {
          topic_status: topicStatus !== "no_change" ? topicStatus : undefined,
          priority: priority !== "no_change" ? priority : undefined,
          cde_state: cdeState !== "no_change" ? (cdeState as any) : undefined,
        });
        updated += 1;
      } catch (err: any) {
        failures.push(toErrorLogEntry(err, `topic ${guid}`));
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
        ? `Updated ${updated} of ${selectedTopicGuids.length} topics -- ${failures.length} failed: ${failures[0].message}`
        : failures[0].message || "Failed to apply bulk update to BCF topics.";
    if (updated > 0) onBulkUpdated();
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
    <Alert
      type="error"
      message={errorMessage}
      errors={errorLog}
      logTitle="BCF Bulk Edit Error Log"
      logContext={{ "Topic count": selectedTopicGuids.length }}
    />
  {/if}

  <div
    class="rounded-xl border border-border-subtle bg-surface-canvas p-3.5 text-xs leading-relaxed text-fg-muted"
  >
    Fields set to <strong class="text-fg-primary">"Keep Current..."</strong> will remain unchanged on all
    selected topics.
  </div>

  <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
    <!-- Status -->
    <div class="space-y-1.5">
      <label for="bulk-bcf-status" class="block text-xs font-semibold text-fg-secondary">
        Topic Status
      </label>
      <Select
        bind:value={topicStatus}
        options={STATUS_OPTIONS}
        ariaLabel="Topic status"
      />
    </div>

    <!-- Priority -->
    <div class="space-y-1.5">
      <label for="bulk-bcf-priority" class="block text-xs font-semibold text-fg-secondary">
        Priority
      </label>
      <Select
        bind:value={priority}
        options={PRIORITY_OPTIONS}
        ariaLabel="Priority"
      />
    </div>
  </div>

  <!-- CDE State -->
  <div class="space-y-1.5">
    <label for="bulk-bcf-cde" class="block text-xs font-semibold text-fg-secondary">
      ISO 19650 CDE State
    </label>
    <Select
        bind:value={cdeState}
        options={CDE_OPTIONS}
        ariaLabel="ISO 19650 CDE state"
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
      <span>{isSaving ? "Applying Changes..." : `Update ${selectedTopicGuids.length} Topics`}</span>
    </button>
  {/snippet}
</Modal>
