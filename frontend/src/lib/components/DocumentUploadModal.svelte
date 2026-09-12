<script lang="ts">
  import { FileText } from "lucide-svelte";
  import Modal from "./Modal.svelte";
  import { Select, Switch } from "./ui";
  import { documentsApi } from "../api";
  import { authState } from "../auth.svelte";
  import { DOCUMENT_TYPES } from "../types";
  import type { DocumentItem, DocumentType, ParsingEngineInstance } from "../types";

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
  let uploadParser = $state<"auto" | "unstructured" | "light">("auto");
  let uploadInstance = $state("");
  let generateDoclangOnUpload = $state(true);
  let isUploading = $state(false);
  let uploadError = $state("");

  let isDoclangSelected = $derived(
    uploadFile ? /\.(doclang|dclg|dclx)$/i.test(uploadFile.name) : false
  );
  let isPdfSelected = $derived(uploadFile ? /\.pdf$/i.test(uploadFile.name) : false);

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

  const parserSelectOptions = $derived([
    { value: "auto", label: "Auto (configured engine, falls back to local)" },
    {
      value: "unstructured",
      label: `Force configured engine only${
        parsingEngines.length === 0
          ? " (no engine configured)"
          : " (best quality, slower, uploads file)"
      }`,
      disabled: parsingEngines.length === 0,
    },
    { value: "light", label: "Light local extraction only (instant, no upload)" },
  ]);

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
    uploadParser = "auto";
    uploadInstance = "";
    generateDoclangOnUpload = true;
    uploadLimitPages = false;
    uploadStartPage = "1";
    uploadEndPage = "";
    uploadError = "";
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
    try {
      const usePageRange = isPdfSelected && uploadLimitPages && !uploadPageRangeError;
      const created = await documentsApi.upload(uploadFile, uploadDocType, {
        parser: uploadParser,
        engine_instance: uploadParser === "light" ? undefined : uploadInstance || undefined,
        generate_doclang: generateDoclangOnUpload,
        organization_id: authState.activeOrganizationId,
        start_page: usePageRange ? parseInt(uploadStartPage, 10) : undefined,
        end_page: usePageRange ? parseInt(uploadEndPage, 10) : undefined,
      });
      resetState();
      onUploaded(created);
    } catch (err: any) {
      uploadError = err.message || "Failed to upload document.";
    } finally {
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
      <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300">
        {uploadError}
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
      <div class="space-y-1.5">
        <label for="upload-parser" class="block text-xs font-semibold text-fg-secondary">
          Parsing Engine
        </label>
        <Select
          ariaLabel="Parsing Engine"
          options={parserSelectOptions}
          value={uploadParser}
          onValueChange={(val) => (uploadParser = val as "auto" | "unstructured" | "light")}
          triggerClass="w-full bg-surface-canvas"
        />
      </div>

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

      {#if uploadParser !== "light" && parsingEngines.length > 0}
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
      <div class="rounded-xl border border-cyan-800/40 bg-cyan-950/20 px-3.5 py-2.5 text-xs text-cyan-300">
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
            if (target.files) uploadFile = target.files[0];
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
        <span class="text-fg-muted">{(uploadFile.size / 1024).toFixed(1)} KB</span>
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
        disabled={!uploadFile || isUploading || (isPdfSelected && uploadLimitPages && !!uploadPageRangeError)}
        onclick={handleUpload}
        class="rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
      >
        {isUploading ? "Extracting Text..." : "Upload & Extract"}
      </button>
    </div>
  {/snippet}
</Modal>
