<script lang="ts">
  import { onDestroy } from "svelte";
  import { FileText, CheckCircle2 } from "lucide-svelte";
  import Modal from "./Modal.svelte";
  import { Select } from "./ui";
  import { documentsApi } from "../api";
  import type { ApiError } from "../api";
  import { authState } from "../auth.svelte";
  import { DOCUMENT_TYPES } from "../types";
  import type { DocumentItem, ParsingEngineInstance } from "../types";
  import { buildIssueLog, copyToClipboard, toErrorLogEntry, type ErrorLogEntry } from "../utils/errorLog";

  interface Props {
    isOpen: boolean;
    parsingEngines?: ParsingEngineInstance[];
    onClose: () => void;
    onUploaded: (doc: DocumentItem) => void;
  }

  let {
    isOpen,
    onClose,
    onUploaded,
  }: Props = $props();

  let uploadFile: File | null = $state(null);
  let uploadDocType = $state<string>("Specification");
  let isUploading = $state(false);
  let uploadError = $state("");
  let uploadErrorLog: ErrorLogEntry[] = $state([]);
  let uploadErrorLogCopied = $state(false);
  let uploadAbortController: AbortController | null = null;

  onDestroy(() => {
    uploadAbortController?.abort();
  });

  let isDoclangSelected = $derived(
    uploadFile ? /\.(doclang|dclg|dclx)$/i.test(uploadFile.name) : false
  );

  const docTypeOptions = DOCUMENT_TYPES.map((type) => ({
    value: type,
    label: type,
  }));

  function resetState() {
    uploadFile = null;
    uploadDocType = "Specification";
    uploadError = "";
    uploadErrorLog = [];
    isUploading = false;
  }

  function handleClose() {
    resetState();
    onClose();
  }

  async function handleUpload() {
    if (!uploadFile) return;
    isUploading = true;
    uploadError = "";
    uploadErrorLog = [];
    uploadAbortController = new AbortController();
    try {
      const created = await documentsApi.upload(
        uploadFile,
        uploadDocType,
        {
          generate_doclang: false,
          organization_id: authState.activeOrganizationId,
        },
        uploadAbortController.signal,
      );
      resetState();
      onUploaded(created);
    } catch (err: any) {
      if (uploadAbortController?.signal.aborted) return;
      const apiErr = err as ApiError;
      uploadError = apiErr.isNetworkError
        ? "Couldn't reach the BIM-Guard server. Make sure the backend is running, then try again."
        : apiErr.message || "Failed to upload document.";
      uploadErrorLog = [toErrorLogEntry(err, uploadFile.name)];
    } finally {
      uploadAbortController = null;
      isUploading = false;
    }
  }
</script>

<Modal
  {isOpen}
  title="Upload Document"
  maxWidth="max-w-xl"
  onClose={handleClose}
>
  <div class="space-y-4">
    {#if uploadError}
      <div class="space-y-2 rounded-xl border border-critical-border bg-critical-bg p-3 text-xs text-critical">
        <p class="font-medium">{uploadError}</p>
        {#if uploadErrorLog.length > 0}
          <button
            type="button"
            onclick={async () => {
              const ok = await copyToClipboard(
                buildIssueLog("Document Upload Error Log", {}, uploadErrorLog),
              );
              if (ok) {
                uploadErrorLogCopied = true;
                setTimeout(() => (uploadErrorLogCopied = false), 2000);
              }
            }}
            class="rounded-lg border border-critical-border px-2.5 py-1 text-caption font-semibold text-critical transition-colors hover:bg-surface-hover"
          >
            {uploadErrorLogCopied ? "Copied!" : "Copy issue log"}
          </button>
        {/if}
      </div>
    {/if}

    <div class="space-y-1.5">
      <label for="upload-doc-type" class="block text-xs font-semibold text-fg-secondary">
        Document Type
      </label>
      <Select
        ariaLabel="Document Type"
        options={docTypeOptions}
        bind:value={uploadDocType}
        triggerClass="w-full bg-surface-canvas"
      />
      <p class="text-caption text-fg-muted">
        Classifies the document for compliance auditing and rule extraction.
      </p>
    </div>

    <div
      class="rounded-xl border-2 border-dashed border-border-interactive bg-surface-canvas/40 p-6 text-center transition-colors hover:border-accent"
    >
      <FileText class="mx-auto mb-2 h-8 w-8 text-fg-muted" />
      <p class="mb-3 text-xs text-fg-muted">
        Upload PDF, Word, Excel, PowerPoint, HTML, AsciiDoc, Markdown, CSV, TXT, an image
        (PNG/JPEG/TIFF/BMP/WEBP), or pre-converted DocLang files (.dclg, .dclx, .doclang)
      </p>
      <label
        class="inline-flex cursor-pointer items-center gap-1.5 rounded-xl bg-surface-overlay px-4 py-2 text-xs font-semibold text-fg-primary transition-colors hover:bg-surface-hover"
      >
        <span>Choose File</span>
        <input
          type="file"
          accept=".pdf,.docx,.xlsx,.pptx,.md,.markdown,.adoc,.asciidoc,.html,.htm,.csv,.txt,.png,.jpg,.jpeg,.tiff,.tif,.bmp,.webp,.doclang,.dclg,.dclx"
          onchange={(e) => {
            const target = e.target as HTMLInputElement;
            if (target.files && target.files[0]) {
              uploadFile = target.files[0];
              uploadError = "";
              uploadErrorLog = [];
            }
          }}
          class="hidden"
        />
      </label>
    </div>

    {#if uploadFile}
      <div
        class="flex items-center justify-between rounded-xl border border-border-default bg-surface-canvas p-3 text-xs"
      >
        <span class="truncate font-medium text-fg-primary">{uploadFile.name}</span>
        <span class="text-fg-muted">
          {uploadFile.size > 1024 * 1024
            ? `${(uploadFile.size / (1024 * 1024)).toFixed(1)} MB`
            : `${(uploadFile.size / 1024).toFixed(1)} KB`}
        </span>
      </div>

      {#if isDoclangSelected}
        <div class="flex items-start gap-2 rounded-xl border border-info-border bg-info-bg px-3.5 py-2.5 text-xs text-info">
          <CheckCircle2 class="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            Pre-converted DocLang XML file detected — it will be ingested immediately as DocLang Ready with no parsing required.
          </p>
        </div>
      {:else}
        <div class="rounded-xl border border-border-subtle bg-surface-canvas/60 p-3 text-xs text-fg-secondary">
          <p class="font-medium text-fg-primary">Storage & Conversion Workflow</p>
          <p class="mt-1 text-caption text-fg-muted">
            The document will be saved directly to your repository. You can convert it to DocLang XML at any time from the documents table, where you can select parsing engines or extract specific page ranges for large building codes.
          </p>
        </div>
      {/if}
    {/if}
  </div>

  {#snippet footer()}
    <div class="flex items-center justify-end gap-2">
      <button
        type="button"
        onclick={handleClose}
        class="rounded-xl bg-surface-overlay px-4 py-2 text-xs font-semibold text-fg-primary hover:bg-surface-hover"
      >
        Cancel
      </button>
      <button
        type="button"
        disabled={!uploadFile || isUploading}
        onclick={handleUpload}
        class="rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
      >
        {isUploading ? "Uploading..." : "Upload Document"}
      </button>
    </div>
  {/snippet}
</Modal>
