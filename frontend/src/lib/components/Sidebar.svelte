<script lang="ts">
  import {
    LayoutDashboard,
    Plus,
    FolderOpen,
    ScanEye,
    LayoutList,
    Cpu,
    Workflow,
    FileText,
    BookOpen,
    Sparkles,
    ListChecks,
    BookOpenCheck,
    Box,
    Settings,
    ChevronLeft,
    ChevronRight,
    RefreshCw,
    Compass,
  } from "lucide-svelte";

  interface Props {
    activeView?: string;
    onSelectView: (view: string) => void;
    /** Drawer visibility below `md`. Above it the sidebar is always shown. */
    mobileOpen?: boolean;
    onCloseMobile?: () => void;
  }

  let {
    activeView = "dashboard",
    onSelectView,
    mobileOpen = false,
    onCloseMobile = () => {},
  }: Props = $props();

  let collapsed = $state(false);

  // On a phone the sidebar is a drawer over the content, so choosing a
  // destination should dismiss it; on desktop it stays put.
  function handleSelect(view: string) {
    onSelectView(view);
    onCloseMobile();
  }

  const NAV_SECTIONS = [
    {
      title: "Project Uploads",
      items: [
        { id: "newproject", label: "New Project Upload", icon: Plus },
        { id: "projects", label: "Existing Projects", icon: FolderOpen },
        { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
        { id: "viewer", label: "3D Viewer", icon: ScanEye },
      ],
    },
    {
      title: "Rule Document Uploads",
      items: [
        { id: "newdocument", label: "New Rule Document Upload", icon: Plus },
        { id: "documents", label: "Existing Rule Documents", icon: BookOpen },
        { id: "extract", label: "Rule Extraction Studio", icon: Sparkles },
        { id: "rules", label: "Rule Catalog Edit", icon: ListChecks },
      ],
    },
    {
      title: "Analysis",
      items: [
        { id: "arch", label: "Architectural", icon: LayoutList },
        { id: "piping", label: "Piping", icon: Cpu },
        { id: "seismic", label: "Seismic", icon: Compass },
        { id: "workflow", label: "Live Workflow", icon: Workflow },
        { id: "reports", label: "Reports & Exports", icon: FileText },
      ],
    },
    {
      title: "Integrations",
      items: [{ id: "revit-sync", label: "Revit Direct Sync", icon: RefreshCw }],
    },
    {
      title: "Manuals",
      items: [
        { id: "user-manual", label: "User Manual", icon: BookOpenCheck },
        { id: "modeling-manual", label: "Modeling Manual", icon: Box },
      ],
    },
  ];
</script>

<!-- Scrim: only below md, and only while the drawer is open. -->
{#if mobileOpen}
  <div
    class="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
    onclick={onCloseMobile}
    aria-hidden="true"
  ></div>
{/if}

<aside
  id="app-sidebar"
  aria-label="Primary"
  class="apple-blur fixed inset-y-0 z-50 flex h-screen w-64 select-none flex-col border-r border-slate-800 bg-slate-950/90 transition-[left] duration-300
    md:sticky md:left-0 md:top-0 md:z-40 md:transition-all
    {mobileOpen ? 'left-0' : '-left-64'}
    {collapsed ? 'md:w-16' : 'md:w-64'}"
>
  <!-- Brand Header -->
  <div class="flex h-16 items-center justify-between border-b border-slate-800/80 px-3.5">
    {#if !collapsed}
      <div class="flex items-center gap-2.5 overflow-hidden">
        <div
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-accent to-cyan-400 text-sm font-bold text-white shadow-md shadow-blue-500/20"
        >
          BG
        </div>
        <div class="flex flex-col truncate">
          <span class="text-base font-bold leading-none tracking-tight text-slate-50"
            >BIM Guard</span
          >
          <span class="mt-1 text-micro font-semibold uppercase tracking-widest text-slate-400"
            >OpenBIM Compliance</span
          >
        </div>
      </div>
    {:else}
      <div
        class="mx-auto flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-tr from-accent to-cyan-400 text-sm font-bold text-white shadow-md shadow-blue-500/20"
      >
        BG
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

  <!-- Nav Groups -->
  <div class="flex-1 space-y-4 overflow-y-auto px-2 py-3">
    {#each NAV_SECTIONS as section (section)}
      <div class="space-y-1">
        {#if !collapsed}
          <div
            class="rounded-lg bg-slate-800/60 px-2.5 py-1 text-sm font-bold uppercase tracking-wider text-slate-400"
          >
            {section.title}
          </div>
        {/if}

        {#each section.items as item (item.id)}
          <button
            type="button"
            onclick={() => handleSelect(item.id)}
            class="group relative flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-sm font-medium transition-all {activeView ===
            item.id
              ? 'bg-accent text-white shadow-sm shadow-blue-600/30'
              : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-100'}"
            title={collapsed ? item.label : undefined}
          >
            <item.icon
              class="h-4 w-4 shrink-0 {activeView === item.id
                ? 'text-slate-50'
                : 'text-slate-400 group-hover:text-slate-200'}"
            />
            {#if !collapsed}
              <span class="truncate text-left">{item.label}</span>
            {/if}

            {#if collapsed && activeView === item.id}
              <span class="absolute bottom-2 left-0 top-2 w-1 rounded-r bg-white"></span>
            {/if}
          </button>
        {/each}
      </div>
    {/each}
  </div>

  <!-- Sidebar Footer: Settings -->
  <div class="space-y-1 border-t border-slate-800/80 bg-slate-950/60 p-2">
    <!-- Settings Button -->
    <button
      type="button"
      onclick={() => handleSelect("settings")}
      class="group flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-sm font-medium transition-all {activeView ===
      'settings'
        ? 'bg-accent text-white'
        : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-100'} {collapsed
        ? 'justify-center'
        : ''}"
      title={collapsed ? "Settings" : undefined}
    >
      <Settings
        class="h-4 w-4 shrink-0 {activeView === 'settings'
          ? 'text-slate-50'
          : 'text-slate-400 group-hover:text-slate-200'}"
      />
      {#if !collapsed}
        <span>Settings</span>
      {/if}
    </button>
  </div>
</aside>
