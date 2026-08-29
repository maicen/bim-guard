<script lang="ts">
  import { onMount } from "svelte";
  import {
    Plus,
    Search,
    Trash2,
    Download,
    ScanEye,
    Cpu,
    Sparkles,
    CheckCircle2,
    XCircle,
    SlidersHorizontal,
    Eye,
    Pencil,
  } from "lucide-svelte";
  import { projectsApi } from "../lib/api";
  import type { Project } from "../lib/types";
  import ProjectEditModal from "../lib/components/ProjectEditModal.svelte";
  import ProjectDetailsModal from "../lib/components/ProjectDetailsModal.svelte";
  import ProjectEnhancementsModal from "../lib/components/ProjectEnhancementsModal.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";

  export let onSelectProjectForAudit: (projectId: number) => void;
  export let onSelectProjectForViewer: (projectId: number) => void;

  let projects: Project[] = [];
  let isLoading = true;
  let error = "";

  // Filter state
  let searchQuery = "";
  let statusFilter = "all";
  let domainFilter = "all";

  // Modals state
  let isEditModalOpen = false;
  let isDetailsModalOpen = false;
  let isEnhancementsOpen = false;
  let isDeleteModalOpen = false;
  let selectedProjectForEdit: Project | null = null;
  let selectedProjectForDetails: Project | null = null;
  let selectedProjectForEnhance: Project | null = null;
  let projectToDelete: { id: number; name: string } | null = null;

  async function loadProjects() {
    isLoading = true;
    error = "";
    try {
      const data = await projectsApi.list();
      projects = data.projects || [];
    } catch (err: any) {
      error = err.message || "Failed to load projects";
    } finally {
      isLoading = false;
    }
  }

  onMount(() => {
    loadProjects();
  });

  $: filteredProjects = projects.filter((p) => {
    const matchesSearch =
      searchQuery === "" ||
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.description || "").toLowerCase().includes(searchQuery.toLowerCase());
    const matchesDomain =
      domainFilter === "all" ||
      p.analysis_type === domainFilter ||
      (domainFilter === "Arch" && (p.analysis_type === "Architecture" || p.analysis_type === "Architectural")) ||
      (domainFilter === "Piping" && p.analysis_type === "Piping (Corrosive)") ||
      (domainFilter === "seismic" && (p.analysis_type === "Seismic" || p.analysis_type === "Halo"));
    return matchesSearch && matchesStatus && matchesDomain;
  });

  function promptDelete(projectId: number, name: string) {
    projectToDelete = { id: projectId, name };
    isDeleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!projectToDelete) return;
    try {
      await projectsApi.delete(projectToDelete.id);
      projects = projects.filter((p) => p.id !== projectToDelete!.id);
      projectToDelete = null;
    } catch (err: any) {
      error = `Could not delete project: ${err.message}`;
    }
  }

  function openEnhancements(project: Project) {
    selectedProjectForEnhance = project;
    isEnhancementsOpen = true;
  }

  function openEdit(project: Project) {
    selectedProjectForEdit = project;
    isEditModalOpen = true;
  }

  function openDetails(project: Project) {
    selectedProjectForDetails = project;
    isDetailsModalOpen = true;
  }

  function handleProjectUpdated(updated: Project) {
    projects = projects.map((p) => (p.id === updated.id ? updated : p));
  }
</script>

<div class="space-y-6 mx-auto">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <div
        class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1"
      >
        Registry
      </div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">
        Project Registry
      </h1>
      <p class="text-xs sm:text-sm text-slate-400">
        Manage OpenBIM models, analysis scopes, and compliance records.
      </p>
    </div>
  </div>

  {#if error}
    <div
      class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs"
    >
      {error}
    </div>
  {/if}

  <!-- Filters and Search Bar -->
  <div
    class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col md:flex-row items-center gap-3"
  >
    <div class="relative flex-1 w-full">
      <Search
        class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2"
      />
      <input
        type="text"
        bind:value={searchQuery}
        placeholder="Filter projects by name or description..."
        class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#0071e3]"
      />
    </div>

    <div class="flex items-center gap-2 w-full md:w-auto">
      <select
        bind:value={statusFilter}
        class="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
      >
        <option value="all">All Statuses</option>
        <option value="Active">Active</option>
        <option value="Draft">Draft</option>
        <option value="Archived">Archived</option>
      </select>

      <select
        bind:value={domainFilter}
        class="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#0071e3]"
      >
        <option value="all">All Domains</option>
        <option value="Arch">Arch</option>
        <option value="Piping">Piping</option>
        <option value="seismic">seismic</option>
      </select>
    </div>
  </div>

  <!-- Projects Table -->
  <div
    class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-900/40"
  >
    {#if isLoading}
      <div class="p-12 text-center text-xs text-slate-400">
        Loading project registry...
      </div>
    {:else if filteredProjects.length === 0}
      <div class="p-12 text-center text-xs text-slate-500 space-y-2">
        <p>No projects match your current filters.</p>
        <button
          type="button"
          on:click={() => {
            searchQuery = "";
            statusFilter = "all";
            domainFilter = "all";
          }}
          class="text-[#0071e3] hover:underline"
        >
          Reset filters
        </button>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-slate-300">
          <thead
            class="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold"
          >
            <tr>
              <th class="py-3 px-4">Project Name</th>
              <th class="py-3 px-4">Status</th>
              <th class="py-3 px-4">IFC Model</th>
              <th class="py-3 px-4">Analysis Domain</th>
              <th class="py-3 px-4">Jurisdiction</th>
              <th class="py-3 px-4">Created</th>
              <th class="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each filteredProjects as project}
              <tr class="hover:bg-slate-900/60 transition-colors">
                <td class="py-3 px-4 font-semibold text-white">
                  <div class="flex flex-col">
                    <span class="text-sm">{project.name}</span>
                    {#if project.description}
                      <span class="text-[11px] text-slate-400 font-normal truncate max-w-sm">
                        {project.description}
                      </span>
                    {/if}
                  </div>
                </td>
                <td class="py-3 px-4">
                  <span
                    class="inline-block px-2.5 py-0.5 rounded-full text-[10px] font-semibold border {project.status ===
                    'Active'
                      ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60'
                      : project.status === 'Archived'
                      ? 'bg-slate-800 text-slate-400 border-slate-700'
                      : 'bg-amber-950/40 text-amber-400 border-amber-800/60'}"
                  >
                    {project.status}
                  </span>
                </td>
                <td class="py-3 px-4">
                  {#if project.ifc_file_path}
                    <div class="flex items-center gap-1.5 text-emerald-400 font-medium">
                      <CheckCircle2 class="w-4 h-4 text-emerald-400" />
                      <span class="text-[11px] truncate max-w-[120px]" title={project.ifc_file_path}>Attached</span>
                    </div>
                  {:else}
                    <div class="flex items-center gap-1.5 text-slate-500">
                      <XCircle class="w-4 h-4" />
                      <span class="text-[11px]">None</span>
                    </div>
                  {/if}
                </td>
                <td class="py-3 px-4">
                  <span
                    class="inline-block px-2 py-0.5 rounded text-[10px] font-semibold font-mono {project.analysis_type ===
                    'Piping'
                      ? 'bg-amber-950/60 border border-amber-800/50 text-amber-300'
                      : project.analysis_type === 'Seismic'
                      ? 'bg-purple-950/60 border border-purple-800/50 text-purple-300'
                      : 'bg-blue-950/60 border border-blue-800/50 text-blue-300'}"
                  >
                    {project.analysis_type}
                  </span>
                </td>
                <td class="py-3 px-4 text-slate-400">{project.country}</td>
                <td class="py-3 px-4 text-slate-500 whitespace-nowrap">
                  {project.created_at
                    ? project.created_at.substring(0, 10)
                    : "-"}
                </td>
                <td class="py-3 px-4 text-right whitespace-nowrap">
                  <div class="flex items-center justify-end gap-1.5">
                    <button
                      type="button"
                      on:click={() => openDetails(project)}
                      class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                      title="View project details"
                    >
                      <Eye class="w-3.5 h-3.5" />
                    </button>

                    {#if project.ifc_file_path}
                      <button
                        type="button"
                        on:click={() => onSelectProjectForViewer(project.id)}
                        class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                        title="Open in 3D Viewer"
                      >
                        <ScanEye class="w-3.5 h-3.5" />
                      </button>

                      <button
                        type="button"
                        on:click={() => openEnhancements(project)}
                        class="p-1.5 rounded-lg bg-purple-950/40 hover:bg-purple-900/60 text-purple-300 border border-purple-800/40 transition-colors"
                        title="Model Quality Improvements (Lineage)"
                      >
                        <Sparkles class="w-3.5 h-3.5" />
                      </button>
                    {/if}

                    <button
                      type="button"
                      on:click={() => onSelectProjectForAudit(project.id)}
                      class="px-2.5 py-1 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 hover:text-blue-300 text-xs font-semibold transition-colors"
                    >
                      Audit
                    </button>

                    <button
                      type="button"
                      on:click={() => openEdit(project)}
                      class="p-1.5 rounded-lg text-slate-400 hover:text-blue-400 hover:bg-blue-950/30 transition-colors"
                      title="Edit project"
                    >
                      <Pencil class="w-3.5 h-3.5" />
                    </button>

                    <button
                      type="button"
                      on:click={() => promptDelete(project.id, project.name)}
                      class="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
                      title="Delete project"
                    >
                      <Trash2 class="w-3.5 h-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</div>

<!-- Modals -->
<ProjectEditModal
  isOpen={isEditModalOpen}
  project={selectedProjectForEdit}
  onClose={() => {
    isEditModalOpen = false;
    selectedProjectForEdit = null;
  }}
  onProjectUpdated={handleProjectUpdated}
/>

<ProjectDetailsModal
  isOpen={isDetailsModalOpen}
  project={selectedProjectForDetails}
  onClose={() => {
    isDetailsModalOpen = false;
    selectedProjectForDetails = null;
  }}
  onOpenViewer={onSelectProjectForViewer}
  onOpenEnhancements={openEnhancements}
/>

<ProjectEnhancementsModal
  isOpen={isEnhancementsOpen}
  project={selectedProjectForEnhance}
  onClose={() => {
    isEnhancementsOpen = false;
    selectedProjectForEnhance = null;
  }}
/>

<ConfirmModal
  bind:isOpen={isDeleteModalOpen}
  title="Delete Project"
  message={`Are you sure you want to delete project "${projectToDelete?.name || ""}" and its associated artifacts? This cannot be undone.`}
  confirmText="Delete Project"
  danger={true}
  onConfirm={confirmDelete}
  onCancel={() => (projectToDelete = null)}
/>
