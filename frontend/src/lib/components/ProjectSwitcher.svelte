<script lang="ts">
  import { Building2, ChevronDown } from "lucide-svelte";
  import { projectsApi } from "../api";
  import { authState } from "../auth.svelte";
  import type { Project } from "../types";

  interface Props {
    selectedProject: Project | null;
    /** Switch the app's current project context. */
    onSwitch: (projectId: number) => void;
  }

  let { selectedProject, onSwitch }: Props = $props();

  // Every project-scoped view (Compliance Audit, Reports, Viewer) used to
  // own an independent project dropdown with no shared "current project"
  // concept, so switching context on one screen never carried over to the
  // next — this is the one place that changes, backing every view's picker.
  let allProjects: Project[] = $state(projectsApi.getCachedList()?.projects || []);

  // Scoped to the active organization so switching projects can never land on
  // one belonging to a different tenant — see auth.svelte.ts activeOrganizationId.
  let projects = $derived(
    authState.activeOrganizationId == null
      ? allProjects
      : allProjects.filter((p) => p.organization_id === authState.activeOrganizationId),
  );

  $effect(() => {
    if (allProjects.length) return;
    projectsApi
      .list()
      .then((res) => {
        allProjects = res.projects || [];
      })
      .catch(() => {
        // Silent: this is a convenience switcher, not the primary project
        // list — ProjectsView surfaces its own load errors.
      });
  });

  function handleChange(e: Event) {
    const id = Number((e.target as HTMLSelectElement).value);
    if (id) onSwitch(id);
  }
</script>

<div
  class="ml-2 hidden items-center gap-1.5 rounded-full border border-blue-500/20 bg-blue-500/10 px-2 py-0.5 lg:inline-flex"
>
  <Building2 class="h-3.5 w-3.5 shrink-0 text-blue-400" />
  <div class="relative">
    <select
      value={selectedProject?.id ?? ""}
      onchange={handleChange}
      aria-label="Switch current project"
      class="max-w-[12rem] cursor-pointer appearance-none truncate bg-transparent py-0.5 pl-0.5 pr-4 text-xs font-medium text-blue-300 focus:outline-none"
    >
      <option value="" disabled>Select project…</option>
      {#each projects as p (p.id)}
        <option value={p.id}>{p.name}</option>
      {/each}
    </select>
    <ChevronDown
      class="pointer-events-none absolute right-0 top-1/2 h-3 w-3 -translate-y-1/2 text-blue-400"
    />
  </div>
</div>
