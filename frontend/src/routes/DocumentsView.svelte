<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import {
    BookOpen,
    Plus,
    Upload,
    CloudDownload,
    Trash2,
    FileText,
    Eye,
    Pencil,
    X,
    CheckCircle2,
    Search,
    RotateCw,
    FolderSync,
    ExternalLink,
  } from "lucide-svelte";
  import { documentsApi, parsingEnginesApi } from "../lib/api";
  import { DOCUMENT_TYPES } from "../lib/types";
  import type {
    DocumentItem,
    DocumentDetail,
    DocumentType,
    IdsImportResult,
    ParsingEngineInstance,
  } from "../lib/types";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import { toasts } from "../lib/toast.svelte";
  import { createTableState } from "../lib/tableState.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import DataTableHeader from "../lib/components/DataTableHeader.svelte";
  import OpenCdeSyncModal from "../lib/components/OpenCdeSyncModal.svelte";
  import DocumentBulkEditModal from "../lib/components/DocumentBulkEditModal.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import IdsImportForm from "../lib/components/IdsImportForm.svelte";
  import DocumentViewer from "../lib/components/DocumentViewer.svelte";
  import GoogleDriveImportModal from "../lib/components/GoogleDriveImportModal.svelte";

  interface Props {
    /**
     * Called when the "Manual" source tab is chosen — hand-typing a rule needs
     * the full per-element-category editor, which lives on its own page rather
     * than cramped inside this modal.
     */
    onNavigateToManualRuleEditor?: () => void;
  }

  let { onNavigateToManualRuleEditor = () => {} }: Props = $props();

  const cachedDocs = documentsApi.getCachedList();
  let documents: DocumentItem[] = $state(cachedDocs || []);
  let isLoading = $state(!cachedDocs);
  let isRefreshing = $state(false);
  let error = $state("");
  let isDeleteModalOpen = $state(false);
  let isOpenCdeModalOpen = $state(false);
  let isBulkEditModalOpen = $state(false);
  let docToDelete: { id: number; filename: string } | null = $state(null);
  let unsubscribeDocs: (() => void) | null = null;

  // Edit modal state
  let isEditModalOpen = $state(false);
  let docToEdit: DocumentItem | null = $state(null);
  let editFilename = $state("");
  let editDocType = $state("Specification");
  let editExtractedText = $state("");
  let isSavingEdit = $state(false);
  let editError = $state("");

  // Upload modal state — three ways a rule source can enter the system,
  // sharing one modal: an uploaded document (parsed later in Rule Extraction
  // Studio), a buildingSMART IDS file, or a hand-typed rule (which routes to
  // the dedicated Manual Rule Editor page instead of rendering here).
  let isUploadModalOpen = $state(false);
  let uploadTab: "document" | "ids" = $state("document");
  let isDriveImportModalOpen = $state(false);

  // Called by the sidebar's "New Rule Document Upload" action once this view is mounted.
  export function openUploadModal(tab: "document" | "ids" = "document") {
    uploadTab = tab;
    isUploadModalOpen = true;
  }
  let uploadFile: File | null = $state(null);
  let uploadDocType = $state("Specification");
  let uploadParser: "auto" | "unstructured" | "light" = $state("auto");
  let uploadInstance = $state("");
  let parsingEngines: ParsingEngineInstance[] = $state([]);
  let isUploading = $state(false);
  let uploadError = $state("");

  async function loadParsingEngines() {
    try {
      parsingEngines = await parsingEnginesApi.list();
    } catch {
      // Non-fatal — the instance selector just stays empty (uses the
      // server's default engine) when this can't be loaded.
    }
  }

  let successMessage = $state("");

  function flashSuccess(message: string) {
    successMessage = message;
    setTimeout(() => {
      if (successMessage === message) successMessage = "";
    }, 6000);
  }

  function goToManualRuleEditor() {
    isUploadModalOpen = false;
    onNavigateToManualRuleEditor();
  }

  function handleDriveImportComplete(successCount: number, failCount: number) {
    isDriveImportModalOpen = false;
    loadDocuments(true);
    if (successCount && !failCount) {
      flashSuccess(`Imported ${successCount} document${successCount === 1 ? "" : "s"} from Google Drive.`);
    } else if (successCount && failCount) {
      flashSuccess(`Imported ${successCount} of ${successCount + failCount} Google Drive links — see errors for the rest.`);
    }
  }

  function handleIdsImportedFromUpload(res: IdsImportResult) {
    isUploadModalOpen = false;
    flashSuccess(
      `Imported ${res.created_count} of ${res.total_parsed} rules from IDS file into "${res.ruleset_id}" — view them in Rules Catalog.`,
    );
  }

  // Text reader modal state
  let selectedDoc: DocumentDetail | null = $state(null);
  let isLoadingDocDetail = false;

  // Search, filter, sort, paginate and select — all owned by the shared state.
  const table = $state(
    createTableState<DocumentItem, number>({
      rows: () => documents,
      getId: (d) => d.id,
      searchFields: (d) => [d.filename, d.extracted_text_preview],
      filters: {
        docType: (d, value) => (d.doc_type || "Specification") === value,
      },
      initialSort: { field: "id", asc: false },
    }),
  );

  async function loadDocuments(force = false) {
    if (!documents.length) {
      isLoading = true;
    } else {
      isRefreshing = true;
    }
    error = "";
    try {
      documents = await documentsApi.list({ forceRefresh: force });
    } catch (err: any) {
      if (!documents.length) {
        error = err.message || "Failed to load document specifications.";
      }
    } finally {
      isLoading = false;
      isRefreshing = false;
    }
  }

  onMount(() => {
    unsubscribeDocs = documentsApi.subscribe((updatedDocs) => {
      documents = updatedDocs;
    });
    loadDocuments();
    loadParsingEngines();
  });

  onDestroy(() => {
    if (unsubscribeDocs) {
      unsubscribeDocs();
    }
  });

  let isBulkDeleteModalOpen = $state(false);

  function exportSelectedToCsv() {
    const targetDocs = table.selectedCount ? table.selectedRows : table.sorted;
    const headers = ["ID", "Filename", "DocType", "CharCount", "UploadDate"];
    const rows = targetDocs.map((d) => [
      d.id,
      `"${(d.filename || "").replace(/"/g, '""')}"`,
      `"${(d.doc_type || "Specification").replace(/"/g, '""')}"`,
      d.char_count || 0,
      `"${d.upload_date || ""}"`,
    ]);
    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute(
      "download",
      `documents_export_${new Date().toISOString().substring(0, 10)}.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  async function confirmBulkDelete() {
    if (!table.selectedCount) return;
    try {
      for (const id of table.selectedIdList) {
        await documentsApi.delete(id);
      }
      documents = documents.filter((d) => !table.selectedIds.has(d.id));
      table.clearSelection();
      isBulkDeleteModalOpen = false;
    } catch (err: any) {
      error = `Could not delete selected documents: ${err.message}`;
    }
  }

  async function handleUpload() {
    if (!uploadFile) return;
    isUploading = true;
    uploadError = "";
    try {
      const created = await documentsApi.upload(uploadFile, uploadDocType, {
        parser: uploadParser,
        engine_instance: uploadParser === "light" ? undefined : uploadInstance || undefined,
      });
      documents = [created, ...documents];
      isUploadModalOpen = false;
      uploadFile = null;
      uploadDocType = "Specification";
      uploadParser = "auto";
      uploadInstance = "";
    } catch (err: any) {
      uploadError = err.message || "Failed to upload document.";
    } finally {
      isUploading = false;
    }
  }

  async function openReader(id: number) {
    isLoadingDocDetail = true;
    try {
      selectedDoc = await documentsApi.get(id);
    } catch (err: any) {
      toasts.error(err.message || "Unknown error", "Could not load document text");
    } finally {
      isLoadingDocDetail = false;
    }
  }

  async function openEdit(doc: DocumentItem) {
    docToEdit = doc;
    editFilename = doc.filename;
    editDocType = doc.doc_type || "Specification";
    editExtractedText = "";
    editError = "";
    isEditModalOpen = true;
    try {
      const detail = await documentsApi.get(doc.id);
      editExtractedText = detail.extracted_text || "";
    } catch {
      editExtractedText = doc.extracted_text_preview || "";
    }
  }

  async function handleSaveEdit() {
    if (!docToEdit) return;
    if (!editFilename.trim()) {
      editError = "Filename is required.";
      return;
    }
    isSavingEdit = true;
    editError = "";
    try {
      const updated = await documentsApi.update(docToEdit.id, {
        filename: editFilename.trim(),
        doc_type: editDocType,
        extracted_text: editExtractedText,
      });
      documents = documents.map((d) =>
        d.id === updated.id
          ? {
              ...d,
              filename: updated.filename,
              doc_type: updated.doc_type,
              extracted_text_preview:
                updated.extracted_text.slice(0, 200) +
                (updated.extracted_text.length > 200 ? "..." : ""),
              char_count: updated.char_count,
            }
          : d,
      );
      isEditModalOpen = false;
      docToEdit = null;
    } catch (err: any) {
      editError = err.message || "Failed to update document.";
    } finally {
      isSavingEdit = false;
    }
  }

  function promptDelete(id: number, filename: string) {
    docToDelete = { id, filename };
    isDeleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!docToDelete) return;
    try {
      await documentsApi.delete(docToDelete.id);
      documents = documents.filter((d) => d.id !== docToDelete!.id);
      docToDelete = null;
    } catch (err: any) {
      error = `Failed to delete document: ${err.message}`;
    }
  }
</script>

<div class="mx-auto space-y-6">
  <!-- Header -->
  <PageHeader
    category="Library"
    title="Document Specifications"
    subtitle="Upload and manage building code standards, specifications, and project manuals."
    icon={BookOpen}
  >
    {#snippet actions()}
      <div class="flex items-center gap-2">
        <button
          type="button"
          onclick={() => (isOpenCdeModalOpen = true)}
          class="inline-flex items-center gap-1.5 rounded-full border border-blue-800/50 bg-blue-950/40 px-3.5 py-2 text-xs font-semibold text-blue-300 transition-colors hover:bg-blue-900/60"
          title="Sync documents via buildingSMART OpenCDE API"
        >
          <FolderSync class="h-3.5 w-3.5" />
          <span>OpenCDE Sync</span>
        </button>

        <button
          type="button"
          onclick={() => loadDocuments(true)}
          class="inline-flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900/60 px-3.5 py-2 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
          title="Refresh document specifications"
        >
          <RotateCw class="h-3.5 w-3.5 {isRefreshing ? 'animate-spin text-blue-400' : ''}" />
          <span>{isRefreshing ? "Refreshing..." : "Refresh"}</span>
        </button>

        <button
          type="button"
          onclick={() => (isDriveImportModalOpen = true)}
          class="inline-flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900/60 px-3.5 py-2 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
          title="Import documents from Google Drive share links"
        >
          <CloudDownload class="h-3.5 w-3.5" />
          <span>Import from Drive</span>
        </button>

        <button
          type="button"
          onclick={() => openUploadModal()}
          class="inline-flex items-center gap-2 rounded-full bg-accent px-4 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover"
        >
          <Upload class="h-3.5 w-3.5" />
          <span>Upload Specification</span>
        </button>
      </div>
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300">
      {error}
    </div>
  {/if}

  {#if successMessage}
    <div
      class="flex items-center gap-2.5 rounded-xl border border-emerald-800 bg-emerald-950/50 p-4 text-xs text-emerald-300"
    >
      <CheckCircle2 class="h-4 w-4 shrink-0 text-emerald-400" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <!-- Bulk Actions Bar -->
  <BulkActionBar
    selectedCount={table.selectedCount}
    itemLabel="document"
    onClearSelection={() => table.clearSelection()}
    onBulkEdit={() => (isBulkEditModalOpen = true)}
    onBulkExport={exportSelectedToCsv}
    onBulkDelete={() => (isBulkDeleteModalOpen = true)}
  />

  <!-- Documents Table Container -->
  <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40">
    <DataTableHeader
      bind:searchQuery={table.search}
      searchPlaceholder="Filter documents by file name or text..."
      {isRefreshing}
      onRefresh={() => loadDocuments(true)}
    >
      {#snippet filters()}
        <div class="flex items-center gap-1.5">
          <select
            bind:value={table.filters.docType}
            aria-label="Filter by document type"
            class="rounded-xl border border-slate-800 bg-slate-950 px-2.5 py-2 text-xs text-slate-300 focus:border-accent focus:outline-none"
          >
            <option value="ALL">All Types</option>
            {#each DOCUMENT_TYPES as type (type)}
              <option value={type}>{type}</option>
            {/each}
          </select>
        </div>
      {/snippet}
    </DataTableHeader>

    {#if isLoading}
      <LoadingState message="Loading document library..." />
    {:else if table.totalItems === 0}
      <div class="p-6">
        <EmptyState
          title="No specification documents found"
          description="Upload building code specifications or sync with OpenCDE to begin extraction."
          actionLabel="Upload Specification (PDF, TXT, MD)"
          onAction={() => openUploadModal()}
        />
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-slate-300">
          <thead
            class="border-b border-slate-800 bg-slate-950 text-caption font-semibold uppercase tracking-wider text-slate-400"
          >
            <tr>
              <th class="w-10 px-4 py-3">
                <TableCheckbox
                  checked={table.allFilteredSelected}
                  indeterminate={table.someFilteredSelected}
                  onchange={() => table.toggleSelectAll()}
                  title="Select or deselect all visible documents"
                />
              </th>
              <SortHeader
                column="id"
                sortField={table.sortField}
                sortAsc={table.sortAsc}
                onSort={(f) => table.toggleSort(f)}
              >
                ID
              </SortHeader>
              <SortHeader
                column="filename"
                sortField={table.sortField}
                sortAsc={table.sortAsc}
                onSort={(f) => table.toggleSort(f)}
              >
                Document File
              </SortHeader>
              <SortHeader
                column="doc_type"
                sortField={table.sortField}
                sortAsc={table.sortAsc}
                onSort={(f) => table.toggleSort(f)}
              >
                Type
              </SortHeader>
              <th class="px-4 py-3">Extracted Text</th>
              <SortHeader
                column="char_count"
                sortField={table.sortField}
                sortAsc={table.sortAsc}
                onSort={(f) => table.toggleSort(f)}
              >
                Characters
              </SortHeader>
              <SortHeader
                column="upload_date"
                sortField={table.sortField}
                sortAsc={table.sortAsc}
                onSort={(f) => table.toggleSort(f)}
              >
                Uploaded
              </SortHeader>
              <th class="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each table.paginated as doc (doc.id)}
              <tr
                class="transition-colors hover:bg-slate-900/60 {table.isSelected(doc.id)
                  ? 'bg-blue-950/20'
                  : ''}"
              >
                <td class="w-10 px-4 py-3">
                  <TableCheckbox
                    checked={table.isSelected(doc.id)}
                    onchange={() => table.toggleSelect(doc.id)}
                    ariaLabel={`Select document ${doc.filename}`}
                  />
                </td>
                <td class="px-4 py-3 font-mono text-slate-500">#{doc.id}</td>
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <FileText class="h-4 w-4 shrink-0 text-blue-400" />
                    <span class="max-w-xs truncate font-semibold text-slate-50">{doc.filename}</span
                    >
                  </div>
                </td>
                <td class="whitespace-nowrap px-4 py-3">
                  <span
                    class="inline-flex items-center rounded-md border border-slate-700/60 bg-slate-800 px-2 py-0.5 text-caption font-medium text-blue-300"
                  >
                    {doc.doc_type || "Specification"}
                  </span>
                </td>
                <td class="max-w-sm truncate px-4 py-3 text-caption text-slate-400">
                  {doc.extracted_text_preview || "No preview available"}
                </td>
                <td class="px-4 py-3 font-mono text-xs text-slate-400">
                  {doc.char_count.toLocaleString()}
                </td>
                <td class="whitespace-nowrap px-4 py-3 text-slate-500">
                  {doc.upload_date ? doc.upload_date.substring(0, 10) : "-"}
                </td>
                <td class="whitespace-nowrap px-4 py-3 text-right">
                  <div class="flex items-center justify-end gap-1.5">
                    <button
                      type="button"
                      onclick={() => openReader(doc.id)}
                      class="rounded-lg bg-slate-800 p-1.5 text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
                      title="Preview document"
                    >
                      <Eye class="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onclick={() => openEdit(doc)}
                      class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-blue-950/30 hover:text-blue-400"
                      title="Edit document"
                    >
                      <Pencil class="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onclick={() => promptDelete(doc.id, doc.filename)}
                      class="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-rose-950/30 hover:text-rose-400"
                      title="Delete document"
                    >
                      <Trash2 class="h-3.5 w-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <TablePagination
        currentPage={table.page}
        pageSize={table.pageSize}
        totalItems={table.totalItems}
        onPageChange={(p) => (table.requestedPage = p)}
        onPageSizeChange={(size) => {
          table.pageSize = size;
          table.requestedPage = 1;
        }}
      />
    {/if}
  </div>
</div>

<!-- Add Rule Source Modal: a document upload, an IDS import, or a hand-typed rule -->
{#if isUploadModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-2xl flex-col space-y-4 rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <h2 class="text-base font-bold text-slate-50">Add Rule Source</h2>
        <button
          type="button"
          onclick={() => (isUploadModalOpen = false)}
          class="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <!-- Source Tabs -->
      <div class="flex items-center gap-1 rounded-xl border border-slate-800 bg-slate-950/60 p-1">
        <button
          type="button"
          onclick={() => (uploadTab = "document")}
          class="flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition-colors {uploadTab ===
          'document'
            ? 'bg-accent text-white shadow-sm'
            : 'text-slate-400 hover:bg-slate-900 hover:text-slate-50'}"
        >
          PDF / Word / Excel / TXT
        </button>
        <button
          type="button"
          onclick={() => (uploadTab = "ids")}
          class="flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition-colors {uploadTab ===
          'ids'
            ? 'bg-accent text-white shadow-sm'
            : 'text-slate-400 hover:bg-slate-900 hover:text-slate-50'}"
        >
          IDS XML File
        </button>
        <button
          type="button"
          onclick={goToManualRuleEditor}
          title="Opens the Manual Rule Editor page, organized by building element category"
          class="inline-flex flex-1 items-center justify-center gap-1 rounded-lg px-3 py-2 text-xs font-semibold text-slate-400 transition-colors hover:bg-slate-900 hover:text-slate-50"
        >
          <span>Manual</span>
          <ExternalLink class="h-3 w-3 opacity-60" />
        </button>
      </div>

      <div class="flex-1 overflow-y-auto pr-1">
        {#if uploadTab === "document"}
          <div class="space-y-4">
            {#if uploadError}
              <div
                class="rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300"
              >
                {uploadError}
              </div>
            {/if}

            <div class="space-y-1.5">
              <label for="upload-doc-type" class="block text-xs font-semibold text-slate-300">
                Document Type
              </label>
              <select
                id="upload-doc-type"
                bind:value={uploadDocType}
                class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
              >
                {#each DOCUMENT_TYPES as type (type)}
                  <option value={type}>{type}</option>
                {/each}
              </select>
              <p class="text-caption text-slate-500">
                Classifies the document for filtering — used later in Rule Extraction Studio.
              </p>
            </div>

            <div class="space-y-1.5">
              <label for="upload-parser" class="block text-xs font-semibold text-slate-300">
                Parsing Engine
              </label>
              <select
                id="upload-parser"
                bind:value={uploadParser}
                class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
              >
                <option value="auto">Auto (Unstructured API, falls back to local)</option>
                <option value="unstructured"
                  >Unstructured API only (best quality, slower, uploads file)</option
                >
                <option value="light">Light local extraction only (instant, no upload)</option>
              </select>
            </div>

            {#if uploadParser !== "light" && parsingEngines.length > 0}
              <div class="space-y-1.5">
                <label for="upload-instance" class="block text-xs font-semibold text-slate-300">
                  Instance
                </label>
                <select
                  id="upload-instance"
                  bind:value={uploadInstance}
                  class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
                >
                  <option value="">Default</option>
                  {#each parsingEngines as engine (engine.id)}
                    <option value={engine.name} disabled={!engine.is_enabled}>
                      {engine.name} ({engine.kind}{engine.is_default ? ", default" : ""}{!engine.is_enabled
                        ? ", disabled"
                        : ""})
                    </option>
                  {/each}
                </select>
                <p class="text-caption text-slate-500">
                  Which configured parsing engine to use — see Settings &gt; Parsing Engines.
                </p>
              </div>
            {/if}

            <div
              class="rounded-xl border-2 border-dashed border-slate-700 bg-slate-950/40 p-6 text-center transition-colors hover:border-accent"
            >
              <FileText class="mx-auto mb-2 h-8 w-8 text-slate-400" />
              <p class="mb-3 text-xs text-slate-400">
                Upload PDF, Word, Excel, CSV, TXT, or Markdown specifications
              </p>
              <label
                class="inline-flex cursor-pointer items-center gap-1.5 rounded-full bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
              >
                <span>Choose File</span>
                <input
                  type="file"
                  accept=".pdf,.txt,.md,.markdown,.docx,.csv,.xlsx"
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
                class="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs"
              >
                <span class="truncate font-medium text-slate-50">{uploadFile.name}</span>
                <span class="text-slate-500">{(uploadFile.size / 1024).toFixed(1)} KB</span>
              </div>
            {/if}

            <div class="flex justify-end gap-2 border-t border-slate-800 pt-2">
              <button
                type="button"
                onclick={() => (isUploadModalOpen = false)}
                class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!uploadFile || isUploading}
                onclick={handleUpload}
                class="rounded-full bg-accent px-5 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
              >
                {isUploading ? "Extracting Text..." : "Upload & Extract"}
              </button>
            </div>
          </div>
        {:else}
          <IdsImportForm
            defaultRulesetId=""
            onCancel={() => (isUploadModalOpen = false)}
            onImported={handleIdsImportedFromUpload}
          />
        {/if}
      </div>
    </div>
  </div>
{/if}

{#if isDriveImportModalOpen}
  <GoogleDriveImportModal
    onClose={() => (isDriveImportModalOpen = false)}
    onComplete={handleDriveImportComplete}
  />
{/if}

<!-- Document Viewer Modal -->
{#if selectedDoc}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div>
          <div class="flex items-center gap-2">
            <h2 class="text-base font-bold tracking-tight text-slate-50">
              {selectedDoc.filename}
            </h2>
            {#if selectedDoc.doc_type}
              <span
                class="rounded-md border border-slate-700/60 bg-slate-800 px-2 py-0.5 text-caption font-medium text-blue-300"
              >
                {selectedDoc.doc_type}
              </span>
            {/if}
          </div>
          <p class="mt-0.5 text-xs text-slate-400">
            {selectedDoc.char_count.toLocaleString()} extracted characters
          </p>
        </div>
        <button
          type="button"
          onclick={() => (selectedDoc = null)}
          class="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <div class="flex-1 overflow-hidden">
        <DocumentViewer documentId={selectedDoc.id} />
      </div>

      <div
        class="flex items-center justify-between border-t border-slate-800 bg-slate-950 px-6 py-3"
      >
        <button
          type="button"
          onclick={() => {
            const doc = documents.find((d) => d.id === selectedDoc!.id);
            selectedDoc = null;
            if (doc) openEdit(doc);
          }}
          class="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-1.5 text-xs text-slate-50 transition-colors hover:bg-slate-700"
        >
          <Pencil class="h-3.5 w-3.5" />
          <span>Edit Document</span>
        </button>

        <button
          type="button"
          onclick={() => (selectedDoc = null)}
          class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 hover:bg-slate-700"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Edit Document Modal -->
{#if isEditModalOpen && docToEdit}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div class="flex items-center gap-2.5">
          <div class="rounded-xl border border-blue-500/20 bg-blue-500/10 p-2 text-blue-400">
            <Pencil class="h-5 w-5" />
          </div>
          <div>
            <h2 class="text-base font-bold tracking-tight text-slate-50">
              Edit Document #{docToEdit.id}
            </h2>
            <p class="text-xs text-slate-400">
              Update specification filename and parsed text content
            </p>
          </div>
        </div>
        <button
          type="button"
          onclick={() => (isEditModalOpen = false)}
          class="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <!-- Body Form -->
      <div class="flex-1 space-y-4 overflow-y-auto p-6">
        {#if editError}
          <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300">
            {editError}
          </div>
        {/if}

        <div class="space-y-1.5">
          <label for="edit-doc-filename" class="block text-xs font-semibold text-slate-300">
            Filename <span class="text-rose-400">*</span>
          </label>
          <input
            id="edit-doc-filename"
            type="text"
            bind:value={editFilename}
            placeholder="e.g. BuildingCode_Part9_Specifications.pdf"
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
          />
        </div>

        <div class="space-y-1.5">
          <label for="edit-doc-type" class="block text-xs font-semibold text-slate-300">
            Document Type
          </label>
          <select
            id="edit-doc-type"
            bind:value={editDocType}
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
          >
            {#each DOCUMENT_TYPES as type (type)}
              <option value={type}>{type}</option>
            {/each}
          </select>
        </div>

        <div class="flex flex-1 flex-col space-y-1.5">
          <label for="edit-doc-text" class="block text-xs font-semibold text-slate-300">
            Extracted Specification Text
          </label>
          <textarea
            id="edit-doc-text"
            rows="10"
            bind:value={editExtractedText}
            placeholder="Parsed specification clauses and text content..."
            class="w-full resize-y rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 font-mono text-xs leading-relaxed text-slate-200 placeholder-slate-500 focus:border-accent focus:outline-none"
          ></textarea>
        </div>
      </div>

      <!-- Footer -->
      <div
        class="flex items-center justify-end gap-2 border-t border-slate-800 bg-slate-950 px-6 py-3"
      >
        <button
          type="button"
          onclick={() => (isEditModalOpen = false)}
          class="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isSavingEdit || !editFilename.trim()}
          onclick={handleSaveEdit}
          class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:opacity-50"
        >
          <span>{isSavingEdit ? "Saving..." : "Save Changes"}</span>
        </button>
      </div>
    </div>
  </div>
{/if}

<ConfirmModal
  bind:isOpen={isDeleteModalOpen}
  title="Delete Specification Document"
  message={`Are you sure you want to delete "${docToDelete?.filename || ""}" and its extracted text? This cannot be undone.`}
  confirmText="Delete Document"
  danger={true}
  onConfirm={confirmDelete}
  onCancel={() => (docToDelete = null)}
/>

<ConfirmModal
  bind:isOpen={isBulkDeleteModalOpen}
  title="Delete Selected Documents"
  message={`Are you sure you want to delete ${table.selectedCount} selected document specification(s)? This action cannot be undone.`}
  confirmText="Delete Selected Documents"
  danger={true}
  onConfirm={confirmBulkDelete}
  onCancel={() => table.clearSelection()}
/>

<OpenCdeSyncModal
  isOpen={isOpenCdeModalOpen}
  onClose={() => (isOpenCdeModalOpen = false)}
  onSyncComplete={() => loadDocuments(true)}
/>

<DocumentBulkEditModal
  isOpen={isBulkEditModalOpen}
  selectedDocIds={table.selectedIdList}
  onClose={() => (isBulkEditModalOpen = false)}
  onBulkUpdated={() => {
    loadDocuments(true);
    table.clearSelection();
  }}
/>
