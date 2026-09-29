<script lang="ts">
  import { untrack } from "svelte";
  import {
    BarChart3,
    ChevronDown,
    ChevronUp,
    ClipboardCheck,
    Download,
    FileSpreadsheet,
    RefreshCw,
    Search,
  } from "lucide-svelte";
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
  import Alert from "../lib/components/Alert.svelte";
  import { toasts } from "../lib/toast.svelte";
  import { toErrorLogEntry, type ErrorLogEntry } from "../lib/utils/errorLog";

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
  let errorLog: ErrorLogEntry[] = $state([]);
  let isBulkDeleteModalOpen = $state(false);
  let isBulkConfirming = $state(false);
  let showMatrixCard = $state(true);

  // Live reactive confusion matrix computed directly from findings
  const reviewedFindings = $derived(findings.filter((f) => !!f.human_verdict));

  const matrixStats = $derived.by(() => {
    let tp = 0;
    let fp = 0;
    let fn = 0;
    let tn = 0;
    let agreed = 0;

    const bgCounts: Record<string, number> = {};
    const humanCounts: Record<string, number> = {};

    for (const f of reviewedFindings) {
      const bg = f.bimguard_verdict;
      const hv = f.human_verdict;
      if (!hv) continue;
      const bgMapped = BIMGUARD_TO_HUMAN[bg];

      if (bgMapped === hv) agreed++;

      bgCounts[bgMapped] = (bgCounts[bgMapped] || 0) + 1;
      humanCounts[hv] = (humanCounts[hv] || 0) + 1;

      // Positive = FAIL (non-compliance), Negative = PASS (compliance)
      if (bg === "FAIL" && hv === "FAIL") tp++;
      else if (bg === "FAIL" && hv === "PASS") fp++;
      else if (bg === "PASS" && hv === "FAIL") fn++;
      else if (bg === "PASS" && hv === "PASS") tn++;
    }

    const n = reviewedFindings.length;
    const binaryTotal = tp + fp + fn + tn;
    const accuracy = binaryTotal > 0 ? (tp + tn) / binaryTotal : null;
    const precision = tp + fp > 0 ? tp / (tp + fp) : null;
    const recall = tp + fn > 0 ? tp / (tp + fn) : null;
    const specificity = tn + fp > 0 ? tn / (tn + fp) : null;
    const f1 =
      precision !== null && recall !== null && precision + recall > 0
        ? (2 * precision * recall) / (precision + recall)
        : null;

    let kappa: number | null = null;
    if (n > 0) {
      const po = agreed / n;
      const allCats = new Set([...Object.keys(bgCounts), ...Object.keys(humanCounts)]);
      let pe = 0;
      for (const cat of allCats) {
        pe += ((bgCounts[cat] || 0) / n) * ((humanCounts[cat] || 0) / n);
      }
      if (Math.abs(1.0 - pe) < 1e-9) {
        kappa = Math.abs(po - 1.0) < 1e-9 ? 1.0 : 0.0;
      } else {
        kappa = (po - pe) / (1.0 - pe);
      }
    }

    return {
      n,
      tp,
      fp,
      fn,
      tn,
      agreed,
      accuracy,
      precision,
      recall,
      specificity,
      f1,
      kappa,
    };
  });

  function kappaDescription(k: number | null): string {
    if (k === null) return "No data";
    if (k >= 0.81) return "Almost Perfect Agreement";
    if (k >= 0.61) return "Substantial Agreement";
    if (k >= 0.41) return "Moderate Agreement";
    if (k >= 0.21) return "Fair Agreement";
    if (k >= 0.0) return "Slight Agreement";
    return "Poor / Chance Agreement";
  }

  function exportMatrixCsv() {
    const s = matrixStats;
    const csv = [
      "Metric,Value",
      `Total Findings,${findings.length}`,
      `Reviewed Findings,${s.n}`,
      `True Positives (TP),${s.tp}`,
      `False Positives (FP),${s.fp}`,
      `False Negatives (FN),${s.fn}`,
      `True Negatives (TN),${s.tn}`,
      `Accuracy,${s.accuracy !== null ? (s.accuracy * 100).toFixed(1) + "%" : "N/A"}`,
      `Precision,${s.precision !== null ? (s.precision * 100).toFixed(1) + "%" : "N/A"}`,
      `Recall (Sensitivity),${s.recall !== null ? (s.recall * 100).toFixed(1) + "%" : "N/A"}`,
      `Specificity,${s.specificity !== null ? (s.specificity * 100).toFixed(1) + "%" : "N/A"}`,
      `F1 Score,${s.f1 !== null ? (s.f1 * 100).toFixed(1) + "%" : "N/A"}`,
      `Cohen's Kappa,${s.kappa !== null ? s.kappa.toFixed(4) : "N/A"}`,
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `validation_matrix_project_${selectedProjectId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toasts.success("Validation matrix CSV exported successfully.");
  }

  function exportMatrixSvg() {
    const s = matrixStats;
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 540 380" width="540" height="380" style="background:#0f172a;font-family:ui-sans-serif,system-ui,sans-serif;color:#f8fafc">
      <text x="24" y="36" font-size="16" font-weight="700" fill="#f8fafc">BIMGuard Validation Matrix (Project #${selectedProjectId})</text>
      <text x="24" y="58" font-size="12" fill="#94a3b8">Reviewed: ${s.n} / ${findings.length} | Cohen's κ: ${s.kappa !== null ? s.kappa.toFixed(3) : "N/A"} (${kappaDescription(s.kappa)})</text>
      
      <text x="140" y="85" font-size="11" font-weight="600" fill="#94a3b8">Expert: FAIL</text>
      <text x="310" y="85" font-size="11" font-weight="600" fill="#94a3b8">Expert: PASS</text>

      <text x="24" y="135" font-size="11" font-weight="600" fill="#94a3b8">Tool: FAIL</text>
      <rect x="140" y="95" width="160" height="85" fill="#064e3b" stroke="#059669" rx="8"/>
      <text x="155" y="120" font-size="11" font-weight="700" fill="#6ee7b7">True Positive (TP)</text>
      <text x="155" y="158" font-size="28" font-weight="800" fill="#ffffff">${s.tp}</text>

      <rect x="310" y="95" width="160" height="85" fill="#7f1d1d" stroke="#dc2626" rx="8"/>
      <text x="325" y="120" font-size="11" font-weight="700" fill="#fca5a5">False Positive (FP)</text>
      <text x="325" y="158" font-size="28" font-weight="800" fill="#ffffff">${s.fp}</text>

      <text x="24" y="235" font-size="11" font-weight="600" fill="#94a3b8">Tool: PASS</text>
      <rect x="140" y="195" width="160" height="85" fill="#7c2d12" stroke="#ea580c" rx="8"/>
      <text x="155" y="220" font-size="11" font-weight="700" fill="#fdba74">False Negative (FN)</text>
      <text x="155" y="258" font-size="28" font-weight="800" fill="#ffffff">${s.fn}</text>

      <rect x="310" y="195" width="160" height="85" fill="#1e293b" stroke="#475569" rx="8"/>
      <text x="325" y="220" font-size="11" font-weight="700" fill="#cbd5e1">True Negative (TN)</text>
      <text x="325" y="258" font-size="28" font-weight="800" fill="#ffffff">${s.tn}</text>

      <text x="24" y="315" font-size="11" fill="#94a3b8">Accuracy: ${s.accuracy !== null ? (s.accuracy * 100).toFixed(1) + "%" : "N/A"} | Precision: ${s.precision !== null ? (s.precision * 100).toFixed(1) + "%" : "N/A"}</text>
      <text x="24" y="335" font-size="11" fill="#94a3b8">Recall: ${s.recall !== null ? (s.recall * 100).toFixed(1) + "%" : "N/A"} | Specificity: ${s.specificity !== null ? (s.specificity * 100).toFixed(1) + "%" : "N/A"} | F1: ${s.f1 !== null ? (s.f1 * 100).toFixed(1) + "%" : "N/A"}</text>
    </svg>`;
    const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `validation_matrix_project_${selectedProjectId}.svg`;
    a.click();
    URL.revokeObjectURL(url);
    toasts.success("Validation matrix SVG exported successfully.");
  }

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
    errorLog = [];
    try {
      const res = await evaluationApi.listFindings(selectedProjectId);
      findings = res.findings;
    } catch (err: any) {
      error = err.message || "Failed to load evaluation findings.";
      errorLog = [toErrorLogEntry(err, `project #${selectedProjectId}`)];
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
    await table.optimisticUpdate({
      ids: finding.id,
      patch: { human_verdict: verdict },
      action: () => evaluationApi.reviewFinding(finding.id, { human_verdict: verdict }),
      onSuccess: (updated) => {
        findings = findings.map((f) => (f.id === finding.id ? updated : f));
        toasts.success(`Recorded review for finding #${finding.id}.`);
      },
      onError: (err) => {
        error = err.message || `Failed to review finding ${finding.id}.`;
        errorLog = [toErrorLogEntry(err, `finding #${finding.id}`)];
        toasts.fromError(err, `Could not review finding #${finding.id}`);
      },
    });
  }

  /** Each selected row is confirmed against its own BIM-Guard verdict, not one shared value. */
  async function confirmSelectedAsCorrect() {
    if (isBulkConfirming || !table.selectedCount) return;
    const targetIds = [...table.selectedIdList];
    const prevFindings = [...findings];
    isBulkConfirming = true;
    error = "";
    errorLog = [];

    // Optimistically assign human_verdict = BIMGUARD_TO_HUMAN[f.bimguard_verdict]
    findings = findings.map((f) =>
      targetIds.includes(f.id)
        ? { ...f, human_verdict: BIMGUARD_TO_HUMAN[f.bimguard_verdict] }
        : f,
    );
    table.clearSelection();

    try {
      const groups = new Map<EvaluationHumanVerdict, number[]>();
      for (const id of targetIds) {
        const item = prevFindings.find((f) => f.id === id);
        if (!item) continue;
        const verdict = BIMGUARD_TO_HUMAN[item.bimguard_verdict];
        groups.set(verdict, [...(groups.get(verdict) ?? []), id]);
      }
      await Promise.all(
        [...groups.entries()].map(([human_verdict, finding_ids]) =>
          evaluationApi.bulkReview({ finding_ids, human_verdict }),
        ),
      );
      toasts.success(`Confirmed ${targetIds.length} finding(s) as correct.`);
    } catch (err: any) {
      findings = prevFindings;
      error = err.message || "Failed to confirm the selected findings.";
      errorLog = [toErrorLogEntry(err, `${targetIds.length} finding(s)`)];
      toasts.fromError(err, "Failed to confirm selected findings");
    } finally {
      isBulkConfirming = false;
    }
  }

  async function confirmBulkDelete() {
    const ids = [...table.selectedIdList];
    if (ids.length === 0) return;
    error = "";
    errorLog = [];
    isBulkDeleteModalOpen = false;

    await table.optimisticDelete({
      ids,
      action: () => evaluationApi.bulkDelete(ids),
      onSuccess: () => {
        findings = findings.filter((f) => !ids.includes(f.id));
        toasts.success(`Removed ${ids.length} finding(s).`);
      },
      onError: (err) => {
        error = err.message || "Failed to remove the selected findings.";
        errorLog = [toErrorLogEntry(err, `${ids.length} finding(s)`)];
        toasts.fromError(err, "Failed to delete findings");
      },
    });
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
    <Alert type="error" message={error} errors={errorLog} logTitle="Evaluation Error Log" />
  {:else if findings.length === 0}
    <EmptyState
      title="Nothing captured yet"
      description='Run a compliance audit, then use "Capture for Evaluation" to snapshot its results here for review.'
    />
  {:else}
    <!-- Tool-vs-Expert Validation Matrix Card -->
    <div class="rounded-2xl border border-border-default bg-surface-card p-5 shadow-xs transition-all">
      <div class="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle pb-4">
        <div class="flex items-center gap-3">
          <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/10 text-accent">
            <BarChart3 class="h-4 w-4" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 class="text-sm font-semibold text-fg-primary">Tool-vs-Expert Validation Matrix</h3>
              <span class="rounded-full bg-surface-overlay px-2 py-0.5 text-[11px] font-medium text-fg-muted border border-border-subtle">
                {matrixStats.n} / {findings.length} Reviewed
              </span>
            </div>
            <p class="text-xs text-fg-muted">
              Empirical confusion matrix and Cohen's κ inter-rater agreement for active architectural rules.
            </p>
          </div>
        </div>

        <div class="flex items-center gap-2">
          {#if matrixStats.n > 0}
            <button
              type="button"
              onclick={exportMatrixSvg}
              class="inline-flex items-center gap-1.5 rounded-xl border border-border-interactive bg-surface-overlay px-2.5 py-1.5 text-xs font-medium text-fg-secondary transition-colors hover:bg-surface-hover"
              title="Export 2x2 confusion matrix as SVG graphic"
            >
              <Download class="h-3.5 w-3.5 text-accent" />
              SVG
            </button>
            <button
              type="button"
              onclick={exportMatrixCsv}
              class="inline-flex items-center gap-1.5 rounded-xl border border-border-interactive bg-surface-overlay px-2.5 py-1.5 text-xs font-medium text-fg-secondary transition-colors hover:bg-surface-hover"
              title="Export statistical validation metrics as CSV"
            >
              <FileSpreadsheet class="h-3.5 w-3.5 text-accent" />
              CSV
            </button>
          {/if}
          <button
            type="button"
            onclick={() => (showMatrixCard = !showMatrixCard)}
            class="inline-flex h-8 w-8 items-center justify-center rounded-xl border border-border-interactive bg-surface-overlay text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
            aria-label={showMatrixCard ? "Collapse Matrix" : "Expand Matrix"}
          >
            {#if showMatrixCard}
              <ChevronUp class="h-4 w-4" />
            {:else}
              <ChevronDown class="h-4 w-4" />
            {/if}
          </button>
        </div>
      </div>

      {#if showMatrixCard}
        <div class="pt-4 space-y-4">
          <!-- 2x2 Matrix & Metrics Split -->
          <div class="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            <!-- 2x2 Confusion Grid -->
            <div class="lg:col-span-6 space-y-2">
              <div class="text-[11px] font-semibold uppercase tracking-wider text-fg-muted mb-1">
                Classification Matrix (Binary Action Threshold: FAIL)
              </div>
              <div class="overflow-hidden rounded-xl border border-border-default bg-surface-overlay/50">
                <table class="w-full text-xs text-center border-collapse">
                  <thead>
                    <tr class="border-b border-border-default bg-surface-overlay text-fg-muted">
                      <th class="p-2.5 text-left font-medium">BIM-Guard \ Expert</th>
                      <th class="p-2.5 font-semibold text-critical">Expert: FAIL (Violation)</th>
                      <th class="p-2.5 font-semibold text-success">Expert: PASS (Compliant)</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr class="border-b border-border-subtle">
                      <td class="p-2.5 text-left font-semibold text-critical bg-surface-overlay/30">
                        Tool: FAIL (Flagged)
                      </td>
                      <td class="p-3 bg-success-bg/20 border-r border-border-subtle">
                        <div class="text-xs font-semibold text-success">True Positive (TP)</div>
                        <div class="text-xl font-bold text-fg-primary mt-0.5">{matrixStats.tp}</div>
                        <div class="text-[10px] text-fg-muted">Accurate violation</div>
                      </td>
                      <td class="p-3 bg-critical-bg/20">
                        <div class="text-xs font-semibold text-critical">False Positive (FP)</div>
                        <div class="text-xl font-bold text-fg-primary mt-0.5">{matrixStats.fp}</div>
                        <div class="text-[10px] text-fg-muted">False alarm</div>
                      </td>
                    </tr>
                    <tr>
                      <td class="p-2.5 text-left font-semibold text-success bg-surface-overlay/30">
                        Tool: PASS (Cleared)
                      </td>
                      <td class="p-3 bg-caution-bg/20 border-r border-border-subtle">
                        <div class="text-xs font-semibold text-caution">False Negative (FN)</div>
                        <div class="text-xl font-bold text-fg-primary mt-0.5">{matrixStats.fn}</div>
                        <div class="text-[10px] text-fg-muted">Missed violation</div>
                      </td>
                      <td class="p-3 bg-surface-card">
                        <div class="text-xs font-semibold text-fg-secondary">True Negative (TN)</div>
                        <div class="text-xl font-bold text-fg-primary mt-0.5">{matrixStats.tn}</div>
                        <div class="text-[10px] text-fg-muted">Accurate pass</div>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Statistical Metrics Cards -->
            <div class="lg:col-span-6 space-y-2">
              <div class="text-[11px] font-semibold uppercase tracking-wider text-fg-muted mb-1">
                Inter-Rater & Evaluation Metrics
              </div>

              <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                <div class="rounded-xl border border-border-default bg-surface-overlay/60 p-3">
                  <div class="text-[11px] text-fg-muted font-medium">Cohen's Kappa (κ)</div>
                  <div class="text-lg font-bold text-fg-primary mt-0.5">
                    {matrixStats.kappa !== null ? matrixStats.kappa.toFixed(3) : "—"}
                  </div>
                  <div class="text-[10px] text-accent truncate font-medium">
                    {kappaDescription(matrixStats.kappa)}
                  </div>
                </div>

                <div class="rounded-xl border border-border-default bg-surface-overlay/60 p-3">
                  <div class="text-[11px] text-fg-muted font-medium">Precision (PPV)</div>
                  <div class="text-lg font-bold text-fg-primary mt-0.5">
                    {matrixStats.precision !== null ? (matrixStats.precision * 100).toFixed(1) + "%" : "—"}
                  </div>
                  <div class="text-[10px] text-fg-muted">TP / (TP + FP)</div>
                </div>

                <div class="rounded-xl border border-border-default bg-surface-overlay/60 p-3">
                  <div class="text-[11px] text-fg-muted font-medium">Recall (Sensitivity)</div>
                  <div class="text-lg font-bold text-fg-primary mt-0.5">
                    {matrixStats.recall !== null ? (matrixStats.recall * 100).toFixed(1) + "%" : "—"}
                  </div>
                  <div class="text-[10px] text-fg-muted">TP / (TP + FN)</div>
                </div>

                <div class="rounded-xl border border-border-default bg-surface-overlay/60 p-3">
                  <div class="text-[11px] text-fg-muted font-medium">Specificity (TNR)</div>
                  <div class="text-lg font-bold text-fg-primary mt-0.5">
                    {matrixStats.specificity !== null ? (matrixStats.specificity * 100).toFixed(1) + "%" : "—"}
                  </div>
                  <div class="text-[10px] text-fg-muted">TN / (TN + FP)</div>
                </div>

                <div class="rounded-xl border border-border-default bg-surface-overlay/60 p-3">
                  <div class="text-[11px] text-fg-muted font-medium">F1 Score</div>
                  <div class="text-lg font-bold text-fg-primary mt-0.5">
                    {matrixStats.f1 !== null ? (matrixStats.f1 * 100).toFixed(1) + "%" : "—"}
                  </div>
                  <div class="text-[10px] text-fg-muted">Harmonic Mean</div>
                </div>

                <div class="rounded-xl border border-border-default bg-surface-overlay/60 p-3">
                  <div class="text-[11px] text-fg-muted font-medium">Overall Accuracy</div>
                  <div class="text-lg font-bold text-fg-primary mt-0.5">
                    {matrixStats.accuracy !== null ? (matrixStats.accuracy * 100).toFixed(1) + "%" : "—"}
                  </div>
                  <div class="text-[10px] text-fg-muted">
                    {matrixStats.agreed} / {matrixStats.n || 0} Agreed
                  </div>
                </div>
              </div>

              {#if matrixStats.n === 0}
                <div class="rounded-xl border border-border-subtle bg-surface-overlay/40 p-2.5 text-center text-xs text-fg-muted">
                  Review findings in the table below to populate real-time validation matrix & kappa metrics.
                </div>
              {/if}
            </div>
          </div>
        </div>
      {/if}
    </div>

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
            <tr class="hover:bg-surface-hover {table.isSelected(finding.id) ? 'bg-surface-selected' : ''} {table.isPending(finding.id) ? 'opacity-50 pointer-events-none' : ''}">
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
  optimistic={true}
  onConfirm={confirmBulkDelete}
  onCancel={() => (isBulkDeleteModalOpen = false)}
/>
