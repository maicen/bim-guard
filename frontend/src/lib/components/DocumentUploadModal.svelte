<script lang="ts">
  import { onDestroy } from "svelte";
  import { FileText, CheckCircle2, X } from "lucide-svelte";
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
  let rawText = $state("");
  let docTitle = $state("");
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
    rawText = "";
    docTitle = "";
    uploadDocType = "Specification";
    uploadError = "";
    uploadErrorLog = [];
    isUploading = false;
  }

  function handleClose() {
    resetState();
    onClose();
  }

  function getPastedFilename(): string {
    const cleanTitle = docTitle.trim();
    if (cleanTitle) {
      let name = cleanTitle.replace(/[^a-zA-Z0-9_\-\.]+/g, "_").replace(/^_+|_+$/g, "");
      if (!name.toLowerCase().endsWith(".txt") && !name.toLowerCase().endsWith(".md")) {
        name += ".txt";
      }
      return name;
    }
    const firstLine = rawText.trim().split("\n")[0].trim().slice(0, 40);
    const candidate = firstLine.replace(/[^a-zA-Z0-9_\-\.]+/g, "_").replace(/^_+|_+$/g, "");
    if (candidate.length >= 3) {
      return `${candidate}.txt`;
    }
    return `specification_clauses_${new Date().toISOString().slice(0, 10)}.txt`;
  }

  async function handleUpload() {
    const fileToUpload =
      uploadFile ||
      (rawText.trim()
        ? new File([rawText.trim()], getPastedFilename(), {
            type: "text/plain;charset=utf-8",
          })
        : null);

    if (!fileToUpload) return;
    isUploading = true;
    uploadError = "";
    uploadErrorLog = [];
    uploadAbortController = new AbortController();
    try {
      const created = await documentsApi.upload(
        fileToUpload,
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
      uploadErrorLog = [toErrorLogEntry(err, fileToUpload.name)];
    } finally {
      uploadAbortController = null;
      isUploading = false;
    }
  }
</script>

<Modal
  {isOpen}
  title="Upload or Add Document"
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

    <!-- Option 1: File dropzone -->
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
              rawText = "";
              docTitle = "";
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
        <div class="flex items-center gap-2">
          <span class="text-fg-muted">
            {uploadFile.size > 1024 * 1024
              ? `${(uploadFile.size / (1024 * 1024)).toFixed(1)} MB`
              : `${(uploadFile.size / 1024).toFixed(1)} KB`}
          </span>
          <button
            type="button"
            onclick={() => { uploadFile = null; }}
            class="rounded p-1 text-fg-muted hover:text-fg-primary hover:bg-surface-hover"
            title="Remove selected file"
          >
            <X class="h-3.5 w-3.5" />
          </button>
        </div>
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

    <!-- Option 2: Paste Building Code / Specification Clauses Directly -->
    <div class="space-y-2">
      <label for="rule-raw-text" class="block text-xs font-bold uppercase tracking-wider text-fg-muted">
        Or Paste Building Code / Specification Clauses Directly:
      </label>
      <textarea
        id="rule-raw-text"
        bind:value={rawText}
        oninput={() => {
          if (rawText.trim()) {
            uploadFile = null;
          }
        }}
        rows="6"
        placeholder="e.g. Section 3.4.1: Exterior exit doors shall have a minimum clear width of 900 mm and fire protection rating of not less than 45 minutes..."
        class="w-full rounded-xl border border-border-default bg-surface-canvas p-3.5 font-mono text-xs leading-relaxed text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
      ></textarea>
    </div>

    {#if rawText.trim()}
      <div class="space-y-1.5">
        <label for="pasted-doc-title" class="block text-xs font-semibold text-fg-secondary">
          Document Title (optional)
        </label>
        <input
          id="pasted-doc-title"
          type="text"
          bind:value={docTitle}
          placeholder="e.g. SBC 201 Section 3.4 Egress Doors"
          class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
        />
        <p class="text-caption text-fg-muted">
          Pasted text will be ingested as a specification document ({rawText.trim().length} characters).
        </p>
      </div>
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
        disabled={(!uploadFile && !rawText.trim()) || isUploading}
        onclick={handleUpload}
        class="rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
      >
        {isUploading
          ? "Uploading..."
          : rawText.trim()
            ? "Add Document"
            : "Upload Document"}
      </button>
    </div>
  {/snippet}
</Modal>
