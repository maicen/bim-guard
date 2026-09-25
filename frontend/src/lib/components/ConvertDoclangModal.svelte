<script lang="ts">
  import { Sparkles, FileText, Settings2, CheckCircle2, AlertTriangle } from "lucide-svelte";
  import Modal from "./Modal.svelte";
  import { Select, Switch } from "./ui";
  import { documentsApi } from "../api";
  import type { ApiError } from "../api";
  import { authState } from "../auth.svelte";
  import type { DocumentItem, DocumentDetail, ParsingEngineInstance } from "../types";
  import { buildIssueLog, copyToClipboard, toErrorLogEntry, type ErrorLogEntry } from "../utils/errorLog";

  interface Props {
    isOpen: boolean;
    document: DocumentItem | null;
    parsingEngines: ParsingEngineInstance[];
    onClose: () => void;
    onConverted: (doc: DocumentDetail) => void;
  }

  let {
    isOpen,
    document: docItem,
    parsingEngines,
    onClose,
    onConverted,
  }: Props = $props();

  let selectedEngine = $state("");
  let limitPages = $state(false);
  let startPage = $state("1");
  let endPage = $state("");
  let isConverting = $state(false);
  let convertError = $state("");
  let convertErrorLog: ErrorLogEntry[] = $state([]);
  let convertErrorLogCopied = $state(false);
  let noParsingEngineConfigured = $state(false);
  let parsingEngineFailed = $state(false);

  let isPdf = $derived(docItem ? /\.pdf$/i.test(docItem.filename) : false);

  let pageRangeError = $derived.by(() => {
    if (!limitPages) return "";
    const start = parseInt(startPage, 10);
    const end = parseInt(endPage, 10);
    if (!startPage.trim() || !endPage.trim() || Number.isNaN(start) || Number.isNaN(end)) {
      return "Enter both a start and end page.";
    }
    if (start < 1) return "Start page must be 1 or greater.";
    if (end < start) return "End page must be greater than or equal to the start page.";
    return "";
  });

  let canManageParsing = $derived(
    authState.isSuperadmin ||
      authState.activeOrganization?.role === "owner" ||
      authState.activeOrganization?.role === "admin"
  );

  const instanceOptions = $derived([
    { value: "", label: "Default Parsing Engine" },
    ...parsingEngines.map((engine) => ({
      value: engine.name,
      label: `${engine.name} (${engine.kind}${engine.is_default ? ", default" : ""}${
        !engine.is_enabled ? ", disabled" : ""
      })`,
      disabled: !engine.is_enabled,
    })),
  ]);

  function resetState() {
    selectedEngine = "";
    limitPages = false;
    startPage = "1";
    endPage = "";
    convertError = "";
    convertErrorLog = [];
    noParsingEngineConfigured = false;
    parsingEngineFailed = false;
    isConverting = false;
  }

  function handleClose() {
    resetState();
    onClose();
  }

  async function handleConvert() {
    if (!docItem) return;
    if (isPdf && limitPages && pageRangeError) return;

    isConverting = true;
    convertError = "";
    convertErrorLog = [];
    noParsingEngineConfigured = false;
    parsingEngineFailed = false;

    try {
      const usePageRange = isPdf && limitPages && !pageRangeError;
      const updated = await documentsApi.generateDoclang(docItem.id, {
        parser: "auto",
        engine_instance: selectedEngine || undefined,
        start_page: usePageRange ? parseInt(startPage, 10) : undefined,
        end_page: usePageRange ? parseInt(endPage, 10) : undefined,
      });
      resetState();
      onConverted(updated);
    } catch (err: any) {
      const apiErr = err as ApiError;
      convertError = apiErr.isNetworkError
        ? "Couldn't reach the BIM-Guard server. Make sure the backend is running, then try again."
        : apiErr.message || "Failed to convert document to DocLang.";
      noParsingEngineConfigured = apiErr.status === 422;
      parsingEngineFailed = apiErr.status === 502;
      convertErrorLog = [toErrorLogEntry(err, docItem.filename)];
    } finally {
      isConverting = false;
    }
  }
</script>

<Modal
  {isOpen}
  title="Convert to DocLang XML"
  maxWidth="max-w-xl"
  onClose={handleClose}
>
  <div class="space-y-4">
    {#if convertError}
      <div class="space-y-2 rounded-xl border border-critical-border bg-critical-bg p-3 text-xs text-critical">
        <p class="font-medium">{convertError}</p>
        {#if noParsingEngineConfigured && canManageParsing}
          <a
            href={`#/external-providers?tab=parsing${authState.activeOrganizationId ? `&org=${authState.activeOrganizationId}` : ""}`}
            class="inline-flex items-center gap-1.5 font-semibold text-accent underline hover:text-accent-hover"
          >
            <Settings2 class="h-3.5 w-3.5" />
            Configure a parsing engine
          </a>
        {/if}
        {#if convertErrorLog.length > 0}
          <button
            type="button"
            onclick={async () => {
              const ok = await copyToClipboard(
                buildIssueLog("DocLang Conversion Error Log", {}, convertErrorLog),
              );
              if (ok) {
                convertErrorLogCopied = true;
                setTimeout(() => (convertErrorLogCopied = false), 2000);
              }
            }}
            class="rounded-lg border border-critical-border px-2.5 py-1 text-caption font-semibold text-critical transition-colors hover:bg-surface-hover"
          >
            {convertErrorLogCopied ? "Copied!" : "Copy issue log"}
          </button>
        {/if}
      </div>
    {/if}

    {#if docItem}
      <!-- Document summary banner -->
      <div class="flex items-center justify-between rounded-xl border border-border-default bg-surface-canvas p-3 text-xs">
        <div class="flex items-center gap-2.5 truncate">
          <FileText class="h-5 w-5 shrink-0 text-accent" />
          <div class="truncate">
            <p class="truncate font-semibold text-fg-primary">{docItem.filename}</p>
            <p class="text-caption text-fg-muted">
              {docItem.doc_type || "Specification"} • #{docItem.id}
            </p>
          </div>
        </div>
        {#if docItem.has_doclang}
          <span class="inline-flex shrink-0 items-center gap-1 rounded-full border border-success-border bg-success-bg px-2.5 py-0.5 text-caption font-medium text-success">
            <CheckCircle2 class="h-3 w-3" />
            DocLang Ready
          </span>
        {:else}
          <span class="inline-flex shrink-0 items-center gap-1 rounded-full border border-warning-border/60 bg-warning-bg/40 px-2.5 py-0.5 text-caption font-medium text-warning">
            Not Converted
          </span>
        {/if}
      </div>

      {#if docItem.has_doclang}
        <div class="flex items-start gap-2 rounded-xl border border-border-default bg-surface-canvas/60 p-3 text-xs text-fg-secondary">
          <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <p>
            This document already has DocLang XML. Re-converting will re-parse the document and overwrite the existing DocLang structure and pages.
          </p>
        </div>
      {/if}

      <!-- Parsing engine selector -->
      <div class="space-y-1.5">
        <label for="convert-engine" class="block text-xs font-semibold text-fg-secondary">
          Parsing Engine Instance
        </label>
        <Select
          ariaLabel="Parsing Engine Instance"
          options={instanceOptions}
          bind:value={selectedEngine}
          triggerClass="w-full bg-surface-canvas"
        />
        <p class="text-caption text-fg-muted">
          Docling engine used to parse clauses, headings, and tables into DocLang XML.
        </p>
      </div>

      <!-- Page range limiter for PDFs -->
      {#if isPdf}
        <div class="rounded-xl border border-border-default bg-surface-canvas/60 px-3.5 py-2.5">
          <div class="flex items-center justify-between">
            <div>
              <label for="convert-limit-pages" class="block text-xs font-semibold text-fg-secondary">
                Limit to a page range
              </label>
              <p class="text-caption text-fg-muted">
                Extract only specific pages (recommended for 100+ page building codes to avoid timeouts).
              </p>
            </div>
            <Switch
              id="convert-limit-pages"
              ariaLabel="Limit to a page range"
              bind:checked={limitPages}
            />
          </div>
          {#if limitPages}
            <div class="mt-3 flex items-center gap-2">
              <label class="flex-1 space-y-1">
                <span class="block text-caption text-fg-muted">Start page</span>
                <input
                  type="text"
                  inputmode="numeric"
                  bind:value={startPage}
                  class="w-full rounded-lg border border-border-default bg-surface-canvas px-3 py-1.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
                />
              </label>
              <span class="mt-4 text-fg-muted">–</span>
              <label class="flex-1 space-y-1">
                <span class="block text-caption text-fg-muted">End page</span>
                <input
                  type="text"
                  inputmode="numeric"
                  bind:value={endPage}
                  class="w-full rounded-lg border border-border-default bg-surface-canvas px-3 py-1.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
                />
              </label>
            </div>
            {#if pageRangeError}
              <p class="mt-1.5 text-caption text-critical">{pageRangeError}</p>
            {/if}
          {/if}
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
        disabled={!docItem || isConverting || (isPdf && limitPages && !!pageRangeError)}
        onclick={handleConvert}
        class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
      >
        <Sparkles class="h-3.5 w-3.5 {isConverting ? 'animate-spin' : ''}" />
        {isConverting ? "Converting..." : docItem?.has_doclang ? "Re-convert to DocLang" : "Convert to DocLang"}
      </button>
    </div>
  {/snippet}
</Modal>
