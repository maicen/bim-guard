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

**One palette, inverted.** `frontend/tailwind.config.js` maps the `slate` scale
onto CSS custom properties, and `frontend/src/app.css` defines those properties
twice — once for dark, once for light, with the ramp reversed:

```css
:root,
html.dark {
  --color-slate-950: 2 6 23;
  --color-slate-50: 248 250 252;
}
html.light {
  --color-slate-950: 248 250 252;
  --color-slate-50: 2 6 23;
}
```

Consequences to internalise before writing markup:

- **Never write a `dark:` variant.** `bg-slate-900` is a near-black card in dark
  mode and a white card in light mode, automatically.
- **`text-slate-50` is "primary text".** Near-white in dark mode, near-black in
  light mode. Use it for headings, labels and input values.
- **`text-white` means "always white"** and is reserved for text sitting on a
  solid coloured control (an accent button, a rose delete button, a gradient
  badge). Using it for ordinary text produces white-on-white in light mode.
- Semantic ramp: `slate-950` canvas → `slate-900` card → `slate-800` border →
  `slate-700` interactive border/hover → `slate-500/400` metadata → `slate-300`
  body → `slate-50` primary text.

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
