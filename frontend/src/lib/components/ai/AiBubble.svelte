<!--
  AiBubble — chat bubble with role avatar and markdown formatting.
  Inspired by shadcn.io/ai/bubble & June 2026 Bubble component:
  Supports user & assistant roles, timestamps, badges, markdown rendering, and inline citation pills.
-->
<script lang="ts">
  import { User, Sparkles, Copy, Check } from "lucide-svelte";
  import { marked } from "marked";
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

  function renderMarkdown(md: string): string {
    if (!md) return "";
    try {
      // Style inline citation markers [Doc: ...] and [IFC: ...] with crisp badge styling
      const processed = md.replace(
        /\[(Doc|IFC):\s*([^\]]+)\]/g,
        '<span class="inline-citation-tag" data-type="$1">[$1: $2]</span>'
      );
      return marked.parse(processed, { gfm: true, breaks: true }) as string;
    } catch {
      return md;
    }
  }

  // Format content: handle code blocks and render markdown for text parts
  let formattedBlocks = $derived.by(() => {
    if (!content) return [];
    // Split by code blocks ```
    const parts = content.split(/(```[\s\S]*?```)/g);
    return parts.map((part) => {
      if (part.startsWith("```") && part.endsWith("```")) {
        const lines = part.slice(3, -3).trim().split("\n");
        const lang = lines[0].trim();
        const code = lines.slice(lang ? 1 : 0).join("\n");
        return { isCode: true, lang, code, html: "" };
      }
      return { isCode: false, text: part, html: renderMarkdown(part) };
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
        {:else if isUser}
          <div class="space-y-2 whitespace-pre-wrap">
            {block.text}
          </div>
        {:else}
          <div class="prose-copilot text-fg-primary text-sm leading-relaxed space-y-2">
            {@html block.html}
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

<style>
  :global(.prose-copilot h1) {
    font-size: 1.15rem;
    font-weight: 600;
    margin-top: 0.75rem;
    margin-bottom: 0.35rem;
    color: var(--color-fg-primary);
  }
  :global(.prose-copilot h2) {
    font-size: 1.05rem;
    font-weight: 600;
    margin-top: 0.65rem;
    margin-bottom: 0.3rem;
    color: var(--color-fg-primary);
  }
  :global(.prose-copilot h3) {
    font-size: 0.95rem;
    font-weight: 600;
    margin-top: 0.5rem;
    margin-bottom: 0.25rem;
    color: var(--color-fg-primary);
  }
  :global(.prose-copilot p) {
    margin-top: 0.35rem;
    margin-bottom: 0.35rem;
    line-height: 1.6;
    color: var(--color-fg-secondary);
  }
  :global(.prose-copilot strong) {
    font-weight: 600;
    color: var(--color-fg-primary);
  }
  :global(.prose-copilot ul) {
    list-style-type: disc;
    padding-left: 1.25rem;
    margin-top: 0.4rem;
    margin-bottom: 0.4rem;
    color: var(--color-fg-secondary);
  }
  :global(.prose-copilot ol) {
    list-style-type: decimal;
    padding-left: 1.25rem;
    margin-top: 0.4rem;
    margin-bottom: 0.4rem;
    color: var(--color-fg-secondary);
  }
  :global(.prose-copilot li) {
    margin-top: 0.2rem;
    margin-bottom: 0.2rem;
    line-height: 1.5;
  }
  :global(.prose-copilot table) {
    width: 100%;
    margin-top: 0.75rem;
    margin-bottom: 0.75rem;
    border-collapse: collapse;
    font-size: 0.8rem;
    border: 1px solid var(--color-border-subtle);
    border-radius: 0.375rem;
    overflow: hidden;
  }
  :global(.prose-copilot th) {
    background-color: var(--color-surface-hover);
    padding: 0.4rem 0.6rem;
    font-weight: 600;
    text-align: left;
    color: var(--color-fg-primary);
    border-bottom: 1px solid var(--color-border-subtle);
  }
  :global(.prose-copilot td) {
    padding: 0.4rem 0.6rem;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border-subtle) 60%, transparent);
    color: var(--color-fg-secondary);
  }
  :global(.prose-copilot blockquote) {
    border-left: 3px solid var(--color-accent);
    padding-left: 0.75rem;
    margin: 0.5rem 0;
    font-style: italic;
    color: var(--color-fg-muted);
  }
  :global(.prose-copilot code:not(pre code)) {
    font-family: var(--font-mono, monospace);
    font-size: 0.8em;
    padding: 0.15rem 0.35rem;
    border-radius: 0.25rem;
    background-color: var(--color-surface-hover);
    border: 1px solid var(--color-border-subtle);
    color: var(--color-accent);
  }
  :global(.prose-copilot hr) {
    margin: 0.75rem 0;
    border: 0;
    border-top: 1px solid var(--color-border-subtle);
  }
  :global(.inline-citation-tag) {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.1rem 0.35rem;
    border-radius: 0.25rem;
    font-size: 0.75rem;
    font-family: var(--font-mono, monospace);
    background-color: color-mix(in srgb, var(--color-accent) 12%, transparent);
    color: var(--color-accent);
    border: 1px solid color-mix(in srgb, var(--color-accent) 25%, transparent);
    margin: 0 0.15rem;
  }
</style>
