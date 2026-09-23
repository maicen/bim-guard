<script lang="ts">
  import { untrack } from "svelte";
  import { ClipboardCheck, RefreshCw, Search } from "lucide-svelte";
  import { evaluationApi } from "../lib/api";
  import { Select } from "../lib/components/ui";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import { createTableState } from "../lib/tableState.svelte";
  import type { EvaluationBimguardVerdict, EvaluationFinding, EvaluationHumanVerdict } from "../lib/types";

  interface Props {
    initialProjectId?: number | null;
  }

  let { initialProjectId = null }: Props = $props();

  let selectedProjectId: number | null = $state(untrack(() => initialProjectId));
  $effect(() => {
    if (initialProjectId !== undefined && initialProjectId !== selectedProjectId) {
      selectedProjectId = initialProjectId;
      load();
    }
  });

  let findings: EvaluationFinding[] = $state.raw([]);
  let loading = $state(false);
  let error = $state("");
  let isBulkDeleteModalOpen = $state(false);
  let isBulkConfirming = $state(false);

  // A rule's "correct" outcome maps onto a smaller human vocabulary: a
  // missing property means the reviewer genuinely can't tell (INDETERMINATE),
  // and a waived violation is, by definition, not a violation (NOT_APPLICABLE).
  const BIMGUARD_TO_HUMAN: Record<EvaluationBimguardVerdict, EvaluationHumanVerdict> = {
    PASS: "PASS",
    FAIL: "FAIL",
    MISSING: "INDETERMINATE",
    WAIVED: "NOT_APPLICABLE",
    NOT_APPLICABLE: "NOT_APPLICABLE",
  };

  const VERDICT_OPTIONS = [
    { value: "PASS", label: "Pass" },
    { value: "FAIL", label: "Fail" },
    { value: "NOT_APPLICABLE", label: "Not applicable" },
    { value: "INDETERMINATE", label: "Indeterminate" },
  ];

  const VERDICT_CLASS: Record<string, string> = {
    PASS: "bg-success-bg border-success-border text-success",
    FAIL: "bg-critical-bg border-critical-border text-critical",
    MISSING: "bg-caution-bg border-caution-border text-caution",
    WAIVED: "bg-caution-bg border-caution-border text-caution",
    NOT_APPLICABLE: "bg-info-bg border-info-border text-info",
    INDETERMINATE: "bg-info-bg border-info-border text-info",
  };

  function ruleLabel(finding: EvaluationFinding): string {
    const snapshot = finding.rule_snapshot || {};
    return (snapshot.rule_ref as string) || (snapshot.rule_desc as string) || `Rule ${finding.rule_id ?? "?"}`;
  }

  async function load() {
    if (!selectedProjectId) {
      findings = [];
      return;
    }
    loading = true;
    error = "";
    try {
      const res = await evaluationApi.listFindings(selectedProjectId);
      findings = res.findings;
    } catch (err: any) {
      error = err.message || "Failed to load evaluation findings.";
    } finally {
      loading = false;
    }
  }
  load();

  const table = createTableState<EvaluationFinding, number>({
    rows: () => findings,
    getId: (f) => f.id,
    searchFields: (f) => [f.element_name, f.element_global_id, ruleLabel(f), f.storey, f.space],
    filters: {
      reviewed: (f, v) => (v === "reviewed" ? !!f.human_verdict : !f.human_verdict),
      agreement: (f, v) => {
        if (!f.human_verdict) return false;
        const agrees = f.human_verdict === BIMGUARD_TO_HUMAN[f.bimguard_verdict];
        return v === "agree" ? agrees : !agrees;
      },
    },
    initialSort: { field: "id", asc: false },
  });

  async function reviewOne(finding: EvaluationFinding, verdict: EvaluationHumanVerdict) {
    try {
      const updated = await evaluationApi.reviewFinding(finding.id, { human_verdict: verdict });
      findings = findings.map((f) => (f.id === finding.id ? updated : f));
    } catch (err: any) {
      error = err.message || `Failed to review finding ${finding.id}.`;
    }
  }

  /** Each selected row is confirmed against its own BIM-Guard verdict, not one shared value. */
  async function confirmSelectedAsCorrect() {
    if (isBulkConfirming) return;
    isBulkConfirming = true;
    error = "";
    try {
      // A one-shot local grouping, never read reactively, so the plain
      // built-in is correct here.
      // eslint-disable-next-line svelte/prefer-svelte-reactivity
      const groups = new Map<EvaluationHumanVerdict, number[]>();
      for (const row of table.selectedRows) {
        const verdict = BIMGUARD_TO_HUMAN[row.bimguard_verdict];
        groups.set(verdict, [...(groups.get(verdict) ?? []), row.id]);
      }
      await Promise.all(
        [...groups.entries()].map(([human_verdict, finding_ids]) =>
          evaluationApi.bulkReview({ finding_ids, human_verdict }),
        ),
      );
      table.clearSelection();
      await load();
    } catch (err: any) {
      error = err.message || "Failed to confirm the selected findings.";
    } finally {
      isBulkConfirming = false;
    }
  }

  async function confirmBulkDelete() {
    const ids = table.selectedIdList;
    try {
      await evaluationApi.bulkDelete(ids);
      table.clearSelection();
      await load();
    } catch (err: any) {
      error = err.message || "Failed to remove the selected findings.";
    } finally {
      isBulkDeleteModalOpen = false;
    }
  }
</script>

<div class="mx-auto max-w-7xl space-y-5">
  <PageHeader
    category="Analysis"
    title="Compliance Evaluation"
    subtitle="Confirm or override BIM-Guard's PASS/FAIL verdicts. bim-guard-evaluation scores agreement between the two columns below into a confusion matrix, precision, recall, and F1."
    icon={ClipboardCheck}
  >
    {#snippet actions()}
      <button
        type="button"
        onclick={load}
        disabled={loading || !selectedProjectId}
        class="inline-flex items-center gap-1.5 rounded-xl border border-border-interactive bg-surface-overlay px-3 py-2 text-xs font-semibold text-fg-secondary transition-colors hover:bg-surface-hover disabled:opacity-50"
      >
        <RefreshCw class="h-3.5 w-3.5 {loading ? 'animate-spin' : ''}" />
        Refresh
      </button>
    {/snippet}
  </PageHeader>

  {#if !selectedProjectId}
    <EmptyState
      title="No project selected"
      description="Select a project to review its captured evaluation findings."
    />
  {:else if loading}
    <LoadingState message="Loading evaluation findings…" />
  {:else if error}
    <div class="rounded-xl border border-critical-border bg-critical-bg p-4 text-xs text-critical">{error}</div>
  {:else if findings.length === 0}
    <EmptyState
      title="Nothing captured yet"
      description='Run a compliance audit, then use "Capture for Evaluation" to snapshot its results here for review.'
    />
  {:else}
    <div class="flex flex-wrap items-center gap-3">
      <div class="relative w-full max-w-xs">
        <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted" />
        <input
          type="text"
          bind:value={table.search}
          placeholder="Search rule, element, storey…"
          class="w-full rounded-xl border border-border-default bg-surface-card py-2 pl-10 pr-4 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
        />
      </div>
      <Select
        ariaLabel="Review status"
        options={[
          { value: "ALL", label: "All findings" },
          { value: "reviewed", label: "Reviewed" },
          { value: "unreviewed", label: "Not yet reviewed" },
        ]}
        value={table.filters.reviewed}
        onValueChange={(v) => table.setFilter("reviewed", v)}
        triggerClass="w-44"
      />
      <Select
        ariaLabel="Agreement"
        options={[
          { value: "ALL", label: "Agreement: all" },
          { value: "agree", label: "Agrees with BIM-Guard" },
          { value: "disagree", label: "Disagrees (false pass/fail)" },
        ]}
        value={table.filters.agreement}
        onValueChange={(v) => table.setFilter("agreement", v)}
        triggerClass="w-56"
      />
    </div>

    <BulkActionBar
      selectedCount={table.selectedCount}
      itemLabel="finding"
      onClearSelection={() => table.clearSelection()}
      onBulkDelete={() => (isBulkDeleteModalOpen = true)}
    >
      <button
        type="button"
        onclick={confirmSelectedAsCorrect}
        disabled={isBulkConfirming}
        class="inline-flex items-center gap-1.5 rounded-lg border border-success-border bg-success-bg px-3 py-1.5 font-semibold text-success transition-all hover:opacity-90 disabled:opacity-50"
      >
        <ClipboardCheck class="h-3.5 w-3.5" />
        {isBulkConfirming ? "Confirming…" : "Confirm Selected as Correct"}
      </button>
    </BulkActionBar>

    <div class="overflow-x-auto rounded-2xl border border-border-default">
      <table class="w-full text-left text-xs">
        <thead class="bg-surface-card">
          <tr>
            <th class="w-10 px-4 py-3">
              <TableCheckbox
                checked={table.allFilteredSelected}
                indeterminate={table.someFilteredSelected}
                ariaLabel="Select all findings"
                onchange={() => table.toggleSelectAll()}
              />
            </th>
            <SortHeader column="rule_id" sortField={table.sortField} sortAsc={table.sortAsc} onSort={table.toggleSort.bind(table)}>Rule</SortHeader>
            <SortHeader column="element_name" sortField={table.sortField} sortAsc={table.sortAsc} onSort={table.toggleSort.bind(table)}>Element</SortHeader>
            <SortHeader column="storey" sortField={table.sortField} sortAsc={table.sortAsc} onSort={table.toggleSort.bind(table)}>Location</SortHeader>
            <SortHeader column="bimguard_verdict" sortField={table.sortField} sortAsc={table.sortAsc} onSort={table.toggleSort.bind(table)}>BIM-Guard</SortHeader>
            <th class="px-4 py-3 text-caption font-semibold uppercase tracking-wider text-fg-muted">Human Verdict</th>
            <SortHeader column="captured_at" sortField={table.sortField} sortAsc={table.sortAsc} onSort={table.toggleSort.bind(table)}>Captured</SortHeader>
          </tr>
        </thead>
        <tbody class="divide-y divide-border-subtle">
          {#each table.paginated as finding (finding.id)}
            {@const disagrees = !!finding.human_verdict && finding.human_verdict !== BIMGUARD_TO_HUMAN[finding.bimguard_verdict]}
            <tr class="hover:bg-surface-hover {table.isSelected(finding.id) ? 'bg-surface-selected' : ''}">
              <td class="px-4 py-3">
                <TableCheckbox
                  checked={table.isSelected(finding.id)}
                  ariaLabel={`Select finding ${finding.id}`}
                  onchange={() => table.toggleSelect(finding.id)}
                />
              </td>
              <td class="px-4 py-3 font-mono text-fg-secondary">{ruleLabel(finding)}</td>
              <td class="px-4 py-3">
                <div class="font-medium text-fg-primary">{finding.element_name || "—"}</div>
                <div class="font-mono text-nano text-fg-muted">{finding.element_global_id}</div>
              </td>
              <td class="px-4 py-3 text-fg-secondary">{finding.storey || "—"} / {finding.space || "—"}</td>
              <td class="px-4 py-3">
                <span class="inline-flex items-center rounded-md border px-2.5 py-0.5 text-micro font-semibold uppercase tracking-wider {VERDICT_CLASS[finding.bimguard_verdict]}">
                  {finding.bimguard_verdict}
                </span>
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <Select
                    ariaLabel={`Human verdict for finding ${finding.id}`}
                    options={VERDICT_OPTIONS}
                    value={finding.human_verdict ?? ""}
                    placeholder="Not reviewed"
                    onValueChange={(v) => reviewOne(finding, v as EvaluationHumanVerdict)}
                    triggerClass="w-40 {finding.human_verdict ? VERDICT_CLASS[finding.human_verdict] : ''}"
                  />
                  {#if disagrees}
                    <span
                      class="rounded-md border border-critical-border bg-critical-bg px-1.5 py-0.5 text-nano font-bold uppercase tracking-wide text-critical"
                      title="Human verdict disagrees with BIM-Guard's verdict"
                    >
                      Mismatch
                    </span>
                  {/if}
                </div>
                {#if finding.reviewer_email}
                  <div class="mt-1 text-nano text-fg-muted">by {finding.reviewer_email}</div>
                {/if}
              </td>
              <td class="px-4 py-3 text-fg-muted">{finding.captured_at ? new Date(finding.captured_at).toLocaleString() : "—"}</td>
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
      onPageSizeChange={(s) => (table.pageSize = s)}
    />
  {/if}
</div>

<ConfirmModal
  bind:isOpen={isBulkDeleteModalOpen}
  title="Remove Selected Findings"
  message={`Remove ${table.selectedCount} selected finding(s) from the evaluation set? This does not affect the underlying compliance rules or results.`}
  confirmText="Remove"
  danger={true}
  onConfirm={confirmBulkDelete}
  onCancel={() => (isBulkDeleteModalOpen = false)}
/>
