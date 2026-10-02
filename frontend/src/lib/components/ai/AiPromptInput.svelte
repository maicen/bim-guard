<!--
  AiPromptInput — chat input bar with auto-expanding textarea and action controls.
  Inspired by shadcn.io/ai/prompt-input:
  Features auto-growing textarea, submit/stop streaming buttons, keyboard shortcuts,
  and integrated scope attachment controls.
-->
<script lang="ts">
  import { ArrowUp, Square, Sparkles } from "lucide-svelte";
  import AiAttachments from "./AiAttachments.svelte";
  import type { GraphRagScope } from "../../types";

  interface Props {
    scope: GraphRagScope;
    isStreaming?: boolean;
    disabled?: boolean;
    placeholder?: string;
    selectedDocTitle?: string | null;
    selectedElementClass?: string | null;
    availableDocs?: Array<{ id: number; title: string }>;
    availableClasses?: Array<{ class_name: string; count: number }>;
    onSubmit: (prompt: string) => void;
    onStop?: () => void;
    onScopeChange: (scope: GraphRagScope) => void;
    onDocChange?: (docId: number | null) => void;
    onClassChange?: (className: string | null) => void;
  }

  let {
    scope = "hybrid",
    isStreaming = false,
    disabled = false,
    placeholder = "Ask anything about this document, IFC model, or compliance requirements...",
    selectedDocTitle = null,
    selectedElementClass = null,
    availableDocs = [],
    availableClasses = [],
    onSubmit,
    onStop,
    onScopeChange,
    onDocChange,
    onClassChange,
  }: Props = $props();

  let promptText = $state("");
  let textareaEl = $state<HTMLTextAreaElement | null>(null);

  function adjustHeight() {
    if (!textareaEl) return;
    textareaEl.style.height = "auto";
    textareaEl.style.height = `${Math.min(textareaEl.scrollHeight, 200)}px`;
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  }

  function handleSubmit() {
    const trimmed = promptText.trim();
    if (!trimmed || isStreaming || disabled) return;
    onSubmit(trimmed);
    promptText = "";
    if (textareaEl) {
      textareaEl.style.height = "auto";
    }
  }

  export function setPrompt(text: string) {
    promptText = text;
    adjustHeight();
    textareaEl?.focus();
  }
</script>

<div class="p-3 border-t border-border-default bg-surface-card rounded-b-xl space-y-2">
  <!-- Scope & Entity Attachments -->
  <AiAttachments
    {scope}
    {selectedDocTitle}
    {selectedElementClass}
    {availableDocs}
    {availableClasses}
    {onScopeChange}
    {onDocChange}
    {onClassChange}
  />

  <!-- Input Field Bar -->
  <div
    class="relative flex items-end gap-2 p-2 rounded-xl border border-border-interactive bg-surface-canvas focus-within:ring-2 focus-within:ring-accent transition-all"
  >
    <textarea
      bind:this={textareaEl}
      bind:value={promptText}
      oninput={adjustHeight}
      onkeydown={handleKeyDown}
      rows={1}
      {disabled}
      {placeholder}
      class="flex-1 max-h-48 resize-none bg-transparent py-1 px-1.5 text-sm text-fg-primary placeholder:text-fg-muted outline-none leading-relaxed"
    ></textarea>

    <!-- Action Button: Send or Stop -->
    <div class="shrink-0 mb-0.5">
      {#if isStreaming}
        <button
          type="button"
          onclick={onStop}
          class="w-8 h-8 rounded-lg border border-critical-border bg-critical-bg hover:bg-critical-bg/70 text-critical flex items-center justify-center transition-colors shadow-xs"
          title="Stop streaming"
        >
          <Square class="w-3.5 h-3.5 fill-current" />
        </button>
      {:else}
        <button
          type="button"
          onclick={handleSubmit}
          disabled={!promptText.trim() || disabled}
          class="w-8 h-8 rounded-lg bg-accent hover:bg-accent/90 disabled:opacity-40 disabled:pointer-events-none text-white flex items-center justify-center transition-colors shadow-xs"
          title="Send query (Enter)"
        >
          <ArrowUp class="w-4 h-4" />
        </button>
      {/if}
    </div>
  </div>

  <div class="flex items-center justify-between px-1 text-[11px] text-fg-muted">
    <div class="flex items-center gap-1.5">
      <Sparkles class="w-3 h-3 text-accent" />
      <span>Grounded in Neo4j Knowledge Graph & LiteLLM</span>
    </div>
    <span>Press <kbd class="px-1 py-0.2 rounded border border-border-subtle bg-surface-hover text-fg-secondary font-mono text-[10px]">Enter</kbd> to send, <kbd class="px-1 py-0.2 rounded border border-border-subtle font-mono text-[10px]">Shift+Enter</kbd> for newline</span>
  </div>
</div>
