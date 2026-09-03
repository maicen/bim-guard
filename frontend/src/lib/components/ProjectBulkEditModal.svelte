<script lang="ts">
  import { run } from "svelte/legacy";

  import { X, Check, SlidersHorizontal, AlertTriangle } from "lucide-svelte";
  import { projectsApi } from "../api";

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
  let isSaving: boolean = $state(false);
  let errorMessage: string = $state("");

  run(() => {
    if (isOpen) {
      status = "no_change";
      country = "no_change";
      analysisType = "no_change";
      errorMessage = "";
    }
  });

  let hasChanges = $derived(
    status !== "no_change" || country !== "no_change" || analysisType !== "no_change",
  );

  async function handleSave() {
    if (!selectedProjectIds.length || !hasChanges) return;

    isSaving = true;
    errorMessage = "";

    try {
      await projectsApi.bulkUpdate({
        project_ids: selectedProjectIds,
        status: status !== "no_change" ? status : undefined,
        country: country !== "no_change" ? country : undefined,
        analysis_type: analysisType !== "no_change" ? analysisType : undefined,
      });
      onBulkUpdated();
      onClose();
    } catch (err: any) {
      errorMessage = err.message || "Failed to apply bulk update.";
    } finally {
      isSaving = false;
    }
  }
</script>

{#if isOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div class="flex items-center gap-2.5">
          <div class="rounded-xl border border-blue-500/20 bg-blue-500/10 p-2 text-blue-400">
            <SlidersHorizontal class="h-5 w-5" />
          </div>
          <div>
            <h2 class="text-base font-bold tracking-tight text-slate-50">
              Bulk Edit ({selectedProjectIds.length} Projects)
            </h2>
            <p class="text-xs text-slate-400">
              Update status, domain, or jurisdiction for all selected projects.
            </p>
          </div>
        </div>
        <button
          type="button"
          onclick={onClose}
          class="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <!-- Body Form -->
      <div class="space-y-4 overflow-y-auto p-6">
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
          Fields set to <strong class="text-slate-200">"Keep Current..."</strong> will remain unchanged
          on all selected projects.
        </div>

        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <!-- Status -->
          <div class="space-y-1.5">
            <label for="bulk-proj-status" class="block text-xs font-semibold text-slate-300">
              Status
            </label>
            <select
              id="bulk-proj-status"
              bind:value={status}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              <option value="no_change">-- Keep Current Status --</option>
              <option value="Active">Active</option>
              <option value="Draft">Draft</option>
              <option value="Archived">Archived</option>
            </select>
          </div>

          <!-- Jurisdiction -->
          <div class="space-y-1.5">
            <label for="bulk-proj-country" class="block text-xs font-semibold text-slate-300">
              Jurisdiction
            </label>
            <select
              id="bulk-proj-country"
              bind:value={country}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
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
          <label for="bulk-proj-domain" class="block text-xs font-semibold text-slate-300">
            Analysis Domain
          </label>
          <select
            id="bulk-proj-domain"
            bind:value={analysisType}
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
          >
            <option value="no_change">-- Keep Current Domain --</option>
            <option value="Arch">Arch</option>
            <option value="Piping">Piping</option>
            <option value="seismic">seismic</option>
          </select>
        </div>
      </div>

      <!-- Footer Actions -->
      <div
        class="flex items-center justify-end gap-2 border-t border-slate-800 bg-slate-950/60 px-6 py-3"
      >
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
          class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover disabled:opacity-50 disabled:hover:scale-100"
        >
          <Check class="h-3.5 w-3.5" />
          <span>{isSaving ? "Applying Changes..." : "Apply Bulk Update"}</span>
        </button>
      </div>
    </div>
  </div>
{/if}
