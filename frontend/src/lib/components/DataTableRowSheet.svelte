<script lang="ts">
  import type { Snippet } from "svelte";
  import { Dialog } from "bits-ui";
  import { X, Copy, Check } from "lucide-svelte";
  import { cn } from "../utils/cn";
  import { toasts } from "../toast.svelte";

  export interface RowSheetField {
    key: string;
    label: string;
    format?: "text" | "badge" | "code" | "date" | "boolean" | "json";
  }

  interface Props {
    open?: boolean;
    title?: string;
    subtitle?: string;
    data?: Record<string, any> | null;
    fields?: RowSheetField[];
    class?: string;
    children?: Snippet;
    actions?: Snippet;
  }

  let {
    open = $bindable(false),
    title = "Row Details",
    subtitle = "",
    data = null,
    fields = [],
    class: className,
    children,
    actions,
  }: Props = $props();

  let copiedKey = $state<string | null>(null);

  async function copyToClipboard(key: string, value: any) {
    try {
      const text = typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
      await navigator.clipboard.writeText(text);
      copiedKey = key;
      setTimeout(() => {
        if (copiedKey === key) copiedKey = null;
      }, 2000);
      toasts.success("Copied to clipboard");
    } catch {
      toasts.error("Failed to copy to clipboard");
    }
  }

  function formatValue(val: any, format?: string): string {
    if (val == null) return "—";
    if (format === "date") {
      try {
        return new Date(val).toLocaleString();
      } catch {
        return String(val);
      }
    }
    if (format === "boolean") return val ? "Yes" : "No";
    if (format === "json") return JSON.stringify(val, null, 2);
    return String(val);
  }
</script>

<Dialog.Root bind:open>
  <Dialog.Portal>
    <Dialog.Overlay
      class="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs transition-opacity animate-in fade-in-0 duration-200"
    />
    <Dialog.Content
      class={cn(
        "fixed inset-y-0 right-0 z-50 flex h-full w-full max-w-md flex-col border-l border-border-default bg-surface-card shadow-2xl outline-hidden animate-in slide-in-from-right duration-300",
        className,
      )}
    >
      <!-- Sheet Header -->
      <div class="flex items-start justify-between border-b border-border-default p-5 shrink-0">
        <div class="space-y-1 pr-6 min-w-0">
          <Dialog.Title class="text-base font-bold text-fg-primary truncate">
            {title}
          </Dialog.Title>
          {#if subtitle}
            <Dialog.Description class="text-xs text-fg-muted truncate">
              {subtitle}
            </Dialog.Description>
          {/if}
        </div>

        <Dialog.Close
          class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
        >
          <X class="h-4 w-4" />
          <span class="sr-only">Close</span>
        </Dialog.Close>
      </div>

      <!-- Sheet Scrollable Content -->
      <div class="flex-1 overflow-y-auto p-5 space-y-4">
        {#if data && fields.length > 0}
          <div class="space-y-3">
            {#each fields as field (field.key)}
              {@const val = data[field.key]}
              <div class="rounded-xl border border-border-default/60 bg-surface-canvas/50 p-3 space-y-1">
                <div class="flex items-center justify-between text-nano font-semibold uppercase tracking-wider text-fg-muted">
                  <span>{field.label}</span>
                  {#if val != null}
                    <button
                      type="button"
                      onclick={() => copyToClipboard(field.key, val)}
                      class="text-fg-muted hover:text-fg-primary transition-colors p-0.5 rounded cursor-pointer"
                      title="Copy value"
                    >
                      {#if copiedKey === field.key}
                        <Check class="h-3 w-3 text-success" />
                      {:else}
                        <Copy class="h-3 w-3" />
                      {/if}
                    </button>
                  {/if}
                </div>

                <div class="text-xs text-fg-primary break-all">
                  {#if field.format === "badge"}
                    <span class="inline-flex rounded-md bg-surface-overlay px-2 py-0.5 text-nano font-semibold text-fg-primary border border-border-subtle">
                      {formatValue(val, field.format)}
                    </span>
                  {:else if field.format === "code"}
                    <code class="rounded bg-surface-overlay px-1.5 py-0.5 font-mono text-nano text-fg-secondary">
                      {formatValue(val, field.format)}
                    </code>
                  {:else if field.format === "json"}
                    <pre class="rounded-lg bg-surface-overlay p-2 font-mono text-nano text-fg-muted overflow-x-auto max-h-40">
                      {formatValue(val, field.format)}
                    </pre>
                  {:else}
                    <span class="font-medium">{formatValue(val, field.format)}</span>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        {/if}

        {@render children?.()}
      </div>

      <!-- Sheet Footer Actions -->
      {#if actions}
        <div class="border-t border-border-default p-4 shrink-0 bg-surface-card">
          {@render actions()}
        </div>
      {/if}
    </Dialog.Content>
  </Dialog.Portal>
</Dialog.Root>
