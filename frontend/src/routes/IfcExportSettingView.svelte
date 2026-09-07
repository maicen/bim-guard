<script lang="ts">
  import { Download, FileText, CheckCircle2, Layers } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import BentoBox from "../lib/components/BentoBox.svelte";

  const CHECKLIST = [
    "Internal Revit and IFC common property sets exported",
    "Steel elements included, 2D elements excluded",
    "Max tessellation detail and solid model representation for accurate stair/railing mesh geometry",
    "Stable IFC GUIDs stored for reliable re-audits",
  ];
</script>

<div class="mx-auto space-y-6">
  <PageHeader
    category="Live Native Integrations"
    title="IFC Export Setting for Architectural Model"
    subtitle="A preconfigured Revit IFC4 export profile tuned for BIM Guard audits — consistent property sets, base quantities, and GUIDs on every export."
    icon={FileText}
  />

  <!-- Bento Grid Overview -->
  <div class="mx-auto w-full max-w-xs">
    <BentoBox title="IFC Version" value="IFC4" icon={Layers} description="Design Transfer View exchange" />
  </div>

  <!-- Download -->
  <div class="flex flex-col items-center gap-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-6 text-center">
    <a
      href="/downloads/IFC_Export_Setting.json"
      download="IFC_Export_Setting.json"
      class="inline-flex shrink-0 items-center gap-3 rounded-xl bg-accent px-8 py-4 text-2xl font-semibold text-white shadow-sm transition-all hover:bg-accent-hover"
    >
      <Download class="h-7 w-7" />
      <span>Download IFC Export Setting</span>
    </a>

    <div>
      <p class="mx-auto max-w-xl text-xs text-slate-400">
        Import this .json profile into Revit's IFC export setup dialog (Modify Setup → Load
        existing setup...) so every export from this project uses the property sets, quantities,
        and GUID handling BIM Guard expects.
      </p>
    </div>
  </div>

  <!-- Setup Guide -->
  <div class="flex flex-col items-center gap-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-6 text-center">
    <a
      href="/downloads/README.md"
      download="IFC_Export_Setting_README.md"
      class="inline-flex shrink-0 items-center gap-3 rounded-xl bg-accent px-8 py-4 text-2xl font-semibold text-white shadow-sm transition-all hover:bg-accent-hover"
    >
      <Download class="h-7 w-7" />
      <span>Download Setup Guide</span>
    </a>

    <div>
      <p class="mx-auto max-w-xl text-xs text-slate-400">
        Covers picking the phase to export per project, why Export Material Psets must stay
        ticked for seismic mass checks, and how to include linked Revit files.
      </p>
    </div>
  </div>

  <!-- What's Included -->
  <div class="space-y-3 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
    <h2 class="text-base font-bold tracking-tight text-slate-50">What's Included</h2>
    <ul class="grid grid-cols-1 gap-2 text-xs text-slate-400 sm:grid-cols-2">
      {#each CHECKLIST as item (item)}
        <li class="flex items-start gap-2">
          <CheckCircle2 class="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
          <span>{item}</span>
        </li>
      {/each}
    </ul>
  </div>
</div>
