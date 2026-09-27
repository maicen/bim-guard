import type { Timestamps } from "./common";

export interface GitHubRepo extends Timestamps {
  id: number;
  name: string;
  owner: string;
  url: string;
  branch: string;
  description: string;
  is_active: boolean;
  organization_id: number;
}

export interface GitHubRepoItem {
  path: string;
  name: string;
  type: string;
  size: number;
  extension: string;
  category: string;
  download_url: string;
}

export interface GitHubRepoStructure {
  repo_id: number;
  owner: string;
  name: string;
  url: string;
  branch: string;
  total_files: number;
  models_count: number;
  categories: string[];
  items: GitHubRepoItem[];
}

export interface GitHubRepoCreatePayload {
  url: string;
  name?: string;
  branch?: string;
  description?: string;
}

export interface GitHubRepoUpdatePayload {
  name?: string;
  branch?: string;
  description?: string;
  is_active?: boolean;
}

/** Payload for attaching one or more IFC models from a GitHub repository to an existing project. */
export interface AttachRepoModelsPayload {
  repo_id: number;
  file_paths: string[];
  primary_index?: number;
}
