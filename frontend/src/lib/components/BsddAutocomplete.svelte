<script lang="ts">
  import { Combobox as ComboboxPrimitive } from "bits-ui";
  import { bsddApi } from "../api";
  import type { BSDDClassItem, BSDDPropertyItem } from "../types";
  import { cn } from "../utils/cn";

  type BsddSuggestion = BSDDClassItem | BSDDPropertyItem;

  interface Props {
    /** Search bSDD classes (element/classification codes) or properties. */
    mode: "class" | "property";
    /** Current input text; the field this autocomplete decorates. */
    value: string;
    id?: string;
    placeholder?: string;
    dictionaryUri?: string;
    /** Called with the picked bSDD item; the caller decides what fields it fills in. */
    onSelect: (item: BsddSuggestion) => void;
    class?: string;
  }

  let {
    mode,
    value = $bindable(""),
    id = "",
    placeholder = "",
    dictionaryUri = undefined,
    onSelect,
    class: className = "",
  }: Props = $props();

  let suggestions = $state<BsddSuggestion[]>([]);
  let open = $state(false);
  let loading = $state(false);
  let debounceHandle: ReturnType<typeof setTimeout> | undefined;
  let requestToken = 0;

  function itemKey(item: BsddSuggestion): string {
    return "code" in item ? item.code : item.uri;
  }

  function labelFor(item: BsddSuggestion): string {
    return "code" in item ? item.code : item.name;
  }

  function subLabelFor(item: BsddSuggestion): string {
    if ("code" in item) return item.name;
    return item.property_set ? `${item.property_set}` : "Property";
  }

  async function runSearch(query: string) {
    const token = ++requestToken;
    loading = true;
    try {
      const result =
        mode === "class"
          ? (await bsddApi.searchClasses(query, dictionaryUri)).classes
          : (await bsddApi.searchProperties(query, dictionaryUri)).properties;
      if (token !== requestToken) return;
      suggestions = result.slice(0, 10);
      open = suggestions.length > 0;
    } catch {
      if (token !== requestToken) return;
      suggestions = [];
      open = false;
    } finally {
      if (token === requestToken) loading = false;
    }
  }

  function handleInput(e: Event) {
    const target = e.target as HTMLInputElement;
    value = target.value;
    clearTimeout(debounceHandle);
    const query = value.trim();
    if (query.length < 2) {
      requestToken += 1;
      loading = false;
      suggestions = [];
      open = false;
      return;
    }
    debounceHandle = setTimeout(() => runSearch(query), 300);
  }

  function pick(item: BsddSuggestion) {
    open = false;
    suggestions = [];
    onSelect(item);
  }
</script>

<ComboboxPrimitive.Root
  bind:open
  type="single"
  inputValue={value}
  onValueChange={(val) => {
    const found = suggestions.find((s) => itemKey(s) === val);
    if (found) pick(found);
  }}
>
  <div class="relative w-full">
    <ComboboxPrimitive.Input
      {id}
      oninput={handleInput}
      {placeholder}
      class={cn(
        "w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-1.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden",
        className,
      )}
    />
    {#if loading}
      <span class="absolute right-3 top-1/2 -translate-y-1/2 text-nano text-fg-muted">…</span>
    {/if}
  </div>

  <ComboboxPrimitive.Portal>
    <ComboboxPrimitive.Content
      class="z-50 max-h-56 min-w-[240px] overflow-hidden rounded-xl border border-border-default bg-surface-card p-1 shadow-xl duration-150 animate-in fade-in zoom-in-95"
      sideOffset={4}
    >
      <ComboboxPrimitive.Viewport class="p-1">
        {#each suggestions as item (itemKey(item))}
          <ComboboxPrimitive.Item
            value={itemKey(item)}
            label={labelFor(item)}
            class="flex cursor-pointer select-none items-center justify-between rounded-lg px-2.5 py-1.5 text-xs text-fg-secondary outline-hidden transition-colors data-[highlighted]:bg-surface-hover data-[highlighted]:text-fg-primary"
          >
            <span class="font-medium text-fg-primary">{labelFor(item)}</span>
            <span class="ml-2 text-nano text-fg-muted">{subLabelFor(item)}</span>
          </ComboboxPrimitive.Item>
        {/each}
      </ComboboxPrimitive.Viewport>
    </ComboboxPrimitive.Content>
  </ComboboxPrimitive.Portal>
</ComboboxPrimitive.Root>
