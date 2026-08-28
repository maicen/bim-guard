<script lang="ts">
  import type { AuditIssue, IssueStats } from '../types';

  export let issues: AuditIssue[] = [];
  export let stats: IssueStats | null = null;

  let searchQuery = '';
  let selectedBand: string = 'all';
  let selectedMechanism: string = 'all';

  $: mechanisms = Array.from(new Set(issues.map((i) => i.mechanism))).filter(Boolean);

  $: filteredIssues = issues.filter((issue) => {
    const matchesSearch =
      !searchQuery ||
      issue.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      issue.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      issue.element_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      issue.rule_id.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesBand = selectedBand === 'all' || issue.band === selectedBand;
    const matchesMech = selectedMechanism === 'all' || issue.mechanism === selectedMechanism;

    return matchesSearch && matchesBand && matchesMech;
  });

  function getBandPill(band: string) {
    switch (band.toLowerCase()) {
      case 'critical':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
      case 'high':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'medium':
        return 'bg-yellow-500/10 text-yellow-300 border-yellow-500/20';
      case 'low':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  }
</script>

<div class="space-y-6">
  <!-- Stats Cards -->
  {#if stats}
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
      <div class="p-4 rounded-xl border border-rose-900/40 bg-rose-950/20 backdrop-blur">
        <div class="text-xs uppercase tracking-wider font-semibold text-rose-400">Critical Risk</div>
        <div class="text-2xl font-bold text-white mt-1">{stats.critical}</div>
      </div>
      <div class="p-4 rounded-xl border border-amber-900/40 bg-amber-950/20 backdrop-blur">
        <div class="text-xs uppercase tracking-wider font-semibold text-amber-400">High Risk</div>
        <div class="text-2xl font-bold text-white mt-1">{stats.high}</div>
      </div>
      <div class="p-4 rounded-xl border border-yellow-900/40 bg-yellow-950/20 backdrop-blur">
        <div class="text-xs uppercase tracking-wider font-semibold text-yellow-300">Medium Risk</div>
        <div class="text-2xl font-bold text-white mt-1">{stats.medium}</div>
      </div>
      <div class="p-4 rounded-xl border border-emerald-900/40 bg-emerald-950/20 backdrop-blur">
        <div class="text-xs uppercase tracking-wider font-semibold text-emerald-400">Low / Tolerable</div>
        <div class="text-2xl font-bold text-white mt-1">{stats.low}</div>
      </div>
    </div>
  {/if}

  <!-- Filter Toolbar -->
  <div class="flex flex-col sm:flex-row gap-3 items-center justify-between">
    <div class="w-full sm:w-72">
      <input
        type="text"
        placeholder="Search issues, elements, rules..."
        bind:value={searchQuery}
        class="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
      />
    </div>
    <div class="flex gap-2 w-full sm:w-auto">
      <select
        bind:value={selectedBand}
        class="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
      >
        <option value="all">All Severities</option>
        <option value="critical">Critical</option>
        <option value="high">High</option>
        <option value="medium">Medium</option>
        <option value="low">Low</option>
      </select>

      {#if mechanisms.length > 0}
        <select
          bind:value={selectedMechanism}
          class="px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
        >
          <option value="all">All Mechanisms</option>
          {#each mechanisms as mech}
            <option value={mech}>{mech}</option>
          {/each}
        </select>
      {/if}
    </div>
  </div>

  <!-- Issues List -->
  <div class="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-xl">
    <div class="overflow-x-auto">
      <table class="w-full text-left text-sm">
        <thead class="bg-slate-950/70 border-b border-slate-800 text-xs uppercase text-slate-400 font-semibold">
          <tr>
            <th class="py-3 px-4">Finding ID</th>
            <th class="py-3 px-4">Severity</th>
            <th class="py-3 px-4">Mechanism</th>
            <th class="py-3 px-4">Element GUID</th>
            <th class="py-3 px-4">Issue Description</th>
            <th class="py-3 px-4">Remediation Action</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-800/60">
          {#if filteredIssues.length === 0}
            <tr>
              <td colspan="6" class="py-8 text-center text-slate-400">
                No compliance issues match the selected criteria.
              </td>
            </tr>
          {:else}
            {#each filteredIssues as issue}
              <tr class="hover:bg-slate-800/30 transition-colors">
                <td class="py-3 px-4 font-mono font-medium text-emerald-400 whitespace-nowrap">
                  {issue.id}
                </td>
                <td class="py-3 px-4 whitespace-nowrap">
                  <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider border {getBandPill(issue.band)}">
                    {issue.band}
                  </span>
                </td>
                <td class="py-3 px-4 text-slate-300 font-medium whitespace-nowrap">
                  {issue.mechanism}
                </td>
                <td class="py-3 px-4 font-mono text-xs text-slate-400 truncate max-w-[140px]" title={issue.element_id}>
                  {issue.element_id}
                </td>
                <td class="py-3 px-4 text-slate-200">
                  <div class="font-medium text-white">{issue.title}</div>
                  {#if issue.description && issue.description !== issue.title}
                    <div class="text-xs text-slate-400 mt-0.5 line-clamp-2">{issue.description}</div>
                  {/if}
                </td>
                <td class="py-3 px-4 text-xs text-slate-300 max-w-[260px]">
                  {issue.mitigation || 'Review element properties against standard.'}
                </td>
              </tr>
            {/each}
          {/if}
        </tbody>
      </table>
    </div>
  </div>
</div>

