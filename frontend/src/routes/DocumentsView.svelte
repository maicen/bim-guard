<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import {
    BookOpen,
    Plus,
    Upload,
    Trash2,
    FileText,
    Eye,
    Pencil,
    X,
    CheckCircle2,
    Search,
    RotateCw,
    FolderSync,
  } from "lucide-svelte";
  import { documentsApi } from "../lib/api";
  import { DOCUMENT_TYPES } from "../lib/types";
  import type { DocumentItem, DocumentDetail, DocumentType, Rule, IdsImportResult } from "../lib/types";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
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
  import RuleForm from "../lib/components/RuleForm.svelte";
  import IdsImportForm from "../lib/components/IdsImportForm.svelte";

  const cachedDocs = documentsApi.getCachedList();
  let documents: DocumentItem[] = cachedDocs || [];
  let isLoading = !cachedDocs;
  let isRefreshing = false;
  let error = "";
  let isDeleteModalOpen = false;
  let isOpenCdeModalOpen = false;
  let isBulkEditModalOpen = false;
  let docToDelete: { id: number; filename: string } | null = null;
  let unsubscribeDocs: (() => void) | null = null;

  // Edit modal state
  let isEditModalOpen = false;
  let docToEdit: DocumentItem | null = null;
  let editFilename = "";
  let editDocType = "Specification";
  let editExtractedText = "";
  let isSavingEdit = false;
  let editError = "";

  // Upload modal state — three ways a rule source can enter the system,
  // sharing one modal: an uploaded document (parsed later in Rule Extraction
  // Studio), a buildingSMART IDS file, or a hand-typed rule.
  let isUploadModalOpen = false;
  let uploadTab: "document" | "ids" | "manual" = "document";

  // Called by the sidebar's "New Rule Document Upload" action once this view is mounted.
  export function openUploadModal(tab: "document" | "ids" | "manual" = "document") {
    uploadTab = tab;
    isUploadModalOpen = true;
  }
  let uploadFile: File | null = null;
  let uploadDocType = "Specification";
  let uploadParser: "auto" | "unstructured" | "light" = "auto";
  let isUploading = false;
  let uploadError = "";

  let successMessage = "";

  function flashSuccess(message: string) {
    successMessage = message;
    setTimeout(() => {
      if (successMessage === message) successMessage = "";
    }, 6000);
  }

  function handleRuleCreatedFromUpload(rule: Rule) {
    isUploadModalOpen = false;
    flashSuccess(`Rule "${rule.rule_id}" created — view it in Rules Catalog.`);
  }

  function handleIdsImportedFromUpload(res: IdsImportResult) {
    isUploadModalOpen = false;
    flashSuccess(
      `Imported ${res.created_count} of ${res.total_parsed} rules from IDS file into "${res.ruleset_id}" — view them in Rules Catalog.`,
    );
  }

  // Text reader modal state
  let selectedDoc: DocumentDetail | null = null;
  let isLoadingDocDetail = false;

  let searchQuery = "";
  let selectedDocTypeFilter: string = "ALL";

  // Sorting state
  let sortField: "id" | "filename" | "doc_type" | "char_count" | "upload_date" = "id";
  let sortAsc = false;

  function toggleSort(field: "id" | "filename" | "doc_type" | "char_count" | "upload_date") {
    if (sortField === field) {
      sortAsc = !sortAsc;
    } else {
      sortField = field;
      sortAsc = true;
    }
  }

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
  });

  onDestroy(() => {
    if (unsubscribeDocs) {
      unsubscribeDocs();
    }
  });

  $: filteredDocuments = documents
    .filter((d) => {
      const matchesSearch =
        d.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (d.extracted_text_preview || "").toLowerCase().includes(searchQuery.toLowerCase());
      const matchesType =
        selectedDocTypeFilter === "ALL" ||
        (d.doc_type || "Specification") === selectedDocTypeFilter;
      return matchesSearch && matchesType;
    })
    .sort((a, b) => {
      let valA: any = a[sortField];
      let valB: any = b[sortField];
      if (valA === undefined || valA === null) valA = "";
      if (valB === undefined || valB === null) valB = "";
      if (typeof valA === "string") valA = valA.toLowerCase();
      if (typeof valB === "string") valB = valB.toLowerCase();
      if (valA < valB) return sortAsc ? -1 : 1;
      if (valA > valB) return sortAsc ? 1 : -1;
      return 0;
    });

  let selectedDocIds: number[] = [];
  let isBulkDeleteModalOpen = false;

  let currentPage = 1;
  let pageSize = 10;

  $: totalItems = filteredDocuments.length;
  $: paginatedDocuments = filteredDocuments.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize,
  );

  $: allFilteredSelected =
    filteredDocuments.length > 0 &&
    filteredDocuments.every((d) => selectedDocIds.includes(d.id));

  function toggleSelectAll() {
    if (allFilteredSelected) {
      selectedDocIds = [];
    } else {
      selectedDocIds = filteredDocuments.map((d) => d.id);
    }
  }

  function toggleSelectDoc(id: number) {
    if (selectedDocIds.includes(id)) {
      selectedDocIds = selectedDocIds.filter((dId) => dId !== id);
    } else {
      selectedDocIds = [...selectedDocIds, id];
    }
  }

  function exportSelectedToCsv() {
    const docsToExport = documents.filter((d) => selectedDocIds.includes(d.id));
    const targetDocs = docsToExport.length ? docsToExport : filteredDocuments;
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
    if (!selectedDocIds.length) return;
    try {
      for (const id of selectedDocIds) {
        await documentsApi.delete(id);
      }
      documents = documents.filter((d) => !selectedDocIds.includes(d.id));
      selectedDocIds = [];
      isBulkDeleteModalOpen = false;
    } catch (err: any) {
      error = `Could not delete selected documents: ${err.message}`;
    }
  }

  $: {
    searchQuery;
    selectedDocTypeFilter;
    currentPage = 1;
  }

  async function handleUpload() {
    if (!uploadFile) return;
    isUploading = true;
    uploadError = "";
    try {
      const created = await documentsApi.upload(uploadFile, uploadDocType, { parser: uploadParser });
      documents = [created, ...documents];
      isUploadModalOpen = false;
      uploadFile = null;
      uploadDocType = "Specification";
      uploadParser = "auto";
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
      alert(`Could not load document text: ${err.message}`);
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

<div class="space-y-6 mx-auto">
  <!-- Header -->
  <PageHeader
    category="Library"
    title="Document Specifications"
    subtitle="Upload and manage building code standards, specifications, and project manuals."
    icon={BookOpen}
  >
    <div slot="actions" class="flex items-center gap-2">
      <button
        type="button"
        on:click={() => (isOpenCdeModalOpen = true)}
        class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-semibold bg-blue-950/40 hover:bg-blue-900/60 text-blue-300 border border-blue-800/50 transition-colors"
        title="Sync documents via buildingSMART OpenCDE API"
      >
        <FolderSync class="w-3.5 h-3.5" />
        <span>OpenCDE Sync</span>
      </button>

      <button
        type="button"
        on:click={() => loadDocuments(true)}
        class="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-semibold bg-slate-900/60 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800 transition-colors"
        title="Refresh document specifications"
      >
        <RotateCw class="w-3.5 h-3.5 {isRefreshing ? 'animate-spin text-blue-400' : ''}" />
        <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
      </button>

      <button
        type="button"
        on:click={() => openUploadModal()}
        class="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02]"
      >
        <Upload class="w-3.5 h-3.5" />
        <span>Upload Specification</span>
      </button>
    </div>
  </PageHeader>

  {#if error}
    <div
      class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs"
    >
      {error}
    </div>
  {/if}

  {#if successMessage}
    <div
      class="p-4 rounded-xl bg-emerald-950/50 border border-emerald-800 text-emerald-300 text-xs flex items-center gap-2.5"
    >
      <CheckCircle2 class="w-4 h-4 text-emerald-400 shrink-0" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <!-- Bulk Actions Bar -->
  <BulkActionBar
    selectedCount={selectedDocIds.length}
    itemLabel="document"
    onClearSelection={() => (selectedDocIds = [])}
    onBulkEdit={() => (isBulkEditModalOpen = true)}
    onBulkExport={exportSelectedToCsv}
    onBulkDelete={() => (isBulkDeleteModalOpen = true)}
  />

  <!-- Documents Table Container -->
  <div
    class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-900/40"
  >
    <DataTableHeader
      bind:searchQuery
      searchPlaceholder="Filter documents by file name or text..."
      {isRefreshing}
      onRefresh={() => loadDocuments(true)}
    >
      <div slot="filters" class="flex items-center gap-1.5">
        <select
          bind:value={selectedDocTypeFilter}
          aria-label="Filter by document type"
          class="bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-2 text-xs text-slate-300 focus:outline-none focus:border-[#0071e3]"
        >
          <option value="ALL">All Types</option>
          {#each DOCUMENT_TYPES as type}
            <option value={type}>{type}</option>
          {/each}
        </select>
      </div>
    </DataTableHeader>

    {#if isLoading}
      <LoadingState message="Loading document library..." />
    {:else if filteredDocuments.length === 0}
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
            class="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold"
          >
            <tr>
              <th class="py-3 px-4 w-10">
                <TableCheckbox
                  checked={allFilteredSelected}
                  on:change={toggleSelectAll}
                  title="Select or deselect all visible documents"
                />
              </th>
              <SortHeader column="id" {sortField} {sortAsc} onSort={toggleSort}>
                ID
              </SortHeader>
              <SortHeader column="filename" {sortField} {sortAsc} onSort={toggleSort}>
                Document File
              </SortHeader>
              <SortHeader column="doc_type" {sortField} {sortAsc} onSort={toggleSort}>
                Type
              </SortHeader>
              <th class="py-3 px-4">Extracted Text</th>
              <SortHeader column="char_count" {sortField} {sortAsc} onSort={toggleSort}>
                Characters
              </SortHeader>
              <SortHeader column="upload_date" {sortField} {sortAsc} onSort={toggleSort}>
                Uploaded
              </SortHeader>
              <th class="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each paginatedDocuments as doc}
              <tr class="hover:bg-slate-900/60 transition-colors {selectedDocIds.includes(doc.id) ? 'bg-blue-950/20' : ''}">
                <td class="py-3 px-4 w-10">
                  <TableCheckbox
                    checked={selectedDocIds.includes(doc.id)}
                    on:change={() => toggleSelectDoc(doc.id)}
                    ariaLabel={`Select document ${doc.filename}`}
                  />
                </td>
                <td class="py-3 px-4 font-mono text-slate-500">#{doc.id}</td>
                <td class="py-3 px-4">
                  <div class="flex items-center gap-2">
                    <FileText class="w-4 h-4 text-blue-400 shrink-0" />
                    <span class="font-semibold text-white truncate max-w-xs"
                      >{doc.filename}</span
                    >
                  </div>
                </td>
                <td class="py-3 px-4 whitespace-nowrap">
                  <span class="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-800 text-blue-300 border border-slate-700/60">
                    {doc.doc_type || 'Specification'}
                  </span>
                </td>
                <td
                  class="py-3 px-4 text-slate-400 text-[11px] max-w-sm truncate"
                >
                  {doc.extracted_text_preview || "No preview available"}
                </td>
                <td class="py-3 px-4 text-slate-400 text-xs font-mono">
                  {doc.char_count.toLocaleString()}
                </td>
                <td class="py-3 px-4 text-slate-500 whitespace-nowrap">
                  {doc.upload_date ? doc.upload_date.substring(0, 10) : "-"}
                </td>
                <td class="py-3 px-4 text-right whitespace-nowrap">
                  <div class="flex items-center justify-end gap-1.5">
                    <button
                      type="button"
                      on:click={() => openReader(doc.id)}
                      class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                      title="Inspect extracted text"
                    >
                      <Eye class="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      on:click={() => openEdit(doc)}
                      class="p-1.5 rounded-lg text-slate-400 hover:text-blue-400 hover:bg-blue-950/30 transition-colors"
                      title="Edit document"
                    >
                      <Pencil class="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      on:click={() => promptDelete(doc.id, doc.filename)}
                      class="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
                      title="Delete document"
                    >
                      <Trash2 class="w-3.5 h-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <TablePagination
        {currentPage}
        {pageSize}
        totalItems={totalItems}
        onPageChange={(p) => (currentPage = p)}
        onPageSizeChange={(s) => {
          pageSize = s;
          currentPage = 1;
        }}
      />
    {/if}
  </div>
</div>

<!-- Add Rule Source Modal: a document upload, an IDS import, or a hand-typed rule -->
{#if isUploadModalOpen}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md"
  >
    <div
      class="bg-slate-900 border border-slate-800 w-full max-w-2xl rounded-2xl shadow-2xl p-6 space-y-4 max-h-[90vh] flex flex-col"
    >
      <div
        class="flex items-center justify-between border-b border-slate-800 pb-3"
      >
        <h2 class="text-base font-bold text-white">Add Rule Source</h2>
        <button
          type="button"
          on:click={() => (isUploadModalOpen = false)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Source Tabs -->
      <div class="flex items-center gap-1 p-1 rounded-xl bg-slate-950/60 border border-slate-800">
        <button
          type="button"
          on:click={() => (uploadTab = "document")}
          class="flex-1 px-3 py-2 rounded-lg text-xs font-semibold transition-colors {uploadTab === 'document'
            ? 'bg-[#0071e3] text-white shadow-sm'
            : 'text-slate-400 hover:text-white hover:bg-slate-900'}"
        >
          PDF / Word / Excel / TXT
        </button>
        <button
          type="button"
          on:click={() => (uploadTab = "ids")}
          class="flex-1 px-3 py-2 rounded-lg text-xs font-semibold transition-colors {uploadTab === 'ids'
            ? 'bg-[#0071e3] text-white shadow-sm'
            : 'text-slate-400 hover:text-white hover:bg-slate-900'}"
        >
          IDS XML File
        </button>
        <button
          type="button"
          on:click={() => (uploadTab = "manual")}
          class="flex-1 px-3 py-2 rounded-lg text-xs font-semibold transition-colors {uploadTab === 'manual'
            ? 'bg-[#0071e3] text-white shadow-sm'
            : 'text-slate-400 hover:text-white hover:bg-slate-900'}"
        >
          Manual
        </button>
      </div>

      <div class="overflow-y-auto pr-1 flex-1">
        {#if uploadTab === "document"}
          <div class="space-y-4">
            {#if uploadError}
              <div class="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
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
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
              >
                {#each DOCUMENT_TYPES as type}
                  <option value={type}>{type}</option>
                {/each}
              </select>
              <p class="text-[11px] text-slate-500">
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
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
              >
                <option value="auto">Auto (Unstructured API, falls back to local)</option>
                <option value="unstructured">Unstructured API only (best quality, slower, uploads file)</option>
                <option value="light">Light local extraction only (instant, no upload)</option>
              </select>
            </div>

            <div
              class="border-2 border-dashed border-slate-700 hover:border-[#0071e3] transition-colors rounded-xl p-6 text-center bg-slate-950/40"
            >
              <FileText class="w-8 h-8 text-slate-400 mx-auto mb-2" />
              <p class="text-xs text-slate-400 mb-3">
                Upload PDF, Word, Excel, CSV, TXT, or Markdown specifications
              </p>
              <label
                class="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold cursor-pointer transition-colors"
              >
                <span>Choose File</span>
                <input
                  type="file"
                  accept=".pdf,.txt,.md,.markdown,.docx,.csv,.xlsx"
                  on:change={(e) => {
                    const target = e.target as HTMLInputElement;
                    if (target.files) uploadFile = target.files[0];
                  }}
                  class="hidden"
                />
              </label>
            </div>

            {#if uploadFile}
              <div class="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs">
                <span class="text-white font-medium truncate">{uploadFile.name}</span>
                <span class="text-slate-500">{(uploadFile.size / 1024).toFixed(1)} KB</span>
              </div>
            {/if}

            <div class="flex justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                type="button"
                on:click={() => (isUploadModalOpen = false)}
                class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!uploadFile || isUploading}
                on:click={handleUpload}
                class="px-5 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white disabled:opacity-50"
              >
                {isUploading ? "Extracting Text..." : "Upload & Extract"}
              </button>
            </div>
          </div>
        {:else if uploadTab === "ids"}
          <IdsImportForm
            defaultRulesetId=""
            onCancel={() => (isUploadModalOpen = false)}
            onImported={handleIdsImportedFromUpload}
          />
        {:else}
          <RuleForm
            onCancel={() => (isUploadModalOpen = false)}
            onSaved={handleRuleCreatedFromUpload}
          />
        {/if}
      </div>
    </div>
  </div>
{/if}

<!-- Text Reader Modal -->
{#if selectedDoc}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md"
  >
    <div
      class="bg-slate-900 border border-slate-800 w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]"
    >
      <div
        class="px-6 py-4 border-b border-slate-800 flex items-center justify-between"
      >
        <div>
          <div class="flex items-center gap-2">
            <h2 class="text-base font-bold text-white tracking-tight">
              {selectedDoc.filename}
            </h2>
            {#if selectedDoc.doc_type}
              <span class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-800 text-blue-300 border border-slate-700/60">
                {selectedDoc.doc_type}
              </span>
            {/if}
          </div>
          <p class="text-xs text-slate-400 mt-0.5">
            {selectedDoc.char_count.toLocaleString()} extracted characters
          </p>
        </div>
        <button
          type="button"
          on:click={() => (selectedDoc = null)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <div
        class="p-6 overflow-y-auto flex-1 bg-slate-950/60 font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed"
      >
        {selectedDoc.extracted_text || "No extracted text found."}
      </div>

      <div
        class="px-6 py-3 border-t border-slate-800 bg-slate-950 flex items-center justify-between"
      >
        <button
          type="button"
          on:click={() => {
            const doc = documents.find((d) => d.id === selectedDoc!.id);
            selectedDoc = null;
            if (doc) openEdit(doc);
          }}
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-slate-800 hover:bg-slate-700 text-white transition-colors"
        >
          <Pencil class="w-3.5 h-3.5" />
          <span>Edit Document</span>
        </button>

        <button
          type="button"
          on:click={() => (selectedDoc = null)}
          class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Edit Document Modal -->
{#if isEditModalOpen && docToEdit}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md"
  >
    <div
      class="bg-slate-900 border border-slate-800 w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
    >
      <!-- Header -->
      <div
        class="px-6 py-4 border-b border-slate-800 flex items-center justify-between"
      >
        <div class="flex items-center gap-2.5">
          <div class="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Pencil class="w-5 h-5" />
          </div>
          <div>
            <h2 class="text-base font-bold text-white tracking-tight">
              Edit Document #{docToEdit.id}
            </h2>
            <p class="text-xs text-slate-400">
              Update specification filename and parsed text content
            </p>
          </div>
        </div>
        <button
          type="button"
          on:click={() => (isEditModalOpen = false)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Body Form -->
      <div class="p-6 space-y-4 overflow-y-auto flex-1">
        {#if editError}
          <div
            class="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs"
          >
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
            placeholder="e.g. OBC_Part9_Specifications.pdf"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
          />
        </div>

        <div class="space-y-1.5">
          <label for="edit-doc-type" class="block text-xs font-semibold text-slate-300">
            Document Type
          </label>
          <select
            id="edit-doc-type"
            bind:value={editDocType}
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
          >
            {#each DOCUMENT_TYPES as type}
              <option value={type}>{type}</option>
            {/each}
          </select>
        </div>

        <div class="space-y-1.5 flex-1 flex flex-col">
          <label for="edit-doc-text" class="block text-xs font-semibold text-slate-300">
            Extracted Specification Text
          </label>
          <textarea
            id="edit-doc-text"
            rows="10"
            bind:value={editExtractedText}
            placeholder="Parsed specification clauses and text content..."
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 font-mono text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-[#0071e3] leading-relaxed resize-y"
          ></textarea>
        </div>
      </div>

      <!-- Footer -->
      <div
        class="px-6 py-3 border-t border-slate-800 bg-slate-950 flex items-center justify-end gap-2"
      >
        <button
          type="button"
          on:click={() => (isEditModalOpen = false)}
          class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isSavingEdit || !editFilename.trim()}
          on:click={handleSaveEdit}
          class="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all disabled:opacity-50"
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
  message={`Are you sure you want to delete ${selectedDocIds.length} selected document specification(s)? This action cannot be undone.`}
  confirmText="Delete Selected Documents"
  danger={true}
  onConfirm={confirmBulkDelete}
  onCancel={() => (selectedDocIds = [])}
/>

<OpenCdeSyncModal
  isOpen={isOpenCdeModalOpen}
  onClose={() => (isOpenCdeModalOpen = false)}
  onSyncComplete={() => loadDocuments(true)}
/>

<DocumentBulkEditModal
  isOpen={isBulkEditModalOpen}
  {selectedDocIds}
  onClose={() => (isBulkEditModalOpen = false)}
  onBulkUpdated={() => {
    loadDocuments(true);
    selectedDocIds = [];
  }}
/>

