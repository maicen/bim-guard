<script lang="ts">
  import { Eye, ScanEye, ArrowUpDown, ArrowUp, ArrowDown, Download, Copy, Check, CheckSquare, Sparkles, Fingerprint, FlaskConical } from 'lucide-svelte';
  import type { AuditIssue, IssueStats } from '../types';
  import TablePagination from './TablePagination.svelte';
  import BulkActionBar from './BulkActionBar.svelte';
  import FindingDetailsModal from './FindingDetailsModal.svelte';
  import SortHeader from './SortHeader.svelte';
  import TableCheckbox from './TableCheckbox.svelte';
  import SeverityBadge from './SeverityBadge.svelte';
  import HoverCard from './HoverCard.svelte';
  import { describeMechanism, describeSeverity } from '../glossary';

  export let issues: AuditIssue[] = [];
  export let stats: IssueStats | null = null;
  export let onSelectViewer?: ((elementGuid: string) => void) | undefined = undefined;

  let searchQuery = '';
  let selectedBand: string = 'all';
  let selectedMechanism: string = 'all';

  // Multi-selection state
  let selectedIssueIds: string[] = [];

  // Sorting state
  let sortField: 'id' | 'band' | 'mechanism' | 'element_id' | 'title' = 'id';
  let sortAsc = true;

  // Pagination state
  let currentPage = 1;
  let pageSize = 10;

  // Details Modal state
  let selectedIssueForDetails: AuditIssue | null = null;
  let isDetailsModalOpen = false;

  $: mechanisms = Array.from(new Set(issues.map((i) => i.mechanism))).filter(Boolean);

  $: filteredIssues = issues
    .filter((issue) => {
      const matchesSearch =
        !searchQuery ||
        (issue.title || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (issue.id || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (issue.element_id || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (issue.rule_id || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (issue.description || '').toLowerCase().includes(searchQuery.toLowerCase());

      const matchesBand = selectedBand === 'all' || (issue.band || '').toLowerCase() === selectedBand.toLowerCase();
      const matchesMech = selectedMechanism === 'all' || issue.mechanism === selectedMechanism;

      return matchesSearch && matchesBand && matchesMech;
    })
    .sort((a, b) => {
      let valA: any = a[sortField];
      let valB: any = b[sortField];
      if (valA === undefined || valA === null) valA = '';
      if (valB === undefined || valB === null) valB = '';
      if (typeof valA === 'string') valA = valA.toLowerCase();
      if (typeof valB === 'string') valB = valB.toLowerCase();
      if (valA < valB) return sortAsc ? -1 : 1;
      if (valA > valB) return sortAsc ? 1 : -1;
      return 0;
    });

  $: totalItems = filteredIssues.length;
  $: paginatedIssues = filteredIssues.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  $: allFilteredSelected =
    filteredIssues.length > 0 &&
    filteredIssues.every((i) => selectedIssueIds.includes(i.id));

  function toggleSelectAll() {
    if (allFilteredSelected) {
      selectedIssueIds = [];
    } else {
      selectedIssueIds = filteredIssues.map((i) => i.id);
    }
  }

  function toggleSelectIssue(id: string) {
    if (selectedIssueIds.includes(id)) {
      selectedIssueIds = selectedIssueIds.filter((iId) => iId !== id);
    } else {
      selectedIssueIds = [...selectedIssueIds, id];
    }
  }

  function toggleSort(field: 'id' | 'band' | 'mechanism' | 'element_id' | 'title') {
    if (sortField === field) {
      sortAsc = !sortAsc;
    } else {
      sortField = field;
      sortAsc = true;
    }
  }

  function exportSelectedToCsv() {
    const toExport = issues.filter((i) => selectedIssueIds.includes(i.id));
    const target = toExport.length ? toExport : filteredIssues;
    const headers = ['FindingID', 'Severity', 'Mechanism', 'RuleID', 'ElementGUID', 'Title', 'Description', 'Mitigation'];
    const rows = target.map((i) => [
      `"${(i.id || '').replace(/"/g, '""')}"`,
      `"${(i.band || '').replace(/"/g, '""')}"`,
      `"${(i.mechanism || '').replace(/"/g, '""')}"`,
      `"${(i.rule_id || '').replace(/"/g, '""')}"`,
      `"${(i.element_id || '').replace(/"/g, '""')}"`,
      `"${(i.title || '').replace(/"/g, '""')}"`,
      `"${(i.description || '').replace(/"/g, '""')}"`,
      `"${(i.mitigation || '').replace(/"/g, '""')}"`,
    ]);
    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `audit_findings_${new Date().toISOString().substring(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  function openDetails(issue: AuditIssue) {
    selectedIssueForDetails = issue;
    isDetailsModalOpen = true;
  }

  // Copy feedback for the element GUID hover card.
  let copiedGuid: string | null = null;
  let copiedTimer: ReturnType<typeof setTimeout> | null = null;

  async function copyGuid(guid: string) {
    try {
      await navigator.clipboard.writeText(guid);
      copiedGuid = guid;
      if (copiedTimer) clearTimeout(copiedTimer);
      copiedTimer = setTimeout(() => (copiedGuid = null), 1600);
    } catch {
      // Clipboard is unavailable (insecure origin, denied permission). The
      // full GUID is already selectable in the card, so there is nothing to
      // recover from and nothing worth interrupting the reviewer about.
    }
  }

  // The five stat tiles are the one place a severity band appears without a
  // row of context, so the definition of each band hangs off them rather than
  // off every badge in the table.
  $: bandCards = stats
    ? [
        { key: 'critical', label: 'Critical', value: stats.critical, tone: 'border-rose-900/40 bg-rose-950/20', text: 'text-rose-400' },
        { key: 'high', label: 'High Risk', value: stats.high, tone: 'border-amber-900/40 bg-amber-950/20', text: 'text-amber-400' },
        { key: 'medium', label: 'Medium Risk', value: stats.medium, tone: 'border-yellow-900/40 bg-yellow-950/20', text: 'text-yellow-300' },
        { key: 'low', label: 'Low Risk', value: stats.low, tone: 'border-emerald-900/40 bg-emerald-950/20', text: 'text-emerald-400' },
        { key: 'data_quality', label: 'Data Quality', value: stats.data_quality || 0, tone: 'border-indigo-900/40 bg-indigo-950/20', text: 'text-indigo-300' },
      ]
    : [];

  function getBandPill(band?: string) {
    switch ((band || '').toLowerCase()) {
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
    <div class="grid grid-cols-2 sm:grid-cols-5 gap-3">
      {#each bandCards as card}
        {@const info = describeSeverity(card.key)}
        <HoverCard
          side="bottom"
          align="start"
          width="w-72"
          triggerClass="block"
          title={info?.label || card.label}
          subtitle="Severity band"
        >
          <span
            slot="trigger"
            class="block w-full p-4 rounded-xl border backdrop-blur cursor-help {card.tone}"
          >
            <span class="block text-xs uppercase tracking-wider font-semibold {card.text}">{card.label}</span>
            <span class="block text-2xl font-bold text-slate-100 mt-1">{card.value}</span>
          </span>

          {info?.description || 'No definition available for this band.'}
        </HoverCard>
      {/each}
    </div>
  {/if}

  <!-- Filter Toolbar -->
  <div class="flex flex-col sm:flex-row gap-3 items-center justify-between">
    <div class="w-full sm:w-80">
      <input
        type="text"
        placeholder="Search issues, elements, rules, descriptions..."
        bind:value={searchQuery}
        class="w-full px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
      />
    </div>
    <div class="flex gap-2 w-full sm:w-auto">
      <select
        bind:value={selectedBand}
        class="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-[#0071e3]"
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
          class="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-[#0071e3]"
        >
          <option value="all">All Mechanisms</option>
          {#each mechanisms as mech}
            <option value={mech}>{mech}</option>
          {/each}
        </select>
      {/if}
    </div>
  </div>

  <!-- Bulk Action Bar -->
  <BulkActionBar
    selectedCount={selectedIssueIds.length}
    itemLabel="compliance finding"
    onClearSelection={() => (selectedIssueIds = [])}
    onBulkExport={exportSelectedToCsv}
    onBulkDelete={null}
    onBulkEdit={null}
  />

  <!-- Issues List -->
  <div class="rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-xl">
    <div class="overflow-x-auto">
      <table class="w-full text-left text-xs">
        <thead class="bg-slate-950 border-b border-slate-800 text-[11px] uppercase text-slate-400 font-semibold">
          <tr>
            <th class="py-3 px-4 w-10">
              <TableCheckbox
                checked={allFilteredSelected}
                on:change={toggleSelectAll}
                title="Select all findings"
              />
            </th>
            <SortHeader column="id" {sortField} {sortAsc} onSort={toggleSort}>
              Finding ID
            </SortHeader>
            <SortHeader column="band" {sortField} {sortAsc} onSort={toggleSort}>
              Severity
            </SortHeader>
            <SortHeader column="mechanism" {sortField} {sortAsc} onSort={toggleSort}>
              Mechanism
            </SortHeader>
            <SortHeader column="element_id" {sortField} {sortAsc} onSort={toggleSort}>
              Element GUID
            </SortHeader>
            <SortHeader column="title" {sortField} {sortAsc} onSort={toggleSort}>
              Issue Description
            </SortHeader>
            <th class="py-3 px-4 text-right">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-800/60">
          {#if filteredIssues.length === 0}
            <tr>
              <td colspan="7" class="py-12 text-center text-slate-400">
                No compliance issues match the selected criteria.
              </td>
            </tr>
          {:else}
            {#each paginatedIssues as issue}
              {@const mech = describeMechanism(issue.mechanism)}
              <tr class="hover:bg-slate-800/30 transition-colors {selectedIssueIds.includes(issue.id) ? 'bg-blue-950/20' : ''}">
                <td class="py-3 px-4 w-10">
                  <TableCheckbox
                    checked={selectedIssueIds.includes(issue.id)}
                    on:change={() => toggleSelectIssue(issue.id)}
                    ariaLabel={`Select finding ${issue.id}`}
                  />
                </td>
                <td class="py-3 px-4 font-mono font-medium text-emerald-400 whitespace-nowrap">
                  {issue.id}
                </td>
                <td class="py-3 px-4 whitespace-nowrap">
                  <SeverityBadge severity={issue.band || 'low'} />
                </td>
                <td class="py-3 px-4 text-slate-300 font-medium whitespace-nowrap">
                  {#if mech}
                    <HoverCard
                      side="top"
                      align="start"
                      width="w-80"
                      icon={FlaskConical}
                      title="{issue.mechanism} — {mech.label}"
                      subtitle="Compliance mechanism"
                      showFooter={!!mech.reference}
                    >
                      <span slot="trigger" class="cursor-help border-b border-dotted border-slate-600">
                        {issue.mechanism}
                      </span>

                      {mech.description}

                      <span slot="footer" class="font-mono">{mech.reference}</span>
                    </HoverCard>
                  {:else}
                    {issue.mechanism}
                  {/if}
                </td>
                <td class="py-3 px-4 font-mono text-xs text-slate-400 max-w-[140px]">
                  <!-- The GUID is truncated to keep the row scannable, which
                       makes it useless for the one thing it is for: pasting
                       into the authoring tool. The card restores the full
                       value plus a copy action. -->
                  <HoverCard
                    side="top"
                    align="start"
                    width="w-80"
                    icon={Fingerprint}
                    title="IFC element GUID"
                    subtitle={issue.rule_id ? `Flagged by ${issue.rule_id}` : ''}
                    triggerClass="max-w-full"
                  >
                    <span slot="trigger" class="truncate cursor-help">{issue.element_id}</span>

                    <div class="space-y-2">
                      <code class="block break-all rounded-lg bg-slate-950/70 border border-slate-800 px-2 py-1.5 text-[10px] text-emerald-300 select-all">
                        {issue.element_id || '—'}
                      </code>
                      <div class="flex items-center gap-1.5">
                        <button
                          type="button"
                          on:click={() => copyGuid(issue.element_id)}
                          class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[10px] font-medium transition-colors"
                        >
                          {#if copiedGuid === issue.element_id}
                            <Check class="w-3 h-3 text-emerald-400" /> Copied
                          {:else}
                            <Copy class="w-3 h-3" /> Copy GUID
                          {/if}
                        </button>
                        {#if onSelectViewer}
                          <button
                            type="button"
                            on:click={() => onSelectViewer && onSelectViewer(issue.element_id)}
                            class="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 text-blue-300 text-[10px] font-medium transition-colors"
                          >
                            <ScanEye class="w-3 h-3" /> Show in 3D
                          </button>
                        {/if}
                      </div>
                    </div>
                  </HoverCard>
                </td>
                <td class="py-3 px-4 text-slate-200">
                  <div class="font-medium text-white">{issue.title}</div>
                  {#if issue.description && issue.description !== issue.title}
                    <div class="text-xs text-slate-400 mt-0.5 line-clamp-2">{issue.description}</div>
                  {/if}
                </td>
                <td class="py-3 px-4 text-right whitespace-nowrap">
                  <div class="flex items-center justify-end gap-1.5">
                    <button
                      type="button"
                      on:click={() => openDetails(issue)}
                      class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                      title="Inspect finding details & citations"
                    >
                      <Eye class="w-3.5 h-3.5" />
                    </button>
                    {#if onSelectViewer}
                      <button
                        type="button"
                        on:click={() => onSelectViewer && onSelectViewer(issue.element_id)}
                        class="p-1.5 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 border border-blue-500/30 transition-colors"
                        title="Highlight element in 3D Viewer"
                      >
                        <ScanEye class="w-3.5 h-3.5" />
                      </button>
                    {/if}
                  </div>
                </td>
              </tr>
            {/each}
          {/if}
        </tbody>
      </table>
    </div>

    <TablePagination
      {currentPage}
      {pageSize}
      {totalItems}
      onPageChange={(p) => (currentPage = p)}
      onPageSizeChange={(s) => {
        pageSize = s;
        currentPage = 1;
      }}
    />
  </div>
</div>

<!-- Finding Details Modal -->
<FindingDetailsModal
  isOpen={isDetailsModalOpen}
  issue={selectedIssueForDetails}
  onClose={() => {
    isDetailsModalOpen = false;
    selectedIssueForDetails = null;
  }}
  onSelectViewer={(guid) => {
    isDetailsModalOpen = false;
    if (onSelectViewer) onSelectViewer(guid);
  }}
/>
