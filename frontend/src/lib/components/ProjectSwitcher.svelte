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
    const orgId = authState.activeOrganizationId;
    projectsApi
      .list({ forceRefresh: true, organization_id: orgId })
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
  class="ml-2 hidden items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-slate-300 transition-colors hover:border-slate-700 lg:inline-flex"
>
  <Building2 class="h-3.5 w-3.5 shrink-0 text-blue-400" />
  <div class="relative">
    <select
      value={selectedProject?.id ?? ""}
      onchange={handleChange}
      aria-label="Switch current project"
      class="max-w-[12rem] cursor-pointer appearance-none truncate bg-transparent py-0.5 pl-0.5 pr-4 text-xs font-medium text-slate-200 focus:outline-none"
    >
      <option value="" disabled>Select project…</option>
      {#each projects as p (p.id)}
        <option value={p.id}>{p.name}</option>
      {/each}
    </select>
    <ChevronDown
      class="pointer-events-none absolute right-0 top-1/2 h-3 w-3 -translate-y-1/2 text-slate-400"
    />
  </div>
</div>
