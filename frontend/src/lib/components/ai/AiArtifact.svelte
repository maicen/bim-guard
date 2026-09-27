<!--
  AiArtifact — canvas & inspection side panel.
  Inspired by shadcn.io/ai/artifact & ai/canvas:
  Provides a side drawer/surface for inspecting executed Cypher queries,
  subgraphs, or deep IFC element metadata with 3D viewer isolation triggers.
-->
<script lang="ts">
  import { X, Copy, Check, ExternalLink, Database, Box, FileText } from "lucide-svelte";
  import type { GraphRagCitation } from "../../types";

  interface Props {
    citation?: GraphRagCitation | null;
    cypherQuery?: string | null;
    subgraphData?: {
      nodes?: Array<{ id: string; label: string; type: string }>;
      edges?: Array<{ source: string; target: string; label?: string }>;
    } | null;
    onClose: () => void;
    onIsolateElement?: (guid: string) => void;
    onOpenDocument?: (docId: number, page?: number | null) => void;
  }

  let {
    citation = null,
    cypherQuery = null,
    subgraphData = null,
    onClose,
    onIsolateElement,
    onOpenDocument,
  }: Props = $props();

  let activeTab = $state<"detail" | "cypher" | "graph">("detail");
  let copied = $state(false);

  function copyText(val: string) {
    navigator.clipboard.writeText(val);
    copied = true;
    setTimeout(() => (copied = false), 2000);
  }
</script>

<div class="h-full w-full flex flex-col bg-surface-card border-l border-border-default overflow-hidden">
  <!-- Header -->
  <div class="flex items-center justify-between px-4 py-3 border-b border-border-default bg-surface-hover/30">
    <div class="flex items-center gap-2 min-w-0">
      {#if citation?.source_type === "model"}
        <Box class="w-4 h-4 text-accent shrink-0" />
      {:else if citation?.source_type === "document"}
        <FileText class="w-4 h-4 text-info shrink-0" />
      {:else}
        <Database class="w-4 h-4 text-accent shrink-0" />
      {/if}

      <div class="truncate">
        <h3 class="font-semibold text-sm text-fg-primary truncate">
          {citation?.title || (cypherQuery ? "Neo4j Cypher Execution" : "Knowledge Artifact")}
        </h3>
        <p class="text-[11px] text-fg-muted font-mono truncate">
          {citation?.reference || "Graph Intelligence Inspector"}
        </p>
      </div>
    </div>

    <button
      type="button"
      onclick={onClose}
      class="p-1 rounded-md text-fg-muted hover:text-fg-primary hover:bg-surface-hover transition-colors"
      title="Close inspector"
    >
      <X class="w-4 h-4" />
    </button>
  </div>

  <!-- Content Tabs -->
  <div class="flex items-center gap-1 px-4 py-2 border-b border-border-subtle bg-surface-canvas/50 text-xs">
    <button
      type="button"
      onclick={() => (activeTab = "detail")}
      class="px-2.5 py-1 rounded font-medium transition-colors {activeTab === 'detail' ? 'bg-surface-selected text-fg-primary' : 'text-fg-muted hover:text-fg-primary'}"
    >
      Details
    </button>
    {#if cypherQuery}
      <button
        type="button"
        onclick={() => (activeTab = "cypher")}
        class="px-2.5 py-1 rounded font-medium transition-colors {activeTab === 'cypher' ? 'bg-surface-selected text-fg-primary' : 'text-fg-muted hover:text-fg-primary'}"
      >
        Cypher Query
      </button>
    {/if}
    {#if subgraphData?.nodes && subgraphData.nodes.length > 0}
      <button
        type="button"
        onclick={() => (activeTab = "graph")}
        class="px-2.5 py-1 rounded font-medium transition-colors {activeTab === 'graph' ? 'bg-surface-selected text-fg-primary' : 'text-fg-muted hover:text-fg-primary'}"
      >
        Subgraph ({subgraphData.nodes.length})
      </button>
    {/if}
  </div>

  <!-- Body -->
  <div class="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
    {#if activeTab === "detail"}
      {#if citation}
        <!-- Citation Details -->
        <div class="space-y-3">
          <div class="p-3 rounded-lg border border-border-subtle bg-surface-canvas space-y-1.5">
            <span class="text-[10px] font-mono uppercase text-fg-muted">Full Evidence Excerpt</span>
            <p class="text-xs text-fg-primary leading-relaxed whitespace-pre-wrap">
              {citation.snippet || "No detailed excerpt stored."}
            </p>
          </div>

          <!-- Metadata Grid -->
          <div class="grid grid-cols-2 gap-2 text-[11px]">
            <div class="p-2.5 rounded-lg border border-border-subtle bg-surface-canvas/60 space-y-0.5">
              <span class="text-fg-muted">Source Type</span>
              <p class="font-semibold text-fg-primary capitalize">{citation.source_type}</p>
            </div>

            {#if citation.page_number}
              <div class="p-2.5 rounded-lg border border-border-subtle bg-surface-canvas/60 space-y-0.5">
                <span class="text-fg-muted">Page Number</span>
                <p class="font-semibold text-fg-primary">Page {citation.page_number}</p>
              </div>
            {/if}

            {#if citation.ifc_type}
              <div class="p-2.5 rounded-lg border border-border-subtle bg-surface-canvas/60 space-y-0.5">
                <span class="text-fg-muted">IFC Entity Class</span>
                <p class="font-mono font-semibold text-fg-primary">{citation.ifc_type}</p>
              </div>
            {/if}

            {#if citation.element_guid}
              <div class="p-2.5 rounded-lg border border-border-subtle bg-surface-canvas/60 space-y-0.5 col-span-2">
                <span class="text-fg-muted">IFC GlobalId (GUID)</span>
                <p class="font-mono text-fg-primary break-all">{citation.element_guid}</p>
              </div>
            {/if}
          </div>

          <!-- Supporting Properties -->
          {#if citation.properties && Object.keys(citation.properties).length > 0}
            <div class="space-y-1.5">
              <span class="text-[11px] font-semibold text-fg-muted uppercase tracking-wider">
                Extracted Attributes & Psets
              </span>
              <div class="rounded-lg border border-border-subtle bg-surface-canvas divide-y divide-border-subtle/60 text-xs">
                {#each Object.entries(citation.properties) as [k, v]}
                  <div class="flex items-center justify-between p-2">
                    <span class="font-mono text-fg-secondary">{k}</span>
                    <span class="font-medium text-fg-primary">{String(v)}</span>
                  </div>
                {/each}
              </div>
            </div>
          {/if}

          <!-- Action Buttons -->
          <div class="pt-2 flex flex-wrap gap-2">
            {#if citation.element_guid && onIsolateElement}
              <button
                type="button"
                onclick={() => onIsolateElement?.(citation.element_guid!)}
                class="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-accent text-white font-medium hover:bg-accent/90 transition-colors shadow-xs"
              >
                <Box class="w-4 h-4" />
                <span>Isolate in 3D BIM Viewer</span>
              </button>
            {/if}

            {#if citation.source_type === "document" && onOpenDocument}
              <button
                type="button"
                onclick={() => onOpenDocument?.(1, citation.page_number)}
                class="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-info-bg text-info border border-info-border font-medium hover:bg-info/20 transition-colors"
              >
                <FileText class="w-4 h-4" />
                <span>Open in Document Viewer</span>
              </button>
            {/if}
          </div>
        </div>
      {:else}
        <div class="p-6 text-center text-fg-muted">
          Select an inline citation or tool call from the conversation to inspect grounded details.
        </div>
      {/if}
    {:else if activeTab === "cypher"}
      <!-- Cypher Tab -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <span class="font-mono text-[11px] text-fg-muted">Neo4j Cypher Execution</span>
          <button
            type="button"
            onclick={() => copyText(cypherQuery || "")}
            class="inline-flex items-center gap-1 text-accent text-xs hover:underline"
          >
            {#if copied}
              <Check class="w-3.5 h-3.5 text-success" />
              <span>Copied</span>
            {:else}
              <Copy class="w-3.5 h-3.5" />
              <span>Copy</span>
            {/if}
          </button>
        </div>

        <pre class="p-3 rounded-lg border border-border-default bg-surface-canvas font-mono text-xs text-fg-primary leading-relaxed overflow-x-auto whitespace-pre-wrap">
          {cypherQuery}
        </pre>
      </div>
    {:else if activeTab === "graph"}
      <!-- Subgraph Nodes -->
      <div class="space-y-2">
        <span class="font-mono text-[11px] text-fg-muted">Retrieved Subgraph Nodes</span>
        <div class="space-y-1.5">
          {#each subgraphData?.nodes || [] as node (node.id)}
            <div class="flex items-center justify-between p-2 rounded border border-border-subtle bg-surface-canvas text-xs font-mono">
              <span class="text-fg-primary truncate max-w-[200px]">{node.label}</span>
              <span class="px-1.5 py-0.2 rounded bg-surface-hover text-fg-muted text-[10px]">{node.type}</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>
