<script lang="ts">
  import { LogOut, LogIn, Settings, Building2, ShieldCheck, FolderKanban, BookOpen } from "lucide-svelte";
  import { DropdownMenu as Menu } from "bits-ui";
  import { push } from "svelte-spa-router";
  import { authState } from "../auth.svelte";
  import { isAuthConfigured } from "../supabaseClient";
  import DropdownMenu from "./DropdownMenu.svelte";

  let displayName = $derived(authState.profile?.profile.full_name || authState.user?.email || "");
  let avatarUrl = $derived(authState.profile?.profile.avatar_url || "");
  let initials = $derived.by(() => {
    const source = authState.profile?.profile.full_name || authState.user?.email || "";
    return source ? source[0]!.toUpperCase() : "?";
  });
  let activeOrg = $derived(authState.activeOrganization);
  let canManageOrg = $derived(activeOrg?.role === "owner" || activeOrg?.role === "admin");
  let isSuperadmin = $derived(authState.profile?.profile.is_superadmin ?? false);

  const ITEM_CLASS =
    "flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-slate-300 transition-colors data-highlighted:bg-slate-800 data-highlighted:text-slate-50";

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
  <!-- Sign-in isn't configured in this environment; nothing to show. -->
{:else if authState.loading}
  <span class="h-7 w-7 animate-pulse rounded-full bg-slate-800"></span>
{:else if authState.user}
  <DropdownMenu width="w-56" align="end">
    {#snippet trigger({ props })}
      <button
        type="button"
        {...props}
        class="flex h-7 w-7 items-center justify-center overflow-hidden rounded-full border border-slate-700 bg-slate-900 text-xs font-semibold text-slate-200 transition-colors hover:border-slate-600"
        aria-label="Account menu"
      >
        {#if avatarUrl}
          <img src={avatarUrl} alt="" class="h-full w-full object-cover" referrerpolicy="no-referrer" />
        {:else}
          {initials}
        {/if}
      </button>
    {/snippet}

    <p class="truncate px-2.5 py-1.5 text-xs font-medium text-slate-200">{displayName}</p>
    <p class="truncate px-2.5 pb-1.5 text-xs text-slate-500">{authState.user.email}</p>
    {#if activeOrg}
      <p class="truncate px-2.5 pb-1.5 text-xs capitalize text-violet-400">
        {activeOrg.name} &middot; {activeOrg.role}
      </p>
    {/if}
    <Menu.Item onSelect={goToProfile} class={ITEM_CLASS}>
      <Settings class="h-3.5 w-3.5" />
      Edit profile
    </Menu.Item>
    {#if canManageOrg}
      <Menu.Item onSelect={goToOrgSettings} class={ITEM_CLASS}>
        <Building2 class="h-3.5 w-3.5" />
        Organization settings
      </Menu.Item>
    {/if}
    {#if isSuperadmin}
      <Menu.Item onSelect={goToSuperadminRulesets} class={ITEM_CLASS}>
        <ShieldCheck class="h-3.5 w-3.5" />
        Ruleset access
      </Menu.Item>
      <Menu.Item onSelect={goToSuperadminProjectGrants} class={ITEM_CLASS}>
        <FolderKanban class="h-3.5 w-3.5" />
        Project access
      </Menu.Item>
      <Menu.Item onSelect={goToSuperadminDocumentGrants} class={ITEM_CLASS}>
        <BookOpen class="h-3.5 w-3.5" />
        Document access
      </Menu.Item>
    {/if}
    <Menu.Item onSelect={handleSignOut} class={ITEM_CLASS}>
      <LogOut class="h-3.5 w-3.5" />
      Sign out
    </Menu.Item>
  </DropdownMenu>
{:else}
  <button
    type="button"
    onclick={() => push("/login")}
    class="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-xs font-medium text-slate-300 transition-colors hover:border-slate-700 hover:text-slate-50"
  >
    <LogIn class="h-3.5 w-3.5" />
    Sign in
  </button>
{/if}
