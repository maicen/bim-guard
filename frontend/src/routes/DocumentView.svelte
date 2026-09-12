<script lang="ts">
  import { onMount } from "svelte";
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

  // The app shell's <main> declares overflow-y-auto but is never actually
  // height-bounded (its ancestor chain uses min-h-screen, not h-screen, so
  // it grows to fit content and the whole page scrolls -- fine for normal
  // routes, but this page's three-pane viewer needs a real fixed-height,
  // internally-scrolling box). Measuring the viewer's own top and pinning
  // its height to the remaining viewport avoids depending on that chain.
  let viewerContainerEl: HTMLDivElement | undefined = $state();
  let viewerHeight = $state("70vh");

  function updateViewerHeight() {
    if (!viewerContainerEl) return;
    const top = viewerContainerEl.getBoundingClientRect().top;
    viewerHeight = `calc(100vh - ${Math.round(top)}px - 1.5rem)`;
  }

  onMount(() => {
    updateViewerHeight();
    window.addEventListener("resize", updateViewerHeight);
    return () => window.removeEventListener("resize", updateViewerHeight);
  });

  $effect(() => {
    // Re-measure once the header settles into its loaded state (its own
    // height can change between the "Loading document…" title and the
    // final filename/badge/subtitle row).
    void doc;
    void loading;
    queueMicrotask(updateViewerHeight);
  });

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
          class="rounded-md border border-accent/30 bg-accent/10 px-2 py-0.5 text-caption font-medium text-accent"
        >
          {doc.doc_type}
        </span>
      {/if}
    {/snippet}
    {#snippet actions()}
      <button
        type="button"
        onclick={onBack}
        class="inline-flex items-center gap-1.5 rounded-xl border border-border-default bg-surface-card px-3.5 py-2 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
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
      bind:this={viewerContainerEl}
      style="height: {viewerHeight};"
      class="overflow-hidden rounded-2xl border border-border-default bg-surface-card shadow-xl"
    >
      <DocumentViewer documentId={documentId!} />
    </div>
  {/if}
</div>
