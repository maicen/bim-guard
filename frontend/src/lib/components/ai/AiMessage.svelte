<!--
  AiMessage — complete conversation turn.
  Inspired by shadcn.io/ai/message & June 2026 Message component:
  Assembles the turn bubble, chain-of-thought reasoning, tool execution cards,
  grounded sources, and action toolbar into a single turn element.
-->
<script lang="ts">
  import AiBubble from "./AiBubble.svelte";
  import AiReasoning from "./AiReasoning.svelte";
  import AiTool from "./AiTool.svelte";
  import AiSources from "./AiSources.svelte";
  import AiActions from "./AiActions.svelte";
  import type { GraphRagCitation, GraphRagStep, GraphRagToolCall } from "../../types";

  export interface ChatMessage {
    id: string;
    role: "user" | "assistant" | "system";
    content: string;
    timestamp?: string;
    citations?: GraphRagCitation[];
    reasoning_steps?: GraphRagStep[];
    tool_calls?: GraphRagToolCall[];
    cypher_queries?: string[];
  }

  interface Props {
    message: ChatMessage;
    isStreaming?: boolean;
    onCitationSelect?: (citation: GraphRagCitation) => void;
    onRegenerate?: () => void;
    onExportBcf?: () => void;
  }

  let {
    message,
    isStreaming = false,
    onCitationSelect,
    onRegenerate,
    onExportBcf,
  }: Props = $props();
</script>

<div class="space-y-2 py-2">
  <!-- Reasoning / Chain of Thought if present -->
  {#if message.reasoning_steps && message.reasoning_steps.length > 0}
    <div class="ml-11 max-w-[85%]">
      <AiReasoning
        steps={message.reasoning_steps}
        {isStreaming}
        defaultOpen={isStreaming}
      />
    </div>
  {/if}

  <!-- Tool execution cards if present -->
  {#if message.tool_calls && message.tool_calls.length > 0}
    <div class="ml-11 max-w-[85%] space-y-1.5">
      {#each message.tool_calls as toolCall, idx (toolCall.tool_name + idx)}
        <AiTool {toolCall} defaultExpanded={false} />
      {/each}
    </div>
  {/if}

  <!-- Main Turn Bubble -->
  <AiBubble
    role={message.role}
    content={message.content}
    timestamp={message.timestamp}
    citations={message.citations}
    {onCitationSelect}
  />

  <!-- Bottom Sources List if multiple sources are grounded -->
  {#if message.citations && message.citations.length > 0 && message.role === "assistant"}
    <div class="ml-11 max-w-[85%]">
      <AiSources citations={message.citations} onSelect={onCitationSelect} />
    </div>
  {/if}

  <!-- Action Toolbar for Assistant Replies -->
  {#if message.role === "assistant" && message.content && !isStreaming}
    <div class="ml-11 max-w-[85%]">
      <AiActions
        content={message.content}
        {onRegenerate}
        {onExportBcf}
      />
    </div>
  {/if}
</div>
