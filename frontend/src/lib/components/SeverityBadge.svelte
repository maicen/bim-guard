<script lang="ts">
  export let severity: string = "low";
  export let size: "xs" | "sm" = "xs";
  export let showDot: boolean = false;

  $: normalized = (severity || "").toLowerCase();

  function getBadgeClasses(sev: string): { bg: string; dot: string } {
    switch (sev) {
      case "critical":
      case "fail":
        return {
          bg: "bg-rose-950/70 text-rose-300 border-rose-800/80 shadow-rose-950/20",
          dot: "bg-rose-400",
        };
      case "high":
        return {
          bg: "bg-amber-950/70 text-amber-300 border-amber-800/80 shadow-amber-950/20",
          dot: "bg-amber-400",
        };
      case "medium":
      case "missing":
      case "missing_data":
        return {
          bg: "bg-yellow-950/70 text-yellow-300 border-yellow-800/80 shadow-yellow-950/20",
          dot: "bg-yellow-400",
        };
      case "low":
      case "pass":
        return {
          bg: "bg-emerald-950/70 text-emerald-300 border-emerald-800/80 shadow-emerald-950/20",
          dot: "bg-emerald-400",
        };
      case "data_quality":
      case "data quality":
        return {
          bg: "bg-indigo-950/70 text-indigo-300 border-indigo-800/80 shadow-indigo-950/20",
          dot: "bg-indigo-400",
        };
      default:
        return {
          bg: "bg-slate-800 text-slate-300 border-slate-700 shadow-slate-900/20",
          dot: "bg-slate-400",
        };
    }
  }

  $: classes = getBadgeClasses(normalized);
  $: label =
    normalized === "data_quality" || normalized === "data quality"
      ? "Data Quality"
      : severity;
</script>

<span
  class="inline-flex items-center gap-1.5 rounded-full font-semibold uppercase tracking-wider border shadow-sm {size === 'xs' ? 'px-2.5 py-0.5 text-[10px]' : 'px-3 py-1 text-xs'} {classes.bg}"
>
  {#if showDot}
    <span class="w-1.5 h-1.5 rounded-full {classes.dot}"></span>
  {/if}
  <span>{label}</span>
</span>
