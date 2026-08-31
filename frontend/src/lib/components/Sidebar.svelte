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

  export let activeView: string = "dashboard";
  export let onSelectView: (view: string) => void;

  let collapsed = false;

  const NAV_SECTIONS = [
    {
      title: "Platform",
      items: [
        { id: "newproject", label: "New Project", icon: Plus },
        { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
        { id: "projects", label: "Projects", icon: FolderOpen },
        { id: "viewer", label: "3D Viewer", icon: ScanEye },
      ],
    },
    {
      title: "Library",
      items: [
        { id: "documents", label: "Documents", icon: BookOpen },
        { id: "extract", label: "Rule Extraction Studio", icon: Sparkles },
        { id: "rules", label: "Rules Catalog", icon: ListChecks },
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
      items: [
        { id: "revit-sync", label: "Revit Direct Sync", icon: RefreshCw },
      ],
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

<aside
  class="h-screen sticky top-0 flex flex-col border-r border-slate-800 bg-slate-950/90 apple-blur z-40 transition-all duration-300 select-none {collapsed
    ? 'w-16'
    : 'w-64'}"
>
  <!-- Brand Header -->
  <div
    class="h-16 border-b border-slate-800/80 flex items-center justify-between px-3.5"
  >
    {#if !collapsed}
      <div class="flex items-center gap-2.5 overflow-hidden">
        <div
          class="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#0071e3] to-cyan-400 flex items-center justify-center font-bold text-white text-sm shadow-md shadow-blue-500/20 shrink-0"
        >
          BG
        </div>
        <div class="flex flex-col truncate">
          <span
            class="font-bold text-base tracking-tight text-white leading-none"
            >BIM Guard</span
          >
          <span
            class="text-[10px] text-slate-400 uppercase tracking-widest mt-1 font-semibold"
            >OpenBIM Compliance</span
          >
        </div>
      </div>
    {:else}
      <div
        class="w-8 h-8 rounded-xl bg-gradient-to-tr from-[#0071e3] to-cyan-400 flex items-center justify-center font-bold text-white text-sm shadow-md shadow-blue-500/20 mx-auto"
      >
        BG
      </div>
    {/if}

    <button
      type="button"
      on:click={() => (collapsed = !collapsed)}
      class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-900 transition-colors shrink-0"
      title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
    >
      {#if collapsed}
        <ChevronRight class="w-4 h-4" />
      {:else}
        <ChevronLeft class="w-4 h-4" />
      {/if}
    </button>
  </div>

  <!-- Nav Groups -->
  <div class="flex-1 overflow-y-auto py-3 px-2 space-y-4">
    {#each NAV_SECTIONS as section}
      <div class="space-y-1">
        {#if !collapsed}
          <div
            class="px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-500"
          >
            {section.title}
          </div>
        {/if}

        {#each section.items as item}
          <button
            type="button"
            on:click={() => onSelectView(item.id)}
            class="w-full flex items-center gap-3 px-2.5 py-2 rounded-xl text-sm font-medium transition-all group relative {activeView ===
            item.id
              ? 'bg-[#0071e3] text-white shadow-sm shadow-blue-600/30'
              : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/60'}"
            title={collapsed ? item.label : undefined}
          >
            <svelte:component
              this={item.icon}
              class="w-4 h-4 shrink-0 {activeView === item.id
                ? 'text-white'
                : 'text-slate-400 group-hover:text-slate-200'}"
            />
            {#if !collapsed}
              <span class="truncate text-left">{item.label}</span>
            {/if}

            {#if collapsed && activeView === item.id}
              <span
                class="absolute left-0 top-2 bottom-2 w-1 bg-white rounded-r"
              ></span>
            {/if}
          </button>
        {/each}
      </div>
    {/each}
  </div>

  <!-- Sidebar Footer: Settings -->
  <div class="border-t border-slate-800/80 p-2 space-y-1 bg-slate-950/60">
    <!-- Settings Button -->
    <button
      type="button"
      on:click={() => onSelectView("settings")}
      class="w-full flex items-center gap-3 px-2.5 py-2 rounded-xl text-sm font-medium transition-all group {activeView ===
      'settings'
        ? 'bg-[#0071e3] text-white'
        : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/60'} {collapsed
        ? 'justify-center'
        : ''}"
      title={collapsed ? "Settings" : undefined}
    >
      <Settings
        class="w-4 h-4 shrink-0 {activeView === 'settings'
          ? 'text-white'
          : 'text-slate-400 group-hover:text-slate-200'}"
      />
      {#if !collapsed}
        <span>Settings</span>
      {/if}
    </button>
  </div>
</aside>
