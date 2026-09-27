<!--
  AiActions — assistant message action toolbar.
  Inspired by shadcn.io/ai/actions:
  Provides quick actions under assistant responses: Copy markdown, Thumbs feedback,
  Regenerate, and Export to BCF compliance issue.
-->
<script lang="ts">
  import { Check, Copy, RefreshCw, ThumbsDown, ThumbsUp, BookmarkPlus } from "lucide-svelte";

  interface Props {
    content: string;
    onRegenerate?: () => void;
    onExportBcf?: () => void;
  }

  let { content, onRegenerate, onExportBcf }: Props = $props();

  let copied = $state(false);
  let feedback = $state<"up" | "down" | null>(null);

  function copyText() {
    navigator.clipboard.writeText(content);
    copied = true;
    setTimeout(() => (copied = false), 2000);
  }

  function handleFeedback(type: "up" | "down") {
    feedback = feedback === type ? null : type;
  }
</script>

<div class="flex items-center gap-1 text-fg-muted mt-2 pt-2 border-t border-border-subtle/50 text-xs">
  <button
    type="button"
    onclick={copyText}
    class="inline-flex items-center gap-1 px-2 py-1 rounded hover:bg-surface-hover hover:text-fg-primary transition-colors text-[11px]"
    title="Copy answer markdown"
  >
    {#if copied}
      <Check class="w-3.5 h-3.5 text-success" />
      <span class="text-success font-medium">Copied</span>
    {:else}
      <Copy class="w-3.5 h-3.5" />
      <span>Copy</span>
    {/if}
  </button>

  {#if onRegenerate}
    <button
      type="button"
      onclick={onRegenerate}
      class="inline-flex items-center gap-1 px-2 py-1 rounded hover:bg-surface-hover hover:text-fg-primary transition-colors text-[11px]"
      title="Regenerate answer"
    >
      <RefreshCw class="w-3.5 h-3.5" />
      <span>Retry</span>
    </button>
  {/if}

  {#if onExportBcf}
    <button
      type="button"
      onclick={onExportBcf}
      class="inline-flex items-center gap-1 px-2 py-1 rounded hover:bg-surface-hover hover:text-accent transition-colors text-[11px]"
      title="Export finding as BCF topic"
    >
      <BookmarkPlus class="w-3.5 h-3.5" />
      <span>Save as BCF Topic</span>
    </button>
  {/if}

  <div class="ml-auto flex items-center gap-0.5">
    <button
      type="button"
      onclick={() => handleFeedback("up")}
      class="p-1 rounded hover:bg-surface-hover transition-colors {feedback === 'up' ? 'text-success bg-success-bg' : ''}"
      title="Helpful response"
    >
      <ThumbsUp class="w-3.5 h-3.5" />
    </button>
    <button
      type="button"
      onclick={() => handleFeedback("down")}
      class="p-1 rounded hover:bg-surface-hover transition-colors {feedback === 'down' ? 'text-critical bg-critical-bg' : ''}"
      title="Inaccurate or unhelpful"
    >
      <ThumbsDown class="w-3.5 h-3.5" />
    </button>
  </div>
</div>
