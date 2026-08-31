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
  } from "lucide-svelte";
  import { documentsApi } from "../lib/api";
  import type { DocumentItem, DocumentDetail } from "../lib/types";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import DataTableHeader from "../lib/components/DataTableHeader.svelte";

  const cachedDocs = documentsApi.getCachedList();
  let documents: DocumentItem[] = cachedDocs || [];
  let isLoading = !cachedDocs;
  let isRefreshing = false;
  let error = "";
  let isDeleteModalOpen = false;
  let docToDelete: { id: number; filename: string } | null = null;
  let unsubscribeDocs: (() => void) | null = null;

  // Edit modal state
  let isEditModalOpen = false;
  let docToEdit: DocumentItem | null = null;
  let editFilename = "";
  let editExtractedText = "";
  let isSavingEdit = false;
  let editError = "";

  // Upload modal state
  let isUploadModalOpen = false;
  let uploadFile: File | null = null;
  let isUploading = false;
  let uploadError = "";

  // Text reader modal state
  let selectedDoc: DocumentDetail | null = null;
  let isLoadingDocDetail = false;

  let searchQuery = "";

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

  $: filteredDocuments = documents.filter((d) =>
    d.filename.toLowerCase().includes(searchQuery.toLowerCase()),
  );

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
    currentPage = 1;
  }

  async function handleUpload() {
    if (!uploadFile) return;
    isUploading = true;
    uploadError = "";
    try {
      const created = await documentsApi.upload(uploadFile);
      documents = [created, ...documents];
      isUploadModalOpen = false;
      uploadFile = null;
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
        extracted_text: editExtractedText,
      });
      documents = documents.map((d) =>
        d.id === updated.id
          ? {
              ...d,
              filename: updated.filename,
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
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <div
        class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1"
      >
        Library
      </div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">
        Document Specifications
      </h1>
      <p class="text-xs sm:text-sm text-slate-400">
        Upload and manage building code standards, specifications, and project
        manuals.
      </p>
    </div>

    <div class="flex items-center gap-2">
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
        on:click={() => (isUploadModalOpen = true)}
        class="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02]"
      >
        <Upload class="w-3.5 h-3.5" />
        <span>Upload Specification</span>
      </button>
    </div>
  </div>

  {#if error}
    <div
      class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs"
    >
      {error}
    </div>
  {/if}

  <!-- Bulk Actions Bar -->
  <BulkActionBar
    selectedCount={selectedDocIds.length}
    itemLabel="document"
    onClearSelection={() => (selectedDocIds = [])}
    onBulkDelete={() => (isBulkDeleteModalOpen = true)}
  />

  <!-- Documents Table Container -->
  <div
    class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-900/40"
  >
    <DataTableHeader
      bind:searchQuery
      searchPlaceholder="Filter documents by file name..."
      {isRefreshing}
      onRefresh={() => loadDocuments(true)}
    />

    {#if isLoading}
      <div class="p-12 text-center text-xs text-slate-400">
        Loading document library...
      </div>
    {:else if filteredDocuments.length === 0}
      <div class="p-12 text-center text-xs text-slate-500 space-y-2">
        <p>No specification documents found.</p>
        <button
          type="button"
          on:click={() => (isUploadModalOpen = true)}
          class="text-[#0071e3] hover:underline font-medium"
        >
          Upload your first specification (PDF, TXT, MD)
        </button>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-slate-300">
          <thead
            class="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold"
          >
            <tr>
              <th class="py-3 px-4 w-10">
                <input
                  type="checkbox"
                  checked={allFilteredSelected}
                  on:change={toggleSelectAll}
                  class="rounded bg-slate-950 border-slate-700 text-[#0071e3] focus:ring-[#0071e3] cursor-pointer w-4 h-4"
                  title="Select or deselect all visible documents"
                />
              </th>
              <th class="py-3 px-4">ID</th>
              <th class="py-3 px-4">Document File</th>
              <th class="py-3 px-4">Extracted Text</th>
              <th class="py-3 px-4">Characters</th>
              <th class="py-3 px-4">Uploaded</th>
              <th class="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each paginatedDocuments as doc}
              <tr class="hover:bg-slate-900/60 transition-colors {selectedDocIds.includes(doc.id) ? 'bg-blue-950/20' : ''}">
                <td class="py-3 px-4 w-10">
                  <input
                    type="checkbox"
                    checked={selectedDocIds.includes(doc.id)}
                    on:change={() => toggleSelectDoc(doc.id)}
                    class="rounded bg-slate-950 border-slate-700 text-[#0071e3] focus:ring-[#0071e3] cursor-pointer w-4 h-4"
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

<!-- Upload Modal -->
{#if isUploadModalOpen}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md"
  >
    <div
      class="bg-slate-900 border border-slate-800 w-full max-w-lg rounded-2xl shadow-2xl p-6 space-y-4"
    >
      <div
        class="flex items-center justify-between border-b border-slate-800 pb-3"
      >
        <h2 class="text-base font-bold text-white">
          Upload Specification Document
        </h2>
        <button
          type="button"
          on:click={() => (isUploadModalOpen = false)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      {#if uploadError}
        <div
          class="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs"
        >
          {uploadError}
        </div>
      {/if}

      <div
        class="border-2 border-dashed border-slate-700 hover:border-[#0071e3] transition-colors rounded-xl p-6 text-center bg-slate-950/40"
      >
        <FileText class="w-8 h-8 text-slate-400 mx-auto mb-2" />
        <p class="text-xs text-slate-400 mb-3">
          Upload PDF, TXT, or Markdown building specifications
        </p>
        <label
          class="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold cursor-pointer transition-colors"
        >
          <span>Choose File</span>
          <input
            type="file"
            accept=".pdf,.txt,.md,.markdown"
            on:change={(e) => {
              const target = e.target as HTMLInputElement;
              if (target.files) uploadFile = target.files[0];
            }}
            class="hidden"
          />
        </label>
      </div>

      {#if uploadFile}
        <div
          class="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-xs"
        >
          <span class="text-white font-medium truncate">{uploadFile.name}</span>
          <span class="text-slate-500"
            >{(uploadFile.size / 1024).toFixed(1)} KB</span
          >
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
          <h2 class="text-base font-bold text-white tracking-tight">
            {selectedDoc.filename}
          </h2>
          <p class="text-xs text-slate-400">
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
