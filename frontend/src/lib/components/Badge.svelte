<script lang="ts">
  import type { Snippet } from "svelte";
  import { SEVERITY_STYLES, normalizeSeverity } from "../severity";
  import { cn } from "../utils/cn";

  type Variant =
    | "critical"
    | "high"
    | "medium"
    | "low"
    | "data_quality"
    | "complete"
    | "running"
    | "pending"
    | "failed"
    | "neutral";

  let {
    variant = "neutral",
    size = "sm",
    children,
  }: {
    variant?: Variant;
    size?: "sm" | "md";
    children?: Snippet;
  } = $props();

  // Pipeline-status variants are local; the severity bands come from the shared
  // table so this and <SeverityBadge> cannot drift apart again.
  const STATUS_STYLES: Record<string, string> = {
    complete: "bg-success-bg border-success-border text-success",
    running: "bg-accent/15 border-accent/40 text-accent animate-pulse",
    pending: "bg-surface-card border-border-default text-fg-muted",
    failed: "bg-critical-bg border-critical-border text-critical",
  };

  let normalizedKey = $derived((variant || "").toLowerCase().replace("-", "_"));
  let cls = $derived(
    STATUS_STYLES[normalizedKey] ?? SEVERITY_STYLES[normalizeSeverity(normalizedKey)].badge,
  );
</script>

<span
  class={cn(
    "inline-flex items-center gap-1 rounded-md border font-semibold uppercase tracking-wide",
    size === "sm" ? "px-2 py-0.5 text-micro" : "px-2.5 py-1 text-xs",
    cls,
  )}
>
  {@render children?.()}
</span>
