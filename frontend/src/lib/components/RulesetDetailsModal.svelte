<script lang="ts">
  import Modal from "./Modal.svelte";
  import { ShieldCheck, BookOpen, Layers, CheckCircle2, FileCode2 } from "lucide-svelte";
  import type { RuleFolder } from "../types";

  interface Props {
    open: boolean;
    ruleset: RuleFolder | null;
    isGranted?: boolean;
    onClose: () => void;
  }

  let { open = false, ruleset = null, isGranted = false, onClose }: Props = $props();
</script>

<Modal isOpen={open} {onClose} title={ruleset?.display_name || "Ruleset Details"} icon={ShieldCheck} maxWidth="max-w-2xl">
  {#if ruleset}
    <div class="space-y-5 text-xs text-slate-300">
      <!-- Overview Banner -->
      <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div class="font-mono text-micro text-violet-400 font-semibold">{ruleset.ruleset_id}</div>
            <div class="mt-0.5 text-sm font-bold text-slate-100">{ruleset.display_name}</div>
          </div>
          <div>
            {#if isGranted}
              <span
                class="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-300"
              >
                <CheckCircle2 class="h-3.5 w-3.5 text-emerald-400" />
                <span>Granted to Organization</span>
              </span>
            {:else}
              <span
                class="inline-flex items-center gap-1.5 rounded-md border border-slate-700 bg-slate-800/80 px-2.5 py-1 text-xs font-medium text-slate-400"
              >
                <span>Catalog Ruleset</span>
              </span>
            {/if}
          </div>
        </div>

        {#if ruleset.description}
          <div class="mt-3 text-xs leading-relaxed text-slate-400 border-t border-slate-800/80 pt-2.5">
            {ruleset.description}
          </div>
        {/if}
      </div>

      <!-- Metadata Grid -->
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div class="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
          <div class="flex items-center gap-1.5 text-micro text-slate-400 font-medium">
            <Layers class="h-3.5 w-3.5 text-violet-400" />
            <span>Category</span>
          </div>
          <div class="mt-1 font-semibold text-slate-100 truncate">
            {ruleset.category || "General"}
          </div>
        </div>

        <div class="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
          <div class="flex items-center gap-1.5 text-micro text-slate-400 font-medium">
            <BookOpen class="h-3.5 w-3.5 text-blue-400" />
            <span>Mechanism</span>
          </div>
          <div class="mt-1 font-semibold text-slate-100 truncate">
            {ruleset.mechanism_scope || "Standard Verification"}
          </div>
        </div>

        <div class="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
          <div class="flex items-center gap-1.5 text-micro text-slate-400 font-medium">
            <FileCode2 class="h-3.5 w-3.5 text-emerald-400" />
            <span>Rule Clauses</span>
          </div>
          <div class="mt-1 font-semibold text-slate-100">
            {ruleset.rules?.length || ruleset.count || 0} active rule(s)
          </div>
        </div>
      </div>

      <!-- Rules List Preview -->
      <div>
        <div class="mb-2 text-micro font-bold uppercase tracking-wider text-slate-400">
          Rules Included in this Ruleset ({ruleset.rules?.length || 0})
        </div>
        {#if ruleset.rules && ruleset.rules.length > 0}
          <div class="max-h-60 overflow-y-auto space-y-2 rounded-xl border border-slate-800 bg-slate-950 p-2 divide-y divide-slate-800/40">
            {#each ruleset.rules as rule (rule.id)}
              <div class="pt-2 first:pt-0">
                <div class="flex items-center justify-between gap-2">
                  <span class="font-mono text-micro text-violet-300 font-semibold">{rule.rule_id || `#${rule.id}`}</span>
                  {#if rule.severity}
                    <span class="rounded bg-slate-800 px-1.5 py-0.5 text-micro uppercase text-slate-300">
                      {rule.severity}
                    </span>
                  {/if}
                </div>
                <div class="text-xs font-medium text-slate-200 mt-0.5">{rule.description || rule.source_text || "Specification clause"}</div>
                {#if rule.target_ifc_class}
                  <div class="mt-1 flex flex-wrap gap-1">
                    <span class="rounded bg-slate-900 px-1.5 py-0.5 text-micro text-slate-400 border border-slate-800">
                      {rule.target_ifc_class}
                    </span>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {:else}
          <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-center text-xs text-slate-500">
            Rules are dynamically evaluated and loaded from the rule catalog database.
          </div>
        {/if}
      </div>
    </div>
  {/if}

  {#snippet footer()}
    <button
      type="button"
      onclick={onClose}
      class="rounded-xl border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 transition-colors hover:bg-slate-700"
    >
      Close
    </button>
  {/snippet}
</Modal>
