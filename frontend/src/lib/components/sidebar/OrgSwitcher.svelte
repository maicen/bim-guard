<script lang="ts">
  import { Building2, ChevronsUpDown, Check, Settings } from "lucide-svelte";
  import { DropdownMenu as Menu } from "bits-ui";
  import DropdownMenu from "../DropdownMenu.svelte";
  import Tooltip from "../Tooltip.svelte";
  import { authState } from "../../auth.svelte";
  import { toasts } from "../../toast.svelte";
  import { push } from "svelte-spa-router";
  import { cn } from "../../utils/cn";

  interface Props {
    collapsed?: boolean;
    class?: string;
  }

  let { collapsed = false, class: className }: Props = $props();

  let organizations = $derived(authState.profile?.organizations ?? []);
  let activeId = $derived(authState.activeOrganizationId);
  let activeOrg = $derived(organizations.find((org) => org.organization_id === activeId));
  let activeName = $derived(activeOrg?.name || "BIM Guard");
  let activeRole = $derived(activeOrg?.role || "OpenBIM Workspace");

  let switching = $state(false);

  async function handleSelectOrg(id: number) {
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

  function goToOrgSettings() {
    const orgId = authState.activeOrganizationId;
    push(orgId ? `/org-settings?org=${orgId}` : "/org-settings");
  }

  const ITEM_CLASS =
    "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-fg-secondary transition-colors data-highlighted:bg-surface-hover data-highlighted:text-fg-primary cursor-pointer select-none";
</script>

<DropdownMenu
  width="w-64"
  align="start"
  side={collapsed ? "right" : "bottom"}
  sideOffset={8}
>
  {#snippet trigger({ props })}
    {#if !collapsed}
      <button
        type="button"
        {...props}
        class={cn(
          "flex w-full items-center gap-2.5 rounded-xl p-1.5 text-left transition-colors hover:bg-surface-hover focus-visible:outline-2 focus-visible:outline-accent outline-hidden",
          className,
        )}
        aria-label="Select organization"
      >
        <div
          class="flex aspect-square size-8 shrink-0 items-center justify-center rounded-lg bg-surface-card border border-border-default text-accent font-bold shadow-xs"
        >
          <Building2 class="size-4" />
        </div>
        <div class="grid flex-1 text-left text-xs leading-tight min-w-0">
          <span class="truncate font-bold text-fg-primary">{activeName}</span>
          <span class="truncate text-nano text-fg-muted font-medium capitalize mt-0.5"
            >{activeRole}</span
          >
        </div>
        <ChevronsUpDown class="ml-auto size-4 text-fg-muted shrink-0" />
      </button>
    {:else}
      <Tooltip text={activeName} side="right" sideOffset={8}>
        {#snippet trigger()}
          <button
            type="button"
            {...props}
            class={cn(
              "flex aspect-square size-8 mx-auto items-center justify-center rounded-lg bg-surface-card border border-border-default text-accent font-bold shadow-xs hover:border-border-interactive transition-colors focus-visible:outline-2 focus-visible:outline-accent outline-hidden",
              className,
            )}
            aria-label="Select organization"
          >
            <Building2 class="size-4" />
          </button>
        {/snippet}
      </Tooltip>
    {/if}
  {/snippet}

  <div class="px-2.5 py-1 text-nano font-bold uppercase tracking-wider text-fg-muted">
    Organizations
  </div>

  {#if organizations.length > 0}
    {#each organizations as org (org.organization_id)}
      {@const isSelected = org.organization_id === activeId}
      <Menu.Item
        onSelect={() => handleSelectOrg(org.organization_id)}
        class={ITEM_CLASS}
      >
        <div
          class={cn(
            "flex aspect-square size-6 shrink-0 items-center justify-center rounded-md border text-nano font-bold",
            isSelected
              ? "border-accent bg-accent/10 text-accent"
              : "border-border-default bg-surface-overlay text-fg-muted",
          )}
        >
          <Building2 class="size-3" />
        </div>
        <div class="flex flex-col min-w-0 flex-1">
          <span class={cn("truncate", isSelected ? "font-bold text-fg-primary" : "")}
            >{org.name}</span
          >
          <span class="text-nano text-fg-muted capitalize">{org.role}</span>
        </div>
        {#if isSelected}
          <Check class="size-4 text-accent shrink-0 ml-auto" />
        {/if}
      </Menu.Item>
    {/each}
  {:else}
    <div class="px-2.5 py-2 text-xs text-fg-muted">
      No organizations found
    </div>
  {/if}

  {#if activeOrg?.role === "owner" || activeOrg?.role === "admin" || authState.isSuperadmin}
    <div class="my-1 h-px bg-border-default/60"></div>
    <Menu.Item onSelect={goToOrgSettings} class={ITEM_CLASS}>
      <Settings class="size-3.5 text-fg-muted" />
      <span>Organization settings</span>
    </Menu.Item>
  {/if}
</DropdownMenu>
