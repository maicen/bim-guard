<script lang="ts">
  import { onMount } from 'svelte';
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
    Wand2,
  } from 'lucide-svelte';
  import { projectsApi } from '../lib/api';
  import type { Project } from '../lib/types';
  import ProjectWizardModal from '../lib/components/ProjectWizardModal.svelte';
  import ProjectEnhancementsModal from '../lib/components/ProjectEnhancementsModal.svelte';

  export let onSelectProjectForAudit: (projectId: number) => void;
  export let onSelectProjectForViewer: (projectId: number) => void;

  let projects: Project[] = [];
  let isLoading = true;
  let error = '';

  // Filter state
  let searchQuery = '';
  let statusFilter = 'all';
  let domainFilter = 'all';

  // Modals state
  let isWizardOpen = false;
  let isEnhancementsOpen = false;
  let selectedProjectForEnhance: Project | null = null;

  async function loadProjects() {
    isLoading = true;
    error = '';
    try {
      const data = await projectsApi.list();
      projects = data.projects || [];
    } catch (err: any) {
      error = err.message || 'Failed to load projects';
    } finally {
      isLoading = false;
    }
  }

  onMount(() => {
    loadProjects();
  });

  $: filteredProjects = projects.filter((p) => {
    const matchesSearch =
      searchQuery === '' ||
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.description || '').toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || p.status === statusFilter;
    const matchesDomain = domainFilter === 'all' || p.analysis_type === domainFilter;
    return matchesSearch && matchesStatus && matchesDomain;
  });

  async function handleDelete(projectId: number, name: string) {
    if (!confirm(`Are you sure you want to delete project "${name}"?`)) return;
    try {
      await projectsApi.delete(projectId);
      projects = projects.filter((p) => p.id !== projectId);
    } catch (err: any) {
      alert(`Could not delete project: ${err.message}`);
    }
  }

  function openEnhancements(project: Project) {
    selectedProjectForEnhance = project;
    isEnhancementsOpen = true;
  }
</script>

<div class="space-y-6 max-w-6xl mx-auto">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <div class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">Registry</div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">Project Registry</h1>
      <p class="text-xs sm:text-sm text-slate-400">Manage OpenBIM models, analysis scopes, and compliance records.</p>
    </div>

    <div class="flex items-center gap-2">
      <button
        type="button"
        on:click={() => (isWizardOpen = true)}
        class="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02]"
      >
        <Wand2 class="w-3.5 h-3.5" />
        <span>Setup Wizard</span>
      </button>
    </div>
  </div>

  {#if error}
    <div class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
      {error}
    </div>
  {/if}

  <!-- Filters and Search Bar -->
  <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col md:flex-row items-center gap-3">
    <div class="relative flex-1 w-full">
      <Search class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
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
        <option value="Piping (Corrosive)">Piping (Corrosive)</option>
        <option value="Piping (Seismic)">Piping (Seismic)</option>
        <option value="Architecture">Architecture</option>
      </select>
    </div>
  </div>

  <!-- Projects Table -->
  <div class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-900/40">
    {#if isLoading}
      <div class="p-12 text-center text-xs text-slate-400">Loading project registry...</div>
    {:else if filteredProjects.length === 0}
      <div class="p-12 text-center text-xs text-slate-500 space-y-2">
        <p>No projects match your current filters.</p>
        <button
          type="button"
          on:click={() => (isWizardOpen = true)}
          class="text-[#0071e3] hover:underline font-medium"
        >
          Launch setup wizard to create one
        </button>
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs text-slate-300">
          <thead class="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
            <tr>
              <th class="py-3 px-4">ID</th>
              <th class="py-3 px-4">Name</th>
              <th class="py-3 px-4">Status</th>
              <th class="py-3 px-4">IFC Model</th>
              <th class="py-3 px-4">Domain</th>
              <th class="py-3 px-4">Jurisdiction</th>
              <th class="py-3 px-4">Created</th>
              <th class="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60">
            {#each filteredProjects as project}
              <tr class="hover:bg-slate-900/60 transition-colors">
                <td class="py-3 px-4 font-mono text-slate-500">#{project.id}</td>
                <td class="py-3 px-4">
                  <div class="font-semibold text-white truncate max-w-xs">{project.name}</div>
                  {#if project.description}
                    <div class="text-[11px] text-slate-400 truncate max-w-xs">{project.description}</div>
                  {/if}
                </td>
                <td class="py-3 px-4">
                  <span class="inline-block px-2.5 py-0.5 rounded-full text-[10px] font-semibold {project.status === 'Active' ? 'bg-emerald-950/50 text-emerald-400 border border-emerald-800/60' : 'bg-slate-800 text-slate-400'}">
                    {project.status}
                  </span>
                </td>
                <td class="py-3 px-4">
                  {#if project.ifc_file_path}
                    <div class="flex items-center gap-1.5 text-emerald-400">
                      <CheckCircle2 class="w-4 h-4" />
                      <span class="text-[11px] font-medium">Attached</span>
                      <a
                        href={projectsApi.getIfcUrl(project.id)}
                        download
                        class="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800 transition-colors ml-1"
                        title="Download attached IFC file"
                      >
                        <Download class="w-3 h-3" />
                      </a>
                    </div>
                  {:else}
                    <div class="flex items-center gap-1.5 text-slate-500">
                      <XCircle class="w-4 h-4" />
                      <span class="text-[11px]">None</span>
                    </div>
                  {/if}
                </td>
                <td class="py-3 px-4 text-slate-300">{project.analysis_type}</td>
                <td class="py-3 px-4 text-slate-400">{project.country}</td>
                <td class="py-3 px-4 text-slate-500 whitespace-nowrap">
                  {project.created_at ? project.created_at.substring(0, 10) : '-'}
                </td>
                <td class="py-3 px-4 text-right whitespace-nowrap">
                  <div class="flex items-center justify-end gap-1.5">
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
                      on:click={() => handleDelete(project.id, project.name)}
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
<ProjectWizardModal
  isOpen={isWizardOpen}
  onClose={() => (isWizardOpen = false)}
  onProjectCreated={(newProject) => {
    projects = [newProject, ...projects];
    onSelectProjectForAudit(newProject.id);
  }}
/>

<ProjectEnhancementsModal
  isOpen={isEnhancementsOpen}
  project={selectedProjectForEnhance}
  onClose={() => {
    isEnhancementsOpen = false;
    selectedProjectForEnhance = null;
  }}
/>
