<script lang="ts">
  import { ShieldCheck, Save } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import { organizationsApi, rulesApi } from "../lib/api";
  import { toasts } from "../lib/toast.svelte";
  import { SvelteSet } from "svelte/reactivity";
  import type { OrganizationSummary, RuleFolder } from "../lib/types";

  // Which rulesets (rule_folders.ruleset_id) each organization may use at
  // all -- the platform-wide grant this app's projects/models/docs never
  // needed, since those are already scoped by organization_id on the row
  // itself (see RulesetAccessService). A project can only bind what its own
  // organization is granted here.
  //
  // Each org's Set is itself a SvelteSet, mutated in place by toggle() --
  // that's what keeps its checkboxes reactive without needing to replace
  // the whole `grants` object on every click.
  let orgs = $state.raw<OrganizationSummary[]>([]);
  let rulesets = $state.raw<RuleFolder[]>([]);
  let grants = $state.raw<Record<number, Set<string>>>({});
  const dirty: Set<number> = new SvelteSet();
  let loading = $state(true);
  let error = $state<string | null>(null);
  let savingOrgId = $state<number | null>(null);

  async function load() {
    loading = true;
    error = null;
    try {
      const [orgRes, folderRes] = await Promise.all([organizationsApi.listAll(), rulesApi.folders()]);
      orgs = orgRes.organizations;
      rulesets = folderRes;
      const nextGrants: Record<number, Set<string>> = {};
      await Promise.all(
        orgs.map(async (org) => {
          const res = await organizationsApi.getRulesetGrants(org.id);
          nextGrants[org.id] = new SvelteSet(res.ruleset_ids);
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

  function toggle(orgId: number, rulesetId: string) {
    const orgGrants = grants[orgId];
    if (!orgGrants) return;
    if (orgGrants.has(rulesetId)) orgGrants.delete(rulesetId);
    else orgGrants.add(rulesetId);
    dirty.add(orgId);
  }

  async function saveOrg(orgId: number) {
    savingOrgId = orgId;
    try {
      await organizationsApi.setRulesetGrants(orgId, Array.from(grants[orgId] ?? []));
      dirty.delete(orgId);
      toasts.success("Ruleset access updated.");
    } catch (err) {
      toasts.fromError(err, "Could not save ruleset access.");
    } finally {
      savingOrgId = null;
    }
  }
</script>

<div class="space-y-6">
  <PageHeader
    category="Platform"
    title="Ruleset Access"
    subtitle="Which rulesets each organization may use. A project can only bind what its own organization is granted here."
    icon={ShieldCheck}
  />

  {#if loading}
    <LoadingState message="Loading organizations and rulesets…" />
  {:else if error}
    <EmptyState title="Could not load ruleset access" description={error} icon={ShieldCheck} />
  {:else if orgs.length === 0 || rulesets.length === 0}
    <EmptyState
      title="Nothing to show yet"
      description="Ruleset access needs at least one organization and one rule folder."
      icon={ShieldCheck}
    />
  {:else}
    <div class="overflow-x-auto rounded-2xl border border-slate-800 bg-slate-900/40">
      <table class="w-full text-left text-xs">
        <thead>
          <tr class="border-b border-slate-800">
            <th
              class="sticky left-0 z-10 min-w-[14rem] bg-slate-900 py-3 px-4 text-caption font-semibold uppercase tracking-wider text-slate-400"
            >
              Ruleset
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
          {#each rulesets as ruleset (ruleset.ruleset_id)}
            <tr class="border-b border-slate-800/60 hover:bg-slate-900/60">
              <td class="sticky left-0 z-10 bg-slate-950/90 px-4 py-2.5">
                <div class="font-semibold text-slate-100">{ruleset.display_name}</div>
                <div class="text-slate-500">{ruleset.ruleset_id}</div>
              </td>
              {#each orgs as org (org.id)}
                <td class="px-4 py-2.5 text-center">
                  <input
                    type="checkbox"
                    checked={grants[org.id]?.has(ruleset.ruleset_id) ?? false}
                    onchange={() => toggle(org.id, ruleset.ruleset_id)}
                    class="h-4 w-4 rounded border-slate-600 bg-slate-950 text-accent focus:ring-1 focus:ring-blue-500"
                  />
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
