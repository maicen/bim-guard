<script lang="ts">
  import { untrack } from "svelte";
  import { run } from "svelte/legacy";

  import { onMount } from "svelte";
  import { projectsApi } from "../lib/api";
  import type { Project, ProjectIfcFile } from "../lib/types";
  import IfcViewer from "../lib/components/IfcViewer.svelte";
  import { ScanEye, Layers } from "lucide-svelte";

  interface Props {
    initialProjectId?: number | null;
    initialElementGuid?: string | null;
    initialBcfArtifactId?: number | null;
  }

  let {
    initialProjectId = null,
    initialElementGuid = null,
    initialBcfArtifactId = null,
  }: Props = $props();

  let projects: Project[] = $state([]);
  // These `initial*` props seed local state once. The component is mounted
  // inside App's view switch, so it remounts whenever the target changes;
  // untrack states that the one-time read is deliberate.
  let selectedProjectId: number | null = $state(untrack(() => initialProjectId));
  let selectedElementGuid: string | null = $state(untrack(() => initialElementGuid));
  let selectedBcfArtifactId: number | null = $state(untrack(() => initialBcfArtifactId));

  // The project's attached models. A project predating project_ifc_files
  // reports its one model here too, with a null id, so this list is the single
  // shape the picker renders either side of that migration.
  let ifcFiles: ProjectIfcFile[] = $state([]);
  let selectedFileId: number | null = $state(null);
  let filesProjectId: number | null = null;
  // The viewport is held back until the list arrives. Loading the project's
  // primary first and the picked model a moment later would fetch two IFCs to
  // show one, and these files are large.
  let filesReady = $state(false);

  let selectedFile = $derived(ifcFiles.find((f) => f.id === selectedFileId) ?? ifcFiles[0] ?? null);

  async function loadIfcFiles(projectId: number) {
    // Guarded so the reactive statement below re-fetches on a project change
    // but not on every unrelated state change that re-runs it.
    if (filesProjectId === projectId) return;
    filesProjectId = projectId;
    // Cleared before the await, not after: leaving the previous project's rows
    // in place would briefly pair a new project id with an old file id, and the
    // viewer would ask for a model that project does not have.
    ifcFiles = [];
    selectedFileId = null;
    filesReady = false;
    try {
      ifcFiles = await projectsApi.listIfcFiles(projectId);
      // Falls back to the primary, which list_project_ifc_files returns first.
      selectedFileId = ifcFiles.find((f) => f.is_primary)?.id ?? ifcFiles[0]?.id ?? null;
    } catch (err) {
      console.error("Failed to load project IFC files:", err);
      ifcFiles = [];
      selectedFileId = null;
    } finally {
      // Ready either way: on failure the viewer falls back to the project's
      // primary, which is what it rendered before there was a picker at all.
      filesReady = true;
    }
  }

  async function loadProjects() {
    try {
      const res = await projectsApi.list();
      projects = res.projects.filter((p) => Boolean(p.ifc_file_path));
      if (!selectedProjectId && projects.length > 0) {
        selectedProjectId = projects[0].id;
      }
    } catch (err) {
      console.error("Failed to load projects for viewer:", err);
    }
  }

  onMount(() => {
    loadProjects();
  });

  run(() => {
    if (selectedProjectId) {
      loadIfcFiles(selectedProjectId);
    }
  });

  run(() => {
    if (initialProjectId) {
      selectedProjectId = initialProjectId;
    }
  });
  run(() => {
    if (initialElementGuid !== undefined) {
      selectedElementGuid = initialElementGuid;
    }
  });
  run(() => {
    if (initialBcfArtifactId !== undefined) {
      selectedBcfArtifactId = initialBcfArtifactId;
    }
  });
</script>

<div class="mx-auto space-y-6">
  <div class="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
    <div>
      <div class="mb-1 text-xs font-bold uppercase tracking-widest text-slate-400">Viewer</div>
      <h1 class="text-2xl font-bold tracking-tight text-slate-50 sm:text-3xl">3D OpenBIM Viewer</h1>
      <p class="text-xs text-slate-400 sm:text-sm">
        Spatial geometry inspection powered by ThatOpenCompany web-ifc and BCF viewpoints.
      </p>
    </div>

    <!-- Project dropdown -->
    {#if projects.length > 0}
      <div class="flex items-center gap-3">
        <label
          for="viewer-project-select"
          class="text-xs font-semibold uppercase tracking-wider text-slate-400"
        >
          Project:
        </label>
        <select
          id="viewer-project-select"
          bind:value={selectedProjectId}
          class="rounded-xl border border-slate-800 bg-slate-900 px-3.5 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
        >
          {#each projects as p (p.id)}
            <option value={p.id}>{p.name} (#{p.id})</option>
          {/each}
        </select>

        {#if ifcFiles.length > 1}
          <label
            for="viewer-file-select"
            class="text-xs font-semibold uppercase tracking-wider text-slate-400"
          >
            Viewing:
          </label>
          <select
            id="viewer-file-select"
            bind:value={selectedFileId}
            class="max-w-[260px] rounded-xl border border-slate-800 bg-slate-900 px-3.5 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
          >
            {#each ifcFiles as file (file.id)}
              <option value={file.id}>
                {file.file_name || `Model #${file.id}`} — {file.role}{file.is_primary
                  ? " (primary)"
                  : ""}
              </option>
            {/each}
          </select>
        {/if}
      </div>
    {/if}
  </div>

  {#if ifcFiles.length > 1}
    <div
      class="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900/60 p-3 text-xs text-slate-400"
    >
      <Layers class="h-4 w-4 shrink-0 text-blue-400" />
      <span>
        This project carries {ifcFiles.length} models. Switching between them changes what the viewport
        renders only — the analysis results already on screen are left as they are.
      </span>
    </div>
  {/if}

  {#if selectedElementGuid}
    <div
      class="flex items-center justify-between rounded-xl border border-blue-800/60 bg-blue-950/40 p-3 text-xs text-blue-300"
    >
      <div class="flex items-center gap-2">
        <ScanEye class="h-4 w-4 shrink-0 text-blue-400" />
        <span
          >Focusing on violating element GUID: <strong class="font-mono"
            >{selectedElementGuid}</strong
          ></span
        >
      </div>
      <button
        type="button"
        onclick={() => (selectedElementGuid = null)}
        class="text-caption text-blue-400 underline hover:text-slate-50"
      >
        Clear Selection
      </button>
    </div>
  {/if}

  {#if projects.length === 0}
    <div
      class="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-xs text-slate-400"
    >
      <span
        >No saved projects with IFC models found. You can upload an IFC model under Projects or open
        a local IFC file directly in the viewport below.</span
      >
    </div>
  {/if}

  <IfcViewer
    projectId={filesReady ? selectedProjectId : null}
    fileId={selectedFile?.id ?? null}
    fileName={selectedFile?.file_name ?? ""}
    elementGuid={selectedElementGuid}
    bcfArtifactId={selectedBcfArtifactId}
  />
</div>
