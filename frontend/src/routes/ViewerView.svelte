<script lang="ts">
  import { untrack, onMount } from "svelte";
  import { router, replace } from "svelte-spa-router";
  import { projectsApi, modelsApi } from "../lib/api";
  import type { Project, Model } from "../lib/types";
  import IfcViewer from "../lib/components/IfcViewer.svelte";
  import { ScanEye } from "lucide-svelte";

  interface Props {
    initialProjectId?: number | null;
    initialElementGuid?: string | null;
    initialBcfArtifactId?: number | null;
    initialFileId?: number | null;
  }

  let {
    initialProjectId = null,
    initialElementGuid = null,
    initialBcfArtifactId = null,
    initialFileId = null,
  }: Props = $props();

  let projects: Project[] = $state([]);
  let selectedProjectId: number | null = $state(untrack(() => initialProjectId));
  let selectedElementGuid: string | null = $state(untrack(() => initialElementGuid));
  let selectedBcfArtifactId: number | null = $state(untrack(() => initialBcfArtifactId));

  // The project's attached models. A project predating project_ifc_files
  // reports its one model here too, with a null id, so this list is the single
  // shape the picker renders either side of that migration.
  let ifcFiles: Model[] = $state([]);
  let selectedFileId: number | null = $state(null);
  let filesProjectId: number | null = null;
  // The viewport is held back until the list arrives. Loading the project's
  // primary first and the picked model a moment later would fetch two IFCs to
  // show one, and these files are large.
  let filesReady = $state(false);

  let selectedFile = $derived(ifcFiles.find((f) => f.id === selectedFileId) ?? ifcFiles[0] ?? null);

  async function loadIfcFiles(projectId: number) {
    if (filesProjectId === projectId) return;
    filesProjectId = projectId;
    ifcFiles = [];
    selectedFileId = null;
    filesReady = false;
    try {
      ifcFiles = await modelsApi.list(projectId);
      const preferred =
        initialFileId !== null ? ifcFiles.find((f) => f.id === initialFileId) : undefined;
      selectedFileId = preferred?.id ?? ifcFiles.find((f) => f.is_primary)?.id ?? ifcFiles[0]?.id ?? null;
    } catch (err) {
      console.error("Failed to load project IFC files:", err);
      ifcFiles = [];
      selectedFileId = null;
    } finally {
      filesReady = true;
    }
  }

  // Reflects the user's model pick in the URL (?file_id=...) so a deep link
  // into the viewer can land on a specific one of a project's models, the
  // same way project_id/element_guid/bcf_artifact_id already do.
  function selectFile(id: number | null) {
    selectedFileId = id;
    const params = new URLSearchParams(router.querystring || "");
    if (id !== null) {
      params.set("file_id", String(id));
    } else {
      params.delete("file_id");
    }
    replace(`/viewer?${params.toString()}`);
  }

  async function loadProjects() {
    try {
      const res = await projectsApi.list();
      projects = res.projects.filter((p) => Boolean(p.ifc_file_path));
    } catch (err) {
      console.error("Failed to load projects for viewer:", err);
    }
  }

  onMount(() => {
    loadProjects();
  });

  $effect(() => {
    if (initialProjectId !== undefined && initialProjectId !== selectedProjectId) {
      selectedProjectId = initialProjectId;
    }
  });

  $effect(() => {
    if (selectedProjectId) {
      loadIfcFiles(selectedProjectId);
    } else {
      ifcFiles = [];
      selectedFileId = null;
      filesReady = true;
    }
  });

  $effect(() => {
    if (initialElementGuid !== undefined) {
      selectedElementGuid = initialElementGuid;
    }
  });

  $effect(() => {
    if (initialBcfArtifactId !== undefined) {
      selectedBcfArtifactId = initialBcfArtifactId;
    }
  });
</script>

<div class="mx-auto space-y-4">
  {#if selectedElementGuid}
    <div
      class="flex items-center justify-between rounded-xl border border-info-border bg-info-bg p-3 text-xs text-info"
    >
      <div class="flex items-center gap-2">
        <ScanEye class="h-4 w-4 shrink-0 text-info" />
        <span
          >Focusing on violating element GUID: <strong class="font-mono"
            >{selectedElementGuid}</strong
          ></span
        >
      </div>
      <button
        type="button"
        onclick={() => (selectedElementGuid = null)}
        class="text-caption text-info underline hover:text-fg-primary"
      >
        Clear Selection
      </button>
    </div>
  {/if}

  {#if !selectedProjectId && projects.length > 0}
    <div
      class="flex items-center justify-between rounded-xl border border-border-default bg-surface-card p-4 text-xs text-fg-muted"
    >
      <span
        >No project currently selected. Please select a project from the top header above, or open a local IFC file directly in the viewport below.</span
      >
    </div>
  {:else if projects.length === 0}
    <div
      class="flex items-center justify-between rounded-xl border border-border-default bg-surface-card p-4 text-xs text-fg-muted"
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
    {ifcFiles}
    onSelectFile={selectFile}
  />
</div>
