<script lang="ts">
  import { rulesApi } from "../api";
  import type { IdsImportResult } from "../types";

  export let defaultRulesetId = "";
  export let onCancel: () => void;
  export let onImported: (result: IdsImportResult) => void;

  let importIdsFile: File | null = null;
  let importIdsRulesetId = defaultRulesetId;
  let isImportingIds = false;
  let importIdsError = "";

  async function handleImportIds() {
    if (!importIdsFile || !importIdsRulesetId.trim()) {
      importIdsError = "Please choose an IDS file and a Rule Folder name.";
      return;
    }
    isImportingIds = true;
    importIdsError = "";
    try {
      const res = await rulesApi.importIds(importIdsFile, importIdsRulesetId.trim());
      onImported(res);
    } catch (err: any) {
      importIdsError = err.message || "Failed to import IDS file.";
    } finally {
      isImportingIds = false;
    }
  }
</script>

<div class="space-y-4">
  {#if importIdsError}
    <div class="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
      {importIdsError}
    </div>
  {/if}

  <div class="space-y-1.5">
    <label for="import-ids-file" class="block text-xs font-semibold text-slate-300">
      IDS File <span class="text-rose-400">*</span>
    </label>
    <input
      id="import-ids-file"
      type="file"
      accept=".ids,.xml"
      on:change={(e) => (importIdsFile = (e.target as HTMLInputElement).files?.[0] || null)}
      class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white file:mr-3 file:py-1 file:px-3 file:rounded-lg file:border-0 file:bg-slate-800 file:text-white file:text-xs focus:outline-none focus:border-[#0071e3]"
    />
  </div>

  <div class="space-y-1.5">
    <label for="import-ids-ruleset" class="block text-xs font-semibold text-slate-300">
      Rule Folder <span class="text-rose-400">*</span>
    </label>
    <input
      id="import-ids-ruleset"
      type="text"
      bind:value={importIdsRulesetId}
      placeholder="e.g. IMPORTED-IDS or an existing folder name"
      class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3] font-mono"
    />
    <p class="text-[11px] text-slate-500">
      Imported rules are saved under this folder and flagged for review (needs_review).
    </p>
  </div>

  <div class="flex justify-end gap-2 pt-2 border-t border-slate-800">
    <button
      type="button"
      on:click={onCancel}
      class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white"
    >
      Cancel
    </button>
    <button
      type="button"
      disabled={isImportingIds || !importIdsFile || !importIdsRulesetId.trim()}
      on:click={handleImportIds}
      class="inline-flex items-center gap-1.5 px-5 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all disabled:opacity-50"
    >
      <span>{isImportingIds ? "Importing..." : "Import Rules"}</span>
    </button>
  </div>
</div>
