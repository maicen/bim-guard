<script lang="ts">
  import { BookOpen, Save } from "lucide-svelte";
  import Modal from "./Modal.svelte";
  import { projectsApi, documentsApi } from "../api";
  import { toasts } from "../toast.svelte";
  import { SvelteSet } from "svelte/reactivity";
  import type { DocumentItem, Project } from "../types";

  interface Props {
    project: Project | null;
    onClose: () => void;
  }

  let { project, onClose }: Props = $props();

  // "Zero bindings unless assigned": a brand-new project starts with none of
  // these checked. `available` is this project's organization's own grant
  // from the superadmin's Document Access screen -- a project can only bind
  // a subset of it.
  let available = $state.raw<number[]>([]);
  let documentsById = $state.raw<Record<number, DocumentItem>>({});
  const selected: Set<number> = new SvelteSet();
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);

  $effect(() => {
    if (project) load(project.id);
  });

  async function load(projectId: number) {
    loading = true;
    error = null;
    try {
      const [bindings, docs] = await Promise.all([
        projectsApi.getDocumentBindings(projectId),
        documentsApi.list(),
      ]);
      available = bindings.available_document_ids;
      documentsById = Object.fromEntries(docs.map((d) => [d.id, d]));
      selected.clear();
      for (const id of bindings.document_ids) selected.add(id);
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  function toggle(documentId: number) {
    if (selected.has(documentId)) selected.delete(documentId);
    else selected.add(documentId);
  }

  async function save() {
    if (!project) return;
    saving = true;
    try {
      await projectsApi.setDocumentBindings(project.id, Array.from(selected));
      toasts.success("Document assignments updated.");
      onClose();
    } catch (err) {
      toasts.fromError(err, "Could not save document assignments.");
    } finally {
      saving = false;
    }
  }
</script>

<Modal
  isOpen={project !== null}
  title="Document Assignments"
  subtitle={project?.name}
  icon={BookOpen}
  {onClose}
>
  {#if loading}
    <p class="text-xs text-slate-500">Loading…</p>
  {:else if error}
    <p class="text-xs text-rose-400">{error}</p>
  {:else if available.length === 0}
    <p class="text-xs text-slate-500">
      This project's organization hasn't been granted any documents yet — ask the platform
      superadmin to grant one under Document Access.
    </p>
  {:else}
    <p class="mb-3 text-xs text-slate-500">
      Only documents checked here are considered relevant to this project. This controls the
      documents your organization has been granted, not the full library.
    </p>
    <div class="max-h-80 space-y-1 overflow-y-auto">
      {#each available as documentId (documentId)}
        <label
          class="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-xs text-slate-200 transition-colors hover:bg-slate-800"
        >
          <input
            type="checkbox"
            checked={selected.has(documentId)}
            onchange={() => toggle(documentId)}
            class="h-3.5 w-3.5 rounded border-slate-600 bg-slate-950 text-accent focus:ring-1 focus:ring-blue-500"
          />
          {documentsById[documentId]?.filename || `Document #${documentId}`}
        </label>
      {/each}
    </div>
  {/if}

  <div class="flex justify-end gap-2 pt-4">
    <button
      type="button"
      onclick={onClose}
      class="h-9 rounded-xl border border-slate-700 bg-slate-800 px-4 text-xs font-semibold text-slate-300 hover:bg-slate-700"
    >
      Cancel
    </button>
    {#if available.length > 0}
      <button
        type="button"
        disabled={saving}
        onclick={save}
        class="inline-flex h-9 items-center gap-1.5 rounded-xl bg-accent px-4 text-xs font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
      >
        <Save class="h-3.5 w-3.5" />
        {saving ? "Saving…" : "Save assignments"}
      </button>
    {/if}
  </div>
</Modal>
