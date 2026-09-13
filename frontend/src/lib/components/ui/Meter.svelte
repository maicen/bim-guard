<script lang="ts" module>
  import { Meter as MeterPrimitive } from "bits-ui";

  export const MeterRoot = MeterPrimitive.Root;
</script>

<script lang="ts">
  import { cn } from "../../utils/cn";

  interface Props {
    value?: number;
    max?: number;
    min?: number;
    low?: number;
    high?: number;
    optimum?: number;
    label?: string;
    class?: string;
  }

  let {
    value = 0,
    max = 100,
    min = 0,
    low,
    high,
    optimum,
    label,
    class: className,
  }: Props = $props();

  let percentage = $derived(Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100)));

  let colorIntent = $derived.by(() => {
    if (high !== undefined && low !== undefined) {
      if (value >= high) return "bg-success";
      if (value >= low) return "bg-warning";
      return "bg-critical";
    }
    return "bg-accent";
  });
</script>

<div class={cn("flex w-full flex-col gap-1.5", className)}>
  {#if label}
    <div class="flex items-center justify-between text-caption font-medium text-fg-secondary">
      <span>{label}</span>
      <span class="font-mono text-fg-primary">{value} / {max}</span>
    </div>
  {/if}

  <MeterPrimitive.Root
    {value}
    {max}
    {min}
    class="relative h-2 w-full overflow-hidden rounded-full border border-border-subtle bg-surface-canvas"
  >
    <div
      class={cn("h-full rounded-full transition-all duration-300", colorIntent)}
      style="width: {percentage}%"
    ></div>
  </MeterPrimitive.Root>
</div>
