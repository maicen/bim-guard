<script lang="ts">
  import { Building2, Check, ChevronDown } from "lucide-svelte";
  import { Select } from "bits-ui";
  import { authState } from "../auth.svelte";
  import { toasts } from "../toast.svelte";
  import { cn } from "../utils/cn";

  // The one place "which tenant am I in" is decided for every other view —
  // see auth.svelte.ts activeOrganizationId, which every org-scoped screen
  // (project list, dashboard widgets, Org Settings) reads from.
  let organizations = $derived(authState.profile?.organizations ?? []);
  let activeId = $derived(authState.activeOrganizationId);
  let switching = $state(false);

  // Select's value is string-based; organization ids are numeric. Convert at
  // this boundary only — `authState.activeOrganizationId` stays the numeric
  // source of truth everywhere else.
  let selectValue = $derived(activeId != null ? String(activeId) : "");
  // Select.Value only knows an item's label once that Item has actually
  // rendered/registered during this session — on a fresh, programmatically
  // set `value` it falls back to showing the raw value string. Look the name
  // up ourselves instead of relying on that.
  let activeName = $derived(organizations.find((org) => org.organization_id === activeId)?.name ?? "");

  async function handleValueChange(value: string) {
    const id = Number(value);
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
  <Select.Root type="single" value={selectValue} onValueChange={handleValueChange} disabled={switching}>
    <Select.Trigger>
      {#snippet child({ props })}
        <button
          type="button"
          {...props}
          class={cn(
            "hidden items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-slate-300 transition-colors hover:border-slate-700 disabled:opacity-60 lg:inline-flex",
          )}
        >
          <Building2 class="h-3.5 w-3.5 shrink-0 text-violet-400" />
          <Select.Value class="max-w-40 truncate text-xs font-medium text-slate-200">
            {#snippet children({ placeholder })}
              {placeholder ? "Select organization…" : activeName}
            {/snippet}
          </Select.Value>
          <ChevronDown class="h-3 w-3 shrink-0 text-slate-400" />
        </button>
      {/snippet}
    </Select.Trigger>

    <Select.Portal>
      <Select.Content
        class="z-40 max-h-64 w-56 space-y-1 overflow-y-auto rounded-xl border border-slate-800 bg-slate-900 p-1.5 text-xs shadow-xl outline-hidden data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
      >
        {#each organizations as org (org.organization_id)}
          <Select.Item
            value={String(org.organization_id)}
            label={org.name}
            class="flex items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-left font-medium text-slate-300 data-highlighted:bg-slate-800 data-highlighted:text-slate-50"
          >
            {#snippet children({ selected })}
              <span class="truncate">{org.name}</span>
              {#if selected}
                <Check class="h-3.5 w-3.5 shrink-0 text-accent" />
              {/if}
            {/snippet}
          </Select.Item>
        {/each}
      </Select.Content>
    </Select.Portal>
  </Select.Root>
{:else if organizations.length === 1}
  <span
    class="hidden items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-xs font-medium text-slate-300 lg:inline-flex"
    title="Your organization"
  >
    <Building2 class="h-3.5 w-3.5 shrink-0 text-violet-400" />
    {organizations[0]!.name}
  </span>
{/if}
