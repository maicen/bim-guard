<script lang="ts">
  import { Tabs } from "bits-ui";
  import { Play } from "lucide-svelte";
  import { graphApi, sparqlApi } from "../../api";
  import type {
    CodeToIfcTraceResponse,
    GraphQueryPresetSummary,
    GraphQueryResultResponse,
    SparqlQueryResult,
  } from "../../types";
  import { Button, Select } from "../ui";
  import LoadingState from "../LoadingState.svelte";

  let { projectId }: { projectId: number | null } = $props();

  let activeTab = $state("cypher");

  // --- Cypher presets: the only way this console reaches the property graph
  // (Neo4j/Kùzu) -- free-form Cypher isn't exposed since that store has no
  // per-project isolation, unlike the triplestore SPARQL uses below. ---
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

  // --- SPARQL: free-form is safe here (GraphTriplestoreService.query() only
  // accepts pyoxigraph's read-only query forms and is tenant-isolated per
  // project via named_graphs). ---
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
</script>

<div class="p-2 text-xs">
  <Tabs.Root value={activeTab} onValueChange={(v) => (activeTab = v)}>
    <Tabs.List
      class="flex w-fit items-center gap-1 rounded-xl border border-border-default bg-surface-canvas/60 p-1"
    >
      <Tabs.Trigger
        value="cypher"
        class="rounded-lg px-2.5 py-1 text-[11px] font-semibold transition-all data-[state=active]:bg-accent data-[state=active]:text-white text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
      >
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

  {#if activeTab === "cypher"}
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
