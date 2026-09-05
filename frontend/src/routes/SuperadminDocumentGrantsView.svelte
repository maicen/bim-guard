<script lang="ts">
  import { ShieldCheck, Save } from "lucide-svelte";
  import PageHeader from "../lib/components/PageHeader.svelte";
  import LoadingState from "../lib/components/LoadingState.svelte";
  import EmptyState from "../lib/components/EmptyState.svelte";
  import { organizationsApi, documentsApi } from "../lib/api";
  import { toasts } from "../lib/toast.svelte";
  import { SvelteSet } from "svelte/reactivity";
  import type { DocumentItem, OrganizationSummary } from "../lib/types";

  // Which documents (the global Rule Documents library -- no owning
  // organization, same situation rulesets were in) an organization may use
  // at all. Mirrors SuperadminRulesetsView exactly.
  let orgs = $state.raw<OrganizationSummary[]>([]);
  let documents = $state.raw<DocumentItem[]>([]);
  let grants = $state.raw<Record<number, Set<number>>>({});
  const dirty: Set<number> = new SvelteSet();
  let loading = $state(true);
  let error = $state<string | null>(null);
  let savingOrgId = $state<number | null>(null);

  async function load() {
    loading = true;
    error = null;
    try {
      const [orgRes, docs] = await Promise.all([organizationsApi.listAll(), documentsApi.list()]);
      orgs = orgRes.organizations;
      documents = [...docs].sort((a, b) => a.filename.localeCompare(b.filename));
      const nextGrants: Record<number, Set<number>> = {};
      await Promise.all(
        orgs.map(async (org) => {
          const res = await organizationsApi.getDocumentGrants(org.id);
          nextGrants[org.id] = new SvelteSet(res.document_ids);
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

  function toggle(orgId: number, documentId: number) {
    const orgGrants = grants[orgId];
    if (!orgGrants) return;
    if (orgGrants.has(documentId)) orgGrants.delete(documentId);
    else orgGrants.add(documentId);
    dirty.add(orgId);
  }

  async function saveOrg(orgId: number) {
    savingOrgId = orgId;
    try {
      await organizationsApi.setDocumentGrants(orgId, Array.from(grants[orgId] ?? []));
      dirty.delete(orgId);
      toasts.success("Document access updated.");
    } catch (err) {
      toasts.fromError(err, "Could not save document access.");
    } finally {
      savingOrgId = null;
    }
  }
</script>

<div class="space-y-6">
  <PageHeader
    category="Platform"
    title="Document Access"
    subtitle="Which documents from the Rule Documents library each organization may use."
    icon={ShieldCheck}
  />

  {#if loading}
    <LoadingState message="Loading organizations and documents…" />
  {:else if error}
    <EmptyState title="Could not load document access" description={error} icon={ShieldCheck} />
  {:else if orgs.length === 0 || documents.length === 0}
    <EmptyState
      title="Nothing to show yet"
      description="Document access needs at least one organization and one document."
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
              Document
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
          {#each documents as doc (doc.id)}
            <tr class="border-b border-slate-800/60 hover:bg-slate-900/60">
              <td class="sticky left-0 z-10 bg-slate-950/90 px-4 py-2.5">
                <div class="font-semibold text-slate-100">{doc.filename}</div>
                <div class="text-slate-500">{doc.doc_type || "—"}</div>
              </td>
              {#each orgs as org (org.id)}
                <td class="px-4 py-2.5 text-center">
                  <input
                    type="checkbox"
                    checked={grants[org.id]?.has(doc.id) ?? false}
                    onchange={() => toggle(org.id, doc.id)}
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
