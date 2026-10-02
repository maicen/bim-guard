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
    Terminal,
    CheckCircle2,
    XCircle,
  } from "lucide-svelte";
  import { router } from "svelte-spa-router";
  import Select from "../lib/components/ui/Select.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import TabStrip from "../lib/components/TabStrip.svelte";
  import ProviderInstanceCard from "../lib/components/ProviderInstanceCard.svelte";
  import ProviderInstanceForm from "../lib/components/ProviderInstanceForm.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import TaskAssignmentModal from "../lib/components/TaskAssignmentModal.svelte";
  import Alert from "../lib/components/Alert.svelte";
  import {
    parsingEnginesApi,
    orgParsingEnginesApi,
    llmProvidersApi,
    settingsApi,
  } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import { formatModelMeta } from "../lib/utils/formatModelMeta";
  import { toErrorLogEntry, type ErrorLogEntry } from "../lib/utils/errorLog";
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
    EnvVarStatusItem,
  } from "../lib/types";

  let activeOrg = $derived(authState.activeOrganization);
  let activeTab = $state<"parsing" | "llm" | "env">("parsing");

  // Deep-link support: #/external-providers?tab=parsing lands on a specific
  // tab (used by the "no parsing engine configured" upload guidance).
  let queryParams = $derived(new URLSearchParams(router.querystring || ""));
  $effect(() => {
    const tabParam = queryParams.get("tab");
    if (tabParam === "parsing" || tabParam === "llm" || tabParam === "env") {
      activeTab = tabParam;
    }
  });

  // Inline role check for now (matches DocumentUploadModal.svelte /
  // TopHeader.svelte / UserMenu.svelte) -- swap for a proper
  // Action.MANAGE_PARSING_ENGINES permission lookup once a frontend helper
  // for the permission matrix exists.
  let canManageOrgParsing = $derived(
    authState.isSuperadmin || activeOrg?.role === "owner" || activeOrg?.role === "admin",
  );

  const TABS = [
    { id: "parsing", label: "Document Parsing", icon: FileText },
    { id: "llm", label: "LLM Providers", icon: BrainCircuit },
    { id: "env", label: "Environment", icon: Terminal },
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
  let enginesErrorLog: ErrorLogEntry[] = $state([]);
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
      enginesErrorLog = [toErrorLogEntry(err, "load parsing engine kinds")];
    }
  }

  async function loadEngines() {
    enginesLoading = true;
    enginesError = "";
    enginesErrorLog = [];
    try {
      engines = await parsingEnginesApi.list();
    } catch (err: any) {
      enginesError = err.message || "Failed to load parsing engines.";
      enginesErrorLog = [toErrorLogEntry(err, "load parsing engines")];
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
    enginesErrorLog = [];
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
      enginesErrorLog = [toErrorLogEntry(err, newEngineName.trim())];
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
      enginesErrorLog = [toErrorLogEntry(err, engine.name)];
    }
  }

  async function handleToggleEngineEnabled(engine: ParsingEngineInstance) {
    try {
      await parsingEnginesApi.update(engine.id, { is_enabled: !engine.is_enabled });
      await loadEngines();
    } catch (err: any) {
      enginesError = err.message || "Failed to update parsing engine.";
      enginesErrorLog = [toErrorLogEntry(err, engine.name)];
    }
  }

  async function handleTestEngine(engine: ParsingEngineInstance) {
    testingEngineId = engine.id;
    try {
      engineTestResults = {
        ...engineTestResults,
        [engine.id]: await parsingEnginesApi.test(engine.id),
      };
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
      enginesErrorLog = [toErrorLogEntry(err, engine.name)];
    } finally {
      enginePendingDelete = null;
    }
  }

  // ── Document Parsing (org-scoped, owner/admin-managed) ───────────────────
  // Preferred over the platform-wide tier below when configured (see
  // ParsingEngineInstancesService.get_effective_default on the backend).
  let orgEngines = $state<ParsingEngineInstance[]>([]);
  let orgEnginesLoading = $state(true);
  let orgEnginesError = $state("");
  let orgEnginesErrorLog: ErrorLogEntry[] = $state([]);
  let showAddOrgEngineForm = $state(false);
  let isSavingOrgEngine = $state(false);
  let newOrgEngineName = $state("");
  let newOrgEngineKind = $state<ParsingEngineKindId>("");
  let newOrgEngineUrl = $state("");
  let newOrgEngineKey = $state("");
  let newOrgEngineStrategy = $state("auto");
  let newOrgEngineNotes = $state("");
  let orgEnginePendingDelete = $state<ParsingEngineInstance | null>(null);
  let testingOrgEngineId = $state<number | null>(null);
  let orgEngineTestResults = $state<Record<number, { ok: boolean; detail: string }>>({});

  async function loadOrgEngines(orgId: number) {
    orgEnginesLoading = true;
    orgEnginesError = "";
    orgEnginesErrorLog = [];
    try {
      orgEngines = await orgParsingEnginesApi.list(orgId);
    } catch (err: any) {
      orgEnginesError = err.message || "Failed to load parsing engines.";
      orgEnginesErrorLog = [toErrorLogEntry(err, "load parsing engines")];
    } finally {
      orgEnginesLoading = false;
    }
  }

  function resetOrgEngineForm() {
    newOrgEngineName = "";
    newOrgEngineKind = engineKinds[0]?.kind ?? "";
    newOrgEngineUrl = "";
    newOrgEngineKey = "";
    newOrgEngineStrategy = "auto";
    newOrgEngineNotes = "";
  }

  async function handleAddOrgEngine() {
    if (!activeOrg) return;
    const selectedKindInfo = engineKindInfo(newOrgEngineKind);
    if (!newOrgEngineName.trim() || !newOrgEngineUrl.trim() || !newOrgEngineKind) {
      orgEnginesError = "Name, kind, and API URL are required.";
      return;
    }
    if (selectedKindInfo?.requires_api_key && !newOrgEngineKey.trim()) {
      orgEnginesError = `A ${selectedKindInfo.display_name} instance requires an API key.`;
      return;
    }
    isSavingOrgEngine = true;
    orgEnginesError = "";
    orgEnginesErrorLog = [];
    try {
      await orgParsingEnginesApi.create(activeOrg.organization_id, {
        name: newOrgEngineName.trim(),
        kind: newOrgEngineKind,
        api_url: newOrgEngineUrl.trim(),
        api_key: newOrgEngineKey.trim() || undefined,
        strategy: newOrgEngineStrategy.trim() || "auto",
        is_default: orgEngines.length === 0,
        notes: newOrgEngineNotes.trim() || undefined,
      });
      resetOrgEngineForm();
      showAddOrgEngineForm = false;
      await loadOrgEngines(activeOrg.organization_id);
    } catch (err: any) {
      orgEnginesError = err.message || "Failed to register parsing engine.";
      orgEnginesErrorLog = [toErrorLogEntry(err, newOrgEngineName.trim())];
    } finally {
      isSavingOrgEngine = false;
    }
  }

  async function handleSetDefaultOrgEngine(engine: ParsingEngineInstance) {
    if (!activeOrg) return;
    try {
      await orgParsingEnginesApi.update(activeOrg.organization_id, engine.id, { is_default: true });
      await loadOrgEngines(activeOrg.organization_id);
    } catch (err: any) {
      orgEnginesError = err.message || "Failed to set default parsing engine.";
      orgEnginesErrorLog = [toErrorLogEntry(err, engine.name)];
    }
  }

  async function handleToggleOrgEngineEnabled(engine: ParsingEngineInstance) {
    if (!activeOrg) return;
    try {
      await orgParsingEnginesApi.update(activeOrg.organization_id, engine.id, {
        is_enabled: !engine.is_enabled,
      });
      await loadOrgEngines(activeOrg.organization_id);
    } catch (err: any) {
      orgEnginesError = err.message || "Failed to update parsing engine.";
      orgEnginesErrorLog = [toErrorLogEntry(err, engine.name)];
    }
  }

  async function handleTestOrgEngine(engine: ParsingEngineInstance) {
    if (!activeOrg) return;
    testingOrgEngineId = engine.id;
    try {
      orgEngineTestResults = {
        ...orgEngineTestResults,
        [engine.id]: await orgParsingEnginesApi.test(activeOrg.organization_id, engine.id),
      };
    } catch (err: any) {
      orgEngineTestResults = {
        ...orgEngineTestResults,
        [engine.id]: { ok: false, detail: err.message || "Test failed." },
      };
    } finally {
      testingOrgEngineId = null;
    }
  }

  async function handleDeleteOrgEngine() {
    if (!activeOrg) return;
    const engine = orgEnginePendingDelete;
    if (!engine) return;
    try {
      await orgParsingEnginesApi.delete(activeOrg.organization_id, engine.id);
      orgEngines = orgEngines.filter((e) => e.id !== engine.id);
    } catch (err: any) {
      orgEnginesError = err.message || "Could not delete parsing engine.";
      orgEnginesErrorLog = [toErrorLogEntry(err, engine.name)];
    } finally {
      orgEnginePendingDelete = null;
    }
  }

  // ── LLM Providers (org-scoped, owner/admin-managed) ──────────────────────
  let llmInstances = $state<LLMProviderInstance[]>([]);
  let llmKinds = $state<LLMProviderKind[]>([]);
  let llmLoading = $state(true);
  let llmError = $state("");
  let llmErrorLog: ErrorLogEntry[] = $state([]);
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
      llmErrorLog = [toErrorLogEntry(err, "load LLM provider kinds")];
    }
  }

  async function loadLlmInstances(orgId: number) {
    llmLoading = true;
    llmError = "";
    llmErrorLog = [];
    try {
      llmInstances = await llmProvidersApi.list(orgId);
    } catch (err: any) {
      llmError = err.message || "Failed to load LLM providers.";
      llmErrorLog = [toErrorLogEntry(err, "load LLM providers")];
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
    llmErrorLog = [];
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
      llmErrorLog = [toErrorLogEntry(err, newLlmName.trim())];
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
  let tasksErrorLog: ErrorLogEntry[] = $state([]);
  let configuringTask = $state<LLMTask | null>(null);

  function assignmentsForTask(taskKey: string): LLMTaskModelAssignment[] {
    return taskAssignments.filter((a) => a.task_key === taskKey);
  }

  async function loadTasksAndAssignments(orgId: number) {
    tasksLoading = true;
    tasksError = "";
    tasksErrorLog = [];
    try {
      const [tasks, assignments] = await Promise.all([
        llmProvidersApi.tasks(orgId),
        llmProvidersApi.taskAssignments(orgId),
      ]);
      llmTasks = tasks;
      taskAssignments = assignments;
    } catch (err: any) {
      tasksError = err.message || "Failed to load task shortlists.";
      tasksErrorLog = [toErrorLogEntry(err, `org #${orgId}`)];
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

  // ── Environment (platform-wide, superadmin-only) ─────────────────────────
  let envVars = $state<EnvVarStatusItem[]>([]);
  let envLoading = $state(false);
  let envError = $state("");
  let envErrorLog: ErrorLogEntry[] = $state([]);
  let envLoaded = $state(false);

  let envCategories = $derived.by(() => {
    const byCategory = new Map<string, EnvVarStatusItem[]>();
    for (const item of envVars) {
      const list = byCategory.get(item.category) ?? [];
      list.push(item);
      byCategory.set(item.category, list);
    }
    return [...byCategory.entries()];
  });
  let envMissingRequired = $derived(envVars.filter((v) => v.required && !v.is_set));

  async function loadEnvStatus() {
    envLoading = true;
    envError = "";
    envErrorLog = [];
    try {
      const res = await settingsApi.getEnvStatus();
      envVars = res.variables || [];
      envLoaded = true;
    } catch (err: any) {
      envError = err.message || "Failed to load environment variable status.";
      envErrorLog = [toErrorLogEntry(err, "load environment status")];
    } finally {
      envLoading = false;
    }
  }

  $effect(() => {
    loadEngineKinds();
    loadEngines();
  });

  $effect(() => {
    if (activeOrg) {
      loadOrgEngines(activeOrg.organization_id);
      loadLlmKinds(activeOrg.organization_id);
      loadLlmInstances(activeOrg.organization_id);
      loadTasksAndAssignments(activeOrg.organization_id);
    }
  });

  $effect(() => {
    if (activeTab === "env" && authState.isSuperadmin && !envLoaded && !envLoading) {
      loadEnvStatus();
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
    <TabStrip
      tabs={TABS}
      active={activeTab}
      onSelect={(id) => (activeTab = id as "parsing" | "llm")}
    />

    {#if activeTab === "env"}
      <div class="border-border-default bg-surface-card/60 space-y-4 rounded-2xl border p-6">
        <div>
          <h2 class="text-fg-primary text-base font-bold tracking-tight">Environment Variables</h2>
          <p class="text-fg-muted text-xs">
            Every environment variable this deployment reads, and whether it's currently set in this
            process — names and presence only, values are never sent to the browser. Most are
            fallbacks used only when no matching DB-configured provider instance exists (see the
            tabs above).
          </p>
        </div>

        {#if !authState.isSuperadmin}
          <div
            class="border-border-default bg-surface-canvas/60 text-fg-muted flex items-center gap-2 rounded-xl border p-3 text-xs"
          >
            <ShieldAlert class="text-fg-muted h-4 w-4 shrink-0" />
            <span>Only a platform superadmin can view environment variable status.</span>
          </div>
        {:else}
          {#if envError}
            <Alert
              type="error"
              message={envError}
              errors={envErrorLog}
              logTitle="Environment Status Error Log"
            />
          {/if}

          {#if envLoading}
            <div class="text-fg-muted p-8 text-center text-xs">Loading environment status...</div>
          {:else if envVars.length > 0}
            {#if envMissingRequired.length > 0}
              <div
                class="flex items-center gap-2 rounded-xl border border-amber-800 bg-amber-950/50 p-3.5 text-xs text-amber-300"
              >
                <ShieldAlert class="h-4 w-4 shrink-0 text-amber-400" />
                <span
                  >{envMissingRequired.length} required variable{envMissingRequired.length === 1
                    ? ""
                    : "s"}
                  missing: {envMissingRequired.map((v) => v.name).join(", ")}</span
                >
              </div>
            {/if}

            <div class="space-y-5">
              {#each envCategories as [category, items] (category)}
                <div>
                  <h3 class="text-caption text-fg-muted mb-2 font-semibold tracking-wide uppercase">
                    {category}
                  </h3>
                  <div
                    class="divide-border-subtle border-border-default bg-surface-canvas/60 divide-y rounded-xl border"
                  >
                    {#each items as item (item.name)}
                      <div class="flex items-center justify-between gap-3 px-3.5 py-2.5">
                        <div class="min-w-0">
                          <div class="flex items-center gap-1.5">
                            <span class="text-fg-secondary font-mono text-xs font-semibold"
                              >{item.name}</span
                            >
                            {#if item.required}
                              <span
                                class="border-border-interactive text-micro text-fg-muted rounded-full border px-1.5 py-0.5 font-semibold tracking-wide uppercase"
                                >Required</span
                              >
                            {/if}
                          </div>
                          {#if item.description}
                            <p class="text-caption text-fg-muted mt-0.5">{item.description}</p>
                          {/if}
                        </div>
                        {#if item.is_set}
                          <span
                            class="text-micro flex shrink-0 items-center gap-1 rounded-full border border-emerald-800/60 bg-emerald-950/60 px-2 py-0.5 font-semibold text-emerald-300"
                          >
                            <CheckCircle2 class="h-3 w-3" />
                            Set
                          </span>
                        {:else}
                          <span
                            class="text-micro flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 font-semibold {item.required
                              ? 'border-rose-800/60 bg-rose-950/60 text-rose-300'
                              : 'border-border-interactive bg-surface-card text-fg-muted'}"
                          >
                            <XCircle class="h-3 w-3" />
                            Missing
                          </span>
                        {/if}
                      </div>
                    {/each}
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        {/if}
      </div>
    {:else if activeTab === "parsing"}
      <div class="border-border-default bg-surface-card/60 space-y-4 rounded-2xl border p-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-fg-primary text-base font-bold tracking-tight">
              Document Parsing Engines
            </h2>
            <p class="text-fg-muted text-xs">
              Scoped to <span class="text-fg-secondary font-semibold">{activeOrg.name}</span> — used in
              preference to the platform default below when configured. Local self-hosted containers,
              hosted accounts, or a mix.
            </p>
          </div>
          {#if canManageOrgParsing}
            <button
              type="button"
              onclick={() => {
                showAddOrgEngineForm = !showAddOrgEngineForm;
                if (showAddOrgEngineForm) resetOrgEngineForm();
              }}
              class="bg-accent hover:bg-accent-hover flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white shadow-xs transition-all"
            >
              <Plus class="h-4 w-4" />
              <span>Add Instance</span>
            </button>
          {/if}
        </div>

        {#if !canManageOrgParsing}
          <div
            class="border-border-default bg-surface-canvas/60 text-fg-muted flex items-center gap-2 rounded-xl border p-3 text-xs"
          >
            <ShieldAlert class="text-fg-muted h-4 w-4 shrink-0" />
            <span
              >Read-only — ask an organization owner or admin to add, edit, or remove parsing
              engines.</span
            >
          </div>
        {/if}

        {#if orgEnginesError}
          <Alert
            type="error"
            message={orgEnginesError}
            errors={orgEnginesErrorLog}
            logTitle="Org Parsing Engines Error Log"
          />
        {/if}

        {#if showAddOrgEngineForm}
          <ProviderInstanceForm
            kinds={engineKinds}
            bind:name={newOrgEngineName}
            bind:kind={newOrgEngineKind}
            bind:url={newOrgEngineUrl}
            bind:apiKey={newOrgEngineKey}
            bind:notes={newOrgEngineNotes}
            urlLabel="API URL"
            submitting={isSavingOrgEngine}
            onSubmit={handleAddOrgEngine}
            onCancel={() => (showAddOrgEngineForm = false)}
          >
            {#snippet extraFields(kindInfo)}
              {#if (kindInfo as ParsingEngineKind | null)?.supports_strategy}
                <div>
                  <label
                    for="org-engine-strategy"
                    class="text-caption text-fg-muted mb-1 block font-semibold">Strategy</label
                  >
                  <Select
                    bind:value={newOrgEngineStrategy}
                    ariaLabel="Parsing strategy"
                    options={[
                      { value: "auto", label: "auto" },
                      { value: "fast", label: "fast" },
                      { value: "hi_res", label: "hi_res" },
                      { value: "ocr_only", label: "ocr_only" },
                    ]}
                  />
                </div>
              {/if}
            {/snippet}
          </ProviderInstanceForm>
        {/if}

        {#if orgEnginesLoading}
          <div class="text-fg-muted p-8 text-center text-xs">Loading parsing engines...</div>
        {:else if orgEngines.length === 0}
          <div
            class="border-border-default text-fg-muted rounded-xl border border-dashed p-8 text-center text-xs"
          >
            No parsing engines configured for this organization — uploads use the platform default
            below, if one is set, or fail with a clear error otherwise.
          </div>
        {:else}
          <div class="space-y-2">
            {#each orgEngines as engine (engine.id)}
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
                testResult={orgEngineTestResults[engine.id]}
                testing={testingOrgEngineId === engine.id}
                canManage={canManageOrgParsing}
                onTest={() => handleTestOrgEngine(engine)}
                onSetDefault={() => handleSetDefaultOrgEngine(engine)}
                onToggleEnabled={() => handleToggleOrgEngineEnabled(engine)}
                onDelete={() => (orgEnginePendingDelete = engine)}
              />
            {/each}
          </div>
        {/if}
      </div>

      <div class="border-border-default bg-surface-card/60 space-y-4 rounded-2xl border p-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-fg-primary text-base font-bold tracking-tight">Platform Default</h2>
            <p class="text-fg-muted text-xs">
              Shared by every organization that hasn't configured its own instance above, managed by
              a superadmin.
            </p>
          </div>
          {#if authState.isSuperadmin}
            <button
              type="button"
              onclick={() => (showAddEngineForm = !showAddEngineForm)}
              class="bg-accent hover:bg-accent-hover flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white shadow-xs transition-all"
            >
              <Plus class="h-4 w-4" />
              <span>Add Instance</span>
            </button>
          {/if}
        </div>

        {#if !authState.isSuperadmin}
          <div
            class="border-border-default bg-surface-canvas/60 text-fg-muted flex items-center gap-2 rounded-xl border p-3 text-xs"
          >
            <ShieldAlert class="text-fg-muted h-4 w-4 shrink-0" />
            <span
              >Read-only — only a platform superadmin can add, edit, or remove the platform default.</span
            >
          </div>
        {/if}

        {#if enginesError}
          <Alert
            type="error"
            message={enginesError}
            errors={enginesErrorLog}
            logTitle="Platform Parsing Engines Error Log"
          />
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
                  <label
                    for="engine-strategy"
                    class="text-caption text-fg-muted mb-1 block font-semibold">Strategy</label
                  >
                  <Select
                    bind:value={newEngineStrategy}
                    ariaLabel="Parsing strategy"
                    options={[
                      { value: "auto", label: "auto" },
                      { value: "fast", label: "fast" },
                      { value: "hi_res", label: "hi_res" },
                      { value: "ocr_only", label: "ocr_only" },
                    ]}
                  />
                </div>
              {/if}
            {/snippet}
          </ProviderInstanceForm>
        {/if}

        {#if enginesLoading}
          <div class="text-fg-muted p-8 text-center text-xs">Loading parsing engines...</div>
        {:else if engines.length === 0}
          <div
            class="border-border-default text-fg-muted rounded-xl border border-dashed p-8 text-center text-xs"
          >
            No platform default configured — organizations with no org-scoped instance of their own
            will fail to upload documents until one is added here, or they configure their own
            above.
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
    {:else if activeTab === "llm"}
      <div class="border-border-default bg-surface-card/60 space-y-4 rounded-2xl border p-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-fg-primary text-base font-bold tracking-tight">LLM Providers</h2>
            <p class="text-fg-muted text-xs">
              Scoped to <span class="text-fg-secondary font-semibold">{activeOrg.name}</span> — bring
              your own API keys per organization. Curate which models each task may use below, under Task
              Shortlists.
            </p>
          </div>
          <button
            type="button"
            onclick={() => {
              showAddLlmForm = !showAddLlmForm;
              if (showAddLlmForm) resetLlmForm();
            }}
            class="bg-accent hover:bg-accent-hover flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white shadow-xs transition-all"
          >
            <Plus class="h-4 w-4" />
            <span>Add Provider</span>
          </button>
        </div>

        {#if llmError}
          <Alert
            type="error"
            message={llmError}
            errors={llmErrorLog}
            logTitle="LLM Provider Error Log"
          />
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
          <div class="text-fg-muted p-8 text-center text-xs">Loading LLM providers...</div>
        {:else if llmInstances.length === 0}
          <div
            class="border-border-default text-fg-muted rounded-xl border border-dashed p-8 text-center text-xs"
          >
            No LLM providers configured for this organization yet — add one above (e.g. OpenRouter
            or OpenAI) so features like Rule Extraction can pick a real model.
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
                    class="text-caption text-accent font-semibold hover:underline disabled:opacity-50"
                  >
                    {loadingModelsId === instance.id ? "Loading models…" : "Fetch available models"}
                  </button>
                  {#if modelsError[instance.id]}
                    <p class="text-caption mt-1 text-rose-400">{modelsError[instance.id]}</p>
                  {:else if modelsById[instance.id]}
                    <div class="mt-1.5 space-y-1">
                      <p class="text-caption text-fg-muted">
                        {modelsById[instance.id].length} model{modelsById[instance.id].length === 1
                          ? ""
                          : "s"} available (showing first 8):
                      </p>
                      <ul class="space-y-0.5">
                        {#each modelsById[instance.id].slice(0, 8) as model (model.id)}
                          <li class="text-caption flex flex-wrap items-baseline gap-x-2">
                            <span class="text-fg-secondary">{model.name}</span>
                            <span class="text-fg-muted">{formatModelMeta(model)}</span>
                          </li>
                        {/each}
                      </ul>
                      {#if modelsById[instance.id].length > 8}
                        <p class="text-caption text-fg-muted">
                          …and {modelsById[instance.id].length - 8} more.
                        </p>
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
      <div class="border-border-default bg-surface-card/60 space-y-4 rounded-2xl border p-6">
        <div>
          <h2 class="text-fg-primary text-base font-bold tracking-tight">Task Shortlists</h2>
          <p class="text-fg-muted text-xs">
            Curate which models each task may use — capped to a deliberate shortlist chosen for
            capability, price, and context window, instead of a provider's whole catalogue.
          </p>
        </div>

        {#if tasksError}
          <Alert
            type="error"
            message={tasksError}
            errors={tasksErrorLog}
            logTitle="Task Shortlists Error Log"
          />
        {/if}

        {#if tasksLoading}
          <div class="text-fg-muted p-8 text-center text-xs">Loading tasks...</div>
        {:else}
          <div class="space-y-2">
            {#each llmTasks as task (task.key)}
              {@const assigned = assignmentsForTask(task.key)}
              <div class="border-border-default bg-surface-canvas/80 rounded-xl border p-3.5">
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div class="space-y-0.5">
                    <div class="text-fg-primary text-sm font-semibold">{task.label}</div>
                    <p class="text-caption text-fg-muted">{task.description}</p>
                  </div>
                  <button
                    type="button"
                    onclick={() => (configuringTask = task)}
                    class="border-border-interactive bg-surface-overlay text-caption text-fg-secondary hover:bg-surface-hover flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 font-semibold transition-colors"
                  >
                    <Settings2 class="h-3.5 w-3.5" />
                    Configure
                  </button>
                </div>
                {#if assigned.length === 0}
                  <p class="text-caption text-fg-muted mt-2">
                    No shortlist yet — every enabled provider's full catalogue is offered for this
                    task.
                  </p>
                {:else}
                  <div class="mt-2 flex flex-wrap gap-1.5">
                    {#each assigned as a (a.model_id + a.provider_instance_id)}
                      <span
                        class="text-micro inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-medium {a.is_default
                          ? 'border-amber-800/60 bg-amber-950/60 text-amber-300'
                          : 'border-border-interactive bg-surface-card text-fg-secondary'}"
                      >
                        {#if a.is_default}<Star class="h-2.5 w-2.5" fill="currentColor" />{/if}
                        {a.model_name}
                        <span class="text-fg-muted">· {formatModelMeta(a)}</span>
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
  isOpen={orgEnginePendingDelete !== null}
  title="Remove Parsing Engine"
  message={`Remove parsing engine '${orgEnginePendingDelete?.name ?? ""}'? Documents already extracted with it are not affected.`}
  confirmText="Remove Instance"
  danger={true}
  onConfirm={handleDeleteOrgEngine}
  onCancel={() => (orgEnginePendingDelete = null)}
/>

<ConfirmModal
  isOpen={enginePendingDelete !== null}
  title="Remove Platform Default Parsing Engine"
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
