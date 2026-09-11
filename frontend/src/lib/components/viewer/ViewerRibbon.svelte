<script lang="ts">
  import { onDestroy } from "svelte";
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
  } from "lucide-svelte";

  // The IFC viewer engine (static/js/viewer/ifc-viewer.js) is loaded dynamically
  // and typed loosely as `any` throughout IfcViewer.svelte — this ribbon just
  // drives whatever bridge object `initViewer()` returned.
  let { viewerAPI }: { viewerAPI: any } = $props();

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

<div class="flex shrink-0 flex-col gap-2 border-b border-slate-800 bg-slate-900/60 px-3 py-2">
  <TabStrip tabs={TABS} active={activeTab} onSelect={(id) => (activeTab = id)} ariaLabel="Viewer ribbon" />

  <div class="flex flex-wrap items-center gap-1">
    {#if activeTab === "view"}
      <div class="rbn-group" title="Camera projection">
        <button
          type="button"
          class="rbn-btn {projection === 'Perspective' ? 'active' : ''}"
          onclick={toggleProjection}
        >
          <Box class="h-4 w-4" /><span>{projection === "Perspective" ? "Persp" : "Ortho"}</span>
        </button>
      </div>
      <div class="rbn-divider"></div>
      <div class="rbn-group" title="Navigation mode">
        <button
          type="button"
          class="rbn-btn {navMode === 'Orbit' ? 'active' : ''}"
          onclick={() => setNavMode("Orbit")}
        >
          <Orbit class="h-4 w-4" /><span>Orbit</span>
        </button>
        <button
          type="button"
          class="rbn-btn {navMode === 'FirstPerson' ? 'active' : ''}"
          onclick={() => setNavMode("FirstPerson")}
        >
          <Footprints class="h-4 w-4" /><span>Walk</span>
        </button>
        <button
          type="button"
          class="rbn-btn {navMode === 'Plan' ? 'active' : ''}"
          onclick={() => setNavMode("Plan")}
        >
          <LayoutPanelTop class="h-4 w-4" /><span>Plan</span>
        </button>
      </div>
      <div class="rbn-divider"></div>
      <button type="button" class="rbn-btn" onclick={fit}>
        <Maximize class="h-4 w-4" /><span>Fit</span>
      </button>
      <div class="rbn-divider"></div>
      <div class="rbn-group" title="Section clipping planes">
        <button
          type="button"
          class="rbn-btn {clippingActive ? 'active warning' : ''}"
          onclick={toggleClippingMode}
        >
          <Scissors class="h-4 w-4" /><span>Section</span>
        </button>
        <button type="button" class="rbn-btn" onclick={toggleClippingVisibility}>
          {#if clippingVisible}<Eye class="h-4 w-4" />{:else}<EyeOff class="h-4 w-4" />{/if}
        </button>
        <button type="button" class="rbn-btn danger" onclick={clearClipping}>Clear</button>
      </div>
      <div class="rbn-divider"></div>
      <button type="button" class="rbn-btn {gridVisible ? 'active' : ''}" onclick={toggleGrid}>
        <Grid3x3 class="h-4 w-4" /><span>Grid</span>
      </button>
      <button type="button" class="rbn-btn" onclick={toggleFullscreen}>
        <Expand class="h-4 w-4" /><span>Full</span>
      </button>
      <div class="rbn-divider"></div>
      <div class="rbn-group" title="Plan / elevation / section views">
        <button type="button" class="rbn-btn" onclick={() => viewerAPI.views.plan()}>
          <LayoutPanelTop class="h-4 w-4" /><span>Plan</span>
        </button>
        {#if plans.length > 1}
          <select class="rbn-select" onchange={openPlan}>
            {#each plans as plan (plan.id)}
              <option value={plan.id} selected={activeViewId === plan.id}>{plan.label}</option>
            {/each}
          </select>
        {/if}
        <button type="button" class="rbn-btn" onclick={() => viewerAPI.views.elevation()}>
          <Building2 class="h-4 w-4" /><span>Elevation</span>
        </button>
        {#if elevations.length > 1}
          <select class="rbn-select" onchange={openElevation}>
            {#each elevations as elevation (elevation.id)}
              <option value={elevation.id} selected={activeViewId === elevation.id}
                >{elevation.label}</option
              >
            {/each}
          </select>
        {/if}
        <button
          type="button"
          class="rbn-btn {sectionModeActive ? 'active warning' : ''}"
          onclick={toggleSectionMode}
          title="Click a surface in the 3D view to create a section view"
        >
          <MousePointer2 class="h-4 w-4" /><span>Pick section</span>
        </button>
        {#if hasOpenView}
          <button type="button" class="rbn-btn" onclick={backTo3d}>
            <ArrowLeft class="h-4 w-4" /><span>Back to 3D</span>
          </button>
          <button type="button" class="rbn-btn" onclick={saveViewAsViewpoint}>
            <Link2 class="h-4 w-4" /><span>Save as BCF viewpoint</span>
          </button>
        {/if}
      </div>
      <div class="rbn-divider"></div>
      <button
        type="button"
        class="rbn-btn {isolateActive ? 'active' : ''}"
        disabled={!canIsolate}
        onclick={toggleIsolate}
      >
        <Building2 class="h-4 w-4" /><span>{isolateActive ? "Isolated" : "Isolate"}</span>
      </button>
    {:else if activeTab === "layers"}
      <button type="button" class="rbn-btn" onclick={showAllLayers}>
        <Eye class="h-4 w-4" /><span>Show all</span>
      </button>
      <button type="button" class="rbn-btn" onclick={hideAllLayers}>
        <EyeOff class="h-4 w-4" /><span>Hide all</span>
      </button>
      <span class="ml-2 text-xs text-slate-500">{layers.length} categories</span>
    {:else if activeTab === "drawings"}
      <button
        type="button"
        class="rbn-btn"
        disabled={!hasOpenView}
        onclick={createDrawing}
        title={hasOpenView ? "" : "Open a plan/elevation/section view first"}
      >
        <SquarePlus class="h-4 w-4" /><span>New drawing from current view</span>
      </button>
      <button
        type="button"
        class="rbn-btn"
        disabled={drawingCount === 0 || !selectedTopic}
        onclick={attachDrawingToBcf}
        title={selectedTopic ? "" : "Select a BCF topic first"}
      >
        <Link2 class="h-4 w-4" /><span>Attach to BCF topic</span>
      </button>
      <span class="ml-2 text-xs text-slate-500">{drawingCount} drawing(s)</span>
    {:else if activeTab === "bcf"}
      <button type="button" class="rbn-btn" onclick={createTopic}>
        <FilePlus2 class="h-4 w-4" /><span>Create topic</span>
      </button>
      <button type="button" class="rbn-btn" onclick={downloadBcf}>
        <Download class="h-4 w-4" /><span>Download BCF</span>
      </button>
    {/if}
  </div>
</div>

<style>
  .rbn-group {
    display: flex;
    align-items: center;
    gap: 2px;
  }
  .rbn-divider {
    width: 1px;
    height: 22px;
    background: rgba(99, 102, 241, 0.2);
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
    color: rgb(148 163 184 / 0.9);
    cursor: pointer;
    font-size: 11px;
    font-weight: 500;
    white-space: nowrap;
    transition: all 0.15s ease;
  }
  .rbn-btn:hover:not(:disabled) {
    background: rgba(99, 102, 241, 0.15);
    border-color: rgba(99, 102, 241, 0.3);
    color: #e2e8f0;
  }
  .rbn-btn.active {
    background: rgba(99, 102, 241, 0.25);
    border-color: rgba(99, 102, 241, 0.6);
    color: #a5b4fc;
  }
  .rbn-btn.active.warning {
    background: rgba(245, 158, 11, 0.2);
    border-color: rgba(245, 158, 11, 0.5);
    color: #fcd34d;
  }
  .rbn-btn.danger:hover:not(:disabled) {
    background: rgba(239, 68, 68, 0.15);
    border-color: rgba(239, 68, 68, 0.4);
    color: #fca5a5;
  }
  .rbn-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }
  .rbn-select {
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid rgba(99, 102, 241, 0.25);
    border-radius: 8px;
    color: #e2e8f0;
    font-size: 11px;
    padding: 4px 6px;
    max-width: 140px;
  }
</style>
