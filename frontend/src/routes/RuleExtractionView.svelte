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
  } from "lucide-svelte";
  import { documentsApi, ruleExtractionApi } from "../lib/api";
  import type {
    DocumentItem,
    DocumentSection,
    ExtractedRule,
    RuleExtractionDraft,
    RuleSourceResponse,
    SectionTreeNode,
  } from "../lib/types";
  import DocumentViewer from "../lib/components/DocumentViewer.svelte";
  import SectionTree from "../lib/components/SectionTree.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import Modal from "../lib/components/Modal.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
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
  let rawText = $state("");
  let selectedModel = $state("gemini-2.5-flash");
  let viewingDraftRule: ExtractedRule | null = $state(null);

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

  $effect(() => {
    const docId = selectedDocId;
    draftRules = [];
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

  function openEditDraftModal(draft: RuleExtractionDraft) {
    editingDraft = draft;
    // Edit on a clone, not the live table row -- otherwise a bound input
    // would mutate draftRules before the PATCH confirms the edit was saved.
    editForm = { ...draft.proposed_rule };
  }

  function closeEditDraftModal() {
    editingDraft = null;
    editForm = null;
  }

  function saveEditedDraft() {
    if (!editingDraft || !editForm) return;
    const draftId = editingDraft.id!;
    ruleExtractionApi
      .reviewDraft(draftId, { status: "edited", edited_rule: editForm })
      .then((updated) => {
        draftRules = draftRules.map((d) => (d.id === draftId ? updated : d));
        closeEditDraftModal();
      })
      .catch((err: any) => {
        error = err.message || "Failed to save draft edits.";
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

  async function promoteDraft(draft: RuleExtractionDraft): Promise<void> {
    try {
      await ruleExtractionApi.promoteDraft(draft.id!);
      draftRules = draftRules.filter((d) => d.id !== draft.id);
      successMessage = `Promoted "${draft.proposed_rule.rule_id}" into the compliance rule library.`;
    } catch (err: any) {
      error = err.message || "Failed to promote draft.";
    }
  }

  async function promoteSelectedDrafts(): Promise<void> {
    const toPromote = draftTable.selectedRows.filter(
      (d) => d.status === "accepted" || d.status === "edited",
    );
    error = "";
    for (const draft of toPromote) {
      try {
        await ruleExtractionApi.promoteDraft(draft.id!);
      } catch (err: any) {
        error = err.message || `Failed to promote "${draft.proposed_rule.rule_id}".`;
      }
    }
    const promotedIds = new Set(toPromote.map((d) => d.id));
    draftRules = draftRules.filter((d) => !promotedIds.has(d.id));
    draftTable.clearSelection();
    if (!error) {
      successMessage = `Promoted ${toPromote.length} draft(s) into the compliance rule library.`;
    }
  }

  async function acceptSelectedDrafts(): Promise<void> {
    const toAccept = draftTable.selectedRows.filter((d) => d.status === "pending_review");
    for (const draft of toAccept) {
      await reviewDraft(draft, "accepted");
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

  const LLM_MODELS = [
    { id: "gemini-2.5-flash", name: "Google Gemini 2.5 Flash (Recommended)" },
    { id: "gemini-1.5-pro", name: "Google Gemini 1.5 Pro" },
    { id: "gpt-4o", name: "OpenAI GPT-4o" },
    { id: "claude-3-5-sonnet", name: "Anthropic Claude 3.5 Sonnet" },
    { id: "ollama/llama3", name: "Local Ollama Llama 3" },
  ];

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

    // Large documents run many clause-nodes through the LLM concurrently on
    // the backend (extraction_progress) — poll it while the request is in
    // flight so the button shows real progress instead of a static spinner.
    let pollInterval: ReturnType<typeof setInterval> | undefined;
    if (selectedDocId) {
      const docId = selectedDocId;
      pollInterval = setInterval(async () => {
        try {
          const progress = await ruleExtractionApi.getExtractionProgress(docId);
          if (progress.status !== "unknown") {
            extractionProgress = { completed: progress.completed, total: progress.total };
          }
        } catch {
          // Transient polling error — the main extraction request is the
          // source of truth; just skip this tick.
        }
      }, 1200);
    }

    try {
      // A selected document runs through the persisted draft-review
      // lifecycle (rule_extraction_drafts) instead of the ephemeral
      // extract-then-bulk-insert path, so results survive a closed tab and
      // get a reviewer audit trail. Picked sections scope the extraction to
      // that subset of the document; leaving none picked runs the whole
      // document through LlamaIndex's own clause-level chunking.
      if (selectedDocId) {
        const scopedText =
          selectedSectionKeys.size > 0
            ? docSections
                .filter((s) => s.id && selectedSectionKeys.has(s.id))
                .map((s) => s.text)
                .join("\n\n")
            : undefined;

        const res = await ruleExtractionApi.extractDrafts(selectedDocId, selectedModel, scopedText);
        draftRules = [...res.drafts, ...draftRules];
        draftTable.clearSelection();
        if (res.drafts.length === 0) {
          error = "No valid OpenBIM rules could be parsed from this document.";
        }
        return;
      }

      if (!rawText.trim()) {
        throw new Error("Please select a specification document or paste text to extract rules.");
      }

      const res = await ruleExtractionApi.extract(undefined, rawText, selectedModel);
      extractedRules = (res.rules || []).map((r: any) => ({
        ...r,
        rowId: nextDraftRowId++,
      }));
      // Every freshly extracted rule starts selected, as before.
      table.clearSelection();
      for (const r of extractedRules) table.selectedIds.add(r.rowId);
      extractionWarnings = res.warnings || [];

      if (extractedRules.length === 0) {
        error = "No valid OpenBIM rules could be parsed from the provided text.";
      }
    } catch (err: any) {
      error = err.message || "Rule extraction failed.";
    } finally {
      if (pollInterval) clearInterval(pollInterval);
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
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute(
      "download",
      `extracted_rules_draft_${new Date().toISOString().substring(0, 10)}.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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
      class="flex items-center gap-2 rounded-xl border border-emerald-800 bg-emerald-950/50 p-4 text-xs text-emerald-300"
    >
      <CheckCircle2 class="h-4 w-4 shrink-0" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <!-- Configuration & Input Section -->
  <div class="space-y-6 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <!-- Document Source Selector -->
      <div class="space-y-2">
        <label
          for="rule-doc-source"
          class="block text-xs font-bold uppercase tracking-wider text-slate-400"
        >
          Source Specification Document
        </label>
        <select
          id="rule-doc-source"
          bind:value={selectedDocId}
          class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
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
          class="block text-xs font-bold uppercase tracking-wider text-slate-400"
        >
          Extraction Model / Parser
        </label>
        <select
          id="rule-ai-model"
          bind:value={selectedModel}
          class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
        >
          {#each LLM_MODELS as model (model.id)}
            <option value={model.id}>{model.name}</option>
          {/each}
        </select>
      </div>
    </div>

    {#if selectedDocId && isLoadingSections}
      <p class="text-xs text-slate-400">Detecting sections…</p>
    {:else if selectedDocId && docSections.length > 0}
      <div
        role="group"
        aria-labelledby="rule-section-scope-label"
        class="space-y-2 rounded-xl border border-slate-800 bg-slate-950/60 p-4"
      >
        <div class="flex items-center justify-between gap-3">
          <span id="rule-section-scope-label" class="block text-xs font-bold uppercase tracking-wider text-slate-400">
            Optionally Scope Extraction to a Section / Paragraph
          </span>
          <div class="flex shrink-0 items-center gap-3 text-micro font-semibold text-accent">
            <button type="button" onclick={selectAllSections} class="hover:underline">
              Select all
            </button>
            <button type="button" onclick={clearSectionSelection} class="hover:underline">
              Clear
            </button>
          </div>
        </div>
        <p class="text-micro text-slate-500">
          {docSections.length} section{docSections.length === 1 ? "" : "s"} detected. Pick one or more
          to scope the extraction, or leave all unselected to process the whole document.
          {#if sectionsEnhanced}
            <span class="ml-1 inline-flex items-center gap-1 text-accent">
              <Sparkles class="h-3 w-3" /> AI-arranged
            </span>
          {/if}
        </p>
        <div class="max-h-64 overflow-y-auto pr-1">
          <SectionTree nodes={sectionTree} selected={selectedSectionKeys} />
        </div>
      </div>
    {:else if selectedDocId}
      <p class="text-xs text-slate-400">
        No sections were detected — extraction will run over the whole document.
      </p>
    {:else}
      <!-- Raw Text Input (no document selected — stays ephemeral until saved) -->
      <div class="space-y-2">
        <label
          for="rule-raw-text"
          class="block text-xs font-bold uppercase tracking-wider text-slate-400"
        >
          Or Paste Building Code / Specification Clauses Directly:
        </label>
        <textarea
          id="rule-raw-text"
          bind:value={rawText}
          rows="6"
          placeholder="e.g. Section 3.4.1: Exterior exit doors shall have a minimum clear width of 900 mm and fire protection rating of not less than 45 minutes..."
          class="w-full rounded-xl border border-slate-800 bg-slate-950 p-3.5 font-mono text-xs leading-relaxed text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
        ></textarea>
      </div>
    {/if}

    <div class="flex justify-end pt-2">
      <button
        type="button"
        disabled={isExtracting}
        onclick={handleExtract}
        class="inline-flex items-center gap-2 rounded-xl bg-accent px-6 py-2.5 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover disabled:opacity-50"
      >
        <Sparkles class="h-4 w-4" />
        <span>
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
        <h2 class="text-lg font-bold tracking-tight text-slate-50">
          Draft Review ({draftRules.length} draft{draftRules.length === 1 ? "" : "s"})
        </h2>
        <p class="text-xs text-slate-400">
          Accept or reject each candidate, then promote accepted drafts into the compliance rule
          library. Drafts persist across sessions.
        </p>
      </div>

      {#if isLoadingDrafts}
        <LoadingState message="Loading extraction drafts…" />
      {:else}
        <div
          class="flex flex-col items-center gap-3 rounded-2xl border border-slate-800/90 bg-slate-950/80 p-3.5 md:flex-row"
        >
          <div class="relative w-full flex-1">
            <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              bind:value={draftTable.search}
              placeholder="Search drafts by reference, description, property..."
              class="w-full rounded-xl border border-slate-800 bg-slate-900 py-2 pl-10 pr-4 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
            />
          </div>
          <select
            bind:value={draftTable.filters.status}
            class="rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
          >
            <option value="ALL">All Statuses</option>
            <option value="pending_review">Pending Review</option>
            <option value="accepted">Accepted</option>
            <option value="edited">Edited</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>

        <BulkActionBar
          selectedCount={draftTable.selectedCount}
          itemLabel="draft"
          onClearSelection={() => draftTable.clearSelection()}
        >
          {#snippet children()}
            <button
              type="button"
              onclick={acceptSelectedDrafts}
              class="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-600/30 px-3 py-1.5 font-semibold text-emerald-200 transition-all hover:bg-emerald-600/50"
            >
              <Check class="h-3.5 w-3.5" />
              <span>Accept</span>
            </button>
            <button
              type="button"
              onclick={promoteSelectedDrafts}
              class="inline-flex items-center gap-1.5 rounded-lg border border-blue-500/40 bg-blue-600/30 px-3 py-1.5 font-semibold text-blue-200 transition-all hover:bg-blue-600/50"
            >
              <Upload class="h-3.5 w-3.5 rotate-180" />
              <span>Promote to Library</span>
            </button>
          {/snippet}
        </BulkActionBar>

        <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40">
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-300">
              <thead
                class="border-b border-slate-800 bg-slate-950 text-caption font-semibold uppercase tracking-wider text-slate-400"
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
                  <th class="px-3 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60">
                {#each draftTable.paginated as draft (draft.id)}
                  <tr
                    class="transition-colors hover:bg-slate-900/60 {draftTable.isSelected(draft.id!)
                      ? 'bg-blue-950/20'
                      : ''}"
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
                          ? 'border-emerald-800 bg-emerald-950/50 text-emerald-300'
                          : draft.status === 'rejected'
                            ? 'border-rose-800 bg-rose-950/50 text-rose-300'
                            : 'border-amber-800 bg-amber-950/50 text-amber-300'}"
                      >
                        {draft.status.replace("_", " ")}
                      </span>
                    </td>
                    <td class="px-3 py-3 font-mono font-bold text-slate-50"
                      >{draft.proposed_rule.rule_id}</td
                    >
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
                    <td class="px-3 py-3 font-mono text-slate-400">
                      <div class="flex items-center gap-1.5">
                        <span
                          >{draft.proposed_rule.property_set || "—"} / {draft.proposed_rule
                            .property_name || "—"}</span
                        >
                        {#if draft.review_notes?.startsWith("bSDD grounding")}
                          <span
                            class="rounded-md border border-emerald-800 bg-emerald-950/50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-300"
                            title={draft.review_notes}
                          >
                            bSDD
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
                    <td class="whitespace-nowrap px-3 py-3 text-right">
                      <div class="flex items-center justify-end gap-1">
                        {#if draft.status === "pending_review"}
                          <button
                            type="button"
                            onclick={() => reviewDraft(draft, "accepted")}
                            class="rounded-lg bg-slate-800 p-1.5 text-emerald-400 transition-colors hover:bg-emerald-950/40"
                            title="Accept draft"
                          >
                            <Check class="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            onclick={() => reviewDraft(draft, "rejected")}
                            class="rounded-lg bg-slate-800 p-1.5 text-rose-400 transition-colors hover:bg-rose-950/40"
                            title="Reject draft"
                          >
                            <X class="h-3.5 w-3.5" />
                          </button>
                        {/if}
                        <button
                          type="button"
                          onclick={() => viewDraftSource(draft)}
                          class="rounded-lg bg-slate-800 p-1.5 text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
                          title="View source in document"
                        >
                          <Eye class="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onclick={() => openEditDraftModal(draft)}
                          class="rounded-lg bg-slate-800 p-1.5 text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
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
          <h2 class="text-lg font-bold tracking-tight text-slate-50">
            Extracted Rules Review ({extractedRules.length} rules identified)
          </h2>
          <p class="text-xs text-slate-400">
            Review, modify properties, filter, and select rules to persist to the library.
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <div class="flex flex-col">
            <label
              for="extraction-ruleset"
              class="mb-0.5 text-micro font-semibold uppercase tracking-wider text-slate-400"
              >Rule Folder</label
            >
            <input
              id="extraction-ruleset"
              type="text"
              bind:value={formRulesetId}
              class="w-44 rounded-xl border border-slate-800 bg-slate-950 px-3 py-1.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>

          <button
            type="button"
            onclick={addManualDraftRule}
            class="inline-flex items-center gap-1.5 rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 transition-all hover:bg-slate-700"
          >
            <Plus class="h-3.5 w-3.5" />
            <span>Add Rule</span>
          </button>

          <button
            type="button"
            disabled={isSaving || table.selectedCount === 0}
            onclick={handleSaveSelected}
            class="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-emerald-500/20 transition-all hover:bg-emerald-500 disabled:opacity-50"
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
        class="flex flex-col items-center gap-3 rounded-2xl border border-slate-800/90 bg-slate-950/80 p-3.5 md:flex-row"
      >
        <div class="relative w-full flex-1">
          <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            bind:value={table.search}
            placeholder="Search draft rules by reference, description, property..."
            class="w-full rounded-xl border border-slate-800 bg-slate-900 py-2 pl-10 pr-4 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
          />
        </div>

        <div class="flex w-full items-center gap-2 md:w-auto">
          <select
            bind:value={table.filters.severity}
            class="rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
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
      <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/40">
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-300">
            <thead
              class="border-b border-slate-800 bg-slate-950 text-caption font-semibold uppercase tracking-wider text-slate-400"
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
                <th class="px-3 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800/60">
              {#each table.paginated as rule (rule.rowId)}
                <tr
                  class="transition-colors hover:bg-slate-900/60 {table.isSelected(rule.rowId)
                    ? 'bg-blue-950/20'
                    : ''}"
                >
                  <td class="px-3 py-3 text-center">
                    <TableCheckbox
                      checked={table.isSelected(rule.rowId)}
                      onchange={() => table.toggleSelect(rule.rowId)}
                      ariaLabel={`Select rule ${rule.rule_id}`}
                    />
                  </td>
                  <td class="px-3 py-3 font-mono font-bold text-slate-50">
                    <input
                      type="text"
                      bind:value={rule.rule_id}
                      class="w-24 border-b border-transparent bg-transparent font-mono text-xs font-bold text-slate-50 hover:border-slate-700 focus:border-accent focus:outline-none"
                    />
                  </td>
                  <td class="px-3 py-3">
                    <input
                      type="text"
                      bind:value={rule.description}
                      class="w-full min-w-[200px] border-b border-transparent bg-transparent text-xs text-slate-300 hover:border-slate-700 focus:border-accent focus:outline-none"
                    />
                  </td>
                  <td class="px-3 py-3 font-mono text-slate-400">
                    <input
                      type="text"
                      bind:value={rule.property_set}
                      class="w-28 border-b border-transparent bg-transparent text-xs text-slate-400 hover:border-slate-700 focus:border-accent focus:outline-none"
                    />
                  </td>
                  <td class="px-3 py-3 font-mono text-slate-300">
                    <input
                      type="text"
                      bind:value={rule.property_name}
                      class="w-28 border-b border-transparent bg-transparent text-xs text-slate-300 hover:border-slate-700 focus:border-accent focus:outline-none"
                    />
                  </td>
                  <td class="px-3 py-3 font-mono text-slate-400">
                    {rule.operator || "=="}
                  </td>
                  <td class="px-3 py-3 font-mono text-cyan-300">
                    {rule.check_value ||
                      (rule.value_min ? `[${rule.value_min}..${rule.value_max}]` : "-")}
                  </td>
                  <td class="px-3 py-3">
                    <select
                      bind:value={rule.severity}
                      class="rounded border border-slate-800 bg-slate-950 px-2 py-0.5 text-micro font-semibold text-slate-50 focus:outline-none"
                    >
                      <option value="Critical">Critical</option>
                      <option value="High">High</option>
                      <option value="Medium">Medium</option>
                      <option value="Low">Low</option>
                    </select>
                  </td>
                  <td class="whitespace-nowrap px-3 py-3 text-right">
                    <div class="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        onclick={() => (viewingDraftRule = rule)}
                        class="rounded-lg bg-slate-800 p-1.5 text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
                        title="Inspect draft details"
                      >
                        <Eye class="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        onclick={() => removeDraftRule(rule.rowId)}
                        class="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-rose-950/30 hover:text-rose-400"
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
  <p class="text-slate-300">
    You can switch back to the Run Compliance Audit tab now — it will pick up this ruleset
    automatically.
  </p>
  {#snippet footer()}
    <button
      type="button"
      onclick={() => (showReturnPrompt = false)}
      class="rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-sm transition-all hover:bg-accent-hover"
    >
      Got it
    </button>
  {/snippet}
</Modal>

<!-- Draft Source Annotation Modal: jumps to and highlights the page/snippet a draft came from -->
{#if viewingDraftSource}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div>
          <h2 class="text-base font-bold tracking-tight text-slate-50">{viewingDraftSource.filename}</h2>
          {#if viewingDraftSource.page_number}
            <p class="mt-0.5 text-xs text-slate-400">Page {viewingDraftSource.page_number}</p>
          {/if}
        </div>
        <button
          type="button"
          onclick={() => (viewingDraftSource = null)}
          class="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>
      <div class="flex-1 overflow-hidden">
        <DocumentViewer
          documentId={viewingDraftSource.document_id}
          page={viewingDraftSource.page_number}
          highlightText={viewingDraftSource.snippet}
        />
      </div>
    </div>
  </div>
{/if}

{#if draftSourceError}
  <div
    class="fixed bottom-6 right-6 z-50 max-w-sm rounded-xl border border-red-800/60 bg-red-950/90 px-4 py-3 text-xs text-red-200 shadow-2xl"
  >
    <div class="flex items-start justify-between gap-3">
      <span>{draftSourceError}</span>
      <button
        type="button"
        onclick={() => (draftSourceError = "")}
        class="shrink-0 text-red-300 hover:text-red-100"
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
      class="w-full max-w-lg space-y-4 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <Pencil class="h-4 w-4 text-accent" />
          <h3 class="font-mono text-sm font-bold text-slate-50">Edit Draft</h3>
        </div>
        <button
          type="button"
          onclick={closeEditDraftModal}
          class="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <div class="space-y-3 text-xs">
        <div class="space-y-1">
          <label for="edit-draft-description" class="block font-semibold text-slate-300"
            >Description</label
          >
          <textarea
            id="edit-draft-description"
            bind:value={editForm.description}
            rows="2"
            class="w-full rounded-xl border border-slate-800 bg-slate-950 p-3 text-slate-50 focus:border-accent focus:outline-none"
          ></textarea>
        </div>

        <div class="grid grid-cols-2 gap-2">
          <div class="space-y-1">
            <label for="edit-draft-target" class="block font-semibold text-slate-300"
              >Target IFC Class</label
            >
            <input
              id="edit-draft-target"
              type="text"
              bind:value={editForm.target_ifc_class}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 font-mono text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>
          <div class="space-y-1">
            <label for="edit-draft-pset" class="block font-semibold text-slate-300"
              >Property Set</label
            >
            <input
              id="edit-draft-pset"
              type="text"
              bind:value={editForm.property_set}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 font-mono text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>
          <div class="space-y-1">
            <label for="edit-draft-prop" class="block font-semibold text-slate-300">Property</label>
            <input
              id="edit-draft-prop"
              type="text"
              bind:value={editForm.property_name}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 font-mono text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>
          <div class="space-y-1">
            <label for="edit-draft-operator" class="block font-semibold text-slate-300"
              >Operator</label
            >
            <select
              id="edit-draft-operator"
              bind:value={editForm.operator}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-slate-50 focus:outline-none"
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
            <label for="edit-draft-value" class="block font-semibold text-slate-300"
              >Check Value</label
            >
            <input
              id="edit-draft-value"
              type="text"
              bind:value={editForm.check_value}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 font-mono text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>
          <div class="space-y-1">
            <label for="edit-draft-severity" class="block font-semibold text-slate-300"
              >Severity</label
            >
            <select
              id="edit-draft-severity"
              bind:value={editForm.severity}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-slate-50 focus:outline-none"
            >
              <option value="mandatory">Mandatory</option>
              <option value="recommended">Recommended</option>
            </select>
          </div>
        </div>
      </div>

      <div class="flex justify-end gap-2 border-t border-slate-800 pt-2">
        <button
          type="button"
          onclick={closeEditDraftModal}
          class="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-50"
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
      class="w-full max-w-lg space-y-4 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <FileText class="h-4 w-4 text-accent" />
          <h3 class="font-mono text-sm font-bold text-slate-50">
            {viewingDraftRule.rule_id || "Draft Rule"}
          </h3>
        </div>
        <button
          type="button"
          onclick={() => (viewingDraftRule = null)}
          class="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <div class="space-y-3 text-xs">
        <div>
          <span class="mb-1 block font-semibold text-slate-400">Description</span>
          <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-slate-200">
            {viewingDraftRule.description || "No description"}
          </div>
        </div>

        <div
          class="grid grid-cols-2 gap-2 rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono text-caption"
        >
          <div>
            <span class="text-slate-500">Pset:</span>
            <span class="text-slate-300">{viewingDraftRule.property_set || "—"}</span>
          </div>
          <div>
            <span class="text-slate-500">Property:</span>
            <BsddBadge
              kind="property"
              value={viewingDraftRule.property_name}
              propertySet={viewingDraftRule.property_set}
              class="text-slate-300"
            />
          </div>
          <div>
            <span class="text-slate-500">Operator:</span>
            <span class="text-cyan-300">{viewingDraftRule.operator || "=="}</span>
          </div>
          <div>
            <span class="text-slate-500">Target Value:</span>
            <span class="text-emerald-300">{viewingDraftRule.check_value || "—"}</span>
          </div>
          <div>
            <span class="text-slate-500">Severity:</span>
            <span class="font-semibold text-amber-400">{viewingDraftRule.severity}</span>
          </div>
        </div>
      </div>

      <div class="flex justify-end pt-2">
        <button
          type="button"
          onclick={() => (viewingDraftRule = null)}
          class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
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
      class="w-full max-w-md space-y-4 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <SlidersHorizontal class="h-4 w-4 text-blue-400" />
          <h3 class="text-sm font-bold text-slate-50">
            Bulk Edit Draft Rules ({table.selectedCount} selected)
          </h3>
        </div>
        <button
          type="button"
          onclick={() => (isDraftBulkEditModalOpen = false)}
          class="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <div class="space-y-3 text-xs">
        <div class="space-y-1">
          <label for="bulk-draft-severity" class="block font-semibold text-slate-300"
            >Severity</label
          >
          <select
            id="bulk-draft-severity"
            bind:value={bulkDraftSeverity}
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-slate-50 focus:border-accent focus:outline-none"
          >
            <option value="no_change">-- Keep Current Severity --</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>

        <div class="space-y-1">
          <label for="bulk-draft-pset" class="block font-semibold text-slate-300"
            >Property Set</label
          >
          <input
            id="bulk-draft-pset"
            type="text"
            bind:value={bulkDraftPset}
            placeholder="Leave empty to keep current"
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-slate-50 placeholder-slate-600 focus:border-accent focus:outline-none"
          />
        </div>

        <div class="space-y-1">
          <label for="bulk-draft-op" class="block font-semibold text-slate-300">Operator</label>
          <select
            id="bulk-draft-op"
            bind:value={bulkDraftOperator}
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-slate-50 focus:border-accent focus:outline-none"
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

      <div class="flex justify-end gap-2 border-t border-slate-800 pt-2">
        <button
          type="button"
          onclick={() => (isDraftBulkEditModalOpen = false)}
          class="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-50"
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
  onConfirm={confirmBulkDeleteDrafts}
  onCancel={() => (isDraftBulkDeleteModalOpen = false)}
/>
