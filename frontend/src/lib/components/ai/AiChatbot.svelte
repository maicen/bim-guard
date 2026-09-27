<!--
  AiChatbot — complete Graph-RAG conversational AI copilot.
  Inspired by shadcn.io/ai/chatbot & conversational AI architecture:
  Orchestrates real-time SSE streaming, message state, scope attachment,
  grounded inline citations, chain-of-thought milestones, and side artifact inspection.
-->
<script lang="ts">
  import { onMount, tick, untrack } from "svelte";
  import { Sparkles, Trash2, PanelRightClose, PanelRightOpen, Layers, Info } from "lucide-svelte";
  import AiConversation from "./AiConversation.svelte";
  import AiMessage, { type ChatMessage } from "./AiMessage.svelte";
  import AiPromptInput from "./AiPromptInput.svelte";
  import AiSuggestions from "./AiSuggestions.svelte";
  import AiLoader from "./AiLoader.svelte";
  import AiArtifact from "./AiArtifact.svelte";
  import { graphApi } from "../../api";
  import { toasts } from "../../toast.svelte";
  import type {
    GraphRagCitation,
    GraphRagContextSummary,
    GraphRagQueryRequest,
    GraphRagQueryResponse,
    GraphRagScope,
    GraphRagStep,
    GraphRagToolCall,
  } from "../../types";

  interface Props {
    projectId: number;
    initialScope?: GraphRagScope;
    initialDocumentId?: number | null;
    initialElementClass?: string | null;
    onIsolateElement?: (guid: string) => void;
    onOpenDocument?: (docId: number, page?: number | null) => void;
  }

  let {
    projectId,
    initialScope = "hybrid",
    initialDocumentId = null,
    initialElementClass = null,
    onIsolateElement,
    onOpenDocument,
  }: Props = $props();

  // State
  let scope = $state<GraphRagScope>(untrack(() => initialScope));
  let selectedDocId = $state<number | null>(untrack(() => initialDocumentId));
  let selectedElementClass = $state<string | null>(untrack(() => initialElementClass));

  let messages = $state<ChatMessage[]>([]);
  let isStreaming = $state(false);
  let stopStreamFn = $state<(() => void) | null>(null);

  let contextSummary = $state<GraphRagContextSummary | null>(null);
  let loadingContext = $state(false);

  // Active Artifact Inspection
  let activeCitation = $state<GraphRagCitation | null>(null);
  let activeCypher = $state<string | null>(null);
  let activeSubgraph = $state<{ nodes?: any[]; edges?: any[] } | null>(null);
  let showArtifactPanel = $state(false);

  // Suggestions
  let suggestions = $state<string[]>([
    "What are the egress door fire rating requirements in our project specification?",
    "How many corridor doors exist in this model and do any lack fire ratings?",
    "Do our Level 1 doors comply with the 60-minute fire resistance requirement?",
  ]);

  let conversationRef = $state<AiConversation | null>(null);
  let promptInputRef = $state<AiPromptInput | null>(null);

  // Load project graph context on mount
  async function loadContext() {
    if (!projectId) return;
    loadingContext = true;
    try {
      contextSummary = await graphApi.getRagContext(projectId);
    } catch (err) {
      console.warn("Could not load Graph-RAG context summary:", err);
    } finally {
      loadingContext = false;
    }
  }

  $effect(() => {
    if (projectId) {
      loadContext();
    }
  });

  // Handle Query Submission
  async function handleSubmit(queryText: string) {
    if (!queryText.trim() || isStreaming) return;

    const userMessageId = `user_${Date.now()}`;
    const assistantMessageId = `asst_${Date.now()}`;
    const timestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    // 1. Add User Turn
    messages = [
      ...messages,
      {
        id: userMessageId,
        role: "user",
        content: queryText,
        timestamp,
      },
    ];

    // 2. Prepare Assistant Turn
    const assistantTurn: ChatMessage = {
      id: assistantMessageId,
      role: "assistant",
      content: "",
      timestamp,
      citations: [],
      reasoning_steps: [],
      tool_calls: [],
      cypher_queries: [],
    };

    messages = [...messages, assistantTurn];
    isStreaming = true;

    await tick();
    conversationRef?.scrollToBottom(true);

    const payload: GraphRagQueryRequest = {
      query: queryText,
      scope,
      document_id: selectedDocId,
      element_class: selectedElementClass,
    };

    // 3. Initiate SSE Streaming
    const cancelFn = graphApi.streamRag(projectId, payload, {
      onStep(step: GraphRagStep) {
        const turn = messages.find((m) => m.id === assistantMessageId);
        if (turn) {
          turn.reasoning_steps = turn.reasoning_steps || [];
          const idx = turn.reasoning_steps.findIndex((s) => s.step_index === step.step_index);
          if (idx >= 0) {
            turn.reasoning_steps[idx] = step;
          } else {
            turn.reasoning_steps.push(step);
          }
          messages = [...messages];
        }
      },
      onToolCall(toolCall: GraphRagToolCall) {
        const turn = messages.find((m) => m.id === assistantMessageId);
        if (turn) {
          turn.tool_calls = turn.tool_calls || [];
          turn.tool_calls.push(toolCall);
          if (toolCall.cypher_query) {
            turn.cypher_queries = turn.cypher_queries || [];
            turn.cypher_queries.push(toolCall.cypher_query);
          }
          messages = [...messages];
        }
      },
      onCitation(citation: GraphRagCitation) {
        const turn = messages.find((m) => m.id === assistantMessageId);
        if (turn) {
          turn.citations = turn.citations || [];
          if (!turn.citations.some((c) => c.id === citation.id)) {
            turn.citations.push(citation);
          }
          messages = [...messages];
        }
      },
      onToken(token: string) {
        const turn = messages.find((m) => m.id === assistantMessageId);
        if (turn) {
          turn.content += token;
          messages = [...messages];
        }
      },
      onDone(result: GraphRagQueryResponse) {
        const turn = messages.find((m) => m.id === assistantMessageId);
        if (turn) {
          if (!turn.content && result.answer) {
            turn.content = result.answer;
          }
          if (result.suggested_followups && result.suggested_followups.length > 0) {
            suggestions = result.suggested_followups;
          }
          messages = [...messages];
        }
        isStreaming = false;
        stopStreamFn = null;
      },
      onError(err: string) {
        toasts.error(`Graph-RAG error: ${err}`);
        isStreaming = false;
        stopStreamFn = null;
      },
    });

    stopStreamFn = cancelFn;
  }

  function handleStop() {
    if (stopStreamFn) {
      stopStreamFn();
      stopStreamFn = null;
    }
    isStreaming = false;
  }

  function clearChat() {
    messages = [];
    activeCitation = null;
    activeCypher = null;
    showArtifactPanel = false;
  }

  function handleSelectCitation(citation: GraphRagCitation) {
    activeCitation = citation;
    showArtifactPanel = true;
  }

  let selectedDocTitle = $derived.by(() => {
    if (!selectedDocId || !contextSummary) return null;
    const d = contextSummary.documents.find((doc) => doc.id === selectedDocId);
    return d ? d.title : null;
  });
</script>

<div class="flex h-full w-full bg-surface-canvas rounded-xl border border-border-default overflow-hidden shadow-xs">
  <!-- Main Chat Flow -->
  <div class="flex-1 flex flex-col min-w-0 h-full">
    <!-- Chat Topbar -->
    <div class="flex items-center justify-between px-4 py-2.5 border-b border-border-default bg-surface-card text-xs">
      <div class="flex items-center gap-2">
        <div class="w-6 h-6 rounded-md bg-accent/15 border border-accent/30 text-accent flex items-center justify-center">
          <Sparkles class="w-3.5 h-3.5" />
        </div>
        <div>
          <h2 class="font-semibold text-fg-primary text-sm leading-tight">
            Graph-RAG Compliance Copilot
          </h2>
          <p class="text-[11px] text-fg-muted font-mono">
            {#if contextSummary?.has_ifc_model}
              {contextSummary.total_elements} IFC nodes connected
            {:else}
              Model graph connecting
            {/if}
            • {contextSummary?.documents.length || 0} document trees
          </p>
        </div>
      </div>

      <div class="flex items-center gap-1.5">
        {#if messages.length > 0}
          <button
            type="button"
            onclick={clearChat}
            class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-fg-muted hover:text-critical hover:bg-critical-bg transition-colors"
            title="Clear conversation history"
          >
            <Trash2 class="w-3.5 h-3.5" />
            <span>Clear</span>
          </button>
        {/if}

        <button
          type="button"
          onclick={() => (showArtifactPanel = !showArtifactPanel)}
          class="p-1.5 rounded-md text-fg-muted hover:text-fg-primary hover:bg-surface-hover transition-colors"
          title={showArtifactPanel ? "Hide Artifact Inspector" : "Show Artifact Inspector"}
        >
          {#if showArtifactPanel}
            <PanelRightClose class="w-4 h-4 text-accent" />
          {:else}
            <PanelRightOpen class="w-4 h-4" />
          {/if}
        </button>
      </div>
    </div>

    <!-- Message Scroller / Turn List -->
    <AiConversation bind:this={conversationRef} {isStreaming}>
      {#if messages.length === 0}
        <!-- Zero State Welcome -->
        <div class="h-full flex flex-col items-center justify-center p-8 text-center max-w-lg mx-auto space-y-4 my-auto">
          <div class="w-12 h-12 rounded-2xl bg-accent/15 border border-accent/30 text-accent flex items-center justify-center shadow-xs">
            <Layers class="w-6 h-6" />
          </div>

          <div class="space-y-1.5">
            <h3 class="text-base font-semibold text-fg-primary">
              Ask about Documents, BIM Models, or Cross-Domain Compliance
            </h3>
            <p class="text-xs text-fg-secondary leading-relaxed">
              Graph-RAG searches your project's Neo4j knowledge graph linking specification clauses,
              spatial containment, and IFC model properties to deliver grounded answers with direct citations.
            </p>
          </div>

          <AiSuggestions
            {suggestions}
            onSelect={(prompt) => {
              promptInputRef?.setPrompt(prompt);
              handleSubmit(prompt);
            }}
          />
        </div>
      {:else}
        {#each messages as message (message.id)}
          <AiMessage
            {message}
            {isStreaming}
            onCitationSelect={handleSelectCitation}
            onRegenerate={() => {
              // Retry last user message
              const lastUser = [...messages].reverse().find((m) => m.role === "user");
              if (lastUser) handleSubmit(lastUser.content);
            }}
          />
        {/each}

        {#if isStreaming && messages[messages.length - 1]?.role === "assistant" && !messages[messages.length - 1]?.content}
          <AiLoader statusText="Traversing Neo4j knowledge graph & synthesizing answer..." />
        {/if}

        {#if !isStreaming && messages.length > 0}
          <div class="ml-11 max-w-[85%]">
            <AiSuggestions
              {suggestions}
              onSelect={(prompt) => {
                promptInputRef?.setPrompt(prompt);
                handleSubmit(prompt);
              }}
            />
          </div>
        {/if}
      {/if}
    </AiConversation>

    <!-- Bottom Input Controls -->
    <AiPromptInput
      bind:this={promptInputRef}
      {scope}
      {isStreaming}
      {selectedDocTitle}
      {selectedElementClass}
      availableDocs={contextSummary?.documents || []}
      availableClasses={contextSummary?.ifc_classes || []}
      onSubmit={handleSubmit}
      onStop={handleStop}
      onScopeChange={(newScope) => (scope = newScope)}
      onDocChange={(docId) => (selectedDocId = docId)}
      onClassChange={(cls) => (selectedElementClass = cls)}
    />
  </div>

  <!-- Side Artifact Inspector Panel -->
  {#if showArtifactPanel}
    <div class="w-80 md:w-96 shrink-0 h-full border-l border-border-default">
      <AiArtifact
        citation={activeCitation}
        cypherQuery={activeCypher}
        subgraphData={activeSubgraph}
        onClose={() => (showArtifactPanel = false)}
        {onIsolateElement}
        {onOpenDocument}
      />
    </div>
  {/if}
</div>
