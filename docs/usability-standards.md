# BIM-Guard — Usability Standards

| | |
| --- | --- |
| **Document** | `docs/usability-standards.md` |
| **Version** | 1.0 |
| **Status** | Active — formalizes existing practice, introduces no new rules |
| **Scope** | ISO 9241 alignment and Nielsen's 10 usability heuristics, mapped onto BIM-Guard's actual frontend components and conventions |
| **Owner** | Group 5 — Masters in BIM Management, Zigurat Global Institute of Technology |

> This document does not introduce new conventions. Every rule and component
> named below already exists in `frontend/src/lib/components/`, `DESIGN.md`,
> and `CLAUDE.md`; this is the first place they are named against the
> standards they satisfy, for enterprise/government procurement review.

---

## 1. ISO 9241 Alignment

ISO 9241 ("Ergonomics of human-system interaction") is not a certification
BIM-Guard holds — it is a process standard for user-centered design and
usability evaluation. BIM-Guard's practice already matches its spirit rather
than treating it as paperwork to retrofit:

- **A single source of truth for the interface's visual language.**
  `frontend/src/app.css`'s `@theme` block (Tailwind v4) defines every color,
  spacing, and typography token once; `DESIGN.md` is the living specification
  of how those tokens compose into components, reviewed and versioned like
  code rather than existing only as a design tool file.
- **A living, browsable interface catalog.** The `#/design-system` route
  (`DESIGN.md` §13) renders every shared component in its current state,
  giving reviewers (and this document) a concrete surface to check claims
  against, rather than a static screenshot that drifts from the real app.
- **Iterative conventions enforced at review time.** `CLAUDE.md`'s frontend
  guidelines (component reuse, the ban on raw HTML form controls, the
  Universal Data Table UX Standards) are applied on every PR that touches
  `frontend/src/`, not audited after the fact.

## 2. Nielsen's 10 Usability Heuristics

Each heuristic below is backed by a specific, existing component or
convention — not a general claim of "good UX."

| # | Heuristic | How BIM-Guard satisfies it | Where |
| --- | --- | --- | --- |
| 1 | Visibility of system status | Pipeline stage transitions (Validation → Parsing → Engine Run → Scoring → Reporting) stream live via SSE and render as progress | [`PipelineProgress.svelte`](../frontend/src/lib/components/PipelineProgress.svelte), [`GlobalPipelineStatus.svelte`](../frontend/src/lib/components/GlobalPipelineStatus.svelte), [`ui/Progress.svelte`](../frontend/src/lib/components/ui/Progress.svelte), loading states via [`LoadingState.svelte`](../frontend/src/lib/components/LoadingState.svelte) |
| 2 | Match between system and the real world | Domain-accurate ISO 19650 CDE state and severity language instead of generic labels | [`IsoGovernanceBadges.svelte`](../frontend/src/lib/components/IsoGovernanceBadges.svelte), [`SeverityBadge.svelte`](../frontend/src/lib/components/SeverityBadge.svelte) |
| 3 | User control and freedom | Every destructive/bulk action is confirmable and cancelable before it commits | [`ConfirmModal.svelte`](../frontend/src/lib/components/ConfirmModal.svelte) (bits-ui `AlertDialog`), [`Modal.svelte`](../frontend/src/lib/components/Modal.svelte) (Escape/backdrop dismissal), [`BulkActionBar.svelte`](../frontend/src/lib/components/BulkActionBar.svelte)'s clear-selection action |
| 4 | Consistency and standards | One token system for every surface/color/border; one control library for every interactive element | `frontend/src/app.css` `@theme`; `CLAUDE.md`'s ban on raw `<select>`/`<input type=checkbox>`/etc. in favor of bits-ui primitives (`DESIGN.md` §12) |
| 5 | Error prevention | Required-field and shape validation happens before submission, not after a failed request | [`ui/FormField.svelte`](../frontend/src/lib/components/ui/FormField.svelte), `ConfirmModal` gating on every delete/bulk action |
| 6 | Recognition rather than recall | Sortable, filterable tables show current sort/filter state instead of requiring the user to remember it | [`SortHeader.svelte`](../frontend/src/lib/components/SortHeader.svelte), persistent search/filter toolbars on every data table (per `CLAUDE.md`'s Universal Data Table UX Standards) |
| 7 | Flexibility and efficiency of use | A command palette for power users, configurable page density for everyone else | [`ui/Command.svelte`](../frontend/src/lib/components/ui/Command.svelte) (Cmd+K), [`TablePagination.svelte`](../frontend/src/lib/components/TablePagination.svelte)'s page-size selector |
| 8 | Aesthetic and minimalist design | A restrained type ramp and explicit anti-patterns list keep screens from accreting unnecessary chrome | `DESIGN.md` §3 (Typography), §7 (Do's/Don'ts) |
| 9 | Help users recognize, diagnose, and recover from errors | Errors surface inline with actionable text, not a raw stack trace or silent failure | [`Alert.svelte`](../frontend/src/lib/components/Alert.svelte), toast notifications (`toasts.fromError`, used throughout `frontend/src/routes/`) |
| 10 | Help and documentation | Contextual hints appear where the decision is made, plus a live reference of every component | [`Tooltip.svelte`](../frontend/src/lib/components/ui/Tooltip.svelte), [`HoverCard.svelte`](../frontend/src/lib/components/HoverCard.svelte), the `#/design-system` showcase (`DESIGN.md` §13) |

## 3. Known Gap: No Automated Enforcement

`frontend/eslint.config.js` currently carries only generic
`eslint-plugin-svelte` rules (`valid-compile`, `no-at-html-tags`,
`button-has-type: warn`) — there is no custom lint rule that mechanically
enforces `CLAUDE.md`'s "Strict Ban on Raw HTML Controls," and no dedicated CI
workflow gates `npm run lint` / `npm run check` before merge (the only
workflow present, `.github/workflows/deploy-pages.yml`, builds and deploys
without a lint/test/a11y step). Today, every rule in this document is
enforced by code review, not tooling. Closing this gap — a custom ESLint rule
for raw control tags, and wiring `lint`/`check` into CI — is tracked as
follow-up work, not claimed as done here.

## 4. Related Documents

- [`DESIGN.md`](../DESIGN.md) — the visual/token specification this document's
  ISO 9241 section references (§1 tokens, §11 data-table UX spec, §12 shared
  components, §13 living showcase).
- [`docs/CONVENTIONS.md`](CONVENTIONS.md) — frontend engineering conventions;
  see its Frontend section for the pointer back here.
