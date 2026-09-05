<script lang="ts">
  import { LogOut, LogIn } from "lucide-svelte";
  import { push } from "svelte-spa-router";
  import { authState } from "../auth.svelte";
  import { isAuthConfigured } from "../supabaseClient";

  let open = $state(false);

  let initials = $derived.by(() => {
    const email = authState.user?.email || "";
    return email ? email[0]!.toUpperCase() : "?";
  });

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
      class="flex h-7 w-7 items-center justify-center rounded-full border border-slate-700 bg-slate-900 text-xs font-semibold text-slate-200 transition-colors hover:border-slate-600"
      aria-label="Account menu"
      aria-haspopup="true"
      aria-expanded={open}
    >
      {initials}
    </button>
    {#if open}
      <div
        class="absolute right-0 top-full z-40 mt-2 w-56 rounded-xl border border-slate-800 bg-slate-900 p-1.5 shadow-xl"
      >
        <p class="truncate px-2.5 py-1.5 text-xs text-slate-400">{authState.user.email}</p>
        {#if authState.profile?.organizations.length}
          <p class="truncate px-2.5 pb-1.5 text-xs text-slate-600">
            {authState.profile.organizations[0].name}
          </p>
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
