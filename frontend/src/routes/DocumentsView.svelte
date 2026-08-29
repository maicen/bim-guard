<script lang="ts">
  import { onMount } from 'svelte';
  import {
    BookOpen,
    Plus,
    Upload,
    Trash2,
    FileText,
    Eye,
    X,
    CheckCircle2,
    Search,
  } from 'lucide-svelte';
  import { documentsApi } from '../lib/api';
  import type { DocumentItem, DocumentDetail } from '../lib/types';
  import ConfirmModal from '../lib/components/ConfirmModal.svelte';

  let documents: DocumentItem[] = [];
  let isLoading = true;
  let error = '';
  let isDeleteModalOpen = false;
  let docToDelete: { id: number; filename: string } | null = null;

  // Upload modal state
  let isUploadModalOpen = false;
  let uploadFile: File | null = null;
  let isUploading = false;
  let uploadError = '';

  // Text reader modal state
  let selectedDoc: DocumentDetail | null = null;
  let isLoadingDocDetail = false;

  let searchQuery = '';

  async function loadDocuments() {
    isLoading = true;
    error = '';
    try {
      documents = await documentsApi.list();
    } catch (err: any) {
      error = err.message || 'Failed to load document specifications.';
    } finally {
      isLoading = false;
    }
  }

  onMount(() => {
    loadDocuments();
  });

  $: filteredDocuments = documents.filter((d) =>
    d.filename.toLowerCase().includes(searchQuery.toLowerCase())
  );

  async function handleUpload() {
    if (!uploadFile) return;
    isUploading = true;
    uploadError = '';
    try {
      const created = await documentsApi.upload(uploadFile);
      documents = [created, ...documents];
      isUploadModalOpen = false;
      uploadFile = null;
    } catch (err: any) {
      uploadError = err.message || 'Failed to upload document.';
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

<div class="space-y-6 max-w-6xl mx-auto">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <div class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Library</div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">Document Specifications</h1>
      <p class="text-xs sm:text-sm text-slate-400">Upload and manage building code standards, specifications, and project manuals.</p>
    </div>

    <button
      type="button"
      on:click={() => (isUploadModalOpen = true)}
      class="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02]"
    >
      <Upload class="w-3.5 h-3.5" />
      <span>Upload Specification</span>
    </button>
  </div>

  {#if error}
    <div class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
      {error}
    </div>
  {/if}

  <!-- Search Filter -->
  <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 flex items-center gap-3">
    <div class="relative flex-1">
      <Search class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
      <input
        type="text"
        bind:value={searchQuery}
        placeholder="Filter documents by file name..."
        class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
      />
    </div>
  </div>

  <!-- Documents Table -->
  <div class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-900/40">
    {#if isLoading}
      <div class="p-12 text-center text-xs text-slate-400">Loading document library...</div>
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
          <thead class="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
            <tr>
              <th class="py-3 px-4">ID</th>
              <th class="py-3 px-4">Document File</th>
              <th class="py-3 px-4">Extracted Text</th>
              <th class="py-3 px-4">Characters</th>
              <th class="py-3 px-4">Uploaded</th>
              <th class="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each filteredDocuments as doc}
              <tr class="hover:bg-slate-900/60 transition-colors">
                <td class="py-3 px-4 font-mono text-slate-500">#{doc.id}</td>
                <td class="py-3 px-4">
                  <div class="flex items-center gap-2">
                    <FileText class="w-4 h-4 text-blue-400 shrink-0" />
                    <span class="font-semibold text-white truncate max-w-xs">{doc.filename}</span>
                  </div>
                </td>
                <td class="py-3 px-4 text-slate-400 text-[11px] max-w-sm truncate">
                  {doc.extracted_text_preview || 'No preview available'}
                </td>
                <td class="py-3 px-4 text-slate-400 text-xs font-mono">
                  {doc.char_count.toLocaleString()}
                </td>
                <td class="py-3 px-4 text-slate-500 whitespace-nowrap">
                  {doc.upload_date ? doc.upload_date.substring(0, 10) : '-'}
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
    {/if}
  </div>
</div>

<!-- Upload Modal -->
{#if isUploadModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-lg rounded-2xl shadow-2xl p-6 space-y-4">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <h2 class="text-base font-bold text-white">Upload Specification Document</h2>
        <button
          type="button"
          on:click={() => (isUploadModalOpen = false)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      {#if uploadError}
        <div class="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
          {uploadError}
        </div>
      {/if}

      <div class="border-2 border-dashed border-slate-700 hover:border-[#0071e3] transition-colors rounded-xl p-6 text-center bg-slate-950/40">
        <FileText class="w-8 h-8 text-slate-400 mx-auto mb-2" />
        <p class="text-xs text-slate-400 mb-3">Upload PDF, TXT, or Markdown building specifications</p>
        <label class="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold cursor-pointer transition-colors">
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
          {isUploading ? 'Extracting Text...' : 'Upload & Extract'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Text Reader Modal -->
{#if selectedDoc}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div>
          <h2 class="text-base font-bold text-white tracking-tight">{selectedDoc.filename}</h2>
          <p class="text-xs text-slate-400">{selectedDoc.char_count.toLocaleString()} extracted characters</p>
        </div>
        <button
          type="button"
          on:click={() => (selectedDoc = null)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <div class="p-6 overflow-y-auto flex-1 bg-slate-950/60 font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
        {selectedDoc.extracted_text || 'No extracted text found.'}
      </div>

      <div class="px-6 py-3 border-t border-slate-800 bg-slate-950 flex justify-end">
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

<ConfirmModal
  bind:isOpen={isDeleteModalOpen}
  title="Delete Specification Document"
  message={`Are you sure you want to delete "${docToDelete?.filename || ''}" and its extracted text? This cannot be undone.`}
  confirmText="Delete Document"
  danger={true}
  onConfirm={confirmDelete}
  onCancel={() => (docToDelete = null)}
/>

