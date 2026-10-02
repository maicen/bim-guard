<script lang="ts">
  import { onMount, untrack } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import {
    Sparkles,
    BookOpen,
    Upload,
    Check,
    Save,
    AlertCircle,
    ChevronDown,
    CheckCircle2,
    FileText,
    Plus,
    Trash2,
    Eye,
    Pencil,
    X,
    Search,
    SlidersHorizontal,
    ArrowUpDown,
    ArrowUp,
    ArrowDown,
    Download,
    AlertTriangle,
    RefreshCw,
  } from "lucide-svelte";
  import { documentsApi, ruleExtractionApi, llmProvidersApi, bsddApi } from "../lib/api";
  import { downloadBlob, downloadText } from "../lib/utils/download";
  import { authState } from "../lib/auth.svelte";
  import { formatModelMeta } from "../lib/utils/formatModelMeta";
  import { toErrorLogEntry, type ErrorLogEntry } from "../lib/utils/errorLog";
  import { toasts } from "../lib/toast.svelte";
  import type {
    DocumentItem,
    DocumentSection,
    ExtractedRule,
    LLMProviderInstance,
    LLMProviderModel,
    RuleExtractionDraft,
    RuleSourceResponse,
    SectionTreeNode,
  } from "../lib/types";
  import DocumentViewer from "../lib/components/DocumentViewer.svelte";
  import SectionTree from "../lib/components/SectionTree.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import Alert from "../lib/components/Alert.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import Button from "../lib/components/ui/Button.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import DocumentUploadModal from "../lib/components/DocumentUploadModal.svelte";
  import Modal from "../lib/components/Modal.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import LiveReliability from "../lib/components/LiveReliability.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import ReliabilityBadge from "../lib/components/ReliabilityBadge.svelte";
  import ReliabilityLegend from "../lib/components/ReliabilityLegend.svelte";
  import BsddBadge from "../lib/components/BsddBadge.svelte";
  import { createTableState } from "../lib/tableState.svelte";

  interface Props {
    /** Pre-selects this document, e.g. when opened from the "Run Compliance Audit" wizard. */
    initialDocId?: number | null;
    /** When true, saving rules offers to send the user back to the tab that opened this page. */
    fromQuickTest?: boolean;
  }

  let { initialDocId = null, fromQuickTest = false }: Props = $props();

  let documents: DocumentItem[] = $state([]);
  let selectedDocId: number | null = $state(untrack(() => initialDocId));
  let showReturnPrompt = $state(false);
  let isUploadModalOpen = $state(false);
  let selectedModel = $state("");
  let viewingDraftRule: ExtractedRule | null = $state(null);

  function handleDocumentAdded(newDoc: DocumentItem) {
    documents = [newDoc, ...documents.filter((d) => d.id !== newDoc.id)];
    selectedDocId = newDoc.id;
    isUploadModalOpen = false;
    toasts.success(`Selected newly added document "${newDoc.filename}".`);
  }

  // Sections/paragraphs detected in the selected document, so extraction can be
  // scoped to a chosen clause instead of the whole document — the picked
  // sections' text is sent as an override to the draft-extraction request.
  // `docSections` is the flat list (for text lookup by id); `sectionTree`
  // nests the same ids for the collapsible picker UI.
  let docSections: DocumentSection[] = $state([]);
  let sectionTree: SectionTreeNode[] = $state([]);
  let sectionsEnhanced = $state(false);
  const selectedSectionKeys: Set<string> = new SvelteSet();
  let isLoadingSections = $state(false);

  function selectAllSections() {
    selectedSectionKeys.clear();
    for (const s of docSections) if (s.id) selectedSectionKeys.add(s.id);
  }

  function clearSectionSelection() {
    selectedSectionKeys.clear();
  }

  let isRegeneratingToc = $state(false);
  let isExportMenuOpen = $state(false);
  let isImportingToc = $state(false);

  async function handleRegenerateToc() {
    if (!selectedDocId || isRegeneratingToc) return;
    isRegeneratingToc = true;
    try {
      toasts.info("Regenerating document outline & Smart TOC…");
      const res = await documentsApi.regenerateSectionsTree(selectedDocId);
      docSections = res.sections;
      sectionTree = res.tree;
      sectionsEnhanced = res.enhanced;
      toasts.success("Table of Contents regenerated and persisted in DB.");
    } catch (err: any) {
      toasts.error(err?.message || "Failed to regenerate Table of Contents.");
    } finally {
      isRegeneratingToc = false;
    }
  }

  async function handleExportToc(format: "json" | "csv") {
    if (!selectedDocId) return;
    isExportMenuOpen = false;
    try {
      toasts.info(`Exporting TOC as ${format.toUpperCase()}…`);
      const blob = await documentsApi.exportSectionsTree(selectedDocId, format);
      downloadBlob(blob, `document_${selectedDocId}_toc.${format}`);
      toasts.success(`Downloaded TOC as ${format.toUpperCase()}.`);
    } catch (err: any) {
      toasts.error(err?.message || "Failed to export TOC.");
    }
  }

  async function handleImportTocFile(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file || !selectedDocId) return;
    isImportingToc = true;
    try {
      toasts.info(`Importing TOC from "${file.name}"…`);
      const res = await documentsApi.importSectionsTree(selectedDocId, file);
      docSections = res.sections;
      sectionTree = res.tree;
      sectionsEnhanced = res.enhanced;
      toasts.success(`Successfully imported TOC (${res.sections.length} clauses).`);
    } catch (err: any) {
      toasts.error(err?.message || "Failed to import TOC.");
    } finally {
      isImportingToc = false;
      input.value = "";
    }
  }

  $effect(() => {
    const docId = selectedDocId;
    docSections = [];
    sectionTree = [];
    sectionsEnhanced = false;
    selectedSectionKeys.clear();
    if (!docId) return;

    isLoadingSections = true;
    documentsApi
      .getSectionsTree(docId)
      .then((res) => {
        if (selectedDocId !== docId) return; // selection changed while in flight
        docSections = res.sections;
        sectionTree = res.tree;
        sectionsEnhanced = res.enhanced;
        // Nothing selected by default when sections were detected, so
        // scoping is deliberate; leaving all sections unselected extracts
        // from the whole document instead.
      })
      .catch(() => {
        if (selectedDocId === docId) {
          docSections = [];
          sectionTree = [];
        }
      })
      .finally(() => {
        if (selectedDocId === docId) isLoadingSections = false;
      });
  });

  // Persisted drafts (rule_extraction_drafts) belonging to the selected
  // document — loaded up front so a reviewer returning to a document sees
  // prior extraction results instead of losing them, unlike the ephemeral
  // raw-text path below.
  let draftRules: RuleExtractionDraft[] = $state([]);
  let isLoadingDrafts = $state(false);
  let editingDraft: RuleExtractionDraft | null = $state(null);
  let editForm: RuleExtractionDraft["proposed_rule"] | null = $state(null);
  let viewingDraftSource: RuleSourceResponse | null = $state(null);
  let draftSourceError = $state("");
  // Accept/reject/edit/promote failures, shown as a red alert inside the Draft
  // Review section itself -- the page-level `error` banner sits above the fold
  // once the table is scrolled into view, so a rejected click looked like a no-op.
  let draftReviewError = $state("");
  // Per-draft failures backing the copiable technical detail log below the
  // banner -- the banner text alone only ever showed the first failure, which
  // left reviewers unable to tell a platform admin exactly what failed for a
  // bulk action that touched many drafts.
  let draftReviewErrorLog: ErrorLogEntry[] = $state([]);
  let draftReviewErrorAction = $state("review");
  let inspectingConflictDraft: RuleExtractionDraft | null = $state(null);
  let isCheckingConflicts = $state(false);

  async function scanDraftConflicts(): Promise<void> {
    if (!selectedDocId || draftRules.length === 0) return;
    isCheckingConflicts = true;
    try {
      const resp = await ruleExtractionApi.detectConflicts({
        document_id: selectedDocId,
        include_threshold_discrepancies: true,
      });
      const conflictMap = new Map(
        resp.drafts_with_conflicts.map((d) => [d.id, d.conflicts || []])
      );
      draftRules = draftRules.map((d) => ({
        ...d,
        conflicts: conflictMap.get(d.id) || [],
      }));
      if (resp.total_conflicts_found > 0) {
        toasts.warning(
          `Detected ${resp.total_conflicts_found} conflict(s) across ${resp.drafts_with_conflicts.length} rule draft(s).`
        );
      } else {
        toasts.success("No cross-rule or cross-draft building code contradictions detected.");
      }
    } catch (err: any) {
      toasts.error(err?.message || "Failed to scan draft conflicts.");
    } finally {
      isCheckingConflicts = false;
    }
  }

  function describeDraftFailure(err: any, fallback: string): string {
    const reason = err?.message || fallback;
    if (err?.status === 403) {
      return `${reason} A platform admin can grant your organization access under Ruleset access, or you can re-run the extraction.`;
    }
    return reason;
  }

  function draftSubject(draft?: { id?: number; proposed_rule?: { rule_id?: string } }): string {
    return `draft #${draft?.id ?? "?"} (${draft?.proposed_rule?.rule_id ?? "unknown rule"})`;
  }

  $effect(() => {
    const docId = selectedDocId;
    draftRules = [];
    draftReviewError = "";
    draftReviewErrorLog = [];
    if (!docId) return;

    isLoadingDrafts = true;
    ruleExtractionApi
      .listDrafts(docId)
      .then((res) => {
        if (selectedDocId !== docId) return;
        draftRules = res.drafts;
      })
      .catch(() => {
        if (selectedDocId === docId) draftRules = [];
      })
      .finally(() => {
        if (selectedDocId === docId) isLoadingDrafts = false;
      });
  });

  const draftTable = createTableState<RuleExtractionDraft, number>({
    rows: () => draftRules,
    getId: (d) => d.id!,
    searchFields: (d) => [
      d.proposed_rule.rule_id,
      d.proposed_rule.description,
      d.proposed_rule.property_name,
      d.proposed_rule.property_set,
    ],
    filters: {
      status: (d, value) => d.status === value,
    },
    initialSort: { field: "id", asc: true },
  });

  async function reviewDraft(
    draft: RuleExtractionDraft,
    status: "accepted" | "rejected",
  ): Promise<void> {
    const updated = await ruleExtractionApi.reviewDraft(draft.id!, { status });
    draftRules = draftRules.map((d) => (d.id === draft.id ? updated : d));
  }

  async function reviewDraftRow(
    draft: RuleExtractionDraft,
    status: "accepted" | "rejected",
  ): Promise<void> {
    draftReviewError = "";
    draftReviewErrorLog = [];
    successMessage = "";

    await draftTable.optimisticUpdate({
      ids: draft.id!,
      patch: { status },
      action: () => ruleExtractionApi.reviewDraft(draft.id!, { status }),
      onSuccess: (updated) => {
        draftRules = draftRules.map((d) => (d.id === draft.id ? updated : d));
        toasts.success(`Marked "${draft.proposed_rule.rule_id}" as ${status}.`);
      },
      onError: (err) => {
        draftReviewError = describeDraftFailure(
          err,
          `Failed to ${status === "accepted" ? "accept" : "reject"} "${draft.proposed_rule.rule_id}".`,
        );
        draftReviewErrorLog = [toErrorLogEntry(err, draftSubject(draft))];
        draftReviewErrorAction = status === "accepted" ? "accept" : "reject";
      },
    });
  }

  function openEditDraftModal(draft: RuleExtractionDraft) {
    editingDraft = draft;
    draftReviewError = "";
    // Edit on a clone, not the live table row -- otherwise a bound input
    // would mutate draftRules before the PATCH confirms the edit was saved.
    editForm = { ...draft.proposed_rule };
  }

  function closeEditDraftModal() {
    editingDraft = null;
    editForm = null;
  }

  let suggestingField: "target_ifc_class" | "property_name" | null = $state(null);

  /** Ask the LLM-backed bSDD mapper for a better class/property match, and fill it in on a confident hit. */
  async function suggestViaAI(field: "target_ifc_class" | "property_name") {
    if (!editForm) return;
    const query = field === "target_ifc_class" ? editForm.target_ifc_class : editForm.property_name;
    if (!query?.trim()) {
      toasts.warning(`Enter a ${field === "target_ifc_class" ? "class" : "property"} name to suggest from first.`);
      return;
    }
    suggestingField = field;
    try {
      const result = await bsddApi.semanticMatch({
        query,
        kind: field === "target_ifc_class" ? "class" : "property",
        target_ifc_class: field === "property_name" ? editForm.target_ifc_class : undefined,
      });
      if (!result.matched || !result.matched_code) {
        toasts.info(`No confident bSDD match found for "${query}".`, "No suggestion");
        return;
      }
      editForm = { ...editForm, [field]: result.matched_code };
      toasts.success(
        `Suggested "${result.matched_code}" (confidence ${(result.confidence * 100).toFixed(0)}%)${
          result.reasoning ? ` — ${result.reasoning}` : ""
        }`,
        "AI suggestion applied",
      );
    } catch (err: any) {
      toasts.fromError(err, "Could not get an AI suggestion.");
    } finally {
      suggestingField = null;
    }
  }

  function saveEditedDraft() {
    if (!editingDraft || !editForm) return;
    const draftId = editingDraft.id!;
    const draftBeingEdited = editingDraft;
    draftReviewError = "";
    draftReviewErrorLog = [];
    ruleExtractionApi
      .reviewDraft(draftId, { status: "edited", edited_rule: editForm })
      .then((updated) => {
        draftRules = draftRules.map((d) => (d.id === draftId ? updated : d));
        closeEditDraftModal();
      })
      .catch((err: any) => {
        draftReviewError = describeDraftFailure(err, "Failed to save draft edits.");
        draftReviewErrorLog = [toErrorLogEntry(err, draftSubject(draftBeingEdited))];
        draftReviewErrorAction = "edit";
      });
  }

  async function viewDraftSource(draft: RuleExtractionDraft): Promise<void> {
    draftSourceError = "";
    try {
      viewingDraftSource = await ruleExtractionApi.getDraftSource(draft.id!);
    } catch (err: any) {
      draftSourceError = err?.message || "Could not resolve this draft's source document.";
    }
  }

  /** Toast a promoted rule's ontology-alignment warnings/conflicts, if any -- promotion itself never blocks on these. */
  function warnAboutAlignment(result: { alignment_issues?: unknown[]; conflicts?: unknown[] }, ruleId: string) {
    const issueCount = result.alignment_issues?.length ?? 0;
    const conflictCount = result.conflicts?.length ?? 0;
    if (issueCount === 0 && conflictCount === 0) return;
    const parts = [];
    if (issueCount > 0) parts.push(`${issueCount} ontology warning${issueCount === 1 ? "" : "s"}`);
    if (conflictCount > 0) parts.push(`${conflictCount} conflicting rule${conflictCount === 1 ? "" : "s"}`);
    toasts.warning(
      `"${ruleId}" was promoted with ${parts.join(" and ")} -- flagged for review.`,
      "Promoted with warnings",
    );
  }

  async function promoteDraft(draft: RuleExtractionDraft): Promise<void> {
    draftReviewError = "";
    draftReviewErrorLog = [];

    await draftTable.optimisticDelete({
      ids: draft.id!,
      action: () => ruleExtractionApi.promoteDraft(draft.id!),
      onSuccess: (result) => {
        draftRules = draftRules.filter((d) => d.id !== draft.id);
        successMessage = `Promoted "${draft.proposed_rule.rule_id}" into the compliance rule library.`;
        toasts.success(`Promoted "${draft.proposed_rule.rule_id}".`);
        warnAboutAlignment(result, draft.proposed_rule.rule_id);
      },
      onError: (err) => {
        draftReviewError = describeDraftFailure(
          err,
          `Failed to promote "${draft.proposed_rule.rule_id}".`,
        );
        draftReviewErrorLog = [toErrorLogEntry(err, draftSubject(draft))];
        draftReviewErrorAction = "promote";
      },
    });
  }

  // Which bulk action is in flight (drives the loading buttons) and how far along it is.
  let bulkAction: "accept" | "promote" | null = $state(null);
  let bulkProgress = $state({ done: 0, total: 0 });

  /** Run `worker` over `items`, `concurrency` at a time. `worker` must handle its own errors. */
  async function runBulk<T>(
    items: T[],
    concurrency: number,
    worker: (item: T) => Promise<void>,
  ): Promise<void> {
    bulkProgress = { done: 0, total: items.length };
    for (let i = 0; i < items.length; i += concurrency) {
      await Promise.all(
        items.slice(i, i + concurrency).map(async (item) => {
          await worker(item);
          bulkProgress.done += 1;
        }),
      );
    }
  }

  async function promoteSelectedDrafts(): Promise<void> {
    if (bulkAction) return;
    const toPromote = draftTable.selectedRows.filter(
      (d) => d.status === "accepted" || d.status === "edited",
    );
    draftReviewError = "";
    draftReviewErrorLog = [];
    successMessage = "";
    if (toPromote.length === 0) {
      draftReviewError =
        "None of the selected drafts are accepted or edited — accept them before promoting.";
      return;
    }

    bulkAction = "promote";
    const promotedIds = new Set<number | undefined>();
    const failures: typeof draftReviewErrorLog = [];
    try {
      // One at a time: each promote inserts into the rule library.
      await runBulk(toPromote, 1, async (draft) => {
        try {
          const result = await ruleExtractionApi.promoteDraft(draft.id!);
          promotedIds.add(draft.id);
          warnAboutAlignment(result, draft.proposed_rule.rule_id);
        } catch (err: any) {
          failures.push(toErrorLogEntry(err, draftSubject(draft)));
        }
      });
    } finally {
      bulkAction = null;
    }

    draftRules = draftRules.filter((d) => !promotedIds.has(d.id));
    draftTable.clearSelection();
    if (promotedIds.size > 0) {
      successMessage = `Promoted ${promotedIds.size} draft(s) into the compliance rule library.`;
    }
    if (failures.length > 0) {
      draftReviewErrorLog = failures;
      draftReviewErrorAction = "promote";
      draftReviewError = `${failures.length} of ${toPromote.length} drafts could not be promoted: ${describeDraftFailure(failures[0], "Failed to promote draft.")}`;
    }
  }

  async function acceptSelectedDrafts(): Promise<void> {
    if (bulkAction) return;
    const toAccept = draftTable.selectedRows.filter((d) => d.status === "pending_review");
    draftReviewError = "";
    draftReviewErrorLog = [];
    successMessage = "";
    if (toAccept.length === 0) {
      draftReviewError = "None of the selected drafts are pending review.";
      return;
    }

    bulkAction = "accept";
    let accepted = 0;
    const failures: typeof draftReviewErrorLog = [];
    try {
      await runBulk(toAccept, 5, async (draft) => {
        try {
          await reviewDraft(draft, "accepted");
          accepted += 1;
        } catch (err: any) {
          failures.push(toErrorLogEntry(err, draftSubject(draft)));
        }
      });
    } finally {
      bulkAction = null;
    }

    if (accepted > 0) successMessage = `Accepted ${accepted} draft(s).`;
    if (failures.length > 0) {
      draftReviewErrorLog = failures;
      draftReviewErrorAction = "accept";
      draftReviewError = `${failures.length} of ${toAccept.length} drafts could not be accepted: ${describeDraftFailure(failures[0], "Failed to accept draft.")}`;
    }
  }

  function addManualDraftRule() {
    const newRule: DraftRule = {
      rowId: nextDraftRowId++,
      rule_id: `CUSTOM-${extractedRules.length + 1}`,
      description: "Custom compliance requirement",
      property_set: "Pset_Compliance",
      property_name: "",
      operator: "==",
      check_value: "",
      severity: "Medium",
    };
    extractedRules = [newRule, ...extractedRules];
    table.selectedIds.add(newRule.rowId);
  }

  function removeDraftRule(rowId: number) {
    extractedRules = extractedRules.filter((r) => r.rowId !== rowId);
    table.selectedIds.delete(rowId);
  }
  let isExtracting = $state(false);
  let extractionProgress: { completed: number; total: number } | null = $state(null);
  let isSaving = $state(false);
  let error = $state("");
  let successMessage = $state("");

  let extractedRules: DraftRule[] = $state([]);
  let extractionWarnings: string[] = [];
  let formRulesetId = $state("EXTRACTED-STANDARDS");

  // Search, Filter, Sort & Pagination for Draft Rules
  // Extracted rules carry no id of their own — `rule_id` is a code reference and
  // repeats — so each draft gets a stable row id when it arrives.
  type DraftRule = ExtractedRule & { rowId: number };
  let nextDraftRowId = 0;

  // Search, filter, sort, paginate and select — all owned by the shared state.
  const table = createTableState<DraftRule, number>({
    rows: () => extractedRules,
    getId: (r) => r.rowId,
    searchFields: (r) => [r.rule_id, r.description, r.property_name, r.property_set],
    filters: {
      severity: (r, value) => (r.severity || "Medium").toLowerCase() === value.toLowerCase(),
    },
    initialSort: { field: "rule_id", asc: true },
  });

  // Bulk Edit Modal for Draft Rules
  let isDraftBulkEditModalOpen = $state(false);
  let bulkDraftSeverity = $state("no_change");
  let bulkDraftPset = $state("");
  let bulkDraftOperator = $state("no_change");
  let isDraftBulkDeleteModalOpen = $state(false);

  // Model choices come from this organization's curated "rule_extraction"
  // task shortlist (Admin → External providers → LLM Providers → Task
  // Shortlists) when one exists, so admins can narrow the picker to models
  // deliberately chosen for capability/price/context fit. If no shortlist
  // has been configured yet, fall back to the default provider's whole
  // catalogue so extraction still works before an admin curates one.
  const RULE_EXTRACTION_TASK_KEY = "rule_extraction";

  let llmModels: LLMProviderModel[] = $state([]);
  let llmModelsLoading = $state(false);
  let llmModelsError = $state("");
  let usingShortlist = $state(false);

  // Bumped per call so a slow response for a previous organization can't
  // overwrite the list for the one now selected.
  let llmModelsRequest = 0;

  async function loadLlmModels() {
    const activeOrg = authState.activeOrganization;
    if (!activeOrg) return;
    const request = ++llmModelsRequest;
    const isCurrent = () => request === llmModelsRequest;
    llmModelsLoading = true;
    llmModelsError = "";
    try {
      const shortlist = await llmProvidersApi.taskAssignments(
        activeOrg.organization_id,
        RULE_EXTRACTION_TASK_KEY,
      );
      if (!isCurrent()) return;
      if (shortlist.length > 0) {
        usingShortlist = true;
        llmModels = shortlist.map((a) => ({
          id: a.model_id,
          name: a.model_name,
          context_length: a.context_length,
          input_price_per_million: a.input_price_per_million,
          output_price_per_million: a.output_price_per_million,
        }));
        const defaultModel = shortlist.find((a) => a.is_default);
        if (defaultModel && !llmModels.some((m) => m.id === selectedModel)) {
          selectedModel = defaultModel.model_id;
        } else if (!llmModels.some((m) => m.id === selectedModel)) {
          selectedModel = llmModels[0].id;
        }
        return;
      }

      usingShortlist = false;
      const instances = await llmProvidersApi.list(activeOrg.organization_id);
      if (!isCurrent()) return;
      const enabled = instances.filter((i) => i.is_enabled);
      const primary: LLMProviderInstance | undefined =
        enabled.find((i) => i.is_default) ?? enabled[0];
      if (!primary) {
        llmModels = [];
        selectedModel = "";
        return;
      }
      const models = await llmProvidersApi.models(activeOrg.organization_id, primary.id);
      if (!isCurrent()) return;
      llmModels = models;
      if (llmModels.length > 0 && !llmModels.some((m) => m.id === selectedModel)) {
        selectedModel = llmModels[0].id;
      }
    } catch (err: any) {
      if (!isCurrent()) return;
      llmModelsError = err.message || "Failed to load models from the configured LLM provider.";
      llmModels = [];
      selectedModel = "";
    } finally {
      if (isCurrent()) llmModelsLoading = false;
    }
  }

  // Load on first render *and* whenever the active organization changes or
  // first resolves. A one-shot call in onMount ran before
  // authState.activeOrganization was set on a fresh page load (leaving a
  // misleading "No LLM provider configured" banner up), and went stale after
  // an organization switch. untrack: loadLlmModels reads other state
  // synchronously, which must not become effect dependencies.
  $effect(() => {
    const _orgId = authState.activeOrganizationId;
    untrack(() => loadLlmModels());
  });

  onMount(async () => {
    try {
      documents = await documentsApi.list();
    } catch {
      documents = [];
    }
  });

  async function handleExtract() {
    isExtracting = true;
    extractionProgress = null;
    error = "";
    successMessage = "";
    extractedRules = [];
    table.clearSelection();
    extractionWarnings = [];
    table.requestedPage = 1;

    try {
      // A selected document runs through the persisted draft-review
      // lifecycle (rule_extraction_drafts) instead of the ephemeral
      // extract-then-bulk-insert path, so results survive a closed tab and
      // get a reviewer audit trail. Picked sections scope the extraction to
      // that subset of the document; leaving none picked runs the whole
      // document through LlamaIndex's own clause-level chunking.
      if (!selectedDocId) {
        throw new Error("Please select a specification document to extract rules.");
      }

      const scopedText =
        selectedSectionKeys.size > 0
          ? docSections
              .filter((s) => s.id && selectedSectionKeys.has(s.id))
              .map((s) => s.text)
              .join("\n\n")
          : undefined;

      // Large documents run many clause-nodes through the LLM concurrently on
      // the backend; its streamed progress drives the button's progress bar.
      const res = await ruleExtractionApi.extractDrafts(
        selectedDocId,
        selectedModel,
        scopedText,
        undefined,
        (progress) => {
          if (progress.total > 0) {
            extractionProgress = { completed: progress.completed, total: progress.total };
          }
        },
      );
      draftRules = [...res.drafts, ...draftRules];
      draftTable.clearSelection();
      if (res.drafts.length === 0) {
        error = "No valid OpenBIM rules could be parsed from this document.";
      }
      return;
    } catch (err: any) {
      error = err.message || "Rule extraction failed.";
    } finally {
      isExtracting = false;
      extractionProgress = null;
    }
  }

  function applyDraftBulkEdit() {
    extractedRules = extractedRules.map((r) => {
      if (!table.isSelected(r.rowId)) return r;
      return {
        ...r,
        severity: bulkDraftSeverity !== "no_change" ? bulkDraftSeverity : r.severity,
        property_set: bulkDraftPset.trim() ? bulkDraftPset.trim() : r.property_set,
        operator: bulkDraftOperator !== "no_change" ? bulkDraftOperator : r.operator,
      };
    });
    isDraftBulkEditModalOpen = false;
    bulkDraftSeverity = "no_change";
    bulkDraftPset = "";
    bulkDraftOperator = "no_change";
  }

  function confirmBulkDeleteDrafts() {
    extractedRules = extractedRules.filter((r) => !table.isSelected(r.rowId));
    table.clearSelection();
    isDraftBulkDeleteModalOpen = false;
  }

  let previewingIds = $state(false);

  /** Download the IDS XML the current document's extraction drafts would produce. */
  async function previewDraftsAsIds() {
    if (!selectedDocId || previewingIds) return;
    previewingIds = true;
    try {
      const xmlText = await ruleExtractionApi.previewDraftsAsIds(selectedDocId);
      downloadText(
        xmlText,
        `document_${selectedDocId}_drafts_preview.ids.xml`,
        "application/xml;charset=utf-8;",
      );
    } catch (err: any) {
      toasts.fromError(err, "Could not generate an IDS preview for this document's drafts.");
    } finally {
      previewingIds = false;
    }
  }

  function exportDraftRulesToCsv() {
    const target = table.selectedCount ? table.selectedRows : table.sorted;
    const headers = [
      "RuleID",
      "Description",
      "PropertySet",
      "PropertyName",
      "Operator",
      "CheckValue",
      "Severity",
    ];
    const rows = target.map((r) => [
      `"${(r.rule_id || "").replace(/"/g, '""')}"`,
      `"${(r.description || "").replace(/"/g, '""')}"`,
      `"${(r.property_set || "").replace(/"/g, '""')}"`,
      `"${(r.property_name || "").replace(/"/g, '""')}"`,
      `"${r.operator || "=="}"`,
      `"${(r.check_value || "").replace(/"/g, '""')}"`,
      r.severity || "Medium",
    ]);
    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const filename = `extracted_rules_draft_${new Date().toISOString().substring(0, 10)}.csv`;
    downloadText(csvContent, filename, "text/csv;charset=utf-8;");
  }

  async function handleSaveSelected() {
    const toSave = table.selectedRows;
    if (toSave.length === 0) {
      error = "Please select at least one rule to save.";
      return;
    }

    isSaving = true;
    error = "";

    try {
      const payloads = toSave.map((r) => ({
        rule_id: r.rule_id,
        description: r.description,
        property_set: r.property_set || "Pset_Compliance",
        property_name: r.property_name || "",
        operator: r.operator || "==",
        check_value: r.check_value || null,
        value_min: r.value_min || null,
        value_max: r.value_max || null,
        unit: r.unit || "",
        severity: r.severity || "Medium",
        mechanism: "CODE",
        ruleset_id: formRulesetId || "EXTRACTED-STANDARDS",
        rule_category: "property_check",
        confidence: r.confidence || "0.9",
        extraction_method: "ai_extracted",
        needs_review: 1,
      }));

      const res = await ruleExtractionApi.bulkCreate(payloads);
      successMessage = `Successfully saved ${res.created_count} rules into the compliance library.`;
      extractedRules = [];
      table.clearSelection();
      if (fromQuickTest) showReturnPrompt = true;
    } catch (err: any) {
      error = err.message || "Failed to save rules to library.";
    } finally {
      isSaving = false;
    }
  }
</script>

<div class="mx-auto space-y-6">
  <!-- Header -->
  <PageHeader
    category="AI Engineering Tools"
    title="Rule Extraction Engine"
    subtitle="Transform natural language building codes, standards, and specifications into machine-executable OpenBIM compliance rules."
    icon={Sparkles}
  />

  {#if error}
    <div
      class="flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300"
    >
      <AlertCircle class="h-4 w-4 shrink-0" />
      <span>{error}</span>
    </div>
  {/if}

  {#if successMessage}
    <div
      class="flex items-center gap-2 rounded-xl border border-success-border/60 bg-success-bg/40 p-4 text-xs text-success"
    >
      <CheckCircle2 class="h-4 w-4 shrink-0 text-success" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <!-- Configuration & Input Section -->
  <div class="space-y-6 rounded-2xl border border-border-default bg-surface-card/40 p-6">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <!-- Document Source Selector -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <label
            for="rule-doc-source"
            class="block text-xs font-bold uppercase tracking-wider text-fg-muted"
          >
            Source Specification Document
          </label>
          <button
            type="button"
            onclick={() => (isUploadModalOpen = true)}
            class="inline-flex items-center gap-1 text-caption font-semibold text-accent hover:underline"
          >
            <Plus class="h-3 w-3" />
            <span>Add / Upload Document</span>
          </button>
        </div>
        <select
          id="rule-doc-source"
          bind:value={selectedDocId}
          class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
        >
          <option value={null}>-- Select from Document Library --</option>
          {#each documents as doc (doc.id)}
            <option value={doc.id}>{doc.filename} ({doc.doc_type || "Spec"})</option>
          {/each}
        </select>
      </div>

      <!-- LLM Model Selector -->
      <div class="space-y-2">
        <label
          for="rule-ai-model"
          class="block text-xs font-bold uppercase tracking-wider text-fg-muted"
        >
          Extraction Model / Parser
        </label>
        {#if llmModelsLoading}
          <p class="text-caption text-fg-muted">Loading available models…</p>
        {:else if llmModels.length === 0}
          <div
            class="rounded-xl border border-critical-border bg-critical-bg px-3.5 py-2.5 text-xs text-critical"
          >
            {llmModelsError || "No LLM provider configured for this organization."} Add one under
            <a href="#/external-providers" class="font-semibold underline hover:no-underline"
              >Admin → External providers</a
            >.
          </div>
        {:else}
          <select
            id="rule-ai-model"
            bind:value={selectedModel}
            class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
          >
            {#each llmModels as model (model.id)}
              <option value={model.id}>{model.name} — {formatModelMeta(model)}</option>
            {/each}
          </select>
          {#if !usingShortlist}
            <p class="text-caption text-fg-muted">
              Showing this provider's full catalogue — curate a shortlist under
              <a href="#/external-providers" class="font-semibold text-accent hover:underline"
                >Admin → External Providers → LLM Providers</a
              > for a shorter, priced list here.
            </p>
          {/if}
        {/if}
      </div>
    </div>

    {#if selectedDocId && isLoadingSections}
      <p class="text-xs text-fg-muted">Detecting sections…</p>
    {:else if selectedDocId && docSections.length > 0}
      <div
        role="group"
        aria-labelledby="rule-section-scope-label"
        class="space-y-3 rounded-xl border border-border-default bg-surface-canvas/60 p-4 shadow-xs"
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="space-y-0.5">
            <span id="rule-section-scope-label" class="block text-xs font-bold uppercase tracking-wider text-fg-muted">
              Document Outline & Extraction Scope
            </span>
            <p class="text-micro text-fg-muted">
              {docSections.length} clause{docSections.length === 1 ? "" : "s"} detected in Smart TOC.
              {#if selectedSectionKeys.size > 0}
                <span class="font-semibold text-accent">({selectedSectionKeys.size} scoped)</span>
              {:else}
                <span>Leave all unselected to process the whole document.</span>
              {/if}
              {#if sectionsEnhanced}
                <span class="ml-1 inline-flex items-center gap-1 text-accent font-medium">
                  <Sparkles class="h-3 w-3" /> AI-arranged
                </span>
              {/if}
            </p>
          </div>

          <!-- Action Toolbar: Regenerate, Export, Import, Select all / Clear -->
          <div class="flex flex-wrap items-center gap-2">
            <!-- Regenerate TOC Button -->
            <button
              type="button"
              disabled={isRegeneratingToc}
              onclick={handleRegenerateToc}
              class="inline-flex items-center gap-1.5 rounded-lg border border-border-default bg-surface-canvas px-2.5 py-1 text-xs font-medium text-fg-secondary hover:bg-surface-hover hover:text-fg-primary disabled:opacity-50 transition-colors"
              title="Re-extract and rebuild Smart TOC from DocLang XML, replacing the persisted DB record"
            >
              <RefreshCw class="h-3 w-3 {isRegeneratingToc ? 'animate-spin' : ''}" />
              <span>{isRegeneratingToc ? "Regenerating…" : "Regenerate TOC"}</span>
            </button>

            <!-- Export Dropdown -->
            <div class="relative inline-block">
              <button
                type="button"
                onclick={() => (isExportMenuOpen = !isExportMenuOpen)}
                class="inline-flex items-center gap-1.5 rounded-lg border border-border-default bg-surface-canvas px-2.5 py-1 text-xs font-medium text-fg-secondary hover:bg-surface-hover hover:text-fg-primary transition-colors"
                title="Export outline as JSON or CSV"
              >
                <Download class="h-3 w-3" />
                <span>Export</span>
                <ChevronDown class="h-3 w-3 text-fg-muted" />
              </button>
              {#if isExportMenuOpen}
                <div
                  class="absolute right-0 top-full z-20 mt-1 w-32 rounded-lg border border-border-default bg-surface-overlay p-1 shadow-lg backdrop-blur-md"
                >
                  <button
                    type="button"
                    onclick={() => handleExportToc("json")}
                    class="flex w-full items-center gap-2 rounded px-2.5 py-1.5 text-xs text-fg-secondary hover:bg-surface-hover hover:text-fg-primary text-left"
                  >
                    Export JSON
                  </button>
                  <button
                    type="button"
                    onclick={() => handleExportToc("csv")}
                    class="flex w-full items-center gap-2 rounded px-2.5 py-1.5 text-xs text-fg-secondary hover:bg-surface-hover hover:text-fg-primary text-left"
                  >
                    Export CSV
                  </button>
                </div>
              {/if}
            </div>

            <!-- Import Button -->
            <label
              class="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-border-default bg-surface-canvas px-2.5 py-1 text-xs font-medium text-fg-secondary hover:bg-surface-hover hover:text-fg-primary transition-colors {isImportingToc ? 'opacity-50 pointer-events-none' : ''}"
              title="Import corrected TOC from JSON or CSV file"
            >
              <Upload class="h-3 w-3" />
              <span>{isImportingToc ? "Importing…" : "Import"}</span>
              <input
                type="file"
                accept=".json,.csv"
                class="hidden"
                onchange={handleImportTocFile}
                disabled={isImportingToc}
              />
            </label>

            <div class="h-3.5 w-px bg-border-default"></div>

            <!-- Selection controls -->
            <div class="flex items-center gap-2 text-micro font-semibold">
              {#if selectedSectionKeys.size > 0}
                <button
                  type="button"
                  onclick={clearSectionSelection}
                  class="rounded bg-accent/15 px-2 py-0.5 text-accent hover:underline"
                >
                  Clear ({selectedSectionKeys.size})
                </button>
              {:else}
                <button
                  type="button"
                  onclick={selectAllSections}
                  class="text-accent hover:underline"
                >
                  Select all
                </button>
              {/if}
            </div>
          </div>
        </div>

        <!-- Section Tree Container: enlarged from max-h-64 to max-h-[30rem] -->
        <div class="max-h-[30rem] overflow-y-auto pr-1 rounded-lg border border-border-subtle bg-surface-canvas/40 p-2">
          <SectionTree
            nodes={sectionTree}
            selected={selectedSectionKeys}
            onViewSource={(node) =>
              (viewingDraftSource = {
                document_id: selectedDocId!,
                filename: documents.find((d) => d.id === selectedDocId)?.filename ?? "",
                page_number: node.page_number ?? null,
                bbox: node.bbox ?? null,
                snippet:
                  docSections.find((s) => s.id === node.id)?.text?.slice(0, 250) ||
                  node.section_name ||
                  node.section_number ||
                  "",
              })}
          />
        </div>
      </div>
    {:else if selectedDocId}
      <p class="text-xs text-fg-muted">
        No sections were detected — extraction will run over the whole document.
      </p>
    {:else}
      <div class="rounded-xl border border-dashed border-border-default bg-surface-canvas/30 p-6 text-center space-y-2">
        <p class="text-xs font-medium text-fg-secondary">
          No document selected — choose a specification from the library above to configure extraction scope.
        </p>
        <p class="text-caption text-fg-muted">
          Need to extract rules from text clauses? Add or paste them directly as a document.
        </p>
        <div>
          <button
            type="button"
            onclick={() => (isUploadModalOpen = true)}
            class="inline-flex items-center gap-1.5 rounded-lg border border-border-interactive bg-surface-overlay px-3 py-1.5 text-xs font-semibold text-fg-primary hover:bg-surface-hover hover:border-accent transition-colors"
          >
            <Plus class="h-3.5 w-3.5 text-accent" />
            <span>Add / Upload Specification</span>
          </button>
        </div>
      </div>
    {/if}

    <div class="flex justify-end pt-2">
      <button
        type="button"
        disabled={isExtracting || !selectedModel || !selectedDocId}
        aria-busy={isExtracting}
        onclick={handleExtract}
        class="inline-flex items-center gap-2 rounded-xl bg-accent px-6 py-2.5 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover {isExtracting
          ? 'disabled:cursor-progress'
          : 'disabled:opacity-50'}"
      >
        {#if isExtracting}
          <!-- Same spinner as LoadingState, on the accent button (border-current = the button's white text). -->
          <span
            class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
            aria-hidden="true"
          ></span>
        {:else}
          <Sparkles class="h-4 w-4" />
        {/if}
        <span role="status">
          {#if !isExtracting}
            Extract Compliance Rules
          {:else if extractionProgress && extractionProgress.total > 0}
            Extracting Rules via AI... ({extractionProgress.completed}/{extractionProgress.total})
          {:else}
            Extracting Rules via AI...
          {/if}
        </span>
      </button>
    </div>
  </div>

  <!-- Persisted Draft Review (document-sourced extractions) -->
  {#if selectedDocId && (isLoadingDrafts || draftRules.length > 0)}
    <div class="space-y-4">
      <div>
        <h2 class="text-lg font-bold tracking-tight text-fg-primary">
          Draft Review ({draftRules.length} draft{draftRules.length === 1 ? "" : "s"})
          {#if draftRules[0]?.proposed_rule.ruleset_id}
            <span class="ml-2 rounded-full border border-border-interactive bg-surface-card px-2.5 py-0.5 text-caption font-semibold text-fg-muted">
              ruleset {draftRules[0].proposed_rule.ruleset_id}
            </span>
          {/if}
        </h2>
        <p class="text-xs text-fg-muted">
          Accept or reject each candidate, then promote accepted drafts into the compliance rule
          library. Drafts persist across sessions.
        </p>
        <ReliabilityLegend class="mt-2" />
      </div>

      {#if draftReviewError}
        <Alert
          type="error"
          title="Draft review failed"
          message={draftReviewError}
          dismissible
          errors={draftReviewErrorLog}
          logTitle="Draft Review Error Log"
          logContext={{
            Action: draftReviewErrorAction,
            "Document ID": selectedDocId ?? undefined,
            Ruleset: draftRules[0]?.proposed_rule.ruleset_id,
          }}
          onDismiss={() => {
            draftReviewError = "";
            draftReviewErrorLog = [];
          }}
        />
      {/if}

      {#if isLoadingDrafts}
        <LoadingState message="Loading extraction drafts…" />
      {:else}
        <div
          class="flex flex-col items-center gap-3 rounded-2xl border border-border-default/90 bg-surface-canvas/80 p-3.5 md:flex-row"
        >
          <div class="relative w-full flex-1">
            <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted" />
            <input
              type="text"
              bind:value={draftTable.search}
              placeholder="Search drafts by reference, description, property..."
              class="w-full rounded-xl border border-border-default bg-surface-card py-2 pl-10 pr-4 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
            />
          </div>
          <select
            bind:value={draftTable.filters.status}
            class="rounded-xl border border-border-default bg-surface-card px-3 py-2 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
          >
            <option value="ALL">All Statuses</option>
            <option value="pending_review">Pending Review</option>
            <option value="accepted">Accepted</option>
            <option value="edited">Edited</option>
            <option value="rejected">Rejected</option>
          </select>
          <Button
            variant="outline"
            size="sm"
            onclick={previewDraftsAsIds}
            loading={previewingIds}
            disabled={!selectedDocId || draftRules.length === 0}
            title="Generate a buildingSMART IDS XML preview from this document's current extraction drafts"
          >
            {#if !previewingIds}<Download class="h-3.5 w-3.5" />{/if}
            <span>Preview as IDS XML</span>
          </Button>
          <Button
            variant="outline"
            size="sm"
            onclick={scanDraftConflicts}
            loading={isCheckingConflicts}
            disabled={!selectedDocId || draftRules.length === 0}
            title="Scan for cross-rule and cross-draft building code contradictions"
          >
            {#if !isCheckingConflicts}<AlertTriangle class="h-3.5 w-3.5 text-warning" />{/if}
            <span>Scan Conflicts</span>
          </Button>
        </div>

        <BulkActionBar
          selectedCount={draftTable.selectedCount}
          itemLabel="draft"
          onClearSelection={() => draftTable.clearSelection()}
        >
          {#snippet children()}
            <Button
              variant="outline"
              size="sm"
              onclick={acceptSelectedDrafts}
              loading={bulkAction === "accept"}
              disabled={bulkAction !== null}
              class="border-success-border bg-success-bg text-success hover:bg-success-bg hover:text-success"
            >
              {#if bulkAction !== "accept"}<Check class="h-3.5 w-3.5" />{/if}
              <span>
                {bulkAction === "accept"
                  ? `Accepting ${bulkProgress.done}/${bulkProgress.total}…`
                  : "Accept"}
              </span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onclick={promoteSelectedDrafts}
              loading={bulkAction === "promote"}
              disabled={bulkAction !== null}
              class="border-info-border bg-info-bg text-info hover:bg-info-bg hover:text-info"
            >
              {#if bulkAction !== "promote"}<Upload class="h-3.5 w-3.5 rotate-180" />{/if}
              <span>
                {bulkAction === "promote"
                  ? `Promoting ${bulkProgress.done}/${bulkProgress.total}…`
                  : "Promote to Library"}
              </span>
            </Button>
          {/snippet}
        </BulkActionBar>

        <div class="overflow-hidden rounded-2xl border border-border-default bg-surface-card/40">
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-fg-secondary">
              <thead
                class="border-b border-border-default bg-surface-canvas text-caption font-semibold uppercase tracking-wider text-fg-muted"
              >
                <tr>
                  <th class="w-10 px-3 py-3 text-center">
                    <TableCheckbox
                      checked={draftTable.allFilteredSelected}
                      indeterminate={draftTable.someFilteredSelected}
                      onchange={() => draftTable.toggleSelectAll()}
                      title="Select all drafts"
                    />
                  </th>
                  <th class="px-3 py-3">Status</th>
                  <th class="px-3 py-3">Rule Ref</th>
                  <th class="px-3 py-3">Description</th>
                  <th class="px-3 py-3">Pset / Property</th>
                  <th class="px-3 py-3">Check</th>
                  <th class="px-3 py-3">Severity</th>
                  <th class="px-3 py-3">Reliability</th>
                  <th class="px-3 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-border-subtle">
                {#each draftTable.paginated as draft (draft.id)}
                  <tr
                    class="transition-colors hover:bg-surface-hover {draftTable.isSelected(draft.id!)
                      ? 'bg-surface-selected'
                      : ''} {draftTable.isPending(draft.id!) ? 'opacity-50 pointer-events-none' : ''}"
                  >
                    <td class="px-3 py-3 text-center">
                      <TableCheckbox
                        checked={draftTable.isSelected(draft.id!)}
                        onchange={() => draftTable.toggleSelect(draft.id!)}
                        ariaLabel={`Select draft ${draft.proposed_rule.rule_id}`}
                      />
                    </td>
                    <td class="px-3 py-3">
                      <span
                        class="rounded-md border px-2 py-0.5 text-micro font-semibold uppercase tracking-wider
                          {draft.status === 'accepted' || draft.status === 'edited'
                          ? 'border-success-border bg-success-bg text-success'
                          : draft.status === 'rejected'
                            ? 'border-critical-border bg-critical-bg text-critical'
                            : 'border-warning-border bg-warning-bg text-warning'}"
                      >
                        {draft.status.replace("_", " ")}
                      </span>
                    </td>
                    <td class="px-3 py-3 font-mono font-bold text-fg-primary">
                      <div class="flex items-center gap-1.5">
                        <span>{draft.proposed_rule.rule_id}</span>
                        {#if draft.conflicts && draft.conflicts.length > 0}
                          <button
                            type="button"
                            onclick={() => (inspectingConflictDraft = draft)}
                            class="inline-flex items-center gap-1 rounded-md border border-warning-border bg-warning-bg px-1.5 py-0.5 text-[10px] font-semibold text-warning transition-transform hover:scale-105"
                            title={`${draft.conflicts.length} conflicting specification(s) detected. Click to inspect.`}
                          >
                            <AlertTriangle class="size-3 text-warning" />
                            <span>{draft.conflicts.length} conflict{draft.conflicts.length === 1 ? '' : 's'}</span>
                          </button>
                        {/if}
                      </div>
                    </td>
                    <td class="max-w-xs truncate px-3 py-3" title={draft.proposed_rule.description}>
                      <div class="flex items-center gap-1.5">
                        <span class="truncate">{draft.proposed_rule.description}</span>
                        {#if draft.proposed_rule.applies_when && Object.keys(draft.proposed_rule.applies_when).length > 0}
                          <span
                            class="shrink-0 rounded-md border border-amber-800 bg-amber-950/50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-300"
                            title={`Scoped: ${JSON.stringify(draft.proposed_rule.applies_when)}`}
                          >
                            Conditional
                          </span>
                        {/if}
                      </div>
                    </td>
                    <td class="px-3 py-3 font-mono text-fg-muted">
                      <div class="flex items-center gap-1.5">
                        <span
                          >{draft.proposed_rule.property_set || "—"} / {draft.proposed_rule
                            .property_name || "—"}</span
                        >
                        {#if draft.review_notes?.startsWith("bSDD grounding")}
                          <span
                            class="rounded-md border border-success-border bg-success-bg px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-success"
                            title={draft.review_notes}
                          >
                            bSDD Grounded
                          </span>
                        {/if}
                      </div>
                    </td>
                    <td class="px-3 py-3 font-mono text-cyan-300">
                      {draft.proposed_rule.operator || "=="}
                      {draft.proposed_rule.check_value ||
                        (draft.proposed_rule.value_min
                          ? `[${draft.proposed_rule.value_min}..${draft.proposed_rule.value_max}]`
                          : "")}
                    </td>
                    <td class="px-3 py-3">{draft.proposed_rule.severity}</td>
                    <td class="px-3 py-3">
                      <ReliabilityBadge reliability={draft.reliability} />
                    </td>
                    <td class="whitespace-nowrap px-3 py-3 text-right">
                      <div class="flex items-center justify-end gap-1">
                        {#if draft.status === "pending_review"}
                          <button
                            type="button"
                            onclick={() => reviewDraftRow(draft, "accepted")}
                            class="rounded-lg bg-surface-card p-1.5 text-success transition-colors hover:bg-success-bg/60"
                            title="Accept draft"
                          >
                            <Check class="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            onclick={() => reviewDraftRow(draft, "rejected")}
                            class="rounded-lg bg-surface-card p-1.5 text-critical transition-colors hover:bg-critical-bg/60"
                            title="Reject draft"
                          >
                            <X class="h-3.5 w-3.5" />
                          </button>
                        {/if}
                        <button
                          type="button"
                          onclick={() => viewDraftSource(draft)}
                          class="rounded-lg bg-surface-overlay p-1.5 text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
                          title="View source in document"
                        >
                          <Eye class="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onclick={() => openEditDraftModal(draft)}
                          class="rounded-lg bg-surface-overlay p-1.5 text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
                          title="Edit draft"
                        >
                          <Pencil class="h-3.5 w-3.5" />
                        </button>
                        {#if draft.status === "accepted" || draft.status === "edited"}
                          <button
                            type="button"
                            onclick={() => promoteDraft(draft)}
                            class="rounded-lg bg-blue-950/40 p-1.5 text-blue-300 transition-colors hover:bg-blue-900/60"
                            title="Promote to rule library"
                          >
                            <Upload class="h-3.5 w-3.5 rotate-180" />
                          </button>
                        {/if}
                      </div>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <TablePagination
            currentPage={draftTable.page}
            pageSize={draftTable.pageSize}
            totalItems={draftTable.totalItems}
            onPageChange={(p) => (draftTable.requestedPage = p)}
            onPageSizeChange={(size) => {
              draftTable.pageSize = size;
              draftTable.requestedPage = 1;
            }}
          />
        </div>
      {/if}
    </div>
  {/if}

  <!-- Extraction Results Review -->
  {#if extractedRules.length > 0}
    <div class="space-y-4">
      <div class="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h2 class="text-lg font-bold tracking-tight text-fg-primary">
            Extracted Rules Review ({extractedRules.length} rules identified)
          </h2>
          <p class="text-xs text-fg-muted">
            Review, modify properties, filter, and select rules to persist to the library.
          </p>
          <ReliabilityLegend class="mt-2" />
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <div class="flex flex-col">
            <label
              for="extraction-ruleset"
              class="mb-0.5 text-micro font-semibold uppercase tracking-wider text-fg-muted"
              >Rule Folder</label
            >
            <input
              id="extraction-ruleset"
              type="text"
              bind:value={formRulesetId}
              class="w-44 rounded-xl border border-border-default bg-surface-canvas px-3 py-1.5 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
            />
          </div>

          <button
            type="button"
            onclick={addManualDraftRule}
            class="inline-flex items-center gap-1.5 rounded-xl bg-surface-overlay px-4 py-2 text-xs font-semibold text-fg-primary transition-all hover:bg-surface-hover"
          >
            <Plus class="h-3.5 w-3.5" />
            <span>Add Rule</span>
          </button>

          <button
            type="button"
            disabled={isSaving || table.selectedCount === 0}
            onclick={handleSaveSelected}
            class="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2 text-xs font-semibold text-white shadow-xs shadow-emerald-500/20 transition-all hover:bg-emerald-500 disabled:opacity-50"
          >
            <Save class="h-3.5 w-3.5" />
            <span
              >{isSaving ? "Saving..." : `Save Selected (${table.selectedCount}) to Library`}</span
            >
          </button>
        </div>
      </div>

      <!-- Filter Toolbar -->
      <div
        class="flex flex-col items-center gap-3 rounded-2xl border border-border-default/90 bg-surface-canvas/80 p-3.5 md:flex-row"
      >
        <div class="relative w-full flex-1">
          <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted" />
          <input
            type="text"
            bind:value={table.search}
            placeholder="Search draft rules by reference, description, property..."
            class="w-full rounded-xl border border-border-default bg-surface-card py-2 pl-10 pr-4 text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
          />
        </div>

        <div class="flex w-full items-center gap-2 md:w-auto">
          <select
            bind:value={table.filters.severity}
            class="rounded-xl border border-border-default bg-surface-card px-3 py-2 text-xs text-fg-primary focus:border-accent focus:outline-hidden"
          >
            <option value="ALL">All Severities</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>
      </div>

      <!-- Bulk Action Bar -->
      <BulkActionBar
        selectedCount={table.selectedCount}
        itemLabel="draft rule"
        onClearSelection={() => {
          table.clearSelection();
        }}
        onBulkEdit={() => (isDraftBulkEditModalOpen = true)}
        onBulkExport={exportDraftRulesToCsv}
        onBulkDelete={() => (isDraftBulkDeleteModalOpen = true)}
      />

      <!-- Table Container -->
      <div class="overflow-hidden rounded-2xl border border-border-default bg-surface-card/40">
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-fg-secondary">
            <thead
              class="border-b border-border-default bg-surface-canvas text-caption font-semibold uppercase tracking-wider text-fg-muted"
            >
              <tr>
                <th class="w-10 px-3 py-3 text-center">
                  <TableCheckbox
                    checked={table.allFilteredSelected}
                    indeterminate={table.someFilteredSelected}
                    onchange={() => table.toggleSelectAll()}
                    title="Select all draft rules"
                  />
                </th>
                <SortHeader
                  column="rule_id"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                  customClass="py-3 px-3"
                >
                  Rule Ref
                </SortHeader>
                <SortHeader
                  column="description"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                  customClass="py-3 px-3"
                >
                  Description
                </SortHeader>
                <SortHeader
                  column="property_set"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                  customClass="py-3 px-3"
                >
                  Property Set
                </SortHeader>
                <SortHeader
                  column="property_name"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                  customClass="py-3 px-3"
                >
                  Property
                </SortHeader>
                <SortHeader
                  column="operator"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                  customClass="py-3 px-3"
                >
                  Op
                </SortHeader>
                <th class="px-3 py-3">Target Value</th>
                <SortHeader
                  column="severity"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                  customClass="py-3 px-3"
                >
                  Severity
                </SortHeader>
                <th class="px-3 py-3">Reliability</th>
                <th class="px-3 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border-subtle">
              {#each table.paginated as rule (rule.rowId)}
                <tr
                  class="transition-colors hover:bg-surface-hover {table.isSelected(rule.rowId)
                    ? 'bg-surface-selected'
                    : ''} {table.isPending(rule.rowId) ? 'opacity-50 pointer-events-none' : ''}"
                >
                  <td class="px-3 py-3 text-center">
                    <TableCheckbox
                      checked={table.isSelected(rule.rowId)}
                      onchange={() => table.toggleSelect(rule.rowId)}
                      ariaLabel={`Select rule ${rule.rule_id}`}
                    />
                  </td>
                  <td class="px-3 py-3 font-mono font-bold text-fg-primary">
                    <input
                      type="text"
                      bind:value={rule.rule_id}
                      class="w-24 border-b border-transparent bg-transparent font-mono text-xs font-bold text-fg-primary hover:border-border-interactive focus:border-accent focus:outline-hidden"
                    />
                  </td>
                  <td class="px-3 py-3">
                    <input
                      type="text"
                      bind:value={rule.description}
                      class="w-full min-w-[200px] border-b border-transparent bg-transparent text-xs text-fg-secondary hover:border-border-interactive focus:border-accent focus:outline-hidden"
                    />
                  </td>
                  <td class="px-3 py-3 font-mono text-fg-muted">
                    <input
                      type="text"
                      bind:value={rule.property_set}
                      class="w-28 border-b border-transparent bg-transparent text-xs text-fg-muted hover:border-border-interactive focus:border-accent focus:outline-hidden"
                    />
                  </td>
                  <td class="px-3 py-3 font-mono text-fg-secondary">
                    <input
                      type="text"
                      bind:value={rule.property_name}
                      class="w-28 border-b border-transparent bg-transparent text-xs text-fg-secondary hover:border-border-interactive focus:border-accent focus:outline-hidden"
                    />
                  </td>
                  <td class="px-3 py-3 font-mono text-fg-muted">
                    {rule.operator || "=="}
                  </td>
                  <td class="px-3 py-3 font-mono text-cyan-300">
                    {rule.check_value ||
                      (rule.value_min ? `[${rule.value_min}..${rule.value_max}]` : "-")}
                  </td>
                  <td class="px-3 py-3">
                    <select
                      bind:value={rule.severity}
                      class="rounded border border-border-default bg-surface-canvas px-2 py-0.5 text-micro font-semibold text-fg-primary focus:outline-hidden"
                    >
                      <option value="Critical">Critical</option>
                      <option value="High">High</option>
                      <option value="Medium">Medium</option>
                      <option value="Low">Low</option>
                    </select>
                  </td>
                  <td class="px-3 py-3">
                    <LiveReliability
                      propertySet={rule.property_set}
                      propertyName={rule.property_name}
                      initial={rule.reliability ?? null}
                    />
                  </td>
                  <td class="whitespace-nowrap px-3 py-3 text-right">
                    <div class="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        onclick={() => (viewingDraftRule = rule)}
                        class="rounded-lg bg-surface-overlay p-1.5 text-fg-secondary transition-colors hover:bg-surface-hover hover:text-fg-primary"
                        title="Inspect draft details"
                      >
                        <Eye class="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onclick={() => removeDraftRule(rule.rowId)}
                        class="rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-rose-950/30 hover:text-rose-400"
                        title="Remove draft rule"
                      >
                        <Trash2 class="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
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
          onPageSizeChange={(size) => {
            table.pageSize = size;
            table.requestedPage = 1;
          }}
        />
      </div>
    </div>
  {/if}
</div>

<!-- Saved-from-quick-test: prompt to switch back to the wizard tab -->
<Modal
  isOpen={showReturnPrompt}
  title="Rules saved"
  subtitle={`Saved to "${formRulesetId}"`}
  icon={CheckCircle2}
  onClose={() => (showReturnPrompt = false)}
>
  <p class="text-fg-secondary">
    You can switch back to the Run Compliance Audit tab now — it will pick up this ruleset
    automatically.
  </p>
  {#snippet footer()}
    <button
      type="button"
      onclick={() => (showReturnPrompt = false)}
      class="rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-xs transition-all hover:bg-accent-hover"
    >
      Got it
    </button>
  {/snippet}
</Modal>

<!-- Draft Source Annotation Modal: jumps to and highlights the page/snippet a draft came from -->
{#if viewingDraftSource}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-border-default bg-surface-card shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-border-default px-6 py-4">
        <div>
          <h2 class="text-base font-bold tracking-tight text-fg-primary">{viewingDraftSource.filename}</h2>
          {#if viewingDraftSource.page_number}
            <p class="mt-0.5 text-xs text-fg-muted">Page {viewingDraftSource.page_number}</p>
          {/if}
        </div>
        <button
          type="button"
          onclick={() => (viewingDraftSource = null)}
          class="rounded-lg p-1 text-fg-muted hover:bg-surface-hover hover:text-fg-primary"
        >
          <X class="h-5 w-5" />
        </button>
      </div>
      <div class="flex-1 overflow-hidden">
        <DocumentViewer
          documentId={viewingDraftSource.document_id}
          page={viewingDraftSource.page_number}
          highlightText={viewingDraftSource.snippet}
          bbox={viewingDraftSource.bbox}
        />
      </div>
    </div>
  </div>
{/if}

{#if draftSourceError}
  <div
    class="fixed bottom-6 right-6 z-50 max-w-sm rounded-xl border border-critical-border bg-critical-bg px-4 py-3 text-xs text-critical shadow-2xl backdrop-blur-md"
  >
    <div class="flex items-start justify-between gap-3">
      <span>{draftSourceError}</span>
      <button
        type="button"
        onclick={() => (draftSourceError = "")}
        class="shrink-0 text-critical hover:text-fg-primary"
        aria-label="Dismiss error"
      >
        <X class="h-3.5 w-3.5" />
      </button>
    </div>
  </div>
{/if}

<!-- Edit Draft Modal -->
{#if editingDraft && editForm}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md">
    <div
      class="w-full max-w-lg space-y-4 overflow-hidden rounded-2xl border border-border-default bg-surface-card p-6 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-border-default pb-3">
        <div class="flex items-center gap-2">
          <Pencil class="h-4 w-4 text-accent" />
          <h3 class="font-mono text-sm font-bold text-fg-primary">Edit Draft</h3>
        </div>
        <button
          type="button"
          onclick={closeEditDraftModal}
          class="rounded-lg p-1 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      {#if draftReviewError}
        <Alert
          type="error"
          title="Could not save changes"
          message={draftReviewError}
          errors={draftReviewErrorLog}
          logTitle="Draft Edit Error Log"
          logContext={{ Action: draftReviewErrorAction, "Document ID": selectedDocId ?? undefined }}
        />
      {/if}

      <div class="space-y-3 text-xs">
        <div class="space-y-1">
          <label for="edit-draft-description" class="block font-semibold text-fg-secondary"
            >Description</label
          >
          <textarea
            id="edit-draft-description"
            bind:value={editForm.description}
            rows="2"
            class="w-full rounded-xl border border-border-default bg-surface-canvas p-3 text-fg-primary focus:border-accent focus:outline-hidden"
          ></textarea>
        </div>

        <div class="grid grid-cols-2 gap-2">
          <div class="space-y-1">
            <div class="flex items-center justify-between gap-2">
              <label for="edit-draft-target" class="block font-semibold text-fg-secondary"
                >Target IFC Class</label
              >
              <button
                type="button"
                onclick={() => suggestViaAI("target_ifc_class")}
                disabled={suggestingField !== null}
                class="text-[10px] font-semibold text-accent hover:underline disabled:opacity-50"
                title="Ask AI to suggest a bSDD class matching this name"
              >
                {suggestingField === "target_ifc_class" ? "Suggesting…" : "Suggest via AI"}
              </button>
            </div>
            <input
              id="edit-draft-target"
              type="text"
              bind:value={editForm.target_ifc_class}
              class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 font-mono text-fg-primary focus:border-accent focus:outline-hidden"
            />
          </div>
          <div class="space-y-1">
            <label for="edit-draft-pset" class="block font-semibold text-fg-secondary"
              >Property Set</label
            >
            <input
              id="edit-draft-pset"
              type="text"
              bind:value={editForm.property_set}
              class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 font-mono text-fg-primary focus:border-accent focus:outline-hidden"
            />
          </div>
          <div class="space-y-1">
            <div class="flex items-center justify-between gap-2">
              <label for="edit-draft-prop" class="block font-semibold text-fg-secondary">Property</label>
              <button
                type="button"
                onclick={() => suggestViaAI("property_name")}
                disabled={suggestingField !== null}
                class="text-[10px] font-semibold text-accent hover:underline disabled:opacity-50"
                title="Ask AI to suggest a bSDD property matching this name"
              >
                {suggestingField === "property_name" ? "Suggesting…" : "Suggest via AI"}
              </button>
            </div>
            <input
              id="edit-draft-prop"
              type="text"
              bind:value={editForm.property_name}
              class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 font-mono text-fg-primary focus:border-accent focus:outline-hidden"
            />
          </div>
          <div class="space-y-1">
            <label for="edit-draft-operator" class="block font-semibold text-fg-secondary"
              >Operator</label
            >
            <select
              id="edit-draft-operator"
              bind:value={editForm.operator}
              class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 text-fg-primary focus:outline-hidden"
            >
              <option value="==">== (Equals)</option>
              <option value="!=">!= (Not equals)</option>
              <option value=">">&gt; (Greater than)</option>
              <option value=">=">&gt;= (Greater or equal)</option>
              <option value="<">&lt; (Less than)</option>
              <option value="<=">&lt;= (Less or equal)</option>
              <option value="between">between</option>
              <option value="exists">exists</option>
            </select>
          </div>
          <div class="space-y-1">
            <label for="edit-draft-value" class="block font-semibold text-fg-secondary"
              >Check Value</label
            >
            <input
              id="edit-draft-value"
              type="text"
              bind:value={editForm.check_value}
              class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 font-mono text-fg-primary focus:border-accent focus:outline-hidden"
            />
          </div>
          <div class="space-y-1">
            <label for="edit-draft-severity" class="block font-semibold text-fg-secondary"
              >Severity</label
            >
            <select
              id="edit-draft-severity"
              bind:value={editForm.severity}
              class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 text-fg-primary focus:outline-hidden"
            >
              <option value="mandatory">Mandatory</option>
              <option value="recommended">Recommended</option>
            </select>
          </div>
        </div>
      </div>

      <div class="flex justify-end gap-2 border-t border-border-default pt-2">
        <button
          type="button"
          onclick={closeEditDraftModal}
          class="rounded-xl px-4 py-2 text-xs font-semibold text-fg-muted hover:text-fg-primary"
        >
          Cancel
        </button>
        <button
          type="button"
          onclick={saveEditedDraft}
          class="rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white hover:bg-accent-hover"
        >
          Save Edits
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Inspect Draft Rule Modal -->
{#if viewingDraftRule}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md">
    <div
      class="w-full max-w-lg space-y-4 overflow-hidden rounded-2xl border border-border-default bg-surface-card p-6 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-border-default pb-3">
        <div class="flex items-center gap-2">
          <FileText class="h-4 w-4 text-accent" />
          <h3 class="font-mono text-sm font-bold text-fg-primary">
            {viewingDraftRule.rule_id || "Draft Rule"}
          </h3>
        </div>
        <button
          type="button"
          onclick={() => (viewingDraftRule = null)}
          class="rounded-lg p-1 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <div class="space-y-3 text-xs">
        <div>
          <span class="mb-1 block font-semibold text-fg-muted">Description</span>
          <div class="rounded-xl border border-border-default bg-surface-canvas/60 p-3 text-fg-secondary">
            {viewingDraftRule.description || "No description"}
          </div>
        </div>

        <div
          class="grid grid-cols-2 gap-2 rounded-xl border border-border-default bg-surface-canvas p-3 font-mono text-caption"
        >
          <div>
            <span class="text-fg-muted">Pset:</span>
            <span class="text-fg-secondary">{viewingDraftRule.property_set || "—"}</span>
          </div>
          <div>
            <span class="text-fg-muted">Property:</span>
            <BsddBadge
              kind="property"
              value={viewingDraftRule.property_name}
              propertySet={viewingDraftRule.property_set}
              class="text-fg-secondary"
            />
          </div>
          <div>
            <span class="text-fg-muted">Operator:</span>
            <span class="text-cyan-300">{viewingDraftRule.operator || "=="}</span>
          </div>
          <div>
            <span class="text-fg-muted">Target Value:</span>
            <span class="text-emerald-300">{viewingDraftRule.check_value || "—"}</span>
          </div>
          <div>
            <span class="text-fg-muted">Severity:</span>
            <span class="font-semibold text-amber-400">{viewingDraftRule.severity}</span>
          </div>
        </div>
      </div>

      <div class="flex justify-end pt-2">
        <button
          type="button"
          onclick={() => (viewingDraftRule = null)}
          class="rounded-xl bg-surface-overlay px-4 py-2 text-xs font-semibold text-fg-primary transition-colors hover:bg-surface-hover"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Bulk Edit Modal for Draft Rules -->
{#if isDraftBulkEditModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md">
    <div
      class="w-full max-w-md space-y-4 overflow-hidden rounded-2xl border border-border-default bg-surface-card p-6 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-border-default pb-3">
        <div class="flex items-center gap-2">
          <SlidersHorizontal class="h-4 w-4 text-blue-400" />
          <h3 class="text-sm font-bold text-fg-primary">
            Bulk Edit Draft Rules ({table.selectedCount} selected)
          </h3>
        </div>
        <button
          type="button"
          onclick={() => (isDraftBulkEditModalOpen = false)}
          class="rounded-lg p-1 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <div class="space-y-3 text-xs">
        <div class="space-y-1">
          <label for="bulk-draft-severity" class="block font-semibold text-fg-secondary"
            >Severity</label
          >
          <select
            id="bulk-draft-severity"
            bind:value={bulkDraftSeverity}
            class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 text-fg-primary focus:border-accent focus:outline-hidden"
          >
            <option value="no_change">-- Keep Current Severity --</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>

        <div class="space-y-1">
          <label for="bulk-draft-pset" class="block font-semibold text-fg-secondary"
            >Property Set</label
          >
          <input
            id="bulk-draft-pset"
            type="text"
            bind:value={bulkDraftPset}
            placeholder="Leave empty to keep current"
            class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 text-fg-primary placeholder:text-fg-muted focus:border-accent focus:outline-hidden"
          />
        </div>

        <div class="space-y-1">
          <label for="bulk-draft-op" class="block font-semibold text-fg-secondary">Operator</label>
          <select
            id="bulk-draft-op"
            bind:value={bulkDraftOperator}
            class="w-full rounded-xl border border-border-default bg-surface-canvas px-3 py-2 text-fg-primary focus:border-accent focus:outline-hidden"
          >
            <option value="no_change">-- Keep Current Operator --</option>
            <option value="==">== (Equals)</option>
            <option value="!=">!= (Not equals)</option>
            <option value=">">&gt; (Greater than)</option>
            <option value=">=">&gt;= (Greater or equal)</option>
            <option value="<">&lt; (Less than)</option>
            <option value="<=">&lt;= (Less or equal)</option>
            <option value="contains">contains</option>
            <option value="exists">exists</option>
          </select>
        </div>
      </div>

      <div class="flex justify-end gap-2 border-t border-border-default pt-2">
        <button
          type="button"
          onclick={() => (isDraftBulkEditModalOpen = false)}
          class="rounded-xl px-4 py-2 text-xs font-semibold text-fg-muted hover:text-fg-primary"
        >
          Cancel
        </button>
        <button
          type="button"
          onclick={applyDraftBulkEdit}
          class="rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white hover:bg-accent-hover"
        >
          Apply Changes
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Bulk Delete Draft Rules Confirmation -->
<ConfirmModal
  bind:isOpen={isDraftBulkDeleteModalOpen}
  title="Delete Selected Draft Rules"
  message={`Are you sure you want to remove ${table.selectedCount} selected draft rule(s) from this extraction batch?`}
  confirmText="Delete Draft Rules"
  danger={true}
  optimistic={true}
  onConfirm={confirmBulkDeleteDrafts}
  onCancel={() => (isDraftBulkDeleteModalOpen = false)}
/>

<!-- Building Code Conflict Inspector Modal -->
{#if inspectingConflictDraft}
  <Modal
    isOpen={!!inspectingConflictDraft}
    title="Building Code Conflict Inspector"
    subtitle={`Detected ${inspectingConflictDraft.conflicts?.length || 0} contradictory specification(s) for ${inspectingConflictDraft.proposed_rule.rule_id}`}
    icon={AlertTriangle}
    maxWidth="max-w-2xl"
    onClose={() => (inspectingConflictDraft = null)}
  >
    <div class="space-y-4 text-xs text-fg-secondary">
      <!-- Candidate rule summary card -->
      <div class="rounded-xl border border-border-default bg-surface-canvas p-3">
        <div class="flex items-center justify-between">
          <span class="font-bold text-fg-primary">Candidate Extracted Rule</span>
          <span class="font-mono text-micro text-fg-muted">Draft #{inspectingConflictDraft.id}</span>
        </div>
        <div class="mt-2 grid grid-cols-2 gap-2 text-micro">
          <div>
            <span class="text-fg-muted">Target Entity:</span>
            <span class="font-mono font-semibold text-fg-primary ml-1">{inspectingConflictDraft.proposed_rule.target_ifc_class}</span>
          </div>
          <div>
            <span class="text-fg-muted">Property:</span>
            <span class="font-mono text-fg-primary ml-1">{inspectingConflictDraft.proposed_rule.property_set || "—"} / {inspectingConflictDraft.proposed_rule.property_name}</span>
          </div>
          <div>
            <span class="text-fg-muted">Constraint:</span>
            <span class="font-mono font-bold text-accent ml-1">
              {inspectingConflictDraft.proposed_rule.operator} {inspectingConflictDraft.proposed_rule.check_value || `${inspectingConflictDraft.proposed_rule.value_min}..${inspectingConflictDraft.proposed_rule.value_max}`}
            </span>
          </div>
          <div>
            <span class="text-fg-muted">Standard / Section:</span>
            <span class="text-fg-primary ml-1">{inspectingConflictDraft.clause?.parent_section || inspectingConflictDraft.proposed_rule.ruleset_id || "Unspecified"}</span>
          </div>
        </div>
        {#if inspectingConflictDraft.proposed_rule.description}
          <p class="mt-2 text-micro italic text-fg-muted">{inspectingConflictDraft.proposed_rule.description}</p>
        {/if}
      </div>

      <!-- Conflicts list -->
      <div class="space-y-3">
        <h4 class="font-semibold text-fg-primary">Contradictory Specifications & Standards</h4>
        {#each inspectingConflictDraft.conflicts || [] as conflict, idx (idx)}
          <div class="rounded-xl border border-warning-border/80 bg-warning-bg/20 p-3.5 space-y-2">
            <div class="flex items-center justify-between">
              <span class="font-bold text-fg-primary flex items-center gap-1.5">
                <AlertTriangle class="size-3.5 text-warning" />
                <span>Conflicting Standard: {conflict.conflicting_reference}</span>
              </span>
              <span
                class="rounded-md border px-2 py-0.5 text-micro font-semibold uppercase tracking-wider
                  {conflict.severity === 'critical'
                    ? 'border-critical-border bg-critical-bg text-critical'
                    : 'border-warning-border bg-warning-bg text-warning'}"
              >
                {conflict.conflict_type === 'mutually_exclusive_range' ? 'Mutually Exclusive' : 'Threshold Discrepancy'}
              </span>
            </div>

            <p class="text-xs text-fg-secondary leading-relaxed">{conflict.message}</p>

            {#if conflict.resolution_suggestion}
              <div class="rounded-lg border border-border-default/60 bg-surface-card/60 p-2 text-micro text-fg-muted">
                <strong class="text-fg-primary">Recommendation:</strong> {conflict.resolution_suggestion}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    </div>

    {#snippet footer()}
      <div class="flex items-center justify-between w-full">
        <Button
          variant="outline"
          size="sm"
          onclick={() => {
            const draftToReject = inspectingConflictDraft;
            inspectingConflictDraft = null;
            if (draftToReject) reviewDraftRow(draftToReject, "rejected");
          }}
          class="border-critical-border text-critical hover:bg-critical-bg"
        >
          Reject Draft
        </Button>
        <div class="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onclick={() => {
              const draftToEdit = inspectingConflictDraft;
              inspectingConflictDraft = null;
              if (draftToEdit) openEditDraftModal(draftToEdit);
            }}
          >
            Edit Candidate Rule
          </Button>
          <Button
            variant="primary"
            size="sm"
            onclick={() => (inspectingConflictDraft = null)}
          >
            Done
          </Button>
        </div>
      </div>
    {/snippet}
  </Modal>
{/if}

<DocumentUploadModal
  isOpen={isUploadModalOpen}
  onClose={() => (isUploadModalOpen = false)}
  onUploaded={handleDocumentAdded}
/>
