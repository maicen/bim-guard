import type {
  BCFCommentCreatePayload,
  BCFCommentResponse,
  BCFProjectResponse,
  BCFTopicCreatePayload,
  BCFTopicResponse,
  BCFTopicUpdatePayload,
  BCFViewpointCreatePayload,
  BCFViewpointResponse,
} from "../types";
import { API_BASE, apiFetch, handleResponse } from "./client";

// =============================================================================
// buildingSMART BCF REST API Client (v2.1)
// =============================================================================

export const bcfApi = {
  async listProjects(): Promise<BCFProjectResponse[]> {
    const res = await apiFetch(`${API_BASE}/bcf/v2.1/projects`);
    return handleResponse<BCFProjectResponse[]>(res);
  },

  async getProject(projectId: string | number): Promise<BCFProjectResponse> {
    const res = await apiFetch(`${API_BASE}/bcf/v2.1/projects/${projectId}`);
    return handleResponse<BCFProjectResponse>(res);
  },

  async listTopics(
    projectId: string | number,
    filters?: {
      topic_status?: string;
      topic_type?: string;
      priority?: string;
      assigned_to?: string;
      cde_state?: string;
    },
  ): Promise<BCFTopicResponse[]> {
    const query = new URLSearchParams();
    if (filters?.topic_status) query.set("topic_status", filters.topic_status);
    if (filters?.topic_type) query.set("topic_type", filters.topic_type);
    if (filters?.priority) query.set("priority", filters.priority);
    if (filters?.assigned_to) query.set("assigned_to", filters.assigned_to);
    if (filters?.cde_state) query.set("cde_state", filters.cde_state);
    const qs = query.toString() ? `?${query.toString()}` : "";
    const res = await apiFetch(`${API_BASE}/bcf/v2.1/projects/${projectId}/topics${qs}`);
    return handleResponse<BCFTopicResponse[]>(res);
  },

  async getTopic(projectId: string | number, topicGuid: string): Promise<BCFTopicResponse> {
    const res = await apiFetch(`${API_BASE}/bcf/v2.1/projects/${projectId}/topics/${topicGuid}`);
    return handleResponse<BCFTopicResponse>(res);
  },

  async createTopic(
    projectId: string | number,
    payload: BCFTopicCreatePayload,
  ): Promise<BCFTopicResponse> {
    const res = await apiFetch(`${API_BASE}/bcf/v2.1/projects/${projectId}/topics`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<BCFTopicResponse>(res);
  },

  async updateTopic(
    projectId: string | number,
    topicGuid: string,
    payload: BCFTopicUpdatePayload,
  ): Promise<BCFTopicResponse> {
    const res = await apiFetch(`${API_BASE}/bcf/v2.1/projects/${projectId}/topics/${topicGuid}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handleResponse<BCFTopicResponse>(res);
  },

  async listComments(projectId: string | number, topicGuid: string): Promise<BCFCommentResponse[]> {
    const res = await apiFetch(
      `${API_BASE}/bcf/v2.1/projects/${projectId}/topics/${topicGuid}/comments`,
    );
    return handleResponse<BCFCommentResponse[]>(res);
  },

  async createComment(
    projectId: string | number,
    topicGuid: string,
    payload: BCFCommentCreatePayload,
  ): Promise<BCFCommentResponse> {
    const res = await apiFetch(
      `${API_BASE}/bcf/v2.1/projects/${projectId}/topics/${topicGuid}/comments`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    return handleResponse<BCFCommentResponse>(res);
  },

  async listViewpoints(
    projectId: string | number,
    topicGuid: string,
  ): Promise<BCFViewpointResponse[]> {
    const res = await apiFetch(
      `${API_BASE}/bcf/v2.1/projects/${projectId}/topics/${topicGuid}/viewpoints`,
    );
    return handleResponse<BCFViewpointResponse[]>(res);
  },

  async createViewpoint(
    projectId: string | number,
    topicGuid: string,
    payload: BCFViewpointCreatePayload,
  ): Promise<BCFViewpointResponse> {
    const res = await apiFetch(
      `${API_BASE}/bcf/v2.1/projects/${projectId}/topics/${topicGuid}/viewpoints`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );
    return handleResponse<BCFViewpointResponse>(res);
  },

  async deleteTopic(projectId: string | number, topicGuid: string): Promise<void> {
    const res = await apiFetch(`${API_BASE}/bcf/v2.1/projects/${projectId}/topics/${topicGuid}`, {
      method: "DELETE",
    });
    return handleResponse<void>(res);
  },

  async bulkDeleteTopics(projectId: string | number, topicGuids: string[]): Promise<void> {
    await Promise.all(topicGuids.map((guid) => this.deleteTopic(projectId, guid)));
  },
};
