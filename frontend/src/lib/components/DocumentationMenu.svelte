<script lang="ts">
  import {
    BookOpen,
    BookOpenCheck,
    Box,
    BookText,
    Palette,
    ExternalLink,
    ChevronDown,
  } from "lucide-svelte";
  import { DropdownMenu as Menu } from "bits-ui";
  import { link } from "svelte-spa-router";
  import { authState } from "../auth.svelte";
  import DropdownMenu from "./DropdownMenu.svelte";

  interface Props {
    activeView: string;
  }

  let { activeView }: Props = $props();

  const DOCS_ITEMS = [
    {
      id: "user-manual",
      label: "User Manual",
      description: "Compliance checks, BCF exports, and model inspection",
      icon: BookOpenCheck,
    },
    {
      id: "modeling-manual",
      label: "Modeling Manual",
      description: "IFC authoring conventions, space boundaries, and property sets",
      icon: Box,
    },
    {
      id: "bsdd-wiki",
      label: "bSDD Wiki",
      description: "buildingSMART Data Dictionary classifications & properties",
      icon: BookText,
    },
    {
      id: "design-system",
      label: "Design System",
      description: "Interactive catalog of semantic design tokens & bits-ui components",
      icon: Palette,
    },
  ];

  let isActive = $derived(DOCS_ITEMS.some((item) => item.id === activeView));
</script>

<div class="hidden sm:block">
  <DropdownMenu width="w-80 md:w-96" align="end">
    {#snippet trigger({ props })}
      <button
        type="button"
        {...props}
        class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors {isActive
          ? 'border-accent/40 bg-accent/15 text-accent'
          : 'border-border-default bg-surface-card text-fg-muted hover:border-border-interactive hover:text-fg-primary'}"
        aria-label="Documentation menu"
      >
        <BookOpen class="h-3.5 w-3.5" />
        <span>Documentation</span>
        <ChevronDown class="h-3 w-3" />
      </button>
    {/snippet}

    <div class="px-2.5 py-2 border-b border-border-subtle">
      <p class="text-xs font-semibold text-fg-primary">Guides & References</p>
      <p class="text-nano text-fg-muted">Platform documentation, authoring manuals, and developer resources</p>
    </div>

    <div class="py-1 space-y-0.5">
      {#each DOCS_ITEMS as item (item.id)}
        <Menu.Item>
          {#snippet child({ props })}
            <a
              {...props}
              href={authState.activeOrganizationId
                ? `/${item.id}?org=${authState.activeOrganizationId}`
                : `/${item.id}`}
              use:link
              class="flex items-start gap-2.5 rounded-lg p-2 text-left transition-colors data-highlighted:bg-surface-hover {activeView === item.id
                ? 'bg-accent/10 text-accent font-medium'
                : 'text-fg-secondary hover:text-fg-primary'}"
            >
              <item.icon class="h-4 w-4 mt-0.5 shrink-0 {activeView === item.id ? 'text-accent' : 'text-fg-muted'}" />
              <div class="min-w-0 flex-1">
                <div class="text-xs font-medium leading-none {activeView === item.id ? 'text-accent' : 'text-fg-primary'}">
                  {item.label}
                </div>
                <div class="text-nano text-fg-muted leading-tight mt-1 line-clamp-1">
                  {item.description}
                </div>
              </div>
            </a>
          {/snippet}
        </Menu.Item>
      {/each}
    </div>

    <div class="pt-1.5 border-t border-border-subtle px-1">
      <Menu.Item>
        {#snippet child({ props })}
          <a
            {...props}
            href="/api/docs"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center justify-between rounded-lg px-2.5 py-1.5 text-xs text-fg-muted transition-colors hover:text-accent data-highlighted:bg-surface-hover data-highlighted:text-accent"
          >
            <span class="font-medium">OpenAPI Specs (/api/docs)</span>
            <ExternalLink class="h-3.5 w-3.5" />
          </a>
        {/snippet}
      </Menu.Item>
    </div>
  </DropdownMenu>
</div>
