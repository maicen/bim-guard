<script lang="ts">
  import { Tabs } from "bits-ui";
  import {
    Activity,
    AlertTriangle,
    BookOpen,
    CheckCircle2,
    Database,
    Info,
    Play,
    RefreshCw,
    Search,
    ShieldAlert,
    XCircle,
  } from "lucide-svelte";
  import { graphApi, sparqlApi } from "../../api";
  import type {
    CodeToIfcTraceResponse,
    GoverningRequirementsResponse,
    GraphQueryPresetSummary,
    GraphQueryResultResponse,
    ModelHealthAuditReport,
    RegulatoryGraphContextResponse,
    SparqlQueryResult,
  } from "../../types";
  import { Button, Select } from "../ui";
  import LoadingState from "../LoadingState.svelte";

  let { projectId }: { projectId: number | null } = $props();

  let activeTab = $state("health");

  // --- Model Health Audit (inspired by ifc-to-graph-assignment) ---
  let healthReport: ModelHealthAuditReport | null = $state(null);
  let healthLoading = $state(false);
  let healthError = $state("");
  let expandedCheckKey = $state<string | null>(null);

  async function loadHealthAudit() {
    if (!projectId) return;
    healthLoading = true;
    healthError = "";
    try {
      healthReport = await graphApi.getModelHealth(projectId);
    } catch (err: any) {
      healthError = err?.message || "Failed to evaluate model health audit.";
    } finally {
      healthLoading = false;
    }
  }

  $effect(() => {
    if (activeTab === "health" && projectId && !healthReport && !healthLoading) {
      loadHealthAudit();
    }
  });

  // --- Regulatory Knowledge Graph (inspired by kg-lite-builder) ---
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

  async function loadGoverningReqs() {
    regRequirementsLoading = true;
    regRequirementsError = "";
    try {
      regRequirements = await graphApi.getGoverningRequirements(regIfcType);
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
      const res = await graphApi.ingestRegulatoryGraph();
      regIngestMessage = `Ingested ${res.nodes ?? 0} nodes and ${res.edges ?? 0} edges into Neo4j graph.`;
    } catch (err: any) {
      regIngestMessage = err?.message || "Failed to ingest regulatory graph.";
    } finally {
      regIngestLoading = false;
    }
  }

  $effect(() => {
    if (activeTab === "regulatory" && !regRequirements && !regRequirementsLoading) {
      loadGoverningReqs();
    }
  });

  // --- Cypher presets: the only way this console reaches the property graph ---
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
      if (presets.length && !selectedPresetKey) selectedPresetKey = presets[0].key;
    } catch {
      presets = [];
    }
  }

  async function runPreset() {
    if (!projectId || !selectedPreset) return;
    presetLoading = true;
    presetError = "";
    presetResult = null;
    try {
      presetResult = await graphApi.runQueryPreset(projectId, selectedPreset.key, presetParamValues);
    } catch (err: any) {
      presetError = err?.message || "Preset query failed.";
    } finally {
      presetLoading = false;
    }
  }

  $effect(() => {
    loadPresets();
  });

  const presetColumns = $derived(
    presetResult && presetResult.rows.length ? Object.keys(presetResult.rows[0]) : [],
  );

  // --- SPARQL ---
  let sparqlText = $state("SELECT * WHERE { ?s ?p ?o } LIMIT 20");
  let sparqlResult: SparqlQueryResult | null = $state(null);
  let sparqlLoading = $state(false);
  let sparqlError = $state("");

  async function runSparql() {
    if (!projectId || !sparqlText.trim()) return;
    sparqlLoading = true;
    sparqlError = "";
    sparqlResult = null;
    try {
      sparqlResult = await sparqlApi.query(projectId, sparqlText);
    } catch (err: any) {
      sparqlError = err?.message || "SPARQL query failed.";
    } finally {
      sparqlLoading = false;
    }
  }

  const sparqlVars = $derived(sparqlResult?.head?.vars ?? []);

  // --- Code-to-BIM trace ---
  let trace: CodeToIfcTraceResponse | null = $state(null);
  let traceLoading = $state(false);
  let traceError = $state("");

  async function loadTrace() {
    if (!projectId) return;
    traceLoading = true;
    traceError = "";
    try {
      trace = await graphApi.getCodeToIfcTrace(projectId);
    } catch (err: any) {
      traceError = err?.message || "Could not load the code-to-IFC trace.";
    } finally {
      traceLoading = false;
    }
  }

  $effect(() => {
    if (activeTab === "trace" && projectId && !trace && !traceLoading) loadTrace();
  });

  function getGradeColor(grade: string) {
    if (grade === "A" || grade === "B") return "text-success border-success-border bg-success-bg";
    if (grade === "C") return "text-warning border-warning-border bg-warning-bg";
    return "text-critical border-critical-border bg-critical-bg";
  }
</script>

<div class="p-2 text-xs">
  <Tabs.Root value={activeTab} onValueChange={(v) => (activeTab = v)}>
    <Tabs.List
      class="flex flex-wrap items-center gap-1 rounded-xl border border-border-default bg-surface-canvas/60 p-1"
    >
      <Tabs.Trigger
        value="health"
        class="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-semibold transition-all data-[state=active]:bg-accent data-[state=active]:text-white text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
      >
        <Activity class="h-3 w-3" />
        Model Health
      </Tabs.Trigger>
      <Tabs.Trigger
        value="regulatory"
        class="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-semibold transition-all data-[state=active]:bg-accent data-[state=active]:text-white text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
      >
        <BookOpen class="h-3 w-3" />
        Regulatory GraphRAG
      </Tabs.Trigger>
      <Tabs.Trigger
        value="cypher"
        class="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-semibold transition-all data-[state=active]:bg-accent data-[state=active]:text-white text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
      >
        <Database class="h-3 w-3" />
        Cypher Presets
      </Tabs.Trigger>
      <Tabs.Trigger
        value="sparql"
        class="rounded-lg px-2.5 py-1 text-[11px] font-semibold transition-all data-[state=active]:bg-accent data-[state=active]:text-white text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
      >
        SPARQL
      </Tabs.Trigger>
      <Tabs.Trigger
        value="trace"
        class="rounded-lg px-2.5 py-1 text-[11px] font-semibold transition-all data-[state=active]:bg-accent data-[state=active]:text-white text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
      >
        Code-to-BIM Trace
      </Tabs.Trigger>
    </Tabs.List>
  </Tabs.Root>

  <!-- TAB 1: MODEL HEALTH AUDIT -->
  {#if activeTab === "health"}
    <div class="mt-3 space-y-3">
      <div class="flex items-center justify-between">
        <div>
          <h4 class="text-xs font-semibold text-fg-primary">Pre-Flight Model Health Audit</h4>
          <p class="text-[11px] text-fg-muted">
            Declarative data-quality & metadata hygiene audit powered by Cypher checks.
          </p>
        </div>
        <Button
          size="sm"
          variant="primary"
          onclick={loadHealthAudit}
          disabled={healthLoading || !projectId}
        >
          <RefreshCw class="h-3 w-3 {healthLoading ? 'animate-spin' : ''}" />
          Run Audit
        </Button>
      </div>

      {#if healthLoading}
        <LoadingState message="Running 8 pre-flight Cypher audit checks…" />
      {:else if healthError}
        <div class="rounded-lg border border-critical-border bg-critical-bg p-2 text-critical text-[11px]">
          {healthError}
        </div>
      {:else if healthReport}
        <!-- Health Scorecard -->
        <div class="grid grid-cols-3 gap-2">
          <div class="rounded-lg border border-border-default bg-surface-card p-2.5 text-center">
            <span class="block text-[10px] uppercase font-semibold text-fg-muted">Health Score</span>
            <span class="text-xl font-bold text-fg-primary">{healthReport.health_score}%</span>
          </div>
          <div class="rounded-lg border border-border-default bg-surface-card p-2.5 text-center">
            <span class="block text-[10px] uppercase font-semibold text-fg-muted">Readiness Grade</span>
            <span class="inline-block px-2 py-0.5 rounded text-sm font-bold border {getGradeColor(healthReport.grade)}">
              Grade {healthReport.grade}
            </span>
          </div>
          <div class="rounded-lg border border-border-default bg-surface-card p-2.5 text-center">
            <span class="block text-[10px] uppercase font-semibold text-fg-muted">Violations</span>
            <span class="text-xl font-bold {healthReport.total_violations > 0 ? 'text-warning' : 'text-success'}">
              {healthReport.total_violations}
            </span>
          </div>
        </div>

        <!-- Checklist of 8 quality rules -->
        <div class="space-y-1.5">
          <h5 class="text-[11px] font-semibold uppercase tracking-wider text-fg-muted">
            Evaluated Data Quality Checks
          </h5>
          {#each healthReport.checks as check (check.key)}
            <div class="rounded-lg border border-border-default bg-surface-card p-2 transition-all">
              <button
                type="button"
                class="w-full text-left flex items-center justify-between cursor-pointer select-none bg-transparent border-0 p-0"
                onclick={() => (expandedCheckKey = expandedCheckKey === check.key ? null : check.key)}
              >
                <div class="flex items-center gap-2">
                  {#if check.passed}
                    <CheckCircle2 class="h-4 w-4 text-success shrink-0" />
                  {:else if check.severity === "critical"}
                    <XCircle class="h-4 w-4 text-critical shrink-0" />
                  {:else}
                    <AlertTriangle class="h-4 w-4 text-warning shrink-0" />
                  {/if}
                  <div>
                    <span class="font-medium text-fg-primary text-[11px]">{check.name}</span>
                    <p class="text-[10px] text-fg-muted">{check.description}</p>
                  </div>
                </div>
                <div class="flex items-center gap-1.5 shrink-0">
                  {#if check.passed}
                    <span class="rounded bg-success-bg px-1.5 py-0.5 text-[10px] font-semibold text-success border border-success-border">
                      PASS
                    </span>
                  {:else}
                    <span class="rounded bg-critical-bg px-1.5 py-0.5 text-[10px] font-semibold text-critical border border-critical-border">
                      {check.violation_count} issue{check.violation_count === 1 ? '' : 's'}
                    </span>
                  {/if}
                </div>
              </button>

              {#if expandedCheckKey === check.key}
                <div class="mt-2 pt-2 border-t border-border-subtle text-[11px] space-y-1.5">
                  <div class="flex items-start gap-1.5 text-accent">
                    <Info class="h-3.5 w-3.5 shrink-0 mt-0.5" />
                    <span><strong>Recommendation:</strong> {check.recommendation}</span>
                  </div>

                  {#if check.details && check.details.length > 0}
                    <div class="max-h-36 overflow-auto rounded border border-border-default bg-surface-canvas/60 mt-1">
                      <table class="w-full text-left text-[10px]">
                        <thead class="bg-surface-canvas font-semibold text-fg-muted">
                          <tr>
                            <th class="px-2 py-1">GUID</th>
                            <th class="px-2 py-1">Name</th>
                            <th class="px-2 py-1">Type</th>
                          </tr>
                        </thead>
                        <tbody>
                          {#each check.details as detail, idx (idx)}
                            <tr class="border-t border-border-subtle">
                              <td class="px-2 py-0.5 font-mono text-fg-muted">{detail.guid ?? "N/A"}</td>
                              <td class="px-2 py-0.5 text-fg-secondary">{detail.name ?? ""}</td>
                              <td class="px-2 py-0.5 text-fg-muted">{detail.type ?? ""}</td>
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
      {:else}
        <p class="text-fg-muted">Click "Run Audit" to inspect model metadata quality.</p>
      {/if}
    </div>

  <!-- TAB 2: REGULATORY KNOWLEDGE GRAPH -->
  {:else if activeTab === "regulatory"}
    <div class="mt-3 space-y-3">
      <div class="flex items-center justify-between">
        <div>
          <h4 class="text-xs font-semibold text-fg-primary">Regulatory GraphRAG Explorer</h4>
          <p class="text-[11px] text-fg-muted">
            Knowledge graph linking standards, sections, clauses, and measurable BIM requirements.
          </p>
        </div>
        <Button
          size="sm"
          variant="secondary"
          onclick={triggerIngestRegulatory}
          disabled={regIngestLoading}
        >
          <Database class="h-3 w-3 {regIngestLoading ? 'animate-spin' : ''}" />
          Ingest to Neo4j
        </Button>
      </div>

      {#if regIngestMessage}
        <div class="rounded-lg border border-success-border bg-success-bg p-2 text-success text-[11px]">
          {regIngestMessage}
        </div>
      {/if}

      <!-- Query by IFC Entity Class -->
      <div class="rounded-lg border border-border-default bg-surface-card p-2.5 space-y-2">
        <span class="block text-[10px] uppercase font-semibold text-fg-muted">
          Governing Requirements by IFC Class
        </span>
        <div class="flex items-center gap-1.5">
          <input
            type="text"
            bind:value={regIfcType}
            class="flex-1 rounded-lg border border-border-default bg-surface-canvas px-2 py-1 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
            placeholder="e.g. IfcDoor, IfcWall, IfcSpace"
          />
          <Button size="sm" variant="primary" onclick={loadGoverningReqs} disabled={regRequirementsLoading}>
            <Search class="h-3 w-3" />
            Query
          </Button>
        </div>

        {#if regRequirementsLoading}
          <LoadingState message="Traversing regulatory graph…" />
        {:else if regRequirementsError}
          <p class="text-critical text-[11px]">{regRequirementsError}</p>
        {:else if regRequirements}
          <p class="text-fg-muted text-[10px]">
            Found {regRequirements.total_requirements} requirement(s) across standards:
            <strong>{regRequirements.standards_covered.join(", ") || "None"}</strong>
          </p>
          {#if regRequirements.requirements.length > 0}
            <div class="max-h-40 overflow-auto rounded border border-border-default">
              <table class="w-full text-left text-[10px]">
                <thead class="bg-surface-canvas/60 font-semibold text-fg-muted">
                  <tr>
                    <th class="px-2 py-1">Standard / Clause</th>
                    <th class="px-2 py-1">Parameter</th>
                    <th class="px-2 py-1">Criteria</th>
                    <th class="px-2 py-1">Severity</th>
                  </tr>
                </thead>
                <tbody>
                  {#each regRequirements.requirements as req, idx (idx)}
                    <tr class="border-t border-border-subtle">
                      <td class="px-2 py-1 text-fg-secondary font-medium">
                        {req.standard} §{req.clause}
                      </td>
                      <td class="px-2 py-1 font-mono text-fg-muted">{req.parameter}</td>
                      <td class="px-2 py-1 text-fg-primary font-mono">{req.operator} {req.value} {req.unit ?? ''}</td>
                      <td class="px-2 py-1">
                        <span class="rounded bg-surface-hover px-1 py-0.5 text-[9px] font-semibold uppercase text-fg-muted">
                          {req.severity}
                        </span>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        {/if}
      </div>

      <!-- Query Clause Neighborhood Context -->
      <div class="rounded-lg border border-border-default bg-surface-card p-2.5 space-y-2">
        <span class="block text-[10px] uppercase font-semibold text-fg-muted">
          Clause Graph Neighborhood & Cross-References
        </span>
        <div class="flex items-center gap-1.5">
          <input
            type="text"
            bind:value={regClauseQuery}
            class="flex-1 rounded-lg border border-border-default bg-surface-canvas px-2 py-1 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
            placeholder="e.g. 1017.2, 716.2.2.1, 404.2.3"
          />
          <Button size="sm" variant="primary" onclick={loadClauseContext} disabled={regClauseLoading}>
            <Search class="h-3 w-3" />
            Lookup
          </Button>
        </div>

        {#if regClauseLoading}
          <LoadingState message="Resolving clause context & cross-references…" />
        {:else if regClauseError}
          <p class="text-critical text-[11px]">{regClauseError}</p>
        {:else if regClauseContext}
          <div class="rounded border border-border-subtle bg-surface-canvas/60 p-2 space-y-1.5 text-[11px]">
            <div class="flex items-center justify-between">
              <span class="font-bold text-fg-primary">
                {regClauseContext.clause.standard} §{regClauseContext.clause.clause_id}
              </span>
              <span class="text-[10px] text-fg-muted">{regClauseContext.parent_section}</span>
            </div>
            <p class="text-fg-secondary">{regClauseContext.clause.text || regClauseContext.clause.title}</p>
            <div class="flex items-center gap-1.5 text-[10px] text-fg-muted pt-1">
              <span>Governs:</span>
              {#each regClauseContext.governed_ifc_types as t (t)}
                <span class="rounded bg-surface-hover px-1 py-0.2 font-mono text-fg-primary">{t}</span>
              {/each}
            </div>

            {#if regClauseContext.cross_referenced_clauses.length > 0}
              <div class="pt-1.5 border-t border-border-subtle">
                <span class="text-[10px] font-semibold text-fg-muted uppercase block">
                  Cited Cross-References in Standard:
                </span>
                <div class="flex flex-wrap gap-1 mt-1">
                  {#each regClauseContext.cross_referenced_clauses as xref (xref.clause_id)}
                    <span class="rounded bg-accent/10 text-accent px-1.5 py-0.5 text-[10px] border border-accent/20">
                      §{xref.clause_id} ({xref.title})
                    </span>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    </div>

  <!-- TAB 3: CYPHER PRESETS -->
  {:else if activeTab === "cypher"}
    <div class="mt-2 space-y-2">
      {#if presets.length === 0}
        <p class="text-fg-muted">No presets available.</p>
      {:else}
        <Select
          options={presets.map((p) => ({ value: p.key, label: p.label }))}
          value={selectedPresetKey}
          onValueChange={(v) => {
            selectedPresetKey = v;
            presetParamValues = {};
          }}
          ariaLabel="Cypher preset"
        />
        {#if selectedPreset}
          <p class="text-fg-muted">{selectedPreset.description}</p>
          {#each selectedPreset.params as param (param)}
            <label class="block">
              <span class="mb-1 block text-[10px] font-semibold uppercase tracking-wider text-fg-muted">
                {param}
              </span>
              <input
                type="text"
                bind:value={presetParamValues[param]}
                class="w-full rounded-lg border border-border-default bg-surface-canvas px-2 py-1 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
                placeholder={param}
              />
            </label>
          {/each}
          <Button
            size="sm"
            variant="primary"
            onclick={runPreset}
            disabled={presetLoading || !projectId}
          >
            <Play class="h-3 w-3" />
            Run
          </Button>
        {/if}

        {#if presetLoading}
          <LoadingState message="Running preset…" />
        {:else if presetError}
          <p class="text-critical">{presetError}</p>
        {:else if presetResult}
          <p class="text-fg-muted">{presetResult.row_count} row(s)</p>
          {#if presetResult.rows.length}
            <div class="overflow-auto rounded-lg border border-border-default">
              <table class="w-full text-left text-[11px]">
                <thead class="bg-surface-canvas/60">
                  <tr>
                    {#each presetColumns as col (col)}
                      <th class="px-2 py-1 font-semibold text-fg-muted">{col}</th>
                    {/each}
                  </tr>
                </thead>
                <tbody>
                  {#each presetResult.rows as row, i (i)}
                    <tr class="border-t border-border-subtle">
                      {#each presetColumns as col (col)}
                        <td class="px-2 py-1 text-fg-secondary">{String(row[col] ?? "")}</td>
                      {/each}
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        {/if}
      {/if}
    </div>

  <!-- TAB 4: SPARQL -->
  {:else if activeTab === "sparql"}
    <div class="mt-2 space-y-2">
      <textarea
        bind:value={sparqlText}
        rows="5"
        class="w-full rounded-lg border border-border-default bg-surface-canvas px-2 py-1.5 font-mono text-[11px] text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
        placeholder="SELECT * WHERE ?s ?p ?o LIMIT 20"
      ></textarea>
      <Button size="sm" variant="primary" onclick={runSparql} disabled={sparqlLoading || !projectId}>
        <Play class="h-3 w-3" />
        Run
      </Button>

      {#if sparqlLoading}
        <LoadingState message="Running SPARQL query…" />
      {:else if sparqlError}
        <p class="text-critical">{sparqlError}</p>
      {:else if sparqlResult?.results}
        <p class="text-fg-muted">{sparqlResult.results.bindings.length} row(s)</p>
        {#if sparqlResult.results.bindings.length}
          <div class="overflow-auto rounded-lg border border-border-default">
            <table class="w-full text-left text-[11px]">
              <thead class="bg-surface-canvas/60">
                <tr>
                  {#each sparqlVars as v (v)}
                    <th class="px-2 py-1 font-semibold text-fg-muted">{v}</th>
                  {/each}
                </tr>
              </thead>
              <tbody>
                {#each sparqlResult.results.bindings as binding, i (i)}
                  <tr class="border-t border-border-subtle">
                    {#each sparqlVars as v (v)}
                      <td class="px-2 py-1 text-fg-secondary">{binding[v]?.value ?? ""}</td>
                    {/each}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      {:else if sparqlResult && "boolean" in sparqlResult}
        <p class="text-fg-secondary">Result: {sparqlResult.boolean ? "true" : "false"}</p>
      {/if}
    </div>

  <!-- TAB 5: CODE-TO-BIM TRACE -->
  {:else if activeTab === "trace"}
    <div class="mt-2 space-y-2">
      <p class="text-fg-muted">
        Rule catalog clauses whose target IFC class this project's model actually contains --
        the only link between a clause and a component that exists today.
      </p>
      {#if traceLoading}
        <LoadingState message="Building code-to-IFC trace…" />
      {:else if traceError}
        <p class="text-critical">{traceError}</p>
      {:else if trace && trace.entries.length === 0}
        <p class="text-fg-muted">No rule targets an IFC class present in this model.</p>
      {:else if trace}
        <div class="overflow-auto rounded-lg border border-border-default">
          <table class="w-full text-left text-[11px]">
            <thead class="bg-surface-canvas/60">
              <tr>
                <th class="px-2 py-1 font-semibold text-fg-muted">Rule</th>
                <th class="px-2 py-1 font-semibold text-fg-muted">IFC Class</th>
                <th class="px-2 py-1 font-semibold text-fg-muted">Elements</th>
              </tr>
            </thead>
            <tbody>
              {#each trace.entries as entry (entry.rule_id)}
                <tr class="border-t border-border-subtle">
                  <td class="px-2 py-1 text-fg-secondary">{entry.reference || `Rule #${entry.rule_id}`}</td>
                  <td class="px-2 py-1 font-mono text-fg-secondary">{entry.target_ifc_class}</td>
                  <td class="px-2 py-1 text-fg-secondary">{entry.element_count}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
</div>
