# bits-ui conventions

Headless Svelte 5 primitives for interaction-heavy UI (menus, popovers,
selects). Two are already shipped: [`HoverCard.svelte`](../../../../frontend/src/lib/components/HoverCard.svelte)
(on `Popover`) and [`DropdownMenu.svelte`](../../../../frontend/src/lib/components/DropdownMenu.svelte)
(wrapping `DropdownMenu`, used by `IntegrationsMenu`/`ResourcesMenu`/`UserMenu`/
`RulesView`'s Import/Export menu). `OrgSwitcher.svelte` is built on `Select`.

## When to reach for it, and when not to

Reach for bits-ui when a component has genuine interaction/focus/positioning
complexity, or the same logic is duplicated across 3+ files. Two real examples
from this codebase:

- `IntegrationsMenu`/`ResourcesMenu`/`UserMenu`/`RulesView`'s Import/Export menu
  each hand-rolled the identical open/close/outside-click recipe — no Escape,
  no arrow-key nav. One `DropdownMenu` wrapper replaced all four.
- `HoverCard`'s old hand-rolled flip/clamp positioning math and scroll/resize
  listeners were genuinely fragile. bits-ui's `Popover` (Floating UI under the
  hood) replaced them outright.

Don't reach for it when a component is already simple or already solid.
`Modal.svelte`'s `dialog.svelte.ts` attachment already has a correct focus
trap, scroll lock, and dialog stacking — migrating it to bits-ui's `Dialog`
would swap working code for a dependency with no behavioral gain.

## The child-snippet pattern — only when overriding the rendered element

bits-ui's primitives already render a sensible default element
(`Popover.Trigger`/`DropdownMenu.Trigger` → `<button>`). The `child` snippet is
for when that default is wrong for the use case — an `<a>` for real
navigation, a non-focusable `<span>` — not a pattern to reach for by default.

```svelte
<!-- DropdownMenu.svelte -->
<Menu.Trigger>
  {#snippet child({ props })}
    {@render trigger?.({ props })}
  {/snippet}
</Menu.Trigger>
```

```svelte
<!-- IntegrationsMenu.svelte — the caller supplies the actual element -->
<Menu.Item>
  {#snippet child({ props })}
    <a {...props} href="/revit-sync" use:link class="...">Revit Direct Sync</a>
  {/snippet}
</Menu.Item>
```

A plain `<button onSelect={fn}>Text</button>`-shaped item (see `UserMenu.svelte`)
needs no `child` snippet at all — bits-ui's own rendered element is fine.

## Portal is not automatic

Every overlay (`Popover`, `DropdownMenu`, `Select`) needs its own explicit
`*.Portal` wrapping `*.Content` — bits-ui does not portal by default.

```svelte
<Popover.Portal>
  <Popover.Content>...</Popover.Content>
</Popover.Portal>
```

## Styling: plain Tailwind classes, merged with `cn()`

bits-ui itself is unstyled and has no opinion beyond "pass classes to `class`"
— nothing to reconcile with bits-ui there. But a wrapper component that has
its *own* base classes plus a caller-supplied override point (`contentClass`,
`triggerClass`) is exactly what `cn()` (`lib/utils/cn.ts`) exists for — it
resolves Tailwind conflicts left-to-right so a caller override reliably wins,
which plain string interpolation does not guarantee:

```svelte
class={cn(
  "z-40 space-y-1 rounded-xl border border-slate-800 bg-slate-900 p-1.5 ...",
  contentClass,
)}
```

## Data-attribute state styling — the only hook bits-ui exposes

bits-ui's primitives are headless and expose state exclusively via data
attributes — `data-[state=open]`, `data-[side=...]`, `data-highlighted`. This
is not a stylistic choice; style state this way, not with a manual class:

```
data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95
```

## Controlled vs. uncontrolled state

- **Uncontrolled** (no `open`/`value` prop passed) when bits-ui's own internal
  state is sufficient — nothing outside needs to know or drive it.
  `DropdownMenu.svelte` is uncontrolled.
- **Controlled** (one-way `value`/`open` + `onValueChange`/`onOpenChange`)
  when the real value lives outside the component and must be pushed in and
  reacted to. `HoverCard.svelte` controls `open` to run its own hover-delay
  timers instead of trusting bits-ui's built-in hover heuristic (which proved
  unreliable — it could leave the card open indefinitely once the pointer
  left both trigger and content). `OrgSwitcher.svelte` controls `value`
  because the real value is `authState.activeOrganizationId`, not a local copy.
- **Function-binding** (`bind:value={get, set}`) is for when the setter itself
  needs custom logic beyond "assign the new value" — not currently needed
  anywhere in this codebase.

## Typing wrapper props: `WithoutChild` / `WithoutChildren` / `WithoutChildrenOrChild`

Optional, not required by bits-ui — a convenience for extending a primitive's
own `*Props` type instead of hand-declaring an interface from scratch:

```ts
import { DropdownMenu, type WithoutChildrenOrChild } from "bits-ui";

let { title, ...restProps }: WithoutChildrenOrChild<DropdownMenu.RootProps & { title: string }> =
  $props();
```

`DropdownMenu.svelte`'s hand-declared `Props` interface still works and isn't
being changed retroactively — use the type helpers for new wrapper components
going forward.

## Utilities not yet adopted

- **`mergeProps`** — not currently needed. Every existing wrapper either
  spreads bits-ui's `props` once onto its own element, or lets bits-ui merge
  internally (event handlers passed directly to a primitive, e.g.
  `HoverCard.svelte`'s `onmouseenter`/`onfocusin` on `Popover.Trigger`, are
  merged by bits-ui itself). It becomes relevant the moment a wrapper needs to
  combine a caller-supplied handler with one the wrapper itself already sets
  on the same element.
- **`useId`** — relevant for label/input association in a future form-like
  component (`import { useId } from "bits-ui"`).
- **`BitsConfig`** — a global context provider for `defaultPortalTo`/
  `defaultLocale`. Relevant only if a non-`<body>` portal root or a non-`en`
  default locale is ever needed; neither applies today.

## Stack note

Tailwind v4 (`@tailwindcss/vite`; theme tokens in `frontend/src/app.css`'s
`@theme` block, no `tailwind.config.js`) — the same major version bits-ui's
own docs and examples use, so its syntax (e.g. `origin-(--css-var)`) can be
copied directly.
