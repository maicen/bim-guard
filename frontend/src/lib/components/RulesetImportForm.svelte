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

  let importFile: File | null = $state(null);
  let importRulesetId = $state(untrack(() => defaultRulesetId));
  let isImporting = $state(false);
  let importError = $state("");

  let detectedFormat = $derived(
    importFile?.name.toLowerCase().endsWith(".json") ? "json" : "ids",
  );

  function handleFileChange(e: Event) {
    importFile = (e.target as HTMLInputElement).files?.[0] || null;
    importError = "";
  }

  async function handleImport() {
    if (!importFile || !importRulesetId.trim()) {
      importError = "Please choose a file and a Rule Folder name.";
      return;
    }
    isImporting = true;
    importError = "";
    try {
      const res =
        detectedFormat === "json"
          ? await rulesApi.importJson(importFile, importRulesetId.trim())
          : await rulesApi.importIds(importFile, importRulesetId.trim());
      onImported(res);
    } catch (err: any) {
      importError = err.message || "Failed to import ruleset file.";
    } finally {
      isImporting = false;
    }
  }
</script>

<div class="space-y-4">
  {#if importError}
    <div class="rounded-xl border border-critical-border bg-critical-bg p-3 text-xs text-critical">
      {importError}
    </div>
  {/if}

  <div class="space-y-1.5">
    <label for="import-ruleset-file" class="block text-xs font-semibold text-fg-secondary">
      Ruleset File <span class="text-critical">*</span>
    </label>
    <input
      id="import-ruleset-file"
      type="file"
      accept=".ids,.xml,.json"
      onchange={handleFileChange}
      class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 text-xs text-fg-primary file:mr-3 file:rounded-lg file:border-0 file:bg-surface-card file:px-3 file:py-1 file:text-xs file:text-fg-primary focus:border-accent focus:ring-accent focus:outline-hidden"
    />
    <p class="text-caption text-fg-muted">
      Accepts a buildingSMART IDS (.ids/.xml) file or a BIM-Guard JSON ruleset (.json).
      {#if importFile}
        <span class="font-semibold text-fg-secondary">
          Detected format: {detectedFormat === "json" ? "JSON" : "IDS XML"}
        </span>
      {/if}
    </p>
  </div>

  <div class="space-y-1.5">
    <label for="import-ruleset-folder" class="block text-xs font-semibold text-fg-secondary">
      Rule Folder <span class="text-critical">*</span>
    </label>
    <input
      id="import-ruleset-folder"
      type="text"
      bind:value={importRulesetId}
      placeholder="e.g. IMPORTED-RULES or an existing folder name"
      class="w-full rounded-xl border border-border-default bg-surface-canvas px-3.5 py-2.5 font-mono text-xs text-fg-primary placeholder:text-fg-muted focus:border-accent focus:ring-accent focus:outline-hidden"
    />
    <p class="text-caption text-fg-muted">
      Imported rules are saved under this folder and flagged for review (needs_review).
    </p>
  </div>

  <div class="flex justify-end gap-2 border-t border-border-subtle pt-2">
    <button
      type="button"
      onclick={onCancel}
      class="rounded-xl px-4 py-2 text-xs font-semibold text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary"
    >
      Cancel
    </button>
    <button
      type="button"
      disabled={isImporting || !importFile || !importRulesetId.trim()}
      onclick={handleImport}
      class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-xs transition-all hover:bg-accent-hover disabled:opacity-50"
    >
      <span>{isImporting ? "Importing..." : "Import Rules"}</span>
    </button>
  </div>
</div>
