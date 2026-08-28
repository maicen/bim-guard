<script lang="ts">
  import {
    FolderPlus,
    ScanEye,
    BookOpen,
    ListChecks,
    Cpu,
    FileText,
    ArrowRight,
    CheckCircle2,
  } from 'lucide-svelte';

  export let onNavigate: (view: string) => void;

  const STEPS = [
    {
      step: 1,
      title: 'Create a project and upload the IFC model',
      icon: FolderPlus,
      description:
        'Create a project record, specify project name, description, country jurisdiction, and upload the IFC 2x3 or IFC4 model. The project becomes the shared source for the 3D viewer, rule evaluations, and reports.',
      result: 'Result: The project appears in the project registry with its IFC file attached and parsed.',
      actions: [
        { label: 'View Projects', view: 'projects', primary: true },
      ],
    },
    {
      step: 2,
      title: 'Inspect the model in the 3D OpenBIM Viewer',
      icon: ScanEye,
      description:
        'Open the viewer and select the uploaded project. Orbit through the model, verify building geometry, inspect element properties, and check that expected spatial components are present.',
      result: 'Result: You visually confirm that the IFC geometry and spatial structure load cleanly.',
      actions: [{ label: 'Open 3D Viewer', view: 'viewer', primary: true }],
    },
    {
      step: 3,
      title: 'Add the compliance reference documents',
      icon: BookOpen,
      description:
        'Upload the PDF, Markdown, or text specifications that define the technical requirements for the project. BIM Guard stores each specification and parses its textual content for automated rule synthesis.',
      result: 'Result: Source specifications and extracted clauses are stored in the library.',
      actions: [{ label: 'Open Document Library', view: 'documents', primary: true }],
    },
    {
      step: 4,
      title: 'Extract and review compliance rules',
      icon: ListChecks,
      description:
        'Use Rule Extraction Studio to turn reference specification clauses into structured, executable checks. Review property sets, operators, target values, and severities, then persist them to the rules library.',
      result: 'Result: A reviewed rule set is categorized and ready to evaluate against the model.',
      actions: [
        { label: 'Rule Extraction Studio', view: 'extract', primary: true },
        { label: 'Review Rules Catalog', view: 'rules', primary: false },
      ],
    },
    {
      step: 5,
      title: 'Run compliance analysis (ARCH & MEP)',
      icon: Cpu,
      description:
        'Execute multi-domain checks against the IFC geometry. Run architectural compliance for Ontario Building Code egress, daylight, and fire separations, or MEP checks for galvanic (GC-001), crevice (CC-001), and MIC (MC-001) piping corrosion and seismic clearances.',
      result: 'Result: Non-compliant elements are tagged with risk bands, scores, and mitigations.',
      actions: [
        { label: 'Run ARCH Audit', view: 'arch', primary: true },
        { label: 'Run MEP & Piping', view: 'analyze', primary: false },
      ],
    },
    {
      step: 6,
      title: 'Export compliance reports & BCF deliverables',
      icon: FileText,
      description:
        'Export findings into BCF 2.1 archives for issue resolution in authoring tools (Revit, ArchiCAD, Navisworks), or download CSV and JSON reports summarizing remediation delays and cost impacts.',
      result: 'Result: Project stakeholders receive industry-standard OpenBIM audit deliverables.',
      actions: [{ label: 'Reports & Exports', view: 'reports', primary: true }],
    },
  ];
</script>

<div class="space-y-6 max-w-4xl mx-auto">
  <!-- Header -->
  <div>
    <div class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Documentation</div>
    <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">User Workflow Manual</h1>
    <p class="text-xs sm:text-sm text-slate-400">
      End-to-end guide to the OpenBIM compliance checking workflow in BIM Guard.
    </p>
  </div>

  <!-- Steps List -->
  <div class="space-y-4">
    {#each STEPS as s}
      <div class="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4 hover:border-slate-700 transition-all">
        <div class="flex items-start gap-4">
          <div class="w-10 h-10 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center font-bold text-sm shrink-0 border border-blue-500/20">
            {s.step}
          </div>
          <div class="space-y-1 flex-1">
            <h2 class="text-base font-bold text-white tracking-tight flex items-center gap-2">
              <svelte:component this={s.icon} class="w-4 h-4 text-[#0071e3]" />
              <span>{s.title}</span>
            </h2>
            <p class="text-xs text-slate-300 leading-relaxed">{s.description}</p>
          </div>
        </div>

        <div class="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-xs flex items-center gap-2 text-emerald-400">
          <CheckCircle2 class="w-3.5 h-3.5 shrink-0" />
          <span>{s.result}</span>
        </div>

        <div class="flex items-center gap-2 pt-1">
          {#each s.actions as act}
            <button
              type="button"
              on:click={() => onNavigate(act.view)}
              class="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-semibold transition-all {act.primary ? 'bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm' : 'bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white'}"
            >
              <span>{act.label}</span>
              <ArrowRight class="w-3 h-3" />
            </button>
          {/each}
        </div>
      </div>
    {/each}
  </div>
</div>

