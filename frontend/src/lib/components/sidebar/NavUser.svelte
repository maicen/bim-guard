<script lang="ts">
  import {
    LogOut,
    LogIn,
    Settings,
    Building2,
    ShieldCheck,
    FolderKanban,
    BookOpen,
    ChevronsUpDown,
  } from "lucide-svelte";
  import { DropdownMenu as Menu } from "bits-ui";
  import { push } from "svelte-spa-router";
  import { authState } from "../../auth.svelte";
  import { isAuthConfigured } from "../../supabaseClient";
  import DropdownMenu from "../DropdownMenu.svelte";
  import Tooltip from "../Tooltip.svelte";
  import { Avatar } from "../ui";
  import { cn } from "../../utils/cn";

  interface Props {
    collapsed?: boolean;
    class?: string;
  }

  let { collapsed = false, class: className }: Props = $props();

  let displayName = $derived(authState.profile?.profile.full_name || authState.user?.email || "User");
  let avatarUrl = $derived(authState.profile?.profile.avatar_url || "");
  let initials = $derived.by(() => {
    const source = authState.profile?.profile.full_name || authState.user?.email || "";
    return source ? source[0]!.toUpperCase() : "U";
  });
  let activeOrg = $derived(authState.activeOrganization);
  let canManageOrg = $derived(activeOrg?.role === "owner" || activeOrg?.role === "admin");
  let isSuperadmin = $derived(authState.profile?.profile.is_superadmin ?? false);

  const ITEM_CLASS =
    "flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-fg-secondary transition-colors data-highlighted:bg-surface-hover data-highlighted:text-fg-primary cursor-pointer select-none";

  function goToProfile() {
    const orgId = authState.activeOrganizationId;
    push(orgId ? `/settings?org=${orgId}` : "/settings");
  }

  function goToOrgSettings() {
    const orgId = authState.activeOrganizationId;
    push(orgId ? `/org-settings?org=${orgId}` : "/org-settings");
  }

  function goToSuperadminRulesets() {
    const orgId = authState.activeOrganizationId;
    push(orgId ? `/superadmin-rulesets?org=${orgId}` : "/superadmin-rulesets");
  }

  function goToSuperadminProjectGrants() {
    const orgId = authState.activeOrganizationId;
    push(orgId ? `/superadmin-project-grants?org=${orgId}` : "/superadmin-project-grants");
  }

  function goToSuperadminDocumentGrants() {
    const orgId = authState.activeOrganizationId;
    push(orgId ? `/superadmin-document-grants?org=${orgId}` : "/superadmin-document-grants");
  }

  async function handleSignOut() {
    await authState.signOut();
  }
</script>

{#if !isAuthConfigured}
  <!-- Auth not configured -->
{:else if authState.loading}
  <div class="flex items-center gap-2 p-1.5">
    <span class="h-8 w-8 animate-pulse rounded-full bg-surface-overlay"></span>
    {#if !collapsed}
      <div class="space-y-1 flex-1">
        <div class="h-3 w-20 animate-pulse rounded bg-surface-overlay"></div>
        <div class="h-2.5 w-32 animate-pulse rounded bg-surface-overlay"></div>
      </div>
    {/if}
  </div>
{:else if authState.user}
  <DropdownMenu
    width="w-60"
    align="end"
    side={collapsed ? "right" : "top"}
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
          aria-label="User account menu"
        >
          <Avatar src={avatarUrl} fallback={initials} size="sm" />
          <div class="grid flex-1 text-left text-xs leading-tight min-w-0">
            <span class="truncate font-semibold text-fg-primary">{displayName}</span>
            <span class="truncate text-nano text-fg-muted font-normal">{authState.user.email}</span>
          </div>
          <ChevronsUpDown class="ml-auto size-4 text-fg-muted shrink-0" />
        </button>
      {:else}
        <Tooltip text={displayName} side="right" sideOffset={8}>
          {#snippet trigger()}
            <button
              type="button"
              {...props}
              class={cn(
                "flex size-8 mx-auto items-center justify-center rounded-full hover:scale-105 transition-transform focus-visible:outline-2 focus-visible:outline-accent outline-hidden",
                className,
              )}
              aria-label="User account menu"
            >
              <Avatar src={avatarUrl} fallback={initials} size="sm" />
            </button>
          {/snippet}
        </Tooltip>
      {/if}
    {/snippet}

    <div class="px-2.5 py-2 border-b border-border-default/60">
      <p class="truncate text-xs font-semibold text-fg-primary">{displayName}</p>
      <p class="truncate text-nano text-fg-muted">{authState.user.email}</p>
      {#if activeOrg}
        <p class="truncate text-nano capitalize text-accent font-medium mt-0.5">
          {activeOrg.name} &middot; {activeOrg.role}
        </p>
      {/if}
    </div>

    <div class="py-1">
      <Menu.Item onSelect={goToProfile} class={ITEM_CLASS}>
        <Settings class="h-3.5 w-3.5 text-fg-muted" />
        <span>Profile & Account</span>
      </Menu.Item>

      {#if canManageOrg}
        <Menu.Item onSelect={goToOrgSettings} class={ITEM_CLASS}>
          <Building2 class="h-3.5 w-3.5 text-fg-muted" />
          <span>Organization settings</span>
        </Menu.Item>
      {/if}

      {#if isSuperadmin}
        <Menu.Item onSelect={goToSuperadminRulesets} class={ITEM_CLASS}>
          <ShieldCheck class="h-3.5 w-3.5 text-fg-muted" />
          <span>Ruleset access</span>
        </Menu.Item>
        <Menu.Item onSelect={goToSuperadminProjectGrants} class={ITEM_CLASS}>
          <FolderKanban class="h-3.5 w-3.5 text-fg-muted" />
          <span>Project access</span>
        </Menu.Item>
        <Menu.Item onSelect={goToSuperadminDocumentGrants} class={ITEM_CLASS}>
          <BookOpen class="h-3.5 w-3.5 text-fg-muted" />
          <span>Document access</span>
        </Menu.Item>
      {/if}
    </div>

    <div class="border-t border-border-default/60 pt-1">
      <Menu.Item onSelect={handleSignOut} class={cn(ITEM_CLASS, "text-critical hover:text-critical")}>
        <LogOut class="h-3.5 w-3.5" />
        <span>Sign out</span>
      </Menu.Item>
    </div>
  </DropdownMenu>
{:else}
  <button
    type="button"
    onclick={() => push("/login")}
    class="flex w-full items-center justify-center gap-2 rounded-xl border border-border-default bg-surface-card p-2 text-xs font-medium text-fg-secondary hover:bg-surface-hover hover:text-fg-primary transition-colors"
  >
    <LogIn class="h-3.5 w-3.5" />
    {#if !collapsed}
      <span>Sign in</span>
    {/if}
  </button>
{/if}
