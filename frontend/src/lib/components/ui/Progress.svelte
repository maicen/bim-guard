<script lang="ts" module>
  import { Progress as ProgressPrimitive } from "bits-ui";

  export const ProgressRoot = ProgressPrimitive.Root;
</script>

<script lang="ts">
  import { cn } from "../../utils/cn";

  interface Props {
    value?: number | null;
    max?: number;
    min?: number;
    showLabel?: boolean;
    indicatorClass?: string;
    class?: string;
  }

  let {
    value = 0,
    max = 100,
    min = 0,
    showLabel = false,
    indicatorClass = "bg-accent",
    class: className,
  }: Props = $props();

  let percentage = $derived(
    value === null ? null : Math.min(100, Math.max(0, (((value ?? 0) - min) / (max - min)) * 100)),
  );
</script>

<div class={cn("flex w-full items-center gap-3", className)}>
  <ProgressPrimitive.Root
    {value}
    {max}
    {min}
    class="relative h-2 w-full overflow-hidden rounded-full border border-border-subtle bg-surface-canvas"
  >
    {#if percentage === null}
      <div class={cn("h-full w-1/3 animate-pulse rounded-full", indicatorClass)}></div>
    {:else}
      <div
        class={cn("h-full rounded-full transition-all duration-300", indicatorClass)}
        style="width: {percentage}%"
      ></div>
    {/if}
  </ProgressPrimitive.Root>

  {#if showLabel && percentage !== null}
    <span class="font-mono text-xs font-semibold text-fg-primary">
      {Math.round(percentage)}%
    </span>
  {/if}
</div>
