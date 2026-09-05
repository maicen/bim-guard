<script lang="ts">
  import { ShieldCheck, Save } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import { organizationsApi, projectsApi } from "../lib/api";
  import { toasts } from "../lib/toast.svelte";
  import { SvelteSet } from "svelte/reactivity";
  import type { OrganizationSummary, Project } from "../lib/types";

  // Cross-org project sharing: which organizations (beyond the owner) may
  // access a project. The owner's own cell is always checked and locked --
  // this screen only manages the *extra* grants layered on top of
  // ownership, not ownership itself (see organization_project_grants).
  let orgs = $state.raw<OrganizationSummary[]>([]);
  let projects = $state.raw<Project[]>([]);
  let grants = $state.raw<Record<number, Set<number>>>({});
  const dirty: Set<number> = new SvelteSet();
  let loading = $state(true);
  let error = $state<string | null>(null);
  let savingOrgId = $state<number | null>(null);

  async function load() {
    loading = true;
    error = null;
    try {
      const [orgRes, projectRes] = await Promise.all([organizationsApi.listAll(), projectsApi.list()]);
      orgs = orgRes.organizations;
      projects = [...projectRes.projects].sort((a, b) => a.name.localeCompare(b.name));
      const nextGrants: Record<number, Set<number>> = {};
      await Promise.all(
        orgs.map(async (org) => {
          const res = await organizationsApi.getProjectGrants(org.id);
          nextGrants[org.id] = new SvelteSet(res.project_ids);
        }),
      );
      grants = nextGrants;
      dirty.clear();
    } catch (err) {
      error = err instanceof Error ? err.message : String(err);
    } finally {
      loading = false;
    }
  }

  load();

  function toggle(orgId: number, projectId: number) {
    const orgGrants = grants[orgId];
    if (!orgGrants) return;
    if (orgGrants.has(projectId)) orgGrants.delete(projectId);
    else orgGrants.add(projectId);
    dirty.add(orgId);
  }

  async function saveOrg(orgId: number) {
    savingOrgId = orgId;
    try {
      await organizationsApi.setProjectGrants(orgId, Array.from(grants[orgId] ?? []));
      dirty.delete(orgId);
      toasts.success("Project access updated.");
    } catch (err) {
      toasts.fromError(err, "Could not save project access.");
    } finally {
      savingOrgId = null;
    }
  }
</script>

<div class="space-y-6">
  <PageHeader
    category="Platform"
    title="Project Access"
    subtitle="Cross-org project sharing — which other organizations (beyond the owner) may access each project."
    icon={ShieldCheck}
  />

  {#if loading}
    <LoadingState message="Loading organizations and projects…" />
  {:else if error}
    <EmptyState title="Could not load project access" description={error} icon={ShieldCheck} />
  {:else if orgs.length === 0 || projects.length === 0}
    <EmptyState
      title="Nothing to show yet"
      description="Project access needs at least one organization and one project."
      icon={ShieldCheck}
    />
  {:else}
    <div class="overflow-x-auto rounded-2xl border border-slate-800 bg-slate-900/40">
      <table class="w-full text-left text-xs">
        <thead>
          <tr class="border-b border-slate-800">
            <th
              class="sticky left-0 z-10 min-w-[16rem] bg-slate-900 py-3 px-4 text-caption font-semibold uppercase tracking-wider text-slate-400"
            >
              Project
            </th>
            {#each orgs as org (org.id)}
              <th class="min-w-[10rem] px-4 py-3 text-center">
                <div class="font-semibold text-slate-100">{org.name}</div>
                <button
                  type="button"
                  disabled={!dirty.has(org.id) || savingOrgId === org.id}
                  onclick={() => saveOrg(org.id)}
                  class="mt-1 inline-flex items-center gap-1 rounded-lg border border-slate-700 px-2 py-0.5 text-micro font-medium text-slate-300 transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Save class="h-3 w-3" />
                  {savingOrgId === org.id ? "Saving…" : dirty.has(org.id) ? "Save" : "Saved"}
                </button>
              </th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each projects as project (project.id)}
            <tr class="border-b border-slate-800/60 hover:bg-slate-900/60">
              <td class="sticky left-0 z-10 bg-slate-950/90 px-4 py-2.5">
                <div class="font-semibold text-slate-100">{project.name}</div>
                <div class="text-slate-500">#{project.id}</div>
              </td>
              {#each orgs as org (org.id)}
                {@const isOwner = project.organization_id === org.id}
                <td class="px-4 py-2.5 text-center">
                  {#if isOwner}
                    <input
                      type="checkbox"
                      checked
                      disabled
                      title="Owning organization -- not managed here"
                      class="h-4 w-4 rounded border-slate-700 bg-slate-800 text-slate-500"
                    />
                  {:else}
                    <input
                      type="checkbox"
                      checked={grants[org.id]?.has(project.id) ?? false}
                      onchange={() => toggle(org.id, project.id)}
                      class="h-4 w-4 rounded border-slate-600 bg-slate-950 text-accent focus:ring-1 focus:ring-blue-500"
                    />
                  {/if}
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
