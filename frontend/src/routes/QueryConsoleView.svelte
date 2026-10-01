<script lang="ts">
  import { onMount, untrack } from "svelte";
  import { push } from "svelte-spa-router";
  import { Tabs } from "bits-ui";
  import {
    Activity,
    AlertTriangle,
    BookOpen,
    CheckCircle2,
    Code,
    Database,
    ExternalLink,
    GitFork,
    Info,
    Play,
    RefreshCw,
    ScanEye,
    Search,
    Terminal,
    XCircle,
    ChevronDown,
    ChevronRight,
    Sparkles,
  } from "lucide-svelte";
  import { graphApi, projectsApi, sparqlApi } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import { toasts } from "../lib/toast.svelte";
  import type {
    CodeToIfcTraceResponse,
    GoverningRequirementsResponse,
    GraphQueryPresetSummary,
    GraphQueryResultResponse,
    ModelHealthAuditReport,
    Project,
    RegulatoryGraphContextResponse,
    SparqlQueryResult,
  } from "../lib/types";
  import { Button, Input, Select } from "../lib/components/ui";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import AiChatbot from "../lib/components/ai/AiChatbot.svelte";

  interface Props {
    initialProjectId?: number | null;
  }

  let { initialProjectId = null }: Props = $props();

  let selectedProjectId: number | null = $state(untrack(() => initialProjectId));
  let projects: Project[] = $state([]);
  let loadingProjects = $state(false);

  const initialTabParam = typeof window !== "undefined"
    ? (new URLSearchParams(window.location.hash.split("?")[1] || window.location.search).get("tab") as any)
    : null;
  const validTabs = ["rag", "health", "regulatory", "cypher", "sparql", "trace"];
  let activeTab = $state<"rag" | "health" | "regulatory" | "cypher" | "sparql" | "trace">(
    validTabs.includes(initialTabParam) ? initialTabParam : "rag",
  );

  // Keep selectedProjectId in sync when initialProjectId changes externally
  $effect(() => {
    if (initialProjectId !== undefined && initialProjectId !== selectedProjectId) {
      selectedProjectId = initialProjectId;
    }
  });

  async function loadProjects() {
    loadingProjects = true;
    try {
      const res = await projectsApi.list();
      projects = res.projects;
      if (!selectedProjectId && projects.length > 0) {
        selectedProjectId = projects[0].id;
      }
    } catch {
      projects = [];
    } finally {
      loadingProjects = false;
    }
  }

  function handleSelectProject(projIdStr: string) {
    const id = Number(projIdStr);
    if (!id || id === selectedProjectId) return;
    selectedProjectId = id;

    const params = new URLSearchParams();
    params.set("project_id", String(id));
    if (authState.activeOrganizationId) {
      params.set("org", String(authState.activeOrganizationId));
    }
    push(`/query-console?${params.toString()}`);

    // Trigger tab-specific reloads
    if (activeTab === "health") loadHealthAudit();
    if (activeTab === "trace") loadTrace();
  }

  // --- 1. MODEL HEALTH AUDIT ---
  let healthReport: ModelHealthAuditReport | null = $state(null);
  let healthLoading = $state(false);
  let healthError = $state("");
  let expandedCheckKey = $state<string | null>(null);

  async function loadHealthAudit() {
    if (!selectedProjectId) return;
    healthLoading = true;
    healthError = "";
    try {
      healthReport = await graphApi.getModelHealth(selectedProjectId);
    } catch (err: any) {
      healthError = err?.message || "Failed to evaluate model health audit.";
      healthReport = null;
    } finally {
      healthLoading = false;
    }
  }

  $effect(() => {
    if (activeTab === "health" && selectedProjectId && !healthReport && !healthLoading) {
      loadHealthAudit();
    }
  });

  function getGradeColor(grade: string) {
    if (grade === "A" || grade === "B") return "text-success border-success-border bg-success-bg";
    if (grade === "C") return "text-warning border-warning-border bg-warning-bg";
    return "text-critical border-critical-border bg-critical-bg";
  }

  // --- 2. REGULATORY KNOWLEDGE GRAPH ---
  let regIfcType = $state("IfcDoor");
  let regRequirements: GoverningRequirementsResponse | null = $state(null);
  let regRequirementsLoading = $state(false);
  let regRequirementsError = $state("");

  let regClauseQuery = $state("1017.2");
  let regClauseContext: RegulatoryGraphContextResponse | null = $state(null);
  let regClauseLoading = $state(false);
  let regClauseError = $state("");

  let regIngestLoading = $state(false);
  let regIngestMessage = $state("");

  const COMMON_IFC_CLASSES = ["IfcDoor", "IfcWall", "IfcStair", "IfcSpace", "IfcWindow", "IfcColumn", "IfcRailing", "IfcSlab"];

  async function loadGoverningReqs() {
    if (!regIfcType.trim()) return;
    regRequirementsLoading = true;
    regRequirementsError = "";
    try {
      regRequirements = await graphApi.getGoverningRequirements(regIfcType.trim());
    } catch (err: any) {
      regRequirementsError = err?.message || "Failed to query governing requirements.";
    } finally {
      regRequirementsLoading = false;
    }
  }

  async function loadClauseContext() {
    if (!regClauseQuery.trim()) return;
    regClauseLoading = true;
    regClauseError = "";
    try {
      regClauseContext = await graphApi.getRegulatoryClauseContext(regClauseQuery.trim());
    } catch (err: any) {
      regClauseContext = null;
      regClauseError = err?.message || "Clause not found in regulatory graph.";
    } finally {
      regClauseLoading = false;
    }
  }

  async function triggerIngestRegulatory() {
    regIngestLoading = true;
    regIngestMessage = "";
    try {
      toasts.info("Ingesting regulatory standards and rules catalog into Neo4j…");
      const res = await graphApi.ingestRegulatoryGraph();
      const nodeCount = res.nodes ?? 0;
      const edgeCount = res.edges ?? 0;
      regIngestMessage = `Ingested ${nodeCount} nodes and ${edgeCount} edges into Neo4j graph.`;
      toasts.success(regIngestMessage);
    } catch (err: any) {
      regIngestMessage = err?.message || "Failed to ingest regulatory graph.";
      toasts.error(regIngestMessage);
    } finally {
      regIngestLoading = false;
    }
  }

  $effect(() => {
    if (activeTab === "regulatory" && !regRequirements && !regRequirementsLoading) {
      loadGoverningReqs();
    }
  });

  // --- 3. CYPHER PRESETS ---
  let presets: GraphQueryPresetSummary[] = $state([]);
  let selectedPresetKey = $state("");
  let presetParamValues: Record<string, string> = $state({});
  let presetResult: GraphQueryResultResponse | null = $state(null);
  let presetLoading = $state(false);
  let presetError = $state("");

  const selectedPreset = $derived(presets.find((p) => p.key === selectedPresetKey) ?? null);

  async function loadPresets() {
    try {
      const res = await graphApi.listQueryPresets();
      presets = res.presets;
      if (presets.length && !selectedPresetKey) {
        selectedPresetKey = presets[0].key;
      }
    } catch {
      presets = [];
    }
  }

  async function runPreset() {
    if (!selectedProjectId || !selectedPreset) return;
    presetLoading = true;
    presetError = "";
    presetResult = null;
    try {
      presetResult = await graphApi.runQueryPreset(selectedProjectId, selectedPreset.key, presetParamValues);
      toasts.success(`Preset "${selectedPreset.label}" returned ${presetResult.row_count} row(s).`);
    } catch (err: any) {
      presetError = err?.message || "Preset query failed.";
      toasts.error(presetError);
    } finally {
      presetLoading = false;
    }
  }

  const presetColumns = $derived(
    presetResult && presetResult.rows.length ? Object.keys(presetResult.rows[0]) : [],
  );

  // --- 4. SPARQL ENDPOINT ---
  let sparqlText = $state(
    `PREFIX bot: <https://w3id.org/bot#>
PREFIX bpo: <https://w3id.org/bpo#>
PREFIX saref: <https://saref.etsi.org/saref4bldg/>

SELECT ?s ?p ?o
WHERE {
  ?s ?p ?o .
}
LIMIT 25`,
  );
  let sparqlResult: SparqlQueryResult | null = $state(null);
  let sparqlLoading = $state(false);
  let sparqlError = $state("");

  const SPARQL_SAMPLE_QUERIES = [
    {
      label: "All Triples",
      query: `SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 25`,
    },
    {
      label: "BOT Spaces",
      query: `PREFIX bot: <https://w3id.org/bot#>
SELECT ?space ?name WHERE {
  ?space a bot:Space .
  OPTIONAL { ?space bot:hasName ?name }
} LIMIT 25`,
    },
    {
      label: "Adjacent Elements",
      query: `PREFIX bot: <https://w3id.org/bot#>
SELECT ?space ?element WHERE {
  ?space bot:adjacentElement ?element .
} LIMIT 25`,
    },
    {
      label: "Building Storeys",
      query: `PREFIX bot: <https://w3id.org/bot#>
SELECT ?storey WHERE {
  ?storey a bot:Storey .
} LIMIT 25`,
    },
  ];

  async function runSparql() {
    if (!selectedProjectId || !sparqlText.trim()) return;
    sparqlLoading = true;
    sparqlError = "";
    sparqlResult = null;
    try {
      sparqlResult = await sparqlApi.query(selectedProjectId, sparqlText.trim());
      toasts.success("SPARQL query executed successfully.");
    } catch (err: any) {
      sparqlError = err?.message || "SPARQL query failed.";
      toasts.error(sparqlError);
    } finally {
      sparqlLoading = false;
    }
  }

  const sparqlVars = $derived(sparqlResult?.head?.vars ?? []);

  // --- 5. CODE-TO-BIM TRACE ---
  let trace: CodeToIfcTraceResponse | null = $state(null);
  let traceLoading = $state(false);
  let traceError = $state("");
  let traceSearch = $state("");

  async function loadTrace() {
    if (!selectedProjectId) return;
    traceLoading = true;
    traceError = "";
    try {
      trace = await graphApi.getCodeToIfcTrace(selectedProjectId);
    } catch (err: any) {
      traceError = err?.message || "Could not load the code-to-IFC trace.";
    } finally {
      traceLoading = false;
    }
  }

  const filteredTraceEntries = $derived.by(() => {
    if (!trace) return [];
    if (!traceSearch.trim()) return trace.entries;
    const q = traceSearch.toLowerCase();
    return trace.entries.filter(
      (e) =>
        e.reference?.toLowerCase().includes(q) ||
        e.target_ifc_class?.toLowerCase().includes(q) ||
        e.description?.toLowerCase().includes(q),
    );
  });

  $effect(() => {
    if (activeTab === "trace" && selectedProjectId && !trace && !traceLoading) {
      loadTrace();
    }
  });

  onMount(() => {
    loadProjects();
    loadPresets();
  });
</script>

<div class="space-y-6 pb-12">
  <!-- Page Header -->
  <PageHeader
    category="Coordination & Graph"
    title="Query Console"
    subtitle="Interactive Property Graph & SPARQL Console — Neo4j Cypher Presets, Regulatory GraphRAG, Model Health Audit & Code-to-BIM Trace."
    icon={Terminal}
  >
    {#snippet actions()}
      <div class="flex flex-wrap items-center gap-2">
        <!-- Project Selector -->
        {#if projects.length > 0}
          <div class="w-64">
            <Select
              options={projects.map((p) => ({
                value: String(p.id),
                label: `${p.name} (#${p.id})`,
              }))}
              value={selectedProjectId ? String(selectedProjectId) : ""}
              onValueChange={handleSelectProject}
              ariaLabel="Select Project"
              placeholder="Select project…"
            />
          </div>
        {/if}

        {#if selectedProjectId}
          <Button
            size="sm"
            variant="secondary"
            onclick={() => push(`/viewer?project_id=${selectedProjectId}`)}
            title="Open project in 3D Viewer"
          >
            <ScanEye class="h-3.5 w-3.5" />
            <span>3D Viewer</span>
          </Button>
        {/if}
      </div>
    {/snippet}
  </PageHeader>

  <!-- Main Tabs Interface -->
  <div class="rounded-2xl border border-border-default bg-surface-card shadow-sm overflow-hidden">
    <Tabs.Root value={activeTab} onValueChange={(v) => (activeTab = v as any)}>
      <!-- Tab Navigation Bar -->
      <div class="border-b border-border-default bg-surface-canvas/50 px-4 py-2.5">
        <Tabs.List class="flex flex-wrap items-center gap-1.5">
          <Tabs.Trigger
            value="rag"
            class="flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all data-[state=active]:bg-surface-selected data-[state=active]:text-accent text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
          >
            <Sparkles class="h-3.5 w-3.5 text-accent" />
            <span>Graph-RAG Copilot</span>
          </Tabs.Trigger>

          <Tabs.Trigger
            value="health"
            class="flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all data-[state=active]:bg-surface-selected data-[state=active]:text-accent text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
          >
            <Activity class="h-3.5 w-3.5" />
            <span>Model Health</span>
          </Tabs.Trigger>

          <Tabs.Trigger
            value="regulatory"
            class="flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all data-[state=active]:bg-surface-selected data-[state=active]:text-accent text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
          >
            <BookOpen class="h-3.5 w-3.5" />
            <span>Regulatory GraphRAG</span>
          </Tabs.Trigger>

          <Tabs.Trigger
            value="cypher"
            class="flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all data-[state=active]:bg-surface-selected data-[state=active]:text-accent text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
          >
            <Database class="h-3.5 w-3.5" />
            <span>Cypher Presets</span>
          </Tabs.Trigger>

          <Tabs.Trigger
            value="sparql"
            class="flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all data-[state=active]:bg-surface-selected data-[state=active]:text-accent text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
          >
            <Code class="h-3.5 w-3.5" />
            <span>SPARQL Endpoint</span>
          </Tabs.Trigger>

          <Tabs.Trigger
            value="trace"
            class="flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-semibold transition-all data-[state=active]:bg-surface-selected data-[state=active]:text-accent text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
          >
            <GitFork class="h-3.5 w-3.5" />
            <span>Code-to-BIM Trace</span>
          </Tabs.Trigger>
        </Tabs.List>
      </div>

      <!-- TAB 0: GRAPH-RAG COPILOT -->
      <Tabs.Content value="rag" class="p-4 focus:outline-hidden">
        {#if !selectedProjectId}
          <div class="py-12">
            <EmptyState
              title="Select a Project"
              description="Choose a project above to start conversational Graph-RAG questioning across documents, BIM model elements, and regulatory standards."
            />
          </div>
        {:else}
          <div class="space-y-3">
            <div class="flex items-center justify-between px-4 py-2.5 rounded-xl border border-accent/30 bg-accent/10 text-xs">
              <div class="flex items-center gap-2">
                <Sparkles class="w-4 h-4 text-accent" />
                <span class="text-fg-primary font-medium">Looking for persistent chat history, thread search, and sidebar navigation?</span>
              </div>
              <button
                type="button"
                onclick={() => push(`/copilot?project_id=${selectedProjectId}`)}
                class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-accent text-white hover:bg-accent/90 transition-colors shadow-2xs cursor-pointer"
              >
                <span>Open Dedicated Copilot Page</span>
                <ExternalLink class="w-3.5 h-3.5" />
              </button>
            </div>

            <div class="h-[740px] rounded-2xl border border-border-default overflow-hidden bg-surface-canvas/20 shadow-inner">
              <AiChatbot
                projectId={selectedProjectId}
                persistent={true}
                onOpenDocument={(docId, page) => {
                  const pageParam = page ? `&page=${page}` : "";
                  const orgParam = authState.activeOrganizationId ? `&org=${authState.activeOrganizationId}` : "";
                  const projParam = selectedProjectId ? `&project_id=${selectedProjectId}` : "";
                  push(`/document?doc_id=${docId}${pageParam}${projParam}${orgParam}`);
                }}
                onIsolateElement={(guid) => push(`/viewer?project_id=${selectedProjectId}&guid=${guid}`)}
              />
            </div>
          </div>
        {/if}
      </Tabs.Content>

      <!-- TAB 1: MODEL HEALTH AUDIT -->
      <Tabs.Content value="health" class="p-6 space-y-6 focus:outline-hidden">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 class="text-sm font-semibold text-fg-primary">Pre-Flight Model Health Audit</h3>
            <p class="text-xs text-fg-muted">
              Declarative data-quality & metadata hygiene audit powered by Neo4j / Kùzu Cypher checks.
            </p>
          </div>
          <Button
            size="sm"
            variant="primary"
            onclick={loadHealthAudit}
            disabled={healthLoading || !selectedProjectId}
          >
            <RefreshCw class="h-3.5 w-3.5 {healthLoading ? 'animate-spin' : ''}" />
            <span>{healthLoading ? "Auditing…" : "Run Audit"}</span>
          </Button>
        </div>

        {#if !selectedProjectId}
          <EmptyState
            title="No project selected"
            description="Select a project in the top bar to inspect its pre-flight model health."
          />
        {:else if healthLoading}
          <LoadingState message="Running 8 pre-flight Cypher audit checks on model metadata…" />
        {:else if healthError}
          <div class="rounded-xl border border-critical-border bg-critical-bg p-4 text-critical text-xs">
            {healthError}
          </div>
        {:else if healthReport}
          <!-- Scorecard Cards -->
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div class="rounded-xl border border-border-default bg-surface-canvas/60 p-4 text-center">
              <span class="block text-micro uppercase font-bold text-fg-muted">Overall Health Score</span>
              <span class="mt-1 block text-3xl font-extrabold text-fg-primary">{healthReport.health_score}%</span>
              <span class="mt-1 block text-micro text-fg-muted">Based on 8 declarative quality axioms</span>
            </div>
            <div class="rounded-xl border border-border-default bg-surface-canvas/60 p-4 text-center">
              <span class="block text-micro uppercase font-bold text-fg-muted">Readiness Grade</span>
              <div class="mt-2 inline-flex items-center justify-center">
                <span class="rounded-lg px-3 py-1 text-base font-bold border {getGradeColor(healthReport.grade)}">
                  Grade {healthReport.grade}
                </span>
              </div>
              <span class="mt-1 block text-micro text-fg-muted">{healthReport.total_elements_audited} elements analyzed</span>
            </div>
            <div class="rounded-xl border border-border-default bg-surface-canvas/60 p-4 text-center">
              <span class="block text-micro uppercase font-bold text-fg-muted">Identified Violations</span>
              <span class="mt-1 block text-3xl font-extrabold {healthReport.total_violations > 0 ? 'text-warning' : 'text-success'}">
                {healthReport.total_violations}
              </span>
              <span class="mt-1 block text-micro text-fg-muted">
                {healthReport.total_violations === 0 ? "Model meets all hygiene criteria" : "Items requiring remediation"}
              </span>
            </div>
          </div>

          <!-- Evaluated Checks Breakdown -->
          <div class="space-y-3">
            <h4 class="text-xs font-bold uppercase tracking-wider text-fg-muted">
              Evaluated Data Quality Checks ({healthReport.checks.length})
            </h4>

            <div class="divide-y divide-border-subtle rounded-xl border border-border-default bg-surface-canvas/30 overflow-hidden">
              {#each healthReport.checks as check (check.key)}
                <div class="p-3 transition-colors hover:bg-surface-hover/50">
                  <button
                    type="button"
                    class="w-full text-left flex items-center justify-between cursor-pointer select-none bg-transparent border-0 p-0"
                    onclick={() => (expandedCheckKey = expandedCheckKey === check.key ? null : check.key)}
                  >
                    <div class="flex items-center gap-3">
                      {#if check.passed}
                        <CheckCircle2 class="h-4 w-4 text-success shrink-0" />
                      {:else if check.severity === "critical"}
                        <XCircle class="h-4 w-4 text-critical shrink-0" />
                      {:else}
                        <AlertTriangle class="h-4 w-4 text-warning shrink-0" />
                      {/if}
                      <div>
                        <span class="text-xs font-semibold text-fg-primary">{check.name}</span>
                        <p class="text-[11px] text-fg-muted">{check.description}</p>
                      </div>
                    </div>

                    <div class="flex items-center gap-3 shrink-0">
                      {#if check.passed}
                        <span class="rounded-md bg-success-bg px-2 py-0.5 text-micro font-bold text-success border border-success-border">
                          PASS
                        </span>
                      {:else}
                        <span class="rounded-md bg-critical-bg px-2 py-0.5 text-micro font-bold text-critical border border-critical-border">
                          {check.violation_count} violation{check.violation_count === 1 ? '' : 's'}
                        </span>
                      {/if}
                      <span class="text-fg-muted">
                        {#if expandedCheckKey === check.key}
                          <ChevronDown class="h-4 w-4" />
                        {:else}
                          <ChevronRight class="h-4 w-4" />
                        {/if}
                      </span>
                    </div>
                  </button>

                  {#if expandedCheckKey === check.key}
                    <div class="mt-3 pt-3 border-t border-border-subtle text-xs space-y-3">
                      <div class="flex items-start gap-2 rounded-lg bg-surface-card p-3 text-fg-secondary border border-border-subtle">
                        <Info class="h-4 w-4 text-accent shrink-0 mt-0.5" />
                        <div>
                          <strong class="text-fg-primary">Remediation Guidance:</strong> {check.recommendation}
                        </div>
                      </div>

                      {#if check.details && check.details.length > 0}
                        <div class="max-h-56 overflow-auto rounded-xl border border-border-default bg-surface-card">
                          <table class="w-full text-left text-xs">
                            <thead class="bg-surface-canvas/80 font-semibold text-fg-muted border-b border-border-subtle">
                              <tr>
                                <th class="px-3 py-2">Element GUID</th>
                                <th class="px-3 py-2">Element Name</th>
                                <th class="px-3 py-2">IFC Entity Type</th>
                              </tr>
                            </thead>
                            <tbody class="divide-y divide-border-subtle">
                              {#each check.details as detail, idx (idx)}
                                <tr class="hover:bg-surface-hover/40">
                                  <td class="px-3 py-1.5 font-mono text-fg-muted">{detail.guid ?? "N/A"}</td>
                                  <td class="px-3 py-1.5 text-fg-primary font-medium">{detail.name ?? "-"}</td>
                                  <td class="px-3 py-1.5 text-fg-secondary font-mono">{detail.type ?? "-"}</td>
                                </tr>
                              {/each}
                            </tbody>
                          </table>
                        </div>
                      {/if}
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {:else}
          <div class="py-12 text-center text-xs text-fg-muted">
            Click "Run Audit" to inspect model metadata quality and check schema hygiene.
          </div>
        {/if}
      </Tabs.Content>

      <!-- TAB 2: REGULATORY GRAPHRAG -->
      <Tabs.Content value="regulatory" class="p-6 space-y-6 focus:outline-hidden">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 class="text-sm font-semibold text-fg-primary">Regulatory GraphRAG Explorer</h3>
            <p class="text-xs text-fg-muted">
              Traverse the multi-layer knowledge graph linking building code standards, sections, clauses, and measurable BIM constraints.
            </p>
          </div>
          <Button
            size="sm"
            variant="secondary"
            onclick={triggerIngestRegulatory}
            disabled={regIngestLoading}
          >
            <Database class="h-3.5 w-3.5 {regIngestLoading ? 'animate-spin' : ''}" />
            <span>{regIngestLoading ? "Ingesting…" : "Ingest Standards to Neo4j"}</span>
          </Button>
        </div>

        {#if regIngestMessage}
          <div class="rounded-xl border border-success-border bg-success-bg p-3 text-success text-xs flex items-center gap-2">
            <CheckCircle2 class="h-4 w-4 shrink-0" />
            <span>{regIngestMessage}</span>
          </div>
        {/if}

        <div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <!-- Sub-panel A: Governing Requirements by IFC Class -->
          <div class="rounded-xl border border-border-default bg-surface-canvas/40 p-4 space-y-4">
            <div>
              <span class="block text-micro uppercase font-bold text-fg-muted">
                1. Governing Requirements by IFC Class
              </span>
              <p class="text-xs text-fg-muted mt-0.5">
                Query all cross-standard requirements governing a specific IFC entity type.
              </p>
            </div>

            <!-- Quick Suggestions -->
            <div class="flex flex-wrap gap-1.5">
              {#each COMMON_IFC_CLASSES as cls (cls)}
                <button
                  type="button"
                  onclick={() => {
                    regIfcType = cls;
                    loadGoverningReqs();
                  }}
                  class="rounded-lg border px-2 py-1 text-micro font-mono transition-colors cursor-pointer {regIfcType === cls
                    ? 'border-accent bg-accent/10 text-accent font-bold'
                    : 'border-border-default bg-surface-card text-fg-secondary hover:bg-surface-hover'}"
                >
                  {cls}
                </button>
              {/each}
            </div>

            <div class="flex items-center gap-2">
              <Input
                bind:value={regIfcType}
                placeholder="e.g. IfcDoor, IfcWall, IfcSpace"
                class="flex-1"
              />
              <Button size="sm" variant="primary" onclick={loadGoverningReqs} disabled={regRequirementsLoading}>
                <Search class="h-3.5 w-3.5" />
                <span>Query</span>
              </Button>
            </div>

            {#if regRequirementsLoading}
              <LoadingState message="Traversing regulatory graph relationships…" />
            {:else if regRequirementsError}
              <p class="text-critical text-xs">{regRequirementsError}</p>
            {:else if regRequirements}
              <div class="space-y-2">
                <p class="text-xs text-fg-muted">
                  Found <strong class="text-fg-primary">{regRequirements.total_requirements}</strong> requirement(s) across standards:
                  <strong class="text-accent">{regRequirements.standards_covered.join(", ") || "None"}</strong>
                </p>

                {#if regRequirements.requirements.length > 0}
                  <div class="max-h-64 overflow-auto rounded-xl border border-border-default bg-surface-card">
                    <table class="w-full text-left text-xs">
                      <thead class="bg-surface-canvas/80 font-semibold text-fg-muted border-b border-border-subtle">
                        <tr>
                          <th class="px-3 py-2">Standard & Clause</th>
                          <th class="px-3 py-2">Target Property</th>
                          <th class="px-3 py-2">Criterion</th>
                          <th class="px-3 py-2">Severity</th>
                        </tr>
                      </thead>
                      <tbody class="divide-y divide-border-subtle">
                        {#each regRequirements.requirements as req, idx (idx)}
                          <tr class="hover:bg-surface-hover/30">
                            <td class="px-3 py-2 text-fg-primary font-medium">
                              {req.standard} §{req.clause}
                            </td>
                            <td class="px-3 py-2 font-mono text-fg-muted">{req.parameter}</td>
                            <td class="px-3 py-2 font-mono text-accent font-semibold">
                              {req.operator} {req.value} {req.unit ?? ""}
                            </td>
                            <td class="px-3 py-2">
                              <span class="rounded bg-surface-hover px-1.5 py-0.5 text-micro font-bold uppercase text-fg-muted">
                                {req.severity}
                              </span>
                            </td>
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  </div>
                {/if}
              </div>
            {/if}
          </div>

          <!-- Sub-panel B: Regulatory Clause Graph Neighborhood -->
          <div class="rounded-xl border border-border-default bg-surface-canvas/40 p-4 space-y-4">
            <div>
              <span class="block text-micro uppercase font-bold text-fg-muted">
                2. Clause Graph Neighborhood & Cross-References
              </span>
              <p class="text-xs text-fg-muted mt-0.5">
                Inspect a clause's hierarchical section context, citations, and governed entities.
              </p>
            </div>

            <div class="flex items-center gap-2">
              <Input
                bind:value={regClauseQuery}
                placeholder="e.g. 1017.2, 716.2.2.1, 404.2.3"
                class="flex-1"
              />
              <Button size="sm" variant="primary" onclick={loadClauseContext} disabled={regClauseLoading}>
                <Search class="h-3.5 w-3.5" />
                <span>Lookup</span>
              </Button>
            </div>

            {#if regClauseLoading}
              <LoadingState message="Resolving clause context & cross-references in Neo4j…" />
            {:else if regClauseError}
              <p class="text-critical text-xs">{regClauseError}</p>
            {:else if regClauseContext}
              <div class="rounded-xl border border-border-default bg-surface-card p-4 space-y-3 text-xs">
                <div class="flex items-center justify-between border-b border-border-subtle pb-2">
                  <span class="font-bold text-sm text-fg-primary">
                    {regClauseContext.clause.standard} §{regClauseContext.clause.clause_id}
                  </span>
                  <span class="text-micro font-semibold text-fg-muted bg-surface-canvas px-2 py-0.5 rounded">
                    {regClauseContext.parent_section || "General"}
                  </span>
                </div>

                <p class="text-xs leading-relaxed text-fg-secondary">
                  {regClauseContext.clause.text || regClauseContext.clause.title}
                </p>

                <div class="space-y-1.5 pt-1">
                  <span class="text-micro font-bold uppercase tracking-wider text-fg-muted block">Governs IFC Entities:</span>
                  <div class="flex flex-wrap gap-1">
                    {#each regClauseContext.governed_ifc_types as t (t)}
                      <span class="rounded-md bg-surface-hover px-2 py-0.5 font-mono text-micro text-fg-primary border border-border-subtle">
                        {t}
                      </span>
                    {/each}
                  </div>
                </div>

                {#if regClauseContext.cross_referenced_clauses.length > 0}
                  <div class="pt-2 border-t border-border-subtle space-y-1.5">
                    <span class="text-micro font-bold uppercase tracking-wider text-fg-muted block">
                      Cited Cross-References:
                    </span>
                    <div class="flex flex-wrap gap-1.5">
                      {#each regClauseContext.cross_referenced_clauses as xref (xref.clause_id)}
                        <span class="rounded-md bg-accent/10 text-accent px-2 py-0.5 text-micro font-medium border border-accent/20">
                          §{xref.clause_id} ({xref.title || xref.standard})
                        </span>
                      {/each}
                    </div>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        </div>
      </Tabs.Content>

      <!-- TAB 3: CYPHER PRESETS -->
      <Tabs.Content value="cypher" class="p-6 space-y-6 focus:outline-hidden">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 class="text-sm font-semibold text-fg-primary">GraphRAG Cypher Query Presets</h3>
            <p class="text-xs text-fg-muted">
              Execute parameterized declarative graph queries against the project's Neo4j / Kùzu property graph.
            </p>
          </div>
          {#if selectedPreset}
            <Button
              size="sm"
              variant="primary"
              onclick={runPreset}
              disabled={presetLoading || !selectedProjectId}
            >
              <Play class="h-3.5 w-3.5 {presetLoading ? 'animate-spin' : ''}" />
              <span>{presetLoading ? "Running…" : "Run Query"}</span>
            </Button>
          {/if}
        </div>

        {#if !selectedProjectId}
          <EmptyState
            title="No project selected"
            description="Select a project in the top bar to run Cypher graph queries."
          />
        {:else if presets.length === 0}
          <EmptyState title="No presets available" description="Unable to load query presets from the graph gateway." />
        {:else}
          <div class="space-y-4">
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label class="block text-micro uppercase font-bold text-fg-muted mb-1.5" for="preset-select">
                  Select Query Preset
                </label>
                <Select
                  options={presets.map((p) => ({ value: p.key, label: p.label }))}
                  value={selectedPresetKey}
                  onValueChange={(v) => {
                    selectedPresetKey = v;
                    presetParamValues = {};
                  }}
                  ariaLabel="Cypher preset"
                />
              </div>

              {#if selectedPreset}
                <div class="rounded-xl border border-border-subtle bg-surface-canvas/50 p-3 text-xs flex flex-col justify-center">
                  <span class="font-semibold text-fg-primary">{selectedPreset.label}</span>
                  <p class="text-fg-muted mt-0.5">{selectedPreset.description}</p>
                </div>
              {/if}
            </div>

            <!-- Parameters Inputs -->
            {#if selectedPreset && selectedPreset.params.length > 0}
              <div class="rounded-xl border border-border-default bg-surface-canvas/30 p-4 space-y-3">
                <span class="block text-micro uppercase font-bold text-fg-muted">
                  Query Parameters
                </span>
                <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {#each selectedPreset.params as param (param)}
                    <div>
                      <label class="block text-micro font-semibold uppercase text-fg-muted mb-1" for={`param-${param}`}>
                        {param}
                      </label>
                      <Input
                        id={`param-${param}`}
                        bind:value={presetParamValues[param]}
                        placeholder={`Enter ${param}…`}
                      />
                    </div>
                  {/each}
                </div>
              </div>
            {/if}

            <!-- Execution Status & Results -->
            {#if presetLoading}
              <LoadingState message="Executing Cypher query on property graph…" />
            {:else if presetError}
              <div class="rounded-xl border border-critical-border bg-critical-bg p-4 text-critical text-xs">
                {presetError}
              </div>
            {:else if presetResult}
              <div class="space-y-2">
                <div class="flex items-center justify-between text-xs text-fg-muted">
                  <span>
                    Query returned <strong class="text-fg-primary">{presetResult.row_count}</strong> record(s).
                  </span>
                </div>

                {#if presetResult.rows.length > 0}
                  <div class="max-h-96 overflow-auto rounded-xl border border-border-default bg-surface-card">
                    <table class="w-full text-left text-xs">
                      <thead class="bg-surface-canvas/80 font-semibold text-fg-muted border-b border-border-subtle sticky top-0">
                        <tr>
                          {#each presetColumns as col (col)}
                            <th class="px-3.5 py-2">{col}</th>
                          {/each}
                        </tr>
                      </thead>
                      <tbody class="divide-y divide-border-subtle">
                        {#each presetResult.rows as row, idx (idx)}
                          <tr class="hover:bg-surface-hover/30">
                            {#each presetColumns as col (col)}
                              <td class="px-3.5 py-2 text-fg-secondary font-mono">
                                {typeof row[col] === "object" ? JSON.stringify(row[col]) : String(row[col] ?? "")}
                              </td>
                            {/each}
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  </div>
                {:else}
                  <div class="py-8 text-center text-xs text-fg-muted border border-dashed border-border-default rounded-xl">
                    Query completed with 0 matches.
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/if}
      </Tabs.Content>

      <!-- TAB 4: SPARQL ENDPOINT -->
      <Tabs.Content value="sparql" class="p-6 space-y-6 focus:outline-hidden">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 class="text-sm font-semibold text-fg-primary">SPARQL Semantic Query Console</h3>
            <p class="text-xs text-fg-muted">
              Query the RDF graph representation over Building Topology Ontology (BOT) and SAREF4BLDG ontologies.
            </p>
          </div>
          <Button
            size="sm"
            variant="primary"
            onclick={runSparql}
            disabled={sparqlLoading || !selectedProjectId}
          >
            <Play class="h-3.5 w-3.5 {sparqlLoading ? 'animate-spin' : ''}" />
            <span>{sparqlLoading ? "Executing…" : "Execute SPARQL"}</span>
          </Button>
        </div>

        {#if !selectedProjectId}
          <EmptyState
            title="No project selected"
            description="Select a project in the top bar to run SPARQL queries against its semantic graph."
          />
        {:else}
          <div class="space-y-4">
            <!-- Sample Query Shortcuts -->
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-micro uppercase font-bold text-fg-muted mr-1">Sample Queries:</span>
              {#each SPARQL_SAMPLE_QUERIES as sample (sample.label)}
                <button
                  type="button"
                  onclick={() => (sparqlText = sample.query)}
                  class="rounded-lg border border-border-default bg-surface-canvas/60 px-2.5 py-1 text-micro font-medium text-fg-secondary hover:bg-surface-hover hover:text-fg-primary transition-colors cursor-pointer"
                >
                  {sample.label}
                </button>
              {/each}
            </div>

            <!-- Query Editor -->
            <div class="rounded-xl border border-border-default bg-surface-canvas p-2 focus-within:border-accent">
              <textarea
                bind:value={sparqlText}
                rows="8"
                class="w-full bg-transparent p-2 font-mono text-xs text-fg-primary placeholder:text-fg-muted focus:outline-hidden resize-y"
                placeholder={"SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 25"}
              ></textarea>
            </div>

            <!-- Execution Status & Results -->
            {#if sparqlLoading}
              <LoadingState message="Executing semantic query across RDF graph…" />
            {:else if sparqlError}
              <div class="rounded-xl border border-critical-border bg-critical-bg p-4 text-critical text-xs">
                {sparqlError}
              </div>
            {:else if sparqlResult?.results}
              <div class="space-y-2">
                <span class="text-xs text-fg-muted">
                  Returned <strong class="text-fg-primary">{sparqlResult.results.bindings.length}</strong> binding(s).
                </span>

                {#if sparqlResult.results.bindings.length > 0}
                  <div class="max-h-96 overflow-auto rounded-xl border border-border-default bg-surface-card">
                    <table class="w-full text-left text-xs">
                      <thead class="bg-surface-canvas/80 font-semibold text-fg-muted border-b border-border-subtle sticky top-0">
                        <tr>
                          {#each sparqlVars as v (v)}
                            <th class="px-3.5 py-2 font-mono">?{v}</th>
                          {/each}
                        </tr>
                      </thead>
                      <tbody class="divide-y divide-border-subtle">
                        {#each sparqlResult.results.bindings as binding, idx (idx)}
                          <tr class="hover:bg-surface-hover/30">
                            {#each sparqlVars as v (v)}
                              <td class="px-3.5 py-2 text-fg-secondary font-mono truncate max-w-xs" title={binding[v]?.value ?? ""}>
                                {binding[v]?.value ?? ""}
                              </td>
                            {/each}
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  </div>
                {:else}
                  <div class="py-8 text-center text-xs text-fg-muted border border-dashed border-border-default rounded-xl">
                    No matching RDF triples found.
                  </div>
                {/if}
              </div>
            {:else if sparqlResult && "boolean" in sparqlResult}
              <div class="rounded-xl border border-border-default bg-surface-card p-4 text-xs">
                <span>Result: <strong class="text-accent">{sparqlResult.boolean ? "TRUE" : "FALSE"}</strong></span>
              </div>
            {/if}
          </div>
        {/if}
      </Tabs.Content>

      <!-- TAB 5: CODE-TO-BIM TRACE -->
      <Tabs.Content value="trace" class="p-6 space-y-6 focus:outline-hidden">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 class="text-sm font-semibold text-fg-primary">Code-to-BIM Traceability Matrix</h3>
            <p class="text-xs text-fg-muted">
              Live linkage connecting regulatory building code rules to actual IFC elements present in this project's model.
            </p>
          </div>
          <Button
            size="sm"
            variant="secondary"
            onclick={loadTrace}
            disabled={traceLoading || !selectedProjectId}
          >
            <RefreshCw class="h-3.5 w-3.5 {traceLoading ? 'animate-spin' : ''}" />
            <span>Refresh Trace</span>
          </Button>
        </div>

        {#if !selectedProjectId}
          <EmptyState
            title="No project selected"
            description="Select a project in the top bar to inspect its code-to-BIM element mappings."
          />
        {:else if traceLoading}
          <LoadingState message="Computing bipartite graph trace between rules and IFC elements…" />
        {:else if traceError}
          <div class="rounded-xl border border-critical-border bg-critical-bg p-4 text-critical text-xs">
            {traceError}
          </div>
        {:else if trace}
          <!-- Search Toolbar -->
          <div class="flex items-center gap-3">
            <Input
              bind:value={traceSearch}
              placeholder="Filter by rule reference, IFC class, or clause description…"
              class="max-w-md"
            />
            <span class="text-xs text-fg-muted">
              Showing {filteredTraceEntries.length} of {trace.entries.length} mapping(s)
            </span>
          </div>

          {#if filteredTraceEntries.length > 0}
            <div class="overflow-auto rounded-xl border border-border-default bg-surface-card max-h-[500px]">
              <table class="w-full text-left text-xs">
                <thead class="bg-surface-canvas/80 font-semibold text-fg-muted border-b border-border-subtle sticky top-0">
                  <tr>
                    <th class="px-4 py-2.5">Rule Reference</th>
                    <th class="px-4 py-2.5">Target IFC Class</th>
                    <th class="px-4 py-2.5">Rule Description</th>
                    <th class="px-4 py-2.5 text-right">Model Element Count</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-border-subtle">
                  {#each filteredTraceEntries as entry (entry.rule_id)}
                    <tr class="hover:bg-surface-hover/30 transition-colors">
                      <td class="px-4 py-2.5 font-bold text-fg-primary">
                        {entry.reference || `Rule #${entry.rule_id}`}
                      </td>
                      <td class="px-4 py-2.5">
                        <span class="rounded-md bg-accent/10 text-accent px-2 py-0.5 font-mono text-micro border border-accent/20">
                          {entry.target_ifc_class}
                        </span>
                      </td>
                      <td class="px-4 py-2.5 text-fg-secondary max-w-md truncate" title={entry.description}>
                        {entry.description || "-"}
                      </td>
                      <td class="px-4 py-2.5 text-right font-mono font-bold text-fg-primary">
                        {entry.element_count.toLocaleString()}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {:else}
            <div class="py-12 text-center text-xs text-fg-muted border border-dashed border-border-default rounded-xl">
              No matching rule-to-BIM traces found for the current search filter.
            </div>
          {/if}
        {/if}
      </Tabs.Content>
    </Tabs.Root>
  </div>
</div>
