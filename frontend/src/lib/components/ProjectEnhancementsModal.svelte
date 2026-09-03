<script lang="ts">
  import { run } from "svelte/legacy";

  import { onMount } from "svelte";
  import {
    X,
    Sparkles,
    Download,
    CheckCircle2,
    AlertTriangle,
    ShieldAlert,
    Eye,
  } from "lucide-svelte";
  import { lineageApi } from "../api";
  import type { Project, ModelLineageRecord } from "../types";

  interface Props {
    isOpen?: boolean;
    project?: Project | null;
    onClose: () => void;
  }

  let { isOpen = false, project = null, onClose }: Props = $props();

  let isRunning = $state(false);
  let message = $state("");
  let messageType: "success" | "error" = $state("success");
  let history: ModelLineageRecord[] = $state([]);
  let isLoadingHistory = $state(false);
  let selectedVersionForView: ModelLineageRecord | null = $state(null);

  async function loadHistory() {
    if (!project) return;
    isLoadingHistory = true;
    try {
      history = await lineageApi.getHistory(project.id);
    } catch {
      history = [];
    } finally {
      isLoadingHistory = false;
    }
  }

  run(() => {
    if (isOpen && project) {
      loadHistory();
    }
  });

  async function handleRunEnhancement() {
    if (!project) return;
    isRunning = true;
    message = "";

    try {
      const res = await lineageApi.enhance(project.id);
      message = res.reused
        ? `Reused persisted quality-improved version v${res.version}`
        : `Quality improvements persisted as version v${res.version}`;
      messageType = "success";
      await loadHistory();
    } catch (err: any) {
      message = err.message || "Enhancement failed. Check project IFC source.";
      messageType = "error";
    } finally {
      isRunning = false;
    }
  }
</script>

{#if isOpen && project}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div class="flex items-center gap-2.5">
          <div class="rounded-xl border border-purple-500/20 bg-purple-500/10 p-2 text-purple-400">
            <Sparkles class="h-5 w-5" />
          </div>
          <div>
            <h2 class="text-lg font-bold tracking-tight text-slate-50">
              Quality Improvements — {project.name}
            </h2>
            <p class="text-xs text-slate-400">
              Generate and persist an improved IFC version without mutating the original source.
            </p>
          </div>
        </div>
        <button
          type="button"
          onclick={onClose}
          class="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <!-- Body -->
      <div class="flex-1 space-y-6 overflow-y-auto p-6">
        {#if message}
          <div
            class="flex items-center gap-2 rounded-xl p-3.5 text-xs {messageType === 'success'
              ? 'border border-emerald-800 bg-emerald-950/40 text-emerald-300'
              : 'border border-rose-800 bg-rose-950/40 text-rose-300'}"
          >
            {#if messageType === "success"}
              <CheckCircle2 class="h-4 w-4 shrink-0 text-emerald-400" />
            {:else}
              <AlertTriangle class="h-4 w-4 shrink-0 text-rose-400" />
            {/if}
            <span>{message}</span>
          </div>
        {/if}

        <!-- Run form -->
        <div class="space-y-3 rounded-2xl border border-slate-800 bg-slate-950/60 p-5">
          <h3 class="text-sm font-semibold text-slate-50">Execute IFC Quality Improvement</h3>
          <p class="text-xs text-slate-400">
            Triggers an automated quality improvement pass. Normalizes geometric properties,
            property sets, and element GUID linkages without mutating original project IFC files.
          </p>

          <div class="flex items-center gap-3 pt-1">
            <button
              type="button"
              disabled={isRunning || !project.ifc_file_path}
              onclick={handleRunEnhancement}
              class="flex shrink-0 items-center justify-center gap-2 rounded-xl bg-purple-600 px-5 py-2.5 text-xs font-semibold text-white shadow-sm shadow-purple-600/20 transition-all hover:scale-[1.02] hover:bg-purple-500 disabled:opacity-50 disabled:hover:scale-100"
            >
              <Sparkles class="h-4 w-4 {isRunning ? 'animate-spin' : ''}" />
              <span
                >{isRunning ? "Processing Model Quality Improvements..." : "Run Improvements"}</span
              >
            </button>

            {#if !project.ifc_file_path}
              <div class="flex items-center gap-1.5 text-caption text-amber-400">
                <ShieldAlert class="h-3.5 w-3.5" />
                <span>Cannot enhance: this project does not have an attached IFC file.</span>
              </div>
            {/if}
          </div>
        </div>

        <!-- Lineage History Table -->
        <div class="space-y-3">
          <h3 class="text-sm font-semibold text-slate-50">Persisted Improvement History</h3>

          <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/40">
            {#if isLoadingHistory}
              <div class="p-8 text-center text-xs text-slate-400">Loading version history...</div>
            {:else if history.length === 0}
              <div class="p-8 text-center text-xs text-slate-500">
                No improved versions generated yet for this project.
              </div>
            {:else}
              <div class="overflow-x-auto">
                <table class="w-full text-left text-xs text-slate-300">
                  <thead
                    class="border-b border-slate-800 bg-slate-950 text-caption font-semibold uppercase tracking-wider text-slate-400"
                  >
                    <tr>
                      <th class="px-4 py-3">Source Ver</th>
                      <th class="px-4 py-3">Generated Ver</th>
                      <th class="px-4 py-3">Status</th>
                      <th class="px-4 py-3">Summary</th>
                      <th class="px-4 py-3">Created</th>
                      <th class="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-slate-800/60">
                    {#each history as row (row.id)}
                      <tr class="transition-colors hover:bg-slate-900/50">
                        <td class="px-4 py-3 font-mono text-slate-400">v{row.source_version}</td>
                        <td class="px-4 py-3 font-mono font-semibold text-purple-300"
                          >v{row.version}</td
                        >
                        <td class="px-4 py-3">
                          <span
                            class="inline-block rounded-full border border-emerald-800/60 bg-emerald-950/50 px-2 py-0.5 text-micro font-semibold text-emerald-400"
                          >
                            {row.status}
                          </span>
                        </td>
                        <td
                          class="max-w-xs truncate px-4 py-3 font-mono text-caption text-slate-400"
                        >
                          {JSON.stringify(row.summary || {})}
                        </td>
                        <td class="whitespace-nowrap px-4 py-3 text-caption text-slate-400">
                          {row.created_at ? row.created_at.substring(0, 10) : "-"}
                        </td>
                        <td class="whitespace-nowrap px-4 py-3 text-right">
                          <div class="flex items-center justify-end gap-1.5">
                            <button
                              type="button"
                              onclick={() => (selectedVersionForView = row)}
                              class="rounded-lg bg-slate-800 p-1.5 text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
                              title="Inspect version details"
                            >
                              <Eye class="h-3.5 w-3.5" />
                            </button>
                            {#if row.output_reference}
                              <a
                                href={`/api/projects/${project.id}/enhancements/${row.id}/download`}
                                class="inline-flex items-center gap-1 rounded-lg border border-purple-800/40 bg-purple-950/40 px-3 py-1 text-xs font-medium text-purple-300 transition-colors hover:bg-purple-900/60"
                                title="Download enhanced IFC"
                              >
                                <Download class="h-3 w-3" />
                                <span>Download</span>
                              </a>
                            {/if}
                          </div>
                        </td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            {/if}
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="flex justify-end border-t border-slate-800 bg-slate-950/60 px-6 py-3">
        <button
          type="button"
          onclick={onClose}
          class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}

{#if selectedVersionForView}
  <div
    class="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 p-4 backdrop-blur-md"
  >
    <div
      class="w-full max-w-lg space-y-4 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <Sparkles class="h-4 w-4 text-purple-400" />
          <h3 class="text-sm font-bold text-slate-50">
            Lineage Version v{selectedVersionForView.version} Details
          </h3>
        </div>
        <button
          type="button"
          onclick={() => (selectedVersionForView = null)}
          class="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <div class="space-y-3 text-xs">
        <div
          class="grid grid-cols-2 gap-2 rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono"
        >
          <div>
            <span class="text-slate-500">Source:</span>
            <span class="text-slate-300">v{selectedVersionForView.source_version}</span>
          </div>
          <div>
            <span class="text-slate-500">Generated:</span>
            <span class="text-purple-300">v{selectedVersionForView.version}</span>
          </div>
          <div>
            <span class="text-slate-500">Status:</span>
            <span class="text-emerald-400">{selectedVersionForView.status}</span>
          </div>
          <div>
            <span class="text-slate-500">Created:</span>
            <span class="text-slate-400">{selectedVersionForView.created_at?.substring(0, 10)}</span
            >
          </div>
        </div>

        <div>
          <span class="text-caption font-semibold uppercase tracking-wider text-slate-400"
            >Modifications Summary</span
          >
          <pre
            class="mt-1 max-h-56 overflow-auto rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono text-caption text-slate-300">{JSON.stringify(
              selectedVersionForView.summary,
              null,
              2,
            )}</pre>
        </div>

        {#if selectedVersionForView.output_reference}
          <div class="truncate text-caption text-slate-400">
            <span class="font-semibold text-slate-300">Storage Ref:</span>
            {selectedVersionForView.output_reference}
          </div>
        {/if}
      </div>

      <div class="flex justify-end pt-2">
        <button
          type="button"
          onclick={() => (selectedVersionForView = null)}
          class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}
