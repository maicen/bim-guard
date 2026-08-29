<script lang="ts">
  import { X, Check, Pencil, AlertTriangle } from 'lucide-svelte';
  import { projectsApi } from '../api';
  import type { Project } from '../types';

  export let isOpen: boolean = false;
  export let project: Project | null = null;
  export let onClose: () => void;
  export let onProjectUpdated: (updated: Project) => void;

  let name = '';
  let description = '';
  let status = 'Active';
  let country = 'Canada';
  let analysisType = 'Architecture';
  let isSaving = false;
  let errorMessage = '';

  $: if (isOpen && project) {
    name = project.name || '';
    description = project.description || '';
    status = project.status || 'Active';
    country = project.country || 'Canada';
    analysisType = project.analysis_type || 'Architecture';
    errorMessage = '';
  }

  async function handleSave() {
    if (!project) return;
    if (!name.trim()) {
      errorMessage = 'Project name is required.';
      return;
    }

    isSaving = true;
    errorMessage = '';
    try {
      const updated = await projectsApi.update(project.id, {
        name: name.trim(),
        description: description.trim(),
        status,
        country,
        analysis_type: analysisType,
      });
      onProjectUpdated(updated);
      onClose();
    } catch (err: any) {
      errorMessage = err.message || 'Failed to update project.';
    } finally {
      isSaving = false;
    }
  }
</script>

{#if isOpen && project}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Pencil class="w-5 h-5" />
          </div>
          <div>
            <h2 class="text-base font-bold text-white tracking-tight">Edit Project #{project.id}</h2>
            <p class="text-xs text-slate-400">Update project metadata and regulatory configuration</p>
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

        <div class="space-y-1.5">
          <label for="edit-proj-name" class="block text-xs font-semibold text-slate-300">
            Project Name <span class="text-rose-400">*</span>
          </label>
          <input
            id="edit-proj-name"
            type="text"
            bind:value={name}
            placeholder="e.g. Waterfront Commercial Tower"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
          />
        </div>

        <div class="space-y-1.5">
          <label for="edit-proj-desc" class="block text-xs font-semibold text-slate-300">
            Description
          </label>
          <textarea
            id="edit-proj-desc"
            rows="3"
            bind:value={description}
            placeholder="Optional project scope or notes..."
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
          ></textarea>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <label for="edit-proj-status" class="block text-xs font-semibold text-slate-300">
              Status
            </label>
            <select
              id="edit-proj-status"
              bind:value={status}
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            >
              <option value="Active">Active</option>
              <option value="Draft">Draft</option>
              <option value="Archived">Archived</option>
            </select>
          </div>

          <div class="space-y-1.5">
            <label for="edit-proj-country" class="block text-xs font-semibold text-slate-300">
              Jurisdiction
            </label>
            <select
              id="edit-proj-country"
              bind:value={country}
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
            >
              <option value="Canada">Canada (NBC)</option>
              <option value="US">United States (IBC)</option>
              <option value="UK">United Kingdom</option>
              <option value="EU">European Union</option>
            </select>
          </div>
        </div>

        <div class="space-y-1.5">
          <label for="edit-proj-domain" class="block text-xs font-semibold text-slate-300">
            Analysis Domain
          </label>
          <select
            id="edit-proj-domain"
            bind:value={analysisType}
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
          >
            <option value="Architecture">Architecture</option>
            <option value="Piping (Corrosive)">Piping (Corrosive)</option>
            <option value="Halo">Halo (Blue Halo)</option>
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
          disabled={isSaving || !name.trim()}
          on:click={handleSave}
          class="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] disabled:opacity-50 disabled:hover:scale-100"
        >
          <Check class="w-3.5 h-3.5" />
          <span>{isSaving ? 'Saving...' : 'Save Changes'}</span>
        </button>
      </div>
    </div>
  </div>
{/if}
