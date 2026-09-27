<!--
  AiConversation — chat scroll container.
  Inspired by June 2026 MessageScroller & shadcn.io/ai/conversation:
  Anchors turns, follows streamed responses smoothly, maintains user scroll position
  when reading earlier history, and shows a floating jump button when scrolled up.
-->
<script lang="ts">
  import { onMount, tick } from "svelte";
  import type { Snippet } from "svelte";
  import { ArrowDown } from "lucide-svelte";

  interface Props {
    isStreaming?: boolean;
    children?: Snippet;
  }

  let { isStreaming = false, children }: Props = $props();

  let containerEl = $state<HTMLDivElement | null>(null);
  let isAtBottom = $state(true);
  let showJumpButton = $state(false);

  const THRESHOLD = 80;

  function handleScroll() {
    if (!containerEl) return;
    const { scrollTop, scrollHeight, clientHeight } = containerEl;
    const distanceToBottom = scrollHeight - scrollTop - clientHeight;
    isAtBottom = distanceToBottom <= THRESHOLD;
    showJumpButton = distanceToBottom > THRESHOLD * 2;
  }

  export async function scrollToBottom(smooth = true) {
    await tick();
    if (!containerEl) return;
    containerEl.scrollTo({
      top: containerEl.scrollHeight,
      behavior: smooth ? "smooth" : "auto",
    });
    isAtBottom = true;
    showJumpButton = false;
  }

  // Follow streamed tokens if user was already at the bottom
  $effect(() => {
    if (isStreaming && isAtBottom) {
      scrollToBottom(false);
    }
  });

  onMount(() => {
    scrollToBottom(false);
  });
</script>

<div class="relative flex-1 w-full min-h-0 flex flex-col overflow-hidden">
  <!-- Scroll Area -->
  <div
    bind:this={containerEl}
    onscroll={handleScroll}
    class="flex-1 w-full overflow-y-auto px-4 py-4 space-y-3 scroll-smooth scrollbar-thin scrollbar-thumb-border-default hover:scrollbar-thumb-border-interactive"
  >
    {#if children}
      {@render children()}
    {/if}
  </div>

  <!-- Floating Jump to Bottom Button -->
  {#if showJumpButton}
    <div class="absolute bottom-4 right-6 z-20">
      <button
        type="button"
        onclick={() => scrollToBottom(true)}
        class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface-overlay border border-border-interactive shadow-md text-xs font-medium text-fg-primary hover:bg-surface-hover hover:border-accent transition-all animate-bounce"
      >
        <ArrowDown class="w-3.5 h-3.5 text-accent" />
        <span>Jump to latest</span>
      </button>
    </div>
  {/if}
</div>
