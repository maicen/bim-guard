<!--
  AiBubble — chat bubble with role avatar and markdown formatting.
  Inspired by shadcn.io/ai/bubble & June 2026 Bubble component:
  Supports user & assistant roles, timestamps, badges, and inline citation pills.
-->
<script lang="ts">
  import { User, Sparkles, Copy, Check } from "lucide-svelte";
  import AiInlineCitation from "./AiInlineCitation.svelte";
  import type { GraphRagCitation } from "../../types";

  interface Props {
    role: "user" | "assistant" | "system";
    content: string;
    timestamp?: string;
    citations?: GraphRagCitation[];
    onCitationSelect?: (citation: GraphRagCitation) => void;
  }

  let {
    role,
    content,
    timestamp,
    citations = [],
    onCitationSelect,
  }: Props = $props();

  let isUser = $derived(role === "user");

  // Format content: handle code blocks and extract citations
  // Simple clean markdown-safe rendering
  let formattedBlocks = $derived.by(() => {
    if (!content) return [];
    // Split by code blocks ```
    const parts = content.split(/(```[\s\S]*?```)/g);
    return parts.map((part) => {
      if (part.startsWith("```") && part.endsWith("```")) {
        const lines = part.slice(3, -3).trim().split("\n");
        const lang = lines[0].trim();
        const code = lines.slice(lang ? 1 : 0).join("\n");
        return { isCode: true, lang, code };
      }
      return { isCode: false, text: part };
    });
  });

  let copied = $state(false);
  function copyText(code: string) {
    navigator.clipboard.writeText(code);
    copied = true;
    setTimeout(() => (copied = false), 2000);
  }
</script>

<div class="flex items-start gap-3 w-full {isUser ? 'flex-row-reverse' : 'flex-row'} group">
  <!-- Avatar -->
  <div
    class="shrink-0 w-8 h-8 rounded-full flex items-center justify-center border shadow-xs transition-colors
           {isUser
             ? 'bg-accent/15 border-accent/30 text-accent'
             : 'bg-surface-card border-border-default text-accent'}"
  >
    {#if isUser}
      <User class="w-4 h-4" />
    {:else}
      <Sparkles class="w-4 h-4" />
    {/if}
  </div>

  <!-- Message Content Container -->
  <div class="flex-1 max-w-[85%] space-y-1">
    <div class="flex items-center gap-2 text-[11px] text-fg-muted {isUser ? 'justify-end' : 'justify-start'}">
      <span class="font-medium text-fg-secondary">
        {isUser ? "You" : "BIM-Guard Copilot"}
      </span>
      {#if timestamp}
        <span class="font-mono text-[10px]">{timestamp}</span>
      {/if}
    </div>

    <!-- Bubble Surface -->
    <div
      class="p-4 rounded-2xl text-sm leading-relaxed border transition-colors shadow-2xs
             {isUser
               ? 'bg-surface-selected border-border-interactive text-fg-primary rounded-tr-xs'
               : 'bg-surface-card border-border-subtle text-fg-primary rounded-tl-xs'}"
    >
      {#each formattedBlocks as block, i}
        {#if block.isCode}
          <div class="my-2.5 rounded-lg border border-border-subtle bg-surface-canvas overflow-hidden text-xs">
            <div class="flex items-center justify-between px-3 py-1.5 bg-surface-hover/60 border-b border-border-subtle text-[11px] font-mono text-fg-muted">
              <span>{block.lang || "code"}</span>
              <button
                type="button"
                onclick={() => copyText(block.code || "")}
                class="hover:text-fg-primary flex items-center gap-1"
              >
                {#if copied}
                  <Check class="w-3 h-3 text-success" />
                  <span>Copied</span>
                {:else}
                  <Copy class="w-3 h-3" />
                  <span>Copy</span>
                {/if}
              </button>
            </div>
            <pre class="p-3 font-mono text-xs overflow-x-auto text-fg-secondary leading-relaxed">
              {block.code}
            </pre>
          </div>
        {:else}
          <div class="space-y-2 whitespace-pre-wrap">
            {block.text}
          </div>
        {/if}
      {/each}

      <!-- Citations bar if attached to message -->
      {#if citations.length > 0 && !isUser}
        <div class="mt-3 pt-2.5 border-t border-border-subtle/60 flex flex-wrap items-center gap-1">
          <span class="text-[10px] font-semibold text-fg-muted uppercase tracking-wider mr-1">
            Sources:
          </span>
          {#each citations as citation, idx (citation.id + idx)}
            <AiInlineCitation {citation} index={idx} onSelect={onCitationSelect} />
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>
