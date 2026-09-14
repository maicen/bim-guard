<script lang="ts">
  import { run } from "svelte/legacy";

  import { onMount, onDestroy } from "svelte";
  import { Loader2, AlertCircle, RefreshCw, ClipboardList, LayoutGrid, PenTool, ListTree, Terminal } from "lucide-svelte";
  import { projectsApi, modelsApi, analyzeApi } from "../api";
  import { authHeaders, authReady } from "../authToken";
  import { resolvedTheme } from "../theme";
  import type { Model } from "../types";
  import CollapsiblePanel from "./CollapsiblePanel.svelte";
  import ViewerRibbon from "./viewer/ViewerRibbon.svelte";
  import LayersPanel from "./viewer/LayersPanel.svelte";
  import DrawingsPanel from "./viewer/DrawingsPanel.svelte";
  import SpatialTreePanel from "./viewer/SpatialTreePanel.svelte";
  import QueryConsolePanel from "./viewer/QueryConsolePanel.svelte";
  import PropertiesSection from "./viewer/PropertiesSection.svelte";
  import { AccordionRoot } from "./ui";

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

  const RIGHT_DOCK_SECTIONS_KEY = "bimguard-collapsible-panel:viewer-right-dock:open-sections";
  function loadOpenRightSections(): string[] {
    try {
      const raw = localStorage.getItem(RIGHT_DOCK_SECTIONS_KEY);
      return raw ? JSON.parse(raw) : ["bcf-topics"];
    } catch {
      return ["bcf-topics"];
    }
  }
  let openRightSections: string[] = $state(loadOpenRightSections());
  $effect(() => {
    try {
      localStorage.setItem(RIGHT_DOCK_SECTIONS_KEY, JSON.stringify(openRightSections));
    } catch {
      // Best-effort only (private browsing, storage disabled, etc.)
    }
  });

  const RIGHT_DOCK_SECTION_ICONS = [
    { id: "bcf-topics", label: "BCF Topics", icon: ClipboardList },
    { id: "spatial-tree", label: "Spatial Hierarchy", icon: ListTree },
    { id: "query-console", label: "Query Console", icon: Terminal },
    { id: "layers", label: "Layers", icon: LayoutGrid },
    { id: "drawings", label: "Drawings", icon: PenTool },
  ];

  // Historically BCF Topics lived in its own always-open left panel; default
  // the merged dock to open (with just BCF Topics expanded) so that visibility
  // carries over for anyone without a stored preference yet.
  let rightDockCollapsed = $state(false);
  function openRightSection(id: string) {
    rightDockCollapsed = false;
    if (!openRightSections.includes(id)) {
      openRightSections = [...openRightSections, id];
    }
  }
  let viewerAPI: any = $state(null);
  let loading = $state(false);
  let loadingMessage = $state("Initializing OpenBIM 3D Viewport...");
  let error: string | null = $state(null);
  let loadedProjectId: number | null = $state(null);
  let loadedFileId: number | null = $state(null);
  let loadedBcfArtifactId: number | null = $state(null);
  let elementNotFound = $state(false);
  let isInitialized = false;

  // A BCF topic carries its own selection; a bare element_guid deep link
  // needs a direct GlobalId lookup against the loaded model instead. Tries
  // the topic match first (cheap, and preserves the topic detail panel when
  // one exists) and falls back to selectByGuid so links without a BCF
  // artifact still land on the element instead of silently doing nothing.
  async function selectElementByGuid(guid: string) {
    elementNotFound = false;
    const topic = viewerAPI.findTopicByElementGuid(guid);
    if (topic) {
      await viewerAPI.selectTopic(topic);
      return;
    }
    const found = await viewerAPI.selectByGuid?.(guid);
    elementNotFound = !found;
  }

  async function init() {
    if (!viewportHost || isInitialized) return;
    try {
      loading = true;
      loadingMessage = "Loading 3D graphics engine...";
      error = null;

      // Dynamic runtime import from static assets without bundling through Vite
      const viewerModuleUrl = "/static/js/viewer/ifc-viewer.js?v=viewer-guid-select-1";
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
        await selectElementByGuid(elementGuid);
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
      selectElementByGuid(elementGuid);
    }
  });

  run(() => {
    if (viewerAPI && viewerAPI.setTheme && $resolvedTheme) {
      viewerAPI.setTheme($resolvedTheme);
    }
  });
</script>

<div
  class="bimguard-viewer-root bimguard-viewer-container relative flex flex-col overflow-hidden bg-surface-canvas"
>
  <!-- Loading indicator: a slim strip, present only while actually loading so
       the viewport otherwise fills the whole card right up to the ribbon. -->
  {#if loading}
    <div
      class="z-20 flex shrink-0 items-center gap-2 border-b border-accent/40 bg-accent/15 px-4 py-1.5 text-xs text-accent"
    >
      <Loader2 class="h-3.5 w-3.5 animate-spin text-accent" />
      <span class="font-medium">{loadingMessage}</span>
    </div>
  {/if}

  <!-- Error Alert Banner -->
  {#if error}
    <div
      class="z-20 flex shrink-0 items-center justify-between border-b border-critical-border bg-critical-bg p-3.5 text-xs text-critical"
    >
      <div class="flex items-center gap-2">
        <AlertCircle class="h-4 w-4 shrink-0 text-critical" />
        <span>{error}</span>
      </div>
      {#if projectId}
        <button
          type="button"
          onclick={() => loadProjectModel(projectId, fileId)}
          class="flex items-center gap-1 rounded-lg bg-critical px-2.5 py-1 text-caption font-medium text-white transition-opacity hover:opacity-90"
        >
          <RefreshCw class="h-3 w-3" />
          <span>Retry</span>
        </button>
      {/if}
    </div>
  {/if}

  <!-- Element-not-found notice: the deep-linked element_guid isn't in the
       loaded model (wrong file, different storey/model, or a stale link) -->
  {#if elementNotFound}
    <div
      class="z-20 flex shrink-0 items-center justify-between border-b border-warning-border bg-warning-bg p-3.5 text-xs text-warning"
    >
      <div class="flex items-center gap-2">
        <AlertCircle class="h-4 w-4 shrink-0 text-warning" />
        <span>Could not find the linked element in this model.</span>
      </div>
      <button
        type="button"
        onclick={() => (elementNotFound = false)}
        class="rounded-lg px-2.5 py-1 text-caption font-medium transition-opacity hover:opacity-90"
      >
        Dismiss
      </button>
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

  <!-- Docked workspace: one collapsible Properties dock (BCF/Spatial/Layers/Drawings) around the 3D viewport -->
  <div class="flex min-h-0 flex-1">
    <div bind:this={viewportHost} class="min-h-0 min-w-0 flex-1 bg-surface-canvas"></div>

    <CollapsiblePanel
      title="Properties"
      icon={ClipboardList}
      side="right"
      id="viewer-right-dock"
      bind:collapsed={rightDockCollapsed}
      resizable
      initialSize={340}
      maxSize={720}
    >
      {#snippet collapsedRail()}
        {#each RIGHT_DOCK_SECTION_ICONS as section (section.id)}
          <button
            type="button"
            onclick={() => openRightSection(section.id)}
            class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg focus-visible:outline-hidden focus-visible:ring-1 focus-visible:ring-accent {openRightSections.includes(
              section.id,
            )
              ? 'bg-surface-selected text-accent'
              : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'}"
            aria-label={section.label}
            title={section.label}
          >
            <section.icon class="h-4 w-4" />
          </button>
        {/each}
      {/snippet}

      <AccordionRoot
        type="multiple"
        bind:value={openRightSections}
        class="w-full rounded-none border-0 divide-y divide-border-subtle bg-transparent"
      >
        <PropertiesSection value="bcf-topics" title="BCF Topics" icon={ClipboardList}>
          <div bind:this={detailsHost} class="min-h-0"></div>
        </PropertiesSection>
        <PropertiesSection value="spatial-tree" title="Spatial Hierarchy" icon={ListTree}>
          <SpatialTreePanel {projectId} />
        </PropertiesSection>
        <PropertiesSection value="query-console" title="Query Console" icon={Terminal}>
          <QueryConsolePanel {projectId} />
        </PropertiesSection>
        <PropertiesSection value="layers" title="Layers" icon={LayoutGrid}>
          <LayersPanel {viewerAPI} />
        </PropertiesSection>
        <PropertiesSection value="drawings" title="Drawings" icon={PenTool}>
          <DrawingsPanel {viewerAPI} bind:sheetBoardHost={drawingsSheetBoardHost} />
        </PropertiesSection>
      </AccordionRoot>
    </CollapsiblePanel>
  </div>
</div>
