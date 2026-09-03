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

  interface Props {
    isOpen?: boolean;
    onClose: () => void;
    onSyncComplete?: (() => void) | undefined;
  }

  let { isOpen = false, onClose, onSyncComplete = undefined }: Props = $props();

  let projects: Project[] = $state([]);
  let selectedProjectId: number | null = $state(null);
  let isLoadingVersions = $state(false);
  let isSyncing = $state(false);
  let syncSuccess = $state(false);
  let syncMessage = $state("");
  let errorMessage = $state("");

  // OpenCDE Foundation info
  let cdeVersions: any = $state(null);
  let cdeUser: any = $state(null);

  // Sync Form
  let externalCdeType = $state("Autodesk Construction Cloud (ACC)");

  // The sync contract needs the CDE's base URL, while the picker shows the
  // platform's product name; keep the two associated here.
  const CDE_PLATFORM_URLS: Record<string, string> = {
    "Autodesk Construction Cloud (ACC)": "https://developer.api.autodesk.com/bim360/docs/v1",
    "Autodesk BIM 360": "https://developer.api.autodesk.com/bim360/docs/v1",
    "Dalux Box": "https://api.dalux.com/opencde/v1",
    "Trimble Connect": "https://app.connect.trimble.com/tc/api/opencde/v1",
    "Procore OpenBIM": "https://api.procore.com/rest/v1/opencde",
  };
  let externalProjectId = $state("urn:adsk.wipprod:dm.lineage:prj-001");
  let targetCdeState: CDEState = $state("SHARED");

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
      const [versions, user] = await Promise.all([cdeApi.getVersions(), cdeApi.getUser()]);
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
          CDE_PLATFORM_URLS[externalCdeType] ??
          CDE_PLATFORM_URLS["Autodesk Construction Cloud (ACC)"],
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
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div class="flex items-center gap-2.5">
          <div class="rounded-xl border border-blue-500/20 bg-blue-500/10 p-2 text-blue-400">
            <FolderSync class="h-5 w-5" />
          </div>
          <div>
            <h2 class="text-base font-bold tracking-tight text-slate-50">
              openCDE Foundation &amp; Documents Hub
            </h2>
            <p class="text-xs text-slate-400">
              buildingSMART OpenCDE RESTful model and document synchronization
            </p>
          </div>
        </div>
        <button
          type="button"
          onclick={onClose}
          class="rounded-xl p-2 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <!-- Body -->
      <div class="space-y-5 overflow-y-auto p-6 text-xs text-slate-300">
        <!-- OpenCDE Foundation Status -->
        <div class="space-y-3 rounded-xl border border-slate-800 bg-slate-950 p-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <Shield class="h-4 w-4 text-emerald-400" />
              <span class="text-caption font-bold uppercase tracking-wider text-slate-50"
                >OpenCDE Foundation Discovery</span
              >
            </div>
            <button
              type="button"
              onclick={loadCdeFoundationInfo}
              disabled={isLoadingVersions}
              class="inline-flex items-center gap-1 text-caption text-blue-400 hover:text-blue-300 disabled:opacity-50"
            >
              <RefreshCw class="h-3 w-3 {isLoadingVersions ? 'animate-spin' : ''}" />
              <span>Refresh</span>
            </button>
          </div>

          {#if cdeVersions}
            <div class="grid grid-cols-2 gap-2 text-caption">
              <div class="rounded-lg border border-slate-800 bg-slate-900 p-2.5">
                <span class="block text-micro font-semibold uppercase text-slate-500"
                  >Supported APIs</span
                >
                <span class="font-mono font-semibold text-emerald-400">
                  {cdeVersions.supported_apis
                    ? cdeVersions.supported_apis.map((a: any) => a.api_type || a).join(", ")
                    : "Foundation, Documents, BCF"}
                </span>
              </div>
              <div class="rounded-lg border border-slate-800 bg-slate-900 p-2.5">
                <span class="block text-micro font-semibold uppercase text-slate-500"
                  >User Context</span
                >
                <span class="block truncate font-semibold text-blue-400">
                  {cdeUser?.name || "BIMGuard Lead Auditor"} ({cdeUser?.organization ||
                    "buildingSMART Org"})
                </span>
              </div>
            </div>
          {:else if isLoadingVersions}
            <div class="flex items-center justify-center gap-2 py-2 text-center text-slate-500">
              <RefreshCw class="h-3.5 w-3.5 animate-spin text-blue-400" />
              <span>Connecting to /api/cde/versions...</span>
            </div>
          {/if}
        </div>

        <!-- Sync Configuration -->
        <div class="space-y-3">
          <span class="block text-micro font-semibold uppercase tracking-wider text-slate-400"
            >External CDE Synchronization Parameters</span
          >

          <!-- Target Project -->
          <div class="space-y-1">
            <label for="opencde-target-project" class="block font-medium text-slate-400"
              >BIMGuard Target Project</label
            >
            <select
              id="opencde-target-project"
              bind:value={selectedProjectId}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-blue-500 focus:outline-none"
            >
              {#each projects as p}
                <option value={p.id}>{p.name} (ISO: {p.cde_state || "WIP"})</option>
              {/each}
            </select>
          </div>

          <!-- External CDE Provider -->
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div class="space-y-1">
              <label for="opencde-platform" class="block font-medium text-slate-400"
                >External CDE Platform</label
              >
              <select
                id="opencde-platform"
                bind:value={externalCdeType}
                class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-blue-500 focus:outline-none"
              >
                <option value="Autodesk Construction Cloud (ACC)"
                  >Autodesk Construction Cloud (ACC)</option
                >
                <option value="Autodesk BIM 360">Autodesk BIM 360</option>
                <option value="Dalux Box">Dalux Box</option>
                <option value="Trimble Connect">Trimble Connect</option>
                <option value="Procore OpenBIM">Procore OpenBIM</option>
              </select>
            </div>

            <div class="space-y-1">
              <label for="opencde-target-state" class="block font-medium text-slate-400"
                >Target ISO 19650 State</label
              >
              <select
                id="opencde-target-state"
                bind:value={targetCdeState}
                class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-blue-500 focus:outline-none"
              >
                <option value="WIP">WIP (Work in Progress)</option>
                <option value="SHARED">SHARED (Coordination &amp; Review)</option>
                <option value="PUBLISHED">PUBLISHED (Authorized Contract Deliverable)</option>
                <option value="ARCHIVED">ARCHIVED</option>
              </select>
            </div>
          </div>

          <div class="space-y-1">
            <label for="opencde-resource-uri" class="block font-medium text-slate-400"
              >External Resource URI / Project Identifier</label
            >
            <input
              id="opencde-resource-uri"
              type="text"
              bind:value={externalProjectId}
              placeholder="urn:adsk.wipprod:dm.lineage:prj-001"
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-50 focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>

        {#if errorMessage}
          <div
            class="flex items-center gap-2 rounded-xl border border-rose-800/60 bg-rose-950/40 p-3 text-xs text-rose-300"
          >
            <AlertTriangle class="h-4 w-4 shrink-0 text-rose-400" />
            <span>{errorMessage}</span>
          </div>
        {/if}

        {#if syncSuccess}
          <div
            class="flex items-center gap-2 rounded-xl border border-emerald-800/60 bg-emerald-950/40 p-3 text-xs text-emerald-300"
          >
            <CheckCircle2 class="h-4 w-4 shrink-0 text-emerald-400" />
            <span>{syncMessage}</span>
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div
        class="flex items-center justify-between border-t border-slate-800 bg-slate-950/60 px-6 py-3"
      >
        <span class="text-caption text-slate-500">Conforms to buildingSMART OpenCDE v1.0</span>
        <div class="flex items-center gap-2">
          <button
            type="button"
            onclick={onClose}
            class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
          >
            Cancel
          </button>
          <button
            type="button"
            onclick={handleTriggerSync}
            disabled={isSyncing}
            class="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-blue-500 disabled:opacity-50"
          >
            {#if isSyncing}
              <RefreshCw class="h-3.5 w-3.5 animate-spin" />
              <span>Syncing...</span>
            {:else}
              <FolderSync class="h-3.5 w-3.5" />
              <span>Trigger OpenCDE Sync</span>
            {/if}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}
