/**
 * BIM-Guard API Client Suite
 * Modular, typed API clients communicating with the FastAPI gateway.
 */

// Core client and HTTP utilities
export {
  API_BASE,
  apiFetch,
  handleResponse,
  isAbortError,
  toNetworkError,
  type ApiError,
} from "./client";

// Domain API clients
export { authApi } from "./auth";
export { organizationsApi, permissionsApi } from "./organizations";
export { projectsApi } from "./projects";
export { modelsApi, githubReposApi } from "./models";
export { rulesApi, ruleExtractionApi, lineageApi, buildRulesFilterKey } from "./rules";
export { documentsApi } from "./documents";
export {
  analyzeApi,
  revitSyncApi,
  type IssueBand,
  type IssueSort,
  type ResultPageQuery,
} from "./analyze";
export { evaluationApi } from "./evaluation";
export { dashboardApi } from "./dashboard";
export { cdeApi } from "./cde";
export { bcfApi } from "./bcf";
export { namingConfigApi } from "./namingConfig";
export { bsddApi } from "./bsdd";
export { graphApi, sparqlApi } from "./graph";
export { copilotApi } from "./copilot";
export {
  settingsApi,
  parsingEnginesApi,
  orgParsingEnginesApi,
  llmProvidersApi,
} from "./settings";

import { projectsApi } from "./projects";
import { documentsApi } from "./documents";
import { rulesApi } from "./rules";
import { dashboardApi } from "./dashboard";

/** Clear all entity and aggregate caches when switching active tenant. */
export function clearTenantCaches(): void {
  projectsApi.clearCache();
  documentsApi.clearCache();
  rulesApi.clearCache();
  dashboardApi.invalidateCache();
}
