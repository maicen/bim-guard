<script lang="ts">
  import {
    Copy,
    Check,
    Send,
    Layers,
    Code,
    CheckCircle2,
    XCircle,
    AlertTriangle,
    Boxes,
    Terminal,
    ArrowRight,
    Shield,
    Search,
    ArrowUpDown,
    ArrowUp,
    ArrowDown,
    Eye,
    X,
    FileText,
  } from "lucide-svelte";
  import { revitSyncApi } from "../lib/api";
  import type { RevitSyncRequest, RevitSyncResponse, RevitRuleResult } from "../lib/types";
  import Badge from "../lib/components/Badge.svelte";
  import BentoBox from "../lib/components/BentoBox.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import BsddBadge from "../lib/components/BsddBadge.svelte";
  import { createTableState } from "../lib/tableState.svelte";

  let copied = $state(false);
  let isSendingTest = $state(false);
  let testResponse: RevitSyncResponse | null = $state(null);
  let testError: string | null = $state(null);

  // The sync response carries no unique key — rule_ref repeats across targets
  // and properties — so rows get a stable index-based id when they arrive.
  type IndexedRuleResult = RevitRuleResult & { rowId: number };
  let indexedResults: IndexedRuleResult[] = [];

  // Search, filter, sort, paginate and select — all owned by the shared state.
  const table = $state(
    createTableState<IndexedRuleResult, number>({
      rows: () => indexedResults,
      getId: (r) => r.rowId,
      searchFields: (r) => [r.rule_ref, r.rule_desc, r.target, r.property_name],
      filters: {
        status: (r, value) => (r.status || "").toUpperCase() === value.toUpperCase(),
      },
      initialSort: { field: "fail_count", asc: false },
    }),
  );

  let viewingRule: IndexedRuleResult | null = $state(null);

  const endpointUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/api/analyze/revit-sync`
      : "http://localhost:8000/api/analyze/revit-sync";

  const pyRevitScript = `"""
BIM Guard — Direct pyRevit Push Script
Save this as script.py inside your pyRevit extension:
e.g. BIMGuard.extension/BIMGuard.tab/Audit.panel/DirectSync.pushbutton/script.py
"""
import json
import urllib2  # IronPython compatible

from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory

doc = __revit__.ActiveUIDocument.Document

# Collect Stairs as an example
stairs = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Stairs).WhereElementIsNotElementType().ToElements()

elements = []
for stair in stairs:
    elements.append({
        "ifc_class": "IfcStairFlight",
        "name": stair.Name,
        "guid": str(stair.UniqueId),
        "storey": doc.GetElement(stair.LevelId).Name if stair.LevelId else "Level 1",
        "properties": {
            "Width": 1050.0,
            "RiserHeight": 175.0,
            "TreadLength": 280.0
        }
    })

payload = {
    "project_name": doc.Title or "Revit Active Model",
    "theme": "Architecture",
    "elements": elements
}

url = "${endpointUrl}"
req = urllib2.Request(url, data=json.dumps(payload), headers={'Content-Type': 'application/json'})
response = urllib2.urlopen(req)
print("BIM Guard Status: " + str(response.getcode()))
print(response.read())
`;

  const samplePayload: RevitSyncRequest = {
    project_name: "Sample Revit Medical Facility",
    theme: "Architecture",
    elements: [
      {
        ifc_class: "IfcStairFlight",
        name: "Stair Flight Main 01",
        guid: "c82b0e91-7299-4674-8b63-125da954a701",
        storey: "Level 1",
        properties: {
          Width: 1200.0,
          RiserHeight: 175.0,
          TreadLength: 280.0,
        },
      },
      {
        ifc_class: "IfcStairFlight",
        name: "Stair Flight Exit West",
        guid: "d41a0f82-8301-4985-9c74-236eb965b802",
        storey: "Level 2",
        properties: {
          Width: 850.0, // Failing: < 900mm
          RiserHeight: 210.0, // Failing: > 200mm
          TreadLength: 220.0,
        },
      },
      {
        ifc_class: "IfcDoor",
        name: "Single Flush Egress Door 102",
        guid: "e52b1a93-9412-4a96-ad85-347fc976c903",
        storey: "Level 1",
        properties: {
          ClearWidth: 920.0,
          FireRating: "45 min",
        },
      },
    ],
  };

  async function copyScript() {
    try {
      await navigator.clipboard.writeText(pyRevitScript);
      copied = true;
      setTimeout(() => (copied = false), 2500);
    } catch {
      // fallback
    }
  }

  async function runSimulation() {
    isSendingTest = true;
    testError = null;
    testResponse = null;
    indexedResults = [];
    table.clearSelection();
    table.requestedPage = 1;

    try {
      testResponse = await revitSyncApi.sync(samplePayload);
      indexedResults = (testResponse.results || []).map((r, i) => ({ ...r, rowId: i }));
    } catch (err: any) {
      testError = err.message || "Failed to communicate with Revit Sync Gateway.";
    } finally {
      isSendingTest = false;
    }
  }

  function exportResultsToCsv() {
    const target = table.selectedCount ? table.selectedRows : table.sorted;
    const headers = [
      "RuleReference",
      "Description",
      "Target",
      "Property",
      "Status",
      "PassCount",
      "FailCount",
      "MissingCount",
    ];
    const rows = target.map((r) => [
      `"${(r.rule_ref || "").replace(/"/g, '""')}"`,
      `"${(r.rule_desc || "").replace(/"/g, '""')}"`,
      `"${(r.target || "").replace(/"/g, '""')}"`,
      `"${(r.property_name || "").replace(/"/g, '""')}"`,
      r.status,
      r.pass_count || 0,
      r.fail_count || 0,
      r.missing_count || 0,
    ]);
    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute(
      "download",
      `revit_sync_results_${new Date().toISOString().substring(0, 10)}.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
</script>

<div class="mx-auto space-y-6">
  <!-- Header -->
  <PageHeader
    category="Live Native Integrations"
    title="Autodesk Revit® Direct Sync"
    subtitle="Zero-file OpenBIM compliance auditing directly from Autodesk Revit via pyRevit, Revit API, or Dynamo Python scripts."
    icon={Layers}
  />

  <!-- Bento Grid Overview -->
  <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
    <BentoBox title="Instant Evaluation" cls="md:col-span-1">
      <p class="mb-4 text-xs leading-relaxed text-slate-400">
        Push elements from active views or entire Revit project models directly to BIM Guard without
        exporting IFC files.
      </p>
      <div class="flex items-center gap-2 text-xs font-medium text-emerald-400">
        <CheckCircle2 class="h-4 w-4" />
        <span>Sub-second Rule Execution</span>
      </div>
    </BentoBox>

    <BentoBox title="Gateway Endpoint" cls="md:col-span-2">
      <p class="mb-2 text-xs text-slate-400">
        HTTP POST target receiving JSON element collections from Revit extensions:
      </p>
      <div
        class="flex select-all items-center justify-between overflow-x-auto rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono text-xs text-blue-400"
      >
        <span>POST {endpointUrl}</span>
      </div>
    </BentoBox>
  </div>

  <!-- pyRevit Snippet Section -->
  <div class="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
    <div class="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
      <div>
        <h2 class="text-base font-bold tracking-tight text-slate-50">
          pyRevit / IronPython Push Script
        </h2>
        <p class="text-xs text-slate-400">
          Embed this script inside your pyRevit ribbon pushbutton to audit selected categories in
          one click.
        </p>
      </div>

      <div class="flex items-center gap-2">
        <button
          type="button"
          onclick={copyScript}
          class="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-1.5 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
        >
          {#if copied}
            <Check class="h-3.5 w-3.5 text-emerald-400" />
            <span class="text-emerald-400">Copied!</span>
          {:else}
            <Copy class="h-3.5 w-3.5" />
            <span>Copy Script</span>
          {/if}
        </button>

        <button
          type="button"
          disabled={isSendingTest}
          onclick={runSimulation}
          class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-1.5 text-xs font-semibold text-white shadow-sm transition-all hover:bg-accent-hover disabled:opacity-50"
        >
          <Send class="h-3.5 w-3.5" />
          <span>{isSendingTest ? "Auditing Payload..." : "Simulate Push"}</span>
        </button>
      </div>
    </div>

    <!-- Code Block -->
    <div class="relative overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
      <pre
        class="max-h-72 overflow-x-auto p-4 font-mono text-xs leading-relaxed text-slate-300">{pyRevitScript}</pre>
    </div>
  </div>

  <!-- Test Simulation Results -->
  {#if testError}
    <div
      class="flex items-start gap-2.5 rounded-2xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300"
    >
      <AlertTriangle class="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
      <div>{testError}</div>
    </div>
  {:else if isSendingTest}
    <LoadingState message="Auditing payload against building codes…" />
  {/if}

  {#if testResponse}
    <div class="space-y-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
      <div
        class="flex flex-col justify-between gap-4 border-b border-slate-800 pb-4 sm:flex-row sm:items-center"
      >
        <div>
          <div class="mb-1 text-xs font-bold uppercase tracking-wider text-emerald-400">
            Sync Results Received
          </div>
          <h2 class="text-lg font-bold text-slate-50">
            {samplePayload.project_name}
          </h2>
          <p class="text-xs text-slate-400">
            Assessed {testResponse.element_count} elements against building codes • Theme:
            {testResponse.theme}
          </p>
        </div>

        <div class="flex items-center gap-3">
          <div
            class="flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs font-bold text-slate-300"
          >
            <span
              >Pass: {testResponse.results.reduce((acc, r) => acc + (r.pass_count || 0), 0)}</span
            >
          </div>
          <div
            class="flex items-center gap-1.5 rounded-full border border-rose-800 bg-rose-950/80 px-3 py-1.5 text-xs font-bold text-rose-400"
          >
            <span
              >Fail: {testResponse.results.reduce((acc, r) => acc + (r.fail_count || 0), 0)}</span
            >
          </div>
        </div>
      </div>

      <!-- Search & Filter Toolbar -->
      <div
        class="flex flex-col items-center justify-between gap-3 rounded-2xl border border-slate-800/90 bg-slate-950/80 p-3.5 sm:flex-row"
      >
        <div class="relative w-full flex-1">
          <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            bind:value={table.search}
            placeholder="Search rules by reference, target, property..."
            class="w-full rounded-xl border border-slate-800 bg-slate-900 py-2 pl-10 pr-4 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
          />
        </div>

        <div class="flex w-full items-center gap-2 sm:w-auto">
          <select
            bind:value={table.filters.status}
            class="rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
          >
            <option value="ALL">All Verdicts</option>
            <option value="PASS">PASS Only</option>
            <option value="FAIL">FAIL Only</option>
          </select>
        </div>
      </div>

      <!-- Bulk Action Bar -->
      <BulkActionBar
        selectedCount={table.selectedCount}
        itemLabel="rule result"
        onClearSelection={() => table.clearSelection()}
        onBulkExport={exportResultsToCsv}
        onBulkDelete={null}
        onBulkEdit={null}
      />

      <!-- Results Table -->
      <div class="overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/50">
        <div class="overflow-x-auto">
          <table class="w-full border-collapse text-left text-xs">
            <thead>
              <tr
                class="border-b border-slate-800 bg-slate-950/80 text-micro font-semibold uppercase tracking-wider text-slate-400"
              >
                <th class="w-10 px-3 py-3">
                  <TableCheckbox
                    checked={table.allFilteredSelected}
                    indeterminate={table.someFilteredSelected}
                    onchange={() => table.toggleSelectAll()}
                    title="Select all results"
                  />
                </th>
                <SortHeader
                  column="rule_ref"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                  customClass="py-3 px-3"
                >
                  Rule Reference
                </SortHeader>
                <SortHeader
                  column="target"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                  customClass="py-3 px-3"
                >
                  Target
                </SortHeader>
                <SortHeader
                  column="property_name"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                  customClass="py-3 px-3"
                >
                  Property
                </SortHeader>
                <SortHeader
                  column="status"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                  customClass="py-3 px-3"
                >
                  Status
                </SortHeader>
                <SortHeader
                  column="fail_count"
                  sortField={table.sortField}
                  sortAsc={table.sortAsc}
                  onSort={(f) => table.toggleSort(f)}
                  customClass="py-3 px-3"
                >
                  Pass / Fail / Missing
                </SortHeader>
                <th class="px-3 py-3">Violations</th>
                <th class="px-3 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800/60">
              {#if table.paginated.length === 0}
                <tr>
                  <td colspan="8" class="p-8 text-center text-xs text-slate-500">
                    No sync results match your filter criteria.
                  </td>
                </tr>
              {:else}
                {#each table.paginated as rule (rule.rowId)}
                  <tr
                    class="transition-colors hover:bg-slate-800/30 {table.isSelected(rule.rowId)
                      ? 'bg-blue-950/20'
                      : ''}"
                  >
                    <td class="w-10 px-3 py-3">
                      <TableCheckbox
                        checked={table.isSelected(rule.rowId)}
                        onchange={() => table.toggleSelect(rule.rowId)}
                        ariaLabel={`Select rule ${rule.rule_ref}`}
                      />
                    </td>
                    <td class="px-3 py-3 font-mono font-semibold text-slate-50">
                      {rule.rule_ref || "Custom Rule"}
                      {#if rule.rule_desc}
                        <div class="mt-0.5 font-sans text-caption font-normal text-slate-400">
                          {rule.rule_desc}
                        </div>
                      {/if}
                    </td>
                    <td class="px-3 py-3 font-mono text-slate-300">
                      <BsddBadge kind="class" value={rule.target} />
                    </td>
                    <td class="px-3 py-3 font-mono text-slate-300">
                      <BsddBadge kind="property" value={rule.property_name} />
                    </td>
                    <td class="px-3 py-3">
                      <Badge
                        variant={rule.status === "PASS"
                          ? "low"
                          : rule.status === "FAIL"
                            ? "critical"
                            : "medium"}
                      >
                        {rule.status || "UNKNOWN"}
                      </Badge>
                    </td>
                    <td class="px-3 py-3 font-mono">
                      <span class="font-semibold text-emerald-400">{rule.pass_count || 0}</span>
                      /
                      <span class="font-semibold text-rose-400">{rule.fail_count || 0}</span>
                      /
                      <span class="text-slate-400">{rule.missing_count || 0}</span>
                    </td>
                    <td class="max-w-xs px-3 py-3">
                      {#if rule.failures && rule.failures.length > 0}
                        <div class="space-y-1">
                          {#each rule.failures as f (f.guid)}
                            <div
                              class="truncate font-mono text-caption text-rose-300"
                              title={f.reason || f.guid}
                            >
                              • {f.reason || f.guid}
                            </div>
                          {/each}
                        </div>
                      {:else}
                        <span class="text-slate-500">—</span>
                      {/if}
                    </td>
                    <td class="whitespace-nowrap px-3 py-3 text-right">
                      <button
                        type="button"
                        onclick={() => (viewingRule = rule)}
                        class="rounded-lg bg-slate-800 p-1.5 text-slate-300 transition-colors hover:bg-slate-700 hover:text-slate-50"
                        title="Inspect rule result details"
                      >
                        <Eye class="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                {/each}
              {/if}
            </tbody>
          </table>
        </div>

        <TablePagination
          currentPage={table.page}
          pageSize={table.pageSize}
          totalItems={table.totalItems}
          onPageChange={(p) => (table.requestedPage = p)}
          onPageSizeChange={(size) => {
            table.pageSize = size;
            table.requestedPage = 1;
          }}
        />
      </div>
    </div>
  {/if}
</div>

<!-- Rule Inspection Modal -->
{#if viewingRule}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-md">
    <div
      class="w-full max-w-lg space-y-4 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl"
    >
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <FileText class="h-4 w-4 text-accent" />
          <h3 class="font-mono text-sm font-bold text-slate-50">
            {viewingRule.rule_ref || "Rule Result"}
          </h3>
        </div>
        <button
          type="button"
          onclick={() => (viewingRule = null)}
          class="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-4 w-4" />
        </button>
      </div>

      <div class="space-y-3 text-xs">
        <div>
          <span class="mb-1 block font-semibold text-slate-400">Description</span>
          <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-3 text-slate-200">
            {viewingRule.rule_desc || "No description provided"}
          </div>
        </div>

        <div
          class="grid grid-cols-2 gap-2 rounded-xl border border-slate-800 bg-slate-950 p-3 font-mono text-caption"
        >
          <div>
            <span class="text-slate-500">Target:</span>
            <BsddBadge kind="class" value={viewingRule.target} class="text-slate-300" />
          </div>
          <div>
            <span class="text-slate-500">Property:</span>
            <BsddBadge kind="property" value={viewingRule.property_name} class="text-slate-300" />
          </div>
          <div>
            <span class="text-slate-500">Verdict:</span>
            <span
              class="font-bold {viewingRule.status === 'PASS'
                ? 'text-emerald-400'
                : 'text-rose-400'}">{viewingRule.status}</span
            >
          </div>
          <div>
            <span class="text-slate-500">Pass / Fail:</span>
            <span class="text-slate-300"
              >{viewingRule.pass_count || 0} / {viewingRule.fail_count || 0}</span
            >
          </div>
        </div>

        {#if viewingRule.failures && viewingRule.failures.length > 0}
          <div>
            <span class="mb-1 block font-semibold text-slate-400"
              >Non-Compliant Element Instances ({viewingRule.failures.length})</span
            >
            <div
              class="max-h-48 space-y-1.5 overflow-y-auto rounded-xl border border-slate-800 bg-slate-950 p-2"
            >
              {#each viewingRule.failures as f (f.guid)}
                <div
                  class="rounded-lg border border-rose-900/40 bg-rose-950/20 p-2 font-mono text-caption text-rose-300"
                >
                  <div class="font-bold">{f.guid}</div>
                  {#if f.reason}<div class="mt-0.5 text-micro text-slate-400">{f.reason}</div>{/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>

      <div class="flex justify-end border-t border-slate-800 pt-2">
        <button
          type="button"
          onclick={() => (viewingRule = null)}
          class="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}
