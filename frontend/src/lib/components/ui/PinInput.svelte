<script lang="ts" module>
  import { PinInput as PinInputPrimitive } from "bits-ui";

  export const PinInputRoot = PinInputPrimitive.Root;
  export const PinInputCell = PinInputPrimitive.Cell;
</script>

<script lang="ts">
  import { cn } from "../../utils/cn";

  interface Props {
    value?: string;
    length?: number;
    disabled?: boolean;
    class?: string;
    onComplete?: (val: string) => void;
  }

  let {
    value = $bindable(""),
    length = 6,
    disabled = false,
    class: className,
    onComplete,
  }: Props = $props();

  const cells = $derived(Array.from({ length }, (_, i) => i));
</script>

<PinInputPrimitive.Root
  maxlength={length}
  bind:value
  {onComplete}
  {disabled}
  class={cn("flex items-center gap-2", className)}
>
  {#snippet children({ cells: pinCells })}
    <div class="flex items-center gap-2">
      {#each pinCells as cell, i (i)}
        <PinInputPrimitive.Cell
          {cell}
          class="flex h-10 w-9 items-center justify-center rounded-xl border border-border-default bg-surface-canvas font-mono text-sm font-semibold text-fg-primary shadow-xs transition-colors focus:border-accent focus:ring-1 focus:ring-accent disabled:opacity-40"
        />
      {/each}
    </div>
  {/snippet}
</PinInputPrimitive.Root>
