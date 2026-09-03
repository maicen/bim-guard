<script lang="ts">
  import { run, preventDefault } from "svelte/legacy";

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
  import ConfirmModal from "./ConfirmModal.svelte";

  interface Props {
    isOpen?: boolean;
    onClose?: () => void;
    onReposUpdated?: () => void;
  }

  let { isOpen = false, onClose = () => {}, onReposUpdated = () => {} }: Props = $props();

  let repos: GitHubRepo[] = $state([]);
  let isLoading = $state(false);
  let isSubmitting = $state(false);
  let error = $state("");
  let successMsg = $state("");

  // Add Form state
  let showAddForm = $state(false);
  let newUrl = $state("");
  let newName = $state("");
  let newBranch = $state("main");
  let newDescription = $state("");

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

  run(() => {
    if (isOpen) {
      loadRepos();
      showAddForm = false;
      error = "";
      successMsg = "";
    }
  });

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

  let repoPendingDelete: GitHubRepo | null = $state(null);

  function promptDeleteRepo(repo: GitHubRepo) {
    repoPendingDelete = repo;
  }

  async function handleDeleteRepo() {
    const repo = repoPendingDelete;
    if (!repo) return;

    try {
      await githubReposApi.delete(repo.id);
      repos = repos.filter((r) => r.id !== repo.id);
      successMsg = `Repository '${repo.name}' removed.`;
      onReposUpdated();
    } catch (err: any) {
      error = err.message || "Could not delete repository.";
    } finally {
      repoPendingDelete = null;
    }
  }
</script>

{#if isOpen}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
  >
    <div
      class="relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <!-- Header -->
      <div
        class="flex items-center justify-between border-b border-slate-800 bg-slate-950/50 px-6 py-4"
      >
        <div class="flex items-center gap-2.5">
          <div class="rounded-xl border border-blue-800/50 bg-blue-950/60 p-2 text-blue-400">
            <FolderGit2 class="h-5 w-5" />
          </div>
          <div>
            <h2 class="text-lg font-semibold text-slate-50">GitHub Project Storage Repositories</h2>
            <p class="text-xs text-slate-400">
              Manage external GitHub repositories hosting OpenBIM IFC models.
            </p>
          </div>
        </div>
        <button
          type="button"
          onclick={onClose}
          class="rounded-xl p-2 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <!-- Content -->
      <div class="flex-1 space-y-4 overflow-y-auto p-6">
        {#if error}
          <div
            class="flex items-center gap-2 rounded-xl border border-rose-800/80 bg-rose-950/60 p-3.5 text-xs text-rose-300"
          >
            <AlertCircle class="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        {/if}

        {#if successMsg}
          <div
            class="flex items-center gap-2 rounded-xl border border-emerald-800/80 bg-emerald-950/60 p-3.5 text-xs text-emerald-300"
          >
            <Check class="h-4 w-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        {/if}

        <!-- Control Bar -->
        <div class="flex items-center justify-between">
          <div class="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Registered Repositories ({repos.length})
          </div>
          <button
            type="button"
            onclick={() => (showAddForm = !showAddForm)}
            class="flex items-center gap-1.5 rounded-xl bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-all hover:bg-blue-500"
          >
            <Plus class="h-4 w-4" />
            <span>Add GitHub Repository</span>
          </button>
        </div>

        <!-- Add Repo Form -->
        {#if showAddForm}
          <form
            onsubmit={preventDefault(handleAddRepo)}
            class="space-y-3 rounded-xl border border-slate-800 bg-slate-950 p-4"
          >
            <h3 class="text-xs font-bold uppercase tracking-wider text-slate-200">
              Register New Repository
            </h3>

            <div>
              <label for="repo-url" class="mb-1 block text-caption font-semibold text-slate-400">
                Repository URL <span class="text-rose-400">*</span>
              </label>
              <input
                id="repo-url"
                type="url"
                required
                bind:value={newUrl}
                placeholder="https://github.com/maicen/bimguard-test-models"
                class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
              />
            </div>

            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label for="repo-name" class="mb-1 block text-caption font-semibold text-slate-400"
                  >Display Name (Optional)</label
                >
                <input
                  id="repo-name"
                  type="text"
                  bind:value={newName}
                  placeholder="bimguard-test-models"
                  class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label
                  for="repo-branch"
                  class="mb-1 block text-caption font-semibold text-slate-400">Git Branch</label
                >
                <input
                  id="repo-branch"
                  type="text"
                  bind:value={newBranch}
                  placeholder="main"
                  class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label for="repo-desc" class="mb-1 block text-caption font-semibold text-slate-400"
                >Description (Optional)</label
              >
              <input
                id="repo-desc"
                type="text"
                bind:value={newDescription}
                placeholder="Repository containing OpenBIM test models..."
                class="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
              />
            </div>

            <div class="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onclick={() => (showAddForm = false)}
                class="rounded-xl border border-slate-800 px-3 py-1.5 text-xs text-slate-400 transition-colors hover:text-slate-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                class="flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white transition-all hover:bg-blue-500 disabled:opacity-50"
              >
                {#if isSubmitting}
                  <Loader2 class="h-3.5 w-3.5 animate-spin" />
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
          <div
            class="flex items-center justify-center gap-2 p-8 text-center text-xs text-slate-500"
          >
            <Loader2 class="h-4 w-4 animate-spin text-blue-400" />
            <span>Loading registered repositories...</span>
          </div>
        {:else if repos.length === 0}
          <div
            class="rounded-xl border border-dashed border-slate-800 p-8 text-center text-xs text-slate-500"
          >
            No custom GitHub repositories registered yet.
          </div>
        {:else}
          <div class="space-y-2">
            {#each repos as repo}
              <div
                class="flex items-start justify-between gap-3 rounded-xl border border-slate-800/80 bg-slate-950/80 p-3.5 transition-colors hover:border-slate-700"
              >
                <div class="space-y-1">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-semibold text-slate-50">{repo.owner}/{repo.name}</span
                    >
                    <span
                      class="inline-flex items-center gap-1 rounded-md border border-slate-800 bg-slate-900 px-2 py-0.5 font-mono text-micro text-slate-400"
                    >
                      <GitBranch class="h-3 w-3 text-blue-400" />
                      {repo.branch}
                    </span>
                    {#if repo.url.includes("maicen/bimguard-test-models")}
                      <span
                        class="rounded-md border border-blue-800/60 bg-blue-950/80 px-2 py-0.5 text-micro font-semibold text-blue-300"
                      >
                        Default Test Repo
                      </span>
                    {/if}
                  </div>
                  {#if repo.description}
                    <p class="text-xs leading-relaxed text-slate-400">{repo.description}</p>
                  {/if}
                  <div class="flex items-center gap-2 pt-0.5 text-caption text-slate-500">
                    <a
                      href={repo.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      class="inline-flex items-center gap-1 text-blue-400 hover:underline"
                    >
                      <span>{repo.url}</span>
                      <ExternalLink class="h-3 w-3" />
                    </a>
                  </div>
                </div>

                <div class="flex shrink-0 items-center gap-1.5">
                  <button
                    type="button"
                    onclick={() => promptDeleteRepo(repo)}
                    class="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-rose-950/30 hover:text-rose-400"
                    title="Remove repository"
                  >
                    <Trash2 class="h-4 w-4" />
                  </button>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Footer -->
      <div
        class="flex items-center justify-end border-t border-slate-800 bg-slate-950/60 px-6 py-3"
      >
        <button
          type="button"
          onclick={onClose}
          class="rounded-xl border border-slate-800 bg-slate-900 px-4 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-800"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}

<ConfirmModal
  isOpen={repoPendingDelete !== null}
  title="Remove Repository"
  message={`Remove repository '${repoPendingDelete?.owner ?? ""}/${repoPendingDelete?.name ?? ""}' from storage options? Imported projects are not affected.`}
  confirmText="Remove Repository"
  danger={true}
  onConfirm={handleDeleteRepo}
  onCancel={() => (repoPendingDelete = null)}
/>
