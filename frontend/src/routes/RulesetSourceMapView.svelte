<script lang="ts">
  import { push } from "svelte-spa-router";
  import { ArrowLeft, Route, BookOpen } from "lucide-svelte";
  import { rulesApi } from "../lib/api";
  import { authState } from "../lib/auth.svelte";
  import { toasts } from "../lib/toast.svelte";
  import type { RulesetSourceMapResponse } from "../lib/types";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";

  interface Props {
    rulesetId: string | null;
    onBack: () => void;
  }

  let { rulesetId, onBack }: Props = $props();

  let map: RulesetSourceMapResponse | null = $state(null);
  let loading = $state(true);
  let loadError = $state("");
  let loadedForId: string | null = null;

  $effect(() => {
    const id = rulesetId;
    if (id == null) {
      map = null;
      loading = false;
      return;
    }
    if (loadedForId === id) return;
    loadedForId = id;
    loading = true;
    loadError = "";
    rulesApi
      .getRulesetSourceMap(id)
      .then((res) => {
        map = res;
      })
      .catch((err: any) => {
        loadError = err?.message || "Could not load this ruleset's source map.";
        toasts.error(loadError, "Source map load failed");
      })
      .finally(() => {
        loading = false;
      });
  });

  function openDocument(documentId: number) {
    const params = new URLSearchParams();
    params.set("doc_id", String(documentId));
    if (authState.activeOrganizationId) {
      params.set("org", String(authState.activeOrganizationId));
    }
    push(`/rule-source?${params.toString()}`);
  }
</script>

<div class="space-y-5 pb-12">
  <PageHeader
    category="Rules & Standards"
    title={rulesetId ? `Source Map — ${rulesetId}` : "Source Map"}
    subtitle="Documents this ruleset's rules were extracted from"
    icon={Route}
  >
    {#snippet actions()}
      <button
        type="button"
        onclick={onBack}
        class="inline-flex items-center gap-1.5 rounded-xl border border-border-default bg-surface-card px-3.5 py-2 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
      >
        <ArrowLeft class="h-3.5 w-3.5" />
        <span>Back to Rules Catalog</span>
      </button>
    {/snippet}
  </PageHeader>

  {#if rulesetId == null}
    <EmptyState title="No ruleset selected" description="Choose a ruleset from the Rules Catalog to see its source map." />
  {:else if loading && !map}
    <LoadingState message="Loading source map…" />
  {:else if loadError && !map}
    <EmptyState title="Could not load source map" description={loadError} />
  {:else if map && map.documents.length === 0}
    <EmptyState
      title="No source documents"
      description="None of this ruleset's rules are linked back to a source document yet."
    />
  {:else if map}
    <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {#each map.documents as doc (doc.document_id)}
        {@const mapped = doc.elements.reduce((n, el) => n + el.rules.length, 0)}
        <button
          type="button"
          onclick={() => openDocument(doc.document_id)}
          class="flex flex-col items-start gap-2 rounded-2xl border border-border-default bg-surface-card p-4 text-left shadow-xl transition-colors hover:bg-surface-hover"
        >
          <div class="flex items-center gap-2">
            <BookOpen class="h-4 w-4 shrink-0 text-accent" />
            <span class="truncate text-sm font-semibold text-fg-primary">{doc.filename}</span>
          </div>
          <div class="flex flex-wrap gap-x-3 gap-y-1 text-caption text-fg-muted">
            <span>{mapped} mapped</span>
            {#if doc.unmapped_rules.length}
              <span>{doc.unmapped_rules.length} approximate</span>
            {/if}
            {#if doc.orphaned_rules.length}
              <span class="text-warning">{doc.orphaned_rules.length} need re-linking</span>
            {/if}
          </div>
        </button>
      {/each}
    </div>
  {/if}
</div>
