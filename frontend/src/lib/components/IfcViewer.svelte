<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { Loader2, AlertCircle, RefreshCw, UploadCloud, Layers } from 'lucide-svelte';
  import { projectsApi, analyzeApi } from '../api';

  export let projectId: number | null = null;
  export let elementGuid: string | null = null;
  export let bcfArtifactId: number | null = null;
  /**
   * Which of the project's attached models to render, by project_ifc_files.id.
   * null renders the project's primary, which is also what a project whose
   * model predates that table resolves to.
   */
  export let fileId: number | null = null;
  /** Display name for the model on screen, shown in the viewport title bar. */
  export let fileName: string = '';

  let containerEl: HTMLDivElement;
  let fileInputEl: HTMLInputElement;
  let viewerAPI: any = null;
  let loading = false;
  let loadingMessage = 'Initializing OpenBIM 3D Viewport...';
  let error: string | null = null;
  let loadedProjectId: number | null = null;
  let loadedFileId: number | null = null;
  let loadedBcfArtifactId: number | null = null;
  let isInitialized = false;

  async function init() {
    if (!containerEl || isInitialized) return;
    try {
      loading = true;
      loadingMessage = 'Loading 3D graphics engine...';
      error = null;

      // Dynamic runtime import from static assets without bundling through Vite
      const viewerModuleUrl = '/static/js/viewer/ifc-viewer.js?v=viewer-camera-state-3';
      const mod = await import(/* @vite-ignore */ viewerModuleUrl);
      viewerAPI = await mod.initViewer(containerEl);
      isInitialized = true;

      if (projectId) {
        await loadProjectModel(projectId, fileId);
      }
    } catch (err: any) {
      console.error('Failed to initialize 3D viewer:', err);
      error = err?.message || 'Failed to initialize 3D viewer engine';
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

      // Only when swapping one model of a project for another. Coming to a
      // project fresh should frame that model, not inherit a viewpoint chosen
      // for whatever was on screen before.
      const isModelSwap = loadedProjectId === id;
      const camera = isModelSwap ? viewerAPI.getCameraState?.() ?? null : null;

      const ifcUrl =
        targetFileId === null
          ? projectsApi.getIfcUrl(id)
          : projectsApi.getIfcFileUrl(id, targetFileId);
      await viewerAPI.loadIfc(ifcUrl);
      loadedProjectId = id;
      loadedFileId = targetFileId;

      if (camera) await viewerAPI.setCameraState?.(camera);

      if (bcfArtifactId) {
        loadingMessage = 'Loading BCF viewpoints...';
        const bcfUrl = analyzeApi.getBcfArtifactUrl(bcfArtifactId);
        await viewerAPI.loadBcf(bcfUrl, elementGuid);
        loadedBcfArtifactId = bcfArtifactId;
      } else if (elementGuid) {
        const topic = viewerAPI.findTopicByElementGuid(elementGuid);
        if (topic) {
          await viewerAPI.selectTopic(topic);
        }
      }
    } catch (err: any) {
      console.error('Failed to load project IFC:', err);
      error = err?.message || 'Failed to load IFC geometry for this project';
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
      console.error('Failed to parse local IFC file:', err);
      error = err?.message || 'Failed to parse local IFC model';
    } finally {
      loading = false;
      target.value = '';
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

  $: if (viewerAPI && projectId && (projectId !== loadedProjectId || fileId !== loadedFileId)) {
    loadProjectModel(projectId, fileId);
  }

  $: if (viewerAPI && bcfArtifactId && bcfArtifactId !== loadedBcfArtifactId && loadedProjectId) {
    loadedBcfArtifactId = bcfArtifactId;
    const bcfUrl = analyzeApi.getBcfArtifactUrl(bcfArtifactId);
    viewerAPI.loadBcf(bcfUrl, elementGuid);
  }

  $: if (viewerAPI && elementGuid && loadedProjectId) {
    const topic = viewerAPI.findTopicByElementGuid(elementGuid);
    if (topic) {
      viewerAPI.selectTopic(topic);
    }
  }
</script>

<div class="rounded-2xl border border-slate-800 bg-slate-950 overflow-hidden shadow-2xl relative flex flex-col">
  <!-- Viewport Window Top Bar -->
  <div class="h-11 bg-slate-900/90 backdrop-blur-md border-b border-slate-800 px-4 flex items-center justify-between z-20">
    <div class="flex items-center gap-2">
      <span class="w-3 h-3 rounded-full bg-rose-500/80 shadow-sm shadow-rose-500/20"></span>
      <span class="w-3 h-3 rounded-full bg-amber-500/80 shadow-sm shadow-amber-500/20"></span>
      <span class="w-3 h-3 rounded-full bg-emerald-500/80 shadow-sm shadow-emerald-500/20"></span>
      <div class="flex items-center gap-2 ml-3">
        <Layers class="w-4 h-4 text-blue-400" />
        <span class="text-xs font-semibold text-slate-200 tracking-wide">Native OpenBIM 3D Viewport</span>
      </div>
    </div>

    <div class="flex items-center gap-3">
      {#if loading}
        <div class="flex items-center gap-2 px-3 py-1 rounded-full bg-blue-950/60 border border-blue-800/60 text-xs text-blue-300">
          <Loader2 class="w-3.5 h-3.5 animate-spin text-blue-400" />
          <span class="font-medium text-caption">{loadingMessage}</span>
        </div>
      {/if}

      {#if projectId}
        <span class="px-2.5 py-0.5 rounded-md bg-emerald-950/60 border border-emerald-800/40 text-xs font-mono font-medium text-emerald-400">
          Project #{projectId}
        </span>
      {/if}

      {#if fileName}
        <span
          class="px-2.5 py-0.5 rounded-md bg-blue-950/60 border border-blue-800/40 text-xs font-medium text-blue-300 max-w-[220px] truncate"
          title={fileName}
        >
          Viewing: {fileName}
        </span>
      {/if}

      <!-- Local File Upload Button -->
      <button
        type="button"
        on:click={() => fileInputEl?.click()}
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-slate-50 text-xs font-medium transition-colors"
        title="Open a local IFC model directly"
      >
        <UploadCloud class="w-3.5 h-3.5" />
        <span>Open Local IFC</span>
      </button>
      <input
        type="file"
        accept=".ifc"
        bind:this={fileInputEl}
        on:change={handleLocalFileUpload}
        class="hidden"
      />
    </div>
  </div>

  <!-- Error Alert Banner -->
  {#if error}
    <div class="p-3.5 bg-red-950/80 border-b border-red-800/60 text-xs text-red-200 flex items-center justify-between z-20">
      <div class="flex items-center gap-2">
        <AlertCircle class="w-4 h-4 text-red-400 shrink-0" />
        <span>{error}</span>
      </div>
      {#if projectId}
        <button
          type="button"
          on:click={() => loadProjectModel(projectId, fileId)}
          class="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-900/80 hover:bg-red-800 text-slate-50 text-caption font-medium transition-colors"
        >
          <RefreshCw class="w-3 h-3" />
          <span>Retry</span>
        </button>
      {/if}
    </div>
  {/if}

  <!-- Viewport DOM Container (ThatOpen mounts here) -->
  <div
    bind:this={containerEl}
    class="bimguard-viewer-container w-full h-[720px] bg-slate-950 relative min-h-[500px]"
  ></div>
</div>

