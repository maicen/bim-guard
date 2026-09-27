<script lang="ts">
  import { onMount, onDestroy, untrack } from "svelte";
  import { push } from "svelte-spa-router";
  import {
    BookOpen,
    Upload,
    CloudDownload,
    Trash2,
    Eye,
    Pencil,
    CheckCircle2,
    RotateCw,
    FolderSync,
    Sparkles,
    FileCode,
    Plus,
    Route,
  } from "lucide-svelte";
  import Icon from "@iconify/svelte";
  import { documentsApi, parsingEnginesApi, orgParsingEnginesApi } from "../lib/api";
  import { withAuthToken } from "../lib/authToken";
  import { downloadText } from "../lib/utils/download";
  import { authState } from "../lib/auth.svelte";
  import { DOCUMENT_TYPES } from "../lib/types";
  import type {
    DocumentItem,
    DocumentType,
    DocumentDetail,
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
  import DocumentUploadModal from "../lib/components/DocumentUploadModal.svelte";
  import ConvertDoclangModal from "../lib/components/ConvertDoclangModal.svelte";
  import DocumentEditModal from "../lib/components/DocumentEditModal.svelte";
  import Alert from "../lib/components/Alert.svelte";
  import { Select } from "../lib/components/ui";
  import { toErrorLogEntry, type ErrorLogEntry } from "../lib/utils/errorLog";

  /** Icon identifier for a document's file extension, rendered as a vscode-icons SVG. */
  function fileIconFor(filename: string): string {
    const ext = (filename.split(".").pop() || "").toLowerCase();
    switch (ext) {
      case "pdf":
        return "vscode-icons:file-type-pdf2";
      case "doc":
      case "docx":
        return "vscode-icons:file-type-word";
      case "xls":
      case "xlsx":
      case "csv":
        return "vscode-icons:file-type-excel";
      case "ppt":
      case "pptx":
        return "vscode-icons:file-type-powerpoint";
      case "png":
      case "jpg":
      case "jpeg":
      case "tiff":
      case "tif":
      case "bmp":
      case "webp":
        return "vscode-icons:file-type-image";
      case "html":
      case "htm":
        return "vscode-icons:file-type-html";
      case "adoc":
      case "asciidoc":
        return "vscode-icons:file-type-asciidoc";
      case "doclang":
      case "dclg":
      case "dclx":
      case "xml":
        return "vscode-icons:file-type-xml";
      case "md":
      case "markdown":
        return "vscode-icons:file-type-markdown";
      case "txt":
        return "vscode-icons:file-type-text";
      default:
        return "vscode-icons:default-file";
    }
  }

  const cachedDocs = documentsApi.getCachedList();
  let documents: DocumentItem[] = $state(cachedDocs || []);
  let isLoading = $state(!cachedDocs);
  let isRefreshing = $state(false);
  let error = $state("");
  let errorLog: ErrorLogEntry[] = $state([]);
  let isDeleteModalOpen = $state(false);
  let isOpenCdeModalOpen = $state(false);
  let isBulkEditModalOpen = $state(false);
  let docToDelete: { id: number; filename: string } | null = $state(null);
  let unsubscribeDocs: (() => void) | null = null;

  // Edit modal state
  let isEditModalOpen = $state(false);
  let docToEdit: DocumentItem | null = $state(null);

  // Upload modal state
  let isUploadModalOpen = $state(false);
  let isDriveImportModalOpen = $state(false);
  let parsingEngines: ParsingEngineInstance[] = $state([]);
  let generatingDoclangId: number | null = $state(null);

  // Convert DocLang modal state
  let isConvertModalOpen = $state(false);
  let docToConvert: DocumentItem | null = $state(null);

  function openConvertModal(doc: DocumentItem) {
    docToConvert = doc;
    isConvertModalOpen = true;
  }

  // Called by the sidebar's "New Rule Document Upload" action once this view is mounted.
  export function openUploadModal() {
    isUploadModalOpen = true;
  }

  async function loadParsingEngines() {
    try {
      const orgId = authState.activeOrganizationId;
      const [platform, org] = await Promise.all([
        parsingEnginesApi.list(),
        orgId ? orgParsingEnginesApi.list(orgId) : Promise.resolve([]),
      ]);
      // Org-scoped instances first -- they're the ones actually used
      // (get_effective_default prefers them), so they should lead the list.
      parsingEngines = [...org, ...platform];
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

  const docTypeFilterOptions = [
    { value: "ALL", label: "All Types" },
    ...DOCUMENT_TYPES.map((type) => ({ value: type, label: type })),
  ];

  const doclangFilterOptions = [
    { value: "ALL", label: "All Conversion States" },
    { value: "ready", label: "DocLang Ready" },
    { value: "pending", label: "Pending Conversion" },
  ];

  // Search, filter, sort, paginate and select — all owned by the shared state.
  const table = $state(
    createTableState<DocumentItem, number>({
      rows: () => documents,
      getId: (d) => d.id,
      searchFields: (d) => [d.filename, d.text_preview],
      filters: {
        docType: (d, value) => !value || value === "ALL" || (d.doc_type || "Specification") === value,
        doclangStatus: (d, value) => {
          if (!value || value === "ALL") return true;
          if (value === "ready") return Boolean(d.has_doclang);
          if (value === "pending") return !d.has_doclang;
          return true;
        },
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

  // A fast double org-switch fires loadDocuments twice in a row; network
  // responses aren't guaranteed to arrive in request order, so a request
  // token makes a slower, stale response a no-op instead of letting it
  // clobber a newer one that already resolved.
  let loadToken = 0;

  async function loadDocuments(force = false) {
    const token = ++loadToken;
    if (!documents.length) {
      isLoading = true;
    } else {
      isRefreshing = true;
    }
    error = "";
    errorLog = [];
    try {
      const result = await documentsApi.list({
        forceRefresh: force,
        organization_id: authState.activeOrganizationId,
      });
      if (token !== loadToken) return;
      documents = result;
    } catch (err: any) {
      if (token !== loadToken) return;
      if (!documents.length) {
        error = err.message || "Failed to load document specifications.";
        errorLog = [toErrorLogEntry(err, "load documents")];
      }
    } finally {
      if (token === loadToken) {
        isLoading = false;
        isRefreshing = false;
      }
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
    const filename = `documents_export_${new Date().toISOString().substring(0, 10)}.csv`;
    downloadText(csvContent, filename, "text/csv;charset=utf-8;");
  }

  async function confirmBulkDelete() {
    if (!table.selectedCount) return;
    error = "";
    errorLog = [];
    const targetIds = [...table.selectedIdList];
    const count = targetIds.length;

    await table.optimisticDelete({
      ids: targetIds,
      action: async () => {
        const failures: ErrorLogEntry[] = [];
        for (const id of targetIds) {
          try {
            await documentsApi.delete(id);
          } catch (err: any) {
            failures.push(toErrorLogEntry(err, `document #${id}`));
          }
        }
        if (failures.length > 0) {
          errorLog = failures;
          throw new Error(`Could not delete ${failures.length} of ${targetIds.length} documents.`);
        }
      },
      onSuccess: () => {
        documents = documents.filter((d) => !targetIds.includes(d.id));
        flashSuccess(`Deleted ${count} document(s).`);
        toasts.success(`Deleted ${count} document(s).`);
      },
      onError: (err) => {
        error = err.message || "Failed to delete documents.";
        toasts.fromError(err, "Failed to delete selected documents");
      },
    });
  }

  function openReader(id: number) {
    const params = new URLSearchParams();
    params.set("doc_id", String(id));
    if (authState.activeOrganizationId) {
      params.set("org", String(authState.activeOrganizationId));
    }
    push(`/document?${params.toString()}`);
  }

  function openRuleSourceMap(id: number) {
    const params = new URLSearchParams();
    params.set("doc_id", String(id));
    if (authState.activeOrganizationId) {
      params.set("org", String(authState.activeOrganizationId));
    }
    push(`/rule-source?${params.toString()}`);
  }

  async function generateDoclangForRow(doc: DocumentItem) {
    generatingDoclangId = doc.id;
    await table.optimisticUpdate({
      ids: doc.id,
      patch: { has_doclang: true },
      action: () => documentsApi.generateDoclang(doc.id),
      onSuccess: (updated) => {
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
        toasts.success(`DocLang generated for "${doc.filename}".`);
      },
      onError: (err) => {
        toasts.error(err.message || "Unknown error", "Could not generate DocLang");
      },
    });
    generatingDoclangId = null;
  }

  function openEdit(doc: DocumentItem) {
    docToEdit = doc;
    isEditModalOpen = true;
  }

  function promptDelete(id: number, filename: string) {
    docToDelete = { id, filename };
    isDeleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!docToDelete) return;
    const target = docToDelete;
    docToDelete = null;

    await table.optimisticDelete({
      ids: target.id,
      action: () => documentsApi.delete(target.id),
      onSuccess: () => {
        documents = documents.filter((d) => d.id !== target.id);
        flashSuccess(`Deleted document "${target.filename}".`);
        toasts.success(`Deleted document "${target.filename}".`);
      },
      onError: (err) => {
        error = `Failed to delete document: ${err.message}`;
        errorLog = [toErrorLogEntry(err, target.filename)];
        toasts.fromError(err, `Could not delete "${target.filename}"`);
      },
    });
  }
</script>

<div class="mx-auto space-y-6">
  <!-- Header -->
  <PageHeader
    category="Library"
    title="Document Specifications"
    subtitle="Upload and manage building code standards, specifications, and project manuals."
    icon={BookOpen}
  />

  <div class="flex flex-wrap items-center gap-2">
    <button
      type="button"
      onclick={() => openUploadModal()}
      class="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover"
    >
      <Upload class="h-3.5 w-3.5" />
      <span>Upload Specification</span>
    </button>

    <button
      type="button"
      onclick={() => push("/manual-rule-editor")}
      class="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover"
      title="Opens the Manual Rule Editor to hand-author a rule, organized by building element category"
    >
      <Plus class="h-3.5 w-3.5" />
      <span>Add Manual Rules</span>
    </button>

    <button
      type="button"
      onclick={() => (isOpenCdeModalOpen = true)}
      class="inline-flex items-center gap-1.5 rounded-xl border border-border-default bg-surface-card/60 px-3.5 py-2 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
      title="Sync documents via buildingSMART OpenCDE API"
    >
      <FolderSync class="h-3.5 w-3.5" />
      <span>OpenCDE Sync</span>
    </button>

    <button
      type="button"
      onclick={() => loadDocuments(true)}
      class="inline-flex items-center gap-1.5 rounded-xl border border-border-default bg-surface-card/60 px-3.5 py-2 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
      title="Refresh document specifications"
    >
      <RotateCw class="h-3.5 w-3.5 {isRefreshing ? 'animate-spin text-blue-400' : ''}" />
      <span>{isRefreshing ? "Refreshing..." : "Refresh"}</span>
    </button>

    <button
      type="button"
      onclick={() => (isDriveImportModalOpen = true)}
      class="inline-flex items-center gap-1.5 rounded-xl border border-border-default bg-surface-card/60 px-3.5 py-2 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
      title="Import documents from Google Drive share links"
    >
      <CloudDownload class="h-3.5 w-3.5" />
      <span>Import from Drive</span>
    </button>
  </div>

  {#if error}
    <Alert
      type="error"
      message={error}
      errors={errorLog}
      logTitle="Documents Error Log"
      dismissible
      onDismiss={() => {
        error = "";
        errorLog = [];
      }}
    />
  {/if}

  {#if successMessage}
    <div
      class="flex items-center gap-2.5 rounded-xl border border-success-border/60 bg-success-bg/40 p-4 text-xs text-success"
    >
      <CheckCircle2 class="h-4 w-4 shrink-0 text-success" />
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
  <div class="overflow-hidden rounded-2xl border border-border-default bg-surface-card/40">
    <DataTableHeader
      bind:searchQuery={table.search}
      searchPlaceholder="Filter documents by file name or text..."
      {isRefreshing}
      onRefresh={() => loadDocuments(true)}
    >
      {#snippet filters()}
        <div class="flex items-center gap-2">
          <Select
            ariaLabel="Filter by document type"
            options={docTypeFilterOptions}
            bind:value={table.filters.docType}
            triggerClass="bg-surface-canvas text-xs min-w-[130px]"
          />
          <Select
            ariaLabel="Filter by DocLang status"
            options={doclangFilterOptions}
            bind:value={table.filters.doclangStatus}
            triggerClass="bg-surface-canvas text-xs min-w-[155px]"
          />
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
        <table class="w-full text-left text-xs text-fg-secondary">
          <thead
            class="border-b border-border-default bg-surface-canvas text-caption font-semibold uppercase tracking-wider text-fg-muted"
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
              <th class="px-4 py-3 text-left">DocLang</th>
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
          <tbody class="divide-y divide-border-subtle">
            {#each table.paginated as doc (doc.id)}
              <tr
                class="transition-colors hover:bg-surface-hover {table.isSelected(doc.id)
                  ? 'bg-surface-selected'
                  : ''} {table.isPending(doc.id) ? 'opacity-50 pointer-events-none' : ''}"
              >
                <td class="w-10 px-4 py-3">
                  <TableCheckbox
                    checked={table.isSelected(doc.id)}
                    onchange={() => table.toggleSelect(doc.id)}
                    ariaLabel={`Select document ${doc.filename}`}
                  />
                </td>
                <td class="px-4 py-3 font-mono text-fg-muted">#{doc.id}</td>
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <span class="relative inline-flex shrink-0">
                      <Icon icon={fileIconFor(doc.filename)} class="h-4 w-4 shrink-0" />
                      {#if doc.has_doclang}
                        <CheckCircle2
                          class="absolute -bottom-1 -right-1 h-2.5 w-2.5 rounded-full bg-surface-card text-success"
                        />
                      {/if}
                    </span>
                    <a
                      href={withAuthToken(documentsApi.getFileUrl(doc.id))}
                      target="_blank"
                      rel="noopener noreferrer"
                      class="max-w-xs truncate font-semibold text-fg-primary hover:text-accent hover:underline"
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
                    class="inline-flex items-center rounded-md border border-border-default bg-surface-overlay px-2 py-0.5 text-caption font-medium text-fg-primary"
                  >
                    {doc.doc_type || "Specification"}
                  </span>
                </td>
                <td class="whitespace-nowrap px-4 py-3">
                  {#if doc.has_doclang}
                    <button
                      type="button"
                      onclick={() => openReader(doc.id)}
                      class="inline-flex items-center gap-1 rounded-full border border-success-border bg-success-bg px-2.5 py-0.5 text-caption font-medium text-success transition-colors hover:bg-success-bg/80"
                      title="DocLang XML ready — click to inspect structure"
                    >
                      <CheckCircle2 class="h-3 w-3" />
                      Ready
                    </button>
                  {:else}
                    <button
                      type="button"
                      onclick={() => openConvertModal(doc)}
                      class="inline-flex items-center gap-1 rounded-full border border-warning-border/60 bg-warning-bg/40 px-2.5 py-0.5 text-caption font-medium text-warning transition-colors hover:bg-warning-bg hover:border-warning-border"
                      title="Not converted — click to configure and convert to DocLang"
                    >
                      <Sparkles class="h-3 w-3" />
                      Convert
                    </button>
                  {/if}
                </td>
                <td class="px-4 py-3 font-mono text-xs text-fg-muted">
                  {doc.char_count.toLocaleString()}
                </td>
                <td class="whitespace-nowrap px-4 py-3 text-fg-muted">
                  {doc.upload_date ? doc.upload_date.substring(0, 10) : "-"}
                </td>
                <td class="whitespace-nowrap px-4 py-3 text-right">
                  <div class="flex items-center justify-end gap-1.5">
                    <button
                      type="button"
                      onclick={() => openReader(doc.id)}
                      class="rounded-lg bg-surface-overlay p-1.5 text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
                      title="Preview document"
                    >
                      <Eye class="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      disabled={!doc.has_doclang}
                      onclick={() => openReader(doc.id)}
                      class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-accent disabled:cursor-not-allowed disabled:opacity-30"
                      title={doc.has_doclang ? "Preview DocLang XML" : "No DocLang generated yet"}
                    >
                      <FileCode class="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onclick={() => openConvertModal(doc)}
                      class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-accent"
                      title={doc.has_doclang ? "Re-convert to DocLang" : "Convert to DocLang"}
                    >
                      <Sparkles class="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onclick={() => openRuleSourceMap(doc.id)}
                      class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-accent"
                      title="Rule-Source Map"
                    >
                      <Route class="h-3.5 w-3.5" />
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
                      class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-critical-bg hover:text-critical"
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

<DocumentUploadModal
  isOpen={isUploadModalOpen}
  {parsingEngines}
  onClose={() => (isUploadModalOpen = false)}
  onUploaded={(created) => {
    // The backend dedupes by content hash: re-uploading a byte-identical file
    // returns the *existing* document (still a 201), which is already in this
    // list. Prepending it blindly would put one id in the keyed table twice
    // and crash the view (each_key_duplicate).
    const alreadyListed = documents.some((d) => d.id === created.id);
    documents = [created, ...documents.filter((d) => d.id !== created.id)];
    isUploadModalOpen = false;
    flashSuccess(
      alreadyListed
        ? `"${created.filename}" was already uploaded — showing the existing document.`
        : `Uploaded "${created.filename}".`,
    );
  }}
/>

<ConvertDoclangModal
  isOpen={isConvertModalOpen}
  document={docToConvert}
  {parsingEngines}
  onClose={() => {
    isConvertModalOpen = false;
    docToConvert = null;
  }}
  onConverted={(updated) => {
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
    isConvertModalOpen = false;
    docToConvert = null;
    flashSuccess(`DocLang XML generated for "${updated.filename}".`);
  }}
/>

{#if isDriveImportModalOpen}
  <GoogleDriveImportModal
    onClose={() => (isDriveImportModalOpen = false)}
    onComplete={handleDriveImportComplete}
  />
{/if}

<DocumentEditModal
  isOpen={isEditModalOpen}
  doc={docToEdit}
  onClose={() => {
    isEditModalOpen = false;
    docToEdit = null;
  }}
  onSaved={(updated) => {
    documents = documents.map((d) => (d.id === updated.id ? { ...d, ...updated } : d));
    flashSuccess(`Updated document "${updated.filename}".`);
  }}
/>

<ConfirmModal
  bind:isOpen={isDeleteModalOpen}
  title="Delete Specification Document"
  message={`Are you sure you want to delete "${docToDelete?.filename || ""}" and its extracted text? This cannot be undone.`}
  confirmText="Delete Document"
  danger={true}
  optimistic={true}
  onConfirm={confirmDelete}
  onCancel={() => (docToDelete = null)}
/>

<ConfirmModal
  bind:isOpen={isBulkDeleteModalOpen}
  title="Delete Selected Documents"
  message={`Are you sure you want to delete ${table.selectedCount} selected document specification(s)? This action cannot be undone.`}
  confirmText="Delete Selected Documents"
  danger={true}
  optimistic={true}
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
