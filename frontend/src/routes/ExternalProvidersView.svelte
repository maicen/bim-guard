<script lang="ts">
  import {
    Plug,
    FileText,
    BrainCircuit,
    Plus,
    Cloud,
    Server,
    ShieldAlert,
    Building2,
    Settings2,
    Star,
  } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import TabStrip from "../lib/components/TabStrip.svelte";
  import ProviderInstanceCard from "../lib/components/ProviderInstanceCard.svelte";
  import ProviderInstanceForm from "../lib/components/ProviderInstanceForm.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import TaskAssignmentModal from "../lib/components/TaskAssignmentModal.svelte";
  import { parsingEnginesApi, llmProvidersApi } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import { formatModelMeta } from "../lib/utils/formatModelMeta";
  import type {
    ParsingEngineInstance,
    ParsingEngineKind,
    ParsingEngineKindId,
    LLMProviderInstance,
    LLMProviderInstanceTestResult,
    LLMProviderKind,
    LLMProviderKindId,
    LLMProviderModel,
    LLMTask,
    LLMTaskModelAssignment,
  } from "../lib/types";

  let activeOrg = $derived(authState.activeOrganization);
  let activeTab = $state<"parsing" | "llm">("parsing");

  const TABS = [
    { id: "parsing", label: "Document Parsing", icon: FileText },
    { id: "llm", label: "LLM Providers", icon: BrainCircuit },
  ];

  // Accent color by provider family/kind — purely cosmetic grouping.
  const FAMILY_ACCENT: Record<string, string> = {
    unstructured: "text-cyan-400",
    docling: "text-violet-400",
    openai: "text-emerald-400",
    anthropic: "text-orange-400",
    gemini: "text-blue-400",
    openrouter: "text-fuchsia-400",
    ollama: "text-teal-400",
    default: "text-blue-400",
  };

  // ── Document Parsing (platform-wide, superadmin-managed) ────────────────
  let engines = $state<ParsingEngineInstance[]>([]);
  let engineKinds = $state<ParsingEngineKind[]>([]);
  let enginesLoading = $state(true);
  let enginesError = $state("");
  let showAddEngineForm = $state(false);
  let isSavingEngine = $state(false);
  let newEngineName = $state("");
  let newEngineKind = $state<ParsingEngineKindId>("");
  let newEngineUrl = $state("");
  let newEngineKey = $state("");
  let newEngineStrategy = $state("auto");
  let newEngineNotes = $state("");
  let enginePendingDelete = $state<ParsingEngineInstance | null>(null);
  let testingEngineId = $state<number | null>(null);
  let engineTestResults = $state<Record<number, { ok: boolean; detail: string }>>({});

  function engineKindInfo(kind: ParsingEngineKindId): ParsingEngineKind | null {
    return engineKinds.find((k) => k.kind === kind) ?? null;
  }

  async function loadEngineKinds() {
    try {
      engineKinds = await parsingEnginesApi.kinds();
      if (!newEngineKind && engineKinds.length > 0) newEngineKind = engineKinds[0].kind;
    } catch (err: any) {
      enginesError = err.message || "Failed to load parsing engine kinds.";
    }
  }

  async function loadEngines() {
    enginesLoading = true;
    enginesError = "";
    try {
      engines = await parsingEnginesApi.list();
    } catch (err: any) {
      enginesError = err.message || "Failed to load parsing engines.";
    } finally {
      enginesLoading = false;
    }
  }

  function resetEngineForm() {
    newEngineName = "";
    newEngineKind = engineKinds[0]?.kind ?? "";
    newEngineUrl = "";
    newEngineKey = "";
    newEngineStrategy = "auto";
    newEngineNotes = "";
  }

  async function handleAddEngine() {
    const selectedKindInfo = engineKindInfo(newEngineKind);
    if (!newEngineName.trim() || !newEngineUrl.trim() || !newEngineKind) {
      enginesError = "Name, kind, and API URL are required.";
      return;
    }
    if (selectedKindInfo?.requires_api_key && !newEngineKey.trim()) {
      enginesError = `A ${selectedKindInfo.display_name} instance requires an API key.`;
      return;
    }
    isSavingEngine = true;
    enginesError = "";
    try {
      await parsingEnginesApi.create({
        name: newEngineName.trim(),
        kind: newEngineKind,
        api_url: newEngineUrl.trim(),
        api_key: newEngineKey.trim() || undefined,
        strategy: newEngineStrategy.trim() || "auto",
        is_default: engines.length === 0,
        notes: newEngineNotes.trim() || undefined,
      });
      resetEngineForm();
      showAddEngineForm = false;
      await loadEngines();
    } catch (err: any) {
      enginesError = err.message || "Failed to register parsing engine.";
    } finally {
      isSavingEngine = false;
    }
  }

  async function handleSetDefaultEngine(engine: ParsingEngineInstance) {
    try {
      await parsingEnginesApi.update(engine.id, { is_default: true });
      await loadEngines();
    } catch (err: any) {
      enginesError = err.message || "Failed to set default parsing engine.";
    }
  }

  async function handleToggleEngineEnabled(engine: ParsingEngineInstance) {
    try {
      await parsingEnginesApi.update(engine.id, { is_enabled: !engine.is_enabled });
      await loadEngines();
    } catch (err: any) {
      enginesError = err.message || "Failed to update parsing engine.";
    }
  }

  async function handleTestEngine(engine: ParsingEngineInstance) {
    testingEngineId = engine.id;
    try {
      engineTestResults = { ...engineTestResults, [engine.id]: await parsingEnginesApi.test(engine.id) };
    } catch (err: any) {
      engineTestResults = {
        ...engineTestResults,
        [engine.id]: { ok: false, detail: err.message || "Test failed." },
      };
    } finally {
      testingEngineId = null;
    }
  }

  async function handleDeleteEngine() {
    const engine = enginePendingDelete;
    if (!engine) return;
    try {
      await parsingEnginesApi.delete(engine.id);
      engines = engines.filter((e) => e.id !== engine.id);
    } catch (err: any) {
      enginesError = err.message || "Could not delete parsing engine.";
    } finally {
      enginePendingDelete = null;
    }
  }

  // ── LLM Providers (org-scoped, owner/admin-managed) ──────────────────────
  let llmInstances = $state<LLMProviderInstance[]>([]);
  let llmKinds = $state<LLMProviderKind[]>([]);
  let llmLoading = $state(true);
  let llmError = $state("");
  let showAddLlmForm = $state(false);
  let isSavingLlm = $state(false);
  let isTestingNewLlm = $state(false);
  let newLlmName = $state("");
  let newLlmKind = $state<LLMProviderKindId>("");
  let newLlmBase = $state("");
  let newLlmKey = $state("");
  let newLlmNotes = $state("");
  let testedLlmKind = $state<LLMProviderKindId>("");
  let testedLlmBase = $state("");
  let testedLlmKey = $state("");
  let candidateLlmTestResult = $state<LLMProviderInstanceTestResult | null>(null);

  // If the user modifies kind, api_base, or api_key after testing, invalidate the test result
  let newLlmTestResult = $derived.by(() => {
    if (!candidateLlmTestResult) return null;
    if (
      newLlmKind !== testedLlmKind ||
      newLlmBase !== testedLlmBase ||
      newLlmKey !== testedLlmKey
    ) {
      return null;
    }
    return candidateLlmTestResult;
  });

  let llmPendingDelete = $state<LLMProviderInstance | null>(null);
  let testingLlmId = $state<number | null>(null);
  let llmTestResults = $state<Record<number, { ok: boolean; detail: string }>>({});
  let modelsById = $state<Record<number, LLMProviderModel[]>>({});
  let loadingModelsId = $state<number | null>(null);
  let modelsError = $state<Record<number, string>>({});

  function llmKindInfo(kind: LLMProviderKindId): LLMProviderKind | null {
    return llmKinds.find((k) => k.kind === kind) ?? null;
  }

  async function loadLlmKinds(orgId: number) {
    try {
      llmKinds = await llmProvidersApi.kinds(orgId);
      if (!newLlmKind && llmKinds.length > 0) newLlmKind = llmKinds[0].kind;
    } catch (err: any) {
      llmError = err.message || "Failed to load LLM provider kinds.";
    }
  }

  async function loadLlmInstances(orgId: number) {
    llmLoading = true;
    llmError = "";
    try {
      llmInstances = await llmProvidersApi.list(orgId);
    } catch (err: any) {
      llmError = err.message || "Failed to load LLM providers.";
    } finally {
      llmLoading = false;
    }
  }

  function resetLlmForm() {
    newLlmName = "";
    newLlmKind = llmKinds[0]?.kind ?? "";
    newLlmBase = "";
    newLlmKey = "";
    newLlmNotes = "";
    testedLlmKind = "";
    testedLlmBase = "";
    testedLlmKey = "";
    candidateLlmTestResult = null;
    isTestingNewLlm = false;
  }

  async function handleTestNewLlm() {
    if (!activeOrg) return;
    const selectedKindInfo = llmKindInfo(newLlmKind);
    if (!newLlmKind) {
      llmError = "Provider kind is required.";
      return;
    }
    if (selectedKindInfo?.requires_api_key && !newLlmKey.trim()) {
      llmError = `A ${selectedKindInfo.display_name} instance requires an API key.`;
      return;
    }
    isTestingNewLlm = true;
    llmError = "";
    try {
      const res = await llmProvidersApi.testConnection(activeOrg.organization_id, {
        kind: newLlmKind,
        api_key: newLlmKey.trim() || undefined,
        api_base: newLlmBase.trim() || undefined,
      });
      testedLlmKind = newLlmKind;
      testedLlmBase = newLlmBase;
      testedLlmKey = newLlmKey;
      candidateLlmTestResult = res;
    } catch (err: any) {
      testedLlmKind = newLlmKind;
      testedLlmBase = newLlmBase;
      testedLlmKey = newLlmKey;
      candidateLlmTestResult = {
        ok: false,
        detail: err.message || "Connection test failed.",
      };
    } finally {
      isTestingNewLlm = false;
    }
  }

  async function handleAddLlm() {
    if (!activeOrg) return;
    const selectedKindInfo = llmKindInfo(newLlmKind);
    if (!newLlmName.trim() || !newLlmKind) {
      llmError = "Name and kind are required.";
      return;
    }
    if (selectedKindInfo?.requires_api_key && !newLlmKey.trim()) {
      llmError = `A ${selectedKindInfo.display_name} instance requires an API key.`;
      return;
    }
    if (!newLlmTestResult?.ok) {
      llmError = "A successful connection test is required before adding this provider.";
      return;
    }
    isSavingLlm = true;
    llmError = "";
    try {
      await llmProvidersApi.create(activeOrg.organization_id, {
        name: newLlmName.trim(),
        kind: newLlmKind,
        api_key: newLlmKey.trim() || undefined,
        api_base: newLlmBase.trim() || undefined,
        is_default: llmInstances.length === 0,
        notes: newLlmNotes.trim() || undefined,
      });
      resetLlmForm();
      showAddLlmForm = false;
      await loadLlmInstances(activeOrg.organization_id);
    } catch (err: any) {
      llmError = err.message || "Failed to register LLM provider.";
    } finally {
      isSavingLlm = false;
    }
  }

  async function handleSetDefaultLlm(instance: LLMProviderInstance) {
    if (!activeOrg) return;
    try {
      await llmProvidersApi.update(activeOrg.organization_id, instance.id, { is_default: true });
      await loadLlmInstances(activeOrg.organization_id);
    } catch (err: any) {
      llmError = err.message || "Failed to set default LLM provider.";
    }
  }

  async function handleToggleLlmEnabled(instance: LLMProviderInstance) {
    if (!activeOrg) return;
    try {
      await llmProvidersApi.update(activeOrg.organization_id, instance.id, {
        is_enabled: !instance.is_enabled,
      });
      await loadLlmInstances(activeOrg.organization_id);
    } catch (err: any) {
      llmError = err.message || "Failed to update LLM provider.";
    }
  }

  async function handleTestLlm(instance: LLMProviderInstance) {
    if (!activeOrg) return;
    testingLlmId = instance.id;
    try {
      llmTestResults = {
        ...llmTestResults,
        [instance.id]: await llmProvidersApi.test(activeOrg.organization_id, instance.id),
      };
    } catch (err: any) {
      llmTestResults = {
        ...llmTestResults,
        [instance.id]: { ok: false, detail: err.message || "Test failed." },
      };
    } finally {
      testingLlmId = null;
    }
  }

  async function handleLoadModels(instance: LLMProviderInstance) {
    if (!activeOrg) return;
    loadingModelsId = instance.id;
    modelsError = { ...modelsError, [instance.id]: "" };
    try {
      modelsById = {
        ...modelsById,
        [instance.id]: await llmProvidersApi.models(activeOrg.organization_id, instance.id),
      };
    } catch (err: any) {
      modelsError = { ...modelsError, [instance.id]: err.message || "Failed to load models." };
    } finally {
      loadingModelsId = null;
    }
  }

  async function handleDeleteLlm() {
    if (!activeOrg) return;
    const instance = llmPendingDelete;
    if (!instance) return;
    try {
      await llmProvidersApi.delete(activeOrg.organization_id, instance.id);
      llmInstances = llmInstances.filter((i) => i.id !== instance.id);
    } catch (err: any) {
      llmError = err.message || "Could not delete LLM provider.";
    } finally {
      llmPendingDelete = null;
    }
  }

  // ── Task Shortlists (org-scoped) ─────────────────────────────────────────
  let llmTasks = $state<LLMTask[]>([]);
  let taskAssignments = $state<LLMTaskModelAssignment[]>([]);
  let tasksLoading = $state(true);
  let tasksError = $state("");
  let configuringTask = $state<LLMTask | null>(null);

  function assignmentsForTask(taskKey: string): LLMTaskModelAssignment[] {
    return taskAssignments.filter((a) => a.task_key === taskKey);
  }

  async function loadTasksAndAssignments(orgId: number) {
    tasksLoading = true;
    tasksError = "";
    try {
      const [tasks, assignments] = await Promise.all([
        llmProvidersApi.tasks(orgId),
        llmProvidersApi.taskAssignments(orgId),
      ]);
      llmTasks = tasks;
      taskAssignments = assignments;
    } catch (err: any) {
      tasksError = err.message || "Failed to load task shortlists.";
    } finally {
      tasksLoading = false;
    }
  }

  function handleTaskAssignmentsSaved(saved: LLMTaskModelAssignment[]) {
    const task = configuringTask;
    if (!task) return;
    taskAssignments = [...taskAssignments.filter((a) => a.task_key !== task.key), ...saved];
    configuringTask = null;
  }

  $effect(() => {
    loadEngineKinds();
    loadEngines();
  });

  $effect(() => {
    if (activeOrg) {
      loadLlmKinds(activeOrg.organization_id);
      loadLlmInstances(activeOrg.organization_id);
      loadTasksAndAssignments(activeOrg.organization_id);
    }
  });
</script>

<div class="space-y-6">
  <PageHeader
    category="Admin"
    title="External Providers"
    subtitle="Every document-parsing and LLM provider this deployment talks to, in one place."
    icon={Plug}
  />

  {#if !activeOrg}
    <EmptyState
      title="No organization selected"
      description="Choose an organization from the header switcher to manage its LLM providers."
      icon={Building2}
    />
  {:else}
    <TabStrip tabs={TABS} active={activeTab} onSelect={(id) => (activeTab = id as "parsing" | "llm")} />

    {#if activeTab === "parsing"}
      <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-base font-bold tracking-tight text-slate-50">Document Parsing Engines</h2>
            <p class="text-xs text-slate-400">
              Platform-wide — shared by every organization, managed by a superadmin. Local self-hosted
              containers, hosted accounts, or a mix. The default instance is used when an upload doesn't
              name one explicitly.
            </p>
          </div>
          {#if authState.isSuperadmin}
            <button
              type="button"
              onclick={() => (showAddEngineForm = !showAddEngineForm)}
              class="flex items-center gap-1.5 rounded-xl bg-accent px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-all hover:bg-accent-hover"
            >
              <Plus class="h-4 w-4" />
              <span>Add Instance</span>
            </button>
          {/if}
        </div>

        {#if !authState.isSuperadmin}
          <div
            class="flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-xs text-slate-400"
          >
            <ShieldAlert class="h-4 w-4 shrink-0 text-slate-500" />
            <span>Read-only — only a platform superadmin can add, edit, or remove parsing engines.</span>
          </div>
        {/if}

        {#if enginesError}
          <div
            class="flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-3.5 text-xs text-rose-300"
          >
            {enginesError}
          </div>
        {/if}

        {#if showAddEngineForm}
          <ProviderInstanceForm
            kinds={engineKinds}
            bind:name={newEngineName}
            bind:kind={newEngineKind}
            bind:url={newEngineUrl}
            bind:apiKey={newEngineKey}
            bind:notes={newEngineNotes}
            urlLabel="API URL"
            submitting={isSavingEngine}
            onSubmit={handleAddEngine}
            onCancel={() => (showAddEngineForm = false)}
          >
            {#snippet extraFields(kindInfo)}
              {#if (kindInfo as ParsingEngineKind | null)?.supports_strategy}
                <div>
                  <label for="engine-strategy" class="mb-1 block text-caption font-semibold text-slate-400"
                    >Strategy</label
                  >
                  <select
                    id="engine-strategy"
                    bind:value={newEngineStrategy}
                    class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
                  >
                    <option value="auto">auto</option>
                    <option value="fast">fast</option>
                    <option value="hi_res">hi_res</option>
                    <option value="ocr_only">ocr_only</option>
                  </select>
                </div>
              {/if}
            {/snippet}
          </ProviderInstanceForm>
        {/if}

        {#if enginesLoading}
          <div class="p-8 text-center text-xs text-slate-400">Loading parsing engines...</div>
        {:else if engines.length === 0}
          <div class="rounded-xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500">
            No parsing engines configured — document upload falls back to the local, dependency-light
            extractor.
          </div>
        {:else}
          <div class="space-y-2">
            {#each engines as engine (engine.id)}
              {@const info = engineKindInfo(engine.kind)}
              {@const accent = FAMILY_ACCENT[info?.family ?? ""] ?? FAMILY_ACCENT.default}
              <ProviderInstanceCard
                name={engine.name}
                kindLabel={engine.kind}
                icon={info?.requires_api_key ? Cloud : Server}
                accentClass={accent}
                isDefault={engine.is_default}
                isEnabled={engine.is_enabled}
                endpoint={engine.api_url}
                detail={`strategy: ${engine.strategy} · ${engine.has_api_key ? "API key set" : "no API key"}${engine.notes ? ` · ${engine.notes}` : ""}`}
                testResult={engineTestResults[engine.id]}
                testing={testingEngineId === engine.id}
                canManage={authState.isSuperadmin}
                onTest={() => handleTestEngine(engine)}
                onSetDefault={() => handleSetDefaultEngine(engine)}
                onToggleEnabled={() => handleToggleEngineEnabled(engine)}
                onDelete={() => (enginePendingDelete = engine)}
              />
            {/each}
          </div>
        {/if}
      </div>
    {:else}
      <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-base font-bold tracking-tight text-slate-50">LLM Providers</h2>
            <p class="text-xs text-slate-400">
              Scoped to <span class="font-semibold text-slate-300">{activeOrg.name}</span> — bring your
              own API keys per organization. Curate which models each task may use below, under
              Task Shortlists.
            </p>
          </div>
          <button
            type="button"
            onclick={() => {
              showAddLlmForm = !showAddLlmForm;
              if (showAddLlmForm) resetLlmForm();
            }}
            class="flex items-center gap-1.5 rounded-xl bg-accent px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-all hover:bg-accent-hover"
          >
            <Plus class="h-4 w-4" />
            <span>Add Provider</span>
          </button>
        </div>

        {#if llmError}
          <div
            class="flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-3.5 text-xs text-rose-300"
          >
            {llmError}
          </div>
        {/if}

        {#if showAddLlmForm}
          <ProviderInstanceForm
            kinds={llmKinds}
            bind:name={newLlmName}
            bind:kind={newLlmKind}
            bind:url={newLlmBase}
            bind:apiKey={newLlmKey}
            bind:notes={newLlmNotes}
            urlLabel="API Base URL (optional override)"
            urlRequired={false}
            submitting={isSavingLlm}
            submitLabel="Save Provider"
            onTest={handleTestNewLlm}
            testing={isTestingNewLlm}
            testResult={newLlmTestResult}
            requireSuccessfulTest={true}
            onSubmit={handleAddLlm}
            onCancel={() => {
              showAddLlmForm = false;
              resetLlmForm();
            }}
          />
        {/if}

        {#if llmLoading}
          <div class="p-8 text-center text-xs text-slate-400">Loading LLM providers...</div>
        {:else if llmInstances.length === 0}
          <div class="rounded-xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500">
            No LLM providers configured for this organization yet — add one above (e.g. OpenRouter or
            OpenAI) so features like Rule Extraction can pick a real model.
          </div>
        {:else}
          <div class="space-y-2">
            {#each llmInstances as instance (instance.id)}
              {@const info = llmKindInfo(instance.kind)}
              {@const accent = FAMILY_ACCENT[instance.kind] ?? FAMILY_ACCENT.default}
              <div class="space-y-2">
                <ProviderInstanceCard
                  name={instance.name}
                  kindLabel={info?.display_name ?? instance.kind}
                  icon={Cloud}
                  accentClass={accent}
                  isDefault={instance.is_default}
                  isEnabled={instance.is_enabled}
                  endpoint={instance.api_base || info?.default_api_base || "default endpoint"}
                  detail={`${instance.has_api_key ? "API key set" : "no API key"}${instance.notes ? ` · ${instance.notes}` : ""}`}
                  testResult={llmTestResults[instance.id]}
                  testing={testingLlmId === instance.id}
                  onTest={() => handleTestLlm(instance)}
                  onSetDefault={() => handleSetDefaultLlm(instance)}
                  onToggleEnabled={() => handleToggleLlmEnabled(instance)}
                  onDelete={() => (llmPendingDelete = instance)}
                />
                <div class="pl-3.5">
                  <button
                    type="button"
                    onclick={() => handleLoadModels(instance)}
                    disabled={loadingModelsId === instance.id}
                    class="text-caption font-semibold text-accent hover:underline disabled:opacity-50"
                  >
                    {loadingModelsId === instance.id ? "Loading models…" : "Fetch available models"}
                  </button>
                  {#if modelsError[instance.id]}
                    <p class="mt-1 text-caption text-rose-400">{modelsError[instance.id]}</p>
                  {:else if modelsById[instance.id]}
                    <div class="mt-1.5 space-y-1">
                      <p class="text-caption text-slate-500">
                        {modelsById[instance.id].length} model{modelsById[instance.id].length === 1 ? "" : "s"} available
                        (showing first 8):
                      </p>
                      <ul class="space-y-0.5">
                        {#each modelsById[instance.id].slice(0, 8) as model (model.id)}
                          <li class="flex flex-wrap items-baseline gap-x-2 text-caption">
                            <span class="text-slate-300">{model.name}</span>
                            <span class="text-slate-500">{formatModelMeta(model)}</span>
                          </li>
                        {/each}
                      </ul>
                      {#if modelsById[instance.id].length > 8}
                        <p class="text-caption text-slate-600">…and {modelsById[instance.id].length - 8} more.</p>
                      {/if}
                    </div>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Task Shortlists: which models each task may pick from -->
      <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
        <div>
          <h2 class="text-base font-bold tracking-tight text-slate-50">Task Shortlists</h2>
          <p class="text-xs text-slate-400">
            Curate which models each task may use — capped to a deliberate shortlist chosen for
            capability, price, and context window, instead of a provider's whole catalogue.
          </p>
        </div>

        {#if tasksError}
          <div class="flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-3.5 text-xs text-rose-300">
            {tasksError}
          </div>
        {/if}

        {#if tasksLoading}
          <div class="p-8 text-center text-xs text-slate-400">Loading tasks...</div>
        {:else}
          <div class="space-y-2">
            {#each llmTasks as task (task.key)}
              {@const assigned = assignmentsForTask(task.key)}
              <div class="rounded-xl border border-slate-800/80 bg-slate-950/80 p-3.5">
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div class="space-y-0.5">
                    <div class="text-sm font-semibold text-slate-50">{task.label}</div>
                    <p class="text-caption text-slate-500">{task.description}</p>
                  </div>
                  <button
                    type="button"
                    onclick={() => (configuringTask = task)}
                    class="flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-1.5 text-caption font-semibold text-slate-200 transition-colors hover:bg-slate-700"
                  >
                    <Settings2 class="h-3.5 w-3.5" />
                    Configure
                  </button>
                </div>
                {#if assigned.length === 0}
                  <p class="mt-2 text-caption text-slate-600">
                    No shortlist yet — every enabled provider's full catalogue is offered for this task.
                  </p>
                {:else}
                  <div class="mt-2 flex flex-wrap gap-1.5">
                    {#each assigned as a (a.model_id + a.provider_instance_id)}
                      <span
                        class="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-micro font-medium {a.is_default
                          ? 'border-amber-800/60 bg-amber-950/60 text-amber-300'
                          : 'border-slate-700 bg-slate-900 text-slate-300'}"
                      >
                        {#if a.is_default}<Star class="h-2.5 w-2.5" fill="currentColor" />{/if}
                        {a.model_name}
                        <span class="text-slate-500">· {formatModelMeta(a)}</span>
                      </span>
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  {/if}
</div>

{#if configuringTask && activeOrg}
  <TaskAssignmentModal
    task={configuringTask}
    organizationId={activeOrg.organization_id}
    instances={llmInstances.filter((i) => i.is_enabled)}
    currentAssignments={assignmentsForTask(configuringTask.key)}
    onClose={() => (configuringTask = null)}
    onSaved={handleTaskAssignmentsSaved}
  />
{/if}

<ConfirmModal
  isOpen={enginePendingDelete !== null}
  title="Remove Parsing Engine"
  message={`Remove parsing engine '${enginePendingDelete?.name ?? ""}'? Documents already extracted with it are not affected.`}
  confirmText="Remove Instance"
  danger={true}
  onConfirm={handleDeleteEngine}
  onCancel={() => (enginePendingDelete = null)}
/>

<ConfirmModal
  isOpen={llmPendingDelete !== null}
  title="Remove LLM Provider"
  message={`Remove LLM provider '${llmPendingDelete?.name ?? ""}'? Features that used it (e.g. rule extraction) will fall back to another configured provider, if any.`}
  confirmText="Remove Provider"
  danger={true}
  onConfirm={handleDeleteLlm}
  onCancel={() => (llmPendingDelete = null)}
/>
