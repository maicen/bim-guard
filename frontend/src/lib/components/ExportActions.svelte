<script lang="ts">
  import { analyzeApi } from '../api';

  export let projectId: number;
  export let slug: string = 'corrosion';
</script>

<div class="flex items-center gap-3 flex-wrap">
  <span class="text-xs uppercase tracking-wider font-semibold text-slate-400">Export Findings:</span>
  <a
    href={analyzeApi.getExportUrl(projectId, slug, 'bcf')}
    target="_blank"
    download
    class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-600/20 transition-colors"
  >
    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
    </svg>
    BCF 2.1 (BIM Collab)
  </a>
  <a
    href={analyzeApi.getExportUrl(projectId, slug, 'csv')}
    target="_blank"
    download
    class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-colors"
  >
    CSV Summary
  </a>
  <a
    href={analyzeApi.getExportUrl(projectId, slug, 'json')}
    target="_blank"
    download
    class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-colors"
  >
    JSON Dataset
  </a>
</div>

