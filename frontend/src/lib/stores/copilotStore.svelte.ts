/**
 * Svelte 5 reactive store for Graph-RAG Copilot conversation persistence.
 *
 * Provides ChatGPT-style date-grouped sidebar state, active message turns,
 * optimistic updates, and automatic synchronization with FastAPI copilot endpoints.
 */

import { copilotApi } from "../api/copilot";
import type {
  ChatConversationCreatePayload,
  ChatConversationDetail,
  ChatConversationSummary,
  ChatMessage,
  GraphRagScope,
  GroupedConversations,
} from "../types";
import { toasts } from "../toast.svelte";

const STORAGE_COLLAPSED_KEY = "bimguard_copilot_sidebar_collapsed";

function isSameDay(d1: Date, d2: Date): boolean {
  return (
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
  );
}

function getInitialCollapsed(): boolean {
  try {
    return localStorage.getItem(STORAGE_COLLAPSED_KEY) === "true";
  } catch {
    return false;
  }
}

export class CopilotStore {
  // Reactive State
  conversations = $state<ChatConversationSummary[]>([]);
  activeConversationId = $state<string | null>(null);
  activeConversation = $state<ChatConversationDetail | null>(null);
  activeMessages = $state<ChatMessage[]>([]);
  searchQuery = $state<string>("");
  isLoadingList = $state<boolean>(false);
  isLoadingConversation = $state<boolean>(false);
  isSidebarCollapsed = $state<boolean>(getInitialCollapsed());

  // Derived: Active Conversation Summary
  activeSummary = $derived.by(() => {
    if (!this.activeConversationId) return null;
    return this.conversations.find((c) => c.id === this.activeConversationId) || null;
  });

  // Derived: Filtered and Date-Grouped Conversations (ChatGPT Style)
  groupedConversations = $derived.by((): GroupedConversations => {
    const query = this.searchQuery.trim().toLowerCase();
    const filtered = this.conversations.filter((c) => {
      if (!query) return true;
      return (
        c.title.toLowerCase().includes(query) ||
        (c.last_message_preview && c.last_message_preview.toLowerCase().includes(query))
      );
    });

    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    const sevenDaysAgo = new Date(today);
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

    const thirtyDaysAgo = new Date(today);
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const groups: GroupedConversations = {
      pinned: [],
      today: [],
      yesterday: [],
      last7Days: [],
      last30Days: [],
      older: [],
    };

    for (const item of filtered) {
      if (item.is_pinned) {
        groups.pinned.push(item);
        continue;
      }

      const itemDate = new Date(item.updated_at);
      if (isSameDay(itemDate, today) || itemDate >= today) {
        groups.today.push(itemDate ? item : item);
      } else if (isSameDay(itemDate, yesterday)) {
        groups.yesterday.push(item);
      } else if (itemDate >= sevenDaysAgo) {
        groups.last7Days.push(item);
      } else if (itemDate >= thirtyDaysAgo) {
        groups.last30Days.push(item);
      } else {
        groups.older.push(item);
      }
    }

    return groups;
  });

  toggleSidebar() {
    this.isSidebarCollapsed = !this.isSidebarCollapsed;
    try {
      localStorage.setItem(STORAGE_COLLAPSED_KEY, String(this.isSidebarCollapsed));
    } catch {}
  }

  /** Load conversations list for the project and select the most recent or active one. */
  async loadConversations(projectId: number, preferredId?: string | null) {
    if (!projectId) return;
    this.isLoadingList = true;
    try {
      const list = await copilotApi.listConversations(projectId);
      this.conversations = list;

      const targetId = preferredId || this.activeConversationId || (list.length > 0 ? list[0].id : null);
      if (targetId && list.some((c) => c.id === targetId)) {
        await this.selectConversation(targetId, projectId);
      } else if (list.length > 0) {
        await this.selectConversation(list[0].id, projectId);
      } else {
        this.activeConversationId = null;
        this.activeConversation = null;
        this.activeMessages = [];
      }
    } catch (err) {
      console.warn("Could not load conversations from server:", err);
    } finally {
      this.isLoadingList = false;
    }
  }

  /** Switch active conversation and fetch its complete message turns. */
  async selectConversation(conversationId: string, projectId: number) {
    this.activeConversationId = conversationId;
    this.isLoadingConversation = true;
    try {
      const detail = await copilotApi.getConversation(conversationId, projectId);
      this.activeConversation = detail;
      this.activeMessages = detail.messages || [];
    } catch (err: any) {
      console.error(`Failed to fetch conversation ${conversationId}:`, err);
      toasts.error("Failed to load conversation history");
    } finally {
      this.isLoadingConversation = false;
    }
  }

  /** Start a fresh conversation in the project. */
  async startNewConversation(
    projectId: number,
    initial?: {
      title?: string;
      scope?: GraphRagScope;
      documentId?: number | null;
      elementClass?: string | null;
    },
  ): Promise<ChatConversationDetail | null> {
    if (!projectId) return null;
    try {
      const payload: ChatConversationCreatePayload = {
        project_id: projectId,
        title: initial?.title || "New Conversation",
        scope: initial?.scope || "hybrid",
        document_id: initial?.documentId || null,
        element_class: initial?.elementClass || null,
      };

      const created = await copilotApi.createConversation(payload);
      const summary: ChatConversationSummary = {
        id: created.id,
        project_id: created.project_id,
        user_id: created.user_id,
        title: created.title,
        scope: created.scope,
        document_id: created.document_id,
        element_class: created.element_class,
        is_pinned: created.is_pinned,
        message_count: 0,
        last_message_preview: null,
        created_at: created.created_at,
        updated_at: created.updated_at,
      };

      this.conversations = [summary, ...this.conversations];
      this.activeConversationId = created.id;
      this.activeConversation = created;
      this.activeMessages = [];
      return created;
    } catch (err: any) {
      console.error("Failed to create new conversation:", err);
      toasts.error("Could not create new conversation");
      return null;
    }
  }

  /** Rename conversation title. */
  async renameConversation(conversationId: string, newTitle: string, projectId: number) {
    const trimmed = newTitle.trim();
    if (!trimmed) return;

    // Optimistic local update
    const prevConversations = [...this.conversations];
    this.conversations = this.conversations.map((c) =>
      c.id === conversationId ? { ...c, title: trimmed } : c,
    );
    if (this.activeConversation && this.activeConversation.id === conversationId) {
      this.activeConversation.title = trimmed;
    }

    try {
      await copilotApi.updateConversation(conversationId, projectId, { title: trimmed });
    } catch (err) {
      this.conversations = prevConversations;
      console.error("Failed to rename conversation:", err);
      toasts.error("Failed to rename conversation");
    }
  }

  /** Toggle pinned state of a conversation. */
  async togglePin(conversationId: string, projectId: number) {
    const item = this.conversations.find((c) => c.id === conversationId);
    if (!item) return;

    const newPinned = !item.is_pinned;
    // Optimistic update
    this.conversations = this.conversations.map((c) =>
      c.id === conversationId ? { ...c, is_pinned: newPinned } : c,
    );
    if (this.activeConversation && this.activeConversation.id === conversationId) {
      this.activeConversation.is_pinned = newPinned;
    }

    try {
      await copilotApi.updateConversation(conversationId, projectId, { is_pinned: newPinned });
    } catch (err) {
      // Revert on failure
      this.conversations = this.conversations.map((c) =>
        c.id === conversationId ? { ...c, is_pinned: !newPinned } : c,
      );
      toasts.error("Failed to update pinned status");
    }
  }

  /** Delete conversation and select next available. */
  async deleteConversation(conversationId: string, projectId: number) {
    const prevList = [...this.conversations];
    this.conversations = this.conversations.filter((c) => c.id !== conversationId);

    if (this.activeConversationId === conversationId) {
      const next = this.conversations[0];
      if (next) {
        await this.selectConversation(next.id, projectId);
      } else {
        this.activeConversationId = null;
        this.activeConversation = null;
        this.activeMessages = [];
      }
    }

    try {
      await copilotApi.deleteConversation(conversationId, projectId);
      toasts.success("Conversation deleted");
    } catch (err) {
      this.conversations = prevList;
      console.error("Failed to delete conversation:", err);
      toasts.error("Could not delete conversation");
    }
  }

  /** Save message turns to active conversation and update summary preview. */
  async saveTurns(
    conversationId: string,
    projectId: number,
    messagesToSave: ChatMessage[],
  ) {
    if (!conversationId || messagesToSave.length === 0) return;

    if (this.activeConversationId === conversationId) {
      this.activeMessages = [...this.activeMessages, ...messagesToSave];
      if (this.activeConversation) {
        this.activeConversation.messages = [
          ...(this.activeConversation.messages || []),
          ...messagesToSave,
        ];
      }
    }

    try {
      await copilotApi.saveMessages(conversationId, projectId, messagesToSave);

      // Update local preview and message count in conversation summary
      const nowIso = new Date().toISOString();
      const lastMsg = messagesToSave[messagesToSave.length - 1];
      const preview = lastMsg?.content
        ? lastMsg.content.slice(0, 120) + (lastMsg.content.length > 120 ? "..." : "")
        : null;

      this.conversations = this.conversations.map((c) => {
        if (c.id === conversationId) {
          return {
            ...c,
            message_count: (c.message_count || 0) + messagesToSave.length,
            last_message_preview: preview || c.last_message_preview,
            updated_at: nowIso,
          };
        }
        return c;
      });
    } catch (err) {
      console.warn("Failed to persist message turns to server:", err);
    }
  }

  /** Auto-generate an informative title from the first prompt. */
  async autoTitleIfDefault(conversationId: string, promptText: string, projectId: number) {
    const current = this.conversations.find((c) => c.id === conversationId);
    if (!current || (current.title !== "New Conversation" && current.title !== "New Chat")) {
      return;
    }

    // Clean prompt to derive concise 3-8 word title
    let title = promptText.replace(/^(what is|what are|how many|can you|tell me about|explain)\s+/i, "");
    title = title.replace(/[?!.]+$/, "").trim();
    if (title.length > 50) {
      title = title.slice(0, 48) + "…";
    }
    title = title.charAt(0).toUpperCase() + title.slice(1);

    if (title) {
      await this.renameConversation(conversationId, title, projectId);
    }
  }
}

export const copilotStore = new CopilotStore();
