<script lang="ts">
  import { AlertTriangle } from 'lucide-svelte';

  export let isOpen: boolean = false;
  export let title: string = 'Confirm Action';
  export let message: string = 'Are you sure you want to proceed? This action cannot be undone.';
  export let confirmText: string = 'Delete';
  export let cancelText: string = 'Cancel';
  export let danger: boolean = true;
  export let onConfirm: () => void | Promise<void>;
  export let onCancel: () => void;

  let isSubmitting = false;

  async function handleConfirm() {
    isSubmitting = true;
    try {
      await onConfirm();
    } finally {
      isSubmitting = false;
      isOpen = false;
    }
  }

  function handleCancel() {
    if (isSubmitting) return;
    onCancel();
    isOpen = false;
  }
</script>

{#if isOpen}
  <!-- Backdrop -->
  <div
    role="dialog"
    aria-modal="true"
    aria-labelledby="confirm-modal-title"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in px-4"
  >
    <!-- Modal Card -->
    <div
      class="bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-5 animate-scale-up"
    >
      <div class="flex items-start gap-3.5">
        {#if danger}
          <div class="w-10 h-10 rounded-xl bg-rose-950/80 border border-rose-800/80 flex items-center justify-center text-rose-400 shrink-0">
            <AlertTriangle class="w-5 h-5" />
          </div>
        {/if}
        <div class="space-y-1.5 flex-1 min-w-0">
          <h2 id="confirm-modal-title" class="text-base font-bold text-slate-50 tracking-tight">
            {title}
          </h2>
          <p id="confirm-modal-body" class="text-xs text-slate-400 leading-relaxed">
            {message}
          </p>
        </div>
      </div>

      <div class="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-800/80">
        <button
          type="button"
          on:click={handleCancel}
          disabled={isSubmitting}
          class="h-9 px-4 rounded-xl border border-slate-700 bg-slate-800 text-slate-300 text-xs font-semibold hover:bg-slate-700 hover:text-slate-50 transition-colors disabled:opacity-50"
        >
          {cancelText}
        </button>

        <button
          type="button"
          on:click={handleConfirm}
          disabled={isSubmitting}
          class="h-9 px-4 rounded-xl text-xs font-semibold transition-all disabled:opacity-50 {danger
            ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-lg shadow-rose-950/50'
            : 'bg-accent hover:bg-accent-hover text-white shadow-lg shadow-blue-950/50'}"
        >
          {isSubmitting ? 'Processing...' : confirmText}
        </button>
      </div>
    </div>
  </div>
{/if}
