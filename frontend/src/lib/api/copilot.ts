import type {
  ChatConversationCreatePayload,
  ChatConversationDetail,
  ChatConversationSummary,
  ChatConversationUpdatePayload,
  ChatMessage,
} from "../types";
import { API_BASE, apiFetch, handleResponse } from "./client";

export const copilotApi = {
  /** List all conversations for the selected project. */
  async listConversations(projectId: number): Promise<ChatConversationSummary[]> {
    const res = await apiFetch(`${API_BASE}/copilot/conversations?project_id=${projectId}`);
    return handleResponse<ChatConversationSummary[]>(res);
  },

  /** Create a new conversation thread. */
  async createConversation(payload: ChatConversationCreatePayload): Promise<ChatConversationDetail> {
    const res = await apiFetch(`${API_BASE}/copilot/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<ChatConversationDetail>(res);
  },

  /** Get a conversation detail including its complete message history. */
  async getConversation(conversationId: string, projectId: number): Promise<ChatConversationDetail> {
    const res = await apiFetch(
      `${API_BASE}/copilot/conversations/${encodeURIComponent(conversationId)}?project_id=${projectId}`,
    );
    return handleResponse<ChatConversationDetail>(res);
  },

  /** Update conversation metadata (title, pinned status, scope). */
  async updateConversation(
    conversationId: string,
    projectId: number,
    payload: ChatConversationUpdatePayload,
  ): Promise<ChatConversationSummary> {
    const res = await apiFetch(
      `${API_BASE}/copilot/conversations/${encodeURIComponent(conversationId)}?project_id=${projectId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    return handleResponse<ChatConversationSummary>(res);
  },

  /** Delete a conversation and all its messages. */
  async deleteConversation(
    conversationId: string,
    projectId: number,
  ): Promise<{ deleted: boolean; conversation_id: string }> {
    const res = await apiFetch(
      `${API_BASE}/copilot/conversations/${encodeURIComponent(conversationId)}?project_id=${projectId}`,
      {
        method: "DELETE",
      },
    );
    return handleResponse<{ deleted: boolean; conversation_id: string }>(res);
  },

  /** Persist/append message turns to a conversation. */
  async saveMessages(
    conversationId: string,
    projectId: number,
    messages: ChatMessage[],
  ): Promise<{ saved: number; conversation_id: string }> {
    const res = await apiFetch(
      `${API_BASE}/copilot/conversations/${encodeURIComponent(conversationId)}/messages?project_id=${projectId}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages }),
      },
    );
    return handleResponse<{ saved: number; conversation_id: string }>(res);
  },
};
