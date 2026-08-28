<script lang="ts">
  import { onMount } from 'svelte';
  import { projectsApi } from '../lib/api';
  import type { Project } from '../lib/types';
  import IfcViewer from '../lib/components/IfcViewer.svelte';

  export let initialProjectId: number | null = null;

  let projects: Project[] = [];
  let selectedProjectId: number | null = initialProjectId;

  async function loadProjects() {
    try {
      const res = await projectsApi.list();
      projects = res.projects.filter((p) => Boolean(p.ifc_file_path));
      if (!selectedProjectId && projects.length > 0) {
        selectedProjectId = projects[0].id;
      }
    } catch (err) {
      console.error('Failed to load projects for viewer:', err);
    }
  }

  onMount(() => {
    loadProjects();
  });
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between flex-wrap gap-4">
    <div>
      <h1 class="text-2xl font-bold tracking-tight text-white">3D OpenBIM Viewer</h1>
      <p class="text-sm text-slate-400 mt-1">Interactive 3D model exploration with element clash highlighting</p>
    </div>

    <!-- Project dropdown -->
    {#if projects.length > 0}
      <div class="flex items-center gap-3">
        <label for="viewer-project-select" class="text-xs uppercase tracking-wider font-semibold text-slate-400">
          Loaded Model:
        </label>
        <select
          id="viewer-project-select"
          bind:value={selectedProjectId}
          class="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-white focus:outline-none focus:border-emerald-500"
        >
          {#each projects as p}
            <option value={p.id}>{p.name} (#{p.id})</option>
          {/each}
        </select>
      </div>
    {/if}
  </div>

  {#if projects.length === 0}
    <div class="p-8 text-center border border-slate-800 rounded-xl bg-slate-900/50 space-y-2">
      <div class="text-slate-300 font-semibold">No IFC models uploaded yet</div>
      <div class="text-xs text-slate-400">Upload an IFC model under Projects to inspect it in the 3D viewport.</div>
    </div>
  {:else}
    <IfcViewer projectId={selectedProjectId} />
  {/if}
</div>

