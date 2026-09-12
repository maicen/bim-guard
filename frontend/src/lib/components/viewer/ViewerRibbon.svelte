<script lang="ts">
  import { onDestroy } from "svelte";
  import { Tooltip as TooltipPrimitive } from "bits-ui";
  import Tooltip from "../Tooltip.svelte";
  import TabStrip from "../TabStrip.svelte";
  import type { TabStripItem } from "../TabStrip.svelte";
  import {
    Box,
    Orbit,
    Footprints,
    LayoutPanelTop,
    Maximize,
    Scissors,
    Grid3x3,
    Expand,
    ArrowLeft,
    Building2,
    Link2,
    Eye,
    EyeOff,
    FilePlus2,
    Download,
    MousePointer2,
    SquarePlus,
    ChevronDown,
    UploadCloud,
  } from "lucide-svelte";
  import type { Model } from "../../types";

  // The IFC viewer engine (static/js/viewer/ifc-viewer.js) is loaded dynamically
  // and typed loosely as `any` throughout IfcViewer.svelte — this ribbon just
  // drives whatever bridge object `initViewer()` returned.
  let {
    viewerAPI,
    fileName = "",
    ifcFiles = [],
    selectedFileId = null,
    onSelectFile,
    onLocalFile,
  }: {
    viewerAPI: any;
    /** Display name for the currently-loaded model, shown when there's only one to pick from. */
    fileName?: string;
    /** The project's attached models, when there's more than one to switch between. */
    ifcFiles?: Model[];
    selectedFileId?: number | null;
    onSelectFile?: (id: number) => void;
    /** Called with a locally-picked IFC file from the "Open Local IFC" button. */
    onLocalFile?: (file: File) => void;
  } = $props();

  let fileInputEl: HTMLInputElement = $state();
  function handleLocalFileUpload(event: Event) {
    const target = event.target as HTMLInputElement;
    const file = target.files?.[0];
    if (file) onLocalFile?.(file);
    target.value = "";
  }

  const TABS: TabStripItem[] = [
    { id: "view", label: "View" },
    { id: "layers", label: "Layers" },
    { id: "drawings", label: "Drawings" },
    { id: "bcf", label: "BCF" },
  ];
  let activeTab = $state("view");

  // Mirrors of engine state, refreshed whenever the engine reports a change.
  // The engine has no reactivity system of its own, so bridge namespaces
  // expose plain getters plus an onChange(cb) subscription (mirroring the
  // pre-existing isolate.onSelectionChange pattern) and this component just
  // re-reads everything on any of those signals.
  let projection = $state("Perspective");
  let navMode = $state("Orbit");
  let gridVisible = $state(true);
  let clippingActive = $state(false);
  let clippingVisible = $state(true);
  let isolateActive = $state(false);
  let canIsolate = $state(false);
  let hasOpenView = $state(false);
  let sectionModeActive = $state(false);
  let activeViewId: string | null = $state(null);
  let plans: { id: string; label: string }[] = $state([]);
  let elevations: { id: string; label: string }[] = $state([]);
  let layers: { name: string; visible: boolean }[] = $state([]);
  let drawingCount = $state(0);
  let selectedTopic: any = $state(null);

  function refreshCamera() {
    if (!viewerAPI) return;
    projection = viewerAPI.camera.getProjection();
    navMode = viewerAPI.camera.getNavMode();
  }
  function refreshGrid() {
    if (!viewerAPI) return;
    gridVisible = viewerAPI.grid.isVisible();
  }
  function refreshClipping() {
    if (!viewerAPI) return;
    clippingActive = viewerAPI.clipping.isModeActive();
    clippingVisible = viewerAPI.clipping.isVisible();
  }
  function refreshIsolate() {
    if (!viewerAPI) return;
    isolateActive = viewerAPI.isolate.isActive();
    canIsolate = viewerAPI.isolate.hasSelection();
  }
  function refreshViews() {
    if (!viewerAPI) return;
    hasOpenView = viewerAPI.views.hasOpenViews();
    sectionModeActive = viewerAPI.views.isSectionModeActive();
    activeViewId = viewerAPI.views.activeViewId();
    plans = viewerAPI.views.listPlans();
    elevations = viewerAPI.views.listElevations();
  }
  function refreshLayers() {
    if (!viewerAPI) return;
    layers = viewerAPI.layers.list();
  }
  function refreshDrawings() {
    if (!viewerAPI) return;
    drawingCount = viewerAPI.drawings.list().length;
  }

  const unsubscribers: Array<() => void> = [];
  $effect(() => {
    if (!viewerAPI) return;
    refreshCamera();
    refreshGrid();
    refreshClipping();
    refreshIsolate();
    refreshViews();
    refreshLayers();
    refreshDrawings();

    unsubscribers.push(viewerAPI.isolate.onSelectionChange(refreshIsolate));
    unsubscribers.push(viewerAPI.views.onChange(refreshViews));
    unsubscribers.push(viewerAPI.layers.onChange(refreshLayers));
    unsubscribers.push(viewerAPI.drawings.onChange(refreshDrawings));
    unsubscribers.push(
      viewerAPI.topics.onSelectionChange((topic: any) => (selectedTopic = topic)),
    );
  });

  onDestroy(() => {
    for (const off of unsubscribers) off();
  });

  function toggleProjection() {
    viewerAPI.camera.setProjection(projection === "Perspective" ? "Orthographic" : "Perspective");
    refreshCamera();
  }
  function setNavMode(mode: string) {
    viewerAPI.camera.setNavMode(mode);
    refreshCamera();
  }
  function fit() {
    viewerAPI.camera.fit();
  }
  function toggleGrid() {
    viewerAPI.grid.toggle(!gridVisible);
    refreshGrid();
  }
  function toggleClippingMode() {
    viewerAPI.clipping.toggleMode(!clippingActive);
    refreshClipping();
  }
  function toggleClippingVisibility() {
    viewerAPI.clipping.toggleVisibility(!clippingVisible);
    refreshClipping();
  }
  function clearClipping() {
    viewerAPI.clipping.clearAll();
    refreshClipping();
  }
  function toggleFullscreen() {
    viewerAPI.fullscreen.toggle();
  }
  function toggleIsolate() {
    viewerAPI.isolate.toggle();
    refreshIsolate();
  }
  function openPlan(event: Event) {
    const id = (event.target as HTMLSelectElement).value;
    if (id) viewerAPI.views.plan(id);
  }
  function openElevation(event: Event) {
    const id = (event.target as HTMLSelectElement).value;
    if (id) viewerAPI.views.elevation(id);
  }
  function toggleSectionMode() {
    if (sectionModeActive) viewerAPI.views.exitSectionMode();
    else viewerAPI.views.enterSectionMode();
    refreshViews();
  }
  function backTo3d() {
    viewerAPI.views.back();
  }
  function saveViewAsViewpoint() {
    viewerAPI.views.saveAsBcfViewpoint();
  }
  function showAllLayers() {
    viewerAPI.layers.showAll();
  }
  function hideAllLayers() {
    viewerAPI.layers.hideAll();
  }
  function createDrawing() {
    viewerAPI.drawings.createFromOpenView();
  }
  function attachDrawingToBcf() {
    viewerAPI.drawings.attachActiveToBcfTopic();
  }
  function createTopic() {
    viewerAPI.topics.openCreateModal();
  }
  function downloadBcf() {
    viewerAPI.topics.download();
  }
</script>

<TooltipPrimitive.Provider delayDuration={300} skipDelayDuration={200}>
<div class="flex shrink-0 flex-col gap-2 border-b border-border-default bg-surface-card px-3 py-2">
  <div class="flex flex-wrap items-center justify-between gap-2">
    <TabStrip tabs={TABS} active={activeTab} onSelect={(id) => (activeTab = id)} ariaLabel="Viewer ribbon" />

    <div class="flex shrink-0 flex-wrap items-center gap-2">
      {#if ifcFiles.length > 1}
        <Tooltip text="Switch which of this project's models the viewport renders">
          {#snippet trigger()}
            <div class="relative">
              <select
                value={selectedFileId}
                onchange={(e) => onSelectFile?.(Number((e.target as HTMLSelectElement).value))}
                class="w-full max-w-[220px] appearance-none rounded-lg border border-border-default bg-surface-overlay py-1.5 pl-3 pr-8 text-xs font-medium text-fg-primary focus:border-accent focus:outline-hidden"
              >
                {#each ifcFiles as file (file.id)}
                  <option value={file.id}>
                    {file.file_name || `Model #${file.id}`} — {file.role}{file.is_primary
                      ? " (primary)"
                      : ""}
                  </option>
                {/each}
              </select>
              <ChevronDown
                class="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-muted"
              />
            </div>
          {/snippet}
        </Tooltip>
      {:else if fileName}
        <span
          class="max-w-[220px] truncate rounded-md border border-accent/40 bg-accent/15 px-2.5 py-1.5 text-xs font-medium text-accent"
          title={fileName}
        >
          Viewing: {fileName}
        </span>
      {/if}

      <Tooltip text="Open a local IFC model directly">
        {#snippet trigger()}
          <button
            type="button"
            onclick={() => fileInputEl?.click()}
            class="flex items-center gap-1.5 rounded-lg border border-border-default bg-surface-overlay px-3 py-1.5 text-xs font-medium text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
          >
            <UploadCloud class="h-3.5 w-3.5" />
            <span>Open Local IFC</span>
          </button>
        {/snippet}
      </Tooltip>
      <input
        type="file"
        accept=".ifc"
        bind:this={fileInputEl}
        onchange={handleLocalFileUpload}
        class="hidden"
      />
    </div>
  </div>

  <div class="flex flex-wrap items-center gap-1">
    {#if activeTab === "view"}
      <Tooltip text={projection === "Perspective" ? "Switch to orthographic projection" : "Switch to perspective projection"}>
        {#snippet trigger()}
          <button
            type="button"
            class="rbn-btn {projection === 'Perspective' ? 'active' : ''}"
            onclick={toggleProjection}
          >
            <Box class="h-4 w-4" /><span>{projection === "Perspective" ? "Persp" : "Ortho"}</span>
          </button>
        {/snippet}
      </Tooltip>
      <div class="rbn-divider"></div>
      <div class="rbn-group">
        <Tooltip text="Orbit navigation — drag to rotate around the model">
          {#snippet trigger()}
            <button
              type="button"
              class="rbn-btn {navMode === 'Orbit' ? 'active' : ''}"
              onclick={() => setNavMode("Orbit")}
            >
              <Orbit class="h-4 w-4" /><span>Orbit</span>
            </button>
          {/snippet}
        </Tooltip>
        <Tooltip text="First-person walk navigation">
          {#snippet trigger()}
            <button
              type="button"
              class="rbn-btn {navMode === 'FirstPerson' ? 'active' : ''}"
              onclick={() => setNavMode("FirstPerson")}
            >
              <Footprints class="h-4 w-4" /><span>Walk</span>
            </button>
          {/snippet}
        </Tooltip>
        <Tooltip text="Locked top-down plan navigation">
          {#snippet trigger()}
            <button
              type="button"
              class="rbn-btn {navMode === 'Plan' ? 'active' : ''}"
              onclick={() => setNavMode("Plan")}
            >
              <LayoutPanelTop class="h-4 w-4" /><span>Plan</span>
            </button>
          {/snippet}
        </Tooltip>
      </div>
      <div class="rbn-divider"></div>
      <Tooltip text="Fit the whole model in view">
        {#snippet trigger()}
          <button type="button" class="rbn-btn" onclick={fit}>
            <Maximize class="h-4 w-4" /><span>Fit</span>
          </button>
        {/snippet}
      </Tooltip>
      <div class="rbn-divider"></div>
      <div class="rbn-group">
        <Tooltip text="Toggle section clipping — click a surface to place a cutting plane">
          {#snippet trigger()}
            <button
              type="button"
              class="rbn-btn {clippingActive ? 'active warning' : ''}"
              onclick={toggleClippingMode}
            >
              <Scissors class="h-4 w-4" /><span>Section</span>
            </button>
          {/snippet}
        </Tooltip>
        <Tooltip text={clippingVisible ? "Hide the clipped-away geometry" : "Show the clipped-away geometry"}>
          {#snippet trigger()}
            <button type="button" class="rbn-btn" onclick={toggleClippingVisibility}>
              {#if clippingVisible}<Eye class="h-4 w-4" />{:else}<EyeOff class="h-4 w-4" />{/if}
            </button>
          {/snippet}
        </Tooltip>
        <Tooltip text="Remove all section clipping planes">
          {#snippet trigger()}
            <button type="button" class="rbn-btn danger" onclick={clearClipping}>Clear</button>
          {/snippet}
        </Tooltip>
      </div>
      <div class="rbn-divider"></div>
      <Tooltip text={gridVisible ? "Hide the ground grid" : "Show the ground grid"}>
        {#snippet trigger()}
          <button type="button" class="rbn-btn {gridVisible ? 'active' : ''}" onclick={toggleGrid}>
            <Grid3x3 class="h-4 w-4" /><span>Grid</span>
          </button>
        {/snippet}
      </Tooltip>
      <Tooltip text="Toggle fullscreen viewport">
        {#snippet trigger()}
          <button type="button" class="rbn-btn" onclick={toggleFullscreen}>
            <Expand class="h-4 w-4" /><span>Full</span>
          </button>
        {/snippet}
      </Tooltip>
      <div class="rbn-divider"></div>
      <div class="rbn-group">
        <Tooltip text="Open a top-down plan view of a storey">
          {#snippet trigger()}
            <button type="button" class="rbn-btn" onclick={() => viewerAPI.views.plan()}>
              <LayoutPanelTop class="h-4 w-4" /><span>Plan</span>
            </button>
          {/snippet}
        </Tooltip>
        {#if plans.length > 1}
          <Tooltip text="Switch between the model's plan views">
            {#snippet trigger()}
              <select class="rbn-select" onchange={openPlan}>
                {#each plans as plan (plan.id)}
                  <option value={plan.id} selected={activeViewId === plan.id}>{plan.label}</option>
                {/each}
              </select>
            {/snippet}
          </Tooltip>
        {/if}
        <Tooltip text="Open an elevation (front/back/left/right) view">
          {#snippet trigger()}
            <button type="button" class="rbn-btn" onclick={() => viewerAPI.views.elevation()}>
              <Building2 class="h-4 w-4" /><span>Elevation</span>
            </button>
          {/snippet}
        </Tooltip>
        {#if elevations.length > 1}
          <Tooltip text="Switch between the model's elevation views">
            {#snippet trigger()}
              <select class="rbn-select" onchange={openElevation}>
                {#each elevations as elevation (elevation.id)}
                  <option value={elevation.id} selected={activeViewId === elevation.id}
                    >{elevation.label}</option
                  >
                {/each}
              </select>
            {/snippet}
          </Tooltip>
        {/if}
        <Tooltip text="Click a surface in the 3D view to create a section view">
          {#snippet trigger()}
            <button
              type="button"
              class="rbn-btn {sectionModeActive ? 'active warning' : ''}"
              onclick={toggleSectionMode}
            >
              <MousePointer2 class="h-4 w-4" /><span>Pick section</span>
            </button>
          {/snippet}
        </Tooltip>
        {#if hasOpenView}
          <Tooltip text="Return to the free 3D view">
            {#snippet trigger()}
              <button type="button" class="rbn-btn" onclick={backTo3d}>
                <ArrowLeft class="h-4 w-4" /><span>Back to 3D</span>
              </button>
            {/snippet}
          </Tooltip>
          <Tooltip text="Save this view as a BCF viewpoint on the selected topic">
            {#snippet trigger()}
              <button type="button" class="rbn-btn" onclick={saveViewAsViewpoint}>
                <Link2 class="h-4 w-4" /><span>Save as BCF viewpoint</span>
              </button>
            {/snippet}
          </Tooltip>
        {/if}
      </div>
      <div class="rbn-divider"></div>
      <Tooltip
        text={canIsolate
          ? isolateActive
            ? "Show hidden elements again"
            : "Isolate the current selection, hiding everything else"
          : "Select an element first to isolate it"}
      >
        {#snippet trigger()}
          <button
            type="button"
            class="rbn-btn {isolateActive ? 'active' : ''}"
            disabled={!canIsolate}
            onclick={toggleIsolate}
          >
            <Building2 class="h-4 w-4" /><span>{isolateActive ? "Isolated" : "Isolate"}</span>
          </button>
        {/snippet}
      </Tooltip>
    {:else if activeTab === "layers"}
      <Tooltip text="Show every category">
        {#snippet trigger()}
          <button type="button" class="rbn-btn" onclick={showAllLayers}>
            <Eye class="h-4 w-4" /><span>Show all</span>
          </button>
        {/snippet}
      </Tooltip>
      <Tooltip text="Hide every category">
        {#snippet trigger()}
          <button type="button" class="rbn-btn" onclick={hideAllLayers}>
            <EyeOff class="h-4 w-4" /><span>Hide all</span>
          </button>
        {/snippet}
      </Tooltip>
      <span class="ml-2 text-xs text-slate-500">{layers.length} categories</span>
    {:else if activeTab === "drawings"}
      <Tooltip text={hasOpenView ? "Create a technical drawing from the open plan/elevation/section view" : "Open a plan/elevation/section view first"}>
        {#snippet trigger()}
          <button
            type="button"
            class="rbn-btn"
            disabled={!hasOpenView}
            onclick={createDrawing}
          >
            <SquarePlus class="h-4 w-4" /><span>New drawing from current view</span>
          </button>
        {/snippet}
      </Tooltip>
      <Tooltip text={selectedTopic ? "Attach the active drawing's DXF to the selected BCF topic" : "Select a BCF topic first"}>
        {#snippet trigger()}
          <button
            type="button"
            class="rbn-btn"
            disabled={drawingCount === 0 || !selectedTopic}
            onclick={attachDrawingToBcf}
          >
            <Link2 class="h-4 w-4" /><span>Attach to BCF topic</span>
          </button>
        {/snippet}
      </Tooltip>
      <span class="ml-2 text-xs text-slate-500">{drawingCount} drawing(s)</span>
    {:else if activeTab === "bcf"}
      <Tooltip text="Create a new BCF topic">
        {#snippet trigger()}
          <button type="button" class="rbn-btn" onclick={createTopic}>
            <FilePlus2 class="h-4 w-4" /><span>Create topic</span>
          </button>
        {/snippet}
      </Tooltip>
      <Tooltip text="Export all BCF topics as a .bcfzip file">
        {#snippet trigger()}
          <button type="button" class="rbn-btn" onclick={downloadBcf}>
            <Download class="h-4 w-4" /><span>Download BCF</span>
          </button>
        {/snippet}
      </Tooltip>
    {/if}
  </div>
</div>
</TooltipPrimitive.Provider>

<style>
  .rbn-group {
    display: flex;
    align-items: center;
    gap: 2px;
  }
  .rbn-divider {
    width: 1px;
    height: 22px;
    background: var(--color-border-default);
    margin: 0 4px;
  }
  .rbn-btn {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 5px 9px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    color: var(--color-fg-secondary);
    cursor: pointer;
    font-size: 11px;
    font-weight: 500;
    white-space: nowrap;
    transition: all 0.15s ease;
  }
  .rbn-btn:hover:not(:disabled) {
    background: var(--color-surface-hover);
    border-color: var(--color-border-interactive);
    color: var(--color-fg-primary);
  }
  .rbn-btn.active {
    background: rgb(var(--accent-rgb) / 0.15);
    border-color: rgb(var(--accent-rgb) / 0.5);
    color: var(--color-accent);
  }
  .rbn-btn.active.warning {
    background: var(--color-warning-bg);
    border-color: var(--color-warning-border);
    color: var(--color-warning);
  }
  .rbn-btn.danger:hover:not(:disabled) {
    background: var(--color-critical-bg);
    border-color: var(--color-critical-border);
    color: var(--color-critical);
  }
  .rbn-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }
  .rbn-select {
    background: var(--color-surface-card);
    border: 1px solid var(--color-border-default);
    border-radius: 8px;
    color: var(--color-fg-primary);
    font-size: 11px;
    padding: 4px 6px;
    max-width: 140px;
  }
</style>
