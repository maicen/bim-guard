<script lang="ts">
  import type { Component, ComponentType, Snippet } from "svelte";
  import { ChevronDown, ChevronRight, ChevronLeft, ChevronUp } from "lucide-svelte";

  interface Props {
    title: string;
    icon?: Component<any> | ComponentType<any> | null;
    /** Which edge this panel docks against — picks the collapse direction and chevron. */
    side?: "left" | "right" | "bottom";
    /** Persists collapse state across reloads under this key. Omit to keep it session-only. */
    id?: string;
    collapsed?: boolean;
    headerExtra?: Snippet;
    children?: Snippet;
  }

  let {
    title,
    icon = null,
    side = "left",
    id,
    collapsed = $bindable(false),
    headerExtra,
    children,
  }: Props = $props();

  const STORAGE_PREFIX = "bimguard-collapsible-panel:";

  function loadStored(): boolean | null {
    if (!id) return null;
    try {
      const raw = localStorage.getItem(STORAGE_PREFIX + id);
      return raw === null ? null : raw === "1";
    } catch {
      return null;
    }
  }

  const stored = loadStored();
  if (stored !== null) collapsed = stored;

  function persist(value: boolean) {
    if (!id) return;
    try {
      localStorage.setItem(STORAGE_PREFIX + id, value ? "1" : "0");
    } catch {
      // Best-effort only (private browsing, storage disabled, etc.)
    }
  }

  function toggle() {
    collapsed = !collapsed;
    persist(collapsed);
  }

  const Icon = $derived(icon);
  // Chevron points toward the direction expanding would go.
  const Chevron = $derived(
    side === "bottom" ? (collapsed ? ChevronUp : ChevronDown)
    : side === "right" ? (collapsed ? ChevronLeft : ChevronRight)
    : collapsed ? ChevronRight : ChevronLeft,
  );
</script>

<div
  class="flex shrink-0 overflow-hidden border-slate-800 bg-slate-900/60 {side === 'bottom'
    ? 'flex-col border-t'
    : side === 'right'
      ? 'flex-col border-l'
      : 'flex-col border-r'}"
>
  <div
    class="flex h-9 shrink-0 items-center justify-between gap-2 border-b border-slate-800/80 bg-slate-950/60 px-2.5"
  >
    <button
      type="button"
      onclick={toggle}
      class="flex min-w-0 flex-1 items-center gap-1.5 text-left text-xs font-semibold tracking-wide text-slate-200 hover:text-slate-50"
      aria-expanded={!collapsed}
    >
      {#if Icon}
        <Icon class="h-3.5 w-3.5 shrink-0 text-blue-400" />
      {/if}
      {#if !collapsed}
        <span class="truncate">{title}</span>
      {/if}
    </button>
    <div class="flex shrink-0 items-center gap-1">
      {#if !collapsed}
        {@render headerExtra?.()}
      {/if}
      <button
        type="button"
        onclick={toggle}
        class="rounded p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        aria-label={collapsed ? `Expand ${title}` : `Collapse ${title}`}
        title={collapsed ? `Expand ${title}` : `Collapse ${title}`}
      >
        <Chevron class="h-3.5 w-3.5" />
      </button>
    </div>
  </div>

  <!-- Content stays mounted while collapsed (hidden via the `hidden` attribute,
       not removed with {#if}) so any DOM refs a child hands to the IFC engine
       (e.g. the Drawings panel's sheet-board host) stay valid regardless of
       collapse state instead of being torn down and never recreated. -->
  <div class="min-h-0 flex-1 overflow-y-auto" hidden={collapsed}>
    {@render children?.()}
  </div>
</div>
