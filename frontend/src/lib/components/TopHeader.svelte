<script lang="ts">
  import { Activity, Menu, Shield } from "lucide-svelte";
  import { push } from "svelte-spa-router";
  import { authState } from "../auth.svelte";
  import ThemeToggle from "./ThemeToggle.svelte";
  import GlobalPipelineStatus from "./GlobalPipelineStatus.svelte";
  import OrgSwitcher from "./OrgSwitcher.svelte";
  import ResourcesMenu from "./ResourcesMenu.svelte";
  import IntegrationsMenu from "./IntegrationsMenu.svelte";
  import UserMenu from "./UserMenu.svelte";
  import {
    Breadcrumb,
    BreadcrumbList,
    BreadcrumbItem,
    BreadcrumbLink,
    BreadcrumbPage,
    BreadcrumbSeparator,
  } from "./breadcrumb";
  import type { Project } from "../types";

  interface Props {
    activeView: string;
    /** Whether the app shell is currently in project view (see App.svelte). */
    isProjectView?: boolean;
    selectedProject?: Project | null;
    /** Opens the navigation drawer; only rendered below `md`. */
    onOpenMobileNav?: () => void;
    /** Navigate to the Live Workflow view for a tracked project's pipeline. */
    onOpenPipeline?: (projectId: number) => void;
    /** Leave project view and return to the organization dashboard. */
    onExitProject?: () => void;
  }

  let {
    activeView,
    isProjectView = false,
    selectedProject = null,
    onOpenMobileNav = () => {},
    onOpenPipeline,
    onExitProject,
  }: Props = $props();

  const TITLES: Record<string, { section: string; title: string }> = {
    dashboard: { section: "Platform", title: "Compliance Dashboard" },
    projects: { section: "Platform", title: "Project Registry" },
    viewer: { section: "Platform", title: "3D OpenBIM Viewer" },
    documents: { section: "Library", title: "Document Specifications" },
    extract: { section: "Library", title: "Rule Extraction Studio" },
    rules: { section: "Library", title: "Rules Catalog" },
    "manual-rule-editor": { section: "Library", title: "Manual Rule Editor" },
    models: { section: "Project", title: "Project Models" },
    arch: { section: "Analysis", title: "Architectural Compliance Audit" },
    piping: { section: "Compliance Audit", title: "Piping Services Audit" },
    seismic: { section: "Compliance Audit", title: "Seismic Bracing Audit" },
    analyze: { section: "Analysis", title: "MEP Piping & Seismic Audit" },
    workflow: { section: "Analysis", title: "Live Pipeline Tracker" },
    reports: { section: "Analysis", title: "Compliance Reports & Exports" },
    "revit-sync": { section: "Integrations", title: "Autodesk Revit Direct Sync" },
    "ifc-export-setting": { section: "Integrations", title: "IFC Export Setting for Architectural Model" },
    "user-manual": { section: "Manuals", title: "User Workflow Manual" },
    "modeling-manual": { section: "Manuals", title: "3D Modeling Reference" },
    settings: { section: "System", title: "Application Settings" },
    admin: { section: "Admin", title: "Organization Settings" },
    "org-settings": { section: "Admin", title: "Organization Settings" },
    "superadmin-rulesets": { section: "Governance", title: "Ruleset Access" },
    "superadmin-project-grants": { section: "Governance", title: "Project Access" },
    "superadmin-document-grants": { section: "Governance", title: "Document Access" },
  };

  let headerInfo = $derived(
    // The dashboard title is org-scoped in TITLES; project view renders the
    // same route with different content, so it needs its own label here.
    activeView === "dashboard" && isProjectView
      ? { section: "Project", title: "Project Dashboard" }
      : TITLES[activeView] || {
          section: "BIM Guard",
          title: activeView,
        },
  );
</script>

<header
  class="apple-blur sticky top-0 z-30 flex h-16 items-center justify-between gap-2 border-b border-slate-800 bg-slate-950/60 px-4 md:px-6"
>
  <div class="flex min-w-0 items-center gap-2">
    <button
      type="button"
      onclick={onOpenMobileNav}
      class="-ml-1 rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-900 hover:text-slate-50 md:hidden"
      aria-label="Open navigation"
      aria-controls="app-sidebar"
    >
      <Menu class="h-5 w-5" />
    </button>
    <Breadcrumb class="min-w-0">
      <BreadcrumbList>
        {#if isProjectView && selectedProject}
          <BreadcrumbItem class="hidden sm:inline-flex">
            <BreadcrumbLink onclick={onExitProject} title="Back to Organization">
              Organization
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator class="hidden sm:inline-flex" />
          <!-- Project identity (short name + ISO 19650 code) appears exactly
               once here -- it replaced the old header project switcher and must
               not also repeat as a separate badge. -->
          <BreadcrumbItem>
            <BreadcrumbPage current={false} title={selectedProject.name} class="truncate font-semibold text-slate-100">
              {selectedProject.short_name || selectedProject.name}
              {#if selectedProject.project_code}
                <span class="font-normal text-slate-500">· {selectedProject.project_code}</span>
              {/if}
            </BreadcrumbPage>
          </BreadcrumbItem>
          <BreadcrumbSeparator class="hidden sm:inline-flex" />
          <BreadcrumbItem class="hidden sm:inline-flex">
            <BreadcrumbPage class="text-slate-400">{headerInfo.title}</BreadcrumbPage>
          </BreadcrumbItem>
        {:else}
          <BreadcrumbItem class="hidden sm:inline-flex">
            <BreadcrumbPage current={false} class="font-medium text-slate-500">{headerInfo.section}</BreadcrumbPage>
          </BreadcrumbItem>
          <BreadcrumbSeparator class="hidden sm:inline-flex" />
          <BreadcrumbItem>
            <BreadcrumbPage class="truncate font-semibold text-slate-100">{headerInfo.title}</BreadcrumbPage>
          </BreadcrumbItem>
        {/if}
      </BreadcrumbList>
    </Breadcrumb>
  </div>

  <!-- Actions & Status -->
  <div class="flex shrink-0 items-center gap-2.5">
    <OrgSwitcher />
    <GlobalPipelineStatus onOpen={onOpenPipeline} />

    <IntegrationsMenu {activeView} />
    <ResourcesMenu {activeView} />

    {#if authState.isSuperadmin || authState.activeOrganization?.role === 'owner' || authState.activeOrganization?.role === 'admin'}
      <button
        type="button"
        onclick={() =>
          push(
            authState.activeOrganizationId
              ? `/org-settings?org=${authState.activeOrganizationId}`
              : "/org-settings",
          )}
        class="hidden sm:inline-flex items-center gap-1.5 rounded-lg border border-accent/30 bg-accent/10 px-2.5 py-1 text-xs font-semibold text-accent transition-colors hover:bg-accent/20 hover:text-white"
        title="Open Admin Console"
      >
        <Shield class="h-3.5 w-3.5 text-accent" />
        <span>Admin</span>
      </button>
    {/if}

    <!-- Theme Toggle Button -->
    <ThemeToggle />

    <UserMenu />
  </div>
</header>
