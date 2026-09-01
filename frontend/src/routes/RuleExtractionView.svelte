<script lang="ts">
  import { onMount } from "svelte";
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
    X,
    Search,
    SlidersHorizontal,
    ArrowUpDown,
    ArrowUp,
    ArrowDown,
    Download,
  } from "lucide-svelte";
  import { documentsApi, ruleExtractionApi } from "../lib/api";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";

  let documents: DocumentItem[] = [];
  let selectedDocId: number | null = null;
  let rawText = "";
  let selectedModel = "gemini-2.5-flash";
  let viewingDraftRule: ExtractedRule | null = null;

  function addManualDraftRule() {
    const newRule: ExtractedRule = {
      rule_id: `CUSTOM-${extractedRules.length + 1}`,
      description: "Custom compliance requirement",
      property_set: "Pset_Compliance",
      property_name: "",
      operator: "==",
      check_value: "",
      severity: "Medium",
      selected: true,
    };
    extractedRules = [newRule, ...extractedRules];
  }

  function removeDraftRule(index: number) {
    extractedRules = extractedRules.filter((_, i) => i !== index);
  }
  let isExtracting = false;
  let isSaving = false;
  let error = "";
  let successMessage = "";

  let extractedRules: ExtractedRule[] = [];
  let extractionWarnings: string[] = [];

  // Search, Filter, Sort & Pagination for Draft Rules
  let draftSearchQuery = "";
  let draftSeverityFilter = "ALL";
  let draftSortField: "rule_id" | "description" | "property_set" | "property_name" | "operator" | "severity" = "rule_id";
  let draftSortAsc = true;
  let draftCurrentPage = 1;
  let draftPageSize = 10;

  // Bulk Edit Modal for Draft Rules
  let isDraftBulkEditModalOpen = false;
  let bulkDraftSeverity = "no_change";
  let bulkDraftPset = "";
  let bulkDraftOperator = "no_change";
  let isDraftBulkDeleteModalOpen = false;

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
    error = "";
    successMessage = "";
    extractedRules = [];
    extractionWarnings = [];
    draftCurrentPage = 1;

    try {
      let textToExtract = rawText;
      if (selectedDocId) {
        const doc = await documentsApi.get(selectedDocId);
        textToExtract = doc.extracted_text;
      }

      if (!textToExtract.trim()) {
        throw new Error(
          "Please select a specification document or paste text to extract rules.",
        );
      }

      const res = await ruleExtractionApi.extract(undefined, textToExtract);
      extractedRules = (res.rules || []).map((r: any) => ({
        ...r,
        selected: true,
      }));
      extractionWarnings = res.warnings || [];

      if (extractedRules.length === 0) {
        error =
          "No valid OpenBIM rules could be parsed from the provided text.";
      }
    } catch (err: any) {
      error = err.message || "Rule extraction failed.";
    } finally {
      isExtracting = false;
    }
  }

  $: selectedDraftCount = extractedRules.filter((r) => r.selected).length;

  $: filteredDraftRules = extractedRules
    .filter((r) => {
      const matchesSearch =
        !draftSearchQuery ||
        (r.rule_id || "").toLowerCase().includes(draftSearchQuery.toLowerCase()) ||
        (r.description || "").toLowerCase().includes(draftSearchQuery.toLowerCase()) ||
        (r.property_name || "").toLowerCase().includes(draftSearchQuery.toLowerCase()) ||
        (r.property_set || "").toLowerCase().includes(draftSearchQuery.toLowerCase());
      const matchesSeverity =
        draftSeverityFilter === "ALL" ||
        (r.severity || "Medium").toLowerCase() === draftSeverityFilter.toLowerCase();
      return matchesSearch && matchesSeverity;
    })
    .sort((a, b) => {
      let valA: any = a[draftSortField];
      let valB: any = b[draftSortField];
      if (valA === undefined || valA === null) valA = "";
      if (valB === undefined || valB === null) valB = "";
      if (typeof valA === "string") valA = valA.toLowerCase();
      if (typeof valB === "string") valB = valB.toLowerCase();
      if (valA < valB) return draftSortAsc ? -1 : 1;
      if (valA > valB) return draftSortAsc ? 1 : -1;
      return 0;
    });

  $: draftTotalItems = filteredDraftRules.length;
  $: paginatedDraftRules = filteredDraftRules.slice(
    (draftCurrentPage - 1) * draftPageSize,
    draftCurrentPage * draftPageSize,
  );

  $: allFilteredDraftsSelected =
    filteredDraftRules.length > 0 &&
    filteredDraftRules.every((r) => r.selected);

  function toggleSelectAllDrafts() {
    const targetState = !allFilteredDraftsSelected;
    filteredDraftRules.forEach((r) => {
      r.selected = targetState;
    });
    extractedRules = [...extractedRules];
  }

  function toggleDraftSort(field: "rule_id" | "description" | "property_set" | "property_name" | "operator" | "severity") {
    if (draftSortField === field) {
      draftSortAsc = !draftSortAsc;
    } else {
      draftSortField = field;
      draftSortAsc = true;
    }
  }

  function applyDraftBulkEdit() {
    extractedRules = extractedRules.map((r) => {
      if (!r.selected) return r;
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
    extractedRules = extractedRules.filter((r) => !r.selected);
    isDraftBulkDeleteModalOpen = false;
  }

  function exportDraftRulesToCsv() {
    const toExport = extractedRules.filter((r) => r.selected);
    const target = toExport.length ? toExport : filteredDraftRules;
    const headers = ["RuleID", "Description", "PropertySet", "PropertyName", "Operator", "CheckValue", "Severity"];
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
    link.setAttribute("download", `extracted_rules_draft_${new Date().toISOString().substring(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  async function handleSaveSelected() {
    const toSave = extractedRules.filter((r) => r.selected);
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
        ruleset_id: "EXTRACTED-STANDARDS",
        rule_category: "property_check",
        confidence: r.confidence || "0.9",
        extraction_method: "ai_extracted",
        needs_review: 1,
      }));

      const res = await ruleExtractionApi.bulkCreate(payloads);
      successMessage = `Successfully saved ${res.created_count} rules into the compliance library.`;
      extractedRules = [];
    } catch (err: any) {
      error = err.message || "Failed to save rules to library.";
    } finally {
      isSaving = false;
    }
  }
</script>

<div class="space-y-6 mx-auto">
  <!-- Header -->
  <PageHeader
    category="AI Engineering Tools"
    title="Rule Extraction Engine"
    subtitle="Transform natural language building codes, standards, and specifications into machine-executable OpenBIM compliance rules."
    icon={Sparkles}
  />

  {#if error}
    <div
      class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs flex items-center gap-2"
    >
      <AlertCircle class="w-4 h-4 shrink-0" />
      <span>{error}</span>
    </div>
  {/if}

  {#if successMessage}
    <div
      class="p-4 rounded-xl bg-emerald-950/50 border border-emerald-800 text-emerald-300 text-xs flex items-center gap-2"
    >
      <CheckCircle2 class="w-4 h-4 shrink-0" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <!-- Configuration & Input Section -->
  <div
    class="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-6"
  >
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
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
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        >
          <option value={null}>-- Select from Document Library --</option>
          {#each documents as doc}
            <option value={doc.id}
              >{doc.filename} ({doc.doc_type || "Spec"})</option
            >
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
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        >
          {#each LLM_MODELS as model}
            <option value={model.id}>{model.name}</option>
          {/each}
        </select>
      </div>
    </div>

    <!-- Raw Text Input (Fallback / Custom Snippet) -->
    {#if !selectedDocId}
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
          class="w-full bg-slate-950 border border-slate-800 rounded-xl p-3.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3] font-mono leading-relaxed"
        ></textarea>
      </div>
    {/if}

    <div class="flex justify-end pt-2">
      <button
        type="button"
        disabled={isExtracting}
        on:click={handleExtract}
        class="inline-flex items-center gap-2 px-6 py-2.5 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] disabled:opacity-50"
      >
        <Sparkles class="w-4 h-4" />
        <span>{isExtracting ? "Extracting Rules via AI..." : "Extract Compliance Rules"}</span>
      </button>
    </div>
  </div>

  <!-- Extraction Results Review -->
  {#if extractedRules.length > 0}
    <div class="space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 class="text-lg font-bold text-white tracking-tight">
            Extracted Rules Review ({extractedRules.length} rules identified)
          </h2>
          <p class="text-xs text-slate-400">
            Review, modify properties, filter, and select rules to persist to the library.
          </p>
        </div>

        <div class="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            on:click={addManualDraftRule}
            class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-all"
          >
            <Plus class="w-3.5 h-3.5" />
            <span>Add Rule</span>
          </button>

          <button
            type="button"
            disabled={isSaving || selectedDraftCount === 0}
            on:click={handleSaveSelected}
            class="inline-flex items-center gap-2 px-5 py-2 rounded-xl text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm shadow-emerald-500/20 transition-all disabled:opacity-50"
          >
            <Save class="w-3.5 h-3.5" />
            <span>{isSaving ? "Saving..." : `Save Selected (${selectedDraftCount}) to Library`}</span>
          </button>
        </div>
      </div>

      <!-- Filter Toolbar -->
      <div class="p-3.5 rounded-2xl bg-slate-950/80 border border-slate-800/90 flex flex-col md:flex-row items-center gap-3">
        <div class="relative flex-1 w-full">
          <Search class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            bind:value={draftSearchQuery}
            placeholder="Search draft rules by reference, description, property..."
            class="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
          />
        </div>

        <div class="flex items-center gap-2 w-full md:w-auto">
          <select
            bind:value={draftSeverityFilter}
            class="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
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
        selectedCount={selectedDraftCount}
        itemLabel="draft rule"
        onClearSelection={() => {
          extractedRules = extractedRules.map((r) => ({ ...r, selected: false }));
        }}
        onBulkEdit={() => (isDraftBulkEditModalOpen = true)}
        onBulkExport={exportDraftRulesToCsv}
        onBulkDelete={() => (isDraftBulkDeleteModalOpen = true)}
      />

      <!-- Table Container -->
      <div class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-900/40">
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-300">
            <thead
              class="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold"
            >
              <tr>
                <th class="py-3 px-3 w-10 text-center">
                  <TableCheckbox
                    checked={allFilteredDraftsSelected}
                    on:change={toggleSelectAllDrafts}
                    title="Select all draft rules"
                  />
                </th>
                <SortHeader column="rule_id" sortField={draftSortField} sortAsc={draftSortAsc} onSort={toggleDraftSort} customClass="py-3 px-3">
                  Rule Ref
                </SortHeader>
                <SortHeader column="description" sortField={draftSortField} sortAsc={draftSortAsc} onSort={toggleDraftSort} customClass="py-3 px-3">
                  Description
                </SortHeader>
                <SortHeader column="property_set" sortField={draftSortField} sortAsc={draftSortAsc} onSort={toggleDraftSort} customClass="py-3 px-3">
                  Property Set
                </SortHeader>
                <SortHeader column="property_name" sortField={draftSortField} sortAsc={draftSortAsc} onSort={toggleDraftSort} customClass="py-3 px-3">
                  Property
                </SortHeader>
                <SortHeader column="operator" sortField={draftSortField} sortAsc={draftSortAsc} onSort={toggleDraftSort} customClass="py-3 px-3">
                  Op
                </SortHeader>
                <th class="py-3 px-3">Target Value</th>
                <SortHeader column="severity" sortField={draftSortField} sortAsc={draftSortAsc} onSort={toggleDraftSort} customClass="py-3 px-3">
                  Severity
                </SortHeader>
                <th class="py-3 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800/60">
              {#each paginatedDraftRules as rule, i}
                <tr class="hover:bg-slate-900/60 transition-colors {rule.selected ? 'bg-blue-950/20' : ''}">
                  <td class="py-3 px-3 text-center">
                    <TableCheckbox
                      bind:checked={rule.selected}
                      ariaLabel={`Select rule ${rule.rule_id}`}
                    />
                  </td>
                  <td class="py-3 px-3 font-mono font-bold text-white">
                    <input
                      type="text"
                      bind:value={rule.rule_id}
                      class="bg-transparent border-b border-transparent hover:border-slate-700 focus:border-[#0071e3] text-xs font-mono font-bold text-white focus:outline-none w-24"
                    />
                  </td>
                  <td class="py-3 px-3">
                    <input
                      type="text"
                      bind:value={rule.description}
                      class="bg-transparent border-b border-transparent hover:border-slate-700 focus:border-[#0071e3] text-xs text-slate-300 focus:outline-none w-full min-w-[200px]"
                    />
                  </td>
                  <td class="py-3 px-3 text-slate-400 font-mono">
                    <input
                      type="text"
                      bind:value={rule.property_set}
                      class="bg-transparent border-b border-transparent hover:border-slate-700 focus:border-[#0071e3] text-xs text-slate-400 focus:outline-none w-28"
                    />
                  </td>
                  <td class="py-3 px-3 text-slate-300 font-mono">
                    <input
                      type="text"
                      bind:value={rule.property_name}
                      class="bg-transparent border-b border-transparent hover:border-slate-700 focus:border-[#0071e3] text-xs text-slate-300 focus:outline-none w-28"
                    />
                  </td>
                  <td class="py-3 px-3 text-slate-400 font-mono">
                    {rule.operator || "=="}
                  </td>
                  <td class="py-3 px-3 font-mono text-cyan-300">
                    {rule.check_value ||
                      (rule.value_min
                        ? `[${rule.value_min}..${rule.value_max}]`
                        : "-")}
                  </td>
                  <td class="py-3 px-3">
                    <select
                      bind:value={rule.severity}
                      class="bg-slate-950 border border-slate-800 rounded px-2 py-0.5 text-[10px] font-semibold text-white focus:outline-none"
                    >
                      <option value="Critical">Critical</option>
                      <option value="High">High</option>
                      <option value="Medium">Medium</option>
                      <option value="Low">Low</option>
                    </select>
                  </td>
                  <td class="py-3 px-3 text-right whitespace-nowrap">
                    <div class="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        on:click={() => (viewingDraftRule = rule)}
                        class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                        title="Inspect draft details"
                      >
                        <Eye class="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        on:click={() => removeDraftRule(i)}
                        class="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
                        title="Remove draft rule"
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

        <TablePagination
          currentPage={draftCurrentPage}
          pageSize={draftPageSize}
          totalItems={draftTotalItems}
          onPageChange={(p) => (draftCurrentPage = p)}
          onPageSizeChange={(s) => {
            draftPageSize = s;
            draftCurrentPage = 1;
          }}
        />
      </div>
    </div>
  {/if}
</div>

<!-- Inspect Draft Rule Modal -->
{#if viewingDraftRule}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden p-6 space-y-4">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <FileText class="w-4 h-4 text-[#0071e3]" />
          <h3 class="text-sm font-bold text-white font-mono">{viewingDraftRule.rule_id || 'Draft Rule'}</h3>
        </div>
        <button
          type="button"
          on:click={() => (viewingDraftRule = null)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <div class="space-y-3 text-xs">
        <div>
          <span class="text-slate-400 font-semibold block mb-1">Description</span>
          <div class="p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-slate-200">
            {viewingDraftRule.description || 'No description'}
          </div>
        </div>

        <div class="grid grid-cols-2 gap-2 text-[11px] font-mono bg-slate-950 p-3 rounded-xl border border-slate-800">
          <div><span class="text-slate-500">Pset:</span> <span class="text-slate-300">{viewingDraftRule.property_set || '—'}</span></div>
          <div><span class="text-slate-500">Property:</span> <span class="text-slate-300">{viewingDraftRule.property_name || '—'}</span></div>
          <div><span class="text-slate-500">Operator:</span> <span class="text-cyan-300">{viewingDraftRule.operator || '=='}</span></div>
          <div><span class="text-slate-500">Target Value:</span> <span class="text-emerald-300">{viewingDraftRule.check_value || '—'}</span></div>
          <div><span class="text-slate-500">Severity:</span> <span class="text-amber-400 font-semibold">{viewingDraftRule.severity}</span></div>
        </div>
      </div>

      <div class="flex justify-end pt-2">
        <button
          type="button"
          on:click={() => (viewingDraftRule = null)}
          class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Bulk Edit Modal for Draft Rules -->
{#if isDraftBulkEditModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-md rounded-2xl shadow-2xl overflow-hidden p-6 space-y-4">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <SlidersHorizontal class="w-4 h-4 text-blue-400" />
          <h3 class="text-sm font-bold text-white">Bulk Edit Draft Rules ({selectedDraftCount} selected)</h3>
        </div>
        <button
          type="button"
          on:click={() => (isDraftBulkEditModalOpen = false)}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <div class="space-y-3 text-xs">
        <div class="space-y-1">
          <label for="bulk-draft-severity" class="block font-semibold text-slate-300">Severity</label>
          <select
            id="bulk-draft-severity"
            bind:value={bulkDraftSeverity}
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-[#0071e3]"
          >
            <option value="no_change">-- Keep Current Severity --</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>

        <div class="space-y-1">
          <label for="bulk-draft-pset" class="block font-semibold text-slate-300">Property Set</label>
          <input
            id="bulk-draft-pset"
            type="text"
            bind:value={bulkDraftPset}
            placeholder="Leave empty to keep current"
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white placeholder-slate-600 focus:outline-none focus:border-[#0071e3]"
          />
        </div>

        <div class="space-y-1">
          <label for="bulk-draft-op" class="block font-semibold text-slate-300">Operator</label>
          <select
            id="bulk-draft-op"
            bind:value={bulkDraftOperator}
            class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-[#0071e3]"
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

      <div class="flex justify-end gap-2 pt-2 border-t border-slate-800">
        <button
          type="button"
          on:click={() => (isDraftBulkEditModalOpen = false)}
          class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white"
        >
          Cancel
        </button>
        <button
          type="button"
          on:click={applyDraftBulkEdit}
          class="px-5 py-2 rounded-xl text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white"
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
  message={`Are you sure you want to remove ${selectedDraftCount} selected draft rule(s) from this extraction batch?`}
  confirmText="Delete Draft Rules"
  danger={true}
  onConfirm={confirmBulkDeleteDrafts}
  onCancel={() => (isDraftBulkDeleteModalOpen = false)}
/>
