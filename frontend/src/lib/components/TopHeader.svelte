<script lang="ts">
  import { Plus, ExternalLink, Activity } from 'lucide-svelte';
  import type { Project } from '../types';

  export let activeView: string;
  export let selectedProject: Project | null = null;
  export let onOpenWizard: () => void;
  export let apiOnline: boolean = true;

  const TITLES: Record<string, { section: string; title: string }> = {
    dashboard: { section: 'Platform', title: 'Compliance Dashboard' },
    projects: { section: 'Platform', title: 'Project Registry' },
    viewer: { section: 'Platform', title: '3D OpenBIM Viewer' },
    documents: { section: 'Library', title: 'Document Specifications' },
    extract: { section: 'Library', title: 'Rule Extraction Studio' },
    rules: { section: 'Library', title: 'Rules Catalog' },
    arch: { section: 'Analysis', title: 'ARCH Compliance Audit' },
    analyze: { section: 'Analysis', title: 'MEP Piping & Seismic Audit' },
    workflow: { section: 'Analysis', title: 'Live Pipeline Tracker' },
    reports: { section: 'Analysis', title: 'Compliance Reports & Exports' },
    'user-manual': { section: 'Manuals', title: 'User Workflow Manual' },
    'modeling-manual': { section: 'Manuals', title: '3D Modeling Reference' },
    settings: { section: 'System', title: 'Application Settings' },
  };

  $: headerInfo = TITLES[activeView] || { section: 'BIM Guard', title: activeView };
</script>

<header class="h-16 border-b border-slate-800 bg-slate-950/60 apple-blur sticky top-0 z-30 px-6 flex items-center justify-between">
  <!-- Breadcrumb -->
  <div class="flex items-center gap-2 text-sm">
    <span class="text-slate-500 font-medium">{headerInfo.section}</span>
    <span class="text-slate-600">/</span>
    <span class="font-semibold text-slate-100">{headerInfo.title}</span>

    {#if selectedProject}
      <span class="ml-2 inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
        Project: {selectedProject.name}
      </span>
    {/if}
  </div>

  <!-- Actions & Status -->
  <div class="flex items-center gap-3">
    <!-- Health status -->
    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border {apiOnline ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60' : 'bg-rose-950/40 text-rose-400 border-rose-800/60'}">
      <span class="w-1.5 h-1.5 rounded-full {apiOnline ? 'bg-emerald-400' : 'bg-rose-400'}"></span>
      {apiOnline ? 'FastAPI Gateway Active' : 'Gateway Offline'}
    </span>

    <a
      href="/api/docs"
      target="_blank"
      rel="noopener noreferrer"
      class="text-xs text-slate-400 hover:text-white px-2.5 py-1 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-900/60 flex items-center gap-1 transition-colors"
      title="Open Swagger OpenAPI Documentation"
    >
      <span>API Docs</span>
      <ExternalLink class="w-3 h-3" />
    </a>

    <!-- New Check CTA Button -->
    <button
      type="button"
      on:click={onOpenWizard}
      class="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02]"
    >
      <Plus class="w-3.5 h-3.5" />
      <span>New Check</span>
    </button>
  </div>
</header>

