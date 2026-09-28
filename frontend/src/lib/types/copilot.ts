/**
 * TypeScript types for Graph-RAG Copilot conversation persistence.
 * Mirrors Pydantic contracts in app/modules/contracts/copilot.py.
 */

import type { GraphRagCitation, GraphRagScope, GraphRagStep, GraphRagToolCall } from "./graph";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations?: GraphRagCitation[];
  reasoning_steps?: GraphRagStep[];
  tool_calls?: GraphRagToolCall[];
  cypher_queries?: string[];
  timestamp?: string;
  created_at?: string;
}

export interface ChatConversationSummary {
  id: string;
  project_id: number;
  user_id?: string | null;
  title: string;
  scope: GraphRagScope;
  document_id?: number | null;
  element_class?: string | null;
  is_pinned: boolean;
  message_count: number;
  last_message_preview?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatConversationDetail {
  id: string;
  project_id: number;
  user_id?: string | null;
  title: string;
  scope: GraphRagScope;
  document_id?: number | null;
  element_class?: string | null;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
}

export interface ChatConversationCreatePayload {
  project_id: number;
  title?: string;
  scope?: GraphRagScope;
  document_id?: number | null;
  element_class?: string | null;
}

export interface ChatConversationUpdatePayload {
  title?: string;
  is_pinned?: boolean;
  scope?: GraphRagScope;
  document_id?: number | null;
  element_class?: string | null;
}

export type ConversationDateGroup =
  | "pinned"
  | "today"
  | "yesterday"
  | "last7Days"
  | "last30Days"
  | "older";

export interface GroupedConversations {
  pinned: ChatConversationSummary[];
  today: ChatConversationSummary[];
  yesterday: ChatConversationSummary[];
  last7Days: ChatConversationSummary[];
  last30Days: ChatConversationSummary[];
  older: ChatConversationSummary[];
}
