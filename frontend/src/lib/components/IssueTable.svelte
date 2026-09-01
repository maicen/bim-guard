<script lang="ts">
  import { Eye, ArrowUpDown, ArrowUp, ArrowDown, Download, Copy, Check, CheckSquare, Sparkles } from 'lucide-svelte';
  import type { AuditIssue, IssueStats } from '../types';
  import TablePagination from './TablePagination.svelte';
  import BulkActionBar from './BulkActionBar.svelte';
  import FindingDetailsModal from './FindingDetailsModal.svelte';
  import SortHeader from './SortHeader.svelte';
  import TableCheckbox from './TableCheckbox.svelte';
  import SeverityBadge from './SeverityBadge.svelte';

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
      <div class="p-4 rounded-xl border border-rose-900/40 bg-rose-950/20 backdrop-blur">
        <div class="text-xs uppercase tracking-wider font-semibold text-rose-400">Critical</div>
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
        <div class="text-xs uppercase tracking-wider font-semibold text-emerald-400">Low Risk</div>
        <div class="text-2xl font-bold text-white mt-1">{stats.low}</div>
      </div>
      <div class="p-4 rounded-xl border border-indigo-900/40 bg-indigo-950/20 backdrop-blur">
        <div class="text-xs uppercase tracking-wider font-semibold text-indigo-300">Data Quality</div>
        <div class="text-2xl font-bold text-white mt-1">{stats.data_quality || 0}</div>
      </div>
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
