<script lang="ts">
  import { onMount, onDestroy } from "svelte";
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
    RotateCw,
    FolderGit2,
    GitBranch,
    ExternalLink,
    Import,
    Box,
    Loader2,
    Database,
  } from "lucide-svelte";
  import { projectsApi, githubReposApi } from "../lib/api";
  import type { Project, GitHubRepo, GitHubRepoStructure, GitHubRepoItem } from "../lib/types";
  import ProjectEditModal from "../lib/components/ProjectEditModal.svelte";
  import ProjectDetailsModal from "../lib/components/ProjectDetailsModal.svelte";
  import ProjectEnhancementsModal from "../lib/components/ProjectEnhancementsModal.svelte";
  import GitHubRepoManagerModal from "../lib/components/GitHubRepoManagerModal.svelte";
  import ProjectBulkEditModal from "../lib/components/ProjectBulkEditModal.svelte";
  import ConfirmModal from "../lib/components/ConfirmModal.svelte";
  import TablePagination from "../lib/components/TablePagination.svelte";
  import BulkActionBar from "../lib/components/BulkActionBar.svelte";
  import DataTableHeader from "../lib/components/DataTableHeader.svelte";

  export let onSelectProjectForAudit: (projectId: number) => void;
  export let onSelectProjectForViewer: (projectId: number) => void;

  // Initialize immediately from synchronous client cache for 0ms render time
  const initialCache = projectsApi.getCachedList();
  let projects: Project[] = initialCache ? initialCache.projects || [] : [];
  let isLoading = !initialCache;
  let isRefreshing = false;
  let error = "";
  let unsubscribe: (() => void) | null = null;

  // Storage Source selector state
  let selectedSource = "supabase"; // 'supabase' or 'repo:<id>'
  let repos: GitHubRepo[] = [];
  let isRepoLoading = false;
  let activeRepoStructure: GitHubRepoStructure | null = null;
  let repoCategoryFilter = "all";
  let importingPath = "";

  // Filter state
  let searchQuery = "";
  let statusFilter = "all";
  let domainFilter = "all";

  // Modals state
  let isEditModalOpen = false;
  let isDetailsModalOpen = false;
  let isEnhancementsOpen = false;
  let isDeleteModalOpen = false;
  let isRepoManagerOpen = false;
  let selectedProjectForEdit: Project | null = null;
  let selectedProjectForDetails: Project | null = null;
  let selectedProjectForEnhance: Project | null = null;
  let projectToDelete: { id: number; name: string } | null = null;

  // Bulk selection state
  let selectedProjectIds: number[] = [];
  let isBulkEditModalOpen = false;
  let isBulkDeleteModalOpen = false;

  function toggleSelectAll() {
    if (allFilteredSelected) {
      selectedProjectIds = [];
    } else {
      selectedProjectIds = filteredProjects.map((p) => p.id);
    }
  }

  function toggleSelectProject(id: number) {
    if (selectedProjectIds.includes(id)) {
      selectedProjectIds = selectedProjectIds.filter((pId) => pId !== id);
    } else {
      selectedProjectIds = [...selectedProjectIds, id];
    }
  }

  $: filteredProjects = (projects || []).filter((p) => {
    const matchesSearch =
      searchQuery === "" ||
      (p.name || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.description || "").toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "all" || p.status === statusFilter;
    const matchesDomain =
      domainFilter === "all" ||
      p.analysis_type === domainFilter ||
      (domainFilter === "Arch" && (p.analysis_type === "Architecture" || p.analysis_type === "Architectural")) ||
      (domainFilter === "Piping" && p.analysis_type === "Piping (Corrosive)") ||
      (domainFilter === "seismic" && (p.analysis_type === "Seismic" || p.analysis_type === "Halo"));
    return matchesSearch && matchesStatus && matchesDomain;
  });

  $: allFilteredSelected =
    filteredProjects.length > 0 &&
    filteredProjects.every((p) => selectedProjectIds.includes(p.id));

  let currentPage = 1;
  let pageSize = 10;

  $: totalItems = filteredProjects.length;
  $: paginatedProjects = filteredProjects.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize,
  );

  $: {
    searchQuery;
    statusFilter;
    domainFilter;
    currentPage = 1;
  }

  $: filteredRepoItems = (activeRepoStructure?.items || []).filter((item) => {
    const matchesSearch =
      searchQuery === "" ||
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.path.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = repoCategoryFilter === "all" || item.category === repoCategoryFilter;
    return matchesSearch && matchesCategory;
  });

  function getImportedProject(item: GitHubRepoItem): Project | undefined {
    return projects.find((p) => {
      if (!p.ifc_file_path) return false;
      const pathClean = p.ifc_file_path.toLowerCase();
      const itemUrlClean = item.download_url.toLowerCase();
      const itemPathClean = item.path.toLowerCase();
      const descClean = (p.description || "").toLowerCase();
      return (
        pathClean === itemUrlClean ||
        pathClean.includes(itemPathClean) ||
        descClean.includes(itemPathClean)
      );
    });
  }

  function handleViewInMainRegistry(project: Project) {
    selectedSource = "supabase";
    activeRepoStructure = null;
    searchQuery = project.name;
  }

  async function handleImportRepoModel(item: GitHubRepoItem) {
    if (!selectedSource.startsWith("repo:")) return;
    const repoId = parseInt(selectedSource.split(":")[1], 10);

    importingPath = item.path;
    error = "";
    try {
      const imported = await githubReposApi.importProject(repoId, {
        file_path: item.path,
        name: item.name.replace(".ifc", "").replace(/_/g, " "),
      });
      await loadProjects(true);
      // Automatically navigate to audit for imported model
      onSelectProjectForAudit(imported.id);
    } catch (err: any) {
      error = err.message || "Failed to import model from GitHub repository.";
    } finally {
      importingPath = "";
    }
  }

  function promptDelete(projectId: number, name: string) {
    projectToDelete = { id: projectId, name };
    isDeleteModalOpen = true;
  }

  async function confirmDelete() {
    if (!projectToDelete) return;
    try {
      await projectsApi.delete(projectToDelete.id);
      projects = projects.filter((p) => p.id !== projectToDelete!.id);
      selectedProjectIds = selectedProjectIds.filter((id) => id !== projectToDelete!.id);
      projectToDelete = null;
    } catch (err: any) {
      error = `Could not delete project: ${err.message}`;
    }
  }

  async function confirmBulkDelete() {
    if (!selectedProjectIds.length) return;
    try {
      await projectsApi.bulkDelete(selectedProjectIds);
      projects = projects.filter((p) => !selectedProjectIds.includes(p.id));
      selectedProjectIds = [];
      isBulkDeleteModalOpen = false;
    } catch (err: any) {
      error = `Could not delete selected projects: ${err.message}`;
    }
  }

  async function handleBulkUpdated() {
    await loadProjects(true);
    selectedProjectIds = [];
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

  function formatBytes(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }
</script>

<div class="space-y-6 mx-auto">
  <!-- Header & Storage Source Control -->
  <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
    <div>
      <div class="text-xs font-bold uppercase tracking-widest text-slate-400 mb-1">
        Registry
      </div>
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight text-white">
        Project Registry
      </h1>
      <p class="text-xs sm:text-sm text-slate-400">
        Manage OpenBIM models, analysis scopes, and project storage sources.
      </p>
    </div>

    <!-- Storage Source Dropdown & Repo Manager Button -->
    <div class="flex flex-wrap items-center gap-2.5 bg-slate-900/90 border border-slate-800 p-2 rounded-2xl">
      <div class="flex items-center gap-2 px-2">
        {#if selectedSource === 'supabase'}
          <Database class="w-4 h-4 text-emerald-400" />
        {:else}
          <FolderGit2 class="w-4 h-4 text-blue-400" />
        {/if}
        <span class="text-xs font-semibold text-slate-300 whitespace-nowrap">Storage Source:</span>
      </div>

      <select
        bind:value={selectedSource}
        on:change={handleSourceChange}
        class="bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs font-semibold text-white focus:outline-none focus:border-blue-500 max-w-[240px] truncate"
      >
        <option value="supabase">Supabase Database (Main Registry)</option>
        {#if repos.length > 0}
          <optgroup label="GitHub Repositories">
            {#each repos as repo}
              <option value={`repo:${repo.id}`}>
                {repo.owner}/{repo.name} ({repo.branch})
              </option>
            {/each}
          </optgroup>
        {/if}
      </select>

      <button
        type="button"
        on:click={() => (isRepoManagerOpen = true)}
        class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-800 bg-slate-950 hover:bg-slate-800 text-slate-200 text-xs font-semibold transition-colors"
        title="Manage GitHub Repositories (Add, Edit, Delete)"
      >
        <Plus class="w-3.5 h-3.5 text-blue-400" />
        <span>Manage Repos</span>
      </button>

      {#if selectedSource === 'supabase'}
        <button
          type="button"
          on:click={() => loadProjects(true)}
          class="p-1.5 rounded-xl border border-slate-800 bg-slate-950 hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
          title="Refresh project registry"
        >
          <RotateCw class="w-3.5 h-3.5 {isRefreshing ? 'animate-spin text-blue-400' : ''}" />
        </button>
      {:else if selectedSource.startsWith('repo:')}
        <button
          type="button"
          on:click={() => {
            const repoId = parseInt(selectedSource.split(":")[1], 10);
            loadSelectedRepoStructure(repoId, true);
          }}
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-800 bg-slate-950 hover:bg-slate-800 text-slate-200 text-xs font-semibold transition-colors"
          title="Re-sync GitHub repository models & manifest"
        >
          <RotateCw class="w-3.5 h-3.5 {isRepoLoading ? 'animate-spin text-blue-400' : ''}" />
          <span>Sync Repo</span>
        </button>
      {/if}
    </div>
  </div>

  {#if error}
    <div class="p-4 rounded-xl bg-rose-950/50 border border-rose-800 text-rose-300 text-xs">
      {error}
    </div>
  {/if}

  <!-- VIEW 1: SUPABASE INTERNAL DATABASE PROJECTS (MAIN REGISTRY) -->
  {#if selectedSource === "supabase"}
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
          <option value="Arch">Arch</option>
          <option value="Piping">Piping</option>
          <option value="seismic">seismic</option>
        </select>
      </div>
    </div>

    <!-- Bulk Operations Toolbar -->
    <BulkActionBar
      selectedCount={selectedProjectIds.length}
      itemLabel="project"
      onClearSelection={() => (selectedProjectIds = [])}
      onBulkEdit={() => (isBulkEditModalOpen = true)}
      onBulkDelete={() => (isBulkDeleteModalOpen = true)}
    />

    <!-- Projects Table -->
    <div class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-900/40">
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
            <thead class="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
              <tr>
                <th class="py-3 px-4 w-10">
                  <input
                    type="checkbox"
                    checked={allFilteredSelected}
                    on:change={toggleSelectAll}
                    class="rounded bg-slate-950 border-slate-700 text-[#0071e3] focus:ring-[#0071e3] cursor-pointer w-4 h-4"
                    title="Select or deselect all visible projects"
                  />
                </th>
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
              {#each paginatedProjects as project}
                <tr class="hover:bg-slate-900/60 transition-colors {selectedProjectIds.includes(project.id) ? 'bg-blue-950/20' : ''}">
                  <td class="py-3 px-4 w-10">
                    <input
                      type="checkbox"
                      checked={selectedProjectIds.includes(project.id)}
                      on:change={() => toggleSelectProject(project.id)}
                      class="rounded bg-slate-950 border-slate-700 text-[#0071e3] focus:ring-[#0071e3] cursor-pointer w-4 h-4"
                    />
                  </td>
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
                    {project.created_at ? project.created_at.substring(0, 10) : "-"}
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

        <TablePagination
          {currentPage}
          {pageSize}
          totalItems={totalItems}
          onPageChange={(p) => (currentPage = p)}
          onPageSizeChange={(s) => {
            pageSize = s;
            currentPage = 1;
          }}
        />
      {/if}
    </div>
  {/if}

  <!-- VIEW 2: GITHUB REPOSITORY STORAGE DISCOVERY -->
  {#if selectedSource.startsWith("repo:")}
    <div class="space-y-4">
      {#if isRepoLoading}
        <div class="p-12 text-center text-xs text-slate-400 border border-slate-800 rounded-2xl bg-slate-900/40 flex items-center justify-center gap-2">
          <Loader2 class="w-4 h-4 animate-spin text-blue-400" />
          <span>Reading GitHub repository structure & OpenBIM models tree...</span>
        </div>
      {:else if activeRepoStructure}
        <!-- Repo Banner -->
        <div class="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div class="space-y-1">
            <div class="flex items-center gap-2">
              <FolderGit2 class="w-5 h-5 text-blue-400" />
              <h2 class="text-lg font-bold text-white">
                {activeRepoStructure.owner}/{activeRepoStructure.name}
              </h2>
              <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-slate-950 border border-slate-800 font-mono text-[11px] text-slate-400">
                <GitBranch class="w-3 h-3 text-blue-400" />
                {activeRepoStructure.branch}
              </span>
            </div>
            <p class="text-xs text-slate-400">
              Discovered <span class="text-blue-400 font-semibold">{activeRepoStructure.models_count}</span> OpenBIM models across
              <span class="text-slate-300 font-semibold">{activeRepoStructure.categories.length}</span> category folders.
            </p>
          </div>

          <div class="flex items-center gap-2">
            <a
              href={activeRepoStructure.url}
              target="_blank"
              rel="noopener noreferrer"
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-800 bg-slate-950 hover:bg-slate-800 text-blue-400 text-xs font-semibold transition-colors"
            >
              <span>GitHub Repo</span>
              <ExternalLink class="w-3.5 h-3.5" />
            </a>
          </div>
        </div>

        <!-- Filter Bar -->
        <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col md:flex-row items-center gap-3">
          <div class="relative flex-1 w-full">
            <Search class="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              bind:value={searchQuery}
              placeholder="Search repository IFC models by filename or path..."
              class="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {#if activeRepoStructure.categories.length > 0}
            <div class="flex items-center gap-2 w-full md:w-auto">
              <select
                bind:value={repoCategoryFilter}
                class="bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
              >
                <option value="all">All Category Folders</option>
                {#each activeRepoStructure.categories as cat}
                  <option value={cat}>{cat}</option>
                {/each}
              </select>
            </div>
          {/if}
        </div>

        <!-- Repo Models Table -->
        <div class="border border-slate-800 rounded-2xl overflow-hidden bg-slate-900/40">
          {#if filteredRepoItems.length === 0}
            <div class="p-12 text-center text-xs text-slate-500">
              No OpenBIM models found matching your search or category filter.
            </div>
          {:else}
            <div class="overflow-x-auto">
              <table class="w-full text-left text-xs text-slate-300">
                <thead class="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                  <tr>
                    <th class="py-3 px-4">IFC Model Name</th>
                    <th class="py-3 px-4">Repository Path</th>
                    <th class="py-3 px-4">Category</th>
                    <th class="py-3 px-4">Size</th>
                    <th class="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-800/60">
                  {#each filteredRepoItems as item}
                    {@const importedProject = getImportedProject(item)}
                    <tr class="hover:bg-slate-900/60 transition-colors">
                      <td class="py-3 px-4 font-semibold text-white">
                        <div class="flex items-center gap-2">
                          <Box class="w-4 h-4 text-blue-400 shrink-0" />
                          <span class="text-sm">{item.name}</span>
                        </div>
                      </td>
                      <td class="py-3 px-4 text-slate-400 font-mono text-[11px] truncate max-w-xs" title={item.path}>
                        {item.path}
                      </td>
                      <td class="py-3 px-4">
                        <span class="inline-block px-2 py-0.5 rounded text-[10px] font-semibold font-mono uppercase bg-slate-800 text-slate-300 border border-slate-700">
                          {item.category}
                        </span>
                      </td>
                      <td class="py-3 px-4 text-slate-400 whitespace-nowrap">
                        {formatBytes(item.size)}
                      </td>
                      <td class="py-3 px-4 text-right whitespace-nowrap">
                        <div class="flex items-center justify-end gap-2">
                          <a
                            href={item.download_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
                            title="Direct download raw IFC"
                          >
                            <Download class="w-3.5 h-3.5" />
                          </a>

                          {#if importedProject}
                            <button
                              type="button"
                              on:click={() => handleViewInMainRegistry(importedProject)}
                              class="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-emerald-950/70 hover:bg-emerald-900/90 border border-emerald-800/80 text-emerald-300 text-xs font-semibold transition-all shadow-sm"
                              title="Model is already imported into Main Registry. Click to view in Main Registry."
                            >
                              <Eye class="w-3.5 h-3.5 text-emerald-400" />
                              <span>View in Main Registry</span>
                            </button>
                          {:else}
                            <button
                              type="button"
                              on:click={() => handleImportRepoModel(item)}
                              disabled={importingPath === item.path}
                              class="flex items-center gap-1 px-3 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-all disabled:opacity-50"
                            >
                              {#if importingPath === item.path}
                                <Loader2 class="w-3.5 h-3.5 animate-spin" />
                                <span>Importing...</span>
                              {:else}
                                <Import class="w-3.5 h-3.5" />
                                <span>Import to Main Registry & Audit</span>
                              {/if}
                            </button>
                          {/if}
                        </div>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
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

<GitHubRepoManagerModal
  isOpen={isRepoManagerOpen}
  onClose={() => (isRepoManagerOpen = false)}
  onReposUpdated={() => {
    loadRepos();
    if (selectedSource.startsWith("repo:")) {
      handleSourceChange();
    }
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

<ProjectBulkEditModal
  isOpen={isBulkEditModalOpen}
  selectedProjectIds={selectedProjectIds}
  onClose={() => (isBulkEditModalOpen = false)}
  onBulkUpdated={handleBulkUpdated}
/>

<ConfirmModal
  bind:isOpen={isBulkDeleteModalOpen}
  title="Delete Selected Projects"
  message={`Are you sure you want to delete ${selectedProjectIds.length} project(s) and their associated artifacts? This cannot be undone.`}
  confirmText={`Delete ${selectedProjectIds.length} Project(s)`}
  danger={true}
  onConfirm={confirmBulkDelete}
  onCancel={() => (isBulkDeleteModalOpen = false)}
/>
