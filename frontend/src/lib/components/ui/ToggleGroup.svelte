<script lang="ts" module>
  import { ToggleGroup as ToggleGroupPrimitive } from "bits-ui";

  export const ToggleGroupRoot = ToggleGroupPrimitive.Root;
  export const ToggleGroupItem = ToggleGroupPrimitive.Item;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../utils/cn";

  export interface ToggleGroupOption {
    value: string;
    label: string;
    icon?: any;
    disabled?: boolean;
  }

  interface Props {
    type?: "single" | "multiple";
    value?: string | string[];
    options?: ToggleGroupOption[];
    disabled?: boolean;
    orientation?: "horizontal" | "vertical";
    class?: string;
    children?: Snippet;
  }

  let {
    type = "single",
    value = $bindable(type === "single" ? "" : []),
    options = [],
    disabled = false,
    orientation = "horizontal",
    class: className,
    children,
  }: Props = $props();
</script>

<!-- svelte-ignore state_referenced_locally -->
<ToggleGroupPrimitive.Root
  {type}
  bind:value={value as any}
  {disabled}
  {orientation}
  class={cn(
    "inline-flex items-center gap-1 rounded-xl border border-border-default bg-surface-canvas p-1 select-none",
    orientation === "vertical" ? "flex-col" : "flex-row",
    className,
  )}
>
  {#if children}
    {@render children()}
  {:else}
    {#each options as opt (opt.value)}
      <ToggleGroupPrimitive.Item
        value={opt.value}
        disabled={opt.disabled || disabled}
        class="inline-flex h-7 items-center justify-center gap-1.5 rounded-lg px-2.5 text-caption font-medium text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-40 data-[state=on]:bg-surface-card data-[state=on]:font-semibold data-[state=on]:text-fg-primary data-[state=on]:shadow-xs"
      >
        {#if opt.icon}
          {@const Icon = opt.icon}
          <Icon class="h-3.5 w-3.5" />
        {/if}
        <span>{opt.label}</span>
      </ToggleGroupPrimitive.Item>
    {/each}
  {/if}
</ToggleGroupPrimitive.Root>
