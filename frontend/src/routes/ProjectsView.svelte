<script lang="ts">
  import { onMount } from 'svelte';
  import { projectsApi } from '../lib/api';
  import type { Project } from '../lib/types';

  export let onSelectProjectForAudit: (projectId: number) => void;
  export let onSelectProjectForViewer: (projectId: number) => void;

  let projects: Project[] = [];
  let loading = true;
  let error = '';

  let showCreateModal = false;
  let newName = '';
  let newDescription = '';
  let newCountry = 'US';
  let newAnalysisType = 'Architecture';
  let ifcFileInput: HTMLInputElement;
  let creating = false;

  async function loadProjects() {
    loading = true;
    error = '';
    try {
      const res = await projectsApi.list();
      projects = res.projects;
    } catch (err: any) {
      error = err.message || 'Failed to load projects.';
    } finally {
      loading = false;
    }
  }

  async function handleCreate() {
    if (!newName.trim()) return;
    creating = true;
    error = '';
    try {
      if (ifcFileInput && ifcFileInput.files && ifcFileInput.files[0]) {
        const formData = new FormData();
        formData.append('name', newName.trim());
        formData.append('description', newDescription.trim());
        formData.append('country', newCountry);
        formData.append('analysis_type', newAnalysisType);
        formData.append('ifc_file', ifcFileInput.files[0]);
        await projectsApi.uploadWithIfc(formData);
      } else {
        await projectsApi.create({
          name: newName.trim(),
          description: newDescription.trim(),
          country: newCountry,
          analysis_type: newAnalysisType,
        });
      }
      showCreateModal = false;
      newName = '';
      newDescription = '';
      await loadProjects();
    } catch (err: any) {
      error = err.message || 'Failed to create project.';
    } finally {
      creating = false;
    }
  }

  async function handleDelete(id: number) {
    if (!confirm('Are you sure you want to delete this project?')) return;
    try {
      await projectsApi.delete(id);
      await loadProjects();
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  }

  onMount(() => {
    loadProjects();
  });
</script>

<div class="space-y-6">
  <!-- Header with title and Create button -->
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold tracking-tight text-white">Project Workspaces</h1>
      <p class="text-sm text-slate-400 mt-1">Manage BIM projects, IFC models, and compliance audit histories</p>
    </div>
    <button
      on:click={() => (showCreateModal = true)}
      class="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold shadow-lg shadow-emerald-600/20 transition-colors"
    >
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
      </svg>
      New Project
    </button>
  </div>

  {#if error}
    <div class="p-4 rounded-lg bg-rose-950/40 border border-rose-800 text-rose-300 text-sm">
      {error}
    </div>
  {/if}

  {#if loading}
    <div class="py-16 text-center text-slate-400">Loading projects from FastAPI backend...</div>
  {:else if projects.length === 0}
    <div class="py-16 text-center border border-dashed border-slate-800 rounded-xl p-8 space-y-4">
      <div class="text-slate-400 text-sm">No projects created yet.</div>
      <button
        on:click={() => (showCreateModal = true)}
        class="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-semibold"
      >
        Create your first project
      </button>
    </div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      {#each projects as project}
        <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur shadow-xl hover:border-slate-700 transition-all flex flex-col justify-between space-y-4">
          <div class="space-y-2">
            <div class="flex items-start justify-between gap-2">
              <h3 class="font-semibold text-white text-base leading-snug">{project.name}</h3>
              <span class="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                #{project.id}
              </span>
            </div>
            <p class="text-xs text-slate-400 line-clamp-2 min-h-[32px]">
              {project.description || 'No description provided.'}
            </p>
            <div class="flex items-center gap-2 text-xs text-slate-400 pt-2 border-t border-slate-800/80">
              <span class="px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 text-[10px] font-semibold uppercase">
                {project.analysis_type}
              </span>
              <span>•</span>
              <span>{project.country}</span>
              <span>•</span>
              <span class="{project.ifc_file_path ? 'text-emerald-400' : 'text-amber-400'}">
                {project.ifc_file_path ? 'IFC Attached' : 'No IFC Model'}
              </span>
            </div>
          </div>

          <div class="flex items-center justify-between pt-3 border-t border-slate-800/80 gap-2">
            <button
              on:click={() => onSelectProjectForAudit(project.id)}
              class="flex-1 py-1.5 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow transition-colors"
            >
              Run Audit
            </button>
            {#if project.ifc_file_path}
              <button
                on:click={() => onSelectProjectForViewer(project.id)}
                class="py-1.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-colors"
              >
                3D View
              </button>
            {/if}
            <button
              on:click={() => handleDelete(project.id)}
              class="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-slate-800 transition-colors"
              title="Delete Project"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
              </svg>
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Create Modal -->
  {#if showCreateModal}
    <div class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div class="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl space-y-4">
        <h2 class="text-lg font-bold text-white">Create New Project</h2>
        <div class="space-y-3">
          <div>
            <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Project Name *
            </label>
            <input
              type="text"
              bind:value={newName}
              placeholder="e.g. Headquarters Block A"
              class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-emerald-500"
            />
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Description
            </label>
            <textarea
              bind:value={newDescription}
              rows="3"
              placeholder="Project details, scope, or facility info..."
              class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-emerald-500"
            ></textarea>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Domain
              </label>
              <select
                bind:value={newAnalysisType}
                class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-emerald-500"
              >
                <option value="Architecture">Architecture</option>
                <option value="MEP">MEP Piping</option>
                <option value="Structure">Structural</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Jurisdiction
              </label>
              <input
                type="text"
                bind:value={newCountry}
                class="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Initial IFC File (Optional)
            </label>
            <input
              type="file"
              accept=".ifc"
              bind:this={ifcFileInput}
              class="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-emerald-400 hover:file:bg-slate-700"
            />
          </div>
        </div>

        <div class="flex items-center justify-end gap-2 pt-4 border-t border-slate-800">
          <button
            on:click={() => (showCreateModal = false)}
            class="px-3.5 py-1.5 rounded-lg text-sm text-slate-400 hover:text-white"
          >
            Cancel
          </button>
          <button
            on:click={handleCreate}
            disabled={creating || !newName.trim()}
            class="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-semibold shadow"
          >
            {creating ? 'Creating...' : 'Create Project'}
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>

