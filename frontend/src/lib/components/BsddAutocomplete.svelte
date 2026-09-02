<script lang="ts">
  import { bsddApi } from '../api';
  import type { BSDDClassItem, BSDDPropertyItem } from '../types';

  type BsddSuggestion = BSDDClassItem | BSDDPropertyItem;

  interface Props {
    /** Search bSDD classes (element/classification codes) or properties. */
    mode: 'class' | 'property';
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
    value = $bindable(''),
    id = '',
    placeholder = '',
    dictionaryUri = undefined,
    onSelect,
    class: className = '',
  }: Props = $props();

  let suggestions = $state<BsddSuggestion[]>([]);
  let open = $state(false);
  let loading = $state(false);
  let highlighted = $state(-1);
  let debounceHandle: ReturnType<typeof setTimeout> | undefined;
  let requestToken = 0;

  function labelFor(item: BsddSuggestion): string {
    return 'code' in item ? item.code : item.name;
  }

  function subLabelFor(item: BsddSuggestion): string {
    if ('code' in item) return item.name;
    return item.property_set ? `${item.property_set}` : 'Property';
  }

  async function runSearch(query: string) {
    const token = ++requestToken;
    loading = true;
    try {
      const result =
        mode === 'class'
          ? (await bsddApi.searchClasses(query, dictionaryUri)).classes
          : (await bsddApi.searchProperties(query, dictionaryUri)).properties;
      if (token !== requestToken) return; // a newer keystroke superseded this request
      suggestions = result.slice(0, 10);
      open = suggestions.length > 0;
      highlighted = -1;
    } catch {
      if (token !== requestToken) return;
      suggestions = [];
      open = false;
    } finally {
      if (token === requestToken) loading = false;
    }
  }

  function handleInput() {
    clearTimeout(debounceHandle);
    const query = value.trim();
    if (query.length < 2) {
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

  function handleKeydown(e: KeyboardEvent) {
    if (!open || suggestions.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      highlighted = (highlighted + 1) % suggestions.length;
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      highlighted = (highlighted - 1 + suggestions.length) % suggestions.length;
    } else if (e.key === 'Enter' && highlighted >= 0) {
      e.preventDefault();
      pick(suggestions[highlighted]);
    } else if (e.key === 'Escape') {
      open = false;
    }
  }
</script>

<div class="relative">
  <input
    {id}
    type="text"
    bind:value
    {placeholder}
    autocomplete="off"
    oninput={handleInput}
    onkeydown={handleKeydown}
    onfocus={() => {
      if (suggestions.length > 0) open = true;
    }}
    onblur={() => setTimeout(() => (open = false), 150)}
    class={`w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#0071e3] ${className}`}
  />
  {#if loading}
    <span class="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-slate-500">…</span>
  {/if}
  {#if open}
    <ul
      class="absolute z-20 mt-1 w-full max-h-56 overflow-y-auto rounded-xl border border-slate-800 bg-slate-900 shadow-lg shadow-black/40"
    >
      {#each suggestions as item, i}
        <li>
          <button
            type="button"
            onmousedown={(e) => {
              e.preventDefault();
              pick(item);
            }}
            class={`w-full text-left px-3 py-1.5 text-xs hover:bg-slate-800 ${
              i === highlighted ? 'bg-slate-800' : ''
            }`}
          >
            <span class="text-white font-medium">{labelFor(item)}</span>
            <span class="ml-2 text-slate-500">{subLabelFor(item)}</span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>
