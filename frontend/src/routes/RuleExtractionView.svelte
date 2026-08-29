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
  } from "lucide-svelte";
  import { documentsApi, ruleExtractionApi } from "../lib/api";
  import type { DocumentItem, ExtractedRule } from "../lib/types";

  let documents: DocumentItem[] = [];
  let selectedDocId: number | null = null;
  let rawText = "";
  let selectedModel = "gemini-2.5-flash";
  let isExtracting = false;
  let isSaving = false;
  let error = "";
  let successMessage = "";

  let extractedRules: ExtractedRule[] = [];
  let extractionWarnings: string[] = [];

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
  <div>
    <div
      class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1"
    >
      Studio
    </div>
    <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">
      Rule Extraction Studio
    </h1>
    <p class="text-xs sm:text-sm text-slate-400">
      Transform building codes, engineering standards, and specification
      documents into structured OpenBIM verification rules.
    </p>
  </div>

  {#if error}
    <div
      class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs flex items-center gap-2"
    >
      <AlertCircle class="w-4 h-4 text-rose-400 shrink-0" />
      <span>{error}</span>
    </div>
  {/if}

  {#if successMessage}
    <div
      class="p-4 rounded-xl bg-emerald-950/50 border border-emerald-800 text-emerald-300 text-xs flex items-center gap-2"
    >
      <CheckCircle2 class="w-4 h-4 text-emerald-400 shrink-0" />
      <span>{successMessage}</span>
    </div>
  {/if}

  <!-- Configuration Box -->
  <div
    class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-5"
  >
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <!-- Source Document Selection -->
      <div>
        <label
          for="extract-doc"
          class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5"
        >
          Select Source Specification Document
        </label>
        <select
          id="extract-doc"
          bind:value={selectedDocId}
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        >
          <option value={null}>-- Paste custom text below instead --</option>
          {#each documents as doc}
            <option value={doc.id}
              >{doc.filename} ({doc.char_count.toLocaleString()} chars)</option
            >
          {/each}
        </select>
      </div>

      <!-- LLM Engine Selection -->
      <div>
        <label
          for="extract-model"
          class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5"
        >
          AI Rule Extraction Engine
        </label>
        <select
          id="extract-model"
          bind:value={selectedModel}
          class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
        >
          {#each LLM_MODELS as model}
            <option value={model.id}>{model.name}</option>
          {/each}
        </select>
      </div>
    </div>

    {#if !selectedDocId}
      <div>
        <label
          for="extract-text"
          class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5"
        >
          Specification Clause / Code Text
        </label>
        <textarea
          id="extract-text"
          bind:value={rawText}
          rows="5"
          placeholder="Paste clauses from Ontario Building Code Part 9, NFPA 13, ASME B31, etc..."
          class="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-white font-mono placeholder-slate-600 focus:outline-none focus:border-[#0071e3]"
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
        <span
          >{isExtracting
            ? "Extracting Rules via AI..."
            : "Extract Compliance Rules"}</span
        >
      </button>
    </div>
  </div>

  <!-- Extraction Results Review -->
  {#if extractedRules.length > 0}
    <div class="space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-lg font-bold text-white tracking-tight">
            Extracted Rules Review ({extractedRules.length} rules identified)
          </h2>
          <p class="text-xs text-slate-400">
            Review, modify properties, and select rules to persist to the
            library.
          </p>
        </div>

        <button
          type="button"
          disabled={isSaving}
          on:click={handleSaveSelected}
          class="inline-flex items-center gap-2 px-5 py-2 rounded-full text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm shadow-emerald-500/20 transition-all disabled:opacity-50"
        >
          <Save class="w-3.5 h-3.5" />
          <span>{isSaving ? "Saving..." : "Save Selected to Library"}</span>
        </button>
      </div>

      <div
        class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-900/40"
      >
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-300">
            <thead
              class="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold"
            >
              <tr>
                <th class="py-3 px-3 w-10 text-center">
                  <input
                    type="checkbox"
                    checked={extractedRules.every((r) => r.selected)}
                    on:change={(e) => {
                      const chk = (e.target as HTMLInputElement).checked;
                      extractedRules = extractedRules.map((r) => ({
                        ...r,
                        selected: chk,
                      }));
                    }}
                    class="rounded border-slate-700 bg-slate-950 text-[#0071e3]"
                  />
                </th>
                <th class="py-3 px-3">Rule Ref</th>
                <th class="py-3 px-3">Description</th>
                <th class="py-3 px-3">Property Set</th>
                <th class="py-3 px-3">Property</th>
                <th class="py-3 px-3">Op</th>
                <th class="py-3 px-3">Target Value</th>
                <th class="py-3 px-3">Severity</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800/60">
              {#each extractedRules as rule, i}
                <tr class="hover:bg-slate-900/60 transition-colors">
                  <td class="py-3 px-3 text-center">
                    <input
                      type="checkbox"
                      bind:checked={rule.selected}
                      class="rounded border-slate-700 bg-slate-950 text-[#0071e3]"
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
                  <td class="py-3 px-3 text-slate-400 font-mono"
                    >{rule.operator || "=="}</td
                  >
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
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  {/if}
</div>
