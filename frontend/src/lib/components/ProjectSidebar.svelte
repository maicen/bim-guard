<script lang="ts">
  import {
    LayoutDashboard,
    Boxes,
    ScanEye,
    PlayCircle,
    FileText,
    Activity,
    ChevronLeft,
    ChevronRight,
    ArrowLeft,
    ClipboardCheck,
    Terminal,
  } from "lucide-svelte";
  import { link, push } from "svelte-spa-router";
  import { authState } from "../auth.svelte";
  import OrgSwitcher from "./sidebar/OrgSwitcher.svelte";
  import NavUser from "./sidebar/NavUser.svelte";
  import Tooltip from "./Tooltip.svelte";
  import type { Project } from "../types";

  interface Props {
    activeView?: string;
    selectedProject?: Project | null;
    selectedProjectId: number;
    /** Drawer visibility below `md`. Above it the sidebar is always shown. */
    mobileOpen?: boolean;
    onCloseMobile?: () => void;
    collapsed?: boolean;
  }

  let {
    activeView = "dashboard",
    selectedProject = null,
    selectedProjectId,
    mobileOpen = false,
    onCloseMobile = () => {},
    collapsed = $bindable(false),
  }: Props = $props();

  // Views that all fall under the single "Compliance Audit" destination
  const AUDIT_VIEW_IDS = new Set(["arch"]);

  function getNavHref(itemId: string): string {
    const params = new URLSearchParams();
    if (authState.activeOrganizationId) {
      params.set("org", String(authState.activeOrganizationId));
    }
    params.set("project_id", String(selectedProjectId));
    return `/${itemId}?${params.toString()}`;
  }

  function handleExitProject() {
    const params = new URLSearchParams();
    if (authState.activeOrganizationId) {
      params.set("org", String(authState.activeOrganizationId));
    }
    const q = params.toString();
    push(q ? `/dashboard?${q}` : "/dashboard");
    onCloseMobile();
  }

  const NAV_SECTIONS = [
    {
      title: "Project",
      items: [
        { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
        { id: "models", label: "Models", icon: Boxes },
      ],
    },
    {
      title: "Compliance",
      items: [
        { id: "arch", label: "Run Compliance Audit", icon: PlayCircle, highlight: true },
        { id: "reports", label: "Reports & Exports", icon: FileText },
        { id: "evaluation", label: "Evaluation", icon: ClipboardCheck },
      ],
    },
    {
      title: "Coordination",
      items: [
        { id: "viewer", label: "3D Viewer", icon: ScanEye },
        { id: "query-console", label: "Query Console", icon: Terminal },
        { id: "workflow", label: "Live Pipeline", icon: Activity },
      ],
    },
  ];
</script>

<!-- Scrim: only below md, and only while the drawer is open. -->
{#if mobileOpen}
  <div
    class="fixed inset-0 z-40 bg-black/60 backdrop-blur-xs md:hidden"
    onclick={onCloseMobile}
    aria-hidden="true"
  ></div>
{/if}

<aside
  id="app-sidebar"
  aria-label="Primary"
  class="apple-blur fixed inset-y-0 z-50 flex h-screen w-64 select-none flex-col border-r border-border-default bg-surface-canvas/90 transition-[left] duration-300
    md:sticky md:left-0 md:top-0 md:z-40 md:transition-all
    {mobileOpen ? 'left-0' : '-left-64'}
    {collapsed ? 'md:w-16' : 'md:w-64'}"
>
  <!-- Header: Team / Organization Switcher (sidebar-07) -->
  <div class="flex h-16 items-center justify-between border-b border-border-default px-2 gap-1.5 shrink-0">
    <div class="flex-1 min-w-0 {collapsed ? 'flex justify-center' : ''}">
      <OrgSwitcher {collapsed} />
    </div>

    {#if !collapsed}
      <button
        type="button"
        onclick={() => (collapsed = !collapsed)}
        class="hidden shrink-0 rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary md:block cursor-pointer"
        aria-label="Collapse sidebar"
      >
        <ChevronLeft class="h-4 w-4" />
      </button>
    {/if}

    <button
      type="button"
      onclick={onCloseMobile}
      class="shrink-0 rounded-lg p-1.5 text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary md:hidden cursor-pointer"
      aria-label="Close navigation"
    >
      <ChevronLeft class="h-5 w-5" />
    </button>
  </div>

  <!-- Current project context bar (sidebar-07) -->
  <div class="border-b border-border-default px-2 py-2 shrink-0">
    {#snippet backButton()}
      <button
        type="button"
        onclick={handleExitProject}
        class="group flex items-center gap-2 rounded-lg px-2 py-1 text-nano font-bold uppercase tracking-wider text-fg-muted transition-colors hover:bg-surface-hover hover:text-fg-primary cursor-pointer {collapsed ? 'justify-center mx-auto size-8 p-0' : 'w-full'}"
        aria-label="Back to Organization"
      >
        <ArrowLeft class="h-3.5 w-3.5 shrink-0" />
        {#if !collapsed}
          <span>All Projects</span>
        {/if}
      </button>
    {/snippet}

    {#if collapsed}
      <Tooltip text="Back to All Projects" side="right" sideOffset={8}>
        {#snippet trigger()}
          {@render backButton()}
        {/snippet}
      </Tooltip>
    {:else}
      {@render backButton()}
      <div class="mt-1 truncate px-2 text-xs font-bold text-fg-primary">
        {selectedProject?.name || "Selected Project"}
      </div>
    {/if}
  </div>

  <!-- Nav Groups -->
  <div class="flex-1 space-y-4 overflow-y-auto px-2 py-3">
    {#each NAV_SECTIONS as section (section.title)}
      <div class="space-y-1">
        {#if !collapsed}
          <div
            class="text-nano font-bold uppercase tracking-wider text-fg-muted px-2.5 py-1"
          >
            {section.title}
          </div>
        {/if}

        {#each section.items as item (item.id)}
          {@const isActive =
            activeView === item.id || (item.id === "arch" && AUDIT_VIEW_IDS.has(activeView))}

          {#snippet navItemBtn()}
            <a
              href={getNavHref(item.id)}
              use:link
              onclick={onCloseMobile}
              class="group relative flex items-center gap-3 rounded-xl px-2.5 py-2 text-sm transition-all {item.highlight
                ? 'font-bold'
                : 'font-medium'} {isActive
                ? 'bg-accent text-white shadow-xs shadow-blue-600/30'
                : item.highlight
                  ? 'text-accent hover:bg-surface-hover'
                  : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'} {collapsed ? 'justify-center px-0 h-9 w-9 mx-auto' : 'w-full'}"
              aria-current={isActive ? 'page' : undefined}
            >
              <item.icon
                class="h-4 w-4 shrink-0 {isActive
                  ? 'text-white'
                  : item.highlight
                    ? 'text-accent'
                    : 'text-fg-muted group-hover:text-fg-primary'}"
              />
              {#if !collapsed}
                <span class="truncate text-left flex-1">{item.label}</span>
              {/if}

              {#if collapsed && isActive}
                <span class="absolute bottom-2 left-0 top-2 w-1 rounded-r-md bg-white"></span>
              {/if}
            </a>
          {/snippet}

          {#if collapsed}
            <Tooltip text={item.label} side="right" sideOffset={8}>
              {#snippet trigger()}
                {@render navItemBtn()}
              {/snippet}
            </Tooltip>
          {:else}
            {@render navItemBtn()}
          {/if}
        {/each}
      </div>
    {/each}
  </div>

  <!-- Sidebar Footer: NavUser (sidebar-07) -->
  <div class="space-y-1 border-t border-border-default bg-surface-canvas/60 p-2 shrink-0 flex flex-col gap-1">
    <NavUser {collapsed} />
    {#if collapsed}
      <button
        type="button"
        onclick={() => (collapsed = false)}
        class="text-fg-muted hover:bg-surface-hover hover:text-fg-primary mx-auto flex size-8 items-center justify-center rounded-lg p-1 transition-colors cursor-pointer"
        aria-label="Expand sidebar"
      >
        <ChevronRight class="h-4 w-4" />
      </button>
    {/if}
  </div>
</aside>
