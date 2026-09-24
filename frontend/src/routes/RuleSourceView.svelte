<script lang="ts">
  import { onMount } from "svelte";
  import { ArrowLeft, Route, FileQuestion, Heading, Pilcrow, Table2, Image as ImageIcon, List as ListIcon } from "lucide-svelte";
  import { documentsApi } from "../lib/api";
  import { toasts } from "../lib/toast.svelte";
  import { cn } from "../lib/utils/cn";
  import type { DocumentDetail, DocumentElementKind, DocumentElementWithRules, RuleSourceMapResponse, RuleSourceSummary } from "../lib/types";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import SeverityBadge from "../lib/components/SeverityBadge.svelte";
  import DocumentViewer from "../lib/components/DocumentViewer.svelte";

  interface Props {
    documentId: number | null;
    onBack: () => void;
  }

  let { documentId, onBack }: Props = $props();

  let doc: DocumentDetail | null = $state(null);
  let map: RuleSourceMapResponse | null = $state(null);
  let loading = $state(true);
  let loadError = $state("");
  let loadedForId: number | null = null;

  let selectedElementId: string | null = $state(null);
  let selectedApproximate: RuleSourceSummary | null = $state(null);

  // Same fixed-height, self-measuring viewer pane pattern as DocumentView.svelte
  // -- the app shell's <main> grows to fit content rather than being
  // height-bounded, so the split viewer pane pins its own height instead.
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
    void doc;
    void loading;
    queueMicrotask(updateViewerHeight);
  });

  $effect(() => {
    const id = documentId;
    if (id == null) {
      doc = null;
      map = null;
      loading = false;
      return;
    }
    if (loadedForId === id) return;
    loadedForId = id;
    loading = true;
    loadError = "";
    selectedElementId = null;
    selectedApproximate = null;
    Promise.all([documentsApi.get(id), documentsApi.getRuleSourceMap(id)])
      .then(([detail, sourceMap]) => {
        doc = detail;
        map = sourceMap;
      })
      .catch((err: any) => {
        loadError = err.message || "Could not load this document's rule-source map.";
        toasts.error(loadError, "Rule-source map load failed");
      })
      .finally(() => {
        loading = false;
      });
  });

  let elementsWithRules = $derived((map?.elements ?? []).filter((el) => el.rules.length > 0));
  let totalMappedRules = $derived(elementsWithRules.reduce((n, el) => n + el.rules.length, 0));

  const KIND_ICON: Record<DocumentElementKind, typeof Heading> = {
    heading: Heading,
    paragraph: Pilcrow,
    list: ListIcon,
    table: Table2,
    picture: ImageIcon,
  };

  function selectExact(elementId: string) {
    selectedApproximate = null;
    selectedElementId = elementId;
  }

  function selectApproximate(rule: RuleSourceSummary) {
    selectedElementId = null;
    selectedApproximate = rule;
  }

  function handleViewerElementSelect(elementId: string | null) {
    if (elementId) selectExact(elementId);
  }
</script>

<div class="flex h-full flex-col space-y-5 pb-12">
  <PageHeader
    category="Documents"
    title={doc ? `Rule-Source Map — ${doc.filename}` : loading ? "Loading rule-source map…" : "Rule-Source Map"}
    subtitle={map ? `${totalMappedRules} rule(s) mapped to ${elementsWithRules.length} element(s)${map.unmapped_rules.length ? `, ${map.unmapped_rules.length} approximate` : ""}` : ""}
    icon={Route}
  >
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
    <EmptyState title="No document selected" description="Choose a document from the Documents list to see its rule-source map." />
  {:else if loading && !map}
    <LoadingState message="Loading rule-source map…" />
  {:else if loadError && !map}
    <EmptyState title="Could not load rule-source map" description={loadError} />
  {:else if map && elementsWithRules.length === 0 && map.unmapped_rules.length === 0}
    <EmptyState
      icon={FileQuestion}
      title="No rules extracted from this document yet"
      description="Run Rule Extraction on this document to build its rule-source map."
    />
  {:else}
    <div bind:this={viewerContainerEl} style="height: {viewerHeight};" class="flex gap-4 overflow-hidden">
      <div class="flex w-[380px] shrink-0 flex-col overflow-y-auto rounded-2xl border border-border-default bg-surface-card shadow-xl">
        <div class="space-y-4 p-4">
          {#each elementsWithRules as el (el.element_id)}
            {@const Icon = KIND_ICON[el.kind]}
            <div class="space-y-1.5">
              <div class="flex items-center gap-1.5 text-micro font-semibold uppercase tracking-wider text-fg-muted">
                <Icon class="h-3 w-3" />
                <span>{el.kind}</span>
                {#if el.page_number}
                  <span class="text-fg-muted/70">· page {el.page_number}</span>
                {/if}
              </div>
              <div class="space-y-1.5">
                {#each el.rules as rule (rule.id)}
                  <button
                    type="button"
                    onclick={() => selectExact(el.element_id)}
                    class={cn(
                      "flex w-full flex-col items-start gap-1 rounded-xl border px-3 py-2 text-left transition-colors",
                      selectedElementId === el.element_id
                        ? "border-accent/50 bg-accent/10"
                        : "border-border-default bg-surface-overlay hover:bg-surface-hover",
                    )}
                  >
                    <div class="flex w-full items-center justify-between gap-2">
                      <span class="truncate text-xs font-semibold text-fg-primary">{rule.rule_id || `Rule #${rule.id}`}</span>
                      <SeverityBadge severity={rule.severity || "recommended"} size="xs" />
                    </div>
                    {#if rule.description}
                      <span class="line-clamp-2 text-caption text-fg-secondary">{rule.description}</span>
                    {/if}
                  </button>
                {/each}
              </div>
            </div>
          {/each}

          {#if map && map.unmapped_rules.length > 0}
            <div class="space-y-1.5 border-t border-border-subtle pt-3">
              <div class="text-micro font-semibold uppercase tracking-wider text-fg-muted">
                Approximate match ({map.unmapped_rules.length})
              </div>
              <p class="text-caption text-fg-muted">
                Extracted before exact element linkage existed — highlighted by page/bbox only.
              </p>
              <div class="space-y-1.5">
                {#each map.unmapped_rules as rule (rule.id)}
                  <button
                    type="button"
                    onclick={() => selectApproximate(rule)}
                    class={cn(
                      "flex w-full flex-col items-start gap-1 rounded-xl border px-3 py-2 text-left transition-colors",
                      selectedApproximate?.id === rule.id
                        ? "border-accent/50 bg-accent/10"
                        : "border-border-default bg-surface-overlay hover:bg-surface-hover",
                    )}
                  >
                    <div class="flex w-full items-center justify-between gap-2">
                      <span class="truncate text-xs font-semibold text-fg-primary">{rule.rule_id || `Rule #${rule.id}`}</span>
                      <SeverityBadge severity={rule.severity || "recommended"} size="xs" />
                    </div>
                    {#if rule.description}
                      <span class="line-clamp-2 text-caption text-fg-secondary">{rule.description}</span>
                    {/if}
                  </button>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      </div>

      <div class="flex-1 overflow-hidden rounded-2xl border border-border-default bg-surface-card shadow-xl">
        <DocumentViewer
          documentId={documentId!}
          selectedElementId={selectedApproximate ? null : selectedElementId}
          page={selectedApproximate?.source_page_number ?? null}
          bbox={selectedApproximate?.source_bbox ?? null}
          onElementSelect={handleViewerElementSelect}
        />
      </div>
    </div>
  {/if}
</div>
