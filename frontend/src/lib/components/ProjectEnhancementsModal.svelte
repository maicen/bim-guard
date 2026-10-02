<script lang="ts">
  import { run } from "svelte/legacy";

  import { onMount } from "svelte";
  import {
    Sparkles,
    Download,
    CheckCircle2,
    ShieldAlert,
    Eye,
    UploadCloud,
  } from "lucide-svelte";
  import { lineageApi } from "../api";
  import { withAuthToken } from "../authToken";
  import type { Project, ModelLineageRecord } from "../types";
  import Alert from "./Alert.svelte";
  import Modal from "./Modal.svelte";
  import { toErrorLogEntry, type ErrorLogEntry } from "../utils/errorLog";

  interface Props {
    isOpen?: boolean;
    project?: Project | null;
    onClose: () => void;
    onAttachModel?: () => void;
  }

  let { isOpen = false, project = null, onClose, onAttachModel }: Props = $props();

  let isRunning = $state(false);
  let message = $state("");
  let messageType: "success" | "error" = $state("success");
  let messageErrorLog: ErrorLogEntry[] = $state([]);
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
    messageErrorLog = [];

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
      messageErrorLog = [toErrorLogEntry(err, `project #${project.id}`)];
    } finally {
      isRunning = false;
    }
  }
</script>

<Modal
  isOpen={isOpen && !!project}
  title={`Quality Improvements — ${project?.name ?? ""}`}
  subtitle="Generate and persist an improved IFC version without mutating the original source."
  icon={Sparkles}
  maxWidth="max-w-3xl"
  closeOnBackdrop={false}
  {onClose}
>
  {#if project}
    <div class="space-y-6">
      {#if message && messageType === "error"}
        <Alert
          type="error"
          message={message}
          errors={messageErrorLog}
          logTitle="Quality Improvement Error Log"
        />
      {:else if message}
        <div
          class="flex items-center gap-2 rounded-xl border border-success-border bg-success-bg p-3.5 text-xs text-success"
        >
          <CheckCircle2 class="h-4 w-4 shrink-0 text-success" />
          <span>{message}</span>
        </div>
      {/if}

      <!-- Run form -->
      <div class="space-y-3 rounded-2xl border border-border-default bg-surface-canvas/60 p-5">
        <h3 class="text-sm font-semibold text-fg-primary">Execute IFC Quality Improvement</h3>
        <p class="text-xs text-fg-muted">
          Triggers an automated quality improvement pass. Normalizes geometric properties,
          property sets, and element GUID linkages without mutating original project IFC files.
        </p>

        <div class="flex items-center gap-3 pt-1">
          <button
            type="button"
            disabled={isRunning || !project.ifc_file_path}
            onclick={handleRunEnhancement}
            class="flex shrink-0 items-center justify-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-xs font-semibold text-white shadow-xs shadow-accent/20 transition-all hover:scale-[1.02] hover:bg-accent-hover disabled:opacity-50 disabled:hover:scale-100"
          >
            <Sparkles class="h-4 w-4 {isRunning ? 'animate-spin' : ''}" />
            <span
              >{isRunning ? "Processing Model Quality Improvements..." : "Run Improvements"}</span
            >
          </button>

          {#if !project.ifc_file_path}
            <div class="flex flex-wrap items-center gap-2 text-caption text-warning">
              <ShieldAlert class="h-3.5 w-3.5 shrink-0" />
              <span>Cannot enhance: this project does not have an attached IFC file.</span>
              {#if onAttachModel}
                <button
                  type="button"
                  onclick={onAttachModel}
                  class="inline-flex items-center gap-1 rounded-lg border border-accent/40 bg-accent/10 px-2.5 py-1 text-xs font-medium text-accent transition-colors hover:bg-accent/20"
                >
                  <UploadCloud class="h-3.5 w-3.5" />
                  Attach Model
                </button>
              {/if}
            </div>
          {/if}
        </div>
      </div>

      <!-- Lineage History Table -->
      <div class="space-y-3">
        <h3 class="text-sm font-semibold text-fg-primary">Persisted Improvement History</h3>

        <div class="overflow-hidden rounded-2xl border border-border-default bg-surface-canvas/40">
          {#if isLoadingHistory}
            <div class="p-8 text-center text-xs text-fg-muted">Loading version history...</div>
          {:else if history.length === 0}
            <div class="p-8 text-center text-xs text-fg-muted">
              No improved versions generated yet for this project.
            </div>
          {:else}
            <div class="overflow-x-auto">
              <table aria-label="Improved model versions" class="w-full text-left text-xs text-fg-secondary">
                <thead
                  class="border-b border-border-default bg-surface-canvas text-caption font-semibold uppercase tracking-wider text-fg-muted"
                >
                  <tr>
                    <th scope="col" class="px-4 py-3">Source Ver</th>
                    <th scope="col" class="px-4 py-3">Generated Ver</th>
                    <th scope="col" class="px-4 py-3">Status</th>
                    <th scope="col" class="px-4 py-3">Summary</th>
                    <th scope="col" class="px-4 py-3">Created</th>
                    <th scope="col" class="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-border-subtle">
                  {#each history as row (row.id)}
                    <tr class="transition-colors hover:bg-surface-hover">
                      <td class="px-4 py-3 font-mono text-fg-muted">v{row.source_version}</td>
                      <td class="px-4 py-3 font-mono font-semibold text-accent"
                        >v{row.version}</td
                      >
                      <td class="px-4 py-3">
                        <span
                          class="inline-block rounded-md border border-success-border bg-success-bg px-2 py-0.5 text-micro font-semibold text-success"
                        >
                          {row.status}
                        </span>
                      </td>
                      <td
                        class="max-w-xs truncate px-4 py-3 font-mono text-caption text-fg-muted"
                      >
                        {JSON.stringify(row.summary || {})}
                      </td>
                      <td class="whitespace-nowrap px-4 py-3 text-caption text-fg-muted">
                        {row.created_at ? row.created_at.substring(0, 10) : "-"}
                      </td>
                      <td class="whitespace-nowrap px-4 py-3 text-right">
                        <div class="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onclick={() => (selectedVersionForView = row)}
                            class="rounded-lg bg-surface-overlay p-1.5 text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
                            title="Inspect version details"
                          >
                            <Eye class="h-3.5 w-3.5" />
                          </button>
                          {#if row.output_reference}
                            <a
                              href={withAuthToken(`/api/projects/${project.id}/enhancements/${row.id}/download`)}
                              class="inline-flex items-center gap-1 rounded-lg border border-accent/40 bg-accent/10 px-3 py-1 text-xs font-medium text-accent transition-colors hover:bg-accent/20"
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
  {/if}

  {#snippet footer()}
    <button
      type="button"
      onclick={onClose}
      class="rounded-xl bg-surface-overlay px-4 py-2 text-xs font-semibold text-fg-primary transition-colors hover:bg-surface-hover"
    >
      Close
    </button>
  {/snippet}
</Modal>

<Modal
  isOpen={selectedVersionForView !== null}
  title={`Lineage Version v${selectedVersionForView?.version ?? ""} Details`}
  icon={Sparkles}
  maxWidth="max-w-lg"
  closeOnBackdrop={false}
  onClose={() => (selectedVersionForView = null)}
>
  {#if selectedVersionForView}
    <div class="space-y-3 text-xs">
      <div
        class="grid grid-cols-2 gap-2 rounded-xl border border-border-default bg-surface-canvas p-3 font-mono"
      >
        <div>
          <span class="text-fg-muted">Source:</span>
          <span class="text-fg-secondary">v{selectedVersionForView.source_version}</span>
        </div>
        <div>
          <span class="text-fg-muted">Generated:</span>
          <span class="text-purple-300">v{selectedVersionForView.version}</span>
        </div>
        <div>
          <span class="text-fg-muted">Status:</span>
          <span class="text-emerald-400">{selectedVersionForView.status}</span>
        </div>
        <div>
          <span class="text-fg-muted">Created:</span>
          <span class="text-fg-muted">{selectedVersionForView.created_at?.substring(0, 10)}</span
          >
        </div>
      </div>

      <div>
        <span class="text-caption font-semibold uppercase tracking-wider text-fg-muted"
          >Modifications Summary</span
        >
        <pre
          class="mt-1 max-h-56 overflow-auto rounded-xl border border-border-default bg-surface-canvas p-3 font-mono text-caption text-fg-secondary">{JSON.stringify(
            selectedVersionForView.summary,
            null,
            2,
          )}</pre>
      </div>

      {#if selectedVersionForView.output_reference}
        <div class="truncate text-caption text-fg-muted">
          <span class="font-semibold text-fg-secondary">Storage Ref:</span>
          {selectedVersionForView.output_reference}
        </div>
      {/if}
    </div>
  {/if}

  {#snippet footer()}
    <button
      type="button"
      onclick={() => (selectedVersionForView = null)}
      class="rounded-xl bg-surface-overlay px-4 py-2 text-xs font-semibold text-fg-primary transition-colors hover:bg-surface-hover"
    >
      Close
    </button>
  {/snippet}
</Modal>
