<script lang="ts">
  import { Activity, Shield } from "lucide-svelte";
  import { push } from "svelte-spa-router";
  import { authState } from "../auth.svelte";
  import ThemeToggle from "./ThemeToggle.svelte";
  import GlobalPipelineStatus from "./GlobalPipelineStatus.svelte";
  import IntegrationsMenu from "./IntegrationsMenu.svelte";
  import DocumentationMenu from "./DocumentationMenu.svelte";
  import { SidebarTrigger, Separator } from "./ui";
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
    /** Toggles desktop sidebar collapse. */
    onToggleSidebar?: () => void;
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
    onToggleSidebar,
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
    workflow: { section: "Analysis", title: "Live Pipeline Tracker" },
    reports: { section: "Analysis", title: "Compliance Reports & Exports" },
    evaluation: { section: "Analysis", title: "Compliance Evaluation" },
    "query-console": { section: "Coordination", title: "Graph Query Console" },
    "revit-sync": { section: "Integrations", title: "Autodesk Revit Direct Sync" },
    "ifc-export-setting": { section: "Resources", title: "IFC Export Setting for Architectural Model" },
    "user-manual": { section: "Resources", title: "User Workflow Manual" },
    "modeling-manual": { section: "Resources", title: "3D Modeling Reference" },
    "bsdd-wiki": { section: "Resources", title: "bSDD Wiki" },
    "design-system": { section: "Resources", title: "Design System Catalog" },
    "new-project": { section: "Platform", title: "New Project" },
    "run-compliance-test": { section: "Analysis", title: "Run Compliance Audit" },
    "copilot": { section: "Coordination", title: "Graph-RAG Copilot" },
    "permissions": { section: "Admin", title: "Permissions" },
    "login": { section: "BIM Guard", title: "Sign In" },
    "external-providers": { section: "Integrations", title: "External Providers" },
    "superadmin-users": { section: "Governance", title: "User Access" },
    "document": { section: "Library", title: "Document Viewer" },
    "rule-source": { section: "Library", title: "Rule Source" },
    "ruleset-source-map": { section: "Library", title: "Ruleset Source Map" },
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

  // Distinct per-route title so agents (and screen readers) can confirm which
  // view a hash navigation landed on.
  $effect(() => {
    document.title = `${headerInfo.title} · BIM Guard`;
  });
</script>

<header
  class="sticky top-0 z-30 flex h-16 items-center justify-between gap-2 border-b border-border-subtle bg-surface-canvas/80 backdrop-blur-md px-4 md:px-6"
>
  <div class="flex min-w-0 items-center gap-2">
    <SidebarTrigger
      class="-ml-1"
      onclick={() => {
        if (window.innerWidth < 768) {
          onOpenMobileNav();
        } else if (onToggleSidebar) {
          onToggleSidebar();
        }
      }}
    />
    <Separator orientation="vertical" class="mr-2 h-4 hidden sm:block" />
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
            <BreadcrumbPage current={false} title={selectedProject.name} class="truncate font-semibold text-fg-primary">
              {selectedProject.short_name || selectedProject.name}
              {#if selectedProject.project_code}
                <span class="font-normal text-fg-muted">· {selectedProject.project_code}</span>
              {/if}
            </BreadcrumbPage>
          </BreadcrumbItem>
          <BreadcrumbSeparator class="hidden sm:inline-flex" />
          <BreadcrumbItem class="hidden sm:inline-flex">
            <BreadcrumbPage class="text-fg-muted">{headerInfo.title}</BreadcrumbPage>
          </BreadcrumbItem>
        {:else}
          <BreadcrumbItem class="hidden sm:inline-flex">
            <BreadcrumbPage current={false} class="font-medium text-fg-muted">{headerInfo.section}</BreadcrumbPage>
          </BreadcrumbItem>
          <BreadcrumbSeparator class="hidden sm:inline-flex" />
          <BreadcrumbItem>
            <BreadcrumbPage class="truncate font-semibold text-fg-primary">{headerInfo.title}</BreadcrumbPage>
          </BreadcrumbItem>
        {/if}
      </BreadcrumbList>
    </Breadcrumb>
  </div>

  <!-- Actions & Status -->
  <div class="flex shrink-0 items-center gap-2.5">
    <GlobalPipelineStatus onOpen={onOpenPipeline} />

    <DocumentationMenu {activeView} />

    <IntegrationsMenu {activeView} />

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
  </div>
</header>
