<script lang="ts">
  import { onMount } from "svelte";
  import { push } from "svelte-spa-router";
  import {
    PlayCircle,
    CheckCircle2,
    Circle,
    FolderOpen,
    ChevronDown,
    RefreshCw,
    UploadCloud,
    Boxes,
    AlertCircle,
    Loader2,
  } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import ProjectWizardModal from "../lib/components/ProjectWizardModal.svelte";
  import UploadModelsModal from "../lib/components/UploadModelsModal.svelte";
  import { projectsApi, rulesApi, documentsApi, analyzeApi } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import { toasts } from "../lib/toast.svelte";
  import { DOCUMENT_TYPES } from "../lib/types";
  import type { Project, RuleFolder, ProjectIfcFile } from "../lib/types";

  // Step 1: project + IFC model.
  let isWizardOpen = $state(false);
  let project: Project | null = $state(null);
  let ifcFiles: ProjectIfcFile[] = $state([]);
  let isModelModalOpen = $state(false);
  let isCheckingModel = $state(false);

  // Step 2: ruleset (pick existing, or extract a new one in another tab).
  let ruleFolders: RuleFolder[] = $state([]);
  let isFoldersLoading = $state(false);
  let selectedFolder = $state("");
  let uploadFile: File | null = $state(null);
  let uploadDocType = $state("Specification");
  let isUploadingDoc = $state(false);
  let uploadError = $state("");

  // Step 3: run.
  let isRunning = $state(false);
  let runError = $state("");

  const hasModel = $derived(ifcFiles.length > 0);
  const hasRuleset = $derived(!!selectedFolder);

  async function handleProjectCreated(created: Project) {
    project = created;
    isWizardOpen = false;
    toasts.success("Project saved — find it later under Project Registry on the Dashboard.");
    await refreshModels();
  }

  async function refreshModels() {
    if (!project) return;
    isCheckingModel = true;
    try {
      ifcFiles = await projectsApi.listIfcFiles(project.id);
    } catch {
      ifcFiles = [];
    } finally {
      isCheckingModel = false;
    }
  }

  function handleModelsUploaded(files: ProjectIfcFile[]) {
    ifcFiles = files;
    isModelModalOpen = false;
  }

  async function loadFolders() {
    isFoldersLoading = true;
    try {
      ruleFolders = await rulesApi.folders("Arch");
    } catch {
      ruleFolders = [];
    } finally {
      isFoldersLoading = false;
    }
  }

  // A ruleset saved from Rule Extraction Studio in another tab won't reach
  // this tab's own cache on its own -- there's no cross-tab messaging in this
  // app -- so re-check whenever the user switches back to this tab.
  async function refreshFolders() {
    rulesApi.clearCache();
    await loadFolders();
  }

  function handleWindowFocus() {
    refreshFolders();
  }

  onMount(() => {
    loadFolders();
    window.addEventListener("focus", handleWindowFocus);
    return () => window.removeEventListener("focus", handleWindowFocus);
  });

  async function handleUploadDocument() {
    if (!uploadFile) return;
    isUploadingDoc = true;
    uploadError = "";
    try {
      const created = await documentsApi.upload(uploadFile, uploadDocType, {
        organization_id: authState.activeOrganizationId,
      });
      uploadFile = null;
      // A one-shot builder for a URL string, never read reactively, so the
      // plain built-in is correct here.
      // eslint-disable-next-line svelte/prefer-svelte-reactivity
      const params = new URLSearchParams();
      params.set("doc_id", String(created.id));
      params.set("from", "quick-test");
      window.open(`/#/extract?${params.toString()}`, "_blank");
    } catch (err: any) {
      uploadError = err?.message || "Upload failed.";
    } finally {
      isUploadingDoc = false;
    }
  }

  async function handleRunTest() {
    if (!project || !hasModel || !hasRuleset) return;
    isRunning = true;
    runError = "";
    try {
      await analyzeApi.runArch(project.id, selectedFolder);
      // A one-shot builder for a URL string, never read reactively, so the
      // plain built-in is correct here.
      // eslint-disable-next-line svelte/prefer-svelte-reactivity
      const params = new URLSearchParams();
      params.set("project_id", String(project.id));
      if (authState.activeOrganizationId) params.set("org", String(authState.activeOrganizationId));
      push(`/arch?${params.toString()}`);
    } catch (err: any) {
      runError = err?.message || "Failed to run the compliance test.";
    } finally {
      isRunning = false;
    }
  }
</script>

<div class="mx-auto max-w-4xl space-y-6">
  <PageHeader
    category="Quick Start"
    title="Run Compliance Test"
    subtitle="Create a project, attach a model and a ruleset, then run your first Architectural compliance audit — all from one guided flow."
    icon={PlayCircle}
  />

  <!-- Step 1: Project -->
  <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
    <div class="flex items-center gap-2.5">
      {#if project}
        <CheckCircle2 class="h-5 w-5 shrink-0 text-emerald-400" />
      {:else}
        <Circle class="h-5 w-5 shrink-0 text-accent" />
      {/if}
      <h2 class="text-base font-bold tracking-tight text-slate-50">1. Create your project</h2>
    </div>

    {#if !project}
      <p class="text-xs text-slate-400">
        Give it a name, country and analysis type — you can attach the IFC model in the same
        step.
      </p>
      <button
        type="button"
        onclick={() => (isWizardOpen = true)}
        class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-sm transition-all hover:bg-accent-hover"
      >
        Create New Project
      </button>
    {:else}
      <div class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/50 p-3.5">
        <div class="min-w-0">
          <p class="truncate text-sm font-semibold text-slate-100">{project.name}</p>
          <p class="text-micro text-slate-500">{project.country} · {project.analysis_type}</p>
        </div>
        {#if isCheckingModel}
          <span class="flex shrink-0 items-center gap-1.5 text-micro text-slate-500">
            <Loader2 class="h-3.5 w-3.5 animate-spin" /> Checking for a model…
          </span>
        {:else if hasModel}
          <span class="flex shrink-0 items-center gap-1.5 text-micro font-medium text-emerald-400">
            <CheckCircle2 class="h-3.5 w-3.5" />
            {ifcFiles.length} model{ifcFiles.length === 1 ? "" : "s"} attached
          </span>
        {:else}
          <button
            type="button"
            onclick={() => (isModelModalOpen = true)}
            class="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-amber-800/60 bg-amber-950/40 px-3 py-1.5 text-micro font-semibold text-amber-300 transition-colors hover:bg-amber-950/70"
          >
            <Boxes class="h-3.5 w-3.5" />
            Attach an IFC Model
          </button>
        {/if}
      </div>
    {/if}
  </div>

  <!-- Step 2: Ruleset -->
  <div
    class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-6 {!project
      ? 'pointer-events-none opacity-50'
      : ''}"
  >
    <div class="flex items-center gap-2.5">
      {#if hasRuleset}
        <CheckCircle2 class="h-5 w-5 shrink-0 text-emerald-400" />
      {:else}
        <Circle class="h-5 w-5 shrink-0 text-accent" />
      {/if}
      <h2 class="text-base font-bold tracking-tight text-slate-50">2. Pick a ruleset</h2>
    </div>

    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <!-- Choose existing -->
      <div class="space-y-2.5 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
        <div class="flex items-center justify-between">
          <span class="flex items-center gap-1.5 text-xs font-bold text-slate-300">
            <FolderOpen class="h-3.5 w-3.5 text-accent" />
            Choose Existing Ruleset
          </span>
          <button
            type="button"
            onclick={refreshFolders}
            disabled={isFoldersLoading}
            title="Refresh the ruleset list"
            class="rounded-lg p-1 text-slate-500 transition-colors hover:bg-slate-800 hover:text-slate-100 disabled:opacity-50"
          >
            <RefreshCw class="h-3.5 w-3.5 {isFoldersLoading ? 'animate-spin' : ''}" />
          </button>
        </div>
        <div class="relative">
          <select
            bind:value={selectedFolder}
            disabled={isFoldersLoading}
            class="w-full appearance-none rounded-lg border border-slate-700 bg-slate-800/60 py-1.5 pl-3 pr-8 text-xs font-medium text-slate-50 focus:border-accent focus:outline-none disabled:opacity-60"
          >
            <option value="">{isFoldersLoading ? "Loading…" : "-- Select a ruleset --"}</option>
            {#each ruleFolders as folder (folder.ruleset_id)}
              <option value={folder.ruleset_id}>{folder.display_name}</option>
            {/each}
          </select>
          <ChevronDown
            class="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400"
          />
        </div>
        <p class="text-micro text-slate-500">
          Just saved one in another tab? Click back into this tab and it refreshes
          automatically — or use the refresh button above.
        </p>
      </div>

      <!-- Upload new -->
      <div class="space-y-2.5 rounded-xl border border-slate-800 bg-slate-950/40 p-4">
        <span class="flex items-center gap-1.5 text-xs font-bold text-slate-300">
          <UploadCloud class="h-3.5 w-3.5 text-accent" />
          Upload New Document
        </span>
        {#if uploadError}
          <p class="text-micro text-rose-400">{uploadError}</p>
        {/if}
        <input
          type="file"
          accept=".pdf,.doc,.docx,.txt"
          onchange={(e) => (uploadFile = (e.target as HTMLInputElement).files?.[0] || null)}
          class="block w-full text-micro text-slate-400 file:mr-2 file:rounded-lg file:border-0 file:bg-slate-800 file:px-2.5 file:py-1.5 file:text-micro file:font-semibold file:text-slate-200 hover:file:bg-slate-700"
        />
        <select
          bind:value={uploadDocType}
          class="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
        >
          {#each DOCUMENT_TYPES as type (type)}
            <option value={type}>{type}</option>
          {/each}
        </select>
        <button
          type="button"
          onclick={handleUploadDocument}
          disabled={!uploadFile || isUploadingDoc}
          class="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-white transition-all hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isUploadingDoc ? "Uploading…" : "Upload & Extract Rules"}
        </button>
        <p class="text-micro text-slate-500">
          Opens Rule Extraction Studio in a new tab to review and approve the extracted rules.
        </p>
      </div>
    </div>
  </div>

  <!-- Step 3: Run -->
  <div
    class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-6 {!project || !hasRuleset
      ? 'pointer-events-none opacity-50'
      : ''}"
  >
    <div class="flex items-center gap-2.5">
      <Circle class="h-5 w-5 shrink-0 text-accent" />
      <h2 class="text-base font-bold tracking-tight text-slate-50">3. Run the test</h2>
    </div>

    {#if runError}
      <div
        class="flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300"
      >
        <AlertCircle class="h-4 w-4 shrink-0" />
        <span>{runError}</span>
      </div>
    {/if}

    <button
      type="button"
      onclick={handleRunTest}
      disabled={!project || !hasModel || !hasRuleset || isRunning}
      class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
    >
      {#if isRunning}
        <Loader2 class="h-4 w-4 animate-spin" />
        Running…
      {:else}
        <PlayCircle class="h-4 w-4" />
        Run Compliance Test
      {/if}
    </button>
  </div>
</div>

<ProjectWizardModal
  isOpen={isWizardOpen}
  onClose={() => (isWizardOpen = false)}
  onProjectCreated={handleProjectCreated}
/>

<UploadModelsModal
  isOpen={isModelModalOpen}
  projectId={project?.id ?? null}
  onClose={() => (isModelModalOpen = false)}
  onUploaded={handleModelsUploaded}
/>
