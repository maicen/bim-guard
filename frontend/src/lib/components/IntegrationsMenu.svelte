<script lang="ts">
  import { RefreshCw, Download, Plug, ChevronDown } from "lucide-svelte";
  import { DropdownMenu as Menu } from "bits-ui";
  import { link } from "svelte-spa-router";
  import { authState } from "../auth.svelte";
  import DropdownMenu from "./DropdownMenu.svelte";

  interface Props {
    activeView: string;
  }

  let { activeView }: Props = $props();

  // Pulled out of the working sidebar into its own navbar menu, same
  // treatment as Resources (see ResourcesMenu.svelte) — these are external
  // sync/export destinations rather than day-to-day project work, so they
  // don't need a permanent sidebar section.
  const ITEMS = [
    { id: "revit-sync", label: "Revit Direct Sync", icon: RefreshCw },
    { id: "ifc-export-setting", label: "IFC Export Setting for Architectural Model", icon: Download },
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
        <Plug class="h-3.5 w-3.5" />
        Integrations
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
            class="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs font-medium transition-colors data-highlighted:bg-surface-hover data-highlighted:text-fg-primary {activeView ===
            item.id
              ? 'bg-accent text-white'
              : 'text-fg-secondary'}"
          >
            <item.icon class="h-3.5 w-3.5" />
            {item.label}
          </a>
        {/snippet}
      </Menu.Item>
    {/each}
  </DropdownMenu>
</div>
