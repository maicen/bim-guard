<script lang="ts">
  import { BookOpenCheck, Box, BookText, LifeBuoy, ChevronDown, ExternalLink, Palette } from "lucide-svelte";
  import { DropdownMenu as Menu } from "bits-ui";
  import { link } from "svelte-spa-router";
  import { authState } from "../auth.svelte";
  import DropdownMenu from "./DropdownMenu.svelte";

  interface Props {
    activeView: string;
  }

  let { activeView }: Props = $props();

  // Reference material, not project work — pulled out of the working sidebar
  // (see Tenant & Workspace Blueprint, Priority 11 in TODO.md) into its own
  // navbar menu so it's reachable from any view without crowding the
  // project-focused nav groups.
  const ITEMS = [
    { id: "user-manual", label: "User Manual", icon: BookOpenCheck },
    { id: "modeling-manual", label: "Modeling Manual", icon: Box },
    { id: "bsdd-wiki", label: "bSDD Wiki", icon: BookText },
    { id: "design-system", label: "Design System", icon: Palette },
  ];

  let isActive = $derived(ITEMS.some((item) => item.id === activeView));
</script>

<div class="hidden md:block">
  <DropdownMenu width="w-52">
    {#snippet trigger({ props })}
      <button
        type="button"
        {...props}
        class="flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors {isActive
          ? 'border-accent/40 bg-accent/15 text-accent'
          : 'border-border-default bg-surface-card text-fg-muted hover:border-border-interactive hover:text-fg-primary'}"
      >
        <LifeBuoy class="h-3.5 w-3.5" />
        Resources
        <ChevronDown class="h-3 w-3" />
      </button>
    {/snippet}

    {#each ITEMS as item (item.id)}
      <Menu.Item>
        {#snippet child({ props })}
          <a
            {...props}
            href={authState.activeOrganizationId
              ? `/${item.id}?org=${authState.activeOrganizationId}`
              : `/${item.id}`}
            use:link
            class="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium transition-colors data-highlighted:bg-slate-800 data-highlighted:text-slate-50 {activeView ===
            item.id
              ? 'bg-accent text-white'
              : 'text-slate-300'}"
          >
            <item.icon class="h-3.5 w-3.5" />
            {item.label}
          </a>
        {/snippet}
      </Menu.Item>
    {/each}

    <Menu.Separator class="my-1 border-t border-slate-800" />

    <Menu.Item>
      {#snippet child({ props })}
        <a
          {...props}
          href="/api/docs"
          target="_blank"
          rel="noopener noreferrer"
          class="flex items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium text-slate-300 transition-colors data-highlighted:bg-slate-800 data-highlighted:text-slate-50"
          title="Open Swagger OpenAPI Documentation"
        >
          <span class="flex items-center gap-2">
            <ExternalLink class="h-3.5 w-3.5" />
            API Docs
          </span>
        </a>
      {/snippet}
    </Menu.Item>
  </DropdownMenu>
</div>
