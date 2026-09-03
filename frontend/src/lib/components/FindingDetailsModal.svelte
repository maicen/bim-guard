<script lang="ts">
  import { AlertTriangle, CheckCircle2, Copy, Check, ScanEye } from 'lucide-svelte';
  import type { AuditIssue } from '../types';
  import Modal from './Modal.svelte';
  import SeverityBadge from './SeverityBadge.svelte';

  export let isOpen: boolean = false;
  export let issue: AuditIssue | null = null;
  export let onClose: () => void;
  export let onSelectViewer: ((elementGuid: string) => void) | undefined = undefined;

  let copiedGuid = false;

  async function copyGuid(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      copiedGuid = true;
      setTimeout(() => (copiedGuid = false), 2000);
    } catch {}
  }
</script>

{#if issue}
  <Modal
    {isOpen}
    title={issue.title}
    subtitle={`Finding ID: ${issue.id}`}
    icon={AlertTriangle}
    maxWidth="max-w-2xl"
    {onClose}
  >
    <div slot="header-extra">
      <SeverityBadge severity={issue.band || 'low'} />
    </div>

    <!-- Key Metrics Cards -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs bg-slate-950 p-3.5 rounded-xl border border-slate-800">
      <div>
        <span class="text-micro font-semibold text-slate-500 uppercase block">Mechanism / Domain</span>
        <span class="text-slate-200 font-medium">{issue.mechanism || 'CODE'}</span>
      </div>
      <div>
        <span class="text-micro font-semibold text-slate-500 uppercase block">Rule Reference</span>
        <span class="text-cyan-300 font-mono font-medium">{issue.rule_id || '—'}</span>
      </div>
      <div>
        <span class="text-micro font-semibold text-slate-500 uppercase block">Risk Score / Verdict</span>
        <span class="text-amber-400 font-medium">{issue.score !== undefined ? issue.score : 'FAIL'}</span>
      </div>
      <div>
        <span class="text-micro font-semibold text-slate-500 uppercase block">Element Type</span>
        <span class="text-slate-300">{issue.details?.element_type || 'IfcProduct'}</span>
      </div>
    </div>

    <!-- Description -->
    {#if issue.description}
      <div class="space-y-1">
        <span class="text-xs font-semibold text-slate-300 block">Finding Description</span>
        <div class="p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">
          {issue.description}
        </div>
      </div>
    {/if}

    <!-- Remediation Recommendation -->
    {#if issue.mitigation}
      <div class="space-y-1">
        <span class="text-xs font-semibold text-emerald-400 block flex items-center gap-1.5">
          <CheckCircle2 class="w-3.5 h-3.5" />
          <span>Recommended Remediation</span>
        </span>
        <div class="p-3 bg-emerald-950/20 rounded-xl border border-emerald-900/40 text-xs text-emerald-200 leading-relaxed">
          {issue.mitigation}
        </div>
      </div>
    {/if}

    <!-- Element GUID -->
    <div class="space-y-1.5">
      <span class="text-xs font-semibold text-slate-300 block">Target Element GUID</span>
      <div class="flex items-center justify-between p-3 bg-slate-950 rounded-xl border border-slate-800">
        <span class="font-mono text-xs text-cyan-300 select-all">{issue.element_id}</span>
        <div class="flex items-center gap-2">
          <button
            type="button"
            on:click={() => copyGuid(issue.element_id)}
            class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 hover:text-slate-50 transition-colors"
          >
            {#if copiedGuid}
              <Check class="w-3.5 h-3.5 text-emerald-400" />
              <span class="text-emerald-400">Copied</span>
            {:else}
              <Copy class="w-3.5 h-3.5" />
              <span>Copy</span>
            {/if}
          </button>
          {#if onSelectViewer}
            <button
              type="button"
              on:click={() => onSelectViewer && onSelectViewer(issue.element_id)}
              class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 text-xs font-semibold transition-colors"
            >
              <ScanEye class="w-3.5 h-3.5" />
              <span>Highlight in 3D</span>
            </button>
          {/if}
        </div>
      </div>
    </div>

    <!-- Citation / Code Reference Details -->
    {#if issue.citations && issue.citations.length > 0}
      <div class="space-y-1">
        <span class="text-xs font-semibold text-slate-300 block">Standard Citations &amp; Clauses</span>
        <div class="flex flex-wrap gap-1.5">
          {#each issue.citations as cit}
            <span class="px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 font-mono text-caption text-purple-300">
              {typeof cit === 'string' ? cit : `${cit.standard} ${cit.clause}`}
            </span>
          {/each}
        </div>
      </div>
    {/if}

    <div slot="footer">
      <button
        type="button"
        on:click={onClose}
        class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-50 transition-colors"
      >
        Close
      </button>
    </div>
  </Modal>
{/if}
