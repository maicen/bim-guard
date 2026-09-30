<script lang="ts">
  import { Select as SelectPrimitive } from "bits-ui";
  import { ChevronDown, Square, SquareCheck } from "lucide-svelte";
  import { cn } from "../../utils/cn";
  import Button from "./Button.svelte";
  import type { SelectOption } from "./Select.svelte";

  interface Props {
    options: SelectOption[];
    value?: string[];
    /** Shown in the trigger when nothing is selected. */
    placeholder?: string;
    /** Hint shown above the options, telling the user several can be picked. */
    hint?: string;
    disabled?: boolean;
    class?: string;
    triggerClass?: string;
    contentClass?: string;
    ariaLabel?: string;
    onValueChange?: (value: string[]) => void;
  }

  let {
    options,
    value = $bindable([]),
    placeholder = "Select options…",
    hint = "Select one or more",
    disabled = false,
    class: className,
    triggerClass,
    contentClass,
    ariaLabel,
    onValueChange,
  }: Props = $props();

  let selectedLabels = $derived(
    value.map((v) => options.find((opt) => opt.value === v)?.label ?? v),
  );

  function clear() {
    value = [];
    onValueChange?.([]);
  }
</script>

<SelectPrimitive.Root type="multiple" bind:value {onValueChange} {disabled}>
  <SelectPrimitive.Trigger
    aria-label={ariaLabel}
    class={cn(
      "inline-flex h-9 w-full items-center justify-between gap-2 rounded-xl border border-border-default bg-surface-card px-3 py-2 text-xs text-fg-primary shadow-xs transition-colors hover:border-border-interactive focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-40",
      triggerClass,
      className,
    )}
  >
    <span class={cn("truncate", !value.length && "text-fg-muted")}>
      {#if value.length === 0}
        {placeholder}
      {:else if value.length === 1}
        {selectedLabels[0]}
      {:else}
        {value.length} selected: {selectedLabels.join(", ")}
      {/if}
    </span>
    <ChevronDown class="h-3.5 w-3.5 shrink-0 text-fg-muted" />
  </SelectPrimitive.Trigger>

  <SelectPrimitive.Portal>
    <SelectPrimitive.Content
      class={cn(
        "z-70 min-w-(--bits-select-anchor-width) overflow-hidden rounded-xl border border-border-default bg-surface-overlay p-1 shadow-2xl backdrop-blur-md origin-(--bits-select-content-transform-origin) duration-150 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
        contentClass,
      )}
      sideOffset={4}
    >
      <div class="px-2.5 pt-1 pb-1.5 text-micro text-fg-muted">{hint}</div>
      {#each options as option (option.value)}
        <SelectPrimitive.Item
          value={option.value}
          label={option.label}
          disabled={option.disabled}
          class="relative flex cursor-pointer select-none items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs text-fg-secondary outline-hidden transition-colors data-highlighted:bg-surface-hover data-highlighted:text-fg-primary data-disabled:cursor-not-allowed data-disabled:opacity-40"
        >
          {#snippet children({ selected })}
            {#if selected}
              <SquareCheck class="h-3.5 w-3.5 shrink-0 text-accent" />
            {:else}
              <Square class="h-3.5 w-3.5 shrink-0 text-fg-muted" />
            {/if}
            <span>{option.label}</span>
          {/snippet}
        </SelectPrimitive.Item>
      {/each}
      {#if value.length}
        <div class="mt-1 border-t border-border-subtle pt-1">
          <Button variant="ghost" size="sm" class="w-full justify-start" onclick={clear}>
            Clear selection ({placeholder})
          </Button>
        </div>
      {/if}
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
</SelectPrimitive.Root>
