<script lang="ts">
  import {
    Building2,
    ShieldCheck,
    FolderGit2,
    BookOpen,
    Users,
    ArrowLeft,
    ChevronLeft,
    ChevronRight,
    Shield,
    Plug,
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
      id: "external-providers",
      label: "External providers",
      icon: Plug,
      path: "/external-providers",
      description: "Document parsing & LLM provider credentials",
    },
    {
      id: "superadmin-users",
      label: "Users & organizations",
      icon: Users,
      path: "/superadmin-users",
      description: "Platform users, orgs & assignments",
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
    class="fixed inset-0 z-40 bg-black/60 backdrop-blur-xs md:hidden"
    onclick={onCloseMobile}
    aria-hidden="true"
  ></div>
{/if}

<aside
  id="admin-sidebar"
  aria-label="Administration"
  class="apple-blur fixed inset-y-0 z-50 flex h-screen w-64 select-none flex-col border-r border-border-default bg-surface-card/95 transition-[left] duration-300
    md:sticky md:left-0 md:top-0 md:z-40 md:transition-all
    {mobileOpen ? 'left-0' : '-left-64'}
    {collapsed ? 'md:w-16' : 'md:w-64'}"
>
  <!-- Brand Header: Admin Console -->
  <div class="flex h-16 items-center justify-between border-b border-border-subtle px-3.5 bg-surface-overlay">
    {#if !collapsed}
      <div class="flex items-center gap-2.5 overflow-hidden">
        <div
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-accent text-sm font-bold text-white shadow-xs"
        >
          <Shield class="h-4 w-4" />
        </div>
        <div class="flex flex-col truncate">
          <span class="text-base font-bold leading-none tracking-tight text-fg-primary">
            Admin Portal
          </span>
          <span class="mt-1 text-micro font-semibold uppercase tracking-widest text-accent">
            Governance & Grants
          </span>
        </div>
      </div>
    {:else}
      <div
        class="mx-auto flex h-8 w-8 items-center justify-center rounded-xl bg-accent text-sm font-bold text-white shadow-xs"
        title="Admin Portal"
      >
        <Shield class="h-4 w-4" />
      </div>
    {/if}

    <button
      type="button"
      onclick={onCloseMobile}
      class="shrink-0 rounded-lg p-2 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary md:hidden"
      aria-label="Close navigation"
    >
      <ChevronLeft class="h-5 w-5" />
    </button>

    <button
      type="button"
      onclick={() => (collapsed = !collapsed)}
      class="hidden shrink-0 rounded-lg p-1 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary md:block"
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
  <div class="p-2 border-b border-border-subtle">
    <button
      type="button"
      onclick={backToApp}
      class="flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-xs font-semibold text-accent transition-all hover:bg-accent/10 hover:text-accent {collapsed
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
      <div class="px-2.5 py-1 text-xs font-bold uppercase tracking-wider text-fg-muted">
        Admin Controls
      </div>
    {/if}

    {#each ADMIN_NAV_ITEMS as item (item.id)}
      {@const isActive = activeView === item.id || (item.id === "org-settings" && activeView === "admin")}
      <button
        type="button"
        onclick={() => navigateTo(item.path)}
        class="group relative flex w-full items-center gap-3 rounded-xl px-2.5 py-2.5 text-sm font-medium transition-all {isActive
          ? 'bg-accent text-white shadow-xs font-semibold'
          : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'} {collapsed ? 'justify-center' : ''}"
        title={collapsed ? item.label : undefined}
      >
        <item.icon
          class="h-4 w-4 shrink-0 {isActive
            ? 'text-white'
            : 'text-fg-muted group-hover:text-accent'}"
        />
        {#if !collapsed}
          <div class="flex flex-col text-left truncate">
            <span class="truncate leading-snug">{item.label}</span>
          </div>
        {/if}

        {#if collapsed && isActive}
          <span class="absolute bottom-2 left-0 top-2 w-1 rounded-r-md bg-white"></span>
        {/if}
      </button>
    {/each}
  </div>

  <!-- Footer Info -->
  <div class="border-t border-border-subtle bg-surface-card p-3">
    {#if !collapsed}
      <div class="rounded-xl border border-border-subtle bg-surface-overlay p-2.5 text-left">
        <div class="text-xs font-semibold text-fg-primary">Tenant Governance</div>
        <div class="mt-0.5 text-micro text-fg-muted leading-normal">
          Manage organization memberships, permissions, and security grants.
        </div>
      </div>
    {:else}
      <div class="flex justify-center text-accent">
        <ShieldCheck class="h-4 w-4" />
      </div>
    {/if}
  </div>
</aside>
