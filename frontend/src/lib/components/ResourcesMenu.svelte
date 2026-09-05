<script lang="ts">
  import { BookOpenCheck, Box, BookText, LifeBuoy, ChevronDown } from "lucide-svelte";
  import { link } from "svelte-spa-router";

  interface Props {
    activeView: string;
  }

  let { activeView }: Props = $props();

  let open = $state(false);

  // Reference material, not project work — pulled out of the working sidebar
  // (see Tenant & Workspace Blueprint, Priority 11 in TODO.md) into its own
  // navbar menu so it's reachable from any view without crowding the
  // project-focused nav groups.
  const ITEMS = [
    { id: "user-manual", label: "User Manual", icon: BookOpenCheck },
    { id: "modeling-manual", label: "Modeling Manual", icon: Box },
    { id: "bsdd-wiki", label: "bSDD Wiki", icon: BookText },
  ];

  let isActive = $derived(ITEMS.some((item) => item.id === activeView));

  function toggle(e: MouseEvent) {
    e.stopPropagation();
    open = !open;
  }
</script>

<svelte:document onclick={() => (open = false)} />

<div class="relative hidden md:block">
  <button
    type="button"
    onclick={toggle}
    class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors {isActive
      ? 'border-blue-800/60 bg-blue-950/40 text-blue-300'
      : 'border-slate-800 bg-slate-900/60 text-slate-400 hover:border-slate-700 hover:text-slate-50'}"
    aria-haspopup="true"
    aria-expanded={open}
  >
    <LifeBuoy class="h-3.5 w-3.5" />
    Resources
    <ChevronDown class="h-3 w-3" />
  </button>

  {#if open}
    <div
      class="absolute right-0 top-full z-40 mt-2 w-52 rounded-xl border border-slate-800 bg-slate-900 p-1.5 shadow-xl"
    >
      {#each ITEMS as item (item.id)}
        <a
          href="/{item.id}"
          use:link
          onclick={() => (open = false)}
          class="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium transition-colors {activeView ===
          item.id
            ? 'bg-accent text-white'
            : 'text-slate-300 hover:bg-slate-800 hover:text-slate-50'}"
        >
          <item.icon class="h-3.5 w-3.5" />
          {item.label}
        </a>
      {/each}
    </div>
  {/if}
</div>
