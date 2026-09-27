import type { Timestamps } from "./common";

export interface DashboardStats {
  db_ok: boolean;
  db_backend: string;
}

export interface SettingItem {
  key: string;
  value: string;
  description: string;
}

export interface SettingsResponse {
  settings: SettingItem[];
  active_log_level: string;
  db_backend: string;
}

export interface EnvVarStatusItem {
  name: string;
  category: string;
  description: string;
  required: boolean;
  is_set: boolean;
}

export interface EnvVarStatusResponse {
  variables: EnvVarStatusItem[];
}

export type ParsingEngineKindId = string;

export interface ParsingEngineKind {
  kind: ParsingEngineKindId;
  family: string;
  display_name: string;
  description: string;
  requires_api_key: boolean;
  supports_strategy: boolean;
  url_placeholder: string;
  docs_url: string;
}

export interface ParsingEngineInstance extends Timestamps {
  id: number;
  organization_id: number | null;
  name: string;
  kind: ParsingEngineKindId;
  api_url: string;
  has_api_key: boolean;
  strategy: string;
  is_default: boolean;
  is_enabled: boolean;
  notes: string;
}

export interface ParsingEngineInstanceCreatePayload {
  name: string;
  kind: ParsingEngineKindId;
  api_url: string;
  api_key?: string;
  strategy?: string;
  is_default?: boolean;
  is_enabled?: boolean;
  notes?: string;
}

export interface ParsingEngineInstanceUpdatePayload {
  name?: string;
  api_url?: string;
  api_key?: string;
  strategy?: string;
  is_default?: boolean;
  is_enabled?: boolean;
  notes?: string;
}

export interface ParsingEngineInstanceTestResult {
  ok: boolean;
  detail: string;
}

export type LLMProviderKindId = string;

export interface LLMProviderKind {
  kind: LLMProviderKindId;
  display_name: string;
  description: string;
  requires_api_key: boolean;
  default_api_base: string;
  url_placeholder: string;
}

export interface LLMProviderInstance extends Timestamps {
  id: number;
  organization_id: number;
  name: string;
  kind: LLMProviderKindId;
  api_base: string;
  has_api_key: boolean;
  is_default: boolean;
  is_enabled: boolean;
  notes: string;
}

export interface LLMProviderInstanceCreatePayload {
  name: string;
  kind: LLMProviderKindId;
  api_key?: string;
  api_base?: string;
  is_default?: boolean;
  is_enabled?: boolean;
  notes?: string;
}

export interface LLMProviderInstanceUpdatePayload {
  name?: string;
  api_key?: string;
  api_base?: string;
  is_default?: boolean;
  is_enabled?: boolean;
  notes?: string;
}

export interface LLMProviderInstanceTestResult {
  ok: boolean;
  detail: string;
}

export interface LLMProviderTestPayload {
  kind: LLMProviderKindId;
  api_key?: string;
  api_base?: string;
}

export interface LLMProviderModel {
  id: string;
  name: string;
  context_length?: number | null;
  input_price_per_million?: number | null;
  output_price_per_million?: number | null;
  capabilities?: string[];
}

export interface LLMTask {
  key: string;
  label: string;
  description: string;
}

export interface LLMTaskAssignmentModel {
  provider_instance_id: number;
  model_id: string;
  model_name: string;
  context_length?: number | null;
  input_price_per_million?: number | null;
  output_price_per_million?: number | null;
}

export interface LLMTaskAssignmentSetPayload {
  models: LLMTaskAssignmentModel[];
  default_provider_instance_id?: number | null;
  default_model_id?: string | null;
}

export interface LLMTaskModelAssignment {
  task_key: string;
  provider_instance_id: number;
  provider_instance_name: string;
  model_id: string;
  model_name: string;
  context_length?: number | null;
  input_price_per_million?: number | null;
  output_price_per_million?: number | null;
  is_default: boolean;
}
