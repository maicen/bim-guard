<script lang="ts">
  import { run } from "svelte/legacy";

  import { X, Check, Pencil, AlertTriangle } from "lucide-svelte";
  import { bsddApi, projectsApi } from "../api";
  import type { BSDDDictionaryItem, Project } from "../types";

  interface Props {
    isOpen?: boolean;
    project?: Project | null;
    onClose: () => void;
    onProjectUpdated: (updated: Project) => void;
  }

  let { isOpen = false, project = null, onClose, onProjectUpdated }: Props = $props();

  let name = $state("");
  let description = $state("");
  let status = $state("Active");
  let country = $state("Canada");
  let analysisType = $state("Architecture");
  let classificationStandard = $state("");
  let isSaving = $state(false);
  let errorMessage = $state("");

  let classificationStandards: BSDDDictionaryItem[] = $state([]);

  run(() => {
    if (isOpen && classificationStandards.length === 0) {
      bsddApi
        .listDictionaries()
        .then((dicts) => (classificationStandards = dicts))
        .catch(() => (classificationStandards = []));
    }
  });

  run(() => {
    if (isOpen && project) {
      name = project.name || "";
      description = project.description || "";
      status = project.status || "Active";
      country = project.country || "Canada";
      analysisType = project.analysis_type || "Arch";
      classificationStandard = project.classification_standard || "";
      errorMessage = "";
    }
  });

  async function handleSave() {
    if (!project) return;
    if (!name.trim()) {
      errorMessage = "Project name is required.";
      return;
    }

    isSaving = true;
    errorMessage = "";
    try {
      const updated = await projectsApi.update(project.id, {
        name: name.trim(),
        description: description.trim(),
        status,
        country,
        analysis_type: analysisType,
        classification_standard: classificationStandard,
      });
      onProjectUpdated(updated);
      onClose();
    } catch (err: any) {
      errorMessage = err.message || "Failed to update project.";
    } finally {
      isSaving = false;
    }
  }
</script>

{#if isOpen && project}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
    <div
      class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
        <div class="flex items-center gap-2.5">
          <div class="rounded-xl border border-blue-500/20 bg-blue-500/10 p-2 text-blue-400">
            <Pencil class="h-5 w-5" />
          </div>
          <div>
            <h2 class="text-base font-bold tracking-tight text-slate-50">
              Edit Project #{project.id}
            </h2>
            <p class="text-xs text-slate-400">
              Update project metadata and regulatory configuration
            </p>
          </div>
        </div>
        <button
          type="button"
          onclick={onClose}
          class="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <!-- Body Form -->
      <div class="space-y-4 overflow-y-auto p-6">
        {#if errorMessage}
          <div
            class="flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300"
          >
            <AlertTriangle class="h-4 w-4 shrink-0 text-rose-400" />
            <span>{errorMessage}</span>
          </div>
        {/if}

        <div class="space-y-1.5">
          <label for="edit-proj-name" class="block text-xs font-semibold text-slate-300">
            Project Name <span class="text-rose-400">*</span>
          </label>
          <input
            id="edit-proj-name"
            type="text"
            bind:value={name}
            placeholder="e.g. Waterfront Commercial Tower"
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
          />
        </div>

        <div class="space-y-1.5">
          <label for="edit-proj-desc" class="block text-xs font-semibold text-slate-300">
            Description
          </label>
          <textarea
            id="edit-proj-desc"
            rows="3"
            bind:value={description}
            placeholder="Optional project scope or notes..."
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
          ></textarea>
        </div>

        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div class="space-y-1.5">
            <label for="edit-proj-status" class="block text-xs font-semibold text-slate-300">
              Status
            </label>
            <select
              id="edit-proj-status"
              bind:value={status}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              <option value="Active">Active</option>
              <option value="Draft">Draft</option>
              <option value="Archived">Archived</option>
            </select>
          </div>

          <div class="space-y-1.5">
            <label for="edit-proj-country" class="block text-xs font-semibold text-slate-300">
              Jurisdiction
            </label>
            <select
              id="edit-proj-country"
              bind:value={country}
              class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
            >
              <option value="Canada">Canada (NBC)</option>
              <option value="US">United States (IBC)</option>
              <option value="UK">United Kingdom</option>
              <option value="EU">European Union</option>
            </select>
          </div>
        </div>

        <div class="space-y-1.5">
          <label for="edit-proj-domain" class="block text-xs font-semibold text-slate-300">
            Analysis Domain
          </label>
          <select
            id="edit-proj-domain"
            bind:value={analysisType}
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
          >
            <option value="Arch">Arch</option>
            <option value="Piping">Piping</option>
            <option value="seismic">seismic</option>
          </select>
        </div>

        <div class="space-y-1.5">
          <label for="edit-proj-classification" class="block text-xs font-semibold text-slate-300">
            Classification Standard
          </label>
          <select
            id="edit-proj-classification"
            bind:value={classificationStandard}
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-xs text-slate-50 focus:border-accent focus:outline-none"
          >
            <option value="">Not set</option>
            {#each classificationStandards as std (std.uri)}
              <option value={std.code}>{std.name}</option>
            {/each}
          </select>
          <p class="text-caption text-slate-500">
            Element and property codes are resolved against this bSDD dictionary throughout the project.
          </p>
        </div>
      </div>

      <!-- Footer Actions -->
      <div
        class="flex items-center justify-end gap-2 border-t border-slate-800 bg-slate-950/60 px-6 py-3"
      >
        <button
          type="button"
          onclick={onClose}
          class="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isSaving || !name.trim()}
          onclick={handleSave}
          class="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:scale-[1.02] hover:bg-accent-hover disabled:opacity-50 disabled:hover:scale-100"
        >
          <Check class="h-3.5 w-3.5" />
          <span>{isSaving ? "Saving..." : "Save Changes"}</span>
        </button>
      </div>
    </div>
  </div>
{/if}
