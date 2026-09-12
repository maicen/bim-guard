# BIMGuard Design System

BIMGuard is a dense, data-first OpenBIM compliance tool: long tables of findings,
multi-step wizards, live pipeline telemetry, and a 3D viewport. It is **not** a
marketing site, and this document describes what is actually built rather than an
aspirational look. Where a rule below conflicts with the code, the code is the
bug — except where a section explicitly marks itself as inspiration.

## Sources

The visual language draws on shadcn/basecoat component structure, adapted
for information density:

- [shadcn/ui components](https://github.com/shadcn-ui/ui/tree/main/apps/v4/registry/bases/base/ui)
- [basecoat css](https://github.com/hunvreus/basecoat/tree/main/src/css) / [js](https://github.com/hunvreus/basecoat/tree/main/src/js)
- [What is DESIGN.md?](https://stitch.withgoogle.com/docs/design-md/overview)
- [Svelte frontend README](frontend/README.md)

**Deliberate divergences from the template**, because a compliance audit
tool is not a product showcase:

| rule                              | BIMGuard                                             | Why                                                                                                            |
| --------------------------------- | ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| No borders on cards               | Borders on every card (`border-slate-800`)           | Dense grids need explicit boundaries; contrast alone cannot separate 40 stacked rows                           |
| 980px pill CTAs                   | 8–12px radius controls (`rounded-lg` / `rounded-xl`) | Pills read as consumer marketing; crisp rectangular controls sit correctly in toolbars, menus, and data tables |
| ~980px max content width          | Full viewport width                                  | Tables need every pixel                                                                                        |
| Black ↔ light-gray section rhythm | One continuous canvas                                | There are no "sections" — there are views                                                                      |
| SF Pro optical sizing             | Inter at one optical size                            | SF Pro does not exist off macOS; the app runs on Windows and Linux                                             |

## 1. Theme architecture (authoritative)

**Tailwind v4.** All theme tokens live in `frontend/src/app.css`'s `@theme` block —
there is no `tailwind.config.js`. The build runs via `@tailwindcss/vite`.

**One palette, inverted.** Each `@theme` color (e.g. `--color-slate-950`) resolves
through a separate `-rgb` "channel" variable (`--slate-950-rgb`) that `app.css`
redefines twice — once for dark, once for light, with the ramp reversed. The
channel and the theme-color variable are deliberately named differently: a
`@theme` variable name becomes a real, unlayered-cascade-winning CSS custom
property the moment anything redefines it, so reusing the same name for the
per-theme channel would silently replace the `rgb(...)` wrapper with a bare,
invalid-as-a-color triplet.

```css
@theme {
  /* Semantic Surfaces */
  --color-surface-canvas: rgb(var(--surface-canvas-rgb));
  --color-surface-card: rgb(var(--surface-card-rgb));
  --color-surface-overlay: rgb(var(--surface-overlay-rgb));
  --color-surface-hover: rgb(var(--surface-hover-rgb));

  /* Semantic Typography / Foreground */
  --color-fg-primary: rgb(var(--fg-primary-rgb));
  --color-fg-secondary: rgb(var(--fg-secondary-rgb));
  --color-fg-muted: rgb(var(--fg-muted-rgb));

  /* Semantic Borders */
  --color-border-subtle: rgb(var(--border-subtle-rgb));
  --color-border-default: rgb(var(--border-default-rgb));
  --color-border-interactive: rgb(var(--border-interactive-rgb));

  /* Semantic Status & Severity */
  --color-critical: rgb(var(--critical-rgb));
  --color-warning: rgb(var(--warning-rgb));
  --color-caution: rgb(var(--caution-rgb));
  --color-success: rgb(var(--success-rgb));
  --color-info: rgb(var(--info-rgb));
}
```

Consequences to internalise before writing markup:

- **Prefer semantic tokens over hardcoded palette numbers.** Use `bg-surface-card`, `border-border-default`, `text-fg-primary`, and `text-fg-secondary`.
- **Never write a `dark:` variant.** Colors resolve via channel variables calibrated for WCAG AA (>= 4.5:1) in both light and dark themes.
- **`text-fg-primary` is "primary text".** High-contrast text in dark mode, deep contrast in light mode.
- **`text-white` means "always white"** and is reserved for text sitting on a solid coloured control (an accent button, a rose delete button, a gradient badge).
- Semantic ramp: `surface-canvas` background → `surface-card` container → `surface-overlay` elevated → `border-subtle` / `border-default` dividers → `fg-muted` metadata → `fg-secondary` body → `fg-primary` headline text.

Theme state lives in `frontend/src/lib/theme.ts` (`light | dark | system`,
persisted at `localStorage['bimguard_theme']`, default dark) with a blocking
FOUC-prevention script in `index.html`.

## 2. Colour

### The single accent

`--color-accent` / `--color-accent-hover`, exposed as the Tailwind `accent`
colour. Use `bg-accent`, `text-accent`, `border-accent`, `ring-accent`,
`hover:bg-accent-hover`. **Never type the hex.**

| Theme | Accent                  | Hover     |
| ----- | ----------------------- | --------- |
| Dark  | `#0071e3`               | `#0077ed` |
| Light | `#0066cc` (AA on white) | `#0071e3` |

The accent is reserved for interactive elements — primary buttons, focus rings,
active nav, links, selected states. It is not a decorative colour.

### Severity banding

Defined once in `frontend/src/lib/severity.ts` and consumed by `<SeverityBadge>`
and `<Badge>`. Do not restate these anywhere else:

| Band           | Hue     | Meaning                                                 |
| -------------- | ------- | ------------------------------------------------------- |
| `critical`     | rose    | Must be resolved before the model progresses            |
| `high`         | amber   | Significant compliance risk                             |
| `medium`       | yellow  | Should be reviewed                                      |
| `low`          | emerald | Tolerable / passing                                     |
| `data_quality` | indigo  | Doctrine-exempt: could not be assessed, not a violation |
| `neutral`      | slate   | No band                                                 |

Status colours for pipeline state (`complete`, `running`, `pending`, `failed`)
live in `<Badge>`.

Outside the accent and these bands, colour is not a design tool here.

## 3. Typography

**Inter** for UI, **JetBrains Mono** for code, GUIDs, hashes and file paths.
Both are loaded in `index.html`; the stacks in `app.css` must keep naming them.

Negative tracking applies at every size (`-0.015em` body, `-0.025em` headings).

| Token                | Size    | Use                                           |
| -------------------- | ------- | --------------------------------------------- |
| `text-nano`          | 9px     | Dense table metadata, unit suffixes           |
| `text-micro`         | 10px    | Badges, chips, table cell metadata            |
| `text-caption`       | 11px    | Labels, secondary table text, toolbar buttons |
| `text-xs`            | 12px    | Default body text in tables and modals        |
| `text-sm`            | 14px    | Nav items, form inputs                        |
| `text-base`          | 16px    | Section headings                              |
| `text-lg`–`text-3xl` | 18–30px | Page titles, stat values                      |

The sub-12px steps exist because this is a data tool; do not invent more with
`text-[Npx]`. Weights: 400 and 600 carry almost everything; 700 for stat values.
Never 800/900.

## 4. Components

Compose from `frontend/src/lib/components/` — see §12. General rules:

- **Buttons.** Primary: `bg-accent text-white`, `rounded-xl`, `px-3.5 py-2`,
  `text-caption font-semibold`. Secondary / Toolbar: `bg-slate-950 border border-slate-800
text-slate-200 hover:bg-slate-800 rounded-xl` (or `rounded-lg` for compact toolbars). Destructive: `bg-rose-600 text-white rounded-xl`.
  Every button needs a `type` and a disabled state. **Never use `rounded-full` on buttons.**
- **Dropdowns & Menus.** Triggers: `rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-xs text-slate-300 hover:border-slate-700`. Popovers / flyouts: `rounded-xl border border-slate-800 bg-slate-900 p-1.5 shadow-xl` with menu items `rounded-lg`. **Never wrap select controls or dropdown triggers in `rounded-full` pills.**
- **Badges & Status Chips.** `<Badge>` and `<SeverityBadge>` use `rounded-md border px-2 py-0.5 text-micro font-semibold uppercase tracking-wide`. Rectangular tags ensure visual hierarchy and information density on complex tables. **Never use `rounded-full` for text tags or status badges.**
- **Inputs.** `w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5
py-2.5 text-xs text-slate-50 focus:border-accent`. Always paired with a
  `<label for>`.
- **Cards.** `bg-slate-900/60 border border-slate-800 rounded-xl`. Borders stay,
  contrary to the template.
- **Glass.** `.apple-blur` (`saturate(180%) blur(20px)`) on sticky headers and
  the sidebar only.

## 5. Layout

- 8px base unit; Tailwind's default spacing scale is already on it.
- **Radius hierarchy**:
  - `rounded-sm` (4px): subtle indicators, sub-pixel borders
  - `rounded-md` (6–8px): badges, chips, tags, table row checkboxes
  - `rounded-lg` (8–11px): dropdown triggers, toolbar buttons, select inputs, popover menu items
  - `rounded-xl` (12px): cards, modals, primary CTA buttons, popover containers
  - `rounded-full`: **strictly restricted to true circles (1:1 aspect ratio)**: circular status dots (`h-1.5 w-1.5`), user avatars (`h-7 w-7`), spinner animations, circular wizard step numbers (`w-6 h-6`), and slim progress bar tracks. **Nothing rectangular or containing text may use `rounded-full`.**
- Content fills the viewport. Tables scroll horizontally inside
  `overflow-x-auto`; the page body never scrolls sideways.

## 6. Depth & motion

Elevation comes from background contrast plus a hairline border, not shadow.
Shadow is reserved for floating layers: modals, dropdowns, the bulk action bar.

| Level    | Treatment                                          |
| -------- | -------------------------------------------------- |
| Flat     | Solid surface, no shadow — the default             |
| Card     | `border border-slate-800`                          |
| Glass    | `.apple-blur` on sticky nav/header                 |
| Floating | `shadow-2xl` on modals and popovers                |
| Focus    | `2px` accent ring on **every** interactive element |

Motion is functional: `animate-in fade-in`, `zoom-in-95`, `duration-200` for
entrances (via `tailwindcss-animate`), `animate-spin` for pending work. All of it
is disabled under `prefers-reduced-motion`, which `app.css` honours globally.

## 7. Do's and Don'ts

### Do

- Use `accent` tokens for every interactive element — it is the only chromatic accent
- Use `text-slate-50` for primary text; reserve `text-white` for coloured controls
- Let the slate inversion do the theming; add no `dark:` variants
- Give every interactive element a visible `:focus-visible` ring
- Compose from `lib/components/` before writing new markup
- Keep negative tracking at all sizes
- Put wide content in `overflow-x-auto`
- Give every `{#each}` a key
- Use `rounded-md` for badges and tags, `rounded-lg` for dropdown triggers and toolbar controls, and `rounded-xl` for cards and primary action buttons

### Don't

- Don't type a hex colour in a component — use the token
- Don't add `text-[Npx]` — the ramp already goes down to 9px
- Don't introduce accent colours beyond the accent and the severity bands
- Don't use radius above 12px on rectangles
- Don't use `rounded-full` or pill borders on dropdowns, select menus, buttons, filter tabs, or data table badges
- Don't use `!important` to fix a theme problem — fix the token
- Don't use weight 800 or 900
- Don't add textures, patterns or decorative gradients
- Don't hand-roll a modal, table, badge or empty state that `lib/components/` already provides
- Don't call `fetch` from a component — go through `lib/api.ts`

## 8. Responsive behaviour

Tailwind's default breakpoints: `sm` 640, `md` 768, `lg` 1024, `xl` 1280,
`2xl` 1536.

| Range      | Behaviour                                                                                                     |
| ---------- | ------------------------------------------------------------------------------------------------------------- |
| <768px     | Sidebar collapses to an off-canvas drawer behind a hamburger; single-column forms; tables scroll horizontally |
| 768–1024px | Sidebar collapsible to icons; two-column forms                                                                |
| >1024px    | Full sidebar, multi-column layouts                                                                            |

Touch targets are at least 44×44px below `md`. Navigation links are 48px tall.
The 3D viewport must not claim a fixed height taller than the viewport.

## 9. Agent guide

### Quick reference

- Interactive: `bg-accent` / `text-accent` / `ring-accent`
- Canvas `bg-slate-950`, card `bg-slate-900`, border `border-slate-800`
- Primary text `text-slate-50`, body `text-slate-300`, metadata `text-slate-400`
- Severity: import from `lib/severity.ts`, never restate
- Class composition: `cn()` from `lib/utils/cn.ts`

### Before writing a component, ask

1. Does `lib/components/` already have it? (§12)
2. Is every colour a token — no hex, no `text-[Npx]`?
3. Does it read correctly in **both** themes? Any `text-white` on a slate surface is a bug.
4. Is it keyboard-reachable, with a visible focus ring and a label?
5. If it is a table, does it meet §11 in full?
6. Does it work at 375px wide?
7. Is it interaction/focus/positioning-heavy (a menu, popover, select, combobox)? Build it on bits-ui rather than hand-rolling — see below.

### bits-ui

Interaction-heavy components (menus, popovers, selects) are built on
[bits-ui](https://www.bits-ui.com/), not hand-rolled — see
`.claude/skills/svelte-frontend/references/bits-ui.md` for the conventions
(child-snippet delegation, `Portal`, data-attribute styling, controlled vs.
uncontrolled state). The frontend runs **Tailwind v4** (`@tailwindcss/vite`;
theme tokens live in `app.css`'s `@theme` block, not a JS config file), the
same major version bits-ui's own docs and examples assume.

## 10. Decoupled Svelte SPA Component System

The standalone frontend (`frontend/src/`) translates these design principles into modern Svelte 5 + Tailwind CSS components:

- **Surface Treatment**: Glassmorphic headers (`bg-slate-900/80 backdrop-blur-md`), elevated cards (`bg-slate-900/60 border-slate-800`), and the deep canvas background (`bg-slate-950`) — each inverting with the theme per §1.
- **Accent Rhythm**: The single `accent` token for interactive states, with dedicated risk banding for compliance findings drawn from `lib/severity.ts` (§2).
- **Real-Time Instrumentation**: The `PipelineProgress` component features animated SSE stream status pings, stage step meters, and dynamic metrics chips reflecting the active physics engines.
- **3D OpenBIM Viewport**: Enclosed viewport canvas (`IfcViewer.svelte`) featuring dark frame styling and model isolation.

## 11. Universal Data Table UX Specifications

Every data table across the application (Projects, Documents, Reports & BCF, Rules Catalog, Extracted Rules, Findings & Issues, Revit Sync) must follow these strict UX design rules:

- **Multiple Selection**: Per-row checkboxes (`w-4 h-4 rounded bg-slate-950 border-slate-700 text-accent`), header master checkbox with indeterminate and selected states, and selected row highlights (`bg-blue-950/20`).
- **Bulk Action Bar**: Sticky/floating `BulkActionBar.svelte` displaying the selected item count, quick clear button, bulk edit modal launcher, bulk delete launcher, and export buttons.
- **Table Pagination**: Uniform `TablePagination.svelte` at the footer of every table showing the current page, page size options (10, 25, 50, 100), item range (`Showing 1 to 10 of 42`), and navigation controls.
- **Search & Multi-Attribute Filters**: Filter toolbar placed above tables with a search input (`Search` icon) and categorized dropdown filters.
- **Column Sorting**: Interactive header buttons with ascending/descending arrow indicators.
- **CRUD Modals & Confirmations**: Modals for creation, editing, inspecting full details, and deleting with explicit confirmation dialogs.

## 12. Reusable UI Component Building Blocks

To maintain cohesive design patterns and avoid duplicate markup, all UI views must compose with the established core component building blocks from `frontend/src/lib/components/`:

- **`<PageHeader.svelte>`**: Standard page hero header with category breadcrumbs, icon, title, subtitle, and action slots.
- **`<Modal.svelte>`**: Reusable modal dialog wrapper with backdrop blur (`backdrop-blur-md`), keyboard `Escape` closing, header with icon, scrollable body, and `slot="footer"` button layout.
- **`<SortHeader.svelte>`**: Interactive sortable table column header with automatic ascending/descending/inactive sort icons and ARIA attributes.
- **`<TableCheckbox.svelte>`**: Unified checkbox supporting indeterminate master toggle, row-level selection, and accessibility labels.
- **`<TablePagination.svelte>`**: Dedicated table pagination component with page size selection (10, 25, 50, 100).
- **`<BulkActionBar.svelte>`**: Floating/inline bulk action toolbar when rows are selected.
- **`<EmptyState.svelte>`**: Standardized zero-state card with icon, title, description, and primary CTA button.
- **`<LoadingState.svelte>`**: Spinner loading container with configurable message and sub-message.
- **`<SeverityBadge.svelte>`**: Universal compact engineering badge (`rounded-md`) for severity levels and verdicts (`critical`, `high`, `medium`, `low`, `data_quality`, `pass`, `fail`).
- **`<IsoGovernanceBadges.svelte>`**: Standard ISO 19650 metadata tags (Suitability `S0`–`S7`, Revision `P01.01`, CDE State `WIP`/`SHARED`/`PUBLISHED`/`ARCHIVED`).
- **`<HoverCard.svelte>`**: Hover/focus-triggered rich preview popover (bits-ui `Popover`), used for supplementary detail without a click or modal.
- **`<DropdownMenu.svelte>`**: Thin bits-ui `DropdownMenu` wrapper for triggered menus (Escape/outside-click dismissal, roving keyboard nav) — used by `IntegrationsMenu`, `ResourcesMenu`, `UserMenu`, and `RulesView`'s Import/Export menu.
- **`<OrgSwitcher.svelte>`**: bits-ui `Select`-backed organization switcher in the header, syncing to `authState.activeOrganizationId`.

### Core Atomic Primitives (`frontend/src/lib/components/ui/`)

To eliminate bespoke, duplicated button and input markup across views, always prefer these shared base primitives:

- **`<Button.svelte>`**: Standardized button primitive supporting 5 variants (`primary`, `secondary`, `outline`, `ghost`, `destructive`), 5 sizes (`xs`, `sm`, `md`, `lg`, `icon`), built-in SVG loading spinner, and keyboard accessibility.
- **`<Input.svelte>`**: Form input with prefix/suffix icon slots, semantic focus rings, and reactive error border styling.
- **`<FormField.svelte>`**: Form field layout wrapper with label, required asterisk, helper text hint, and validation error messages.
- **`<Card.svelte>` / `<CardHeader.svelte>` / `<CardTitle.svelte>` / `<CardContent.svelte>`**: Semantic card container set wrapping standard background, border, and padding tokens.

## 13. Living Design System & UI Kit Showcase

A dedicated interactive showcase is available in-app at **`#/design-system`** (reachable from the top navigation under **Resources → Design System**).

The showcase allows live inspection of:
- Semantic color tokens, surface elevations, and foreground contrast levels.
- Real-time dark, light, and system theme switching side-by-side.
- The button primitive matrix across all variants, sizes, and states (including dynamic loading spinner tests).
- Form inputs, icon slot positioning, and validation error states.
- OpenBIM compliance severity badges (`critical`, `high`, `medium`, `low`, `data_quality`) and pipeline execution status chips.

