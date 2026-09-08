<script lang="ts">
  import { run } from "svelte/legacy";
  import { Pencil, UploadCloud, AlertTriangle, X as XIcon } from "lucide-svelte";
  import Modal from "./Modal.svelte";
  import { projectsApi } from "../api";
  import { IFC_FILE_ROLES, type ProjectIfcFile } from "../types";

  interface Props {
    isOpen: boolean;
    projectId: number | null;
    file: ProjectIfcFile | null;
    onClose: () => void;
    onSaved: (updated: ProjectIfcFile) => void;
  }

  let { isOpen, projectId, file, onClose, onSaved }: Props = $props();

  let fileName = $state("");
  let role = $state("context");
  let projectCode = $state("");
  let originator = $state("");
  let volumeSystem = $state("");
  let level = $state("");
  let type = $state("");
  let number = $state("");
  let suitabilityCode = $state("S0");
  let revisionCode = $state("P01.01");
  let replacement: File | null = $state(null);

  let isSaving = $state(false);
  let errorMessage = $state("");

  // Re-seed the form fields whenever a different file is opened for editing.
  run(() => {
    if (isOpen && file) {
      fileName = file.file_name || "";
      role = file.role || "context";
      projectCode = file.project_code || "";
      originator = file.originator || "";
      volumeSystem = file.volume_system || "";
      level = file.level || "";
      type = file.type || "";
      number = file.number || "";
      suitabilityCode = file.suitability_code || "S0";
      revisionCode = file.revision_code || "P01.01";
      replacement = null;
      errorMessage = "";
    }
  });

  function handleReplacementInput(e: Event) {
    const input = e.target as HTMLInputElement;
    replacement = input.files?.[0] ?? null;
    input.value = "";
  }

  async function handleSave() {
    if (!projectId || file?.id == null) return;
    if (!fileName.trim()) {
      errorMessage = "File name is required.";
      return;
    }

    isSaving = true;
    errorMessage = "";
    try {
      let updated: ProjectIfcFile;
      if (replacement) {
        updated = await projectsApi.replaceIfcFile(projectId, file.id, replacement);
      }
      updated = await projectsApi.updateIfcFile(projectId, file.id, {
        file_name: fileName.trim(),
        role,
        project_code: projectCode.trim(),
        originator: originator.trim(),
        volume_system: volumeSystem.trim(),
        level: level.trim(),
        type: type.trim(),
        number: number.trim(),
        suitability_code: suitabilityCode.trim() || "S0",
        revision_code: revisionCode.trim() || "P01.01",
      });
      onSaved(updated);
    } catch (err: any) {
      errorMessage = err?.message || "Failed to save model.";
    } finally {
      isSaving = false;
    }
  }

  function handleClose() {
    if (isSaving) return;
    onClose();
  }
</script>

<Modal
  {isOpen}
  title="Edit Model"
  subtitle={file?.file_name || ""}
  icon={Pencil}
  maxWidth="max-w-lg"
  onClose={handleClose}
>
  {#if file}
    <div class="space-y-4">
      {#if errorMessage}
        <div
          class="flex items-center gap-2 rounded-xl border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300"
        >
          <AlertTriangle class="h-4 w-4 shrink-0 text-rose-400" />
          <span>{errorMessage}</span>
        </div>
      {/if}

      <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div class="space-y-1.5 sm:col-span-2">
          <label for="model-file-name" class="block text-xs font-semibold text-slate-300">
            File Name
          </label>
          <input
            id="model-file-name"
            type="text"
            bind:value={fileName}
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3.5 py-2 text-xs text-slate-50 placeholder-slate-500 focus:border-accent focus:outline-none"
          />
        </div>
        <div class="space-y-1.5">
          <label for="model-role" class="block text-xs font-semibold text-slate-300"> Role </label>
          <select
            id="model-role"
            bind:value={role}
            class="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-50 focus:border-accent focus:outline-none"
          >
            {#each IFC_FILE_ROLES as r (r)}
              <option value={r}>{r}</option>
            {/each}
          </select>
        </div>
      </div>

      <!-- Replace IFC file -->
      <div class="space-y-1.5">
        <label for="model-replace" class="block text-xs font-semibold text-slate-300">
          Replace IFC File
        </label>
        {#if replacement}
          <div
            class="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/40 p-2.5"
          >
            <span class="min-w-0 flex-1 truncate text-xs text-slate-200">{replacement.name}</span>
            <button
              type="button"
              onclick={() => (replacement = null)}
              class="rounded p-1 text-slate-500 hover:bg-slate-800 hover:text-rose-400"
              aria-label="Cancel replacement"
            >
              <XIcon class="h-3.5 w-3.5" />
            </button>
          </div>
          <p class="text-micro text-slate-500">
            The stored file swaps for this one when you save; schema, storey/element counts, and
            discipline breakdown are re-read from it.
          </p>
        {:else}
          <label
            id="model-replace"
            class="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-slate-700 bg-slate-950/40 p-3 text-center transition-colors hover:border-slate-600"
          >
            <UploadCloud class="h-4 w-4 text-slate-400" />
            <span class="text-xs font-medium text-slate-300">Click to choose a replacement .ifc file</span>
            <input type="file" accept=".ifc" class="hidden" onchange={handleReplacementInput} />
          </label>
        {/if}
      </div>

      <!-- ISO 19650 fields -->
      <div class="space-y-3 rounded-xl border border-slate-800 bg-slate-950/70 p-4">
        <div class="text-xs font-bold uppercase tracking-wider text-slate-300">
          ISO 19650 Container Naming
        </div>
        <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div class="space-y-1">
            <label for="model-project-code" class="block text-caption font-semibold text-slate-400"
              >Project Code</label
            >
            <input
              id="model-project-code"
              type="text"
              bind:value={projectCode}
              class="w-full rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 font-mono text-xs text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>
          <div class="space-y-1">
            <label for="model-originator" class="block text-caption font-semibold text-slate-400"
              >Originator</label
            >
            <input
              id="model-originator"
              type="text"
              bind:value={originator}
              class="w-full rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 font-mono text-xs text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>
          <div class="space-y-1">
            <label for="model-volume" class="block text-caption font-semibold text-slate-400"
              >Volume/System</label
            >
            <input
              id="model-volume"
              type="text"
              bind:value={volumeSystem}
              class="w-full rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 font-mono text-xs text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>
          <div class="space-y-1">
            <label for="model-level" class="block text-caption font-semibold text-slate-400"
              >Level</label
            >
            <input
              id="model-level"
              type="text"
              bind:value={level}
              class="w-full rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 font-mono text-xs text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>
          <div class="space-y-1">
            <label for="model-type" class="block text-caption font-semibold text-slate-400"
              >Type</label
            >
            <input
              id="model-type"
              type="text"
              bind:value={type}
              class="w-full rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 font-mono text-xs text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>
          <div class="space-y-1">
            <label for="model-number" class="block text-caption font-semibold text-slate-400"
              >Number</label
            >
            <input
              id="model-number"
              type="text"
              bind:value={number}
              class="w-full rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 font-mono text-xs text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>
          <div class="space-y-1">
            <label for="model-suitability" class="block text-caption font-semibold text-slate-400"
              >Suitability</label
            >
            <input
              id="model-suitability"
              type="text"
              bind:value={suitabilityCode}
              class="w-full rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 font-mono text-xs text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>
          <div class="space-y-1">
            <label for="model-revision" class="block text-caption font-semibold text-slate-400"
              >Revision</label
            >
            <input
              id="model-revision"
              type="text"
              bind:value={revisionCode}
              class="w-full rounded-lg border border-slate-800 bg-slate-900 px-2.5 py-1.5 font-mono text-xs text-slate-50 focus:border-accent focus:outline-none"
            />
          </div>
        </div>
      </div>
    </div>
  {/if}

  {#snippet footer()}
    <button
      type="button"
      onclick={handleClose}
      disabled={isSaving}
      class="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 transition-colors hover:text-slate-100"
    >
      Cancel
    </button>
    <button
      type="button"
      onclick={handleSave}
      disabled={isSaving || !projectId || file?.id == null}
      class="rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
    >
      {isSaving ? "Saving…" : "Save Changes"}
    </button>
  {/snippet}
</Modal>
