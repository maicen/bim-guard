<script lang="ts">
  import { ArrowLeft, BookOpen } from "lucide-svelte";
  import { documentsApi } from "../lib/api";
  import { toasts } from "../lib/toast.svelte";
  import type { DocumentDetail } from "../lib/types";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import DocumentViewer from "../lib/components/DocumentViewer.svelte";

  interface Props {
    documentId: number | null;
    onBack: () => void;
  }

  let { documentId, onBack }: Props = $props();

  let doc: DocumentDetail | null = $state(null);
  let loading = $state(true);
  let loadError = $state("");
  let loadedForId: number | null = null;

  $effect(() => {
    const id = documentId;
    if (id == null) {
      doc = null;
      loading = false;
      return;
    }
    if (loadedForId === id) return;
    loadedForId = id;
    loading = true;
    loadError = "";
    documentsApi
      .get(id)
      .then((detail) => {
        doc = detail;
      })
      .catch((err: any) => {
        loadError = err.message || "Could not load this document.";
        toasts.error(loadError, "Document load failed");
      })
      .finally(() => {
        loading = false;
      });
  });
</script>

<div class="flex h-full flex-col space-y-5 pb-12">
  <PageHeader
    category="Documents"
    title={doc?.filename || (loading ? "Loading document…" : "Document")}
    subtitle={doc ? `${doc.char_count.toLocaleString()} extracted characters` : ""}
    icon={BookOpen}
  >
    {#snippet badge()}
      {#if doc?.doc_type}
        <span
          class="rounded-md border border-slate-700/60 bg-slate-800 px-2 py-0.5 text-caption font-medium text-blue-300"
        >
          {doc.doc_type}
        </span>
      {/if}
    {/snippet}
    {#snippet actions()}
      <button
        type="button"
        onclick={onBack}
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-800 bg-slate-900/60 px-3.5 py-2 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
      >
        <ArrowLeft class="h-3.5 w-3.5" />
        <span>Back to Documents</span>
      </button>
    {/snippet}
  </PageHeader>

  {#if documentId == null}
    <EmptyState title="No document selected" description="Choose a document from the Documents list to preview it here." />
  {:else if loading && !doc}
    <LoadingState message="Loading document…" />
  {:else if loadError && !doc}
    <EmptyState title="Could not load document" description={loadError} />
  {:else}
    <div
      class="min-h-0 flex-1 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-xl"
    >
      <DocumentViewer documentId={documentId!} />
    </div>
  {/if}
</div>
