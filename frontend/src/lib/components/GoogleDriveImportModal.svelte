<script lang="ts">
  import { CloudDownload, CheckCircle2, XCircle, Loader2 } from "lucide-svelte";
  import Modal from "./Modal.svelte";
  import { documentsApi } from "../api";
  import type { GoogleDriveImportResult } from "../types";
  import { DOCUMENT_TYPES } from "../types";

  interface Props {
    onClose: () => void;
    /** Called once the import batch finishes, with success/failure counts. */
    onComplete: (successCount: number, failCount: number) => void;
  }

  let { onClose, onComplete }: Props = $props();

  let urlsText = $state("");
  let docType = $state("Specification");
  let isImporting = $state(false);
  let results: GoogleDriveImportResult[] | null = $state(null);

  function parseUrls(): string[] {
    return urlsText
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
  }

  async function handleImport() {
    const urls = parseUrls();
    if (!urls.length) return;
    isImporting = true;
    results = null;
    try {
      const res = await documentsApi.importFromGoogleDrive({ urls, doc_type: docType });
      results = res.results;
      const successCount = results.filter((r) => r.ok).length;
      const failCount = results.length - successCount;
      onComplete(successCount, failCount);
    } catch (err: any) {
      results = parseUrls().map((url) => ({
        url,
        ok: false,
        error: err?.message || "Import request failed.",
      }));
    } finally {
      isImporting = false;
    }
  }
</script>

<Modal isOpen={true} title="Import from Google Drive" icon={CloudDownload} maxWidth="max-w-xl" {onClose}>
  <p class="text-slate-400">
    Paste one or more Google Drive share links (one per line). Each file must be shared
    <span class="font-semibold text-slate-300">"Anyone with the link"</span> — a private file will fail
    with a clear error below rather than aborting the whole batch.
  </p>

  <div class="space-y-1.5">
    <label for="drive-urls" class="text-xs font-semibold text-slate-300">Drive links or file IDs</label>
    <textarea
      id="drive-urls"
      bind:value={urlsText}
      rows="5"
      placeholder="https://drive.google.com/file/d/.../view?usp=sharing"
      class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-100 placeholder:text-slate-600 focus:border-accent focus:outline-none"
    ></textarea>
  </div>

  <div class="space-y-1.5">
    <label for="drive-doc-type" class="text-xs font-semibold text-slate-300">Document type</label>
    <select
      id="drive-doc-type"
      bind:value={docType}
      class="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100 focus:border-accent focus:outline-none"
    >
      {#each DOCUMENT_TYPES as type (type)}
        <option value={type}>{type}</option>
      {/each}
    </select>
  </div>

  {#if results}
    <div class="space-y-1.5 rounded-lg border border-slate-800 bg-slate-950/60 p-3">
      {#each results as result (result.url)}
        <div class="flex items-start gap-2 text-xs">
          {#if result.ok}
            <CheckCircle2 class="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
          {:else}
            <XCircle class="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" />
          {/if}
          <div class="min-w-0">
            <p class="truncate text-slate-300">{result.document?.filename || result.url}</p>
            {#if !result.ok}
              <p class="text-red-400">{result.error}</p>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}

  {#snippet footer()}
    <button
      type="button"
      onclick={onClose}
      class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 hover:bg-slate-700"
    >
      Close
    </button>
    <button
      type="button"
      disabled={!parseUrls().length || isImporting}
      onclick={handleImport}
      class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
    >
      {#if isImporting}
        <Loader2 class="h-3.5 w-3.5 animate-spin" />
      {/if}
      <span>{isImporting ? "Importing…" : "Import"}</span>
    </button>
  {/snippet}
</Modal>
