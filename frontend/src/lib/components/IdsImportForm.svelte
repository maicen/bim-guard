<script lang="ts">
  import { untrack } from "svelte";
  import { rulesApi } from "../api";
  import type { IdsImportResult } from "../types";

  interface Props {
    defaultRulesetId?: string;
    onCancel: () => void;
    onImported: (result: IdsImportResult) => void;
  }

  let { defaultRulesetId = "", onCancel, onImported }: Props = $props();

  let importIdsFile: File | null = $state(null);
  let importIdsRulesetId = $state(untrack(() => defaultRulesetId));
  let isImportingIds = $state(false);
  let importIdsError = $state("");

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
    <div class="rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300">
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
      onchange={(e) => (importIdsFile = (e.target as HTMLInputElement).files?.[0] || null)}
      class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 file:mr-3 file:rounded-lg file:border-0 file:bg-slate-800 file:px-3 file:py-1 file:text-xs file:text-slate-50 focus:border-accent focus:outline-none"
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
      class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 font-mono text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
    />
    <p class="text-caption text-slate-500">
      Imported rules are saved under this folder and flagged for review (needs_review).
    </p>
  </div>

  <div class="flex justify-end gap-2 border-t border-slate-800 pt-2">
    <button
      type="button"
      onclick={onCancel}
      class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 hover:bg-slate-700"
    >
      Cancel
    </button>
    <button
      type="button"
      disabled={isImportingIds || !importIdsFile || !importIdsRulesetId.trim()}
      onclick={handleImportIds}
      class="inline-flex items-center gap-1.5 rounded-full bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:opacity-50"
    >
      <span>{isImportingIds ? "Importing..." : "Import Rules"}</span>
    </button>
  </div>
</div>
