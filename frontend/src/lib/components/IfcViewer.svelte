<script lang="ts">
  import { run } from "svelte/legacy";

  import { onMount, onDestroy } from "svelte";
  import { Loader2, AlertCircle, RefreshCw, UploadCloud, Layers } from "lucide-svelte";
  import { projectsApi, analyzeApi } from "../api";
  import { authHeaders, authReady } from "../authToken";

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
    /** Display name for the model on screen, shown in the viewport title bar. */
    fileName?: string;
  }

  let {
    projectId = null,
    elementGuid = null,
    bcfArtifactId = null,
    fileId = null,
    fileName = "",
  }: Props = $props();

  let containerEl: HTMLDivElement = $state();
  let fileInputEl: HTMLInputElement = $state();
  let viewerAPI: any = $state(null);
  let loading = $state(false);
  let loadingMessage = $state("Initializing OpenBIM 3D Viewport...");
  let error: string | null = $state(null);
  let loadedProjectId: number | null = $state(null);
  let loadedFileId: number | null = $state(null);
  let loadedBcfArtifactId: number | null = $state(null);
  let isInitialized = false;

  async function init() {
    if (!containerEl || isInitialized) return;
    try {
      loading = true;
      loadingMessage = "Loading 3D graphics engine...";
      error = null;

      // Dynamic runtime import from static assets without bundling through Vite
      const viewerModuleUrl = "/static/js/viewer/ifc-viewer.js?v=viewer-isolate-1";
      const mod = await import(/* @vite-ignore */ viewerModuleUrl);
      viewerAPI = await mod.initViewer(containerEl);
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
          : projectsApi.getIfcFileUrl(id, targetFileId);
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

  async function handleLocalFileUpload(event: Event) {
    const target = event.target as HTMLInputElement;
    const file = target.files?.[0];
    if (!file || !viewerAPI) return;

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
      target.value = "";
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
  class="relative flex flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl"
>
  <!-- Viewport Window Top Bar -->
  <div
    class="z-20 flex h-11 items-center justify-between border-b border-slate-800 bg-slate-900/90 px-4 backdrop-blur-md"
  >
    <div class="flex items-center gap-2">
      <span class="h-3 w-3 rounded-full bg-rose-500/80 shadow-sm shadow-rose-500/20"></span>
      <span class="h-3 w-3 rounded-full bg-amber-500/80 shadow-sm shadow-amber-500/20"></span>
      <span class="h-3 w-3 rounded-full bg-emerald-500/80 shadow-sm shadow-emerald-500/20"></span>
      <div class="ml-3 flex items-center gap-2">
        <Layers class="h-4 w-4 text-blue-400" />
        <span class="text-xs font-semibold tracking-wide text-slate-200"
          >Native OpenBIM 3D Viewport</span
        >
      </div>
    </div>

    <div class="flex items-center gap-3">
      {#if loading}
        <div
          class="flex items-center gap-2 rounded-md border border-blue-800/60 bg-blue-950/60 px-3 py-1 text-xs text-blue-300"
        >
          <Loader2 class="h-3.5 w-3.5 animate-spin text-blue-400" />
          <span class="text-caption font-medium">{loadingMessage}</span>
        </div>
      {/if}

      {#if projectId}
        <span
          class="rounded-md border border-emerald-800/40 bg-emerald-950/60 px-2.5 py-0.5 font-mono text-xs font-medium text-emerald-400"
        >
          Project #{projectId}
        </span>
      {/if}

      {#if fileName}
        <span
          class="max-w-[220px] truncate rounded-md border border-blue-800/40 bg-blue-950/60 px-2.5 py-0.5 text-xs font-medium text-blue-300"
          title={fileName}
        >
          Viewing: {fileName}
        </span>
      {/if}

      <!-- Local File Upload Button -->
      <button
        type="button"
        onclick={() => fileInputEl?.click()}
        class="flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
        title="Open a local IFC model directly"
      >
        <UploadCloud class="h-3.5 w-3.5" />
        <span>Open Local IFC</span>
      </button>
      <input
        type="file"
        accept=".ifc"
        bind:this={fileInputEl}
        onchange={handleLocalFileUpload}
        class="hidden"
      />
    </div>
  </div>

  <!-- Error Alert Banner -->
  {#if error}
    <div
      class="z-20 flex items-center justify-between border-b border-red-800/60 bg-red-950/80 p-3.5 text-xs text-red-200"
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

  <!-- Viewport DOM Container (ThatOpen mounts here) -->
  <div
    bind:this={containerEl}
    class="bimguard-viewer-container relative h-[720px] min-h-[500px] w-full bg-slate-950"
  ></div>
</div>
