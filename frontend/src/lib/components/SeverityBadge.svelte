<script lang="ts">
  import { SEVERITY_STYLES, normalizeSeverity, severityLabel } from "../severity";
  import { cn } from "../utils/cn";

  interface Props {
    severity?: string;
    size?: "xs" | "sm";
    showDot?: boolean;
  }

  let { severity = "low", size = "xs", showDot = false }: Props = $props();

  let style = $derived(SEVERITY_STYLES[normalizeSeverity(severity)]);
  let label = $derived(severityLabel(severity));
</script>

<span
  class={cn(
    "inline-flex items-center gap-1.5 rounded-full border font-semibold uppercase tracking-wider shadow-sm",
    size === "xs" ? "px-2.5 py-0.5 text-micro" : "px-3 py-1 text-xs",
    style.badge,
  )}
>
  {#if showDot}
    <span class={cn("h-1.5 w-1.5 rounded-full", style.dot)}></span>
  {/if}
  <span>{label}</span>
</span>
