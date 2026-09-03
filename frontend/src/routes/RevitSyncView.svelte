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
    Download,
    FileText,
  } from "lucide-svelte";
  import { revitSyncApi } from "../lib/api";
  import type {
    RevitSyncRequest,
    RevitSyncResponse,
    RevitRuleResult,
  } from "../lib/types";
  import Badge from "../lib/components/Badge.svelte";
  import BentoBox from "../lib/components/BentoBox.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import SortHeader from "../lib/components/SortHeader.svelte";
  import TableCheckbox from "../lib/components/TableCheckbox.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import { createTableState } from "../lib/tableState.svelte";

  let copied = false;
  let isSendingTest = false;
  let testResponse: RevitSyncResponse | null = null;
  let testError: string | null = null;

  // The sync response carries no unique key — rule_ref repeats across targets
  // and properties — so rows get a stable index-based id when they arrive.
  type IndexedRuleResult = RevitRuleResult & { rowId: number };
  let indexedResults: IndexedRuleResult[] = [];

  // Search, filter, sort, paginate and select — all owned by the shared state.
  const table = createTableState<IndexedRuleResult, number>({
    rows: () => indexedResults,
    getId: (r) => r.rowId,
    searchFields: (r) => [r.rule_ref, r.rule_desc, r.target, r.property_name],
    filters: {
      status: (r, value) => (r.status || "").toUpperCase() === value.toUpperCase(),
    },
    initialSort: { field: "fail_count", asc: false },
  });

  let viewingRule: IndexedRuleResult | null = null;

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
    const headers = ["RuleReference", "Description", "Target", "Property", "Status", "PassCount", "FailCount", "MissingCount"];
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
    link.setAttribute("download", `revit_sync_results_${new Date().toISOString().substring(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
</script>

<div class="space-y-6 mx-auto">
  <!-- Header -->
  <PageHeader
    category="Live Native Integrations"
    title="Autodesk Revit® Direct Sync"
    subtitle="Zero-file OpenBIM compliance auditing directly from Autodesk Revit via pyRevit, Revit API, or Dynamo Python scripts."
    icon={Layers}
  />

  <!-- Bento Grid Overview -->
  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
    <BentoBox title="Instant Evaluation" cls="md:col-span-1">
      <p class="text-xs text-slate-400 leading-relaxed mb-4">
        Push elements from active views or entire Revit project models directly
        to BIM Guard without exporting IFC files.
      </p>
      <div class="flex items-center gap-2 text-xs text-emerald-400 font-medium">
        <CheckCircle2 class="w-4 h-4" />
        <span>Sub-second Rule Execution</span>
      </div>
    </BentoBox>

    <BentoBox title="Gateway Endpoint" cls="md:col-span-2">
      <p class="text-xs text-slate-400 mb-2">
        HTTP POST target receiving JSON element collections from Revit
        extensions:
      </p>
      <div
        class="flex items-center justify-between p-3 rounded-xl bg-slate-950 border border-slate-800 font-mono text-xs text-blue-400 select-all overflow-x-auto"
      >
        <span>POST {endpointUrl}</span>
      </div>
    </BentoBox>
  </div>

  <!-- pyRevit Snippet Section -->
  <div
    class="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4"
  >
    <div
      class="flex flex-col sm:flex-row sm:items-center justify-between gap-3"
    >
      <div>
        <h2 class="text-base font-bold text-slate-50 tracking-tight">
          pyRevit / IronPython Push Script
        </h2>
        <p class="text-xs text-slate-400">
          Embed this script inside your pyRevit ribbon pushbutton to audit
          selected categories in one click.
        </p>
      </div>

      <div class="flex items-center gap-2">
        <button
          type="button"
          on:click={copyScript}
          class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-50 text-xs font-semibold border border-slate-700 transition-colors"
        >
          {#if copied}
            <Check class="w-3.5 h-3.5 text-emerald-400" />
            <span class="text-emerald-400">Copied!</span>
          {:else}
            <Copy class="w-3.5 h-3.5" />
            <span>Copy Script</span>
          {/if}
        </button>

        <button
          type="button"
          disabled={isSendingTest}
          on:click={runSimulation}
          class="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-accent hover:bg-accent-hover text-white text-xs font-semibold shadow-sm transition-all disabled:opacity-50"
        >
          <Send class="w-3.5 h-3.5" />
          <span>{isSendingTest ? "Auditing Payload..." : "Simulate Push"}</span>
        </button>
      </div>
    </div>

    <!-- Code Block -->
    <div
      class="relative rounded-xl overflow-hidden border border-slate-800 bg-slate-950"
    >
      <pre
        class="p-4 text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed max-h-72">{pyRevitScript}</pre>
    </div>
  </div>

  <!-- Test Simulation Results -->
  {#if testError}
    <div
      class="p-4 rounded-2xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs flex items-start gap-2.5"
    >
      <AlertTriangle class="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
      <div>{testError}</div>
    </div>
  {/if}

  {#if testResponse}
    <div
      class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-6"
    >
      <div
        class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4"
      >
        <div>
          <div
            class="text-xs font-bold uppercase tracking-wider text-emerald-400 mb-1"
          >
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
            class="flex items-center gap-1.5 text-xs font-bold text-slate-300 bg-slate-800/80 px-3 py-1.5 rounded-full border border-slate-700"
          >
            <span
              >Pass: {testResponse.results.reduce(
                (acc, r) => acc + (r.pass_count || 0),
                0,
              )}</span
            >
          </div>
          <div
            class="flex items-center gap-1.5 text-xs font-bold text-rose-400 bg-rose-950/80 px-3 py-1.5 rounded-full border border-rose-800"
          >
            <span
              >Fail: {testResponse.results.reduce(
                (acc, r) => acc + (r.fail_count || 0),
                0,
              )}</span
            >
          </div>
        </div>
      </div>

      <!-- Search & Filter Toolbar -->
      <div class="p-3.5 rounded-2xl bg-slate-950/80 border border-slate-800/90 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div class="relative flex-1 w-full">
          <Search class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            bind:value={table.search}
            placeholder="Search rules by reference, target, property..."
            class="w-full bg-slate-900 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-xs text-slate-50 placeholder-slate-500 focus:outline-none focus:border-accent"
          />
        </div>

        <div class="flex items-center gap-2 w-full sm:w-auto">
          <select
            bind:value={table.filters.status}
            class="bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-50 focus:outline-none focus:border-accent"
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
      <div class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-950/50">
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs border-collapse">
            <thead>
              <tr
                class="border-b border-slate-800 bg-slate-950/80 text-slate-400 uppercase text-micro tracking-wider font-semibold"
              >
                <th class="py-3 px-3 w-10">
                  <TableCheckbox
                    checked={table.allFilteredSelected}
                    indeterminate={table.someFilteredSelected}
                    on:change={() => table.toggleSelectAll()}
                    title="Select all results"
                  />
                </th>
                <SortHeader column="rule_ref" sortField={table.sortField} sortAsc={table.sortAsc} onSort={(f) => table.toggleSort(f)} customClass="py-3 px-3">
                  Rule Reference
                </SortHeader>
                <SortHeader column="target" sortField={table.sortField} sortAsc={table.sortAsc} onSort={(f) => table.toggleSort(f)} customClass="py-3 px-3">
                  Target
                </SortHeader>
                <SortHeader column="property_name" sortField={table.sortField} sortAsc={table.sortAsc} onSort={(f) => table.toggleSort(f)} customClass="py-3 px-3">
                  Property
                </SortHeader>
                <SortHeader column="status" sortField={table.sortField} sortAsc={table.sortAsc} onSort={(f) => table.toggleSort(f)} customClass="py-3 px-3">
                  Status
                </SortHeader>
                <SortHeader column="fail_count" sortField={table.sortField} sortAsc={table.sortAsc} onSort={(f) => table.toggleSort(f)} customClass="py-3 px-3">
                  Pass / Fail / Missing
                </SortHeader>
                <th class="py-3 px-3">Violations</th>
                <th class="py-3 px-3 text-right">Actions</th>
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
                  <tr class="hover:bg-slate-800/30 transition-colors {table.isSelected(rule.rowId) ? 'bg-blue-950/20' : ''}">
                    <td class="py-3 px-3 w-10">
                      <TableCheckbox
                        checked={table.isSelected(rule.rowId)}
                        on:change={() => table.toggleSelect(rule.rowId)}
                        ariaLabel={`Select rule ${rule.rule_ref}`}
                      />
                    </td>
                    <td class="py-3 px-3 font-semibold text-slate-50 font-mono">
                      {rule.rule_ref || "Custom Rule"}
                      {#if rule.rule_desc}
                        <div
                          class="text-caption text-slate-400 font-sans font-normal mt-0.5"
                        >
                          {rule.rule_desc}
                        </div>
                      {/if}
                    </td>
                    <td class="py-3 px-3 font-mono text-slate-300">
                      {rule.target || "—"}
                    </td>
                    <td class="py-3 px-3 text-slate-300 font-mono">
                      {rule.property_name || "—"}
                    </td>
                    <td class="py-3 px-3">
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
                    <td class="py-3 px-3 font-mono">
                      <span class="text-emerald-400 font-semibold"
                        >{rule.pass_count || 0}</span
                      >
                      /
                      <span class="text-rose-400 font-semibold"
                        >{rule.fail_count || 0}</span
                      >
                      /
                      <span class="text-slate-400">{rule.missing_count || 0}</span>
                    </td>
                    <td class="py-3 px-3 max-w-xs">
                      {#if rule.failures && rule.failures.length > 0}
                        <div class="space-y-1">
                          {#each rule.failures as f}
                            <div
                              class="text-caption text-rose-300 font-mono truncate"
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
                    <td class="py-3 px-3 text-right whitespace-nowrap">
                      <button
                        type="button"
                        on:click={() => (viewingRule = rule)}
                        class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-slate-50 transition-colors"
                        title="Inspect rule result details"
                      >
                        <Eye class="w-3.5 h-3.5" />
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
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden p-6 space-y-4">
      <div class="flex items-center justify-between border-b border-slate-800 pb-3">
        <div class="flex items-center gap-2">
          <FileText class="w-4 h-4 text-accent" />
          <h3 class="text-sm font-bold text-slate-50 font-mono">{viewingRule.rule_ref || 'Rule Result'}</h3>
        </div>
        <button
          type="button"
          on:click={() => (viewingRule = null)}
          class="text-slate-400 hover:text-slate-50 p-1 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <div class="space-y-3 text-xs">
        <div>
          <span class="text-slate-400 font-semibold block mb-1">Description</span>
          <div class="p-3 bg-slate-950/60 rounded-xl border border-slate-800 text-slate-200">
            {viewingRule.rule_desc || 'No description provided'}
          </div>
        </div>

        <div class="grid grid-cols-2 gap-2 text-caption font-mono bg-slate-950 p-3 rounded-xl border border-slate-800">
          <div><span class="text-slate-500">Target:</span> <span class="text-slate-300">{viewingRule.target || '—'}</span></div>
          <div><span class="text-slate-500">Property:</span> <span class="text-slate-300">{viewingRule.property_name || '—'}</span></div>
          <div><span class="text-slate-500">Verdict:</span> <span class="font-bold {viewingRule.status === 'PASS' ? 'text-emerald-400' : 'text-rose-400'}">{viewingRule.status}</span></div>
          <div><span class="text-slate-500">Pass / Fail:</span> <span class="text-slate-300">{viewingRule.pass_count || 0} / {viewingRule.fail_count || 0}</span></div>
        </div>

        {#if viewingRule.failures && viewingRule.failures.length > 0}
          <div>
            <span class="text-slate-400 font-semibold block mb-1">Non-Compliant Element Instances ({viewingRule.failures.length})</span>
            <div class="max-h-48 overflow-y-auto space-y-1.5 p-2 bg-slate-950 rounded-xl border border-slate-800">
              {#each viewingRule.failures as f}
                <div class="p-2 bg-rose-950/20 border border-rose-900/40 rounded-lg text-rose-300 font-mono text-caption">
                  <div class="font-bold">{f.guid}</div>
                  {#if f.reason}<div class="text-slate-400 text-micro mt-0.5">{f.reason}</div>{/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>

      <div class="flex justify-end pt-2 border-t border-slate-800">
        <button
          type="button"
          on:click={() => (viewingRule = null)}
          class="px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-50 transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}
