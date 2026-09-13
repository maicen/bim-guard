<script lang="ts" module>
  import { Combobox as ComboboxPrimitive } from "bits-ui";

  export const ComboboxRoot = ComboboxPrimitive.Root;
  export const ComboboxInput = ComboboxPrimitive.Input;
  export const ComboboxTrigger = ComboboxPrimitive.Trigger;
  export const ComboboxPortal = ComboboxPrimitive.Portal;
  export const ComboboxContent = ComboboxPrimitive.Content;
  export const ComboboxItem = ComboboxPrimitive.Item;
</script>

<script lang="ts">
  import { Check, ChevronsUpDown } from "lucide-svelte";
  import { cn } from "../../utils/cn";

  export interface ComboboxOption {
    value: string;
    label: string;
    description?: string;
    disabled?: boolean;
  }

  interface Props {
    options: ComboboxOption[];
    value?: string;
    placeholder?: string;
    disabled?: boolean;
    class?: string;
    onValueChange?: (val: string) => void;
  }

  let {
    options = [],
    value = $bindable(""),
    placeholder = "Search or select…",
    disabled = false,
    class: className,
    onValueChange,
  }: Props = $props();

  let searchValue = $state("");

  let filteredOptions = $derived(
    searchValue === ""
      ? options
      : options.filter(
          (o) =>
            o.label.toLowerCase().includes(searchValue.toLowerCase()) ||
            o.value.toLowerCase().includes(searchValue.toLowerCase()) ||
            (o.description && o.description.toLowerCase().includes(searchValue.toLowerCase())),
        ),
  );
</script>

<ComboboxPrimitive.Root
  bind:value
  type="single"
  {disabled}
  onValueChange={(v) => {
    if (typeof v === "string") onValueChange?.(v);
  }}
>
  <div class={cn("relative w-full", className)}>
    <ComboboxPrimitive.Input
      {placeholder}
      oninput={(e) => (searchValue = e.currentTarget.value)}
      class="flex h-9 w-full items-center rounded-xl border border-border-default bg-surface-canvas pl-3 pr-8 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden focus:ring-1 focus:ring-accent disabled:cursor-not-allowed disabled:opacity-40"
    />
    <ComboboxPrimitive.Trigger class="absolute right-2.5 top-1/2 -translate-y-1/2 text-fg-muted hover:text-fg-primary">
      <ChevronsUpDown class="h-3.5 w-3.5" />
    </ComboboxPrimitive.Trigger>
  </div>

  <ComboboxPrimitive.Portal>
    <ComboboxPrimitive.Content
      class="z-50 max-h-60 min-w-[200px] overflow-hidden rounded-2xl border border-border-default bg-surface-card p-1 shadow-xl duration-150 animate-in fade-in zoom-in-95"
      sideOffset={6}
    >
      <ComboboxPrimitive.Viewport class="p-1">
        {#if filteredOptions.length === 0}
          <div class="px-3 py-2 text-center text-xs text-fg-muted">
            No options found.
          </div>
        {:else}
          {#each filteredOptions as opt (opt.value)}
            <ComboboxPrimitive.Item
              value={opt.value}
              label={opt.label}
              disabled={opt.disabled}
              class="relative flex cursor-pointer select-none items-center justify-between rounded-lg px-2.5 py-1.5 text-xs text-fg-secondary outline-hidden transition-colors data-[highlighted]:bg-surface-hover data-[highlighted]:text-fg-primary data-[selected]:font-semibold data-[selected]:text-accent disabled:cursor-not-allowed disabled:opacity-40"
            >
              <div class="flex flex-col">
                <span>{opt.label}</span>
                {#if opt.description}
                  <span class="text-nano text-fg-muted">{opt.description}</span>
                {/if}
              </div>
              {#if value === opt.value}
                <Check class="h-3.5 w-3.5 text-accent" />
              {/if}
            </ComboboxPrimitive.Item>
          {/each}
        {/if}
      </ComboboxPrimitive.Viewport>
    </ComboboxPrimitive.Content>
  </ComboboxPrimitive.Portal>
</ComboboxPrimitive.Root>
