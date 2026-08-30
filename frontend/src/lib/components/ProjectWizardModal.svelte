<script lang="ts">
  import { onMount } from 'svelte';
  import { X, Check, Upload, ArrowRight, ArrowLeft, FileText, CheckCircle2 } from 'lucide-svelte';
  import { projectsApi, documentsApi } from '../api';
  import type { Project, DocumentItem, ProjectOptions } from '../types';

  export let isOpen: boolean = false;
  export let onClose: () => void;
  export let onProjectCreated: (project: Project) => void;

  let currentStep = 1;
  let isSubmitting = false;
  let errorMessage = '';

  // Form State
  let name = '';
  let description = '';
  let status = 'Active';
  let country = 'Canada';
  let analysisType = 'Arch';
  let ifcFile: File | null = null;

  // Step 1 building details. Held as strings because an empty number input
  // yields '', and sending '' is how the wizard says "not answered" — coercing
  // to 0 here would claim the building has no floors.
  let projectType = '';
  let projectSizeSqm = '';
  let buildingsCount = '';
  let floorsCount = '';

  // Available Documents and standards for Step 4
  let documents: DocumentItem[] = [];
  let selectedDocIds: Set<number> = new Set();
  let selectedStandardIds: Set<string> = new Set();

  // Reference lists served by /api/projects/options, so the country and
  // building-type lists live in app/constants.py alone and cannot drift.
  let options: ProjectOptions = {
    countries: [],
    project_types: [],
    analysis_types: [],
    standards: [],
  };

  //: Building code framework shown alongside the chosen jurisdiction. Only the
  //: four jurisdictions with a bundled ruleset are named; everywhere else falls
  //: back to the international standards, which is what the engines apply.
  const CODE_FRAMEWORKS: Record<string, string> = {
    Canada: 'Ontario Building Code Part 9',
    'United Kingdom': 'Building Regulations Part B/M',
    'United States': 'IBC / NFPA',
  };

  $: codeFramework = CODE_FRAMEWORKS[country] || 'ISO / IFC international standards';
  $: standardsForDomain = options.standards.filter(
    (s) => !s.applicable_to?.length || s.applicable_to.includes(analysisType),
  );

  const STEPS = [
    { num: 1, title: 'Details' },
    { num: 2, title: 'IFC Model' },
    { num: 3, title: 'Scope' },
    { num: 4, title: 'Inputs' },
    { num: 5, title: 'Confirm' },
  ];

  onMount(async () => {
    try {
      documents = await documentsApi.list();
    } catch {
      documents = [];
    }
    try {
      options = await projectsApi.options();
    } catch {
      // The wizard stays usable on the four bundled jurisdictions if the
      // options endpoint is unreachable; the selects fall back below.
      options = {
        countries: [],
        project_types: [],
        analysis_types: [],
        standards: [],
      };
    }
  });

  function handleFileChange(event: Event) {
    const target = event.target as HTMLInputElement;
    if (target.files && target.files[0]) {
      ifcFile = target.files[0];
    }
  }

  function toggleDocument(id: number) {
    if (selectedDocIds.has(id)) {
      selectedDocIds.delete(id);
    } else {
      selectedDocIds.add(id);
    }
    selectedDocIds = new Set(selectedDocIds);
  }

  function toggleStandard(id: string) {
    if (selectedStandardIds.has(id)) {
      selectedStandardIds.delete(id);
    } else {
      selectedStandardIds.add(id);
    }
    selectedStandardIds = new Set(selectedStandardIds);
  }

  async function handleFinish() {
    if (!name.trim()) {
      errorMessage = 'Project name is required.';
      currentStep = 1;
      return;
    }

    isSubmitting = true;
    errorMessage = '';

    try {
      const documentIds = Array.from(selectedDocIds);
      const standardsCodes = Array.from(selectedStandardIds);

      let createdProject: Project;
      if (ifcFile) {
        const formData = new FormData();
        formData.append('name', name);
        formData.append('description', description);
        formData.append('status', status);
        formData.append('country', country);
        formData.append('analysis_type', analysisType);
        if (projectType) formData.append('project_type', projectType);
        if (projectSizeSqm) formData.append('project_size_sqm', projectSizeSqm);
        if (buildingsCount) formData.append('buildings_count', buildingsCount);
        if (floorsCount) formData.append('floors_count', floorsCount);
        // Repeated fields, not a JSON blob: FastAPI reads a list[int] Form
        // parameter from one entry per value.
        documentIds.forEach((id) => formData.append('document_ids', String(id)));
        standardsCodes.forEach((id) => formData.append('standards_codes', id));
        formData.append('ifc_file', ifcFile);
        createdProject = await projectsApi.uploadWithIfc(formData);
      } else {
        createdProject = await projectsApi.create({
          name,
          description,
          status,
          country,
          analysis_type: analysisType,
          project_type: projectType || null,
          project_size_sqm: projectSizeSqm ? Number(projectSizeSqm) : null,
          buildings_count: buildingsCount ? Number(buildingsCount) : null,
          floors_count: floorsCount ? Number(floorsCount) : null,
          document_ids: documentIds,
          standards_codes: standardsCodes,
        });
      }

      onProjectCreated(createdProject);
      handleClose();
    } catch (err: any) {
      errorMessage = err.message || 'Failed to complete project setup wizard.';
    } finally {
      isSubmitting = false;
    }
  }

  function handleClose() {
    currentStep = 1;
    name = '';
    description = '';
    status = 'Active';
    country = 'Canada';
    analysisType = 'Piping (Corrosive)';
    ifcFile = null;
    projectType = '';
    projectSizeSqm = '';
    buildingsCount = '';
    floorsCount = '';
    selectedDocIds = new Set();
    selectedStandardIds = new Set();
    errorMessage = '';
    onClose();
  }
</script>

{#if isOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md">
    <div class="bg-slate-900 border border-slate-800 w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden flex flex-col">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
        <div>
          <h2 class="text-lg font-bold text-white tracking-tight">New Project Setup</h2>
          <p class="text-xs text-slate-400">Initialize a new OpenBIM compliance audit project</p>
        </div>
        <button
          type="button"
          on:click={handleClose}
          class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Step Stepper -->
      <div class="px-6 py-3 border-b border-slate-800/80 bg-slate-950/40 flex items-center justify-between">
        {#each STEPS as step, idx}
          <div class="flex items-center gap-2 {idx < STEPS.length - 1 ? 'flex-1' : ''}">
            <div
              class="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-colors {currentStep === step.num ? 'bg-[#0071e3] text-white' : currentStep > step.num ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-400'}"
            >
              {#if currentStep > step.num}
                <Check class="w-3.5 h-3.5" />
              {:else}
                {step.num}
              {/if}
            </div>
            <span class="text-xs font-medium {currentStep === step.num ? 'text-white' : 'text-slate-500'}">
              {step.title}
            </span>
            {#if idx < STEPS.length - 1}
              <div class="h-0.5 flex-1 mx-2 {currentStep > step.num ? 'bg-emerald-600/60' : 'bg-slate-800'}"></div>
            {/if}
          </div>
        {/each}
      </div>

      <!-- Body -->
      <div class="p-6 flex-1 overflow-y-auto max-h-[60vh]">
        {#if errorMessage}
          <div class="mb-4 p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
            {errorMessage}
          </div>
        {/if}

        {#if currentStep === 1}
          <!-- Step 1: Project Details -->
          <div class="space-y-4">
            <div>
              <label for="wizard-name" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Project Name *
              </label>
              <input
                id="wizard-name"
                type="text"
                bind:value={name}
                placeholder="e.g. BIM Headquarters Phase 1"
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
              />
            </div>
            <div>
              <label for="wizard-desc" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Project Description
              </label>
              <textarea
                id="wizard-desc"
                bind:value={description}
                rows="4"
                placeholder="Scope, regulatory framework, and notes..."
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
              ></textarea>
            </div>
            <div>
              <label for="wizard-status" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Lifecycle Status
              </label>
              <select
                id="wizard-status"
                bind:value={status}
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-[#0071e3]"
              >
                <option value="Draft">Draft</option>
                <option value="Active">Active</option>
                <option value="Archived">Archived</option>
              </select>
            </div>

            <div>
              <label for="wizard-location" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Location *
              </label>
              <select
                id="wizard-location"
                bind:value={country}
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-[#0071e3]"
              >
                {#if options.countries.length}
                  {#each options.countries as c}
                    <option value={c}>{c}</option>
                  {/each}
                {:else}
                  <!-- Options endpoint unreachable: the four jurisdictions with
                       a bundled ruleset keep the wizard usable. -->
                  <option value="Canada">Canada</option>
                  <option value="United Kingdom">United Kingdom</option>
                  <option value="United States">United States</option>
                  <option value="International">International</option>
                {/if}
              </select>
              <p class="text-[11px] text-slate-500 mt-1">
                Building code framework: {codeFramework}
              </p>
            </div>

            <div>
              <span class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Project Type
              </span>
              <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {#each options.project_types as type}
                  <button
                    type="button"
                    on:click={() => (projectType = projectType === type ? '' : type)}
                    class="px-2.5 py-2.5 rounded-xl border text-[11px] font-semibold text-left transition-all {projectType ===
                    type
                      ? 'bg-blue-950/40 border-[#0071e3] text-white'
                      : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'}"
                  >
                    {type}
                  </button>
                {/each}
              </div>
              {#if !options.project_types.length}
                <p class="text-[11px] text-slate-500">
                  Building types are unavailable — the project can be created without one.
                </p>
              {/if}
            </div>

            <div class="grid grid-cols-3 gap-3">
              <div>
                <label for="wizard-size" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Size (m²)
                </label>
                <input
                  id="wizard-size"
                  type="number"
                  min="0"
                  step="any"
                  bind:value={projectSizeSqm}
                  placeholder="5000"
                  class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
                />
              </div>
              <div>
                <label for="wizard-buildings" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Buildings
                </label>
                <input
                  id="wizard-buildings"
                  type="number"
                  min="0"
                  step="1"
                  bind:value={buildingsCount}
                  placeholder="1"
                  class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
                />
              </div>
              <div>
                <label for="wizard-floors" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Floors
                </label>
                <input
                  id="wizard-floors"
                  type="number"
                  min="0"
                  step="1"
                  bind:value={floorsCount}
                  placeholder="2"
                  class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
                />
              </div>
            </div>
          </div>

        {:else if currentStep === 2}
          <!-- Step 2: IFC Upload -->
          <div class="space-y-4 text-center">
            <div class="border-2 border-dashed border-slate-700 hover:border-[#0071e3] transition-colors rounded-2xl p-8 bg-slate-950/40">
              <Upload class="w-10 h-10 text-slate-400 mx-auto mb-3" />
              <h3 class="text-sm font-semibold text-white mb-1">Upload OpenBIM IFC Model</h3>
              <p class="text-xs text-slate-400 max-w-sm mx-auto mb-4">
                Attach an IFC 2x3 or IFC4 building/piping model for compliance checks.
              </p>
              <label class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-800 hover:bg-slate-700 text-white text-xs font-medium cursor-pointer transition-colors">
                <span>Browse File (.ifc)</span>
                <input type="file" accept=".ifc" on:change={handleFileChange} class="hidden" />
              </label>
            </div>
            {#if ifcFile}
              <div class="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between text-left">
                <div class="flex items-center gap-2.5 truncate">
                  <CheckCircle2 class="w-4 h-4 text-emerald-400 shrink-0" />
                  <span class="text-xs font-medium text-white truncate">{ifcFile.name}</span>
                  <span class="text-[11px] text-slate-500">({(ifcFile.size / 1024 / 1024).toFixed(2)} MB)</span>
                </div>
                <button
                  type="button"
                  on:click={() => (ifcFile = null)}
                  class="text-xs text-rose-400 hover:text-rose-300 ml-2"
                >
                  Remove
                </button>
              </div>
            {/if}
          </div>

        {:else if currentStep === 3}
          <!-- Step 3: Scope & Jurisdiction -->
          <div class="space-y-4">
            <!-- Jurisdiction is chosen on step 1, where the full country list
                 lives. Shown here read-only so this step still states which
                 code the domain below will be judged against. -->
            <div class="p-3 rounded-xl bg-slate-950 border border-slate-800">
              <div class="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Jurisdiction &amp; Building Code
              </div>
              <div class="text-sm text-white">{country}</div>
              <div class="text-[11px] text-slate-400 mt-0.5">{codeFramework}</div>
              <button
                type="button"
                on:click={() => (currentStep = 1)}
                class="text-[11px] text-[#0071e3] hover:underline mt-1.5"
              >
                Change on step 1
              </button>
            </div>
            <div>
              <label for="wizard-type" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Primary Analysis Domain
              </label>
              <select
                id="wizard-type"
                bind:value={analysisType}
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-[#0071e3]"
              >
                <option value="Arch">Arch — Doors, Egress, Daylight, Stairs</option>
                <option value="Piping">Piping — GC-001, CC-001, MC-001</option>
                <option value="seismic">seismic — Blue Halo Clearance Detection</option>
              </select>
            </div>
          </div>

        {:else if currentStep === 4}
          <!-- Step 4: Reference Specifications -->
          <div class="space-y-3">
            <p class="text-xs text-slate-400 mb-2">
              Select specification documents and standards from the library to link with this project:
            </p>
            {#if documents.length === 0}
              <div class="p-6 rounded-xl border border-slate-800 text-center text-xs text-slate-500">
                No specification documents uploaded yet. You can add them later in the Document Library.
              </div>
            {:else}
              <div class="space-y-2 max-h-56 overflow-y-auto">
                {#each documents as doc}
                  <button
                    type="button"
                    on:click={() => toggleDocument(doc.id)}
                    class="w-full p-3 rounded-xl border flex items-center justify-between text-left transition-all {selectedDocIds.has(doc.id) ? 'bg-blue-950/30 border-[#0071e3]' : 'bg-slate-950 border-slate-800 hover:border-slate-700'}"
                  >
                    <div class="flex items-center gap-2.5 truncate">
                      <FileText class="w-4 h-4 {selectedDocIds.has(doc.id) ? 'text-[#0071e3]' : 'text-slate-500'}" />
                      <div class="truncate">
                        <div class="text-xs font-semibold text-white truncate">{doc.filename}</div>
                        <div class="text-[10px] text-slate-400">{doc.char_count.toLocaleString()} chars extracted</div>
                      </div>
                    </div>
                    <div class="w-4 h-4 rounded-full border flex items-center justify-center {selectedDocIds.has(doc.id) ? 'border-[#0071e3] bg-[#0071e3] text-white' : 'border-slate-700'}">
                      {#if selectedDocIds.has(doc.id)}
                        <Check class="w-3 h-3" />
                      {/if}
                    </div>
                  </button>
                {/each}
              </div>
            {/if}

            <div class="pt-2 border-t border-slate-800">
              <p class="text-xs text-slate-400 mb-2 mt-2">
                Normative standards to evaluate against
                {#if analysisType}
                  <span class="text-slate-500">— relevant to {analysisType}</span>
                {/if}
              </p>
              {#if standardsForDomain.length === 0}
                <div class="p-4 rounded-xl border border-slate-800 text-center text-xs text-slate-500">
                  No bundled standards match this analysis domain.
                </div>
              {:else}
                <div class="space-y-2 max-h-44 overflow-y-auto">
                  {#each standardsForDomain as standard}
                    <button
                      type="button"
                      on:click={() => toggleStandard(standard.id)}
                      class="w-full p-3 rounded-xl border flex items-center justify-between text-left transition-all {selectedStandardIds.has(
                        standard.id,
                      )
                        ? 'bg-blue-950/30 border-[#0071e3]'
                        : 'bg-slate-950 border-slate-800 hover:border-slate-700'}"
                    >
                      <div class="truncate pr-2">
                        <div class="text-xs font-semibold text-white truncate">{standard.name}</div>
                        <div class="text-[10px] text-slate-400 truncate">{standard.domain}</div>
                      </div>
                      <div
                        class="w-4 h-4 rounded-full border flex items-center justify-center shrink-0 {selectedStandardIds.has(
                          standard.id,
                        )
                          ? 'border-[#0071e3] bg-[#0071e3] text-white'
                          : 'border-slate-700'}"
                      >
                        {#if selectedStandardIds.has(standard.id)}
                          <Check class="w-3 h-3" />
                        {/if}
                      </div>
                    </button>
                  {/each}
                </div>
              {/if}
            </div>
          </div>

        {:else if currentStep === 5}
          <!-- Step 5: Summary & Confirm -->
          <div class="space-y-3 text-xs">
            <div class="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div class="flex justify-between py-1 border-b border-slate-800">
                <span class="text-slate-400 font-medium">Project Name:</span>
                <span class="font-semibold text-white">{name}</span>
              </div>
              <div class="flex justify-between py-1 border-b border-slate-800">
                <span class="text-slate-400 font-medium">Status:</span>
                <span class="font-semibold text-white">{status}</span>
              </div>
              <div class="flex justify-between py-1 border-b border-slate-800">
                <span class="text-slate-400 font-medium">Jurisdiction:</span>
                <span class="font-semibold text-white">{country}</span>
              </div>
              <div class="flex justify-between py-1 border-b border-slate-800">
                <span class="text-slate-400 font-medium">Building Type:</span>
                <span class="font-semibold text-white">{projectType || '—'}</span>
              </div>
              <div class="flex justify-between py-1 border-b border-slate-800">
                <span class="text-slate-400 font-medium">Size / Buildings / Floors:</span>
                <span class="font-semibold text-white">
                  {projectSizeSqm ? `${projectSizeSqm} m²` : '—'} · {buildingsCount || '—'} · {floorsCount || '—'}
                </span>
              </div>
              <div class="flex justify-between py-1 border-b border-slate-800">
                <span class="text-slate-400 font-medium">Analysis Domain:</span>
                <span class="font-semibold text-white">{analysisType}</span>
              </div>
              <div class="flex justify-between py-1 border-b border-slate-800">
                <span class="text-slate-400 font-medium">Attached Model:</span>
                <span class="font-semibold text-emerald-400">{ifcFile ? ifcFile.name : 'None (can attach later)'}</span>
              </div>
              <div class="flex justify-between py-1 border-b border-slate-800">
                <span class="text-slate-400 font-medium">Linked Documents:</span>
                <span class="font-semibold text-white">{selectedDocIds.size} selected</span>
              </div>
              <div class="flex justify-between py-1">
                <span class="text-slate-400 font-medium">Linked Standards:</span>
                <span class="font-semibold text-white">{selectedStandardIds.size} selected</span>
              </div>
            </div>
            <p class="text-[11px] text-slate-400">
              Clicking "Create &amp; Launch Audit" will register the project in the repository and prepare the compliance analysis engines.
            </p>
          </div>
        {/if}
      </div>

      <!-- Footer Buttons -->
      <div class="px-6 py-4 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between">
        {#if currentStep > 1}
          <button
            type="button"
            on:click={() => (currentStep -= 1)}
            class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-white transition-colors"
          >
            <ArrowLeft class="w-3.5 h-3.5" />
            <span>Back</span>
          </button>
        {:else}
          <div></div>
        {/if}

        {#if currentStep < 5}
          <button
            type="button"
            on:click={() => {
              if (currentStep === 1 && !name.trim()) {
                errorMessage = 'Please provide a project name.';
                return;
              }
              errorMessage = '';
              currentStep += 1;
            }}
            class="inline-flex items-center gap-1.5 px-5 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all"
          >
            <span>Next Step</span>
            <ArrowRight class="w-3.5 h-3.5" />
          </button>
        {:else}
          <button
            type="button"
            disabled={isSubmitting}
            on:click={handleFinish}
            class="inline-flex items-center gap-1.5 px-6 py-2 rounded-full text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm shadow-emerald-500/20 transition-all disabled:opacity-50"
          >
            <span>{isSubmitting ? 'Creating Project...' : 'Create & Launch Audit'}</span>
            <Check class="w-3.5 h-3.5" />
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

