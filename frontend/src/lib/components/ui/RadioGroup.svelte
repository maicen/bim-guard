<script lang="ts" module>
  import { RadioGroup as RadioGroupPrimitive } from "bits-ui";

  export const RadioGroupRoot = RadioGroupPrimitive.Root;
  export const RadioGroupItem = RadioGroupPrimitive.Item;
</script>

<script lang="ts">
  import type { Snippet } from "svelte";
  import { cn } from "../../utils/cn";

  export interface RadioOption {
    value: string;
    label: string;
    description?: string;
    disabled?: boolean;
  }

  interface Props {
    options?: RadioOption[];
    value?: string;
    onValueChange?: (value: string) => void;
    disabled?: boolean;
    name?: string;
    orientation?: "horizontal" | "vertical";
    class?: string;
    children?: Snippet;
  }

  let {
    options = [],
    value = $bindable(""),
    onValueChange,
    disabled = false,
    name,
    orientation = "vertical",
    class: className,
    children,
  }: Props = $props();
</script>

<RadioGroupPrimitive.Root
  bind:value
  {onValueChange}
  {disabled}
  {name}
  {orientation}
  class={cn(
    "flex gap-3",
    orientation === "vertical" ? "flex-col" : "flex-row flex-wrap items-center",
    className,
  )}
>
  {#if children}
    {@render children()}
  {:else}
    {#each options as opt (opt.value)}
      <label
        class={cn(
          "flex cursor-pointer select-none items-start gap-3 rounded-xl border border-border-default bg-surface-card p-3 text-xs transition-colors hover:bg-surface-hover",
          value === opt.value && "border-accent/60 bg-surface-selected ring-1 ring-accent/40",
          opt.disabled && "cursor-not-allowed opacity-40 hover:bg-surface-card",
        )}
      >
        <RadioGroupPrimitive.Item
          value={opt.value}
          disabled={opt.disabled || disabled}
          class="relative mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-border-interactive bg-surface-canvas transition-colors focus-visible:outline-2 focus-visible:outline-accent data-[state=checked]:border-accent data-[state=checked]:bg-accent"
        >
          {#snippet children({ checked })}
            {#if checked}
              <span class="h-1.5 w-1.5 rounded-full bg-white"></span>
            {/if}
          {/snippet}
        </RadioGroupPrimitive.Item>

        <div class="space-y-0.5">
          <span class="font-medium text-fg-primary">{opt.label}</span>
          {#if opt.description}
            <p class="text-nano text-fg-muted">{opt.description}</p>
          {/if}
        </div>
      </label>
    {/each}
  {/if}
</RadioGroupPrimitive.Root>
