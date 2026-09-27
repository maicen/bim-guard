<script lang="ts">
  import type { Component } from "svelte";
  import { Popover } from "bits-ui";
  import { PlusCircle, Check, Search, X } from "lucide-svelte";
  import { cn } from "../utils/cn";

  export interface FacetedFilterOption {
    value: string;
    label: string;
    icon?: Component<{ class?: string }>;
  }

  interface Props {
    title: string;
    options: FacetedFilterOption[];
    selectedValues?: string[];
    facets?: Record<string, number>;
    onSelect?: (values: string[]) => void;
    onClear?: () => void;
    class?: string;
  }

  let {
    title,
    options = [],
    selectedValues = $bindable([]),
    facets = {},
    onSelect,
    onClear,
    class: className,
  }: Props = $props();

  let open = $state(false);
  let searchQuery = $state("");

  let filteredOptions = $derived.by(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return options;
    return options.filter((opt) => opt.label.toLowerCase().includes(q) || opt.value.toLowerCase().includes(q));
  });

  let selectedSet = $derived(new Set(selectedValues));

  function toggleOption(value: string) {
    let next: string[];
    if (selectedSet.has(value)) {
      next = selectedValues.filter((v) => v !== value);
    } else {
      next = [...selectedValues, value];
    }
    selectedValues = next;
    onSelect?.(next);
  }

  function handleClear() {
    selectedValues = [];
    searchQuery = "";
    onClear?.();
    onSelect?.([]);
  }
</script>

<Popover.Root bind:open>
  <Popover.Trigger>
    {#snippet child({ props })}
      <button
        type="button"
        {...props}
        class={cn(
          "inline-flex h-8 items-center gap-1.5 rounded-lg border border-dashed border-border-default bg-surface-card/60 px-2.5 text-xs font-medium text-fg-secondary transition-colors hover:border-border-interactive hover:text-fg-primary focus-visible:outline-2 focus-visible:outline-accent",
          selectedValues.length > 0 && "border-solid border-accent/40 bg-accent/5 text-fg-primary",
          className,
        )}
      >
        <PlusCircle class="h-3.5 w-3.5 shrink-0 text-fg-muted" />
        <span>{title}</span>

        {#if selectedValues.length > 0}
          <div class="h-3.5 w-px bg-border-default"></div>

          {#if selectedValues.length <= 2}
            <div class="flex items-center gap-1">
              {#each selectedValues as val (val)}
                {@const opt = options.find((o) => o.value === val)}
                <span
                  class="rounded-md bg-surface-overlay px-1.5 py-0.5 text-nano font-semibold text-fg-primary border border-border-subtle"
                >
                  {opt?.label || val}
                </span>
              {/each}
            </div>
          {:else}
            <span
              class="rounded-md bg-surface-overlay px-1.5 py-0.5 text-nano font-semibold text-fg-primary border border-border-subtle"
            >
              {selectedValues.length} selected
            </span>
          {/if}
        {/if}
      </button>
    {/snippet}
  </Popover.Trigger>

  <Popover.Portal>
    <Popover.Content
      align="start"
      sideOffset={6}
      class="z-50 w-56 rounded-xl border border-border-default bg-surface-card p-1.5 text-xs shadow-xl outline-hidden animate-in fade-in-0 zoom-in-95"
    >
      {#if options.length > 5}
        <div class="relative mb-1 flex items-center border-b border-border-default/60 pb-1.5 pt-0.5 px-1">
          <Search class="h-3.5 w-3.5 text-fg-muted shrink-0 mr-1.5" />
          <input
            type="text"
            bind:value={searchQuery}
            placeholder={title}
            class="w-full bg-transparent text-xs text-fg-primary placeholder:text-fg-muted outline-hidden"
          />
          {#if searchQuery}
            <button
              type="button"
              onclick={() => (searchQuery = "")}
              class="p-0.5 text-fg-muted hover:text-fg-primary"
            >
              <X class="h-3 w-3" />
            </button>
          {/if}
        </div>
      {/if}

      <div class="max-h-56 overflow-y-auto space-y-0.5 py-0.5">
        {#each filteredOptions as option (option.value)}
          {@const isChecked = selectedSet.has(option.value)}
          {@const count = facets[option.value]}
          <button
            type="button"
            onclick={() => toggleOption(option.value)}
            class={cn(
              "flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs font-medium transition-colors hover:bg-surface-hover hover:text-fg-primary cursor-pointer select-none",
              isChecked ? "text-fg-primary font-semibold" : "text-fg-secondary",
            )}
          >
            <div
              class={cn(
                "flex h-4 w-4 shrink-0 items-center justify-center rounded-sm border transition-colors",
                isChecked
                  ? "border-accent bg-accent text-white"
                  : "border-border-default bg-surface-canvas/80 text-transparent",
              )}
            >
              <Check class="h-3 w-3" />
            </div>

            {#if option.icon}
              <option.icon class="h-3.5 w-3.5 text-fg-muted shrink-0" />
            {/if}

            <span class="truncate flex-1">{option.label}</span>

            {#if count !== undefined}
              <span class="ml-auto font-mono text-nano text-fg-muted tabular-nums">
                {count}
              </span>
            {/if}
          </button>
        {:else}
          <div class="py-3 text-center text-xs text-fg-muted">
            No matching options
          </div>
        {/each}
      </div>

      {#if selectedValues.length > 0}
        <div class="border-t border-border-default/60 mt-1 pt-1">
          <button
            type="button"
            onclick={handleClear}
            class="flex w-full items-center justify-center rounded-lg py-1.5 text-center text-xs font-medium text-fg-muted hover:bg-surface-hover hover:text-fg-primary transition-colors cursor-pointer"
          >
            Clear filters
          </button>
        </div>
      {/if}
    </Popover.Content>
  </Popover.Portal>
</Popover.Root>
