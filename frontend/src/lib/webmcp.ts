/**
 * WebMCP — exposes BIM Guard's main actions to in-browser AI agents as typed
 * tools (https://developer.chrome.com/docs/ai/webmcp), so an agent can call
 * `run_architecture_analysis` instead of clicking through the UI.
 *
 * Tools run in the signed-in user's own session through the same typed API
 * clients the UI uses, so org scoping, auth and RLS apply unchanged. Feature
 * detected: browsers without WebMCP are unaffected.
 */
import { push } from "svelte-spa-router";
import { analyzeApi, projectsApi, rulesApi } from "./api";

interface ToolResultContext {
  signal?: AbortSignal;
}

interface WebMcpTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  annotations?: { readOnlyHint?: boolean; consequentialHint?: boolean };
  execute: (input: any, ctx?: ToolResultContext) => Promise<string>;
}

interface ModelContextLike {
  registerTool(tool: WebMcpTool, options?: { signal?: AbortSignal }): unknown;
}

/** Views an agent may navigate to, keyed by hash route. */
const VIEWS: Record<string, string> = {
  dashboard: "Compliance dashboard",
  "new-project": "Create a project",
  "run-compliance-test": "Run a compliance audit",
  documents: "Specification documents",
  extract: "Rule extraction studio",
  rules: "Rules catalog",
  copilot: "Graph-RAG copilot",
  "query-console": "Graph query console",
  reports: "Compliance reports and exports",
  models: "Project models",
  viewer: "3D IFC viewer",
};

const json = (value: unknown): string => JSON.stringify(value);

const TOOLS: WebMcpTool[] = [
  {
    name: "list_projects",
    description: "List the projects in the active organization (id, name, project_code).",
    inputSchema: { type: "object", properties: {} },
    annotations: { readOnlyHint: true },
    execute: async () => {
      const { projects } = await projectsApi.list();
      return json(
        projects.map((p) => ({ id: p.id, name: p.name, project_code: p.project_code })),
      );
    },
  },
  {
    name: "list_rulesets",
    description:
      "List available rulesets. Pass a returned ruleset_id to run_architecture_analysis.",
    inputSchema: { type: "object", properties: {} },
    annotations: { readOnlyHint: true },
    execute: async () => {
      const folders = await rulesApi.folders();
      return json(
        folders.map((f) => ({
          ruleset_id: f.ruleset_id,
          display_name: f.display_name,
          rule_count: f.count ?? f.rules.length,
        })),
      );
    },
  },
  {
    name: "get_analysis_status",
    description: "Get the pipeline status of a project's latest compliance analysis run.",
    inputSchema: {
      type: "object",
      properties: { project_id: { type: "number", description: "Project id" } },
      required: ["project_id"],
    },
    annotations: { readOnlyHint: true },
    execute: async ({ project_id }) => json(await analyzeApi.getStatus(Number(project_id))),
  },
  {
    name: "run_architecture_analysis",
    description:
      "Start the architectural compliance analysis for a project against the given rulesets " +
      "(all rulesets when omitted). Poll get_analysis_status for progress.",
    inputSchema: {
      type: "object",
      properties: {
        project_id: { type: "number", description: "Project id" },
        rule_folders: {
          type: "array",
          items: { type: "string" },
          description: "ruleset_id values from list_rulesets",
        },
      },
      required: ["project_id"],
    },
    annotations: { readOnlyHint: false },
    execute: async ({ project_id, rule_folders }) => {
      await analyzeApi.runArch(Number(project_id), rule_folders ?? []);
      return json({ started: true, project_id: Number(project_id) });
    },
  },
  {
    name: "navigate",
    description: `Open a view of the app. Views: ${Object.entries(VIEWS)
      .map(([k, v]) => `${k} (${v})`)
      .join(", ")}.`,
    inputSchema: {
      type: "object",
      properties: {
        view: { type: "string", enum: Object.keys(VIEWS) },
        project_id: { type: "number", description: "Optional project to scope the view to" },
      },
      required: ["view"],
    },
    annotations: { readOnlyHint: false },
    execute: async ({ view, project_id }) => {
      if (!(view in VIEWS)) throw new Error(`Unknown view: ${view}`);
      push(`/${view}${project_id ? `?project_id=${Number(project_id)}` : ""}`);
      return json({ navigated: view });
    },
  },
];

/**
 * Register every tool with the browser. Returns a cleanup that unregisters
 * them, or a no-op when WebMCP is unavailable.
 */
export function registerWebMcpTools(): () => void {
  // Current Chrome docs expose `document.modelContext`; earlier previews and
  // the original proposal used `navigator.modelContext`.
  const ctx = ((document as unknown as { modelContext?: ModelContextLike }).modelContext ??
    (navigator as unknown as { modelContext?: ModelContextLike }).modelContext) as
    | ModelContextLike
    | undefined;
  if (!ctx?.registerTool) return () => {};

  const controller = new AbortController();
  for (const tool of TOOLS) {
    try {
      void Promise.resolve(ctx.registerTool(tool, { signal: controller.signal })).catch(() => {});
    } catch {
      // A browser build with a different signature must not break the app.
    }
  }
  return () => controller.abort();
}
