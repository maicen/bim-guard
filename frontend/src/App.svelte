<script lang="ts">
  import Navbar from './lib/components/Navbar.svelte';
  import ProjectsView from './routes/ProjectsView.svelte';
  import AnalyzeView from './routes/AnalyzeView.svelte';
  import RulesView from './routes/RulesView.svelte';
  import ViewerView from './routes/ViewerView.svelte';

  let activeTab: 'projects' | 'analyze' | 'rules' | 'viewer' = 'projects';
  let targetProjectId: number | null = null;

  function handleSelectTab(tab: 'projects' | 'analyze' | 'rules' | 'viewer') {
    activeTab = tab;
  }

  function handleSelectProjectForAudit(projectId: number) {
    targetProjectId = projectId;
    activeTab = 'analyze';
  }

  function handleSelectProjectForViewer(projectId: number) {
    targetProjectId = projectId;
    activeTab = 'viewer';
  }
</script>

<div class="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
  <Navbar {activeTab} onSelectTab={handleSelectTab} />

  <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
    {#if activeTab === 'projects'}
      <ProjectsView
        onSelectProjectForAudit={handleSelectProjectForAudit}
        onSelectProjectForViewer={handleSelectProjectForViewer}
      />
    {:else if activeTab === 'analyze'}
      <AnalyzeView initialProjectId={targetProjectId} />
    {:else if activeTab === 'rules'}
      <RulesView />
    {:else if activeTab === 'viewer'}
      <ViewerView initialProjectId={targetProjectId} />
    {/if}
  </main>

  <footer class="border-t border-slate-800/80 py-6 text-center text-xs text-slate-500 bg-slate-950/60">
    <div class="max-w-7xl mx-auto px-4 flex items-center justify-between flex-wrap gap-4">
      <div>
        <span>BIM Guard OpenBIM Compliance Engine</span>
        <span class="mx-2">•</span>
        <span class="text-slate-400">FastAPI Gateway + Svelte SPA Client</span>
      </div>
      <div>
        <span>OpenBIM / IFC 2x3 &amp; IFC4 / BCF 2.1</span>
      </div>
    </div>
  </footer>
</div>

