<script lang="ts">
  import {
    LayoutDashboard,
    Sparkles,
    ListChecks,
    ChevronLeft,
    ChevronRight,
    PlayCircle,
    Plus,
  } from "lucide-svelte";
  import { link } from "svelte-spa-router";
  import { authState } from "../auth.svelte";
  import OrgSwitcher from "./sidebar/OrgSwitcher.svelte";
  import NavUser from "./sidebar/NavUser.svelte";
  import Tooltip from "./Tooltip.svelte";

  interface Props {
    activeView?: string;
    /** Drawer visibility below `md`. Above it the sidebar is always shown. */
    mobileOpen?: boolean;
    onCloseMobile?: () => void;
  }

  let { activeView = "dashboard", mobileOpen = false, onCloseMobile = () => {} }: Props = $props();

  let collapsed = $state(false);

  function getNavHref(itemId: string): string {
    if (!authState.activeOrganizationId) return `/${itemId}`;
    return `/${itemId}?org=${authState.activeOrganizationId}`;
  }

  const NAV_SECTIONS = [
    {
      title: "My Home",
      items: [
        { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
        {
          id: "run-compliance-test",
          label: "Run Compliance Audit",
          icon: PlayCircle,
          highlight: true,
        },
      ],
    },
    {
      title: "Rules & Standards",
      items: [
        { id: "documents", label: "Documents", icon: Plus },
        { id: "extract", label: "Rule Extraction Studio", icon: Sparkles },
        { id: "rules", label: "Rule Catalog", icon: ListChecks },
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
  class="apple-blur border-border-default bg-surface-canvas/90 fixed inset-y-0 z-50 flex h-screen w-64 flex-col border-r transition-[left] duration-300 select-none
    md:sticky md:top-0 md:left-0 md:z-40 md:transition-all
    {mobileOpen ? 'left-0' : '-left-64'}
    {collapsed ? 'md:w-16' : 'md:w-64'}"
>
  <!-- Header: Team / Organization Switcher (sidebar-07) -->
  <div class="border-border-default flex h-16 items-center justify-between border-b px-2 gap-1.5 shrink-0">
    <div class="flex-1 min-w-0 {collapsed ? 'flex justify-center' : ''}">
      <OrgSwitcher {collapsed} />
    </div>

    {#if !collapsed}
      <button
        type="button"
        onclick={() => (collapsed = !collapsed)}
        class="text-fg-muted hover:bg-surface-hover hover:text-fg-primary hidden shrink-0 rounded-lg p-1.5 transition-colors md:block cursor-pointer"
        aria-label="Collapse sidebar"
      >
        <ChevronLeft class="h-4 w-4" />
      </button>
    {/if}

    <button
      type="button"
      onclick={onCloseMobile}
      class="text-fg-muted hover:bg-surface-hover hover:text-fg-primary shrink-0 rounded-lg p-1.5 transition-colors md:hidden cursor-pointer"
      aria-label="Close navigation"
    >
      <ChevronLeft class="h-5 w-5" />
    </button>
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
          {@const isActive = activeView === item.id}
          {#if item.id === "dashboard"}
            {#snippet newProjectBtn()}
              <a
                href={getNavHref("new-project")}
                use:link
                onclick={onCloseMobile}
                class="group flex items-center gap-3 rounded-xl px-2.5 py-2 text-sm font-medium transition-all {activeView ===
                'new-project'
                  ? 'bg-accent text-white shadow-xs shadow-blue-600/30'
                  : 'text-fg-muted hover:bg-surface-hover hover:text-fg-primary'} {collapsed ? 'justify-center px-0 h-9 w-9 mx-auto' : 'w-full'}"
                aria-current={activeView === 'new-project' ? 'page' : undefined}
              >
                <Plus
                  class="h-4 w-4 shrink-0 {activeView === 'new-project'
                    ? 'text-white'
                    : 'text-fg-muted group-hover:text-fg-primary'}"
                />
                {#if !collapsed}
                  <span class="truncate text-left flex-1">New Project</span>
                {/if}
              </a>
            {/snippet}

            {#if collapsed}
              <Tooltip text="New Project" side="right" sideOffset={8}>
                {#snippet trigger()}
                  {@render newProjectBtn()}
                {/snippet}
              </Tooltip>
            {:else}
              {@render newProjectBtn()}
            {/if}
          {/if}

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
                <span class="absolute top-2 bottom-2 left-0 w-1 rounded-r-md bg-white"></span>
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
  <div class="border-border-default bg-surface-canvas/60 border-t p-2 flex flex-col gap-1 shrink-0">
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
