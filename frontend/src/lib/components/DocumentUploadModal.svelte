<script lang="ts">
  import { onDestroy } from "svelte";
  import { FileText, Settings2 } from "lucide-svelte";
  import Modal from "./Modal.svelte";
  import { Select, Switch } from "./ui";
  import { documentsApi } from "../api";
  import type { ApiError } from "../api";
  import { authState } from "../auth.svelte";
  import { DOCUMENT_TYPES } from "../types";
  import type { DocumentItem, DocumentType, ParsingEngineInstance } from "../types";
  import { buildIssueLog, copyToClipboard, toErrorLogEntry, type ErrorLogEntry } from "../utils/errorLog";

  interface Props {
    isOpen: boolean;
    parsingEngines: ParsingEngineInstance[];
    onClose: () => void;
    onUploaded: (doc: DocumentItem) => void;
  }

  let {
    isOpen,
    parsingEngines,
    onClose,
    onUploaded,
  }: Props = $props();

  let uploadFile: File | null = $state(null);
  let uploadDocType = $state<string>("Specification");
  let uploadInstance = $state("");
  let generateDoclangOnUpload = $state(true);
  let isUploading = $state(false);
  let uploadError = $state("");
  let uploadErrorLog: ErrorLogEntry[] = $state([]);
  let uploadErrorLogCopied = $state(false);
  let noParsingEngineConfigured = $state(false);
  let parsingEngineFailed = $state(false);
  let isTimeout = $state(false);
  // Cancels the in-flight upload if the component unmounts mid-upload
  // (navigating away) -- otherwise the fetch keeps running as an orphaned
  // promise with no one left to report its result to.
  let uploadAbortController: AbortController | null = null;

  onDestroy(() => {
    uploadAbortController?.abort();
  });

  // Inline role check for now (matches the pattern in TopHeader.svelte /
  // UserMenu.svelte / DashboardView.svelte) -- swap for a proper
  // Action.MANAGE_PARSING_ENGINES permission lookup once a frontend helper
  // for the permission matrix exists.
  let canManageParsing = $derived(
    authState.isSuperadmin ||
      authState.activeOrganization?.role === "owner" ||
      authState.activeOrganization?.role === "admin"
  );

  let isDoclangSelected = $derived(
    uploadFile ? /\.(doclang|dclg|dclx)$/i.test(uploadFile.name) : false
  );
  let isPdfSelected = $derived(uploadFile ? /\.pdf$/i.test(uploadFile.name) : false);
  let isLargePdf = $derived(isPdfSelected && (uploadFile?.size ?? 0) > 2 * 1024 * 1024);

  let uploadLimitPages = $state(false);
  let uploadStartPage = $state("1");
  let uploadEndPage = $state("");
  let uploadPageRangeError = $derived.by(() => {
    if (!uploadLimitPages) return "";
    const start = parseInt(uploadStartPage, 10);
    const end = parseInt(uploadEndPage, 10);
    if (!uploadStartPage.trim() || !uploadEndPage.trim() || Number.isNaN(start) || Number.isNaN(end)) {
      return "Enter both a start and end page.";
    }
    if (start < 1) return "Start page must be 1 or greater.";
    if (end < start) return "End page must be greater than or equal to the start page.";
    return "";
  });

  const docTypeOptions = DOCUMENT_TYPES.map((type) => ({
    value: type,
    label: type,
  }));

  const instanceOptions = $derived([
    { value: "", label: "Default" },
    ...parsingEngines.map((engine) => ({
      value: engine.name,
      label: `${engine.name} (${engine.kind}${engine.is_default ? ", default" : ""}${
        !engine.is_enabled ? ", disabled" : ""
      })`,
      disabled: !engine.is_enabled,
    })),
  ]);

  function resetState() {
    uploadFile = null;
    uploadDocType = "Specification";
    uploadInstance = "";
    generateDoclangOnUpload = true;
    uploadLimitPages = false;
    uploadStartPage = "1";
    uploadEndPage = "";
    uploadError = "";
    uploadErrorLog = [];
    noParsingEngineConfigured = false;
    parsingEngineFailed = false;
    isTimeout = false;
    isUploading = false;
  }

  function handleClose() {
    resetState();
    onClose();
  }

  async function handleUpload() {
    if (!uploadFile) return;
    if (isPdfSelected && uploadLimitPages && uploadPageRangeError) return;
    isUploading = true;
    uploadError = "";
    uploadErrorLog = [];
    noParsingEngineConfigured = false;
    parsingEngineFailed = false;
    isTimeout = false;
    uploadAbortController = new AbortController();
    try {
      const usePageRange = isPdfSelected && uploadLimitPages && !uploadPageRangeError;
      const created = await documentsApi.upload(
        uploadFile,
        uploadDocType,
        {
          engine_instance: uploadInstance || undefined,
          generate_doclang: generateDoclangOnUpload,
          organization_id: authState.activeOrganizationId,
          start_page: usePageRange ? parseInt(uploadStartPage, 10) : undefined,
          end_page: usePageRange ? parseInt(uploadEndPage, 10) : undefined,
        },
        uploadAbortController.signal,
      );
      resetState();
      onUploaded(created);
    } catch (err: any) {
      if (uploadAbortController?.signal.aborted) return;
      const apiErr = err as ApiError;
      const isTimeoutErr =
        apiErr.status === 524 ||
        apiErr.status === 504 ||
        apiErr.message?.includes("524") ||
        apiErr.message?.toLowerCase().includes("timeout");
      isTimeout = isTimeoutErr;
      if (isTimeoutErr) {
        generateDoclangOnUpload = false;
      }
      // apiFetch (lib/api.ts) already normalizes a fetch()-level failure
      // (offline, unreachable backend) into this same ApiError shape with
      // isNetworkError set, instead of a raw browser-specific TypeError.
      uploadError = apiErr.isNetworkError
        ? "Couldn't reach the BIM-Guard server. Make sure the backend is running, then try again."
        : isTimeoutErr
          ? "Upload timed out during inline DocLang conversion (HTTP 524). Converting large documents can exceed the network proxy limit."
          : apiErr.message || "Failed to upload document.";
      noParsingEngineConfigured = apiErr.status === 422;
      parsingEngineFailed = apiErr.status === 502;
      uploadErrorLog = [toErrorLogEntry(err, uploadFile.name)];
    } finally {
      uploadAbortController = null;
      isUploading = false;
    }
  }
</script>

<Modal
  {isOpen}
  title="Add Document"
  maxWidth="max-w-2xl"
  onClose={handleClose}
>
  <div class="space-y-4">
    {#if uploadError}
      <div class="space-y-2 rounded-xl border border-critical-border bg-critical-bg p-3 text-xs text-critical">
        <p class="font-medium">{uploadError}</p>
        {#if isTimeout}
          <div class="space-y-1 text-fg-secondary">
            <p>
              “Convert to DocLang now” has been automatically disabled below so you can upload and store the file immediately. Click <strong>Upload Document</strong> to proceed.
            </p>
            {#if isPdfSelected}
              <p class="text-caption text-fg-muted">
                You can also use “Limit to a page range” below to extract only the relevant chapters.
              </p>
            {/if}
          </div>
        {:else if parsingEngineFailed && generateDoclangOnUpload}
          <p class="text-fg-secondary">
            You can also turn off “Convert to DocLang now” to store the file and convert it later.
          </p>
        {/if}
        {#if noParsingEngineConfigured && canManageParsing}
          <a
            href={`#/external-providers?tab=parsing${authState.activeOrganizationId ? `&org=${authState.activeOrganizationId}` : ""}`}
            class="inline-flex items-center gap-1.5 font-semibold text-accent underline hover:text-accent-hover"
          >
            <Settings2 class="h-3.5 w-3.5" />
            Configure a parsing engine
          </a>
        {/if}
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
            class="rounded-lg border border-border-interactive px-2.5 py-1 text-caption font-semibold text-fg-primary transition-colors hover:bg-surface-hover"
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
        Classifies the document for filtering — used later in Rule Extraction Studio.
      </p>
    </div>

    {#if !isDoclangSelected}
      <div class="flex items-center justify-between rounded-xl border border-border-default bg-surface-canvas/60 px-3.5 py-2.5">
        <div>
          <label for="upload-generate-doclang" class="block text-xs font-semibold text-fg-secondary">
            Convert to DocLang now
          </label>
          <p class="text-caption text-fg-muted">
            When off, the file is stored but DocLang is generated later from the documents table.
          </p>
        </div>
        <Switch
          id="upload-generate-doclang"
          ariaLabel="Convert to DocLang now"
          bind:checked={generateDoclangOnUpload}
        />
      </div>

      {#if isPdfSelected}
        <div class="rounded-xl border border-border-default bg-surface-canvas/60 px-3.5 py-2.5">
          <div class="flex items-center justify-between">
            <div>
              <label for="upload-limit-pages" class="block text-xs font-semibold text-fg-secondary">
                Limit to a page range
              </label>
              <p class="text-caption text-fg-muted">
                Only these pages are stored and parsed — the rest of the PDF is discarded.
              </p>
            </div>
            <Switch
              id="upload-limit-pages"
              ariaLabel="Limit to a page range"
              bind:checked={uploadLimitPages}
            />
          </div>
          {#if uploadLimitPages}
            <div class="mt-3 flex items-center gap-2">
              <label class="flex-1 space-y-1">
                <span class="block text-caption text-fg-muted">Start page</span>
                <input
                  type="text"
                  inputmode="numeric"
                  bind:value={uploadStartPage}
                  class="w-full rounded-lg border border-border-default bg-surface-canvas px-3 py-1.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
                />
              </label>
              <span class="mt-4 text-fg-muted">–</span>
              <label class="flex-1 space-y-1">
                <span class="block text-caption text-fg-muted">End page</span>
                <input
                  type="text"
                  inputmode="numeric"
                  bind:value={uploadEndPage}
                  class="w-full rounded-lg border border-border-default bg-surface-canvas px-3 py-1.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
                />
              </label>
            </div>
            {#if uploadPageRangeError}
              <p class="mt-1.5 text-caption text-rose-400">{uploadPageRangeError}</p>
            {/if}
          {/if}
        </div>
      {/if}

      {#if parsingEngines.length > 0}
        <div class="space-y-1.5">
          <label for="upload-instance" class="block text-xs font-semibold text-fg-secondary">
            Instance
          </label>
          <Select
            ariaLabel="Instance"
            options={instanceOptions}
            bind:value={uploadInstance}
            triggerClass="w-full bg-surface-canvas"
          />
          <p class="text-caption text-fg-muted">
            Which configured parsing engine to use — see Settings &gt; Parsing Engines.
          </p>
        </div>
      {/if}
    {:else}
      <div class="rounded-xl border border-info-border bg-info-bg px-3.5 py-2.5 text-xs text-info">
        This is a pre-converted DocLang XML file — it's stored as-is, with no parsing engine or
        conversion step needed.
      </div>
    {/if}

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
              const file = target.files[0];
              uploadFile = file;
              uploadError = "";
              uploadErrorLog = [];
              isTimeout = false;
              if (file.name.toLowerCase().endsWith(".pdf") && file.size > 2 * 1024 * 1024) {
                generateDoclangOnUpload = false;
              }
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
      {#if isLargePdf}
        <div class="rounded-xl border border-warning-border bg-warning-bg p-2.5 text-xs text-warning">
          <p class="font-medium">Large document detected ({(uploadFile.size / (1024 * 1024)).toFixed(1)} MB)</p>
          <p class="text-caption text-fg-secondary mt-0.5">
            Converting entire building codes or multi-page specifications inline can exceed the 100-second network proxy limit (HTTP 524). “Convert to DocLang now” has been turned off by default so the file uploads immediately; you can convert it later from the documents table or specify a page range.
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
        disabled={!uploadFile || isUploading || (isPdfSelected && uploadLimitPages && !!uploadPageRangeError)}
        onclick={handleUpload}
        class="rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
      >
        {isUploading
          ? generateDoclangOnUpload
            ? "Extracting Text..."
            : "Uploading..."
          : generateDoclangOnUpload
            ? "Upload & Extract"
            : "Upload Document"}
      </button>
    </div>
  {/snippet}
</Modal>
