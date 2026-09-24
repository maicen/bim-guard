<script lang="ts">
  import { run } from "svelte/legacy";

  import { X, Check, SlidersHorizontal } from "lucide-svelte";
  import { projectsApi } from "../api";
  import { PROJECT_TYPES } from "../types";
  import Alert from "./Alert.svelte";
  import { toErrorLogEntry, type ErrorLogEntry } from "../utils/errorLog";

  interface Props {
    isOpen?: boolean;
    selectedProjectIds?: number[];
    onClose: () => void;
    onBulkUpdated: () => void;
  }

  let { isOpen = false, selectedProjectIds = [], onClose, onBulkUpdated }: Props = $props();

  let status: string = $state("no_change");
  let country: string = $state("no_change");
  let analysisType: string = $state("no_change");
  let projectType: string = $state("no_change");
  let isSaving: boolean = $state(false);
  let errorMessage: string = $state("");
  let errorLog: ErrorLogEntry[] = $state([]);

  run(() => {
    if (isOpen) {
      status = "no_change";
      country = "no_change";
      analysisType = "no_change";
      projectType = "no_change";
      errorMessage = "";
      errorLog = [];
    }
  });

  let hasChanges = $derived(
    status !== "no_change" ||
      country !== "no_change" ||
      analysisType !== "no_change" ||
      projectType !== "no_change",
  );

  async function handleSave() {
    if (!selectedProjectIds.length || !hasChanges) return;

    isSaving = true;
    errorMessage = "";
    errorLog = [];

    try {
      await projectsApi.bulkUpdate({
        project_ids: selectedProjectIds,
        status: status !== "no_change" ? status : undefined,
        country: country !== "no_change" ? country : undefined,
        analysis_type: analysisType !== "no_change" ? analysisType : undefined,
        project_type: projectType !== "no_change" ? projectType : undefined,
      });
      onBulkUpdated();
      onClose();
    } catch (err: any) {
      errorMessage = err.message || "Failed to apply bulk update.";
      errorLog = [toErrorLogEntry(err, `${selectedProjectIds.length} project(s)`)];
    } finally {
      isSaving = false;
    }
  }
</script>

{#if isOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-border-default bg-surface-card shadow-2xl"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-border-default px-6 py-4">
        <div class="flex items-center gap-2.5">
          <div class="rounded-xl border border-blue-500/20 bg-blue-500/10 p-2 text-blue-400">
            <SlidersHorizontal class="h-5 w-5" />
          </div>
          <div>
            <h2 class="text-base font-bold tracking-tight text-fg-primary">
              Bulk Edit ({selectedProjectIds.length} Projects)
            </h2>
            <p class="text-xs text-fg-muted">
              Update status, domain, or jurisdiction for all selected projects.
            </p>
          </div>
        </div>
        <button
          type="button"
          onclick={onClose}
          class="rounded-lg p-1 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <!-- Body Form -->
      <div class="space-y-4 overflow-y-auto p-6">
        {#if errorMessage}
          <Alert
            type="error"
            message={errorMessage}
            errors={errorLog}
            logTitle="Project Bulk Edit Error Log"
            logContext={{ "Project IDs": selectedProjectIds.join(", ") }}
          />
        {/if}

        <div
          class="rounded-xl border border-border-default bg-surface-canvas p-3.5 text-xs leading-relaxed text-fg-muted"
        >
          Fields set to <strong class="text-fg-secondary">"Keep Current..."</strong> will remain unchanged
          on all selected projects.
        </div>

        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <!-- Status -->
          <div class="space-y-1.5">
            <label for="bulk-proj-status" class="block text-xs font-semibold text-fg-secondary">
              Status
            </label>
            <select
              id="bulk-proj-status"
              bind:value={status}
              class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
            >
              <option value="no_change">-- Keep Current Status --</option>
              <option value="Active">Active</option>
              <option value="Draft">Draft</option>
              <option value="Archived">Archived</option>
            </select>
          </div>

          <!-- Jurisdiction -->
          <div class="space-y-1.5">
            <label for="bulk-proj-country" class="block text-xs font-semibold text-fg-secondary">
              Jurisdiction
            </label>
            <select
              id="bulk-proj-country"
              bind:value={country}
              class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
            >
              <option value="no_change">-- Keep Current Jurisdiction --</option>
              <option value="Canada">Canada (NBC)</option>
              <option value="US">United States (IBC)</option>
              <option value="UK">United Kingdom</option>
              <option value="EU">European Union</option>
            </select>
          </div>
        </div>

        <!-- Analysis Domain -->
        <div class="space-y-1.5">
          <label for="bulk-proj-domain" class="block text-xs font-semibold text-fg-secondary">
            Analysis Domain
          </label>
          <select
            id="bulk-proj-domain"
            bind:value={analysisType}
            class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
          >
            <option value="no_change">-- Keep Current Domain --</option>
            <option value="Arch">Arch</option>
          </select>
        </div>

        <!-- Project Type -->
        <div class="space-y-1.5">
          <label for="bulk-proj-type" class="block text-xs font-semibold text-fg-secondary">
            Project Type
          </label>
          <select
            id="bulk-proj-type"
            bind:value={projectType}
            class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
          >
            <option value="no_change">-- Keep Current Project Type --</option>
            {#each PROJECT_TYPES as type (type)}
              <option value={type}>{type}</option>
            {/each}
          </select>
        </div>
      </div>

      <!-- Footer Actions -->
      <div
        class="flex items-center justify-end gap-2 border-t border-border-default bg-surface-canvas/60 px-6 py-3"
      >
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
          class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover disabled:opacity-50 disabled:hover:scale-100"
        >
          <Check class="h-3.5 w-3.5" />
          <span>{isSaving ? "Applying Changes..." : "Apply Bulk Update"}</span>
        </button>
      </div>
    </div>
  </div>
{/if}
