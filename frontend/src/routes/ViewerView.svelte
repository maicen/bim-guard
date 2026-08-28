<script lang="ts">
  import { onMount } from 'svelte';
  import { projectsApi } from '../lib/api';
  import type { Project } from '../lib/types';
  import IfcViewer from '../lib/components/IfcViewer.svelte';
  import { ScanEye, Layers } from 'lucide-svelte';

  export let initialProjectId: number | null = null;
  export let initialElementGuid: string | null = null;
  export let initialBcfArtifactId: number | null = null;

  let projects: Project[] = [];
  let selectedProjectId: number | null = initialProjectId;
  let selectedElementGuid: string | null = initialElementGuid;
  let selectedBcfArtifactId: number | null = initialBcfArtifactId;

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

  $: if (initialProjectId) {
    selectedProjectId = initialProjectId;
  }
  $: if (initialElementGuid !== undefined) {
    selectedElementGuid = initialElementGuid;
  }
  $: if (initialBcfArtifactId !== undefined) {
    selectedBcfArtifactId = initialBcfArtifactId;
  }
</script>

<div class="space-y-6 max-w-6xl mx-auto">
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <div class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Viewer</div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">3D OpenBIM Viewer</h1>
      <p class="text-xs sm:text-sm text-slate-400">
        Spatial geometry inspection powered by ThatOpenCompany web-ifc and BCF viewpoints.
      </p>
    </div>

    <!-- Project dropdown -->
    {#if projects.length > 0}
      <div class="flex items-center gap-3">
        <label for="viewer-project-select" class="text-xs uppercase tracking-wider font-semibold text-slate-400">
          Model:
        </label>
        <select
          id="viewer-project-select"
          bind:value={selectedProjectId}
          class="px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        >
          {#each projects as p}
            <option value={p.id}>{p.name} (#{p.id})</option>
          {/each}
        </select>
      </div>
    {/if}
  </div>

  {#if selectedElementGuid}
    <div class="p-3 rounded-xl bg-blue-950/40 border border-blue-800/60 text-xs text-blue-300 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <ScanEye class="w-4 h-4 text-blue-400 shrink-0" />
        <span>Focusing on violating element GUID: <strong class="font-mono">{selectedElementGuid}</strong></span>
      </div>
      <button
        type="button"
        on:click={() => (selectedElementGuid = null)}
        class="text-blue-400 hover:text-white underline text-[11px]"
      >
        Clear Selection
      </button>
    </div>
  {/if}

  {#if projects.length === 0}
    <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400 flex items-center justify-between">
      <span>No saved projects with IFC models found. You can upload an IFC model under Projects or open a local IFC file directly in the viewport below.</span>
    </div>
  {/if}

  <IfcViewer projectId={selectedProjectId} elementGuid={selectedElementGuid} bcfArtifactId={selectedBcfArtifactId} />
</div>
