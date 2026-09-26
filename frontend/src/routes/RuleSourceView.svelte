<script lang="ts">
  import { onMount } from "svelte";
  import {
    ArrowLeft,
    Route,
    FileQuestion,
    Heading,
    Pilcrow,
    Table2,
    Image as ImageIcon,
    List as ListIcon,
    Check,
    X,
    ArrowUpCircle,
    Link2,
  } from "lucide-svelte";
  import { documentsApi, ruleExtractionApi, rulesApi } from "../lib/api";
  import { toasts } from "../lib/toast.svelte";
  import { cn } from "../lib/utils/cn";
  import { createTableState } from "../lib/tableState.svelte";
  import type {
    DocumentDetail,
    DocumentElementKind,
    DraftSourceMapResponse,
    DraftSourceSummary,
    RuleFolder,
    RuleSourceMapResponse,
    RuleSourceSummary,
  } from "../lib/types";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import SeverityBadge from "../lib/components/SeverityBadge.svelte";
  import DocumentViewer from "../lib/components/DocumentViewer.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import RuleBulkEditModal from "../lib/components/rules/RuleBulkEditModal.svelte";

  interface Props {
    documentId: number | null;
    onBack: () => void;
  }

  let { documentId, onBack }: Props = $props();

  let mode: "rules" | "drafts" = $state("rules");

  let doc: DocumentDetail | null = $state(null);
  let map: RuleSourceMapResponse | null = $state(null);
  let draftMap: DraftSourceMapResponse | null = $state(null);
  let loading = $state(true);
  let loadError = $state("");
  let loadedForId: number | null = null;
  let draftActionInFlight: number | null = $state(null);

  let selectedElementId: string | null = $state(null);
  let selectedApproximate: RuleSourceSummary | null = $state(null);
  let selectedDraftElementId: string | null = $state(null);
  let selectedDraftApproximate: DraftSourceSummary | null = $state(null);
  /** The specific draft card selected in the Drafts tab, rendered as the proposed-rule panel next to the viewer. */
  let selectedDraft: DraftSourceSummary | null = $state(null);

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

  let folders: RuleFolder[] = $state([]);

  onMount(() => {
    updateViewerHeight();
    window.addEventListener("resize", updateViewerHeight);
    rulesApi.folders().then((f) => (folders = f)).catch(() => {});
    return () => window.removeEventListener("resize", updateViewerHeight);
  });

  $effect(() => {
    void doc;
    void loading;
    void mode;
    queueMicrotask(updateViewerHeight);
  });

  function loadMaps(id: number): Promise<void> {
    return Promise.all([documentsApi.get(id), documentsApi.getRuleSourceMap(id), documentsApi.getDraftSourceMap(id)])
      .then(([detail, sourceMap, draftSourceMap]) => {
        doc = detail;
        map = sourceMap;
        draftMap = draftSourceMap;
      })
      .catch((err: any) => {
        loadError = err.message || "Could not load this document's rule-source map.";
        toasts.error(loadError, "Rule-source map load failed");
      });
  }

  /** Reload just the draft map after a review/promote action -- promoting also changes the rule map. */
  function refreshMaps(): Promise<void> {
    if (documentId == null) return Promise.resolve();
    return Promise.all([documentsApi.getRuleSourceMap(documentId), documentsApi.getDraftSourceMap(documentId)]).then(
      ([sourceMap, draftSourceMap]) => {
        map = sourceMap;
        draftMap = draftSourceMap;
      },
    );
  }

  /** Find one draft by id across every bucket of the current draft map (mapped/unmapped/orphaned). */
  function findDraftById(draftId: number): DraftSourceSummary | null {
    if (!draftMap) return null;
    for (const el of draftMap.elements) {
      const hit = el.drafts.find((d) => d.id === draftId);
      if (hit) return hit;
    }
    return (
      draftMap.unmapped_drafts.find((d) => d.id === draftId) ??
      draftMap.orphaned_drafts.find((d) => d.id === draftId) ??
      null
    );
  }

  $effect(() => {
    const id = documentId;
    if (id == null) {
      doc = null;
      map = null;
      draftMap = null;
      loading = false;
      return;
    }
    if (loadedForId === id) return;
    loadedForId = id;
    loading = true;
    loadError = "";
    selectedElementId = null;
    selectedApproximate = null;
    selectedDraftElementId = null;
    selectedDraftApproximate = null;
    selectedDraft = null;
    relinkingDraftId = null;
    loadMaps(id).finally(() => {
      loading = false;
    });
  });

  let elementsWithRules = $derived((map?.elements ?? []).filter((el) => el.rules.length > 0));
  let totalMappedRules = $derived(elementsWithRules.reduce((n, el) => n + el.rules.length, 0));
  let orphanedRules = $derived(map?.orphaned_rules ?? []);
  // Every element (not just ones with rules) gets a count for the overlay --
  // zero-rule elements are dimmed there instead of just hidden from the sidebar.
  let elementRuleCounts = $derived(
    Object.fromEntries((map?.elements ?? []).map((el) => [el.element_id, el.rules.length])),
  );

  // Every rule currently shown in the Rules tab (mapped + approximate + orphaned),
  // flattened once for multi-select/bulk-edit -- the same table-state pattern
  // RulesView.svelte uses for its own rule list.
  let allRuleRows = $derived([
    ...elementsWithRules.flatMap((el) => el.rules),
    ...(map?.unmapped_rules ?? []),
    ...orphanedRules,
  ]);
  const ruleTable = createTableState<RuleSourceSummary, number>({
    rows: () => allRuleRows,
    getId: (r) => r.id,
  });

  let isBulkEditModalOpen = $state(false);
  let isBulkDeleteModalOpen = $state(false);
  let bulkActionBusy = $state(false);

  async function handleBulkUpdateRules(payload: {
    ruleset_id?: string;
    category?: string;
    mechanism?: string;
    severity?: string;
    needs_review?: number;
  }) {
    const res = await rulesApi.bulkUpdate({ rule_ids: ruleTable.selectedIdList, ...payload });
    toasts.success(`Updated ${res.success_count} rule(s).`);
    ruleTable.clearSelection();
    refreshMaps();
  }

  async function confirmBulkDeleteRules() {
    bulkActionBusy = true;
    try {
      const res = await rulesApi.bulkDelete(ruleTable.selectedIdList);
      toasts.success(`Deleted ${res.success_count} rule(s).`);
      ruleTable.clearSelection();
      isBulkDeleteModalOpen = false;
      refreshMaps();
    } catch (err: any) {
      toasts.error(err.message || "Could not delete selected rules.", "Bulk delete failed");
    } finally {
      bulkActionBusy = false;
    }
  }

  let elementsWithDrafts = $derived((draftMap?.elements ?? []).filter((el) => el.drafts.length > 0));
  let totalMappedDrafts = $derived(elementsWithDrafts.reduce((n, el) => n + el.drafts.length, 0));
  let orphanedDrafts = $derived(draftMap?.orphaned_drafts ?? []);
  let elementDraftCounts = $derived(
    Object.fromEntries((draftMap?.elements ?? []).map((el) => [el.element_id, el.drafts.length])),
  );

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

  /** Select one draft card: `elementId` set for an exact match, null for an approximate/orphaned one. */
  function selectDraft(draft: DraftSourceSummary, elementId: string | null) {
    selectedDraft = draft;
    if (elementId) {
      selectedDraftElementId = elementId;
      selectedDraftApproximate = null;
    } else {
      selectedDraftElementId = null;
      selectedDraftApproximate = draft;
    }
  }

  /** When set, the next overlay click relinks this draft instead of just selecting it. */
  let relinkingDraftId: number | null = $state(null);

  function handleViewerElementSelect(elementId: string | null) {
    if (!elementId) return;
    if (mode === "drafts" && relinkingDraftId != null) {
      relinkDraft(relinkingDraftId, elementId);
      return;
    }
    if (mode === "rules") {
      selectExact(elementId);
      return;
    }
    // Clicking the overlay directly (not a card) selects the first draft at that element, if any.
    const el = elementsWithDrafts.find((e) => e.element_id === elementId);
    if (el && el.drafts.length > 0) {
      selectDraft(el.drafts[0], elementId);
    } else {
      selectedDraft = null;
      selectedDraftApproximate = null;
      selectedDraftElementId = elementId;
    }
  }

  function startRelink(draftId: number) {
    relinkingDraftId = relinkingDraftId === draftId ? null : draftId;
  }

  async function relinkDraft(draftId: number, elementId: string) {
    draftActionInFlight = draftId;
    relinkingDraftId = null;
    try {
      await ruleExtractionApi.relinkDraftSource(draftId, elementId);
      toasts.success("Draft relinked to the new element.");
      await refreshMaps();
      const relinked = findDraftById(draftId);
      if (relinked) selectDraft(relinked, elementId);
    } catch (err: any) {
      toasts.error(err.message || "Could not relink this draft.", "Relink failed");
    } finally {
      draftActionInFlight = null;
    }
  }

  async function reviewDraft(draftId: number, status: "accepted" | "rejected") {
    draftActionInFlight = draftId;
    try {
      await ruleExtractionApi.reviewDraft(draftId, { status });
      refreshMaps();
    } catch (err: any) {
      toasts.error(err.message || "Could not review this draft.", "Review failed");
    } finally {
      draftActionInFlight = null;
    }
  }

  async function promoteDraftRow(draftId: number) {
    draftActionInFlight = draftId;
    try {
      const result = await ruleExtractionApi.promoteDraft(draftId);
      const issueCount = result.alignment_issues?.length ?? 0;
      const conflictCount = result.conflicts?.length ?? 0;
      if (issueCount === 0 && conflictCount === 0) {
        toasts.success("Draft promoted to the rules library.");
      } else {
        toasts.warning(
          `Draft promoted, flagged for review (${issueCount} ontology warning(s), ${conflictCount} conflicting rule(s)).`,
          "Promoted with warnings",
        );
      }
      refreshMaps();
    } catch (err: any) {
      toasts.error(err.message || "Could not promote this draft.", "Promotion failed");
    } finally {
      draftActionInFlight = null;
    }
  }
</script>

<div class="flex h-full flex-col space-y-5 pb-12">
  <PageHeader
    category="Documents"
    title={doc ? `Rule-Source Map — ${doc.filename}` : loading ? "Loading rule-source map…" : "Rule-Source Map"}
    subtitle={mode === "rules"
      ? map
        ? `${totalMappedRules} rule(s) mapped to ${elementsWithRules.length} element(s)${map.unmapped_rules.length ? `, ${map.unmapped_rules.length} approximate` : ""}${orphanedRules.length ? `, ${orphanedRules.length} need re-linking` : ""}`
        : ""
      : draftMap
        ? `${totalMappedDrafts} pending draft(s) mapped to ${elementsWithDrafts.length} element(s)${draftMap.unmapped_drafts.length ? `, ${draftMap.unmapped_drafts.length} approximate` : ""}${orphanedDrafts.length ? `, ${orphanedDrafts.length} need re-linking` : ""}`
        : ""}
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
  {:else}
    <div class="flex gap-1.5 rounded-xl border border-border-default bg-surface-card p-1 self-start">
      <button
        type="button"
        onclick={() => {
          mode = "rules";
          relinkingDraftId = null;
        }}
        class={cn(
          "rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
          mode === "rules" ? "bg-accent/15 text-accent" : "text-fg-secondary hover:text-fg-primary",
        )}
      >
        Rules ({totalMappedRules + (map?.unmapped_rules.length ?? 0) + orphanedRules.length})
      </button>
      <button
        type="button"
        onclick={() => (mode = "drafts")}
        class={cn(
          "rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors",
          mode === "drafts" ? "bg-accent/15 text-accent" : "text-fg-secondary hover:text-fg-primary",
        )}
      >
        Pending Drafts ({totalMappedDrafts + (draftMap?.unmapped_drafts.length ?? 0) + orphanedDrafts.length})
      </button>
    </div>

    {#if mode === "rules" && ruleTable.selectedCount > 0}
      <BulkActionBar
        selectedCount={ruleTable.selectedCount}
        itemLabel="rule"
        onClearSelection={() => ruleTable.clearSelection()}
        onBulkEdit={() => (isBulkEditModalOpen = true)}
        onBulkDelete={() => (isBulkDeleteModalOpen = true)}
      />
    {/if}

    {#snippet ruleCard(rule: RuleSourceSummary, isSelected: boolean, onClick: () => void)}
      <div
        class={cn(
          "flex w-full items-start gap-2 rounded-xl border px-3 py-2 transition-colors",
          isSelected
            ? "border-accent/50 bg-accent/10"
            : "border-border-default bg-surface-overlay hover:bg-surface-hover",
        )}
      >
        <div class="pt-0.5">
          <TableCheckbox
            checked={ruleTable.isSelected(rule.id)}
            onchange={() => ruleTable.toggleSelect(rule.id)}
            ariaLabel={`Select ${rule.rule_id || `rule #${rule.id}`}`}
          />
        </div>
        <button type="button" onclick={onClick} class="flex flex-1 flex-col items-start gap-1 text-left">
          <div class="flex w-full items-center justify-between gap-2">
            <span class="truncate text-xs font-semibold text-fg-primary">{rule.rule_id || `Rule #${rule.id}`}</span>
            <SeverityBadge severity={rule.severity || "recommended"} size="xs" />
          </div>
          {#if rule.description}
            <span class="line-clamp-2 text-caption text-fg-secondary">{rule.description}</span>
          {/if}
        </button>
      </div>
    {/snippet}

    {#snippet draftCard(draft: DraftSourceSummary, isSelected: boolean, onClick: () => void)}
      {@const busy = draftActionInFlight === draft.id}
      <div
        class={cn(
          "flex w-full flex-col items-start gap-1.5 rounded-xl border px-3 py-2 text-left transition-colors",
          isSelected ? "border-accent/50 bg-accent/10" : "border-border-default bg-surface-overlay",
        )}
      >
        <button type="button" onclick={onClick} class="flex w-full flex-col items-start gap-1 text-left">
          <div class="flex w-full items-center justify-between gap-2">
            <span class="truncate text-xs font-semibold text-fg-primary">{draft.rule_id || `Draft #${draft.id}`}</span>
            <div class="flex items-center gap-1.5">
              <span class="rounded-md border border-border-default px-1.5 py-0.5 text-micro font-semibold uppercase tracking-wider text-fg-muted">
                {draft.status.replace("_", " ")}
              </span>
              <SeverityBadge severity={draft.severity || "recommended"} size="xs" />
            </div>
          </div>
          {#if draft.description}
            <span class="line-clamp-2 text-caption text-fg-secondary">{draft.description}</span>
          {/if}
        </button>
        {#if draft.status === "pending_review"}
          <div class="flex w-full items-center gap-1.5 pt-0.5">
            <button
              type="button"
              disabled={busy}
              onclick={() => reviewDraft(draft.id, "accepted")}
              class="inline-flex items-center gap-1 rounded-md border border-success-border bg-success-bg px-2 py-1 text-micro font-semibold text-success transition-colors hover:bg-success-bg/70 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Check class="h-3 w-3" /> Accept
            </button>
            <button
              type="button"
              disabled={busy}
              onclick={() => reviewDraft(draft.id, "rejected")}
              class="inline-flex items-center gap-1 rounded-md border border-critical-border bg-critical-bg px-2 py-1 text-micro font-semibold text-critical transition-colors hover:bg-critical-bg/70 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <X class="h-3 w-3" /> Reject
            </button>
          </div>
        {:else if draft.status === "accepted" || draft.status === "edited"}
          <button
            type="button"
            disabled={busy}
            onclick={() => promoteDraftRow(draft.id)}
            class="inline-flex items-center gap-1 rounded-md border border-accent/40 bg-accent/10 px-2 py-1 text-micro font-semibold text-accent transition-colors hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ArrowUpCircle class="h-3 w-3" /> Promote
          </button>
        {/if}
        <button
          type="button"
          disabled={busy}
          onclick={() => startRelink(draft.id)}
          class={cn(
            "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-micro font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50",
            relinkingDraftId === draft.id
              ? "border-accent bg-accent/20 text-accent"
              : "border-border-default text-fg-secondary hover:bg-surface-hover",
          )}
        >
          <Link2 class="h-3 w-3" />
          {relinkingDraftId === draft.id ? "Click an element to relink…" : "Relink"}
        </button>
      </div>
    {/snippet}

    {#if mode === "rules" && elementsWithRules.length === 0 && (map?.unmapped_rules.length ?? 0) === 0 && orphanedRules.length === 0}
      <EmptyState
        icon={FileQuestion}
        title="No rules extracted from this document yet"
        description="Run Rule Extraction on this document to build its rule-source map."
      />
    {:else if mode === "drafts" && elementsWithDrafts.length === 0 && (draftMap?.unmapped_drafts.length ?? 0) === 0 && orphanedDrafts.length === 0}
      <EmptyState
        icon={FileQuestion}
        title="No pending drafts for this document"
        description="Run Rule Extraction on this document to generate reviewable draft rules."
      />
    {:else}
      <div bind:this={viewerContainerEl} style="height: {viewerHeight};" class="flex gap-4 overflow-hidden">
        <div class="flex w-[380px] shrink-0 flex-col overflow-y-auto rounded-2xl border border-border-default bg-surface-card shadow-xl">
          <div class="space-y-4 p-4">
            {#if mode === "rules"}
              {#if allRuleRows.length > 0}
                <div class="flex items-center gap-2 border-b border-border-subtle pb-2 text-micro text-fg-muted">
                  <TableCheckbox
                    checked={ruleTable.allFilteredSelected}
                    indeterminate={ruleTable.someFilteredSelected}
                    onchange={() => ruleTable.toggleSelectAll()}
                    ariaLabel="Select all rules"
                  />
                  <span>Select all ({allRuleRows.length})</span>
                </div>
              {/if}
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
                      {@render ruleCard(rule, selectedElementId === el.element_id, () => selectExact(el.element_id))}
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
                      {@render ruleCard(rule, selectedApproximate?.id === rule.id, () => selectApproximate(rule))}
                    {/each}
                  </div>
                </div>
              {/if}

              {#if orphanedRules.length > 0}
                <div class="space-y-1.5 border-t border-border-subtle pt-3">
                  <div class="text-micro font-semibold uppercase tracking-wider text-warning">
                    Needs re-linking ({orphanedRules.length})
                  </div>
                  <p class="text-caption text-fg-muted">
                    Linked to an element that no longer exists — the source document was likely re-parsed or
                    re-uploaded since this rule was extracted. Highlighted by page/bbox only until re-linked.
                  </p>
                  <div class="space-y-1.5">
                    {#each orphanedRules as rule (rule.id)}
                      {@render ruleCard(rule, selectedApproximate?.id === rule.id, () => selectApproximate(rule))}
                    {/each}
                  </div>
                </div>
              {/if}
            {:else}
              {#each elementsWithDrafts as el (el.element_id)}
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
                    {#each el.drafts as draft (draft.id)}
                      {@render draftCard(draft, selectedDraft?.id === draft.id, () => selectDraft(draft, el.element_id))}
                    {/each}
                  </div>
                </div>
              {/each}

              {#if draftMap && draftMap.unmapped_drafts.length > 0}
                <div class="space-y-1.5 border-t border-border-subtle pt-3">
                  <div class="text-micro font-semibold uppercase tracking-wider text-fg-muted">
                    Approximate match ({draftMap.unmapped_drafts.length})
                  </div>
                  <p class="text-caption text-fg-muted">
                    Extracted before exact element linkage existed — highlighted by page/bbox only.
                  </p>
                  <div class="space-y-1.5">
                    {#each draftMap.unmapped_drafts as draft (draft.id)}
                      {@render draftCard(draft, selectedDraft?.id === draft.id, () => selectDraft(draft, null))}
                    {/each}
                  </div>
                </div>
              {/if}

              {#if orphanedDrafts.length > 0}
                <div class="space-y-1.5 border-t border-border-subtle pt-3">
                  <div class="text-micro font-semibold uppercase tracking-wider text-warning">
                    Needs re-linking ({orphanedDrafts.length})
                  </div>
                  <p class="text-caption text-fg-muted">
                    Linked to an element that no longer exists — the source document was likely re-parsed or
                    re-uploaded since this draft was extracted. Highlighted by page/bbox only until re-linked.
                  </p>
                  <div class="space-y-1.5">
                    {#each orphanedDrafts as draft (draft.id)}
                      {@render draftCard(draft, selectedDraft?.id === draft.id, () => selectDraft(draft, null))}
                    {/each}
                  </div>
                </div>
              {/if}
            {/if}
          </div>
        </div>

        {#if mode === "drafts"}
          <div class="flex w-[340px] shrink-0 flex-col overflow-y-auto rounded-2xl border border-border-default bg-surface-card shadow-xl">
            <div class="space-y-4 p-4">
              <div class="text-micro font-semibold uppercase tracking-wider text-fg-muted">Proposed Rule</div>
              {#if !selectedDraft}
                <EmptyState
                  title="No draft selected"
                  description="Select a draft on the left to see its proposed rule here, next to the source it was extracted from."
                />
              {:else}
                {@const pr = selectedDraft.proposed_rule}
                <div class="space-y-1.5">
                  <div class="flex items-start justify-between gap-2">
                    <h3 class="text-sm font-bold text-fg-primary">{selectedDraft.rule_id || `Draft #${selectedDraft.id}`}</h3>
                    <SeverityBadge severity={selectedDraft.severity || "recommended"} size="xs" />
                  </div>
                  {#if selectedDraft.description}
                    <p class="text-xs leading-relaxed text-fg-secondary">{selectedDraft.description}</p>
                  {/if}
                </div>

                {#if pr}
                  <dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-micro">
                    <dt class="uppercase tracking-wider text-fg-muted">Target class</dt>
                    <dd class="wrap-break-word font-mono text-fg-secondary">{pr.target_ifc_class || "—"}</dd>
                    <dt class="uppercase tracking-wider text-fg-muted">Property</dt>
                    <dd class="wrap-break-word font-mono text-fg-secondary">
                      {pr.property_set || "Pset_Compliance"}.{pr.property_name || "—"}
                    </dd>
                    <dt class="uppercase tracking-wider text-fg-muted">Check</dt>
                    <dd class="wrap-break-word font-mono text-fg-secondary">
                      {pr.operator || "=="}
                      {pr.check_value ?? [pr.value_min, pr.value_max].filter((v) => v != null && v !== "").join(" – ")}
                      {pr.unit || ""}
                    </dd>
                    <dt class="uppercase tracking-wider text-fg-muted">Mechanism</dt>
                    <dd class="font-mono text-fg-secondary">{pr.mechanism || "—"}</dd>
                    <dt class="uppercase tracking-wider text-fg-muted">Confidence</dt>
                    <dd class="font-mono text-fg-secondary">{selectedDraft.confidence.toFixed(2)}</dd>
                    <dt class="uppercase tracking-wider text-fg-muted">Method</dt>
                    <dd class="wrap-break-word font-mono text-fg-secondary">{selectedDraft.extraction_method}</dd>
                  </dl>

                  {#if pr.rase_requirement}
                    <div class="space-y-1 border-t border-border-subtle pt-3">
                      <div class="text-micro font-semibold uppercase tracking-wider text-fg-muted">Requirement</div>
                      <p class="text-caption italic leading-relaxed text-fg-secondary">"{pr.rase_requirement}"</p>
                    </div>
                  {/if}
                {/if}
              {/if}
            </div>
          </div>
        {/if}

        <div class="flex flex-1 flex-col gap-2 overflow-hidden">
          {#if relinkingDraftId != null}
            <div class="flex items-center justify-between gap-2 rounded-xl border border-accent/40 bg-accent/10 px-3 py-2 text-xs text-accent">
              <span class="flex items-center gap-1.5 font-semibold">
                <Link2 class="h-3.5 w-3.5" />
                Click the correct element on the right to relink this draft.
              </span>
              <button type="button" onclick={() => (relinkingDraftId = null)} class="font-semibold hover:underline">
                Cancel
              </button>
            </div>
          {/if}
          <div class="flex-1 overflow-hidden rounded-2xl border border-border-default bg-surface-card shadow-xl">
          <DocumentViewer
            documentId={documentId!}
            selectedElementId={mode === "rules"
              ? selectedApproximate
                ? null
                : selectedElementId
              : selectedDraftApproximate
                ? null
                : selectedDraftElementId}
            page={mode === "rules" ? (selectedApproximate?.source_page_number ?? null) : (selectedDraftApproximate?.source_page_number ?? null)}
            bbox={mode === "rules" ? (selectedApproximate?.source_bbox ?? null) : (selectedDraftApproximate?.source_bbox ?? null)}
            elementRuleCounts={mode === "rules" ? elementRuleCounts : elementDraftCounts}
            badgeMode="rule-count"
            onElementSelect={handleViewerElementSelect}
          />
          </div>
        </div>
      </div>
    {/if}
  {/if}
</div>

<RuleBulkEditModal
  isOpen={isBulkEditModalOpen}
  selectedCount={ruleTable.selectedCount}
  {folders}
  onClose={() => (isBulkEditModalOpen = false)}
  onUpdate={handleBulkUpdateRules}
/>

<ConfirmModal
  bind:isOpen={isBulkDeleteModalOpen}
  title={`Delete ${ruleTable.selectedCount} Rules`}
  message={`This will permanently delete ${ruleTable.selectedCount} selected rule(s). This action cannot be undone.`}
  confirmText={bulkActionBusy ? "Deleting…" : "Delete"}
  onConfirm={confirmBulkDeleteRules}
  onCancel={() => (isBulkDeleteModalOpen = false)}
/>
