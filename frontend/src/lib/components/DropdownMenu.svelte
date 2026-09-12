<!--
  DropdownMenu — thin bits-ui wrapper for a triggered menu popover.

  Consolidates the open/close/positioning boilerplate that IntegrationsMenu,
  ResourcesMenu, UserMenu, and RulesView's Import/Export menu each hand-rolled
  independently (a `$state` boolean plus a `svelte:document`/`window` click
  listener, with no Escape or arrow-key handling). bits-ui's `DropdownMenu`
  underneath supplies Escape/outside-click dismissal, focus trap/return, and
  roving keyboard navigation between items for free.

  Callers keep full control of the trigger button and menu item markup:
  import bits-ui's `DropdownMenu` directly for `.Item` / `.Separator` /
  `.Group` inside the `children` snippet.

  Usage:

      <script lang="ts">
        import { DropdownMenu as Menu } from "bits-ui";
        import DropdownMenu from "./DropdownMenu.svelte";
      </script>

      <DropdownMenu width="w-52">
        {#snippet trigger({ props })}
          <button type="button" {...props} class="...">Integrations</button>
        {/snippet}

        <Menu.Item onSelect={doSomething} class="...">Do something</Menu.Item>
      </DropdownMenu>

  A link item that should stay a real `<a>` (right-click / open-in-new-tab,
  `use:link` routing) renders via `Menu.Item`'s own `child` snippet:

      <Menu.Item>
        {#snippet child({ props })}
          <a {...props} href="/foo" use:link class="...">Foo</a>
        {/snippet}
      </Menu.Item>
-->
<script lang="ts">
  import type { Snippet } from "svelte";
  import { DropdownMenu as Menu } from "bits-ui";
  import { cn } from "../utils/cn";

  type Align = "start" | "center" | "end";
  type Side = "top" | "bottom" | "left" | "right";

  interface Props {
    /** Alignment along the trigger's cross axis. */
    align?: Align;
    /** Preferred side of the trigger to render on. Flips when space is tight. */
    side?: Side;
    /** Gap in px between trigger and menu. */
    sideOffset?: number;
    /** Tailwind width class for the menu panel. */
    width?: string;
    /** Extra classes on the menu panel. */
    contentClass?: string;
    trigger?: Snippet<[{ props: Record<string, unknown> }]>;
    children?: Snippet;
  }

  let {
    align = "end",
    side = "bottom",
    sideOffset = 8,
    width = "w-52",
    contentClass = "",
    trigger,
    children,
  }: Props = $props();
</script>

<Menu.Root>
  <Menu.Trigger>
    {#snippet child({ props })}
      {@render trigger?.({ props })}
    {/snippet}
  </Menu.Trigger>

  <Menu.Portal>
    <Menu.Content
      {align}
      {side}
      {sideOffset}
      class={cn(
        "z-40 space-y-1 rounded-xl border border-border-default bg-surface-card p-1.5 text-xs shadow-xl outline-hidden data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
        width,
        contentClass,
      )}
    >
      {@render children?.()}
    </Menu.Content>
  </Menu.Portal>
</Menu.Root>
