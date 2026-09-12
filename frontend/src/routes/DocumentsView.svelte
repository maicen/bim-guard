<script lang="ts">
  import { onMount, onDestroy, untrack } from "svelte";
  import { push } from "svelte-spa-router";
  import {
    BookOpen,
    Plus,
    Upload,
    CloudDownload,
    Trash2,
    FileText,
    FileSpreadsheet,
    FileImage,
    Presentation,
    File as FileGeneric,
    Eye,
    Pencil,
    X,
    CheckCircle2,
    Search,
    RotateCw,
    FolderSync,
    Sparkles,
    FileCode,
  } from "lucide-svelte";
  import type { ComponentType } from "svelte";
  import { documentsApi, parsingEnginesApi } from "../lib/api";
  import { withAuthToken } from "../lib/authToken";
  import { authState } from "../lib/auth.svelte";
  import { DOCUMENT_TYPES } from "../lib/types";
  import type {
    DocumentItem,
    DocumentType,
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
  import GoogleDriveImportModal from "../lib/components/GoogleDriveImportModal.svelte";

  /** Icon + accent color for a document's file extension, shown in the table's file column. */
  function fileIconFor(filename: string): { icon: ComponentType; color: string } {
    const ext = (filename.split(".").pop() || "").toLowerCase();
    switch (ext) {
      case "pdf":
        return { icon: FileText, color: "text-rose-400" };
      case "doc":
      case "docx":
        return { icon: FileText, color: "text-blue-400" };
      case "xls":
      case "xlsx":
      case "csv":
        return { icon: FileSpreadsheet, color: "text-emerald-400" };
      case "ppt":
      case "pptx":
        return { icon: Presentation, color: "text-orange-400" };
      case "png":
      case "jpg":
      case "jpeg":
      case "tiff":
      case "tif":
      case "bmp":
      case "webp":
        return { icon: FileImage, color: "text-purple-400" };
      case "html":
      case "htm":
      case "adoc":
      case "asciidoc":
        return { icon: FileCode, color: "text-amber-400" };
      case "doclang":
      case "dclg":
      case "dclx":
      case "xml":
        return { icon: FileCode, color: "text-cyan-400" };
      case "md":
      case "markdown":
      case "txt":
        return { icon: FileText, color: "text-slate-400" };
      default:
        return { icon: FileGeneric, color: "text-slate-400" };
    }
  }

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
  let isSavingEdit = $state(false);
  let editError = $state("");

  // Upload modal state — a document (PDF/Word/Excel/etc, parsed into DocLang
  // later in Rule Extraction Studio) or a pre-converted DocLang XML export.
  let isUploadModalOpen = $state(false);
  let isDriveImportModalOpen = $state(false);

  // Called by the sidebar's "New Rule Document Upload" action once this view is mounted.
  export function openUploadModal() {
    isUploadModalOpen = true;
  }
  let uploadFile: File | null = $state(null);
  let uploadDocType = $state("Specification");
  let uploadParser: "auto" | "unstructured" | "light" = $state("auto");
  let uploadInstance = $state("");
  let generateDoclangOnUpload = $state(true);
  let parsingEngines: ParsingEngineInstance[] = $state([]);
  let isUploading = $state(false);
  let uploadError = $state("");
  let generatingDoclangId: number | null = $state(null);

  /** A pre-converted DocLang upload (.doclang, .dclg, .dclx) is already DocLang — no parsing engine or conversion step applies to it. */
  let isDoclangSelected = $derived(
    uploadFile ? /\.(doclang|dclg|dclx)$/i.test(uploadFile.name) : false
  );
  let isPdfSelected = $derived(uploadFile ? /\.pdf$/i.test(uploadFile.name) : false);

  // Optional page range (1-based, inclusive) trimming a PDF upload down
  // before storage/extraction -- see app/modules/document_parsing/pdf_page_range.py.
  // PDF-only; left blank, the whole document is uploaded as before.
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

  function handleDriveImportComplete(successCount: number, failCount: number) {
    isDriveImportModalOpen = false;
    loadDocuments(true);
    if (successCount && !failCount) {
      flashSuccess(`Imported ${successCount} document${successCount === 1 ? "" : "s"} from Google Drive.`);
    } else if (successCount && failCount) {
      flashSuccess(`Imported ${successCount} of ${successCount + failCount} Google Drive links — see errors for the rest.`);
    }
  }

  // Search, filter, sort, paginate and select — all owned by the shared state.
  const table = $state(
    createTableState<DocumentItem, number>({
      rows: () => documents,
      getId: (d) => d.id,
      searchFields: (d) => [d.filename, d.text_preview],
      filters: {
        docType: (d, value) => (d.doc_type || "Specification") === value,
      },
      initialSort: { field: "id", asc: false },
    }),
  );

  $effect(() => {
    const _orgId = authState.activeOrganizationId;
    // loadDocuments synchronously reads `documents.length` before its first
    // await; without untrack that read makes this effect depend on
    // `documents`, and the subsequent `documents = ...` assignment (both the
    // direct one and the one from the cache-subscribe callback) re-triggers
    // the effect — an infinite fetch loop that floods the network.
    untrack(() => loadDocuments(true));
  });

  async function loadDocuments(force = false) {
    if (!documents.length) {
      isLoading = true;
    } else {
      isRefreshing = true;
    }
    error = "";
    try {
      documents = await documentsApi.list({
        forceRefresh: force,
        organization_id: authState.activeOrganizationId,
      });
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
      documents = [created, ...documents];
      isUploadModalOpen = false;
      uploadFile = null;
      uploadDocType = "Specification";
      uploadParser = "auto";
      uploadInstance = "";
      generateDoclangOnUpload = true;
      uploadLimitPages = false;
      uploadStartPage = "1";
      uploadEndPage = "";
    } catch (err: any) {
      uploadError = err.message || "Failed to upload document.";
    } finally {
      isUploading = false;
    }
  }

  function openReader(id: number) {
    const params = new URLSearchParams();
    params.set("doc_id", String(id));
    if (authState.activeOrganizationId) {
      params.set("org", String(authState.activeOrganizationId));
    }
    push(`/document?${params.toString()}`);
  }

  async function generateDoclangForRow(doc: DocumentItem) {
    generatingDoclangId = doc.id;
    try {
      const updated = await documentsApi.generateDoclang(doc.id);
      documents = documents.map((d) =>
        d.id === updated.id
          ? {
              ...d,
              text_preview: updated.text?.slice(0, 200) || "",
              char_count: updated.char_count,
              has_doclang: Boolean(updated.doclang_xml?.trim()),
            }
          : d,
      );
      flashSuccess(`DocLang generated for "${doc.filename}".`);
    } catch (err: any) {
      toasts.error(err.message || "Unknown error", "Could not generate DocLang");
    } finally {
      generatingDoclangId = null;
    }
  }

  function openEdit(doc: DocumentItem) {
    docToEdit = doc;
    editFilename = doc.filename;
    editDocType = doc.doc_type || "Specification";
    editError = "";
    isEditModalOpen = true;
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
      });
      documents = documents.map((d) =>
        d.id === updated.id
          ? {
              ...d,
              filename: updated.filename,
              doc_type: updated.doc_type,
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
          class="inline-flex items-center gap-1.5 rounded-xl border border-blue-800/50 bg-blue-950/40 px-3.5 py-2 text-xs font-semibold text-blue-300 transition-colors hover:bg-blue-900/60"
          title="Sync documents via buildingSMART OpenCDE API"
        >
          <FolderSync class="h-3.5 w-3.5" />
          <span>OpenCDE Sync</span>
        </button>

        <button
          type="button"
          onclick={() => loadDocuments(true)}
          class="inline-flex items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-900/60 px-3.5 py-2 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
          title="Refresh document specifications"
        >
          <RotateCw class="h-3.5 w-3.5 {isRefreshing ? 'animate-spin text-blue-400' : ''}" />
          <span>{isRefreshing ? "Refreshing..." : "Refresh"}</span>
        </button>

        <button
          type="button"
          onclick={() => (isDriveImportModalOpen = true)}
          class="inline-flex items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-900/60 px-3.5 py-2 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
          title="Import documents from Google Drive share links"
        >
          <CloudDownload class="h-3.5 w-3.5" />
          <span>Import from Drive</span>
        </button>

        <button
          type="button"
          onclick={() => openUploadModal()}
          class="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover"
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
            class="rounded-xl border border-slate-800 bg-slate-950 px-2.5 py-2 text-xs text-slate-300 focus:border-accent focus:outline-hidden"
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
          actionLabel="Upload Specification (PDF, Word, Excel, DocLang...)"
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
              {@const fi = fileIconFor(doc.filename)}
              {@const FileIcon = fi.icon}
              <tr
                class="transition-colors hover:bg-slate-900/60 {table.isSelected(doc.id)
                  ? 'bg-surface-selected'
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
                    <span class="relative inline-flex shrink-0">
                      <FileIcon class="h-4 w-4 {fi.color}" />
                      {#if doc.has_doclang}
                        <CheckCircle2
                          class="absolute -bottom-1 -right-1 h-2.5 w-2.5 rounded-full bg-slate-900 text-emerald-400"
                        />
                      {/if}
                    </span>
                    <a
                      href={withAuthToken(documentsApi.getFileUrl(doc.id))}
                      target="_blank"
                      rel="noopener noreferrer"
                      class="max-w-xs truncate font-semibold text-slate-50 hover:text-accent hover:underline"
                      title={doc.has_doclang
                        ? "DocLang XML available — click to open the original file"
                        : "Click to open the original file"}
                    >
                      {doc.filename}
                    </a>
                  </div>
                </td>
                <td class="whitespace-nowrap px-4 py-3">
                  <span
                    class="inline-flex items-center rounded-md border border-slate-700/60 bg-slate-800 px-2 py-0.5 text-caption font-medium text-blue-300"
                  >
                    {doc.doc_type || "Specification"}
                  </span>
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
                      disabled={!doc.has_doclang}
                      onclick={() => openReader(doc.id)}
                      class="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-cyan-950/30 hover:text-cyan-400 disabled:cursor-not-allowed disabled:opacity-30"
                      title={doc.has_doclang ? "Preview DocLang XML" : "No DocLang generated yet"}
                    >
                      <FileCode class="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      disabled={doc.has_doclang || generatingDoclangId === doc.id}
                      onclick={() => generateDoclangForRow(doc)}
                      class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-success-bg/40 hover:text-success disabled:cursor-not-allowed disabled:opacity-30"
                      title={doc.has_doclang ? "DocLang already generated" : "Generate DocLang"}
                    >
                      <Sparkles class="h-3.5 w-3.5 {generatingDoclangId === doc.id ? 'animate-pulse' : ''}" />
                    </button>
                    <button
                      type="button"
                      onclick={() => openEdit(doc)}
                      class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-accent"
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

<!-- Add Document Modal -->
{#if isUploadModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-2xl flex-col space-y-4 rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <h2 class="text-base font-bold text-slate-50">Add Document</h2>
        <button
          type="button"
          onclick={() => (isUploadModalOpen = false)}
          class="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <div class="flex-1 overflow-y-auto pr-1">
        <div class="space-y-4">
          {#if uploadError}
            <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300">
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
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 focus:border-accent focus:outline-hidden"
            >
              {#each DOCUMENT_TYPES as type (type)}
                <option value={type}>{type}</option>
              {/each}
            </select>
            <p class="text-caption text-slate-500">
              Classifies the document for filtering — used later in Rule Extraction Studio.
            </p>
          </div>

          {#if !isDoclangSelected}
            <div class="space-y-1.5">
              <label for="upload-parser" class="block text-xs font-semibold text-slate-300">
                Parsing Engine
              </label>
              <select
                id="upload-parser"
                bind:value={uploadParser}
                class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 focus:border-accent focus:outline-hidden"
              >
                <option value="auto">Auto (configured engine, falls back to local)</option>
                <option value="unstructured" disabled={parsingEngines.length === 0}
                  >Force configured engine only{parsingEngines.length === 0
                    ? " (no engine configured)"
                    : " (best quality, slower, uploads file)"}</option
                >
                <option value="light">Light local extraction only (instant, no upload)</option>
              </select>
            </div>

            <div class="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-3.5 py-2.5">
              <div>
                <label for="upload-generate-doclang" class="block text-xs font-semibold text-slate-300">
                  Convert to DocLang now
                </label>
                <p class="text-caption text-slate-500">
                  When off, the file is stored but DocLang is generated later from the documents table.
                </p>
              </div>
              <button
                id="upload-generate-doclang"
                type="button"
                role="switch"
                aria-checked={generateDoclangOnUpload}
                aria-label="Convert to DocLang now"
                onclick={() => (generateDoclangOnUpload = !generateDoclangOnUpload)}
                class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors {generateDoclangOnUpload
                  ? 'bg-accent'
                  : 'bg-slate-700'}"
              >
                <span
                  class="inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform {generateDoclangOnUpload
                    ? 'translate-x-5'
                    : 'translate-x-1'}"
                ></span>
              </button>
            </div>

            {#if isPdfSelected}
              <div class="rounded-xl border border-slate-800 bg-slate-950/60 px-3.5 py-2.5">
                <div class="flex items-center justify-between">
                  <div>
                    <label for="upload-limit-pages" class="block text-xs font-semibold text-slate-300">
                      Limit to a page range
                    </label>
                    <p class="text-caption text-slate-500">
                      Only these pages are stored and parsed — the rest of the PDF is discarded.
                    </p>
                  </div>
                  <button
                    id="upload-limit-pages"
                    type="button"
                    role="switch"
                    aria-checked={uploadLimitPages}
                    aria-label="Limit to a page range"
                    onclick={() => (uploadLimitPages = !uploadLimitPages)}
                    class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors {uploadLimitPages
                      ? 'bg-accent'
                      : 'bg-slate-700'}"
                  >
                    <span
                      class="inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform {uploadLimitPages
                        ? 'translate-x-5'
                        : 'translate-x-1'}"
                    ></span>
                  </button>
                </div>
                {#if uploadLimitPages}
                  <div class="mt-3 flex items-center gap-2">
                    <label class="flex-1 space-y-1">
                      <span class="block text-caption text-slate-500">Start page</span>
                      <input
                        type="text"
                        inputmode="numeric"
                        bind:value={uploadStartPage}
                        class="w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-hidden"
                      />
                    </label>
                    <span class="mt-4 text-slate-600">–</span>
                    <label class="flex-1 space-y-1">
                      <span class="block text-caption text-slate-500">End page</span>
                      <input
                        type="text"
                        inputmode="numeric"
                        bind:value={uploadEndPage}
                        class="w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-hidden"
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
                <label for="upload-instance" class="block text-xs font-semibold text-slate-300">
                  Instance
                </label>
                <select
                  id="upload-instance"
                  bind:value={uploadInstance}
                  class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 focus:border-accent focus:outline-hidden"
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
          {:else}
            <div class="rounded-xl border border-cyan-800/40 bg-cyan-950/20 px-3.5 py-2.5 text-xs text-cyan-300">
              This is a pre-converted DocLang XML file — it's stored as-is, with no parsing engine or
              conversion step needed.
            </div>
          {/if}

          <div
            class="rounded-xl border-2 border-dashed border-slate-700 bg-slate-950/40 p-6 text-center transition-colors hover:border-accent"
          >
            <FileText class="mx-auto mb-2 h-8 w-8 text-slate-400" />
            <p class="mb-3 text-xs text-slate-400">
              Upload PDF, Word, Excel, PowerPoint, HTML, AsciiDoc, Markdown, CSV, TXT, an image
              (PNG/JPEG/TIFF/BMP/WEBP), or pre-converted DocLang files (.dclg, .dclx, .doclang)
            </p>
            <label
              class="inline-flex cursor-pointer items-center gap-1.5 rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
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
              disabled={!uploadFile || isUploading || (isPdfSelected && uploadLimitPages && !!uploadPageRangeError)}
              onclick={handleUpload}
              class="rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {isUploading ? "Extracting Text..." : "Upload & Extract"}
            </button>
          </div>
        </div>
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
              Update specification filename and document type
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
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-hidden"
          />
        </div>

        <div class="space-y-1.5">
          <label for="edit-doc-type" class="block text-xs font-semibold text-slate-300">
            Document Type
          </label>
          <select
            id="edit-doc-type"
            bind:value={editDocType}
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 focus:border-accent focus:outline-hidden"
          >
            {#each DOCUMENT_TYPES as type (type)}
              <option value={type}>{type}</option>
            {/each}
          </select>
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
          class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:opacity-50"
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
