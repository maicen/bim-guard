<script lang="ts">
  import { Building2 } from "lucide-svelte";
  import { authState } from "../auth.svelte";
  import { toasts } from "../toast.svelte";

  // Blocks entry into the app for a signed-in user who belongs to more than
  // one organization and has never chosen a default — the alternative is the
  // backend silently picking their first membership (see
  // `_primary_organization_id` in app/api/projects.py), which risks a
  // coordinator editing the wrong tenant's data without noticing. No close
  // affordance on purpose: a choice is required, not optional.
  let organizations = $derived(authState.profile?.organizations ?? []);
  let choosing = $state<number | null>(null);

  async function choose(organizationId: number) {
    choosing = organizationId;
    try {
      await authState.setActiveOrganization(organizationId);
    } catch (err) {
      toasts.fromError(err, "Could not set your organization.");
    } finally {
      choosing = null;
    }
  }
</script>

<div
  class="fixed inset-0 z-[100] flex items-center justify-center bg-black/85 p-4 backdrop-blur-md"
  role="dialog"
  aria-modal="true"
  aria-labelledby="org-picker-title"
>
  <div
    class="w-full max-w-md rounded-2xl border border-violet-800/50 bg-slate-900 p-6 shadow-2xl"
  >
    <div class="mb-4 flex items-center gap-3">
      <div
        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-violet-700/60 bg-violet-950/60 text-violet-300"
      >
        <Building2 class="h-5 w-5" />
      </div>
      <div>
        <h2 id="org-picker-title" class="text-base font-bold tracking-tight text-slate-50">
          Choose your organization
        </h2>
        <p class="mt-0.5 text-xs text-slate-400">
          You belong to more than one — pick which one to work in first.
        </p>
      </div>
    </div>

    <div class="space-y-2">
      {#each organizations as org (org.organization_id)}
        <button
          type="button"
          onclick={() => choose(org.organization_id)}
          disabled={choosing !== null}
          class="flex w-full items-center justify-between rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-left transition-colors hover:border-violet-700/60 hover:bg-violet-950/30 disabled:opacity-60"
        >
          <span>
            <span class="block text-sm font-semibold text-slate-100">{org.name}</span>
            <span class="block text-xs capitalize text-slate-500">{org.role}</span>
          </span>
          {#if choosing === org.organization_id}
            <span class="text-xs text-violet-400">Switching…</span>
          {/if}
        </button>
      {/each}
    </div>

    <p class="mt-4 text-xs text-slate-500">
      You can switch organizations anytime from the header.
    </p>
  </div>
</div>
