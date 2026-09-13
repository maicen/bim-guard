<script lang="ts">
  import { UploadCloud, X as XIcon } from "lucide-svelte";
  import Modal from "./Modal.svelte";
  import Tooltip from "./Tooltip.svelte";
  import { RadioGroupRoot, RadioGroupItem, Select, type SelectOption } from "./ui";
  import { modelsApi } from "../api";
  import { IFC_FILE_ROLES, type Model } from "../types";

  interface Props {
    isOpen: boolean;
    projectId: number | null;
    onClose: () => void;
    onUploaded: (files: Model[]) => void;
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
      const res = await modelsApi.upload(projectId, selectedFiles, primaryIndex, roles);
      const updated = await modelsApi.list(projectId);
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
  const roleOptions: SelectOption[] = IFC_FILE_ROLES.map((r) => ({ value: r, label: r }));
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
      class="flex cursor-pointer flex-col items-center gap-2 rounded-xl border border-dashed border-border-interactive bg-surface-canvas/40 p-6 text-center transition-colors hover:border-border-interactive"
    >
      <UploadCloud class="h-5 w-5 text-fg-muted" />
      <span class="text-xs font-medium text-fg-secondary">Click to choose .ifc files</span>
      <input type="file" accept=".ifc" multiple class="hidden" onchange={handleFileInput} />
    </label>

    {#if selectedFiles.length > 0}
      <div class="space-y-2">
        <RadioGroupRoot
          value={String(primaryIndex)}
          onValueChange={(val) => (primaryIndex = Number(val))}
          class="space-y-2"
        >
          {#each selectedFiles as file, i (file.name + i)}
            <div
              class="flex items-center gap-2 rounded-lg border border-border-default bg-surface-canvas/40 p-2.5"
            >
              <Tooltip content="Set as primary model">
                <RadioGroupItem value={String(i)} aria-label="Set as primary model" />
              </Tooltip>
              <span class="min-w-0 flex-1 truncate text-xs text-fg-secondary">{file.name}</span>
              <div class="w-32 shrink-0">
                <Select options={roleOptions} bind:value={roles[i]} />
              </div>
              <button
                type="button"
                onclick={() => removeFile(i)}
                class="rounded p-1 text-fg-muted hover:bg-critical-bg hover:text-critical"
                aria-label="Remove file"
              >
                <XIcon class="h-3.5 w-3.5" />
              </button>
            </div>
          {/each}
        </RadioGroupRoot>
        <p class="text-micro text-fg-muted">
          Select the radio button to mark which file is the primary model.
        </p>
      </div>
    {/if}

    {#if errorMessage}
      <div class="rounded-lg border border-critical-border bg-critical-bg p-2.5 text-xs text-critical">
        {errorMessage}
      </div>
    {/if}
  </div>

  {#snippet footer()}
    <button
      type="button"
      onclick={handleClose}
      disabled={isSubmitting}
      class="rounded-xl px-4 py-2 text-xs font-semibold text-fg-muted transition-colors hover:text-fg-primary"
    >
      Cancel
    </button>
    <button
      type="button"
      onclick={handleUpload}
      disabled={isSubmitting || selectedFiles.length === 0 || !projectId}
      class="rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-white shadow-xs shadow-blue-500/20 transition-all hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
    >
      {isSubmitting ? "Uploading…" : "Attach Models"}
    </button>
  {/snippet}
</Modal>
