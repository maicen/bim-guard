<script lang="ts">
  import { UploadCloud, X as XIcon } from "lucide-svelte";
  import Modal from "./Modal.svelte";
  import { projectsApi } from "../api";
  import { IFC_FILE_ROLES, type ProjectIfcFile } from "../types";

  interface Props {
    isOpen: boolean;
    projectId: number | null;
    onClose: () => void;
    onUploaded: (files: ProjectIfcFile[]) => void;
  }

  let { isOpen, projectId, onClose, onUploaded }: Props = $props();

  let selectedFiles: File[] = $state([]);
  let roles: string[] = $state([]);
  let primaryIndex = $state(0);
  let isSubmitting = $state(false);
  let errorMessage = $state("");

  function reset() {
    selectedFiles = [];
    roles = [];
    primaryIndex = 0;
    errorMessage = "";
  }

  function handleFileInput(e: Event) {
    const input = e.target as HTMLInputElement;
    const newFiles = Array.from(input.files || []);
    selectedFiles = [...selectedFiles, ...newFiles];
    roles = [...roles, ...newFiles.map(() => "context")];
    input.value = "";
  }

  function removeFile(index: number) {
    selectedFiles = selectedFiles.filter((_, i) => i !== index);
    roles = roles.filter((_, i) => i !== index);
    if (primaryIndex >= selectedFiles.length) primaryIndex = 0;
  }

  async function handleUpload() {
    if (!projectId || selectedFiles.length === 0) return;
    isSubmitting = true;
    errorMessage = "";
    try {
      const res = await projectsApi.uploadIfcFiles(projectId, selectedFiles, primaryIndex, roles);
      const updated = await projectsApi.listIfcFiles(projectId);
      onUploaded(updated.length ? updated : res.files);
      reset();
    } catch (err: any) {
      errorMessage = err?.message || "Upload failed.";
    } finally {
      isSubmitting = false;
    }
  }

  function handleClose() {
    if (isSubmitting) return;
    reset();
    onClose();
  }
</script>

<Modal
  {isOpen}
  title="Attach IFC Models"
  subtitle="Add primary or context models to this project"
  icon={UploadCloud}
  maxWidth="max-w-lg"
  onClose={handleClose}
>
  <div class="space-y-4">
    <label
      class="flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed border-slate-700 bg-slate-950/40 p-6 text-center transition-colors hover:border-slate-600"
    >
      <UploadCloud class="h-5 w-5 text-slate-400" />
      <span class="text-xs font-medium text-slate-300">Click to choose .ifc files</span>
      <input type="file" accept=".ifc" multiple class="hidden" onchange={handleFileInput} />
    </label>

    {#if selectedFiles.length > 0}
      <div class="space-y-2">
        {#each selectedFiles as file, i (file.name + i)}
          <div
            class="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/40 p-2.5"
          >
            <input
              type="radio"
              name="primary-file"
              checked={primaryIndex === i}
              onchange={() => (primaryIndex = i)}
              title="Set as primary model"
            />
            <span class="min-w-0 flex-1 truncate text-xs text-slate-200">{file.name}</span>
            <select
              bind:value={roles[i]}
              class="rounded-md border border-slate-700 bg-slate-900 px-1.5 py-1 text-micro text-slate-300"
            >
              {#each IFC_FILE_ROLES as role (role)}
                <option value={role}>{role}</option>
              {/each}
            </select>
            <button
              type="button"
              onclick={() => removeFile(i)}
              class="rounded p-1 text-slate-500 hover:bg-slate-800 hover:text-rose-400"
              aria-label="Remove file"
            >
              <XIcon class="h-3.5 w-3.5" />
            </button>
          </div>
        {/each}
        <p class="text-micro text-slate-500">
          Select the radio button to mark which file is the primary model.
        </p>
      </div>
    {/if}

    {#if errorMessage}
      <div class="rounded-lg border border-rose-800/60 bg-rose-950/40 p-2.5 text-xs text-rose-300">
        {errorMessage}
      </div>
    {/if}
  </div>

  {#snippet footer()}
    <button
      type="button"
      onclick={handleClose}
      disabled={isSubmitting}
      class="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 transition-colors hover:text-slate-100"
    >
      Cancel
    </button>
    <button
      type="button"
      onclick={handleUpload}
      disabled={isSubmitting || selectedFiles.length === 0 || !projectId}
      class="rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
    >
      {isSubmitting ? "Uploading…" : "Attach Models"}
    </button>
  {/snippet}
</Modal>
