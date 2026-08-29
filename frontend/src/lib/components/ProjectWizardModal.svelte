<script lang="ts">
  import { onMount } from 'svelte';
  import { X, Check, Upload, ArrowRight, ArrowLeft, FileText, CheckCircle2 } from 'lucide-svelte';
  import { projectsApi, documentsApi } from '../api';
  import type { Project, DocumentItem } from '../types';

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
  let analysisType = 'Piping (Corrosive)';
  let ifcFile: File | null = null;

  // Available Documents for Step 4
  let documents: DocumentItem[] = [];
  let selectedDocIds: Set<number> = new Set();

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

  async function handleFinish() {
    if (!name.trim()) {
      errorMessage = 'Project name is required.';
      currentStep = 1;
      return;
    }

    isSubmitting = true;
    errorMessage = '';

    try {
      let createdProject: Project;
      if (ifcFile) {
        const formData = new FormData();
        formData.append('name', name);
        formData.append('description', description);
        formData.append('status', status);
        formData.append('country', country);
        formData.append('analysis_type', analysisType);
        formData.append('ifc_file', ifcFile);
        createdProject = await projectsApi.uploadWithIfc(formData);
      } else {
        createdProject = await projectsApi.create({
          name,
          description,
          status,
          country,
          analysis_type: analysisType,
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
    selectedDocIds = new Set();
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
          <h2 class="text-lg font-bold text-white tracking-tight">Project Setup Wizard</h2>
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
            <div>
              <label for="wizard-country" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Jurisdiction &amp; Building Code
              </label>
              <select
                id="wizard-country"
                bind:value={country}
                class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-[#0071e3]"
              >
                <option value="Canada">Canada (Ontario Building Code Part 9)</option>
                <option value="United Kingdom">United Kingdom (Building Regulations Part B/M)</option>
                <option value="United States">United States (IBC / NFPA)</option>
                <option value="International">International (ISO / IFC standard)</option>
              </select>
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
                <option value="Piping (Corrosive)">Piping (Corrosive) — GC-001, CC-001, MC-001</option>
                <option value="Halo">Halo — Blue Halo Clearance Detection</option>
                <option value="Architecture">Architecture — Doors, Egress, Daylight, Stairs</option>
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
                <span class="text-slate-400 font-medium">Analysis Domain:</span>
                <span class="font-semibold text-white">{analysisType}</span>
              </div>
              <div class="flex justify-between py-1 border-b border-slate-800">
                <span class="text-slate-400 font-medium">Attached Model:</span>
                <span class="font-semibold text-emerald-400">{ifcFile ? ifcFile.name : 'None (can attach later)'}</span>
              </div>
              <div class="flex justify-between py-1">
                <span class="text-slate-400 font-medium">Linked Documents:</span>
                <span class="font-semibold text-white">{selectedDocIds.size} selected</span>
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

