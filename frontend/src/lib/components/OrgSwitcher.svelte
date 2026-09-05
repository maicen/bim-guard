<script lang="ts">
  import { Building2, ChevronDown } from "lucide-svelte";
  import { authState } from "../auth.svelte";
  import { toasts } from "../toast.svelte";

  // The one place "which tenant am I in" is decided for every other view —
  // see auth.svelte.ts activeOrganizationId, which every org-scoped screen
  // (project list, dashboard widgets, Org Settings) reads from.
  let organizations = $derived(authState.profile?.organizations ?? []);
  let activeId = $derived(authState.activeOrganizationId);
  let switching = $state(false);

  async function handleChange(e: Event) {
    const id = Number((e.target as HTMLSelectElement).value);
    if (!id || id === activeId) return;
    switching = true;
    try {
      await authState.setActiveOrganization(id);
    } catch (err) {
      toasts.fromError(err, "Could not switch organization.");
    } finally {
      switching = false;
    }
  }
</script>

{#if organizations.length > 1}
  <div
    class="hidden items-center gap-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 lg:inline-flex"
  >
    <Building2 class="h-3.5 w-3.5 shrink-0 text-violet-400" />
    <div class="relative">
      <select
        value={activeId ?? ""}
        onchange={handleChange}
        disabled={switching}
        aria-label="Switch current organization"
        class="max-w-[10rem] cursor-pointer appearance-none truncate bg-transparent py-0.5 pl-0.5 pr-4 text-xs font-medium text-violet-300 focus:outline-none disabled:opacity-60"
      >
        <option value="" disabled>Select organization…</option>
        {#each organizations as org (org.organization_id)}
          <option value={org.organization_id}>{org.name}</option>
        {/each}
      </select>
      <ChevronDown
        class="pointer-events-none absolute right-0 top-1/2 h-3 w-3 -translate-y-1/2 text-violet-400"
      />
    </div>
  </div>
{:else if organizations.length === 1}
  <span
    class="hidden items-center gap-1.5 rounded-full border border-violet-500/20 bg-violet-500/5 px-2.5 py-0.5 text-xs font-medium text-violet-300 lg:inline-flex"
    title="Your organization"
  >
    <Building2 class="h-3.5 w-3.5 shrink-0" />
    {organizations[0]!.name}
  </span>
{/if}
