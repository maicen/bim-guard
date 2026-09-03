<script lang="ts">
  import { onMount, tick } from "svelte";
  import Sidebar from "./lib/components/Sidebar.svelte";
  import TopHeader from "./lib/components/TopHeader.svelte";
  import ProjectWizardModal from "./lib/components/ProjectWizardModal.svelte";
  import Toaster from "./lib/components/Toaster.svelte";
  import { toasts } from "./lib/toast.svelte";

  // Routes
  import DashboardView from "./routes/DashboardView.svelte";
  import ProjectsView from "./routes/ProjectsView.svelte";
  import ViewerView from "./routes/ViewerView.svelte";
  import DocumentsView from "./routes/DocumentsView.svelte";
  import RuleExtractionView from "./routes/RuleExtractionView.svelte";
  import RulesView from "./routes/RulesView.svelte";
  import ManualRuleEditorView from "./routes/ManualRuleEditorView.svelte";
  import ArchAnalyzeView from "./routes/ArchAnalyzeView.svelte";
  import AnalyzeView from "./routes/AnalyzeView.svelte";
  import WorkflowView from "./routes/WorkflowView.svelte";
  import ReportsView from "./routes/ReportsView.svelte";
  import UserManualView from "./routes/UserManualView.svelte";
  import ModelingManualView from "./routes/ModelingManualView.svelte";
  import BsddWikiView from "./routes/BsddWikiView.svelte";
  import RevitSyncView from "./routes/RevitSyncView.svelte";
  import IfcExportSettingView from "./routes/IfcExportSettingView.svelte";
  import SettingsView from "./routes/SettingsView.svelte";

  import { dashboardApi, projectsApi } from "./lib/api";
  import { viewForAnalysisDomain } from "./lib/analysisDomain";
  import { initTheme } from "./lib/theme";
  import type { Project } from "./lib/types";

  let activeView = $state("dashboard");
  // Navigation drawer state; only meaningful below the md breakpoint.
  let isMobileNavOpen = $state(false);
  let targetProjectId: number | null = $state(null);
  let targetElementGuid: string | null = $state(null);
  let targetBcfArtifactId: number | null = $state(null);
  let selectedProject: Project | null = $state(null);
  let isGlobalWizardOpen = $state(false);
  let documentsViewRef: DocumentsView = $state();

  let dbOk = $state(true);
  let dbBackend = $state("SUPABASE");
  let apiOnline = $state(true);

  async function checkHealth() {
    try {
      const stats = await dashboardApi.getStats();
      dbOk = stats.db_ok;
      dbBackend = stats.db_backend || "SUPABASE";
      apiOnline = true;
    } catch {
      // Deliberately quiet: the header's gateway/database chips are this
      // check's UI, and it re-runs every 20s. A toast per poll would be noise.
      apiOnline = false;
      dbOk = false;
    }
  }

  async function loadProjectDetails(projectId: number) {
    try {
      selectedProject = await projectsApi.get(projectId);
    } catch (err) {
      selectedProject = null;
      toasts.fromError(err, "Could not load the selected project.");
    }
  }

  // The app is a client-state SPA with no URL-driven router, but the backend
  // still hands out real links (e.g. "View in 3D" on analysis/report pages)
  // built as /viewer?project_id=...&bcf_artifact_id=...&element_guid=....
  // Without this, landing on one of those just shows the default Dashboard —
  // the query string was never read. Only /viewer is handled here since it's
  // the one path server-generated links actually point at today.
  function applyDeepLinkFromLocation() {
    if (window.location.pathname !== "/viewer") return;
    const params = new URLSearchParams(window.location.search);
    const projectId = Number(params.get("project_id"));
    if (!projectId) return;
    targetProjectId = projectId;
    targetElementGuid = params.get("element_guid");
    const bcfArtifactId = Number(params.get("bcf_artifact_id"));
    targetBcfArtifactId = bcfArtifactId || null;
    loadProjectDetails(projectId);
    activeView = "viewer";
  }

  onMount(() => {
    initTheme();
    checkHealth();
    dashboardApi.prefetchAll();
    applyDeepLinkFromLocation();
    const interval = setInterval(checkHealth, 20000);
    return () => clearInterval(interval);
  });

  async function handleSelectView(view: string) {
    // "New Project" is an action, not a destination: it opens the wizard over
    // whatever is on screen. Changing activeView would leave the sidebar
    // highlighting a view that renders nothing once the modal is dismissed.
    if (view === "newproject") {
      isGlobalWizardOpen = true;
      return;
    }
    // "New Rule Document Upload" mirrors that: land on the Documents view,
    // then open its upload modal once it's actually mounted.
    if (view === "newdocument") {
      activeView = "documents";
      await tick();
      documentsViewRef?.openUploadModal();
      return;
    }
    activeView = view;
  }

  function handleSelectProjectForAudit(projectId: number) {
    targetProjectId = projectId;
    loadProjectDetails(projectId);
    activeView = "analyze";
  }

  function handleSelectProjectForViewer(
    projectId: number,
    elementGuid?: string,
    bcfArtifactId?: number,
  ) {
    targetProjectId = projectId;
    targetElementGuid = elementGuid || null;
    targetBcfArtifactId = bcfArtifactId || null;
    loadProjectDetails(projectId);
    activeView = "viewer";
  }

  // The wizard closes itself once the project is saved; this puts the new
  // project on screen in the analysis view for the domain it was created with.
  // Routed through viewForAnalysisDomain rather than compared inline: the
  // wizard sends the canonical 'Arch' / 'Piping' / 'seismic', and matching only
  // the legacy spellings sent every Arch project to the piping view.
  function handleProjectCreated(project: Project) {
    targetProjectId = project.id;
    selectedProject = project;
    activeView = viewForAnalysisDomain(project.analysis_type);
  }
</script>

<a
  href="#main-content"
  class="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[200] focus:rounded-xl focus:bg-accent focus:px-4 focus:py-2 focus:text-xs focus:font-semibold focus:text-white"
>
  Skip to main content
</a>

<div
  class="flex min-h-screen bg-slate-950 font-sans text-slate-100 antialiased transition-colors duration-200 selection:bg-blue-500/30 selection:text-blue-200"
>
  <!-- Apple-Style Sidebar -->
  <Sidebar
    {activeView}
    onSelectView={handleSelectView}
    mobileOpen={isMobileNavOpen}
    onCloseMobile={() => (isMobileNavOpen = false)}
  />

  <!-- Main Content Column -->
  <div class="flex min-w-0 flex-1 flex-col">
    <!-- Top Header Bar -->
    <TopHeader
      {activeView}
      {selectedProject}
      {apiOnline}
      {dbOk}
      {dbBackend}
      onOpenMobileNav={() => (isMobileNavOpen = true)}
    />

    <!-- Viewport Container -->
    <main id="main-content" tabindex="-1" class="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8">
      <svelte:boundary>
        {#if activeView === "dashboard"}
          <DashboardView
            onSelectProjectForAudit={handleSelectProjectForAudit}
            onSelectProjectForViewer={handleSelectProjectForViewer}
            onOpenWizard={() => (isGlobalWizardOpen = true)}
            onNavigate={handleSelectView}
          />
        {:else if activeView === "projects"}
          <ProjectsView
            onSelectProjectForAudit={handleSelectProjectForAudit}
            onSelectProjectForViewer={handleSelectProjectForViewer}
          />
        {:else if activeView === "viewer"}
          <ViewerView
            initialProjectId={targetProjectId}
            initialElementGuid={targetElementGuid}
            initialBcfArtifactId={targetBcfArtifactId}
          />
        {:else if activeView === "documents"}
          <DocumentsView
            bind:this={documentsViewRef}
            onNavigateToManualRuleEditor={() => (activeView = "manual-rule-editor")}
          />
        {:else if activeView === "extract"}
          <RuleExtractionView />
        {:else if activeView === "rules"}
          <RulesView />
        {:else if activeView === "manual-rule-editor"}
          <ManualRuleEditorView onBack={() => (activeView = "rules")} />
        {:else if activeView === "arch"}
          <ArchAnalyzeView initialProjectId={targetProjectId} />
        {:else if activeView === "piping"}
          <!-- Keyed so moving between PIPING and SEISMIC remounts the view:
             both routes share AnalyzeView, and without this the previous
             route's results and filters survive the switch. -->
          {#key activeView}
            <AnalyzeView
              activeCategory="Piping"
              initialProjectId={targetProjectId}
              onSelectProjectForViewer={handleSelectProjectForViewer}
            />
          {/key}
        {:else if activeView === "seismic"}
          {#key activeView}
            <AnalyzeView
              activeCategory="seismic"
              initialProjectId={targetProjectId}
              onSelectProjectForViewer={handleSelectProjectForViewer}
            />
          {/key}
        {:else if activeView === "analyze"}
          <AnalyzeView
            activeCategory="Piping"
            initialProjectId={targetProjectId}
            onSelectProjectForViewer={handleSelectProjectForViewer}
          />
        {:else if activeView === "workflow"}
          <WorkflowView initialProjectId={targetProjectId} />
        {:else if activeView === "reports"}
          <ReportsView
            initialProjectId={targetProjectId}
            onSelectProjectForViewer={handleSelectProjectForViewer}
          />
        {:else if activeView === "user-manual"}
          <UserManualView onNavigate={handleSelectView} />
        {:else if activeView === "modeling-manual"}
          <ModelingManualView />
        {:else if activeView === "bsdd-wiki"}
          <BsddWikiView />
        {:else if activeView === "revit-sync"}
          <RevitSyncView />
        {:else if activeView === "ifc-export-setting"}
          <IfcExportSettingView />
        {:else if activeView === "settings"}
          <SettingsView />
        {/if}
        {#snippet failed(error, reset)}
          <div
            role="alert"
            class="mx-auto mt-10 max-w-lg space-y-4 rounded-xl border border-rose-800/80 bg-rose-950/40 p-6 text-center"
          >
            <h2 class="text-base font-bold text-rose-200">This view failed to render</h2>
            <p class="text-xs leading-relaxed text-rose-300/90">
              {error instanceof Error ? error.message : String(error)}
            </p>
            <button
              type="button"
              onclick={reset}
              class="rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white hover:bg-accent-hover"
            >
              Try again
            </button>
          </div>
        {/snippet}
      </svelte:boundary>
    </main>

    <!-- Clean Footer -->
    <footer
      class="flex flex-wrap items-center justify-between gap-4 border-t border-slate-800/80 bg-slate-950/40 px-8 py-4 text-xs text-slate-500"
    >
      <div>
        <span>BIM Guard OpenBIM Compliance Engine</span>
      </div>
      <div>
        <span>&copy; {new Date().getFullYear()} BIM Guard</span>
      </div>
    </footer>
  </div>
</div>

<Toaster />

<!-- Global Wizard Modal (can be triggered from anywhere) -->
<ProjectWizardModal
  isOpen={isGlobalWizardOpen}
  onClose={() => (isGlobalWizardOpen = false)}
  onProjectCreated={handleProjectCreated}
/>
