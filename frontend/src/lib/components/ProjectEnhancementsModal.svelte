<script lang="ts">
  import { onMount } from 'svelte';
  import { X, Sparkles, Download, CheckCircle2, AlertTriangle, ShieldAlert } from 'lucide-svelte';
  import { lineageApi } from '../api';
  import type { Project, ModelLineageRecord } from '../types';

  export let isOpen: boolean = false;
  export let project: Project | null = null;
  export let onClose: () => void;

  let token = '';
  let isRunning = false;
  let message = '';
  let messageType: 'success' | 'error' = 'success';
  let history: ModelLineageRecord[] = [];
  let isLoadingHistory = false;

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

  $: if (isOpen && project) {
    loadHistory();
  }

  async function handleRunEnhancement() {
    if (!project) return;
    if (!token.trim()) {
      message = 'Please provide an enhancement authorization token.';
      messageType = 'error';
      return;
    }

    isRunning = true;
    message = '';

    try {
      const res = await lineageApi.enhance(project.id, token);
      message = res.reused
        ? `Reused persisted quality-improved version v${res.version}`
        : `Quality improvements persisted as version v${res.version}`;
      messageType = 'success';
      token = '';
      await loadHistory();
    } catch (err: any) {
      message = err.message || 'Enhancement failed. Check your token and project IFC source.';
      messageType = 'error';
    } finally {
      isRunning = false;
    }
  }
</script>

{#if isOpen && project}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div class="flex items-center gap-2.5">
          <div class="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Sparkles class="w-5 h-5" />
          </div>
          <div>
            <h2 class="text-lg font-bold text-white tracking-tight">Quality Improvements — {project.name}</h2>
            <p class="text-xs text-slate-400">Generate and persist an improved IFC version without mutating the original source.</p>
          </div>
        </div>
        <button
          type="button"
          on:click={onClose}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Body -->
      <div class="p-6 overflow-y-auto space-y-6 flex-1">
        {#if message}
          <div class="p-3.5 rounded-xl text-xs flex items-center gap-2 {messageType === 'success' ? 'bg-emerald-950/40 border border-emerald-800 text-emerald-300' : 'bg-rose-950/40 border border-rose-800 text-rose-300'}">
            {#if messageType === 'success'}
              <CheckCircle2 class="w-4 h-4 text-emerald-400 shrink-0" />
            {:else}
              <AlertTriangle class="w-4 h-4 text-rose-400 shrink-0" />
            {/if}
            <span>{message}</span>
          </div>
        {/if}

        <!-- Run form -->
        <div class="p-5 rounded-2xl bg-slate-950/60 border border-slate-800 space-y-3">
          <h3 class="text-sm font-semibold text-white">Execute IFC Enhancement</h3>
          <p class="text-xs text-slate-400">
            Authorizes an automated quality improvement pass. Normalizes geometric properties, property sets, and element GUID linkages.
          </p>

          <div class="flex flex-col sm:flex-row gap-3 pt-1">
            <div class="flex-1">
              <label for="enhancement-token" class="sr-only">Authorization Token</label>
              <input
                id="enhancement-token"
                type="password"
                bind:value={token}
                placeholder="Enter enhancement authorization token"
                class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
            <button
              type="button"
              disabled={isRunning || !project.ifc_file_path}
              on:click={handleRunEnhancement}
              class="px-5 py-2 rounded-xl text-xs font-semibold bg-purple-600 hover:bg-purple-500 text-white shadow-sm shadow-purple-600/20 transition-all disabled:opacity-50 flex items-center justify-center gap-2 shrink-0"
            >
              <Sparkles class="w-3.5 h-3.5" />
              <span>{isRunning ? 'Processing Model...' : 'Run Improvements'}</span>
            </button>
          </div>

          {#if !project.ifc_file_path}
            <div class="text-[11px] text-amber-400 flex items-center gap-1.5 pt-1">
              <ShieldAlert class="w-3.5 h-3.5" />
              <span>Cannot enhance: this project does not have an attached IFC file.</span>
            </div>
          {/if}
        </div>

        <!-- Lineage History Table -->
        <div class="space-y-3">
          <h3 class="text-sm font-semibold text-white">Persisted Improvement History</h3>

          <div class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-950/40">
            {#if isLoadingHistory}
              <div class="p-8 text-center text-xs text-slate-400">Loading version history...</div>
            {:else if history.length === 0}
              <div class="p-8 text-center text-xs text-slate-500">
                No improved versions generated yet for this project.
              </div>
            {:else}
              <div class="overflow-x-auto">
                <table class="w-full text-left text-xs text-slate-300">
                  <thead class="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                    <tr>
                      <th class="px-4 py-3">Source Ver</th>
                      <th class="px-4 py-3">Generated Ver</th>
                      <th class="px-4 py-3">Status</th>
                      <th class="px-4 py-3">Summary</th>
                      <th class="px-4 py-3">Created</th>
                      <th class="px-4 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-slate-800/60">
                    {#each history as row}
                      <tr class="hover:bg-slate-900/50 transition-colors">
                        <td class="px-4 py-3 font-mono text-slate-400">v{row.source_version}</td>
                        <td class="px-4 py-3 font-semibold text-purple-300 font-mono">v{row.version}</td>
                        <td class="px-4 py-3">
                          <span class="inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-950/50 text-emerald-400 border border-emerald-800/60">
                            {row.status}
                          </span>
                        </td>
                        <td class="px-4 py-3 font-mono text-[11px] text-slate-400 max-w-xs truncate">
                          {JSON.stringify(row.summary || {})}
                        </td>
                        <td class="px-4 py-3 text-slate-400 text-[11px] whitespace-nowrap">
                          {row.created_at ? row.created_at.substring(0, 10) : '-'}
                        </td>
                        <td class="px-4 py-3 text-right whitespace-nowrap">
                          {#if row.output_reference}
                            <a
                              href={`/api/projects/${project.id}/enhancements/${row.id}/download`}
                              class="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-white transition-colors"
                            >
                              <Download class="w-3 h-3" />
                              <span>Download</span>
                            </a>
                          {/if}
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
      <div class="px-6 py-3 border-t border-slate-800 bg-slate-950/60 flex justify-end">
        <button
          type="button"
          on:click={onClose}
          class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}

