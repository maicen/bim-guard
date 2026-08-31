<script lang="ts">
  import { onMount } from 'svelte';
  import Sidebar from './lib/components/Sidebar.svelte';
  import TopHeader from './lib/components/TopHeader.svelte';
  import ProjectWizardModal from './lib/components/ProjectWizardModal.svelte';

  // Routes
  import DashboardView from './routes/DashboardView.svelte';
  import ProjectsView from './routes/ProjectsView.svelte';
  import ViewerView from './routes/ViewerView.svelte';
  import DocumentsView from './routes/DocumentsView.svelte';
  import RuleExtractionView from './routes/RuleExtractionView.svelte';
  import RulesView from './routes/RulesView.svelte';
  import ArchAnalyzeView from './routes/ArchAnalyzeView.svelte';
  import AnalyzeView from './routes/AnalyzeView.svelte';
  import WorkflowView from './routes/WorkflowView.svelte';
  import ReportsView from './routes/ReportsView.svelte';
  import UserManualView from './routes/UserManualView.svelte';
  import ModelingManualView from './routes/ModelingManualView.svelte';
  import RevitSyncView from './routes/RevitSyncView.svelte';
  import SettingsView from './routes/SettingsView.svelte';

  import { dashboardApi, projectsApi } from './lib/api';
  import { viewForAnalysisDomain } from './lib/analysisDomain';
  import { initTheme } from './lib/theme';
  import type { Project } from './lib/types';

  let activeView = 'dashboard';
  let targetProjectId: number | null = null;
  let targetElementGuid: string | null = null;
  let targetBcfArtifactId: number | null = null;
  let selectedProject: Project | null = null;
  let isGlobalWizardOpen = false;

  let dbOk = true;
  let dbBackend = 'SUPABASE';
  let apiOnline = true;

  async function checkHealth() {
    try {
      const stats = await dashboardApi.getStats();
      dbOk = stats.db_ok;
      dbBackend = stats.db_backend || 'SUPABASE';
      apiOnline = true;
    } catch {
      apiOnline = false;
      dbOk = false;
    }
  }

  async function loadProjectDetails(projectId: number) {
    try {
      selectedProject = await projectsApi.get(projectId);
    } catch {
      selectedProject = null;
    }
  }

  onMount(() => {
    initTheme();
    checkHealth();
    dashboardApi.prefetchAll();
    const interval = setInterval(checkHealth, 20000);
    return () => clearInterval(interval);
  });

  function handleSelectView(view: string) {
    // "New Project" is an action, not a destination: it opens the wizard over
    // whatever is on screen. Changing activeView would leave the sidebar
    // highlighting a view that renders nothing once the modal is dismissed.
    if (view === 'newproject') {
      isGlobalWizardOpen = true;
      return;
    }
    activeView = view;
  }

  function handleSelectProjectForAudit(projectId: number) {
    targetProjectId = projectId;
    loadProjectDetails(projectId);
    activeView = 'analyze';
  }

  function handleSelectProjectForViewer(projectId: number, elementGuid?: string, bcfArtifactId?: number) {
    targetProjectId = projectId;
    targetElementGuid = elementGuid || null;
    targetBcfArtifactId = bcfArtifactId || null;
    loadProjectDetails(projectId);
    activeView = 'viewer';
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

<div class="min-h-screen bg-slate-950 text-slate-100 flex font-sans antialiased selection:bg-blue-500/30 selection:text-blue-200 transition-colors duration-200">
  <!-- Apple-Style Sidebar -->
  <Sidebar
    {activeView}
    onSelectView={handleSelectView}
  />

  <!-- Main Content Column -->
  <div class="flex-1 flex flex-col min-w-0">
    <!-- Top Header Bar -->
    <TopHeader
      {activeView}
      {selectedProject}
      {apiOnline}
      {dbOk}
      {dbBackend}
    />

    <!-- Viewport Container -->
    <main class="flex-1 p-6 md:p-8 overflow-y-auto">
      {#if activeView === 'dashboard'}
        <DashboardView
          onSelectProjectForAudit={handleSelectProjectForAudit}
          onSelectProjectForViewer={handleSelectProjectForViewer}
          onOpenWizard={() => (isGlobalWizardOpen = true)}
          onNavigate={handleSelectView}
        />
      {:else if activeView === 'projects'}
        <ProjectsView
          onSelectProjectForAudit={handleSelectProjectForAudit}
          onSelectProjectForViewer={handleSelectProjectForViewer}
        />
      {:else if activeView === 'viewer'}
        <ViewerView
          initialProjectId={targetProjectId}
          initialElementGuid={targetElementGuid}
          initialBcfArtifactId={targetBcfArtifactId}
        />
      {:else if activeView === 'documents'}
        <DocumentsView />
      {:else if activeView === 'extract'}
        <RuleExtractionView />
      {:else if activeView === 'rules'}
        <RulesView />
      {:else if activeView === 'arch'}
        <ArchAnalyzeView
          initialProjectId={targetProjectId}
          onSelectProjectForViewer={handleSelectProjectForViewer}
        />
      {:else if activeView === 'piping'}
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
      {:else if activeView === 'seismic'}
        {#key activeView}
          <AnalyzeView
            activeCategory="seismic"
            initialProjectId={targetProjectId}
            onSelectProjectForViewer={handleSelectProjectForViewer}
          />
        {/key}
      {:else if activeView === 'analyze'}
        <AnalyzeView
          activeCategory="Piping"
          initialProjectId={targetProjectId}
          onSelectProjectForViewer={handleSelectProjectForViewer}
        />
      {:else if activeView === 'workflow'}
        <WorkflowView initialProjectId={targetProjectId} />
      {:else if activeView === 'reports'}
        <ReportsView
          initialProjectId={targetProjectId}
          onSelectProjectForViewer={handleSelectProjectForViewer}
        />
      {:else if activeView === 'user-manual'}
        <UserManualView onNavigate={handleSelectView} />
      {:else if activeView === 'modeling-manual'}
        <ModelingManualView />
      {:else if activeView === 'revit-sync'}
        <RevitSyncView />
      {:else if activeView === 'settings'}
        <SettingsView />
      {/if}
    </main>

    <!-- Clean Footer -->
    <footer class="border-t border-slate-800/80 py-4 px-8 text-xs text-slate-500 bg-slate-950/40 flex items-center justify-between flex-wrap gap-4">
      <div>
        <span>BIM Guard OpenBIM Compliance Engine</span>
      </div>
      <div>
        <span>&copy; {new Date().getFullYear()} BIM Guard</span>
      </div>
    </footer>
  </div>
</div>

<!-- Global Wizard Modal (can be triggered from anywhere) -->
<ProjectWizardModal
  isOpen={isGlobalWizardOpen}
  onClose={() => (isGlobalWizardOpen = false)}
  onProjectCreated={handleProjectCreated}
/>
