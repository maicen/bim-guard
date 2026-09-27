<script lang="ts">
  import type { Snippet } from "svelte";
  import { link } from "svelte-spa-router";
  import { useSidebar } from "./context.svelte";
  import Tooltip from "../../Tooltip.svelte";
  import { cn } from "../../../utils/cn";

  interface Props {
    isActive?: boolean;
    variant?: "default" | "outline";
    size?: "default" | "sm" | "lg";
    tooltip?: string | { text: string; hidden?: boolean };
    href?: string;
    class?: string;
    onclick?: (e: MouseEvent) => void;
    child?: Snippet<[{ props: Record<string, any> }]>;
    children?: Snippet;
  }

  let {
    isActive = false,
    variant = "default",
    size = "default",
    tooltip,
    href,
    class: className,
    onclick,
    child,
    children,
  }: Props = $props();

  let sidebar: ReturnType<typeof useSidebar> | null = null;
  try {
    sidebar = useSidebar();
  } catch {
    // If used outside of provider, fallback gracefully
  }

  let tooltipText = $derived(typeof tooltip === "string" ? tooltip : tooltip?.text);
  let isTooltipDisabled = $derived(
    !tooltipText || (typeof tooltip === "object" && tooltip.hidden) || !sidebar || sidebar.state !== "collapsed" || sidebar.isMobile
  );

  const sizeClasses = {
    default: "h-8 text-sm",
    sm: "h-7 text-xs",
    lg: "h-12 text-sm group-data-[collapsible=icon]:size-10!",
  };

  const variantClasses = {
    default: "hover:bg-surface-hover hover:text-fg-primary active:bg-surface-hover data-[active=true]:bg-accent data-[active=true]:text-white data-[active=true]:font-medium data-[active=true]:shadow-xs data-[active=true]:shadow-blue-600/30",
    outline: "bg-surface-card border border-border-default hover:bg-surface-hover hover:border-border-interactive active:bg-surface-hover data-[active=true]:border-accent data-[active=true]:bg-accent/10 data-[active=true]:text-accent",
  };

  const buttonClasses = $derived(
    cn(
      "peer/menu-button flex w-full items-center gap-2.5 overflow-hidden rounded-lg p-2 text-left text-sm outline-hidden transition-[width,height,padding,background-color,color] duration-150 focus-visible:ring-2 focus-visible:ring-accent disabled:pointer-events-none disabled:opacity-50 select-none",
      "group-has-data-[sidebar=menu-action]/menu-item:pr-8",
      "group-data-[collapsible=icon]:size-8 group-data-[collapsible=icon]:p-2 group-data-[collapsible=icon]:justify-center",
      "[&>span:last-child]:truncate [&>svg]:size-4 [&>svg]:shrink-0",
      sizeClasses[size],
      variantClasses[variant],
      isActive && variant === "default" && "bg-accent text-white font-medium shadow-xs shadow-blue-600/30",
      className,
    )
  );

  const buttonProps = $derived({
    "data-sidebar": "menu-button",
    "data-size": size,
    "data-active": isActive,
    class: buttonClasses,
    onclick,
  });
</script>

{#snippet content()}
  {#if child}
    {@render child({ props: buttonProps })}
  {:else if href}
    <a {href} use:link {...buttonProps}>
      {@render children?.()}
    </a>
  {:else}
    <button type="button" {...buttonProps}>
      {@render children?.()}
    </button>
  {/if}
{/snippet}

{#if tooltipText}
  <Tooltip text={tooltipText} side="right" sideOffset={8} disabled={isTooltipDisabled}>
    {#snippet trigger()}
      {@render content()}
    {/snippet}
  </Tooltip>
{:else}
  {@render content()}
{/if}
