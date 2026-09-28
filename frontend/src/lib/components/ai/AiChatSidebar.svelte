<!--
  AiChatSidebar — ChatGPT-style persistent conversation history sidebar.
  Supports date-grouped threads (Pinned, Today, Yesterday, Previous 7 Days,
  Previous 30 Days, Older), real-time title search, inline renaming,
  pinning/unpinning, and deletion with accessible confirmation modal.
-->
<script lang="ts">
  import {
    Plus,
    Search,
    Pin,
    PinOff,
    MoreHorizontal,
    Pencil,
    Trash2,
    Download,
    Check,
    X,
    ChevronDown,
    ChevronRight,
    MessageSquare,
    PanelLeftClose,
    PanelLeft,
    Sparkles,
  } from "lucide-svelte";
  import { DropdownMenu as Menu } from "bits-ui";
  import DropdownMenu from "../DropdownMenu.svelte";
  import ConfirmModal from "../ConfirmModal.svelte";
  import { Button, Input } from "../ui";
  import { copilotStore } from "../../stores/copilotStore.svelte";
  import type { ChatConversationSummary } from "../../types";

  interface Props {
    projectId: number;
    onSelect?: (conversationId: string) => void;
    onNewChat?: () => void;
  }

  let { projectId, onSelect, onNewChat }: Props = $props();

  // Rename Inline State
  let editingId = $state<string | null>(null);
  let editTitleText = $state("");

  // Delete Confirmation State
  let deleteModalOpen = $state(false);
  let conversationToDelete = $state<ChatConversationSummary | null>(null);

  // Collapsed Sections Accordion State
  let collapsedSections = $state<Record<string, boolean>>({});

  function toggleSection(sectionKey: string) {
    collapsedSections[sectionKey] = !collapsedSections[sectionKey];
  }

  function handleStartNew() {
    copilotStore.startNewConversation(projectId);
    onNewChat?.();
  }

  function handleSelect(id: string) {
    if (editingId) return;
    copilotStore.selectConversation(id, projectId);
    onSelect?.(id);
  }

  function startRename(conv: ChatConversationSummary) {
    editingId = conv.id;
    editTitleText = conv.title;
  }

  function commitRename() {
    if (editingId && editTitleText.trim()) {
      copilotStore.renameConversation(editingId, editTitleText.trim(), projectId);
    }
    editingId = null;
    editTitleText = "";
  }

  function cancelRename() {
    editingId = null;
    editTitleText = "";
  }

  function requestDelete(conv: ChatConversationSummary) {
    conversationToDelete = conv;
    deleteModalOpen = true;
  }

  function confirmDelete() {
    if (conversationToDelete) {
      copilotStore.deleteConversation(conversationToDelete.id, projectId);
      conversationToDelete = null;
    }
  }

  function exportConversation(conv: ChatConversationSummary) {
    const data = {
      title: conv.title,
      id: conv.id,
      scope: conv.scope,
      updated_at: conv.updated_at,
      messages: copilotStore.activeConversationId === conv.id ? copilotStore.activeMessages : [],
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${conv.title.replace(/[^a-zA-Z0-9_-]/g, "_")}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const SECTIONS = [
    { key: "pinned", label: "Pinned", icon: Pin },
    { key: "today", label: "Today" },
    { key: "yesterday", label: "Yesterday" },
    { key: "last7Days", label: "Previous 7 Days" },
    { key: "last30Days", label: "Previous 30 Days" },
    { key: "older", label: "Older" },
  ] as const;
</script>

<aside
  class="flex flex-col h-full bg-surface-card border-r border-border-default select-none transition-all duration-300 relative {copilotStore.isSidebarCollapsed
    ? 'w-14 items-center'
    : 'w-64 md:w-72'}"
>
  <!-- Sidebar Header: New Chat & Collapse Toggle -->
  <div class="p-3 border-b border-border-default flex items-center justify-between gap-2 shrink-0 w-full">
    {#if !copilotStore.isSidebarCollapsed}
      <button
        type="button"
        onclick={handleStartNew}
        class="flex-1 flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold bg-accent/10 border border-accent/30 text-accent hover:bg-accent/20 transition-colors shadow-xs"
        title="Start a new Graph-RAG conversation"
      >
        <span class="flex items-center gap-2">
          <Plus class="w-4 h-4" />
          <span>New Chat</span>
        </span>
        <kbd class="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-mono rounded bg-surface-canvas text-fg-muted border border-border-default">
          ⌘N
        </kbd>
      </button>

      <button
        type="button"
        onclick={() => copilotStore.toggleSidebar()}
        class="p-2 rounded-lg text-fg-muted hover:text-fg-primary hover:bg-surface-hover transition-colors shrink-0"
        title="Collapse sidebar"
      >
        <PanelLeftClose class="w-4 h-4" />
      </button>
    {:else}
      <button
        type="button"
        onclick={handleStartNew}
        class="p-2.5 rounded-xl bg-accent/10 border border-accent/30 text-accent hover:bg-accent/20 transition-colors"
        title="New Chat"
      >
        <Plus class="w-4 h-4" />
      </button>
      <button
        type="button"
        onclick={() => copilotStore.toggleSidebar()}
        class="p-2 rounded-lg text-fg-muted hover:text-fg-primary hover:bg-surface-hover transition-colors mt-2"
        title="Expand sidebar"
      >
        <PanelLeft class="w-4 h-4" />
      </button>
    {/if}
  </div>

  {#if !copilotStore.isSidebarCollapsed}
    <!-- Search Filter Bar -->
    <div class="px-3 pt-2.5 pb-1 shrink-0 w-full">
      <div class="relative flex items-center">
        <Search class="absolute left-2.5 w-3.5 h-3.5 text-fg-muted pointer-events-none" />
        <input
          type="text"
          bind:value={copilotStore.searchQuery}
          placeholder="Search chats..."
          class="w-full pl-8 pr-7 py-1.5 text-xs rounded-lg bg-surface-canvas border border-border-subtle focus:border-border-interactive focus:outline-hidden text-fg-primary placeholder:text-fg-muted"
        />
        {#if copilotStore.searchQuery}
          <button
            type="button"
            onclick={() => (copilotStore.searchQuery = "")}
            class="absolute right-2 text-fg-muted hover:text-fg-primary"
            title="Clear search"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        {/if}
      </div>
    </div>

    <!-- Scrollable Conversation Groups -->
    <div class="flex-1 overflow-y-auto overflow-x-hidden px-2 py-2 space-y-4">
      {#if copilotStore.isLoadingList}
        <div class="p-4 space-y-2">
          {#each Array(4) as _}
            <div class="h-8 bg-surface-hover/60 rounded-lg animate-pulse"></div>
          {/each}
        </div>
      {:else if copilotStore.conversations.length === 0}
        <div class="p-6 text-center text-fg-muted text-xs space-y-2">
          <MessageSquare class="w-6 h-6 mx-auto opacity-40 text-fg-muted" />
          <p>No conversations yet.</p>
          <p class="text-[11px]">Start a new chat to begin querying BIM compliance models.</p>
        </div>
      {:else}
        {#each SECTIONS as section (section.key)}
          {@const items = copilotStore.groupedConversations[section.key]}
          {#if items && items.length > 0}
            <div class="space-y-1">
              <!-- Section Group Header -->
              <button
                type="button"
                onclick={() => toggleSection(section.key)}
                class="w-full flex items-center justify-between px-2 py-1 text-[11px] font-semibold text-fg-muted hover:text-fg-primary transition-colors tracking-wider uppercase"
              >
                <span class="flex items-center gap-1.5">
                  {#if section.key === "pinned"}
                    <Pin class="w-3 h-3 text-accent" />
                  {/if}
                  <span>{section.label}</span>
                  <span class="text-[10px] font-mono px-1 py-0.2 rounded-md bg-surface-hover text-fg-muted">
                    {items.length}
                  </span>
                </span>
                {#if collapsedSections[section.key]}
                  <ChevronRight class="w-3 h-3 text-fg-muted" />
                {:else}
                  <ChevronDown class="w-3 h-3 text-fg-muted" />
                {/if}
              </button>

              <!-- Section Item List -->
              {#if !collapsedSections[section.key]}
                <div class="space-y-0.5">
                  {#each items as conv (conv.id)}
                    {@const isActive = copilotStore.activeConversationId === conv.id}
                    <div
                      role="button"
                      tabindex="0"
                      onclick={() => handleSelect(conv.id)}
                      onkeydown={(e) => {
                        if (e.key === "Enter" || e.key === " ") handleSelect(conv.id);
                      }}
                      class="group relative flex items-center justify-between w-full px-2.5 py-2 rounded-xl text-xs transition-colors cursor-pointer {isActive
                        ? 'bg-surface-selected text-accent font-medium shadow-2xs border border-accent/20'
                        : 'text-fg-secondary hover:bg-surface-hover hover:text-fg-primary'}"
                    >
                      <!-- Left: Icon + Title or Editing Input -->
                      <div class="flex items-center gap-2 min-w-0 flex-1">
                        {#if conv.is_pinned}
                          <Pin class="w-3.5 h-3.5 shrink-0 text-accent" />
                        {:else}
                          <MessageSquare class="w-3.5 h-3.5 shrink-0 opacity-60 {isActive ? 'text-accent opacity-100' : ''}" />
                        {/if}

                        {#if editingId === conv.id}
                          <!-- Inline Rename Form -->
                          <div
                            role="presentation"
                            class="flex items-center gap-1 flex-1 min-w-0"
                            onclick={(e) => e.stopPropagation()}
                            onkeydown={(e) => e.stopPropagation()}
                          >
                            <input
                              type="text"
                              bind:value={editTitleText}
                              onkeydown={(e) => {
                                if (e.key === "Enter") commitRename();
                                if (e.key === "Escape") cancelRename();
                              }}
                              class="w-full px-1.5 py-0.5 text-xs bg-surface-canvas border border-border-interactive rounded text-fg-primary focus:outline-hidden"
                            />
                            <button
                              type="button"
                              onclick={commitRename}
                              class="p-1 hover:text-success text-fg-muted"
                              title="Save title"
                            >
                              <Check class="w-3 h-3" />
                            </button>
                            <button
                              type="button"
                              onclick={cancelRename}
                              class="p-1 hover:text-critical text-fg-muted"
                              title="Cancel"
                            >
                              <X class="w-3 h-3" />
                            </button>
                          </div>
                        {:else}
                          <span class="truncate flex-1" title={conv.title}>
                            {conv.title}
                          </span>
                        {/if}
                      </div>

                      <!-- Right: Options Menu Trigger (Visible on Hover or Active) -->
                      {#if editingId !== conv.id}
                        <div
                          role="presentation"
                          class="shrink-0 flex items-center {isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'} transition-opacity"
                          onclick={(e) => e.stopPropagation()}
                          onkeydown={(e) => e.stopPropagation()}
                        >
                          <DropdownMenu width="w-44">
                            {#snippet trigger({ props })}
                              <button
                                type="button"
                                {...props}
                                class="p-1 rounded-md text-fg-muted hover:text-fg-primary hover:bg-surface-canvas transition-colors"
                                title="Conversation actions"
                              >
                                <MoreHorizontal class="w-3.5 h-3.5" />
                              </button>
                            {/snippet}

                            <Menu.Item
                              onSelect={() => copilotStore.togglePin(conv.id, projectId)}
                              class="flex items-center gap-2 px-2.5 py-1.5 text-xs cursor-pointer text-fg-secondary hover:text-fg-primary hover:bg-surface-hover rounded-md"
                            >
                              {#if conv.is_pinned}
                                <PinOff class="w-3.5 h-3.5" />
                                <span>Unpin from top</span>
                              {:else}
                                <Pin class="w-3.5 h-3.5" />
                                <span>Pin to top</span>
                              {/if}
                            </Menu.Item>

                            <Menu.Item
                              onSelect={() => startRename(conv)}
                              class="flex items-center gap-2 px-2.5 py-1.5 text-xs cursor-pointer text-fg-secondary hover:text-fg-primary hover:bg-surface-hover rounded-md"
                            >
                              <Pencil class="w-3.5 h-3.5" />
                              <span>Rename</span>
                            </Menu.Item>

                            <Menu.Item
                              onSelect={() => exportConversation(conv)}
                              class="flex items-center gap-2 px-2.5 py-1.5 text-xs cursor-pointer text-fg-secondary hover:text-fg-primary hover:bg-surface-hover rounded-md"
                            >
                              <Download class="w-3.5 h-3.5" />
                              <span>Export JSON</span>
                            </Menu.Item>

                            <Menu.Separator class="h-px bg-border-subtle my-1" />

                            <Menu.Item
                              onSelect={() => requestDelete(conv)}
                              class="flex items-center gap-2 px-2.5 py-1.5 text-xs cursor-pointer text-critical hover:bg-critical-bg rounded-md"
                            >
                              <Trash2 class="w-3.5 h-3.5" />
                              <span>Delete chat</span>
                            </Menu.Item>
                          </DropdownMenu>
                        </div>
                      {/if}
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        {/each}
      {/if}
    </div>

    <!-- Sidebar Footer -->
    <div class="p-3 border-t border-border-default flex items-center justify-between text-[11px] text-fg-muted shrink-0 w-full bg-surface-card">
      <span class="flex items-center gap-1.5">
        <Sparkles class="w-3.5 h-3.5 text-accent" />
        <span>Graph-RAG Memory</span>
      </span>
      <span class="font-mono text-[10px]">
        {copilotStore.conversations.length} saved
      </span>
    </div>
  {:else}
    <!-- Collapsed View Quick Icons -->
    <div class="flex-1 flex flex-col items-center py-4 space-y-2 overflow-y-auto">
      {#each copilotStore.conversations.slice(0, 10) as conv (conv.id)}
        <button
          type="button"
          onclick={() => handleSelect(conv.id)}
          class="w-9 h-9 rounded-xl flex items-center justify-center transition-colors {copilotStore.activeConversationId === conv.id
            ? 'bg-accent/15 border border-accent/30 text-accent font-semibold'
            : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'}"
          title={conv.title}
        >
          {#if conv.is_pinned}
            <Pin class="w-4 h-4 text-accent" />
          {:else}
            <MessageSquare class="w-4 h-4" />
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</aside>

<!-- Confirm Delete Modal -->
<ConfirmModal
  isOpen={deleteModalOpen}
  title="Delete Conversation"
  message="Are you sure you want to delete '{conversationToDelete?.title}'? All message turns, citations, and inspection history will be permanently deleted."
  confirmText="Delete Conversation"
  cancelText="Cancel"
  danger={true}
  onConfirm={confirmDelete}
  onCancel={() => {
    deleteModalOpen = false;
    conversationToDelete = null;
  }}
/>
