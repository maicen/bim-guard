<script lang="ts">
  import { X, Check, SlidersHorizontal, AlertTriangle } from 'lucide-svelte';
  import { projectsApi } from '../api';

  export let isOpen: boolean = false;
  export let selectedProjectIds: number[] = [];
  export let onClose: () => void;
  export let onBulkUpdated: () => void;

  let status: string = 'no_change';
  let country: string = 'no_change';
  let analysisType: string = 'no_change';
  let isSaving: boolean = false;
  let errorMessage: string = '';

  $: if (isOpen) {
    status = 'no_change';
    country = 'no_change';
    analysisType = 'no_change';
    errorMessage = '';
  }

  $: hasChanges = status !== 'no_change' || country !== 'no_change' || analysisType !== 'no_change';

  async function handleSave() {
    if (!selectedProjectIds.length || !hasChanges) return;

    isSaving = true;
    errorMessage = '';

    try {
      await projectsApi.bulkUpdate({
        project_ids: selectedProjectIds,
        status: status !== 'no_change' ? status : undefined,
        country: country !== 'no_change' ? country : undefined,
        analysis_type: analysisType !== 'no_change' ? analysisType : undefined,
      });
      onBulkUpdated();
      onClose();
    } catch (err: any) {
      errorMessage = err.message || 'Failed to apply bulk update.';
    } finally {
      isSaving = false;
    }
  }
</script>

{#if isOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <SlidersHorizontal class="w-5 h-5" />
          </div>
          <div>
            <h2 class="text-base font-bold text-white tracking-tight">
              Bulk Edit ({selectedProjectIds.length} Projects)
            </h2>
            <p class="text-xs text-slate-400">
              Update status, domain, or jurisdiction for all selected projects.
            </p>
          </div>
        </div>
        <button
          type="button"
          on:click={onClose}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Body Form -->
      <div class="p-6 space-y-4 overflow-y-auto">
        {#if errorMessage}
          <div class="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs flex items-center gap-2">
            <AlertTriangle class="w-4 h-4 shrink-0 text-rose-400" />
            <span>{errorMessage}</span>
          </div>
        {/if}

        <div class="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 text-xs text-slate-400 leading-relaxed">
          Fields set to <strong class="text-slate-200">"Keep Current..."</strong> will remain unchanged on all selected projects.
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <!-- Status -->
          <div class="space-y-1.5">
            <label for="bulk-proj-status" class="block text-xs font-semibold text-slate-300">
              Status
            </label>
            <select
              id="bulk-proj-status"
              bind:value={status}
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
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
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
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
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
          >
            <option value="no_change">-- Keep Current Domain --</option>
            <option value="Arch">Arch</option>
            <option value="Piping">Piping</option>
            <option value="seismic">seismic</option>
          </select>
        </div>
      </div>

      <!-- Footer Actions -->
      <div class="px-6 py-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-end gap-2">
        <button
          type="button"
          on:click={onClose}
          class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isSaving || !hasChanges}
          on:click={handleSave}
          class="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] disabled:opacity-50 disabled:hover:scale-100"
        >
          <Check class="w-3.5 h-3.5" />
          <span>{isSaving ? 'Applying Changes...' : 'Apply Bulk Update'}</span>
        </button>
      </div>
    </div>
  </div>
{/if}
