<script lang="ts">
  import Modal from "./Modal.svelte";
  import { FolderGit2, Users, Check, Save } from "lucide-svelte";
  import { organizationsApi } from "../api";
  import { toasts } from "../toast.svelte";
  import { SvelteSet } from "svelte/reactivity";
  import type { Group, Project } from "../types";

  interface Props {
    open: boolean;
    project: Project | null;
    organizationId: number;
    groups: Group[];
    onClose: () => void;
    onSaved?: () => void;
  }

  let {
    open = false,
    project = null,
    organizationId,
    groups = [],
    onClose,
    onSaved = () => {},
  }: Props = $props();

  let saving = $state(false);
  let assignedGroupIds: Set<number> = new SvelteSet();
  let loadingGrants = $state(false);

  $effect(() => {
    if (open && project && organizationId) {
      loadGroupGrants();
    }
  });

  async function loadGroupGrants() {
    if (!project) return;
    loadingGrants = true;
    assignedGroupIds.clear();
    try {
      await Promise.all(
        groups.map(async (group) => {
          const res = await organizationsApi.getGroupProjectGrants(organizationId, group.id);
          if (res.project_ids.includes(project!.id)) {
            assignedGroupIds.add(group.id);
          }
        }),
      );
    } catch (err) {
      toasts.fromError(err, "Could not load current group grants.");
    } finally {
      loadingGrants = false;
    }
  }

  function toggleGroup(groupId: number) {
    if (assignedGroupIds.has(groupId)) {
      assignedGroupIds.delete(groupId);
    } else {
      assignedGroupIds.add(groupId);
    }
  }

  async function save() {
    if (!project) return;
    saving = true;
    try {
      await Promise.all(
        groups.map(async (group) => {
          const res = await organizationsApi.getGroupProjectGrants(organizationId, group.id);
          const currentSet = new Set(res.project_ids);
          const shouldHave = assignedGroupIds.has(group.id);
          if (shouldHave && !currentSet.has(project!.id)) {
            currentSet.add(project!.id);
            await organizationsApi.setGroupProjectGrants(organizationId, group.id, Array.from(currentSet));
          } else if (!shouldHave && currentSet.has(project!.id)) {
            currentSet.delete(project!.id);
            await organizationsApi.setGroupProjectGrants(organizationId, group.id, Array.from(currentSet));
          }
        }),
      );
      toasts.success("Group project access updated.");
      onSaved();
      onClose();
    } catch (err) {
      toasts.fromError(err, "Failed to update group project access.");
    } finally {
      saving = false;
    }
  }
</script>

<Modal
  isOpen={open}
  {onClose}
  title={`Project Access: ${project?.name || "Project"}`}
  icon={FolderGit2}
  maxWidth="max-w-lg"
>
  {#if project}
    <div class="space-y-4 text-xs text-slate-300">
      <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3.5">
        <div class="font-semibold text-slate-100">{project.name}</div>
        <div class="text-micro text-slate-400 font-mono mt-0.5">
          ID #{project.id} &middot; {project.country || "Global"} &middot; {project.analysis_type || "Standard"}
        </div>
        <div class="mt-2 text-micro text-slate-400">
          Select which internal organization groups have permission to view and analyze this project.
        </div>
      </div>

      <div>
        <div class="mb-2 text-micro font-bold uppercase tracking-wider text-slate-400">
          User Groups ({groups.length})
        </div>

        {#if loadingGrants}
          <div class="py-8 text-center text-slate-500">
            Loading group permissions…
          </div>
        {:else if groups.length === 0}
          <div class="rounded-xl border border-dashed border-slate-800 p-6 text-center text-slate-500">
            <Users class="mx-auto h-6 w-6 text-slate-600 mb-1" />
            <p>No user groups exist yet in this organization.</p>
            <p class="text-micro text-slate-500 mt-1">Create groups in Organization Settings &rarr; Groups.</p>
          </div>
        {:else}
          <div class="max-h-60 overflow-y-auto space-y-1.5 rounded-xl border border-slate-800 bg-slate-950 p-2">
            {#each groups as group (group.id)}
              {@const isAssigned = assignedGroupIds.has(group.id)}
              <button
                type="button"
                onclick={() => toggleGroup(group.id)}
                class="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left transition-colors {isAssigned
                  ? 'bg-violet-950/40 border border-violet-500/30 text-violet-200'
                  : 'hover:bg-slate-900 text-slate-300 border border-transparent'}"
              >
                <div class="flex items-center gap-2.5">
                  <div
                    class="flex h-6 w-6 items-center justify-center rounded-md {isAssigned
                      ? 'bg-violet-600 text-white'
                      : 'border border-slate-700 bg-slate-900 text-transparent'}"
                  >
                    <Check class="h-3.5 w-3.5 {isAssigned ? 'opacity-100' : 'opacity-0'}" />
                  </div>
                  <span class="font-medium">{group.name}</span>
                </div>
                <span class="text-micro text-slate-500 font-mono">
                  {group.member_count ?? 0} member{(group.member_count ?? 0) === 1 ? "" : "s"}
                </span>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  {/if}

  {#snippet footer()}
    <div class="flex items-center justify-end gap-2">
      <button
        type="button"
        onclick={onClose}
        disabled={saving}
        class="rounded-xl border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 transition-colors hover:bg-slate-700 disabled:opacity-50"
      >
        Cancel
      </button>
      <button
        type="button"
        onclick={save}
        disabled={saving || loadingGrants}
        class="inline-flex items-center gap-1.5 rounded-xl bg-violet-600 px-4 py-2 text-xs font-semibold text-white shadow-md shadow-violet-600/30 transition-all hover:bg-violet-500 disabled:opacity-50"
      >
        <Save class="h-3.5 w-3.5" />
        <span>{saving ? "Saving…" : "Save Access"}</span>
      </button>
    </div>
  {/snippet}
</Modal>
