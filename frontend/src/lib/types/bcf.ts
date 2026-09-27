import type { CDEState } from "./common";

// =============================================================================
// buildingSMART BCF REST API Types (v2.1)
// =============================================================================

export interface BCFProjectResponse {
  project_id: string;
  name: string;
  authorization?: {
    project_actions: string[];
    topic_actions: string[];
  };
}

export interface BCFCommentResponse {
  guid: string;
  date: string;
  author: string;
  comment: string;
  topic_guid: string;
  modified_date?: string | null;
  modified_author?: string | null;
  viewpoint_guid?: string | null;
}

export interface BCFCommentCreatePayload {
  comment: string;
  viewpoint_guid?: string | null;
}

export interface BCFViewpointResponse {
  guid: string;
  topic_guid: string;
  index: number;
  perspective_camera?: Record<string, any> | null;
  orthogonal_camera?: Record<string, any> | null;
  lines?: Record<string, any>[];
  clipping_planes?: Record<string, any>[];
  components?: Record<string, any>;
  snapshot_url?: string | null;
}

export interface BCFViewpointCreatePayload {
  perspective_camera?: Record<string, any> | null;
  orthogonal_camera?: Record<string, any> | null;
  components?: Record<string, any> | null;
  snapshot_base64?: string | null;
}

export interface BCFTopicResponse {
  guid: string;
  topic_type: string;
  topic_status: string;
  title: string;
  priority: string;
  index: number;
  creation_date: string;
  creation_author: string;
  modified_date?: string | null;
  modified_author?: string | null;
  assigned_to?: string | null;
  description?: string | null;
  due_date?: string | null;
  labels: string[];
  stage?: string | null;
  component_guids: string[];
  project_code?: string | null;
  originator?: string | null;
  suitability_code?: string | null;
  revision_code?: string | null;
  cde_state?: CDEState | null;
  comments_count: number;
  viewpoints_count: number;
}

export interface BCFTopicCreatePayload {
  title: string;
  topic_type?: string;
  topic_status?: string;
  priority?: string;
  description?: string;
  assigned_to?: string;
  due_date?: string;
  labels?: string[];
  component_guids?: string[];
  suitability_code?: string;
  revision_code?: string;
  cde_state?: CDEState;
}

export interface BCFTopicUpdatePayload {
  title?: string;
  topic_type?: string;
  topic_status?: string;
  priority?: string;
  description?: string;
  assigned_to?: string;
  due_date?: string;
  labels?: string[];
  component_guids?: string[];
  suitability_code?: string;
  revision_code?: string;
  cde_state?: CDEState;
}
