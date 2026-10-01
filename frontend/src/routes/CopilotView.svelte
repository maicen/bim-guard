<!--
  CopilotView — dedicated Graph-RAG Copilot workspace page.
  Features ChatGPT-style persistent history sidebar on the left,
  conversational agent with grounded citations in the center,
  and collapsible Neo4j knowledge artifact inspector on the right.
-->
<script lang="ts">
  import { onMount } from "svelte";
  import { push, router } from "svelte-spa-router";
  import {
    Sparkles,
    RefreshCw,
  } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import AiChatSidebar from "../lib/components/ai/AiChatSidebar.svelte";
  import AiChatbot from "../lib/components/ai/AiChatbot.svelte";
  import { copilotStore } from "../lib/stores/copilotStore.svelte";
  import { authState } from "../lib/auth.svelte";
  import { projectsApi } from "../lib/api";
  import type { Project } from "../lib/types";

  interface Props {
    projectId?: number | null;
  }

  let { projectId = null }: Props = $props();

  let targetProjectId = $derived(projectId);
  let projects = $state<Project[]>([]);
  let loadingProjects = $state(false);

  // Read URL query params (?thread=...)
  let queryParams = $derived(new URLSearchParams(router.querystring || ""));
  let threadParam = $derived(queryParams.get("thread"));

  async function loadProjects() {
    loadingProjects = true;
    try {
      const res = await projectsApi.list();
      projects = res.projects || [];
    } catch (err) {
      console.warn("Could not load projects for CopilotView:", err);
    } finally {
      loadingProjects = false;
    }
  }

  onMount(() => {
    loadProjects();
  });

  $effect(() => {
    if (targetProjectId) {
      copilotStore.loadConversations(targetProjectId, threadParam);
    }
  });

  function handleSelectConversation(convId: string) {
    if (targetProjectId) {
      push(`/copilot?project_id=${targetProjectId}&thread=${encodeURIComponent(convId)}`);
    }
  }

  function handleNewChat() {
    if (targetProjectId) {
      push(`/copilot?project_id=${targetProjectId}`);
    }
  }

  function handleProjectChange(newId: number) {
    push(`/copilot?project_id=${newId}`);
  }
</script>

<div class="flex flex-col h-[calc(100vh-4rem)] p-4 md:p-6 space-y-4 overflow-hidden">
  <!-- View Header -->
  <PageHeader
    category="Coordination"
    title="Graph-RAG Copilot"
    subtitle="Conversational engineering compliance intelligence connecting specification clauses, spatial containment, and IFC model elements."
    icon={Sparkles}
  >
    {#snippet actions()}
      <div class="flex items-center gap-2">
        {#if targetProjectId}
          <button
            type="button"
            onclick={() => copilotStore.loadConversations(targetProjectId)}
            class="p-2 rounded-xl border border-border-default bg-surface-card text-fg-muted hover:text-fg-primary hover:bg-surface-hover transition-colors shadow-2xs cursor-pointer"
            title="Refresh conversations"
          >
            <RefreshCw class="w-4 h-4 {copilotStore.isLoadingList ? 'animate-spin' : ''}" />
          </button>
        {/if}

        {#if projects.length > 0}
          <div class="flex items-center gap-2 text-xs">
            <span class="text-fg-muted font-medium">Project:</span>
            <select
              value={targetProjectId ?? ""}
              onchange={(e) => {
                const val = Number((e.target as HTMLSelectElement).value);
                if (val) handleProjectChange(val);
              }}
              class="px-2.5 py-1.5 rounded-xl border border-border-default bg-surface-card text-fg-primary text-xs font-semibold focus:ring-2 focus:ring-accent focus:outline-hidden cursor-pointer"
            >
              <option value="" disabled>Select project...</option>
              {#each projects as p}
                <option value={p.id}>{p.name} ({p.project_code})</option>
              {/each}
            </select>
          </div>
        {/if}
      </div>
    {/snippet}
  </PageHeader>

  <!-- Workspace Canvas -->
  {#if !targetProjectId}
    <div class="flex-1 flex items-center justify-center bg-surface-card rounded-2xl border border-border-default p-8 shadow-xs">
      <EmptyState
        title="Select a Project"
        description="Choose a project above to load its Graph-RAG knowledge graph, IFC building elements, specification trees, and persistent conversations."
        icon={Sparkles}
      >
        {#if projects.length > 0}
          <div class="flex flex-wrap gap-2 justify-center max-w-md pt-2">
            {#each projects.slice(0, 4) as p}
              <button
                type="button"
                onclick={() => handleProjectChange(p.id)}
                class="px-3 py-1.5 rounded-xl text-xs font-medium border border-border-interactive bg-surface-hover text-fg-primary hover:border-accent hover:text-accent transition-colors cursor-pointer"
              >
                {p.name}
              </button>
            {/each}
          </div>
        {/if}
      </EmptyState>
    </div>
  {:else}
    <div class="flex-1 flex min-h-0 bg-surface-card rounded-2xl border border-border-default overflow-hidden shadow-xs">
      <!-- Left: Persistent ChatGPT-Style History Sidebar -->
      <AiChatSidebar
        projectId={targetProjectId}
        onSelect={handleSelectConversation}
        onNewChat={handleNewChat}
      />

      <!-- Right: Main Chat Area with Streaming, Turns, and Artifact Inspector -->
      <main class="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        <AiChatbot
          projectId={targetProjectId}
          persistent={true}
          onOpenDocument={(docId, page) => {
            const pageParam = page ? `&page=${page}` : "";
            const orgParam = authState.activeOrganizationId ? `&org=${authState.activeOrganizationId}` : "";
            const projParam = targetProjectId ? `&project_id=${targetProjectId}` : "";
            push(`/document?doc_id=${docId}${pageParam}${projParam}${orgParam}`);
          }}
          onIsolateElement={(guid) => {
            push(`/viewer?project_id=${targetProjectId}&guid=${encodeURIComponent(guid)}`);
          }}
        />
      </main>
    </div>
  {/if}
</div>
