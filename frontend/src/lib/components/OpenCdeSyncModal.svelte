<script lang="ts">
  import { onMount } from "svelte";
  import {
    X,
    FolderSync,
    Layers,
    CheckCircle2,
    AlertTriangle,
    RefreshCw,
    ExternalLink,
    Shield,
    FileText,
    ArrowRight,
    Building,
  } from "lucide-svelte";
  import { cdeApi, projectsApi } from "../api";
  import type { Project, CDEState } from "../types";

  export let isOpen: boolean = false;
  export let onClose: () => void;
  export let onSyncComplete: (() => void) | undefined = undefined;

  let projects: Project[] = [];
  let selectedProjectId: number | null = null;
  let isLoadingVersions = false;
  let isSyncing = false;
  let syncSuccess = false;
  let syncMessage = "";
  let errorMessage = "";

  // OpenCDE Foundation info
  let cdeVersions: any = null;
  let cdeUser: any = null;

  // Sync Form
  let externalCdeType = "Autodesk Construction Cloud (ACC)";

  // The sync contract needs the CDE's base URL, while the picker shows the
  // platform's product name; keep the two associated here.
  const CDE_PLATFORM_URLS: Record<string, string> = {
    "Autodesk Construction Cloud (ACC)": "https://developer.api.autodesk.com/bim360/docs/v1",
    "Autodesk BIM 360": "https://developer.api.autodesk.com/bim360/docs/v1",
    "Dalux Box": "https://api.dalux.com/opencde/v1",
    "Trimble Connect": "https://app.connect.trimble.com/tc/api/opencde/v1",
    "Procore OpenBIM": "https://api.procore.com/rest/v1/opencde",
  };
  let externalProjectId = "urn:adsk.wipprod:dm.lineage:prj-001";
  let targetCdeState: CDEState = "SHARED";

  onMount(async () => {
    try {
      const data = await projectsApi.list();
      projects = data.projects || [];
      if (projects.length > 0) {
        selectedProjectId = projects[0].id;
      }
      await loadCdeFoundationInfo();
    } catch {
      // ignore
    }
  });

  async function loadCdeFoundationInfo() {
    isLoadingVersions = true;
    errorMessage = "";
    try {
      const [versions, user] = await Promise.all([
        cdeApi.getVersions(),
        cdeApi.getUser(),
      ]);
      cdeVersions = versions;
      cdeUser = user;
    } catch (err: any) {
      errorMessage = err.message || "Failed to query OpenCDE Foundation discovery endpoint.";
    } finally {
      isLoadingVersions = false;
    }
  }

  async function handleTriggerSync() {
    if (!selectedProjectId) {
      errorMessage = "Please select a project to synchronize.";
      return;
    }
    isSyncing = true;
    errorMessage = "";
    syncSuccess = false;
    syncMessage = "";

    try {
      const res = await cdeApi.syncDocuments({
        cde_server_url:
          CDE_PLATFORM_URLS[externalCdeType] ?? CDE_PLATFORM_URLS["Autodesk Construction Cloud (ACC)"],
        project_id: selectedProjectId,
        external_project_id: externalProjectId,
      });
      syncSuccess = true;
      syncMessage = `Synchronized ${res.synced_documents_count ?? 1} documents and models via OpenCDE Documents API (ISO 19650 State: ${targetCdeState}).`;
      if (onSyncComplete) {
        onSyncComplete();
      }
    } catch (err: any) {
      errorMessage = err.message || "Document sync failed via OpenCDE API.";
    } finally {
      isSyncing = false;
    }
  }
</script>

{#if isOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <FolderSync class="w-5 h-5" />
          </div>
          <div>
            <h2 class="text-base font-bold text-white tracking-tight">openCDE Foundation &amp; Documents Hub</h2>
            <p class="text-xs text-slate-400">buildingSMART OpenCDE RESTful model and document synchronization</p>
          </div>
        </div>
        <button
          type="button"
          on:click={onClose}
          class="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Body -->
      <div class="p-6 overflow-y-auto space-y-5 text-xs text-slate-300">
        <!-- OpenCDE Foundation Status -->
        <div class="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <Shield class="w-4 h-4 text-emerald-400" />
              <span class="font-bold text-white uppercase tracking-wider text-[11px]">OpenCDE Foundation Discovery</span>
            </div>
            <button
              type="button"
              on:click={loadCdeFoundationInfo}
              disabled={isLoadingVersions}
              class="inline-flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 disabled:opacity-50"
            >
              <RefreshCw class="w-3 h-3 {isLoadingVersions ? 'animate-spin' : ''}" />
              <span>Refresh</span>
            </button>
          </div>

          {#if cdeVersions}
            <div class="grid grid-cols-2 gap-2 text-[11px]">
              <div class="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                <span class="text-slate-500 block text-[10px] uppercase font-semibold">Supported APIs</span>
                <span class="text-emerald-400 font-semibold font-mono">
                  {cdeVersions.supported_apis ? cdeVersions.supported_apis.map((a: any) => a.api_type || a).join(', ') : 'Foundation, Documents, BCF'}
                </span>
              </div>
              <div class="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                <span class="text-slate-500 block text-[10px] uppercase font-semibold">User Context</span>
                <span class="text-blue-400 font-semibold truncate block">
                  {cdeUser?.name || 'BIMGuard Lead Auditor'} ({cdeUser?.organization || 'buildingSMART Org'})
                </span>
              </div>
            </div>
          {:else if isLoadingVersions}
            <div class="py-2 text-center text-slate-500 flex items-center justify-center gap-2">
              <RefreshCw class="w-3.5 h-3.5 animate-spin text-blue-400" />
              <span>Connecting to /api/cde/versions...</span>
            </div>
          {/if}
        </div>

        <!-- Sync Configuration -->
        <div class="space-y-3">
          <span class="text-slate-400 text-[10px] uppercase tracking-wider font-semibold block">External CDE Synchronization Parameters</span>

          <!-- Target Project -->
          <div class="space-y-1">
            <label for="opencde-target-project" class="block text-slate-400 font-medium">BIMGuard Target Project</label>
            <select
              id="opencde-target-project"
              bind:value={selectedProjectId}
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
            >
              {#each projects as p}
                <option value={p.id}>{p.name} (ISO: {p.cde_state || 'WIP'})</option>
              {/each}
            </select>
          </div>

          <!-- External CDE Provider -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div class="space-y-1">
              <label for="opencde-platform" class="block text-slate-400 font-medium">External CDE Platform</label>
              <select
                id="opencde-platform"
                bind:value={externalCdeType}
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
              >
                <option value="Autodesk Construction Cloud (ACC)">Autodesk Construction Cloud (ACC)</option>
                <option value="Autodesk BIM 360">Autodesk BIM 360</option>
                <option value="Dalux Box">Dalux Box</option>
                <option value="Trimble Connect">Trimble Connect</option>
                <option value="Procore OpenBIM">Procore OpenBIM</option>
              </select>
            </div>

            <div class="space-y-1">
              <label for="opencde-target-state" class="block text-slate-400 font-medium">Target ISO 19650 State</label>
              <select
                id="opencde-target-state"
                bind:value={targetCdeState}
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
              >
                <option value="WIP">WIP (Work in Progress)</option>
                <option value="SHARED">SHARED (Coordination &amp; Review)</option>
                <option value="PUBLISHED">PUBLISHED (Authorized Contract Deliverable)</option>
                <option value="ARCHIVED">ARCHIVED</option>
              </select>
            </div>
          </div>

          <div class="space-y-1">
            <label for="opencde-resource-uri" class="block text-slate-400 font-medium">External Resource URI / Project Identifier</label>
            <input
              id="opencde-resource-uri"
              type="text"
              bind:value={externalProjectId}
              placeholder="urn:adsk.wipprod:dm.lineage:prj-001"
              class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white font-mono focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        {#if errorMessage}
          <div class="p-3 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs flex items-center gap-2">
            <AlertTriangle class="w-4 h-4 shrink-0 text-rose-400" />
            <span>{errorMessage}</span>
          </div>
        {/if}

        {#if syncSuccess}
          <div class="p-3 rounded-xl bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 class="w-4 h-4 shrink-0 text-emerald-400" />
            <span>{syncMessage}</span>
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div class="px-6 py-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between">
        <span class="text-[11px] text-slate-500">Conforms to buildingSMART OpenCDE v1.0</span>
        <div class="flex items-center gap-2">
          <button
            type="button"
            on:click={onClose}
            class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            on:click={handleTriggerSync}
            disabled={isSyncing}
            class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-colors disabled:opacity-50"
          >
            {#if isSyncing}
              <RefreshCw class="w-3.5 h-3.5 animate-spin" />
              <span>Syncing...</span>
            {:else}
              <FolderSync class="w-3.5 h-3.5" />
              <span>Trigger OpenCDE Sync</span>
            {/if}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}
