<script lang="ts">
  import { onMount } from "svelte";
  import {
    Settings,
    Save,
    CheckCircle2,
    AlertCircle,
    Database,
    Sun,
    Moon,
    Laptop,
    Server,
    Cloud,
    Plus,
    Trash2,
    Loader2,
    Star,
    PlugZap,
  } from "lucide-svelte";
  import { settingsApi, parsingEnginesApi } from "../lib/api";
  import { themeMode, setTheme, type ThemeMode } from "../lib/theme";
  import { authState } from "../lib/auth.svelte";
  import { isAuthConfigured } from "../lib/supabaseClient";
  import type {
    SettingItem,
    ParsingEngineInstance,
    ParsingEngineKind,
    ParsingEngineKindId,
  } from "../lib/types";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";

  let settings: SettingItem[] = $state([]);
  let activeLogLevel = $state("INFO");
  let dbBackend = $state("SUPABASE");
  let isLoading = $state(true);
  let isSaving = $state(false);
  let error = $state("");
  let successMessage = $state("");

  // ── Your Profile ──────────────────────────────────────────────────────────
  let profileFullName = $state("");
  let profileTitle = $state("");
  let profileSaving = $state(false);
  let profileError = $state("");
  let profileSuccess = $state("");

  // authState.profile loads asynchronously after sign-in, independent of this
  // view's own onMount, so the form fields track it reactively rather than
  // being read once.
  $effect(() => {
    profileFullName = authState.profile?.profile.full_name || "";
    profileTitle = authState.profile?.profile.title || "";
  });

  async function handleSaveProfile() {
    profileSaving = true;
    profileError = "";
    profileSuccess = "";
    try {
      await authState.updateProfile({ full_name: profileFullName.trim(), title: profileTitle.trim() });
      profileSuccess = "Profile saved.";
    } catch (err: any) {
      profileError = err.message || "Failed to save profile.";
    } finally {
      profileSaving = false;
    }
  }

  // ── Parsing Engines ──────────────────────────────────────────────────────
  // `kinds` is fetched from the backend's ParsingEngineRegistry — the "Kind"
  // selector and its per-kind field behavior (needs an API key? does
  // "strategy" apply?) are driven entirely by that data, so a new backend
  // driver shows up here automatically with no frontend change.
  let engines: ParsingEngineInstance[] = $state([]);
  let engineKinds: ParsingEngineKind[] = $state([]);
  let enginesLoading = $state(true);
  let enginesError = $state("");
  let showAddEngineForm = $state(false);
  let isSavingEngine = $state(false);
  let newEngineName = $state("");
  let newEngineKind: ParsingEngineKindId = $state("");
  let newEngineUrl = $state("");
  let newEngineKey = $state("");
  let newEngineStrategy = $state("auto");
  let newEngineNotes = $state("");
  let enginePendingDelete: ParsingEngineInstance | null = $state(null);
  let testingEngineId: number | null = $state(null);
  let testResults: Record<number, { ok: boolean; detail: string }> = $state({});

  let selectedKindInfo = $derived(engineKinds.find((k) => k.kind === newEngineKind) ?? null);

  // Accent color by engine family — purely cosmetic grouping in the list
  // view. A family not in this map (a future backend outside Unstructured
  // and Docling) still renders correctly via `default`, just without a
  // distinct color.
  const FAMILY_ACCENT: Record<string, string> = {
    unstructured: "text-cyan-400",
    docling: "text-violet-400",
    default: "text-blue-400",
  };

  function kindInfo(kind: ParsingEngineKindId): ParsingEngineKind | null {
    return engineKinds.find((k) => k.kind === kind) ?? null;
  }

  async function loadEngineKinds() {
    try {
      engineKinds = await parsingEnginesApi.kinds();
      if (!newEngineKind && engineKinds.length > 0) {
        newEngineKind = engineKinds[0].kind;
      }
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

  async function handleSetDefault(engine: ParsingEngineInstance) {
    try {
      await parsingEnginesApi.update(engine.id, { is_default: true });
      await loadEngines();
    } catch (err: any) {
      enginesError = err.message || "Failed to set default parsing engine.";
    }
  }

  async function handleToggleEnabled(engine: ParsingEngineInstance) {
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
      testResults = { ...testResults, [engine.id]: await parsingEnginesApi.test(engine.id) };
    } catch (err: any) {
      testResults = {
        ...testResults,
        [engine.id]: { ok: false, detail: err.message || "Test failed." },
      };
    } finally {
      testingEngineId = null;
    }
  }

  function promptDeleteEngine(engine: ParsingEngineInstance) {
    enginePendingDelete = engine;
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

  onMount(async () => {
    try {
      const data = await settingsApi.get();
      settings = data.settings || [];
      activeLogLevel = data.active_log_level || "INFO";
      dbBackend = data.db_backend || "SUPABASE";
    } catch (err: any) {
      error = err.message || "Failed to load application settings.";
    } finally {
      isLoading = false;
    }
    loadEngineKinds();
    loadEngines();
  });

  async function handleSave() {
    isSaving = true;
    error = "";
    successMessage = "";

    const payload: Record<string, string> = {};
    settings.forEach((s) => {
      payload[s.key] = s.value;
    });

    try {
      const updated = await settingsApi.update(payload);
      settings = updated.settings || [];
      activeLogLevel = updated.active_log_level || activeLogLevel;
      successMessage = "Runtime settings saved and persisted to database.";
    } catch (err: any) {
      error = err.message || "Failed to save settings.";
    } finally {
      isSaving = false;
    }
  }
</script>

<div class="mx-auto space-y-6">
  <!-- Header -->
  <PageHeader
    category="Configuration"
    title="Runtime Settings"
    subtitle="Manage application runtime parameters and logging levels persisted in database."
    icon={Settings}
  >
    {#snippet actions()}
      <div>
        <button
          type="button"
          disabled={isSaving}
          onclick={handleSave}
          class="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover disabled:opacity-50"
        >
          <Save class="h-3.5 w-3.5" />
          <span>{isSaving ? "Saving..." : "Save Settings"}</span>
        </button>
      </div>
    {/snippet}
  </PageHeader>

  {#if error}
    <div
      class="flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300"
    >
      <AlertCircle class="h-4 w-4 shrink-0 text-rose-400" />
      <span>{error}</span>
    </div>
  {/if}

  {#if successMessage}
    <div
      class="flex items-center gap-2 rounded-xl border border-emerald-800 bg-emerald-950/50 p-4 text-xs text-emerald-300"
    >
      <CheckCircle2 class="h-4 w-4 shrink-0 text-emerald-400" />
      <span>{successMessage}</span>
    </div>
  {/if}

  {#if isAuthConfigured && authState.user}
    <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
      <div>
        <h2 class="text-base font-bold tracking-tight text-slate-50">Your Profile</h2>
        <p class="text-xs text-slate-400">
          Display name and title shown alongside your account. Your avatar and email come from
          Google and aren't editable here.
        </p>
      </div>

      {#if profileError}
        <div
          class="flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-3.5 text-xs text-rose-300"
        >
          <AlertCircle class="h-4 w-4 shrink-0 text-rose-400" />
          <span>{profileError}</span>
        </div>
      {/if}
      {#if profileSuccess}
        <div
          class="flex items-center gap-2 rounded-xl border border-emerald-800 bg-emerald-950/50 p-3.5 text-xs text-emerald-300"
        >
          <CheckCircle2 class="h-4 w-4 shrink-0 text-emerald-400" />
          <span>{profileSuccess}</span>
        </div>
      {/if}

      <div class="flex items-center gap-4">
        {#if authState.profile?.profile.avatar_url}
          <img
            src={authState.profile.profile.avatar_url}
            alt=""
            referrerpolicy="no-referrer"
            class="h-14 w-14 shrink-0 rounded-full object-cover"
          />
        {:else}
          <div
            class="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-slate-800 text-lg font-semibold text-slate-300"
          >
            {(profileFullName || authState.user.email || "?")[0]?.toUpperCase()}
          </div>
        {/if}
        <div class="grid flex-1 grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label for="profile-full-name" class="mb-1 block text-caption font-semibold text-slate-400"
              >Display name</label
            >
            <input
              id="profile-full-name"
              type="text"
              bind:value={profileFullName}
              placeholder={authState.user.email}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 placeholder-slate-600 focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label for="profile-title" class="mb-1 block text-caption font-semibold text-slate-400"
              >Title / discipline</label
            >
            <input
              id="profile-title"
              type="text"
              bind:value={profileTitle}
              placeholder="e.g. BIM Coordinator"
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 placeholder-slate-600 focus:border-accent focus:outline-none"
            />
          </div>
        </div>
      </div>

      <div class="flex justify-end">
        <button
          type="button"
          disabled={profileSaving}
          onclick={handleSaveProfile}
          class="flex items-center gap-1.5 rounded-xl bg-accent px-4 py-1.5 text-xs font-semibold text-white transition-all hover:bg-accent-hover disabled:opacity-50"
        >
          {#if profileSaving}
            <Loader2 class="h-3.5 w-3.5 animate-spin" />
            <span>Saving...</span>
          {:else}
            <Save class="h-3.5 w-3.5" />
            <span>Save Profile</span>
          {/if}
        </button>
      </div>
    </div>
  {/if}

  <!-- Environment & Persistence Info -->
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
    <div class="space-y-1 rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
      <div class="text-xs font-semibold uppercase text-slate-400">Persistence Backend</div>
      <div class="flex items-center gap-2 text-lg font-bold text-slate-50">
        <Database class="h-4 w-4 text-emerald-400" />
        <span>DB {dbBackend}</span>
      </div>
      <div class="text-caption text-slate-500">Configured via environment variables</div>
    </div>

    <div class="space-y-1 rounded-2xl border border-slate-800 bg-slate-900/40 p-5">
      <div class="text-xs font-semibold uppercase text-slate-400">Active Logging Level</div>
      <div class="font-mono text-lg font-bold text-cyan-400">
        {activeLogLevel}
      </div>
      <div class="text-caption text-slate-500">Dynamic log level filter</div>
    </div>
  </div>

  <!-- Appearance & Theme Selector -->
  <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
    <div>
      <h2 class="text-base font-bold tracking-tight text-slate-50">Interface Appearance</h2>
      <p class="text-xs text-slate-400">
        Select your preferred color theme or synchronize automatically with your operating system.
      </p>
    </div>

    <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <!-- Dark Option -->
      <button
        type="button"
        onclick={() => setTheme("dark")}
        class="flex flex-col items-start rounded-xl border p-4 text-left transition-all {$themeMode ===
        'dark'
          ? 'border-accent bg-accent/10 ring-1 ring-accent'
          : 'border-slate-800 bg-slate-900/50 hover:bg-slate-800/60'}"
      >
        <div class="mb-3 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800">
          <Moon class="h-4 w-4 text-blue-400" />
        </div>
        <span class="text-sm font-semibold text-slate-50">Dark Theme</span>
        <span class="mt-0.5 text-caption text-slate-400"
          >Deep midnight palette for focused low-light environments</span
        >
      </button>

      <!-- Light Option -->
      <button
        type="button"
        onclick={() => setTheme("light")}
        class="flex flex-col items-start rounded-xl border p-4 text-left transition-all {$themeMode ===
        'light'
          ? 'border-accent bg-accent/10 ring-1 ring-accent'
          : 'border-slate-800 bg-slate-900/50 hover:bg-slate-800/60'}"
      >
        <div class="mb-3 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800">
          <Sun class="h-4 w-4 text-amber-400" />
        </div>
        <span class="text-sm font-semibold text-slate-50">Light Theme</span>
        <span class="mt-0.5 text-caption text-slate-400"
          >High-contrast clean palette for bright environments</span
        >
      </button>

      <!-- System Option -->
      <button
        type="button"
        onclick={() => setTheme("system")}
        class="flex flex-col items-start rounded-xl border p-4 text-left transition-all {$themeMode ===
        'system'
          ? 'border-accent bg-accent/10 ring-1 ring-accent'
          : 'border-slate-800 bg-slate-900/50 hover:bg-slate-800/60'}"
      >
        <div class="mb-3 flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800">
          <Laptop class="h-4 w-4 text-slate-300" />
        </div>
        <span class="text-sm font-semibold text-slate-50">System Auto</span>
        <span class="mt-0.5 text-caption text-slate-400"
          >Synchronize appearance with OS color scheme</span
        >
      </button>
    </div>
  </div>

  <!-- Parsing Engines (Unstructured instances) -->
  <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-base font-bold tracking-tight text-slate-50">Parsing Engines</h2>
        <p class="text-xs text-slate-400">
          Configure the document-parsing engines available to document upload — local self-hosted
          containers, hosted accounts, or a mix. The default instance is used when an upload
          doesn't name one explicitly.
        </p>
      </div>
      <button
        type="button"
        onclick={() => (showAddEngineForm = !showAddEngineForm)}
        class="flex items-center gap-1.5 rounded-xl bg-accent px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-all hover:bg-accent-hover"
      >
        <Plus class="h-4 w-4" />
        <span>Add Instance</span>
      </button>
    </div>

    {#if enginesError}
      <div
        class="flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-3.5 text-xs text-rose-300"
      >
        <AlertCircle class="h-4 w-4 shrink-0 text-rose-400" />
        <span>{enginesError}</span>
      </div>
    {/if}

    {#if showAddEngineForm}
      <form
        onsubmit={(e) => {
          e.preventDefault();
          handleAddEngine();
        }}
        class="space-y-3 rounded-xl border border-slate-800 bg-slate-950 p-4"
      >
        <h3 class="text-xs font-bold uppercase tracking-wider text-slate-200">
          Register Parsing Engine Instance
        </h3>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label for="engine-name" class="mb-1 block text-caption font-semibold text-slate-400">
              Name <span class="text-rose-400">*</span>
            </label>
            <input
              id="engine-name"
              type="text"
              required
              bind:value={newEngineName}
              placeholder="local, hosted-1, hosted-2..."
              class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
            />
          </div>
          <div>
            <label for="engine-kind" class="mb-1 block text-caption font-semibold text-slate-400">
              Kind
            </label>
            <select
              id="engine-kind"
              bind:value={newEngineKind}
              class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              {#each engineKinds as kindOption (kindOption.kind)}
                <option value={kindOption.kind}>{kindOption.display_name}</option>
              {/each}
            </select>
            {#if selectedKindInfo?.description}
              <p class="mt-1 text-caption text-slate-500">{selectedKindInfo.description}</p>
            {/if}
          </div>
        </div>

        <div>
          <label for="engine-url" class="mb-1 block text-caption font-semibold text-slate-400">
            API URL <span class="text-rose-400">*</span>
          </label>
          <input
            id="engine-url"
            type="text"
            required
            bind:value={newEngineUrl}
            placeholder={selectedKindInfo?.url_placeholder || "https://..."}
            class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
          />
        </div>

        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label for="engine-key" class="mb-1 block text-caption font-semibold text-slate-400">
              API Key{selectedKindInfo?.requires_api_key ? "" : " (not required)"}
            </label>
            <input
              id="engine-key"
              type="password"
              bind:value={newEngineKey}
              placeholder={selectedKindInfo?.requires_api_key ? "sk-..." : "(optional)"}
              class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
            />
          </div>
          {#if selectedKindInfo?.supports_strategy}
            <div>
              <label
                for="engine-strategy"
                class="mb-1 block text-caption font-semibold text-slate-400">Strategy</label
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
        </div>

        <div>
          <label for="engine-notes" class="mb-1 block text-caption font-semibold text-slate-400"
            >Notes (Optional)</label
          >
          <input
            id="engine-notes"
            type="text"
            bind:value={newEngineNotes}
            placeholder="e.g. EU region hosted account"
            class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
          />
        </div>

        <div class="flex items-center justify-end gap-2 pt-2">
          <button
            type="button"
            onclick={() => (showAddEngineForm = false)}
            class="rounded-xl border border-slate-800 px-3 py-1.5 text-xs text-slate-400 transition-colors hover:text-slate-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSavingEngine}
            class="flex items-center gap-1.5 rounded-xl bg-accent px-4 py-1.5 text-xs font-semibold text-white transition-all hover:bg-accent-hover disabled:opacity-50"
          >
            {#if isSavingEngine}
              <Loader2 class="h-3.5 w-3.5 animate-spin" />
              <span>Saving...</span>
            {:else}
              <span>Save Instance</span>
            {/if}
          </button>
        </div>
      </form>
    {/if}

    {#if enginesLoading}
      <div class="p-8 text-center text-xs text-slate-400">Loading parsing engines...</div>
    {:else if engines.length === 0}
      <div
        class="rounded-xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500"
      >
        No parsing engines configured — document upload falls back to the local, dependency-light
        extractor. Add a local container or a hosted account above.
      </div>
    {:else}
      <div class="space-y-2">
        {#each engines as engine (engine.id)}
          {@const info = kindInfo(engine.kind)}
          {@const accent = FAMILY_ACCENT[info?.family ?? ""] ?? FAMILY_ACCENT.default}
          <div
            class="flex flex-col gap-2 rounded-xl border border-slate-800/80 bg-slate-950/80 p-3.5 transition-colors hover:border-slate-700 sm:flex-row sm:items-start sm:justify-between"
          >
            <div class="space-y-1">
              <div class="flex flex-wrap items-center gap-2">
                {#if info?.requires_api_key}
                  <Cloud class="h-4 w-4 {accent}" />
                {:else}
                  <Server class="h-4 w-4 {accent}" />
                {/if}
                <span class="text-sm font-semibold text-slate-50">{engine.name}</span>
                <span
                  class="rounded-md border border-slate-800 bg-slate-900 px-2 py-0.5 text-micro font-semibold uppercase text-slate-400"
                >
                  {engine.kind}
                </span>
                {#if engine.is_default}
                  <span
                    class="inline-flex items-center gap-1 rounded-md border border-amber-800/60 bg-amber-950/60 px-2 py-0.5 text-micro font-semibold text-amber-300"
                  >
                    <Star class="h-3 w-3" /> Default
                  </span>
                {/if}
                {#if !engine.is_enabled}
                  <span
                    class="rounded-md border border-slate-700 bg-slate-800 px-2 py-0.5 text-micro font-semibold text-slate-400"
                  >
                    Disabled
                  </span>
                {/if}
              </div>
              <div class="font-mono text-caption text-slate-500">{engine.api_url}</div>
              <div class="flex flex-wrap items-center gap-2 text-caption text-slate-500">
                <span>strategy: {engine.strategy}</span>
                <span>&middot;</span>
                <span>{engine.has_api_key ? "API key set" : "no API key"}</span>
                {#if engine.notes}
                  <span>&middot;</span>
                  <span>{engine.notes}</span>
                {/if}
              </div>
              {#if testResults[engine.id]}
                <div
                  class="text-caption {testResults[engine.id].ok
                    ? 'text-emerald-400'
                    : 'text-rose-400'}"
                >
                  {testResults[engine.id].ok ? "Reachable" : "Unreachable"} — {testResults[
                    engine.id
                  ].detail}
                </div>
              {/if}
            </div>

            <div class="flex shrink-0 flex-wrap items-center gap-1.5">
              <button
                type="button"
                onclick={() => handleTestEngine(engine)}
                disabled={testingEngineId === engine.id}
                class="flex items-center gap-1 rounded-lg border border-slate-800 px-2.5 py-1.5 text-caption font-medium text-slate-300 transition-colors hover:bg-slate-800 disabled:opacity-50"
                title="Test connectivity"
              >
                {#if testingEngineId === engine.id}
                  <Loader2 class="h-3.5 w-3.5 animate-spin" />
                {:else}
                  <PlugZap class="h-3.5 w-3.5" />
                {/if}
                <span>Test</span>
              </button>
              {#if !engine.is_default}
                <button
                  type="button"
                  onclick={() => handleSetDefault(engine)}
                  class="rounded-lg border border-slate-800 px-2.5 py-1.5 text-caption font-medium text-slate-300 transition-colors hover:bg-slate-800"
                  title="Make default"
                >
                  Set Default
                </button>
              {/if}
              <button
                type="button"
                onclick={() => handleToggleEnabled(engine)}
                class="rounded-lg border border-slate-800 px-2.5 py-1.5 text-caption font-medium text-slate-300 transition-colors hover:bg-slate-800"
                title={engine.is_enabled ? "Disable" : "Enable"}
              >
                {engine.is_enabled ? "Disable" : "Enable"}
              </button>
              <button
                type="button"
                onclick={() => promptDeleteEngine(engine)}
                class="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-rose-950/30 hover:text-rose-400"
                title="Remove instance"
              >
                <Trash2 class="h-4 w-4" />
              </button>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>

  <!-- Settings Form Table -->
  <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
    <h2 class="text-base font-bold tracking-tight text-slate-50">Database Persisted Settings</h2>

    {#if isLoading}
      <div class="p-12 text-center text-xs text-slate-400">Loading settings...</div>
    {:else if settings.length === 0}
      <div
        class="rounded-xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500"
      >
        No settings records currently found in the database.
      </div>
    {:else}
      <div class="space-y-4">
        {#each settings as item (item.key)}
          <div class="space-y-1.5 border-b border-slate-800/80 pb-4 last:border-b-0">
            <div class="flex items-center justify-between">
              <label for={`setting-${item.key}`} class="font-mono text-xs font-bold text-slate-50"
                >{item.key}</label
              >
              {#if item.description}
                <span class="text-caption text-slate-400">{item.description}</span>
              {/if}
            </div>
            {#if item.key === "BIM_GUARD_LOG_LEVEL"}
              <select
                id={`setting-${item.key}`}
                bind:value={item.value}
                class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
              >
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
              </select>
            {:else}
              <input
                id={`setting-${item.key}`}
                type="text"
                bind:value={item.value}
                placeholder={item.description || item.key}
                class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 placeholder-slate-600 focus:border-accent focus:outline-none"
              />
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<ConfirmModal
  isOpen={enginePendingDelete !== null}
  title="Remove Parsing Engine"
  message={`Remove parsing engine '${enginePendingDelete?.name ?? ""}'? Documents already extracted with it are not affected.`}
  confirmText="Remove Instance"
  danger={true}
  onConfirm={handleDeleteEngine}
  onCancel={() => (enginePendingDelete = null)}
/>
