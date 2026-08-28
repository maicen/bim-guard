<script lang="ts">
  export let projectId: number | null = null;
  export let elementGuid: string | null = null;

  $: viewerSrc = projectId
    ? `/viewer?project_id=${projectId}${elementGuid ? `&element_guid=${elementGuid}` : ''}`
    : '/viewer';
</script>

<div class="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden shadow-2xl relative">
  <div class="h-10 bg-slate-900 border-b border-slate-800 px-4 flex items-center justify-between">
    <div class="flex items-center gap-2">
      <span class="w-2.5 h-2.5 rounded-full bg-red-500/80"></span>
      <span class="w-2.5 h-2.5 rounded-full bg-yellow-500/80"></span>
      <span class="w-2.5 h-2.5 rounded-full bg-emerald-500/80"></span>
      <span class="text-xs font-medium text-slate-400 ml-2">OpenBIM 3D Viewport</span>
    </div>
    {#if projectId}
      <span class="text-xs font-mono text-emerald-400">Project #{projectId}</span>
    {/if}
  </div>

  <iframe
    src={viewerSrc}
    title="IFC 3D Viewer"
    class="w-full h-[700px] border-none bg-slate-950"
    allow="fullscreen"
  ></iframe>
</div>

