<!--
  AiAttachments — scope selector & attachment badges.
  Inspired by shadcn.io/ai/attachments & June 2026 Attachment component:
  Displays active Document and IFC Model scopes, and lets the user quickly
  switch focus between Document, Model, or Hybrid cross-domain analysis.
-->
<script lang="ts">
  import { FileText, Box, Layers, Check, ChevronDown } from "lucide-svelte";
  import type { GraphRagScope } from "../../types";

  interface Props {
    scope: GraphRagScope;
    selectedDocTitle?: string | null;
    selectedElementClass?: string | null;
    availableDocs?: Array<{ id: number; title: string }>;
    availableClasses?: Array<{ class_name: string; count: number }>;
    onScopeChange: (scope: GraphRagScope) => void;
    onDocChange?: (docId: number | null) => void;
    onClassChange?: (className: string | null) => void;
  }

  let {
    scope = "hybrid",
    selectedDocTitle = null,
    selectedElementClass = null,
    availableDocs = [],
    availableClasses = [],
    onScopeChange,
    onDocChange,
    onClassChange,
  }: Props = $props();

  let showScopeMenu = $state(false);
  let showDocMenu = $state(false);
  let showClassMenu = $state(false);
</script>

<div class="flex flex-wrap items-center gap-1.5 py-1.5 px-2 bg-surface-canvas/60 rounded-md border border-border-subtle text-xs">
  <span class="text-fg-muted font-medium text-[11px] uppercase tracking-wider mr-1">
    Knowledge Scope:
  </span>

  <!-- Scope Toggle Badge -->
  <div class="relative">
    <button
      type="button"
      onclick={() => (showScopeMenu = !showScopeMenu)}
      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md font-medium text-xs border transition-colors
             {scope === 'hybrid'
               ? 'bg-accent/10 border-accent/40 text-accent hover:bg-accent/20'
               : scope === 'document'
                 ? 'bg-info-bg border-info-border text-info hover:bg-info/20'
                 : 'bg-success-bg border-success-border text-success hover:bg-success/20'}"
    >
      {#if scope === "hybrid"}
        <Layers class="w-3.5 h-3.5" />
        <span>Hybrid (Doc + Model)</span>
      {:else if scope === "document"}
        <FileText class="w-3.5 h-3.5" />
        <span>Document Only</span>
      {:else}
        <Box class="w-3.5 h-3.5" />
        <span>IFC Model Only</span>
      {/if}
      <ChevronDown class="w-3 h-3 opacity-75" />
    </button>

    {#if showScopeMenu}
      <div
        class="absolute left-0 top-full mt-1 w-48 rounded-lg border border-border-default bg-surface-overlay shadow-lg p-1 z-50 space-y-0.5"
      >
        <button
          type="button"
          onclick={() => {
            onScopeChange("hybrid");
            showScopeMenu = false;
          }}
          class="w-full flex items-center justify-between px-2.5 py-1.5 rounded text-left hover:bg-surface-hover text-fg-primary text-xs"
        >
          <div class="flex items-center gap-2">
            <Layers class="w-3.5 h-3.5 text-accent" />
            <span>Hybrid (Both)</span>
          </div>
          {#if scope === "hybrid"}<Check class="w-3.5 h-3.5 text-accent" />{/if}
        </button>

        <button
          type="button"
          onclick={() => {
            onScopeChange("document");
            showScopeMenu = false;
          }}
          class="w-full flex items-center justify-between px-2.5 py-1.5 rounded text-left hover:bg-surface-hover text-fg-primary text-xs"
        >
          <div class="flex items-center gap-2">
            <FileText class="w-3.5 h-3.5 text-info" />
            <span>Document Only</span>
          </div>
          {#if scope === "document"}<Check class="w-3.5 h-3.5 text-info" />{/if}
        </button>

        <button
          type="button"
          onclick={() => {
            onScopeChange("model");
            showScopeMenu = false;
          }}
          class="w-full flex items-center justify-between px-2.5 py-1.5 rounded text-left hover:bg-surface-hover text-fg-primary text-xs"
        >
          <div class="flex items-center gap-2">
            <Box class="w-3.5 h-3.5 text-success" />
            <span>IFC Model Only</span>
          </div>
          {#if scope === "model"}<Check class="w-3.5 h-3.5 text-success" />{/if}
        </button>
      </div>
    {/if}
  </div>

  <!-- Document Focus Attachment -->
  {#if (scope === "document" || scope === "hybrid") && availableDocs.length > 0}
    <div class="relative">
      <button
        type="button"
        onclick={() => (showDocMenu = !showDocMenu)}
        class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded border border-border-default bg-surface-card hover:bg-surface-hover text-fg-secondary text-[11px] transition-colors"
      >
        <FileText class="w-3 h-3 text-info" />
        <span class="truncate max-w-[140px] font-medium">
          {selectedDocTitle || "All Project Docs"}
        </span>
        <ChevronDown class="w-2.5 h-2.5 opacity-60" />
      </button>

      {#if showDocMenu}
        <div
          class="absolute left-0 top-full mt-1 w-56 rounded-lg border border-border-default bg-surface-overlay shadow-lg p-1 z-50 max-h-48 overflow-y-auto space-y-0.5 text-xs"
        >
          <button
            type="button"
            onclick={() => {
              onDocChange?.(null);
              showDocMenu = false;
            }}
            class="w-full text-left px-2 py-1 rounded hover:bg-surface-hover text-fg-primary font-medium"
          >
            All Project Documents
          </button>
          {#each availableDocs as doc (doc.id)}
            <button
              type="button"
              onclick={() => {
                onDocChange?.(doc.id);
                showDocMenu = false;
              }}
              class="w-full text-left px-2 py-1 rounded hover:bg-surface-hover text-fg-secondary truncate"
            >
              {doc.title}
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {/if}

  <!-- IFC Element Class Attachment -->
  {#if (scope === "model" || scope === "hybrid") && availableClasses.length > 0}
    <div class="relative">
      <button
        type="button"
        onclick={() => (showClassMenu = !showClassMenu)}
        class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded border border-border-default bg-surface-card hover:bg-surface-hover text-fg-secondary text-[11px] transition-colors"
      >
        <Box class="w-3 h-3 text-accent" />
        <span class="truncate max-w-[120px] font-medium">
          {selectedElementClass || "All IFC Classes"}
        </span>
        <ChevronDown class="w-2.5 h-2.5 opacity-60" />
      </button>

      {#if showClassMenu}
        <div
          class="absolute left-0 top-full mt-1 w-52 rounded-lg border border-border-default bg-surface-overlay shadow-lg p-1 z-50 max-h-48 overflow-y-auto space-y-0.5 text-xs"
        >
          <button
            type="button"
            onclick={() => {
              onClassChange?.(null);
              showClassMenu = false;
            }}
            class="w-full text-left px-2 py-1 rounded hover:bg-surface-hover text-fg-primary font-medium"
          >
            All IFC Classes
          </button>
          {#each availableClasses as c (c.class_name)}
            <button
              type="button"
              onclick={() => {
                onClassChange?.(c.class_name);
                showClassMenu = false;
              }}
              class="w-full flex items-center justify-between px-2 py-1 rounded hover:bg-surface-hover text-fg-secondary font-mono text-[11px]"
            >
              <span>{c.class_name}</span>
              <span class="text-fg-muted font-sans text-[10px]">({c.count})</span>
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>
