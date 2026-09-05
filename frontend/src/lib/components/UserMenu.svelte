<script lang="ts">
  import { LogOut, LogIn, Settings, Building2, ShieldCheck, FolderKanban, BookOpen } from "lucide-svelte";
  import { push } from "svelte-spa-router";
  import { authState } from "../auth.svelte";
  import { isAuthConfigured } from "../supabaseClient";

  let open = $state(false);

  let displayName = $derived(authState.profile?.profile.full_name || authState.user?.email || "");
  let avatarUrl = $derived(authState.profile?.profile.avatar_url || "");
  let initials = $derived.by(() => {
    const source = authState.profile?.profile.full_name || authState.user?.email || "";
    return source ? source[0]!.toUpperCase() : "?";
  });
  let activeOrg = $derived(authState.activeOrganization);
  let canManageOrg = $derived(activeOrg?.role === "owner" || activeOrg?.role === "admin");
  let isSuperadmin = $derived(authState.profile?.profile.is_superadmin ?? false);

  function goToProfile() {
    open = false;
    push("/settings");
  }

  function goToOrgSettings() {
    open = false;
    push("/org-settings");
  }

  function goToSuperadminRulesets() {
    open = false;
    push("/superadmin-rulesets");
  }

  function goToSuperadminProjectGrants() {
    open = false;
    push("/superadmin-project-grants");
  }

  function goToSuperadminDocumentGrants() {
    open = false;
    push("/superadmin-document-grants");
  }

  function toggle(e: MouseEvent) {
    e.stopPropagation();
    open = !open;
  }

  async function handleSignOut() {
    open = false;
    await authState.signOut();
  }
</script>

<svelte:document onclick={() => (open = false)} />

{#if !isAuthConfigured}
  <!-- Sign-in isn't configured in this environment; nothing to show. -->
{:else if authState.loading}
  <span class="h-7 w-7 animate-pulse rounded-full bg-slate-800"></span>
{:else if authState.user}
  <div class="relative">
    <button
      type="button"
      onclick={toggle}
      class="flex h-7 w-7 items-center justify-center overflow-hidden rounded-full border border-slate-700 bg-slate-900 text-xs font-semibold text-slate-200 transition-colors hover:border-slate-600"
      aria-label="Account menu"
      aria-haspopup="true"
      aria-expanded={open}
    >
      {#if avatarUrl}
        <img src={avatarUrl} alt="" class="h-full w-full object-cover" referrerpolicy="no-referrer" />
      {:else}
        {initials}
      {/if}
    </button>
    {#if open}
      <div
        class="absolute right-0 top-full z-40 mt-2 w-56 rounded-xl border border-slate-800 bg-slate-900 p-1.5 shadow-xl"
      >
        <p class="truncate px-2.5 py-1.5 text-xs font-medium text-slate-200">{displayName}</p>
        <p class="truncate px-2.5 pb-1.5 text-xs text-slate-500">{authState.user.email}</p>
        {#if activeOrg}
          <p class="truncate px-2.5 pb-1.5 text-xs capitalize text-violet-400">
            {activeOrg.name} &middot; {activeOrg.role}
          </p>
        {/if}
        <button
          type="button"
          onclick={goToProfile}
          class="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <Settings class="h-3.5 w-3.5" />
          Edit profile
        </button>
        {#if canManageOrg}
          <button
            type="button"
            onclick={goToOrgSettings}
            class="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
          >
            <Building2 class="h-3.5 w-3.5" />
            Organization settings
          </button>
        {/if}
        {#if isSuperadmin}
          <button
            type="button"
            onclick={goToSuperadminRulesets}
            class="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
          >
            <ShieldCheck class="h-3.5 w-3.5" />
            Ruleset access
          </button>
          <button
            type="button"
            onclick={goToSuperadminProjectGrants}
            class="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
          >
            <FolderKanban class="h-3.5 w-3.5" />
            Project access
          </button>
          <button
            type="button"
            onclick={goToSuperadminDocumentGrants}
            class="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
          >
            <BookOpen class="h-3.5 w-3.5" />
            Document access
          </button>
        {/if}
        <button
          type="button"
          onclick={handleSignOut}
          class="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-slate-300 transition-colors hover:bg-slate-800 hover:text-slate-50"
        >
          <LogOut class="h-3.5 w-3.5" />
          Sign out
        </button>
      </div>
    {/if}
  </div>
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
