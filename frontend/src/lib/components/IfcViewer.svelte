<script lang="ts">
  import { run } from "svelte/legacy";

  import { onMount, onDestroy } from "svelte";
  import { Loader2, AlertCircle, RefreshCw, ClipboardList, LayoutGrid, PenTool } from "lucide-svelte";
  import { projectsApi, modelsApi, analyzeApi } from "../api";
  import { authHeaders, authReady } from "../authToken";
  import type { Model } from "../types";
  import CollapsiblePanel from "./CollapsiblePanel.svelte";
  import ViewerRibbon from "./viewer/ViewerRibbon.svelte";
  import LayersPanel from "./viewer/LayersPanel.svelte";
  import DrawingsPanel from "./viewer/DrawingsPanel.svelte";

  interface Props {
    projectId?: number | null;
    elementGuid?: string | null;
    bcfArtifactId?: number | null;
    /**
     * Which of the project's attached models to render, by project_ifc_files.id.
     * null renders the project's primary, which is also what a project whose
     * model predates that table resolves to.
     */
    fileId?: number | null;
    /** Display name for the model on screen, shown by the ribbon when there's only one to pick from. */
    fileName?: string;
    /** The project's attached models, forwarded to the ribbon's model switcher when there's more than one. */
    ifcFiles?: Model[];
    /** Called with the id the user picked from the ribbon's model switcher. */
    onSelectFile?: (id: number) => void;
  }

  let {
    projectId = null,
    elementGuid = null,
    bcfArtifactId = null,
    fileId = null,
    fileName = "",
    ifcFiles = [],
    onSelectFile,
  }: Props = $props();

  let viewportHost: HTMLDivElement = $state();
  let detailsHost: HTMLDivElement = $state();
  let drawingsSheetBoardHost: HTMLDivElement | undefined = $state();
  let viewerAPI: any = $state(null);
  let loading = $state(false);
  let loadingMessage = $state("Initializing OpenBIM 3D Viewport...");
  let error: string | null = $state(null);
  let loadedProjectId: number | null = $state(null);
  let loadedFileId: number | null = $state(null);
  let loadedBcfArtifactId: number | null = $state(null);
  let isInitialized = false;

  async function init() {
    if (!viewportHost || isInitialized) return;
    try {
      loading = true;
      loadingMessage = "Loading 3D graphics engine...";
      error = null;

      // Dynamic runtime import from static assets without bundling through Vite
      const viewerModuleUrl = "/static/js/viewer/ifc-viewer.js?v=viewer-ribbon-2";
      const mod = await import(/* @vite-ignore */ viewerModuleUrl);
      viewerAPI = await mod.initViewer({
        viewport: viewportHost,
        details: detailsHost,
        drawings: drawingsSheetBoardHost,
      });
      isInitialized = true;

      if (projectId) {
        await loadProjectModel(projectId, fileId);
      }
    } catch (err: any) {
      console.error("Failed to initialize 3D viewer:", err);
      error = err?.message || "Failed to initialize 3D viewer engine";
    } finally {
      loading = false;
    }
  }

  async function loadProjectModel(id: number, targetFileId: number | null = null) {
    if (!viewerAPI) return;
    try {
      loading = true;
      loadingMessage = fileName
        ? `Loading ${fileName}...`
        : `Loading IFC geometry for Project #${id}...`;
      error = null;

      // This module's own fetch (in the static viewer bundle) doesn't go
      // through api.ts's apiFetch, so it doesn't get that choke point's wait
      // for the initial Supabase session lookup for free. A direct deep link
      // into the viewer can reach here before that lookup settles; wait for
      // it explicitly so the first request carries a real token instead of
      // racing into a "missing bearer token" 401.
      await authReady;

      // Only when swapping one model of a project for another. Coming to a
      // project fresh should frame that model, not inherit a viewpoint chosen
      // for whatever was on screen before.
      const isModelSwap = loadedProjectId === id;
      const camera = isModelSwap ? (viewerAPI.getCameraState?.() ?? null) : null;

      const ifcUrl =
        targetFileId === null
          ? projectsApi.getIfcUrl(id)
          : modelsApi.downloadUrl(id, targetFileId);
      await viewerAPI.loadIfc(ifcUrl, authHeaders);
      loadedProjectId = id;
      loadedFileId = targetFileId;

      if (camera) await viewerAPI.setCameraState?.(camera);

      if (bcfArtifactId) {
        loadingMessage = "Loading BCF viewpoints...";
        const bcfUrl = analyzeApi.getBcfArtifactUrl(bcfArtifactId);
        await viewerAPI.loadBcf(bcfUrl, elementGuid, authHeaders);
        loadedBcfArtifactId = bcfArtifactId;
      } else if (elementGuid) {
        const topic = viewerAPI.findTopicByElementGuid(elementGuid);
        if (topic) {
          await viewerAPI.selectTopic(topic);
        }
      }
    } catch (err: any) {
      console.error("Failed to load project IFC:", err);
      error = err?.message || "Failed to load IFC geometry for this project";
    } finally {
      loading = false;
    }
  }

  async function loadLocalFile(file: File) {
    if (!viewerAPI) return;
    try {
      loading = true;
      loadingMessage = `Parsing ${file.name}...`;
      error = null;
      await viewerAPI.loadIfc(file);
      loadedProjectId = null;
      loadedFileId = null;
    } catch (err: any) {
      console.error("Failed to parse local IFC file:", err);
      error = err?.message || "Failed to parse local IFC model";
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    init();
  });

  onDestroy(() => {
    if (viewerAPI && viewerAPI.dispose) {
      viewerAPI.dispose();
      viewerAPI = null;
    }
    isInitialized = false;
  });

  run(() => {
    if (viewerAPI && projectId && (projectId !== loadedProjectId || fileId !== loadedFileId)) {
      loadProjectModel(projectId, fileId);
    }
  });

  run(() => {
    if (viewerAPI && bcfArtifactId && bcfArtifactId !== loadedBcfArtifactId && loadedProjectId) {
      loadedBcfArtifactId = bcfArtifactId;
      const bcfUrl = analyzeApi.getBcfArtifactUrl(bcfArtifactId);
      viewerAPI.loadBcf(bcfUrl, elementGuid, authHeaders);
    }
  });

  run(() => {
    if (viewerAPI && elementGuid && loadedProjectId) {
      const topic = viewerAPI.findTopicByElementGuid(elementGuid);
      if (topic) {
        viewerAPI.selectTopic(topic);
      }
    }
  });
</script>

<div
  class="bimguard-viewer-root bimguard-viewer-container relative flex flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl"
>
  <!-- Loading indicator: a slim strip, present only while actually loading so
       the viewport otherwise fills the whole card right up to the ribbon. -->
  {#if loading}
    <div
      class="z-20 flex shrink-0 items-center gap-2 border-b border-blue-800/60 bg-blue-950/60 px-4 py-1.5 text-xs text-blue-300"
    >
      <Loader2 class="h-3.5 w-3.5 animate-spin text-blue-400" />
      <span class="font-medium">{loadingMessage}</span>
    </div>
  {/if}

  <!-- Error Alert Banner -->
  {#if error}
    <div
      class="z-20 flex shrink-0 items-center justify-between border-b border-red-800/60 bg-red-950/80 p-3.5 text-xs text-red-200"
    >
      <div class="flex items-center gap-2">
        <AlertCircle class="h-4 w-4 shrink-0 text-red-400" />
        <span>{error}</span>
      </div>
      {#if projectId}
        <button
          type="button"
          onclick={() => loadProjectModel(projectId, fileId)}
          class="flex items-center gap-1 rounded-lg bg-red-900/80 px-2.5 py-1 text-caption font-medium text-slate-50 transition-colors hover:bg-red-800"
        >
          <RefreshCw class="h-3 w-3" />
          <span>Retry</span>
        </button>
      {/if}
    </div>
  {/if}

  <!-- Revit-style ribbon: tabs of grouped buttons driving the engine bridge -->
  {#if viewerAPI}
    <ViewerRibbon
      {viewerAPI}
      {fileName}
      {ifcFiles}
      selectedFileId={fileId}
      {onSelectFile}
      onLocalFile={loadLocalFile}
    />
  {/if}

  <!-- Docked workspace: collapsible BCF/Layers/Drawings panels around the 3D viewport -->
  <div class="flex min-h-0 flex-1">
    <CollapsiblePanel
      title="BCF Topics"
      icon={ClipboardList}
      side="left"
      id="viewer-details"
      collapsed={false}
      resizable
      initialSize={320}
    >
      <div bind:this={detailsHost} class="min-h-0"></div>
    </CollapsiblePanel>

    <div bind:this={viewportHost} class="min-h-0 min-w-0 flex-1 bg-slate-950"></div>

    <CollapsiblePanel
      title="Layers"
      icon={LayoutGrid}
      side="right"
      id="viewer-layers"
      collapsed={true}
      resizable
    >
      <LayersPanel {viewerAPI} />
    </CollapsiblePanel>

    <CollapsiblePanel
      title="Drawings"
      icon={PenTool}
      side="right"
      id="viewer-drawings"
      collapsed={true}
      resizable
      initialSize={360}
      maxSize={720}
    >
      <DrawingsPanel {viewerAPI} bind:sheetBoardHost={drawingsSheetBoardHost} />
    </CollapsiblePanel>
  </div>
</div>
