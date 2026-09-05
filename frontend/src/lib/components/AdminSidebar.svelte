<script lang="ts">
  import {
    Building2,
    ShieldCheck,
    FolderGit2,
    BookOpen,
    ArrowLeft,
    ChevronLeft,
    ChevronRight,
    Shield,
  } from "lucide-svelte";
  import { push } from "svelte-spa-router";
  import { authState } from "../auth.svelte";

  interface Props {
    activeView?: string;
    mobileOpen?: boolean;
    onCloseMobile?: () => void;
  }

  let { activeView = "org-settings", mobileOpen = false, onCloseMobile = () => {} }: Props = $props();

  let collapsed = $state(false);

  const ADMIN_NAV_ITEMS = [
    {
      id: "org-settings",
      label: "Organization settings",
      icon: Building2,
      path: "/org-settings",
      description: "Members, roles, invites & groups",
    },
    {
      id: "superadmin-rulesets",
      label: "Ruleset access",
      icon: ShieldCheck,
      path: "/superadmin-rulesets",
      description: "Organization ruleset grants",
    },
    {
      id: "superadmin-project-grants",
      label: "Project access",
      icon: FolderGit2,
      path: "/superadmin-project-grants",
      description: "Cross-organization project sharing",
    },
    {
      id: "superadmin-document-grants",
      label: "Document access",
      icon: BookOpen,
      path: "/superadmin-document-grants",
      description: "Organization document library grants",
    },
  ];

  function navigateTo(path: string) {
    onCloseMobile();
    const orgId = authState.activeOrganizationId;
    const target = orgId ? `${path}?org=${orgId}` : path;
    push(target);
  }

  function backToApp() {
    onCloseMobile();
    const orgId = authState.activeOrganizationId;
    const target = orgId ? `/dashboard?org=${orgId}` : "/dashboard";
    push(target);
  }
</script>

<!-- Scrim: only below md, and only while mobile drawer is open -->
{#if mobileOpen}
  <div
    class="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
    onclick={onCloseMobile}
    aria-hidden="true"
  ></div>
{/if}

<aside
  id="admin-sidebar"
  aria-label="Administration"
  class="apple-blur fixed inset-y-0 z-50 flex h-screen w-64 select-none flex-col border-r border-violet-900/40 bg-slate-950/95 transition-[left] duration-300
    md:sticky md:left-0 md:top-0 md:z-40 md:transition-all
    {mobileOpen ? 'left-0' : '-left-64'}
    {collapsed ? 'md:w-16' : 'md:w-64'}"
>
  <!-- Brand Header: Admin Console -->
  <div class="flex h-16 items-center justify-between border-b border-violet-900/30 px-3.5 bg-violet-950/20">
    {#if !collapsed}
      <div class="flex items-center gap-2.5 overflow-hidden">
        <div
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-violet-600 to-indigo-500 text-sm font-bold text-white shadow-md shadow-violet-500/20"
        >
          <Shield class="h-4 w-4" />
        </div>
        <div class="flex flex-col truncate">
          <span class="text-base font-bold leading-none tracking-tight text-slate-50">
            Admin Portal
          </span>
          <span class="mt-1 text-micro font-semibold uppercase tracking-widest text-violet-400">
            Governance & Grants
          </span>
        </div>
      </div>
    {:else}
      <div
        class="mx-auto flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-tr from-violet-600 to-indigo-500 text-sm font-bold text-white shadow-md shadow-violet-500/20"
        title="Admin Portal"
      >
        <Shield class="h-4 w-4" />
      </div>
    {/if}

    <button
      type="button"
      onclick={onCloseMobile}
      class="shrink-0 rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-900 hover:text-slate-50 md:hidden"
      aria-label="Close navigation"
    >
      <ChevronLeft class="h-5 w-5" />
    </button>

    <button
      type="button"
      onclick={() => (collapsed = !collapsed)}
      class="hidden shrink-0 rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-900 hover:text-slate-50 md:block"
      title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
    >
      {#if collapsed}
        <ChevronRight class="h-4 w-4" />
      {:else}
        <ChevronLeft class="h-4 w-4" />
      {/if}
    </button>
  </div>

  <!-- Back to App Action -->
  <div class="p-2 border-b border-slate-800/60">
    <button
      type="button"
      onclick={backToApp}
      class="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-xs font-semibold text-violet-300 transition-all hover:bg-violet-500/10 hover:text-violet-200 {collapsed
        ? 'justify-center'
        : ''}"
      title={collapsed ? "Back to Main App" : undefined}
    >
      <ArrowLeft class="h-4 w-4 shrink-0" />
      {#if !collapsed}
        <span class="truncate">Back to Main App</span>
      {/if}
    </button>
  </div>

  <!-- Admin Navigation Buttons -->
  <div class="flex-1 space-y-2 overflow-y-auto p-2">
    {#if !collapsed}
      <div class="px-2.5 py-1 text-xs font-bold uppercase tracking-wider text-slate-400">
        Admin Controls
      </div>
    {/if}

    {#each ADMIN_NAV_ITEMS as item (item.id)}
      {@const isActive = activeView === item.id || (item.id === "org-settings" && activeView === "admin")}
      <button
        type="button"
        onclick={() => navigateTo(item.path)}
        class="group relative flex w-full items-center gap-3 rounded-xl px-2.5 py-2.5 text-sm font-medium transition-all {isActive
          ? 'bg-violet-600 text-white shadow-md shadow-violet-600/30 font-semibold'
          : 'text-slate-400 hover:bg-slate-900 hover:text-slate-100'} {collapsed ? 'justify-center' : ''}"
        title={collapsed ? item.label : undefined}
      >
        <item.icon
          class="h-4 w-4 shrink-0 {isActive
            ? 'text-white'
            : 'text-slate-400 group-hover:text-violet-300'}"
        />
        {#if !collapsed}
          <div class="flex flex-col text-left truncate">
            <span class="truncate leading-snug">{item.label}</span>
          </div>
        {/if}

        {#if collapsed && isActive}
          <span class="absolute bottom-2 left-0 top-2 w-1 rounded-r bg-white"></span>
        {/if}
      </button>
    {/each}
  </div>

  <!-- Footer Info -->
  <div class="border-t border-slate-800/80 bg-slate-950/60 p-3">
    {#if !collapsed}
      <div class="rounded-xl border border-violet-500/20 bg-violet-500/5 p-2.5 text-left">
        <div class="text-xs font-semibold text-violet-300">Tenant Governance</div>
        <div class="mt-0.5 text-micro text-slate-400 leading-normal">
          Manage organization memberships, permissions, and security grants.
        </div>
      </div>
    {:else}
      <div class="flex justify-center text-violet-400">
        <ShieldCheck class="h-4 w-4" />
      </div>
    {/if}
  </div>
</aside>
