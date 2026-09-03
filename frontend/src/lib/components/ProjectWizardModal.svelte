<script lang="ts">
  import { run, preventDefault } from "svelte/legacy";

  import { onMount } from "svelte";
  import { X, Check, Upload, ArrowRight, ArrowLeft, FileText, CheckCircle2 } from "lucide-svelte";
  import { projectsApi, documentsApi, namingConfigApi } from "../api";
  import { IFC_FILE_ROLES } from "../types";
  import type { Project, DocumentItem, ProjectOptions, NamingConfigPayload } from "../types";
  import NamingConfigStep from "./NamingConfigStep.svelte";

  interface Props {
    isOpen?: boolean;
    onClose: () => void;
    onProjectCreated: (project: Project) => void;
  }

  let { isOpen = false, onClose, onProjectCreated }: Props = $props();

  let currentStep = $state(1);
  let isSubmitting = $state(false);
  let errorMessage = $state("");

  // Form State
  let name = $state("");
  let description = $state("");
  let status = $state("Active");
  let country = $state("Canada");
  let analysisType = $state("Arch");
  // Chosen on step 3 rather than step 1: which code governs a model is a
  // question about the audit's scope, and only the Arch domain is judged
  // against one at all.
  let buildingCode = $state("");
  // A project can carry several discipline models -- an architectural model, a
  // structural one, the site context -- and exactly one of them is primary: the
  // model an analysis run starts from, and the one projects.ifc_file_path keeps
  // naming. ifcRoles is parallel to ifcFiles, and the primary is the entry
  // whose role is PRIMARY_ROLE, so the two can never disagree.
  const PRIMARY_ROLE = "primary";
  const DEFAULT_ROLE = "context";
  let ifcFiles: File[] = $state([]);
  let ifcRoles: string[] = $state([]);
  let primaryIndex = $state(0);
  let isDraggingIfc = $state(false);
  let ifcNotice = $state("");
  // Set once the project row exists. A failed model upload must not make the
  // retry create a second project, so handleFinish reuses this id if it is set.
  let createdProjectId: number | null = null;

  let primaryIfcFile = $derived(ifcFiles[primaryIndex] ?? null);

  // Step 1 building details. Held as strings because an empty number input
  // yields '', and sending '' is how the wizard says "not answered" — coercing
  // to 0 here would claim the building has no floors.
  let projectType = $state("");
  let projectSizeSqm = $state("");
  let buildingsCount = $state("");
  let floorsCount = $state("");

  // ISO 19650 naming, edited on step 3. The project row does not exist until
  // the final step, so this is held here and written once it does -- there is
  // no project to PUT it against while the step is on screen.
  const NAMING_DEFAULTS: NamingConfigPayload = {
    project_code: "",
    originator_code: "",
    type_code: "CO",
    suitability: "S1",
    revision: "01",
    separator: "_",
    date_format: "YYMMDD",
    class_a: "",
    class_b: "",
    active_convention: "iso19650_date",
    level_codes: [],
    type_codes: [],
    discipline_codes: [],
    volume_codes: [],
    custom_conventions: [],
  };
  let namingConfig: NamingConfigPayload = $state({ ...NAMING_DEFAULTS });
  // A project is only given a naming row if the user actually filled the step
  // in. Writing the untouched defaults would make every project claim a naming
  // setup it never chose, and is_configured would stop meaning anything.
  let namingConfigTouched = $derived(
    JSON.stringify(namingConfig) !== JSON.stringify(NAMING_DEFAULTS),
  );

  // Available Documents and standards for Step 5
  let documents: DocumentItem[] = $state([]);
  let selectedDocIds: Set<number> = $state(new Set());
  let selectedStandardIds: Set<string> = $state(new Set());

  // Reference lists served by /api/projects/options, so the country and
  // building-type lists live in app/constants.py alone and cannot drift.
  let options: ProjectOptions = $state({
    countries: [],
    project_types: [],
    analysis_types: [],
    standards: [],
    building_codes: [],
  });

  // Codes are served for every jurisdiction at once and filtered here, so
  // changing the jurisdiction on step 1 re-scopes step 3 without a round trip.
  // An entry with no jurisdictions applies everywhere -- that is the ISO/IFC
  // fallback for the jurisdictions with no bundled national code.
  let buildingCodesForJurisdiction = $derived(
    (options.building_codes || []).filter(
      (c) => !c.jurisdictions?.length || c.jurisdictions.includes(country),
    ),
  );
  // A code chosen for one jurisdiction must not survive a move to another:
  // clearing it is better than quietly auditing an Ontario model against the IBC.
  run(() => {
    if (buildingCode && !buildingCodesForJurisdiction.some((c) => c.id === buildingCode)) {
      buildingCode = "";
    }
  });
  let selectedBuildingCode = $derived(
    buildingCodesForJurisdiction.find((c) => c.id === buildingCode) || null,
  );
  let buildingCodeRequired = $derived(analysisType === "Arch");
  // Named so the confirm step can say which analysis page the button opens.
  let analysisDomainLabel = $derived(
    analysisType === "Piping" ? "Piping" : analysisType === "seismic" ? "Seismic" : "Architectural",
  );
  let standardsForDomain = $derived(
    options.standards.filter(
      (s) => !s.applicable_to?.length || s.applicable_to.includes(analysisType),
    ),
  );

  const STEPS = [
    { num: 1, title: "Details" },
    { num: 2, title: "IFC Model" },
    { num: 3, title: "Naming" },
    { num: 4, title: "Scope" },
    { num: 5, title: "Inputs" },
    { num: 6, title: "Confirm" },
  ];
  const LAST_STEP = STEPS.length;

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
      notices.push(
        `${rejectedCount} file${rejectedCount === 1 ? "" : "s"} skipped — only .ifc models are accepted.`,
      );
    }
    if (duplicateCount) {
      notices.push(`${duplicateCount} file${duplicateCount === 1 ? "" : "s"} already in the list.`);
    }
    ifcNotice = notices.join(" ");
  }

  function handleFileChange(event: Event) {
    const target = event.target as HTMLInputElement;
    addIfcFiles(target.files);
    // Cleared so re-picking the same file after removing it still fires change.
    target.value = "";
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
    ifcNotice = "";
  }

  /** Make one model the primary, demoting whichever held the role before. */
  function setPrimaryIfc(index: number) {
    if (index < 0 || index >= ifcFiles.length) return;
    ifcRoles = ifcRoles.map((role, idx) => {
      if (idx === index) return PRIMARY_ROLE;
      return role === PRIMARY_ROLE ? DEFAULT_ROLE : role;
    });
    primaryIndex = index;
    ifcNotice = "";
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
        ifcNotice = "The only attached model has to be the primary one.";
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

  function goToStep(stepNum: number) {
    if (stepNum === currentStep) return;
    if (stepNum > 1 && !name.trim()) {
      errorMessage = "Please provide a project name first.";
      currentStep = 1;
      return;
    }
    errorMessage = "";
    currentStep = stepNum;
  }

  async function handleFinish() {
    if (!name.trim()) {
      errorMessage = "Project name is required.";
      currentStep = 1;
      return;
    }

    isSubmitting = true;
    errorMessage = "";

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
            `${uploadErr.message || "unknown error"}. Adjust the selection and press ` +
            `Create again — the models will attach to the project that already exists.`;
          currentStep = 2;
          return;
        }
        // The primary is mirrored onto projects.ifc_file_path server-side, so
        // the row fetched before the upload names no model yet.
        createdProject = await projectsApi.get(createdProject.id, { forceRefresh: true });
      }

      if (namingConfigTouched) {
        try {
          await namingConfigApi.save(createdProject.id, namingConfig);
        } catch (namingErr: any) {
          // Non-fatal on purpose. The project and its models are saved; a
          // naming setup that failed to write is recoverable from the project's
          // own settings, and failing here would strand work already done.
          console.warn("Naming configuration was not saved:", namingErr);
        }
      }

      onProjectCreated(createdProject);
      handleClose();
    } catch (err: any) {
      errorMessage = err.message || "Failed to complete project setup wizard.";
    } finally {
      isSubmitting = false;
    }
  }

  function handleClose() {
    currentStep = 1;
    name = "";
    description = "";
    status = "Active";
    country = "Canada";
    // Back to the same domain the wizard opens on. Resetting to a legacy alias
    // left the step-3 select matching no option, so a second project could be
    // created against a domain the user was never shown.
    analysisType = "Arch";
    buildingCode = "";
    ifcFiles = [];
    ifcRoles = [];
    primaryIndex = 0;
    isDraggingIfc = false;
    ifcNotice = "";
    namingConfig = { ...NAMING_DEFAULTS };
    createdProjectId = null;
    projectType = "";
    projectSizeSqm = "";
    buildingsCount = "";
    floorsCount = "";
    selectedDocIds = new Set();
    selectedStandardIds = new Set();
    errorMessage = "";
    onClose();
  }
</script>

{#if isOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div>
          <h2 class="text-lg font-bold tracking-tight text-slate-50">New Project Setup</h2>
          <p class="text-xs text-slate-400">Initialize a new OpenBIM compliance audit project</p>
        </div>
        <button
          type="button"
          onclick={handleClose}
          class="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <!-- Step Stepper -->
      <nav
        aria-label="Project setup steps"
        class="flex items-center justify-between border-b border-slate-800/80 bg-slate-950/40 px-6 py-3"
      >
        {#each STEPS as step, idx}
          <div class="flex items-center gap-2 {idx < STEPS.length - 1 ? 'flex-1' : ''}">
            <button
              type="button"
              onclick={() => goToStep(step.num)}
              class="group flex cursor-pointer items-center gap-2 rounded-lg p-1 text-left transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              title="Go to step {step.num}: {step.title}"
            >
              <div
                class="flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold transition-all duration-200 {currentStep ===
                step.num
                  ? 'scale-105 bg-accent text-white shadow-sm shadow-blue-500/50'
                  : currentStep > step.num
                    ? 'bg-emerald-600 text-white group-hover:bg-emerald-500'
                    : 'bg-slate-800 text-slate-400 group-hover:bg-slate-700 group-hover:text-slate-200'}"
              >
                {#if currentStep > step.num}
                  <Check class="h-3.5 w-3.5" />
                {:else}
                  {step.num}
                {/if}
              </div>
              <span
                class="text-xs font-medium transition-colors {currentStep === step.num
                  ? 'font-semibold text-slate-50'
                  : currentStep > step.num
                    ? 'text-slate-300 group-hover:text-slate-50'
                    : 'text-slate-500 group-hover:text-slate-300'}"
              >
                {step.title}
              </span>
            </button>
            {#if idx < STEPS.length - 1}
              <div
                class="mx-2 h-0.5 flex-1 {currentStep > step.num
                  ? 'bg-emerald-600/60'
                  : 'bg-slate-800'}"
              ></div>
            {/if}
          </div>
        {/each}
      </nav>

      <!-- Body -->
      <div class="max-h-[60vh] flex-1 overflow-y-auto p-6">
        {#if errorMessage}
          <div
            class="mb-4 rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300"
          >
            {errorMessage}
          </div>
        {/if}

        {#if currentStep === 1}
          <!-- Step 1: Project Details -->
          <div class="space-y-4">
            <div>
              <label
                for="wizard-name"
                class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300"
              >
                Project Name *
              </label>
              <input
                id="wizard-name"
                type="text"
                bind:value={name}
                placeholder="e.g. BIM Headquarters Phase 1"
                class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-sm text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label
                for="wizard-desc"
                class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300"
              >
                Project Description
              </label>
              <textarea
                id="wizard-desc"
                bind:value={description}
                rows="4"
                placeholder="Scope, regulatory framework, and notes..."
                class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-sm text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
              ></textarea>
            </div>
            <div>
              <label
                for="wizard-status"
                class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300"
              >
                Lifecycle Status
              </label>
              <select
                id="wizard-status"
                bind:value={status}
                class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-50 focus:border-accent focus:outline-none"
              >
                <option value="Draft">Draft</option>
                <option value="Active">Active</option>
                <option value="Archived">Archived</option>
              </select>
            </div>

            <div>
              <label
                for="wizard-jurisdiction"
                class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300"
              >
                Jurisdiction *
              </label>
              <select
                id="wizard-jurisdiction"
                bind:value={country}
                class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-50 focus:border-accent focus:outline-none"
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
              <p class="mt-1 text-caption text-slate-500">
                Required for Architectural compliance checks; optional for Piping corrosion
                analysis. The building code is chosen on step 3, from the codes this jurisdiction
                publishes.
              </p>
            </div>

            <div>
              <span
                class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300"
              >
                Project Type
              </span>
              <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {#each options.project_types as type}
                  <button
                    type="button"
                    onclick={() => (projectType = projectType === type ? "" : type)}
                    class="rounded-xl border px-2.5 py-2.5 text-left text-caption font-semibold transition-all {projectType ===
                    type
                      ? 'border-accent bg-blue-950/40 text-slate-50'
                      : 'border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700'}"
                  >
                    {type}
                  </button>
                {/each}
              </div>
              {#if !options.project_types.length}
                <p class="text-caption text-slate-500">
                  Building types are unavailable — the project can be created without one.
                </p>
              {/if}
            </div>

            <div class="grid grid-cols-3 gap-3">
              <div>
                <label
                  for="wizard-size"
                  class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300"
                >
                  Size (m²)
                </label>
                <input
                  id="wizard-size"
                  type="number"
                  min="0"
                  step="any"
                  bind:value={projectSizeSqm}
                  placeholder="5000"
                  class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-sm text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
                />
              </div>
              <div>
                <label
                  for="wizard-buildings"
                  class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300"
                >
                  Buildings
                </label>
                <input
                  id="wizard-buildings"
                  type="number"
                  min="0"
                  step="1"
                  bind:value={buildingsCount}
                  placeholder="1"
                  class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-sm text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
                />
              </div>
              <div>
                <label
                  for="wizard-floors"
                  class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300"
                >
                  Floors
                </label>
                <input
                  id="wizard-floors"
                  type="number"
                  min="0"
                  step="1"
                  bind:value={floorsCount}
                  placeholder="2"
                  class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-sm text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
                />
              </div>
            </div>
          </div>
        {:else if currentStep === 2}
          <!-- Step 2: IFC Upload -->
          <div class="space-y-4">
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div
              role="region"
              aria-label="IFC model drop zone"
              ondragover={preventDefault(() => (isDraggingIfc = true))}
              ondragleave={handleIfcDragLeave}
              ondrop={preventDefault(handleIfcDrop)}
              class="rounded-2xl border-2 border-dashed p-8 text-center transition-colors {isDraggingIfc
                ? 'border-accent bg-blue-950/20'
                : 'border-slate-700 bg-slate-950/40 hover:border-accent'}"
            >
              <Upload
                class="h-10 w-10 {isDraggingIfc ? 'text-accent' : 'text-slate-400'} mx-auto mb-3"
              />
              <h3 class="mb-1 text-sm font-semibold text-slate-50">Upload OpenBIM IFC Models</h3>
              <p class="mx-auto mb-4 max-w-sm text-xs text-slate-400">
                Drag and drop IFC 2x3 or IFC4 models here, or browse. Attach one model per
                discipline — the primary is the one the compliance run analyses.
              </p>
              <label
                class="inline-flex cursor-pointer items-center gap-2 rounded-full bg-slate-800 px-4 py-2 text-xs font-medium text-slate-50 transition-colors hover:bg-slate-700"
              >
                <span>Browse Files (.ifc)</span>
                <input
                  type="file"
                  accept=".ifc"
                  multiple
                  onchange={handleFileChange}
                  class="hidden"
                />
              </label>
            </div>

            {#if ifcNotice}
              <p class="text-caption text-amber-400">{ifcNotice}</p>
            {/if}

            {#if ifcFiles.length}
              <div class="flex items-center justify-between">
                <span class="text-xs text-slate-400">
                  {ifcFiles.length} model{ifcFiles.length === 1 ? "" : "s"} selected
                </span>
                {#if ifcFiles.length > 1}
                  <span class="text-caption text-slate-500">Click a model to make it primary</span>
                {/if}
              </div>

              <div class="max-h-64 space-y-2 overflow-y-auto">
                {#each ifcFiles as file, idx (`${file.name}:${file.size}`)}
                  <div
                    class="flex items-center gap-2 rounded-xl border p-3 transition-all {idx ===
                    primaryIndex
                      ? 'border-accent bg-blue-950/30'
                      : 'border-slate-800 bg-slate-950'}"
                  >
                    <button
                      type="button"
                      onclick={() => setPrimaryIfc(idx)}
                      title="Make this the primary model"
                      class="flex min-w-0 flex-1 items-center gap-2.5 text-left"
                    >
                      <CheckCircle2
                        class="h-4 w-4 shrink-0 {idx === primaryIndex
                          ? 'text-accent'
                          : 'text-emerald-400'}"
                      />
                      <span class="truncate text-xs font-medium text-slate-50">{file.name}</span>
                      <span class="shrink-0 text-caption text-slate-500">
                        ({(file.size / 1024 / 1024).toFixed(2)} MB)
                      </span>
                      {#if idx === primaryIndex}
                        <span
                          class="shrink-0 rounded-md bg-accent px-1.5 py-0.5 text-micro font-semibold uppercase tracking-wide text-white"
                        >
                          Primary
                        </span>
                      {/if}
                    </button>

                    <select
                      aria-label="Role for {file.name}"
                      value={ifcRoles[idx]}
                      onchange={(event) => {
                        const select = event.currentTarget;
                        if (!setIfcRole(idx, select.value)) select.value = ifcRoles[idx];
                      }}
                      class="shrink-0 rounded-lg border border-slate-800 bg-slate-900 px-2 py-1 text-caption text-slate-50 focus:border-accent focus:outline-none"
                    >
                      {#each IFC_FILE_ROLES as roleOption}
                        <option value={roleOption}>{roleOption}</option>
                      {/each}
                    </select>

                    <button
                      type="button"
                      onclick={() => removeIfcFile(idx)}
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
          <!-- Step 3: ISO 19650 Naming -->
          <NamingConfigStep bind:config={namingConfig} />
        {:else if currentStep === 4}
          <!-- Step 4: Scope -->
          <div class="space-y-4">
            <div>
              <label
                for="wizard-type"
                class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300"
              >
                Primary Analysis Domain
              </label>
              <select
                id="wizard-type"
                bind:value={analysisType}
                class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-50 focus:border-accent focus:outline-none"
              >
                <option value="Arch">Arch — Doors, Egress, Daylight, Stairs</option>
                <option value="Piping">Piping — GC-001, CC-001, MC-001</option>
                <option value="seismic">seismic — Blue Halo Clearance Detection</option>
              </select>
              <p class="mt-1 text-caption text-slate-500">
                Determines which analysis page opens once the project is created.
              </p>
            </div>

            <!-- Specifications: the code the model is judged against. Filtered
                 by the jurisdiction chosen on step 1, and only asked for here
                 because it is the analysis domain above that decides whether it
                 matters at all. -->
            <div class="border-t border-slate-800 pt-3">
              <span
                class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-300"
              >
                Specifications
              </span>
              <label
                for="wizard-building-code"
                class="mb-1.5 block text-caption font-medium text-slate-400"
              >
                Building Code — {country}
              </label>
              {#if buildingCodesForJurisdiction.length === 0}
                <div class="rounded-xl border border-slate-800 p-3 text-caption text-slate-500">
                  Building codes are unavailable — the project can be created without one and the
                  engines will apply the ISO / IFC international standards.
                </div>
              {:else}
                <select
                  id="wizard-building-code"
                  bind:value={buildingCode}
                  class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-50 focus:border-accent focus:outline-none"
                >
                  <option value="">Not specified</option>
                  {#each buildingCodesForJurisdiction as code}
                    <option value={code.id}>{code.name}</option>
                  {/each}
                </select>
                {#if selectedBuildingCode}
                  <p class="mt-1 text-caption text-slate-500">
                    {selectedBuildingCode.description}
                    {#if selectedBuildingCode.ruleset_id}
                      <span class="text-slate-400"
                        >Ruleset: <span class="font-mono">{selectedBuildingCode.ruleset_id}</span
                        >.</span
                      >
                    {/if}
                  </p>
                {:else if buildingCodeRequired}
                  <p class="mt-1 text-caption text-amber-400/80">
                    Architectural checks are judged against a code — without one the audit falls
                    back to the ISO / IFC international standards.
                  </p>
                {:else}
                  <p class="mt-1 text-caption text-slate-500">
                    Optional for {analysisType}: corrosion and clearance checks are judged against
                    material and geometry rules, not a jurisdiction's code.
                  </p>
                {/if}
              {/if}
              <button
                type="button"
                onclick={() => (currentStep = 1)}
                class="mt-2 text-caption text-accent hover:underline"
              >
                Change jurisdiction on step 1
              </button>
            </div>
          </div>
        {:else if currentStep === 5}
          <!-- Step 5: Reference Specifications -->
          <div class="space-y-3">
            <p class="mb-2 text-xs text-slate-400">
              Select specification documents and standards from the library to link with this
              project:
            </p>
            {#if documents.length === 0}
              <div
                class="rounded-xl border border-slate-800 p-6 text-center text-xs text-slate-500"
              >
                No specification documents uploaded yet. You can add them later in the Document
                Library.
              </div>
            {:else}
              <div class="max-h-56 space-y-2 overflow-y-auto">
                {#each documents as doc}
                  <button
                    type="button"
                    onclick={() => toggleDocument(doc.id)}
                    class="flex w-full items-center justify-between rounded-xl border p-3 text-left transition-all {selectedDocIds.has(
                      doc.id,
                    )
                      ? 'border-accent bg-blue-950/30'
                      : 'border-slate-800 bg-slate-950 hover:border-slate-700'}"
                  >
                    <div class="flex items-center gap-2.5 truncate">
                      <FileText
                        class="h-4 w-4 {selectedDocIds.has(doc.id)
                          ? 'text-accent'
                          : 'text-slate-500'}"
                      />
                      <div class="truncate">
                        <div class="flex items-center gap-2">
                          <span class="truncate text-xs font-semibold text-slate-50"
                            >{doc.filename}</span
                          >
                          {#if doc.doc_type}
                            <span
                              class="py-0.2 rounded border border-slate-700/60 bg-slate-800 px-1.5 text-micro font-medium text-blue-300"
                            >
                              {doc.doc_type}
                            </span>
                          {/if}
                        </div>
                        <div class="text-micro text-slate-400">
                          {doc.char_count.toLocaleString()} chars extracted
                        </div>
                      </div>
                    </div>
                    <div
                      class="flex h-4 w-4 items-center justify-center rounded-full border {selectedDocIds.has(
                        doc.id,
                      )
                        ? 'border-accent bg-accent text-white'
                        : 'border-slate-700'}"
                    >
                      {#if selectedDocIds.has(doc.id)}
                        <Check class="h-3 w-3" />
                      {/if}
                    </div>
                  </button>
                {/each}
              </div>
            {/if}

            <div class="border-t border-slate-800 pt-2">
              <p class="mb-2 mt-2 text-xs text-slate-400">
                Normative standards to evaluate against
                {#if analysisType}
                  <span class="text-slate-500">— relevant to {analysisType}</span>
                {/if}
              </p>
              {#if standardsForDomain.length === 0}
                <div
                  class="rounded-xl border border-slate-800 p-4 text-center text-xs text-slate-500"
                >
                  No bundled standards match this analysis domain.
                </div>
              {:else}
                <div class="max-h-44 space-y-2 overflow-y-auto">
                  {#each standardsForDomain as standard}
                    <button
                      type="button"
                      onclick={() => toggleStandard(standard.id)}
                      class="flex w-full items-center justify-between rounded-xl border p-3 text-left transition-all {selectedStandardIds.has(
                        standard.id,
                      )
                        ? 'border-accent bg-blue-950/30'
                        : 'border-slate-800 bg-slate-950 hover:border-slate-700'}"
                    >
                      <div class="truncate pr-2">
                        <div class="truncate text-xs font-semibold text-slate-50">
                          {standard.name}
                        </div>
                        <div class="truncate text-micro text-slate-400">{standard.domain}</div>
                      </div>
                      <div
                        class="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border {selectedStandardIds.has(
                          standard.id,
                        )
                          ? 'border-accent bg-accent text-white'
                          : 'border-slate-700'}"
                      >
                        {#if selectedStandardIds.has(standard.id)}
                          <Check class="h-3 w-3" />
                        {/if}
                      </div>
                    </button>
                  {/each}
                </div>
              {/if}
            </div>
          </div>
        {:else if currentStep === 6}
          <!-- Step 6: Summary & Confirm -->
          <div class="space-y-3 text-xs">
            <div class="space-y-2 rounded-xl border border-slate-800 bg-slate-950 p-4">
              <div class="flex justify-between border-b border-slate-800 py-1">
                <span class="font-medium text-slate-400">Project Name:</span>
                <span class="font-semibold text-slate-50">{name}</span>
              </div>
              <div class="flex justify-between border-b border-slate-800 py-1">
                <span class="font-medium text-slate-400">Status:</span>
                <span class="font-semibold text-slate-50">{status}</span>
              </div>
              <div class="flex justify-between border-b border-slate-800 py-1">
                <span class="font-medium text-slate-400">Jurisdiction:</span>
                <span class="font-semibold text-slate-50">{country}</span>
              </div>
              <div class="flex justify-between border-b border-slate-800 py-1">
                <span class="font-medium text-slate-400">Building Type:</span>
                <span class="font-semibold text-slate-50">{projectType || "—"}</span>
              </div>
              <div class="flex justify-between border-b border-slate-800 py-1">
                <span class="font-medium text-slate-400">Size / Buildings / Floors:</span>
                <span class="font-semibold text-slate-50">
                  {projectSizeSqm ? `${projectSizeSqm} m²` : "—"} · {buildingsCount || "—"} · {floorsCount ||
                    "—"}
                </span>
              </div>
              <div class="flex justify-between border-b border-slate-800 py-1">
                <span class="font-medium text-slate-400">Building Code:</span>
                <span class="font-semibold text-slate-50"
                  >{selectedBuildingCode?.name || "Not specified"}</span
                >
              </div>
              <div class="flex justify-between border-b border-slate-800 py-1">
                <span class="font-medium text-slate-400">Analysis Domain:</span>
                <span class="font-semibold text-slate-50">{analysisType}</span>
              </div>
              <div class="flex justify-between border-b border-slate-800 py-1">
                <span class="font-medium text-slate-400">Attached Models:</span>
                <span class="font-semibold text-emerald-400">
                  {#if primaryIfcFile}
                    {primaryIfcFile.name}{ifcFiles.length > 1
                      ? ` + ${ifcFiles.length - 1} more`
                      : ""}
                  {:else}
                    None (can attach later)
                  {/if}
                </span>
              </div>
              <div class="flex justify-between border-b border-slate-800 py-1">
                <span class="font-medium text-slate-400">Linked Documents:</span>
                <span class="font-semibold text-slate-50">{selectedDocIds.size} selected</span>
              </div>
              <div class="flex justify-between py-1">
                <span class="font-medium text-slate-400">Linked Standards:</span>
                <span class="font-semibold text-slate-50">{selectedStandardIds.size} selected</span>
              </div>
            </div>
            <p class="text-caption text-slate-400">
              Clicking "Create &amp; Launch Audit" saves the project, closes this wizard and opens
              the
              <span class="font-semibold text-slate-200">{analysisDomainLabel}</span> analysis page with
              it selected.
            </p>
          </div>
        {/if}
      </div>

      <!-- Footer Buttons -->
      <div
        class="flex items-center justify-between border-t border-slate-800 bg-slate-950/60 px-6 py-4"
      >
        {#if currentStep > 1}
          <button
            type="button"
            onclick={() => (currentStep -= 1)}
            class="inline-flex items-center gap-1.5 rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-50 transition-colors hover:bg-slate-700"
          >
            <ArrowLeft class="h-3.5 w-3.5" />
            <span>Back</span>
          </button>
        {:else}
          <div></div>
        {/if}

        {#if currentStep < LAST_STEP}
          <button
            type="button"
            onclick={() => {
              if (currentStep === 1 && !name.trim()) {
                errorMessage = "Please provide a project name.";
                return;
              }
              errorMessage = "";
              currentStep += 1;
            }}
            class="inline-flex items-center gap-1.5 rounded-full bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-accent-hover"
          >
            <span>Next Step</span>
            <ArrowRight class="h-3.5 w-3.5" />
          </button>
        {:else}
          <button
            type="button"
            disabled={isSubmitting}
            onclick={handleFinish}
            class="inline-flex items-center gap-1.5 rounded-full bg-emerald-600 px-6 py-2 text-xs font-semibold text-white shadow-sm shadow-emerald-500/20 transition-all hover:bg-emerald-500 disabled:opacity-50"
          >
            <span>{isSubmitting ? "Creating & launching..." : "Create & Launch Audit"}</span>
            <Check class="h-3.5 w-3.5" />
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}
