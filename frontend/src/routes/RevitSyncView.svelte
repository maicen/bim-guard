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
  } from 'lucide-svelte';
  import { revitSyncApi } from '../lib/api';
  import type { RevitSyncRequest, RevitSyncResponse, RevitRuleResult } from '../lib/types';
  import Badge from '../lib/components/Badge.svelte';
  import BentoBox from '../lib/components/BentoBox.svelte';

  let copied = false;
  let isSendingTest = false;
  let testResponse: RevitSyncResponse | null = null;
  let testError: string | null = null;

  const endpointUrl = typeof window !== 'undefined'
    ? `${window.location.origin}/api/analyze/revit-sync`
    : 'http://localhost:8000/api/analyze/revit-sync';

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
          Width: 850.0,  // Failing: < 900mm
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

  async function runSampleTest() {
    isSendingTest = true;
    testError = null;
    testResponse = null;
    try {
      testResponse = await revitSyncApi.sync(samplePayload);
    } catch (err: any) {
      testError = err.message || 'Direct sync failed.';
    } finally {
      isSendingTest = false;
    }
  }
</script>

<div class="space-y-8 max-w-6xl mx-auto">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <div class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
        Integrations
      </div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">
        Revit Direct Sync
      </h1>
      <p class="text-xs sm:text-sm text-slate-400">
        Push live BIM element data directly from Autodesk Revit using pyRevit — zero IFC export required.
      </p>
    </div>

    <div class="flex items-center gap-2">
      <button
        type="button"
        on:click={runSampleTest}
        disabled={isSendingTest}
        class="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] disabled:opacity-50"
      >
        <Send class="w-3.5 h-3.5" />
        <span>{isSendingTest ? 'Sending Test...' : 'Simulate Direct Push'}</span>
      </button>
    </div>
  </div>

  <!-- Bento Overview Grid -->
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
    <BentoBox
      title="Endpoint URL"
      value="POST /api/analyze/revit-sync"
      description="Accepts JSON element payloads directly from pyRevit or custom plugins"
      icon={Terminal}
    />
    <BentoBox
      title="Supported Categories"
      value="Architecture & MEP"
      description="Stairs, Doors, Walls, Piping, Clearances against Ontario Building Code & BIMGUARD rules"
      icon={Boxes}
    />
    <BentoBox
      title="Execution Mode"
      value="Instant In-Memory"
      description="Validates element attributes without intermediate disk storage or file parsing overhead"
      icon={Layers}
    />
  </div>

  <!-- Setup Instructions & pyRevit Template -->
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <!-- Steps Card -->
    <div class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4 flex flex-col justify-between">
      <div class="space-y-3">
        <div class="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400">
          <Code class="w-4 h-4 text-blue-400" />
          <span>Connection Guide</span>
        </div>
        <h2 class="text-lg font-bold text-white tracking-tight">
          How to connect your Revit model
        </h2>
        <ol class="list-decimal list-inside space-y-3 text-xs text-slate-300 leading-relaxed">
          <li>
            <strong class="text-white">Install pyRevit:</strong> Download and install the open-source pyRevit CLI/GUI from <a href="https://pyrevitlabs.io" target="_blank" rel="noreferrer" class="text-blue-400 underline">pyrevitlabs.io</a>.
          </li>
          <li>
            <strong class="text-white">Create Button:</strong> In your Revit extensions folder, create a pushbutton folder structure (e.g. <code class="font-mono bg-slate-800 px-1 py-0.5 rounded text-slate-200">BIMGuard.extension/BIMGuard.tab/Audit.panel/DirectSync.pushbutton</code>).
          </li>
          <li>
            <strong class="text-white">Copy Template:</strong> Paste the IronPython script template on the right into <code class="font-mono bg-slate-800 px-1 py-0.5 rounded text-slate-200">script.py</code>.
          </li>
          <li>
            <strong class="text-white">Click &amp; Verify:</strong> Click the button in your Revit ribbon. Compliance findings appear instantly in this view and in your audit reports.
          </li>
        </ol>
      </div>

      <div class="p-4 rounded-xl bg-slate-950/70 border border-slate-800 space-y-1.5">
        <div class="text-[11px] font-bold text-slate-400 uppercase tracking-widest">Active Sync Target</div>
        <div class="font-mono text-xs text-blue-400 break-all select-all">
          {endpointUrl}
        </div>
      </div>
    </div>

    <!-- Script Template Card -->
    <div class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3 flex flex-col justify-between">
      <div class="flex items-center justify-between">
        <div class="text-xs font-bold uppercase tracking-wider text-slate-400">
          pyRevit Script Template
        </div>
        <button
          type="button"
          on:click={copyScript}
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
        >
          {#if copied}
            <Check class="w-3.5 h-3.5 text-emerald-400" />
            <span class="text-emerald-400 font-semibold">Copied!</span>
          {:else}
            <Copy class="w-3.5 h-3.5" />
            <span>Copy Script</span>
          {/if}
        </button>
      </div>

      <pre class="bg-slate-950/90 border border-slate-800/80 rounded-xl p-4 overflow-x-auto text-[11px] font-mono text-slate-300 leading-relaxed max-h-80 select-all">
{pyRevitScript}
      </pre>
    </div>
  </div>

  <!-- Test Simulation Results -->
  {#if testError}
    <div class="p-4 rounded-2xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs flex items-start gap-2.5">
      <AlertTriangle class="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
      <div>{testError}</div>
    </div>
  {/if}

  {#if testResponse}
    <div class="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-6">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div class="text-xs font-bold uppercase tracking-wider text-emerald-400 mb-1">
            Sync Results Received
          </div>
          <h2 class="text-lg font-bold text-white">
            {samplePayload.project_name}
          </h2>
          <p class="text-xs text-slate-400">
            Assessed {testResponse.element_count} elements against OBC rules • Theme: {testResponse.theme}
          </p>
        </div>

        <div class="flex items-center gap-3">
          <div class="flex items-center gap-1.5 text-xs font-bold text-slate-300 bg-slate-800/80 px-3 py-1.5 rounded-full border border-slate-700">
            <span>Pass: {testResponse.results.reduce((acc, r) => acc + (r.pass_count || 0), 0)}</span>
          </div>
          <div class="flex items-center gap-1.5 text-xs font-bold text-rose-400 bg-rose-950/80 px-3 py-1.5 rounded-full border border-rose-800">
            <span>Fail: {testResponse.results.reduce((acc, r) => acc + (r.fail_count || 0), 0)}</span>
          </div>
        </div>
      </div>

      <!-- Results Table -->
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="border-b border-slate-800 text-slate-400 uppercase text-[10px] tracking-wider">
              <th class="py-2.5 px-3">Rule Reference</th>
              <th class="py-2.5 px-3">Target</th>
              <th class="py-2.5 px-3">Property</th>
              <th class="py-2.5 px-3">Status</th>
              <th class="py-2.5 px-3">Pass / Fail / Missing</th>
              <th class="py-2.5 px-3">Violations</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each testResponse.results as rule}
              <tr class="hover:bg-slate-800/30 transition-colors">
                <td class="py-3 px-3 font-semibold text-white font-mono">
                  {rule.rule_ref || 'Custom Rule'}
                  {#if rule.rule_desc}
                    <div class="text-[11px] text-slate-400 font-sans font-normal mt-0.5">
                      {rule.rule_desc}
                    </div>
                  {/if}
                </td>
                <td class="py-3 px-3 font-mono text-slate-300">
                  {rule.target || '—'}
                </td>
                <td class="py-3 px-3 text-slate-300 font-mono">
                  {rule.property_name || '—'}
                </td>
                <td class="py-3 px-3">
                  <Badge variant={rule.status === 'PASS' ? 'low' : rule.status === 'FAIL' ? 'critical' : 'medium'}>
                    {rule.status || 'UNKNOWN'}
                  </Badge>
                </td>
                <td class="py-3 px-3 font-mono">
                  <span class="text-emerald-400 font-semibold">{rule.pass_count || 0}</span> /
                  <span class="text-rose-400 font-semibold">{rule.fail_count || 0}</span> /
                  <span class="text-slate-400">{rule.missing_count || 0}</span>
                </td>
                <td class="py-3 px-3 max-w-xs">
                  {#if rule.failures && rule.failures.length > 0}
                    <div class="space-y-1">
                      {#each rule.failures as f}
                        <div class="text-[11px] text-rose-300 font-mono truncate" title={f.reason || f.guid}>
                          • {f.reason || f.guid}
                        </div>
                      {/each}
                    </div>
                  {:else}
                    <span class="text-slate-500">—</span>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}
</div>
