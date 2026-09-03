<script lang="ts">
  import { onMount } from "svelte";
  import {
    X,
    FolderGit2,
    Plus,
    Trash2,
    ExternalLink,
    GitBranch,
    Loader2,
    Check,
    AlertCircle,
  } from "lucide-svelte";
  import { githubReposApi } from "../api";
  import type { GitHubRepo } from "../types";

  export let isOpen = false;
  export let onClose: () => void = () => {};
  export let onReposUpdated: () => void = () => {};

  let repos: GitHubRepo[] = [];
  let isLoading = false;
  let isSubmitting = false;
  let error = "";
  let successMsg = "";

  // Add Form state
  let showAddForm = false;
  let newUrl = "";
  let newName = "";
  let newBranch = "main";
  let newDescription = "";

  async function loadRepos() {
    isLoading = true;
    error = "";
    try {
      repos = await githubReposApi.list();
    } catch (err: any) {
      error = err.message || "Failed to load repositories";
    } finally {
      isLoading = false;
    }
  }

  $: if (isOpen) {
    loadRepos();
    showAddForm = false;
    error = "";
    successMsg = "";
  }

  async function handleAddRepo() {
    if (!newUrl.trim()) {
      error = "Please enter a valid GitHub repository URL.";
      return;
    }

    isSubmitting = true;
    error = "";
    successMsg = "";

    try {
      const created = await githubReposApi.create({
        url: newUrl.trim(),
        name: newName.trim() || undefined,
        branch: newBranch.trim() || "main",
        description: newDescription.trim() || undefined,
      });

      successMsg = `Repository '${created.owner}/${created.name}' registered successfully!`;
      newUrl = "";
      newName = "";
      newBranch = "main";
      newDescription = "";
      showAddForm = false;
      await loadRepos();
      onReposUpdated();
    } catch (err: any) {
      error = err.message || "Failed to register repository.";
    } finally {
      isSubmitting = false;
    }
  }

  async function handleDeleteRepo(repo: GitHubRepo) {
    if (!confirm(`Remove repository '${repo.owner}/${repo.name}' from storage options?`)) return;

    try {
      await githubReposApi.delete(repo.id);
      repos = repos.filter((r) => r.id !== repo.id);
      successMsg = `Repository '${repo.name}' removed.`;
      onReposUpdated();
    } catch (err: any) {
      error = err.message || "Could not delete repository.";
    }
  }
</script>

{#if isOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
    <div class="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/50">
        <div class="flex items-center gap-2.5">
          <div class="p-2 rounded-xl bg-blue-950/60 border border-blue-800/50 text-blue-400">
            <FolderGit2 class="w-5 h-5" />
          </div>
          <div>
            <h2 class="text-lg font-semibold text-slate-50">GitHub Project Storage Repositories</h2>
            <p class="text-xs text-slate-400">Manage external GitHub repositories hosting OpenBIM IFC models.</p>
          </div>
        </div>
        <button
          type="button"
          on:click={onClose}
          class="p-2 rounded-xl text-slate-400 hover:text-slate-50 hover:bg-slate-800 transition-colors"
        >
          <X class="w-5 h-5" />
        </button>
      </div>

      <!-- Content -->
      <div class="p-6 space-y-4 overflow-y-auto flex-1">
        {#if error}
          <div class="p-3.5 rounded-xl bg-rose-950/60 border border-rose-800/80 text-rose-300 text-xs flex items-center gap-2">
            <AlertCircle class="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        {/if}

        {#if successMsg}
          <div class="p-3.5 rounded-xl bg-emerald-950/60 border border-emerald-800/80 text-emerald-300 text-xs flex items-center gap-2">
            <Check class="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        {/if}

        <!-- Control Bar -->
        <div class="flex items-center justify-between">
          <div class="text-xs font-semibold text-slate-300 uppercase tracking-wider">
            Registered Repositories ({repos.length})
          </div>
          <button
            type="button"
            on:click={() => (showAddForm = !showAddForm)}
            class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-sm transition-all"
          >
            <Plus class="w-4 h-4" />
            <span>Add GitHub Repository</span>
          </button>
        </div>

        <!-- Add Repo Form -->
        {#if showAddForm}
          <form on:submit|preventDefault={handleAddRepo} class="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
            <h3 class="text-xs font-bold text-slate-200 uppercase tracking-wider">Register New Repository</h3>

            <div>
              <label for="repo-url" class="block text-caption font-semibold text-slate-400 mb-1">
                Repository URL <span class="text-rose-400">*</span>
              </label>
              <input
                id="repo-url"
                type="url"
                required
                bind:value={newUrl}
                placeholder="https://github.com/maicen/bimguard-test-models"
                class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label for="repo-name" class="block text-caption font-semibold text-slate-400 mb-1">Display Name (Optional)</label>
                <input
                  id="repo-name"
                  type="text"
                  bind:value={newName}
                  placeholder="bimguard-test-models"
                  class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label for="repo-branch" class="block text-caption font-semibold text-slate-400 mb-1">Git Branch</label>
                <input
                  id="repo-branch"
                  type="text"
                  bind:value={newBranch}
                  placeholder="main"
                  class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            <div>
              <label for="repo-desc" class="block text-caption font-semibold text-slate-400 mb-1">Description (Optional)</label>
              <input
                id="repo-desc"
                type="text"
                bind:value={newDescription}
                placeholder="Repository containing OpenBIM test models..."
                class="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div class="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                on:click={() => (showAddForm = false)}
                class="px-3 py-1.5 rounded-xl border border-slate-800 text-slate-400 hover:text-slate-50 text-xs transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                class="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-all disabled:opacity-50"
              >
                {#if isSubmitting}
                  <Loader2 class="w-3.5 h-3.5 animate-spin" />
                  <span>Registering...</span>
                {:else}
                  <span>Save Repository</span>
                {/if}
              </button>
            </div>
          </form>
        {/if}

        <!-- Repository List -->
        {#if isLoading}
          <div class="p-8 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
            <Loader2 class="w-4 h-4 animate-spin text-blue-400" />
            <span>Loading registered repositories...</span>
          </div>
        {:else if repos.length === 0}
          <div class="p-8 text-center text-xs text-slate-500 border border-dashed border-slate-800 rounded-xl">
            No custom GitHub repositories registered yet.
          </div>
        {:else}
          <div class="space-y-2">
            {#each repos as repo}
              <div class="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800/80 hover:border-slate-700 flex items-start justify-between gap-3 transition-colors">
                <div class="space-y-1">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-semibold text-slate-50">{repo.owner}/{repo.name}</span>
                    <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-900 border border-slate-800 text-micro font-mono text-slate-400">
                      <GitBranch class="w-3 h-3 text-blue-400" />
                      {repo.branch}
                    </span>
                    {#if repo.url.includes("maicen/bimguard-test-models")}
                      <span class="px-2 py-0.5 rounded-md bg-blue-950/80 border border-blue-800/60 text-blue-300 text-micro font-semibold">
                        Default Test Repo
                      </span>
                    {/if}
                  </div>
                  {#if repo.description}
                    <p class="text-xs text-slate-400 leading-relaxed">{repo.description}</p>
                  {/if}
                  <div class="text-caption text-slate-500 flex items-center gap-2 pt-0.5">
                    <a
                      href={repo.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      class="inline-flex items-center gap-1 text-blue-400 hover:underline"
                    >
                      <span>{repo.url}</span>
                      <ExternalLink class="w-3 h-3" />
                    </a>
                  </div>
                </div>

                <div class="flex items-center gap-1.5 shrink-0">
                  <button
                    type="button"
                    on:click={() => handleDeleteRepo(repo)}
                    class="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
                    title="Remove repository"
                  >
                    <Trash2 class="w-4 h-4" />
                  </button>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div class="px-6 py-3 border-t border-slate-800 bg-slate-950/60 flex items-center justify-end">
        <button
          type="button"
          on:click={onClose}
          class="px-4 py-1.5 rounded-xl border border-slate-800 bg-slate-900 hover:bg-slate-800 text-slate-300 text-xs font-medium transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}
