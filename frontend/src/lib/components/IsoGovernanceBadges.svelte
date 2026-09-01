<script lang="ts">
  export let suitability: string = "S0";
  export let revision: string = "P01.01";
  export let cdeState: string = "WIP";
  export let size: "xs" | "sm" = "xs";

  function getCdeColor(state: string) {
    switch ((state || "").toUpperCase()) {
      case "PUBLISHED":
        return "text-emerald-400 border-emerald-800/60 bg-emerald-950/40";
      case "SHARED":
        return "text-blue-400 border-blue-800/60 bg-blue-950/40";
      case "ARCHIVED":
        return "text-slate-400 border-slate-700/60 bg-slate-900/60";
      default:
        return "text-amber-400 border-amber-800/60 bg-amber-950/40";
    }
  }
</script>

<div class="flex items-center gap-1.5 font-mono {size === 'xs' ? 'text-[10px]' : 'text-xs'}">
  <span
    class="px-1.5 py-0.5 rounded bg-slate-800 text-amber-400 font-semibold border border-slate-700/60 shadow-sm"
    title="ISO 19650 Suitability Status: {suitability || 'S0'}"
  >
    {suitability || "S0"}
  </span>
  <span
    class="px-1.5 py-0.5 rounded bg-slate-800 text-blue-400 font-semibold border border-slate-700/60 shadow-sm"
    title="ISO 19650 Revision Code: {revision || 'P01.01'}"
  >
    {revision || "P01.01"}
  </span>
  <span
    class="px-1.5 py-0.5 rounded font-semibold border shadow-sm {getCdeColor(cdeState)}"
    title="CDE Workflow State: {cdeState || 'WIP'}"
  >
    {cdeState || "WIP"}
  </span>
</div>
