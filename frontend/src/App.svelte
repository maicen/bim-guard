<script lang="ts">
  import { onMount } from "svelte";
  import { router, push, replace } from "svelte-spa-router";
  import Sidebar from "./lib/components/Sidebar.svelte";
  import AnalysisDomainTabs from "./lib/components/AnalysisDomainTabs.svelte";
  import type { AnalysisDomainTab } from "./lib/components/AnalysisDomainTabs.svelte";
  import TopHeader from "./lib/components/TopHeader.svelte";
  import ProjectWizardModal from "./lib/components/ProjectWizardModal.svelte";
  import Toaster from "./lib/components/Toaster.svelte";
  import Modal from "./lib/components/Modal.svelte";
  import PipelineProgress from "./lib/components/PipelineProgress.svelte";
  import { Activity } from "lucide-svelte";
  import { toasts } from "./lib/toast.svelte";
  import { pipelineTracker } from "./lib/stores/activePipelines.svelte";

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
  import LoginView from "./routes/LoginView.svelte";

  import { dashboardApi, projectsApi } from "./lib/api";
  import { viewForAnalysisDomain } from "./lib/analysisDomain";
  import { initTheme } from "./lib/theme";
  import { authState } from "./lib/auth.svelte";
  import { isAuthConfigured } from "./lib/supabaseClient";
  import type { Project } from "./lib/types";

  // The URL hash (via svelte-spa-router) is the source of truth for which
  // view is on screen — this is what makes refresh, back/forward, and
  // shareable links work. "/" maps to the dashboard; every other view's id
  // (e.g. "rules", "manual-rule-editor") is used verbatim as its path.
  let activeView = $derived(router.location === "/" ? "dashboard" : router.location.slice(1));
  // "analyze" is a legacy alias for "piping"; both render AnalyzeView.
  let auditDomain: AnalysisDomainTab = $derived(
    activeView === "arch" ? "arch" : activeView === "seismic" ? "seismic" : "piping",
  );
  let queryParams = $derived(new URLSearchParams(router.querystring || ""));
  // Signing in is required once Supabase Auth is actually configured (see
  // supabaseClient.ts) -- everything the app does reads through /api/projects
  // or /api/rules, both of which now require a bearer token. Left ungated
  // when auth isn't configured so a checkout without Supabase set up still
  // runs, per isAuthConfigured's own "non-fatal until configured" contract.
  let authGateBlocking = $derived(
    isAuthConfigured && !authState.loading && !authState.user && activeView !== "login",
  );

  $effect(() => {
    if (authGateBlocking) push("/login");
  });
  // Navigation drawer state; only meaningful below the md breakpoint.
  let isMobileNavOpen = $state(false);
  let targetProjectId: number | null = $state(null);
  let targetElementGuid: string | null = $state(null);
  let targetBcfArtifactId: number | null = $state(null);
  let selectedProject: Project | null = $state(null);
  let isGlobalWizardOpen = $state(false);
  // Clicking the header's running-pipeline badge opens the live tracker in a
  // drawer rather than navigating to a dedicated page — the same information
  // was previously duplicated across an inline panel, a standalone page, and
  // this badge; the badge is now the one entry point into the detail view.
  let pipelineModalProjectId: number | null = $state(null);

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

  // Every navigation that targets a specific project encodes it as
  // ?project_id=...&element_guid=...&bcf_artifact_id=... in the URL's query
  // string (see buildTargetUrl below), so this stays live across refresh,
  // back/forward, and links shared from elsewhere — not just a one-shot read
  // on mount. A previous version of this only handled the initial load of
  // /viewer specifically; this generalizes it to every view.
  $effect(() => {
    const params = queryParams;
    const projectId = Number(params.get("project_id"));
    if (projectId && projectId !== targetProjectId) {
      targetProjectId = projectId;
      loadProjectDetails(projectId);
    }
    targetElementGuid = params.get("element_guid");
    const bcfArtifactId = Number(params.get("bcf_artifact_id"));
    targetBcfArtifactId = bcfArtifactId || null;
  });

  function buildTargetUrl(
    view: string,
    projectId: number,
    elementGuid?: string | null,
    bcfArtifactId?: number | null,
  ): string {
    // A one-shot builder for a URL string, never read reactively, so the
    // plain built-in is correct here.
    // eslint-disable-next-line svelte/prefer-svelte-reactivity
    const params = new URLSearchParams();
    params.set("project_id", String(projectId));
    if (elementGuid) params.set("element_guid", elementGuid);
    if (bcfArtifactId) params.set("bcf_artifact_id", String(bcfArtifactId));
    return `/${view}?${params.toString()}`;
  }

  onMount(() => {
    initTheme();
    checkHealth();
    dashboardApi.prefetchAll();
    // Backward compatibility for the one link shape that predates hash
    // routing: a plain (non-hash) /viewer?... URL, e.g. an old bookmark.
    if (window.location.pathname === "/viewer" && !window.location.hash) {
      replace(`/viewer?${window.location.search.slice(1)}`);
    }
    const interval = setInterval(checkHealth, 20000);
    return () => clearInterval(interval);
  });

  function handleSelectView(view: string) {
    push(`/${view}`);
  }

  // Routes to the audit view matching the project's own domain rather than
  // always landing on Piping — a project created as Arch or Seismic used to
  // open in AnalyzeView regardless, where it wouldn't even appear in the
  // project picker (AnalyzeView only lists Piping/Seismic projects).
  function handleSelectProjectForAudit(projectId: number, analysisType?: string | null) {
    push(buildTargetUrl(viewForAnalysisDomain(analysisType), projectId));
  }

  function handleSelectProjectForViewer(
    projectId: number,
    elementGuid?: string,
    bcfArtifactId?: number,
  ) {
    push(buildTargetUrl("viewer", projectId, elementGuid, bcfArtifactId));
  }

  // The wizard closes itself once the project is saved; this puts the new
  // project on screen in the analysis view for the domain it was created with.
  // Routed through viewForAnalysisDomain rather than compared inline: the
  // wizard sends the canonical 'Arch' / 'Piping' / 'seismic', and matching only
  // the legacy spellings sent every Arch project to the piping view.
  function handleProjectCreated(project: Project) {
    selectedProject = project;
    push(buildTargetUrl(viewForAnalysisDomain(project.analysis_type), project.id));
  }

  // Views that read a project from targetProjectId/query string. Switching
  // context from the header's ProjectSwitcher while on one of these re-runs
  // that same view against the new project; from anywhere else it just
  // updates the context so the next project-scoped view you open has it.
  const PROJECT_SCOPED_VIEWS = new Set([
    "arch",
    "piping",
    "seismic",
    "analyze",
    "reports",
    "viewer",
    "workflow",
  ]);

  function handleSwitchProject(projectId: number) {
    if (PROJECT_SCOPED_VIEWS.has(activeView)) {
      push(buildTargetUrl(activeView, projectId));
    } else {
      targetProjectId = projectId;
      loadProjectDetails(projectId);
    }
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
      onOpenPipeline={(projectId) => (pipelineModalProjectId = projectId)}
      onSwitchProject={handleSwitchProject}
    />

    <!-- Viewport Container -->
    <main id="main-content" tabindex="-1" class="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8">
      <svelte:boundary>
        {#if isAuthConfigured && authState.loading}
          <div class="flex min-h-[50vh] items-center justify-center text-sm text-slate-500">
            Loading your session…
          </div>
        {:else if authGateBlocking}
          <!-- The $effect above is already redirecting to /login; render
               nothing of the protected view in the meantime. -->
        {:else if activeView === "dashboard"}
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
            onOpenWizard={() => (isGlobalWizardOpen = true)}
          />
        {:else if activeView === "viewer"}
          <ViewerView
            initialProjectId={targetProjectId}
            initialElementGuid={targetElementGuid}
            initialBcfArtifactId={targetBcfArtifactId}
          />
        {:else if activeView === "documents"}
          <DocumentsView onNavigateToManualRuleEditor={() => push("/manual-rule-editor")} />
        {:else if activeView === "extract"}
          <RuleExtractionView />
        {:else if activeView === "rules"}
          <RulesView />
        {:else if activeView === "manual-rule-editor"}
          <ManualRuleEditorView onBack={() => push("/rules")} />
        {:else if activeView === "arch" || activeView === "piping" || activeView === "seismic" || activeView === "analyze"}
          <!-- One "Compliance Audit" destination covers all three domains; the
             tab strip is how you switch between them without a trip back to
             the sidebar. "analyze" is a legacy alias for "piping". -->
          <div class="space-y-5">
            <AnalysisDomainTabs active={auditDomain} onSelect={(domain) => push(`/${domain}`)} />
            {#if activeView === "arch"}
              <ArchAnalyzeView initialProjectId={targetProjectId} />
            {:else}
              <!-- Keyed so moving between PIPING and SEISMIC remounts the view:
                 both routes share AnalyzeView, and without this the previous
                 route's results and filters survive the switch. -->
              {#key activeView}
                <AnalyzeView
                  activeCategory={activeView === "seismic" ? "seismic" : "Piping"}
                  initialProjectId={targetProjectId}
                  onSelectProjectForViewer={handleSelectProjectForViewer}
                />
              {/key}
            {/if}
          </div>
        {:else if activeView === "workflow"}
          <WorkflowView initialProjectId={targetProjectId} onNavigate={handleSelectView} />
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
        {:else if activeView === "login"}
          <LoginView />
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

<!-- Live pipeline detail, opened from the header's running-pipeline badge -->
<Modal
  isOpen={pipelineModalProjectId !== null}
  title="Live Pipeline"
  subtitle={pipelineTracker.tracked.find((t) => t.projectId === pipelineModalProjectId)
    ?.projectName}
  icon={Activity}
  maxWidth="max-w-3xl"
  onClose={() => (pipelineModalProjectId = null)}
>
  {#if pipelineModalProjectId !== null}
    <PipelineProgress projectId={pipelineModalProjectId} />
  {/if}
</Modal>
