<script lang="ts">
  import { Select as SelectPrimitive } from "bits-ui";
  import { Check, ChevronDown } from "lucide-svelte";
  import { cn } from "../../utils/cn";

  export interface SelectOption {
    value: string;
    label: string;
    disabled?: boolean;
  }

  interface Props {
    options: SelectOption[];
    value?: string;
    placeholder?: string;
    disabled?: boolean;
    class?: string;
    triggerClass?: string;
    contentClass?: string;
    ariaLabel?: string;
    onValueChange?: (value: string) => void;
  }

  let {
    options,
    value = $bindable(""),
    placeholder = "Select an option…",
    disabled = false,
    class: className,
    triggerClass,
    contentClass,
    ariaLabel,
    onValueChange,
  }: Props = $props();

  let selectedLabel = $derived(options.find((opt) => opt.value === value)?.label ?? "");
</script>

<SelectPrimitive.Root
  type="single"
  bind:value
  {onValueChange}
  {disabled}
>
  <SelectPrimitive.Trigger
    aria-label={ariaLabel}
    class={cn(
      "inline-flex h-9 w-full items-center justify-between gap-2 rounded-xl border border-border-default bg-surface-card px-3 py-2 text-xs text-fg-primary shadow-xs transition-colors hover:border-border-interactive focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-40",
      triggerClass,
      className,
    )}
  >
    <span class={cn("truncate", !value && "text-fg-muted")}>
      {selectedLabel || placeholder}
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
      {#each options as option (option.value)}
        <SelectPrimitive.Item
          value={option.value}
          label={option.label}
          disabled={option.disabled}
          class="relative flex cursor-pointer select-none items-center justify-between rounded-lg px-2.5 py-1.5 text-xs text-fg-secondary outline-hidden transition-colors data-highlighted:bg-surface-hover data-highlighted:text-fg-primary data-disabled:cursor-not-allowed data-disabled:opacity-40"
        >
          {#snippet children({ selected })}
            <span>{option.label}</span>
            {#if selected}
              <Check class="h-3.5 w-3.5 text-accent" />
            {/if}
          {/snippet}
        </SelectPrimitive.Item>
      {/each}
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
</SelectPrimitive.Root>
