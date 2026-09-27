<!--
  AiSuggestions — clickable follow-up prompt chips.
  Inspired by shadcn.io/ai/suggestion:
  Provides context-aware prompt recommendations after an assistant answer.
-->
<script lang="ts">
  import { Sparkles } from "lucide-svelte";

  interface Props {
    suggestions: string[];
    onSelect: (prompt: string) => void;
  }

  let { suggestions = [], onSelect }: Props = $props();
</script>

{#if suggestions.length > 0}
  <div class="mt-2.5 pt-2 flex flex-wrap items-center gap-1.5">
    <div class="flex items-center gap-1 text-[11px] font-semibold text-fg-muted uppercase tracking-wider mr-1">
      <Sparkles class="w-3 h-3 text-accent" />
      <span>Suggested Follow-ups:</span>
    </div>

    {#each suggestions as suggestion}
      <button
        type="button"
        onclick={() => onSelect(suggestion)}
        class="inline-flex items-center px-2.5 py-1 rounded-full text-xs bg-surface-card border border-border-default hover:border-accent hover:bg-surface-hover hover:text-accent text-fg-secondary transition-all text-left"
      >
        <span>{suggestion}</span>
      </button>
    {/each}
  </div>
{/if}
