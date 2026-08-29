<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { MoreVertical, Eye, Pencil, Trash2 } from 'lucide-svelte';

  export let onView: (() => void) | null = null;
  export let onEdit: (() => void) | null = null;
  export let onDelete: (() => void) | null = null;
  export let viewLabel: string = 'View';
  export let editLabel: string = 'Edit';
  export let deleteLabel: string = 'Delete';

  let isOpen = false;
  let menuRef: HTMLDivElement | null = null;

  function toggle() {
    isOpen = !isOpen;
  }

  function handleClickOutside(e: MouseEvent) {
    if (isOpen && menuRef && !menuRef.contains(e.target as Node)) {
      isOpen = false;
    }
  }

  onMount(() => {
    document.addEventListener('click', handleClickOutside);
  });

  onDestroy(() => {
    document.removeEventListener('click', handleClickOutside);
  });
</script>

<div class="relative inline-block text-left" bind:this={menuRef}>
  <button
    type="button"
    on:click|stopPropagation={toggle}
    class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors focus:outline-none"
    title="Actions"
  >
    <MoreVertical class="w-4 h-4" />
  </button>

  {#if isOpen}
    <div
      class="origin-top-right absolute right-0 mt-1.5 w-40 rounded-xl bg-slate-900 border border-slate-800 shadow-xl z-50 py-1 divide-y divide-slate-800 focus:outline-none animate-scale-up"
    >
      <div class="py-1">
        {#if onView}
          <button
            type="button"
            on:click={() => {
              isOpen = false;
              onView();
            }}
            class="group flex items-center gap-2.5 w-full px-3.5 py-1.5 text-xs text-slate-300 hover:text-white hover:bg-slate-800/80 transition-colors text-left"
          >
            <Eye class="w-3.5 h-3.5 text-slate-400 group-hover:text-white" />
            <span>{viewLabel}</span>
          </button>
        {/if}

        {#if onEdit}
          <button
            type="button"
            on:click={() => {
              isOpen = false;
              onEdit();
            }}
            class="group flex items-center gap-2.5 w-full px-3.5 py-1.5 text-xs text-slate-300 hover:text-white hover:bg-slate-800/80 transition-colors text-left"
          >
            <Pencil class="w-3.5 h-3.5 text-slate-400 group-hover:text-white" />
            <span>{editLabel}</span>
          </button>
        {/if}
      </div>

      {#if onDelete}
        <div class="py-1">
          <button
            type="button"
            on:click={() => {
              isOpen = false;
              onDelete();
            }}
            class="group flex items-center gap-2.5 w-full px-3.5 py-1.5 text-xs text-rose-400 hover:text-rose-300 hover:bg-rose-950/40 transition-colors text-left"
          >
            <Trash2 class="w-3.5 h-3.5 text-rose-400 group-hover:text-rose-300" />
            <span>{deleteLabel}</span>
          </button>
        </div>
      {/if}
    </div>
  {/if}
</div>
