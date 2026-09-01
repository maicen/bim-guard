<script lang="ts">
  import type { ComponentType } from "svelte";
  import { X } from "lucide-svelte";

  export let isOpen: boolean = false;
  export let title: string = "";
  export let subtitle: string = "";
  export let icon: ComponentType | null = null;
  export let maxWidth:
    | "max-w-sm"
    | "max-w-md"
    | "max-w-lg"
    | "max-w-xl"
    | "max-w-2xl"
    | "max-w-3xl"
    | "max-w-4xl" = "max-w-lg";
  export let onClose: () => void;

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === "Escape" && isOpen) {
      onClose();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if isOpen}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200"
    role="dialog"
    aria-modal="true"
    aria-labelledby="modal-title"
  >
    <!-- Modal Dialog Card -->
    <div
      class="bg-slate-900 border border-slate-800 w-full {maxWidth} rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-200"
    >
      <!-- Header -->
      <div
        class="px-6 py-4 border-b border-slate-800 flex items-center justify-between gap-4 bg-slate-950/60"
      >
        <div class="flex items-center gap-3 min-w-0">
          {#if icon}
            <div
              class="w-9 h-9 rounded-xl bg-blue-950/60 border border-blue-800/60 flex items-center justify-center text-[#0071e3] shrink-0"
            >
              <svelte:component this={icon} class="w-4 h-4" />
            </div>
          {/if}
          <div class="min-w-0">
            <h3
              id="modal-title"
              class="text-base font-bold text-white tracking-tight truncate"
            >
              {title}
            </h3>
            {#if subtitle}
              <p class="text-xs text-slate-400 truncate mt-0.5">{subtitle}</p>
            {/if}
          </div>
        </div>

        <div class="flex items-center gap-2 shrink-0">
          <slot name="header-extra" />
          <button
            type="button"
            on:click={onClose}
            class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close dialog"
          >
            <X class="w-4 h-4" />
          </button>
        </div>
      </div>

      <!-- Scrollable Body Content -->
      <div class="p-6 space-y-4 overflow-y-auto flex-1 text-xs">
        <slot />
      </div>

      <!-- Footer Actions -->
      {#if $$slots.footer}
        <div
          class="px-6 py-3.5 border-t border-slate-800 bg-slate-950/80 flex items-center justify-end gap-2 shrink-0"
        >
          <slot name="footer" />
        </div>
      {/if}
    </div>
  </div>
{/if}
