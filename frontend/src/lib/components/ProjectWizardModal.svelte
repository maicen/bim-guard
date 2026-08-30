<script lang="ts">
  import { onMount } from 'svelte';
  import { X, Check, Upload, ArrowRight, ArrowLeft, FileText, CheckCircle2 } from 'lucide-svelte';
  import { projectsApi, documentsApi } from '../api';
  import { IFC_FILE_ROLES } from '../types';
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
  // Chosen on step 3 rather than step 1: which code governs a model is a
  // question about the audit's scope, and only the Arch domain is judged
  // against one at all.
  let buildingCode = '';
  // A project can carry several discipline models -- an architectural model, a
  // structural one, the site context -- and exactly one of them is primary: the
  // model an analysis run starts from, and the one projects.ifc_file_path keeps
  // naming. ifcRoles is parallel to ifcFiles, and the primary is the entry
  // whose role is PRIMARY_ROLE, so the two can never disagree.
  const PRIMARY_ROLE = 'primary';
  const DEFAULT_ROLE = 'context';
  let ifcFiles: File[] = [];
  let ifcRoles: string[] = [];
  let primaryIndex = 0;
  let isDraggingIfc = false;
  let ifcNotice = '';
  // Set once the project row exists. A failed model upload must not make the
  // retry create a second project, so handleFinish reuses this id if it is set.
  let createdProjectId: number | null = null;

  $: primaryIfcFile = ifcFiles[primaryIndex] ?? null;

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
    building_codes: [],
  };

  // Codes are served for every jurisdiction at once and filtered here, so
  // changing the jurisdiction on step 1 re-scopes step 3 without a round trip.
  // An entry with no jurisdictions applies everywhere -- that is the ISO/IFC
  // fallback for the jurisdictions with no bundled national code.
  $: buildingCodesForJurisdiction = (options.building_codes || []).filter(
    (c) => !c.jurisdictions?.length || c.jurisdictions.includes(country),
  );
  // A code chosen for one jurisdiction must not survive a move to another:
  // clearing it is better than quietly auditing an Ontario model against the IBC.
  $: if (buildingCode && !buildingCodesForJurisdiction.some((c) => c.id === buildingCode)) {
    buildingCode = '';
  }
  $: selectedBuildingCode = buildingCodesForJurisdiction.find((c) => c.id === buildingCode) || null;
  $: buildingCodeRequired = analysisType === 'Arch';
  // Named so the confirm step can say which analysis page the button opens.
  $: analysisDomainLabel =
    analysisType === 'Piping' ? 'Piping' : analysisType === 'seismic' ? 'Seismic' : 'Architectural';
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
        building_codes: [],
      };
    }
  });

  /** Add .ifc files, skipping non-IFC uploads and ones already in the list. */
  function addIfcFiles(incoming: FileList | null | undefined) {
    const candidates = Array.from(incoming ?? []);
    if (!candidates.length) return;

    const accepted = candidates.filter((file) => /\.ifc$/i.test(file.name));
    const rejectedCount = candidates.length - accepted.length;

    const mergedFiles = [...ifcFiles];
    const mergedRoles = [...ifcRoles];
    let duplicateCount = 0;
    for (const file of accepted) {
      const isDuplicate = mergedFiles.some(
        (existing) => existing.name === file.name && existing.size === file.size,
      );
      if (isDuplicate) {
        duplicateCount += 1;
        continue;
      }
      mergedFiles.push(file);
      // The first model attached is the primary; anything added after it is
      // context until the user says otherwise.
      mergedRoles.push(mergedFiles.length === 1 ? PRIMARY_ROLE : DEFAULT_ROLE);
    }
    ifcFiles = mergedFiles;
    ifcRoles = mergedRoles;
    if (primaryIndex >= ifcFiles.length) primaryIndex = 0;
    if (ifcFiles.length) setPrimaryIfc(primaryIndex);

    const notices: string[] = [];
    if (rejectedCount) {
      notices.push(`${rejectedCount} file${rejectedCount === 1 ? '' : 's'} skipped — only .ifc models are accepted.`);
    }
    if (duplicateCount) {
      notices.push(`${duplicateCount} file${duplicateCount === 1 ? '' : 's'} already in the list.`);
    }
    ifcNotice = notices.join(' ');
  }

  function handleFileChange(event: Event) {
    const target = event.target as HTMLInputElement;
    addIfcFiles(target.files);
    // Cleared so re-picking the same file after removing it still fires change.
    target.value = '';
  }

  function handleIfcDrop(event: DragEvent) {
    isDraggingIfc = false;
    addIfcFiles(event.dataTransfer?.files);
  }

  function handleIfcDragLeave(event: DragEvent) {
    // Moving onto a child fires dragleave on the zone; only unhighlight once
    // the pointer has actually left the drop zone's subtree.
    const zone = event.currentTarget as HTMLElement;
    const next = event.relatedTarget as Node | null;
    if (next && zone.contains(next)) return;
    isDraggingIfc = false;
  }

  function removeIfcFile(index: number) {
    const wasPrimary = index === primaryIndex;
    ifcFiles = ifcFiles.filter((_, idx) => idx !== index);
    ifcRoles = ifcRoles.filter((_, idx) => idx !== index);
    if (!ifcFiles.length) {
      primaryIndex = 0;
    } else if (wasPrimary) {
      // Removing the primary leaves a set with none; the first model takes over
      // rather than the project going to the server with primary_index dangling.
      setPrimaryIfc(0);
    } else if (index < primaryIndex) {
      primaryIndex -= 1;
    }
    ifcNotice = '';
  }

  /** Make one model the primary, demoting whichever held the role before. */
  function setPrimaryIfc(index: number) {
    if (index < 0 || index >= ifcFiles.length) return;
    ifcRoles = ifcRoles.map((role, idx) => {
      if (idx === index) return PRIMARY_ROLE;
      return role === PRIMARY_ROLE ? DEFAULT_ROLE : role;
    });
    primaryIndex = index;
    ifcNotice = '';
  }

  /**
   * Apply a role chosen from one file's dropdown.
   *
   * Returns false when the change was refused, which the caller uses to snap
   * the select back to the role the file actually still has.
   */
  function setIfcRole(index: number, role: string): boolean {
    if (role === PRIMARY_ROLE) {
      setPrimaryIfc(index);
      return true;
    }
    if (index === primaryIndex) {
      const successor = ifcFiles.findIndex((_, idx) => idx !== index);
      if (successor === -1) {
        ifcNotice = 'The only attached model has to be the primary one.';
        return false;
      }
      const next = [...ifcRoles];
      next[index] = role;
      ifcRoles = next;
      setPrimaryIfc(successor);
      return true;
    }
    const next = [...ifcRoles];
    next[index] = role;
    ifcRoles = next;
    return true;
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

      // Create first, attach after: the multi-model endpoint attaches to a
      // project that already exists, so the single-shot multipart create is no
      // longer the path a model takes into a project.
      let createdProject: Project =
        createdProjectId !== null
          ? await projectsApi.get(createdProjectId)
          : await projectsApi.create({
              name,
              description,
              status,
              country,
              analysis_type: analysisType,
              building_code: buildingCode || null,
              project_type: projectType || null,
              project_size_sqm: projectSizeSqm ? Number(projectSizeSqm) : null,
              buildings_count: buildingsCount ? Number(buildingsCount) : null,
              floors_count: floorsCount ? Number(floorsCount) : null,
              document_ids: documentIds,
              standards_codes: standardsCodes,
            });
      createdProjectId = createdProject.id;

      if (ifcFiles.length) {
        try {
          await projectsApi.uploadIfcFiles(createdProject.id, ifcFiles, primaryIndex, ifcRoles);
        } catch (uploadErr: any) {
          // The project row is already saved. Reporting that plainly and
          // staying open is better than closing on an error the user would
          // then try to fix by creating the project a second time.
          errorMessage =
            `Project "${name}" was saved, but attaching the models failed: ` +
            `${uploadErr.message || 'unknown error'}. Adjust the selection and press ` +
            `Create again — the models will attach to the project that already exists.`;
          currentStep = 2;
          return;
        }
        // The primary is mirrored onto projects.ifc_file_path server-side, so
        // the row fetched before the upload names no model yet.
        createdProject = await projectsApi.get(createdProject.id, { forceRefresh: true });
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
    // Back to the same domain the wizard opens on. Resetting to a legacy alias
    // left the step-3 select matching no option, so a second project could be
    // created against a domain the user was never shown.
    analysisType = 'Arch';
    buildingCode = '';
    ifcFiles = [];
    ifcRoles = [];
    primaryIndex = 0;
    isDraggingIfc = false;
    ifcNotice = '';
    createdProjectId = null;
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
              <label for="wizard-jurisdiction" class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Jurisdiction *
              </label>
              <select
                id="wizard-jurisdiction"
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
                Required for Architectural compliance checks; optional for Piping corrosion analysis.
                The building code is chosen on step 3, from the codes this jurisdiction publishes.
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
          <div class="space-y-4">
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <div
              role="region"
              aria-label="IFC model drop zone"
              on:dragover|preventDefault={() => (isDraggingIfc = true)}
              on:dragleave={handleIfcDragLeave}
              on:drop|preventDefault={handleIfcDrop}
              class="border-2 border-dashed rounded-2xl p-8 text-center transition-colors {isDraggingIfc
                ? 'border-[#0071e3] bg-blue-950/20'
                : 'border-slate-700 hover:border-[#0071e3] bg-slate-950/40'}"
            >
              <Upload class="w-10 h-10 {isDraggingIfc ? 'text-[#0071e3]' : 'text-slate-400'} mx-auto mb-3" />
              <h3 class="text-sm font-semibold text-white mb-1">Upload OpenBIM IFC Models</h3>
              <p class="text-xs text-slate-400 max-w-sm mx-auto mb-4">
                Drag and drop IFC 2x3 or IFC4 models here, or browse. Attach one model per
                discipline — the primary is the one the compliance run analyses.
              </p>
              <label class="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-800 hover:bg-slate-700 text-white text-xs font-medium cursor-pointer transition-colors">
                <span>Browse Files (.ifc)</span>
                <input type="file" accept=".ifc" multiple on:change={handleFileChange} class="hidden" />
              </label>
            </div>

            {#if ifcNotice}
              <p class="text-[11px] text-amber-400">{ifcNotice}</p>
            {/if}

            {#if ifcFiles.length}
              <div class="flex items-center justify-between">
                <span class="text-xs text-slate-400">
                  {ifcFiles.length} model{ifcFiles.length === 1 ? '' : 's'} selected
                </span>
                {#if ifcFiles.length > 1}
                  <span class="text-[11px] text-slate-500">Click a model to make it primary</span>
                {/if}
              </div>

              <div class="space-y-2 max-h-64 overflow-y-auto">
                {#each ifcFiles as file, idx (`${file.name}:${file.size}`)}
                  <div
                    class="p-3 rounded-xl border flex items-center gap-2 transition-all {idx === primaryIndex
                      ? 'bg-blue-950/30 border-[#0071e3]'
                      : 'bg-slate-950 border-slate-800'}"
                  >
                    <button
                      type="button"
                      on:click={() => setPrimaryIfc(idx)}
                      title="Make this the primary model"
                      class="flex items-center gap-2.5 flex-1 min-w-0 text-left"
                    >
                      <CheckCircle2
                        class="w-4 h-4 shrink-0 {idx === primaryIndex ? 'text-[#0071e3]' : 'text-emerald-400'}"
                      />
                      <span class="text-xs font-medium text-white truncate">{file.name}</span>
                      <span class="text-[11px] text-slate-500 shrink-0">
                        ({(file.size / 1024 / 1024).toFixed(2)} MB)
                      </span>
                      {#if idx === primaryIndex}
                        <span
                          class="px-1.5 py-0.5 rounded-md bg-[#0071e3] text-white text-[10px] font-semibold uppercase tracking-wide shrink-0"
                        >
                          Primary
                        </span>
                      {/if}
                    </button>

                    <select
                      aria-label="Role for {file.name}"
                      value={ifcRoles[idx]}
                      on:change={(event) => {
                        const select = event.currentTarget;
                        if (!setIfcRole(idx, select.value)) select.value = ifcRoles[idx];
                      }}
                      class="shrink-0 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-[11px] text-white focus:outline-none focus:border-[#0071e3]"
                    >
                      {#each IFC_FILE_ROLES as roleOption}
                        <option value={roleOption}>{roleOption}</option>
                      {/each}
                    </select>

                    <button
                      type="button"
                      on:click={() => removeIfcFile(idx)}
                      class="shrink-0 text-xs text-rose-400 hover:text-rose-300"
                    >
                      Remove
                    </button>
                  </div>
                {/each}
              </div>
            {/if}
          </div>

        {:else if currentStep === 3}
          <!-- Step 3: Scope -->
          <div class="space-y-4">
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
              <p class="text-[11px] text-slate-500 mt-1">
                Determines which analysis page opens once the project is created.
              </p>
            </div>

            <!-- Specifications: the code the model is judged against. Filtered
                 by the jurisdiction chosen on step 1, and only asked for here
                 because it is the analysis domain above that decides whether it
                 matters at all. -->
            <div class="pt-3 border-t border-slate-800">
              <span class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Specifications
              </span>
              <label for="wizard-building-code" class="block text-[11px] font-medium text-slate-400 mb-1.5">
                Building Code — {country}
              </label>
              {#if buildingCodesForJurisdiction.length === 0}
                <div class="p-3 rounded-xl border border-slate-800 text-[11px] text-slate-500">
                  Building codes are unavailable — the project can be created without one and the
                  engines will apply the ISO / IFC international standards.
                </div>
              {:else}
                <select
                  id="wizard-building-code"
                  bind:value={buildingCode}
                  class="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-[#0071e3]"
                >
                  <option value="">Not specified</option>
                  {#each buildingCodesForJurisdiction as code}
                    <option value={code.id}>{code.name}</option>
                  {/each}
                </select>
                {#if selectedBuildingCode}
                  <p class="text-[11px] text-slate-500 mt-1">
                    {selectedBuildingCode.description}
                    {#if selectedBuildingCode.ruleset_id}
                      <span class="text-slate-400">Ruleset: <span class="font-mono">{selectedBuildingCode.ruleset_id}</span>.</span>
                    {/if}
                  </p>
                {:else if buildingCodeRequired}
                  <p class="text-[11px] text-amber-400/80 mt-1">
                    Architectural checks are judged against a code — without one the audit falls back
                    to the ISO / IFC international standards.
                  </p>
                {:else}
                  <p class="text-[11px] text-slate-500 mt-1">
                    Optional for {analysisType}: corrosion and clearance checks are judged against
                    material and geometry rules, not a jurisdiction's code.
                  </p>
                {/if}
              {/if}
              <button
                type="button"
                on:click={() => (currentStep = 1)}
                class="text-[11px] text-[#0071e3] hover:underline mt-2"
              >
                Change jurisdiction on step 1
              </button>
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
                <span class="text-slate-400 font-medium">Building Code:</span>
                <span class="font-semibold text-white">{selectedBuildingCode?.name || 'Not specified'}</span>
              </div>
              <div class="flex justify-between py-1 border-b border-slate-800">
                <span class="text-slate-400 font-medium">Analysis Domain:</span>
                <span class="font-semibold text-white">{analysisType}</span>
              </div>
              <div class="flex justify-between py-1 border-b border-slate-800">
                <span class="text-slate-400 font-medium">Attached Models:</span>
                <span class="font-semibold text-emerald-400">
                  {#if primaryIfcFile}
                    {primaryIfcFile.name}{ifcFiles.length > 1
                      ? ` + ${ifcFiles.length - 1} more`
                      : ''}
                  {:else}
                    None (can attach later)
                  {/if}
                </span>
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
              Clicking "Create &amp; Launch Audit" saves the project, closes this wizard and opens the
              <span class="text-slate-200 font-semibold">{analysisDomainLabel}</span> analysis page with it selected.
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
            <span>{isSubmitting ? 'Creating & launching...' : 'Create & Launch Audit'}</span>
            <Check class="w-3.5 h-3.5" />
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

