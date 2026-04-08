# Revised Open Issue Backlog

Each issue below is referenced by its GitHub issue number and mapped to the work that belongs in this repo.

Backend / core workflow

## 22 — Implement IFC compliance check core logic ([#22](https://github.com/maicen/bim-guard/issues/22))

Body: Build `check_ifc()` to parse IFC geometry, apply extracted rules, and return compliance findings. Use `Module2_IFCRead`, the rule comparator, and the orchestrator workflow.

- Work reference: Core comparator, IFC geometry extraction, and rule evaluation.

## 23 — Add `/check` backend endpoint for the compliance workflow ([#23](https://github.com/maicen/bim-guard/issues/23))

Body: Create the endpoint that accepts project and document IDs, runs the orchestrator, and returns IFC stats, extracted document sections, rules, violations, and report metadata.

- Work reference: Routing, request validation, orchestrator integration.

## 24 — Add `/generate-rules` endpoint using Gemini rule extraction ([#24](https://github.com/maicen/bim-guard/issues/24))

Body: Implement backend rule extraction from uploaded BEP/PDF documents using `Module1_DocReader` and `RuleExtractionService`, returning normalized JSON rules.

- Work reference: Document parsing, AI rule extraction, schema normalization.

## 25 — Implement BCF exporter for compliance issues ([#25](https://github.com/maicen/bim-guard/issues/25))

Body: Build `bcf_exporter.py` to convert compliance findings into valid BCF file format for issue sharing.

- Work reference: Export logic, BCF structure, downloadable artifact generation.

## 26 — Add `/check/bcf` endpoint to return downloadable BCF output ([#26](https://github.com/maicen/bim-guard/issues/26))

Body: Create the API route that generates and serves the BCF file produced from the current validation result.

- Work reference: response streaming, file headers, endpoint integration.

## 27 — Add backend tests for the compliance workflow ([#27](https://github.com/maicen/bim-guard/issues/27))

Body: Write `tests/test_check.py` covering IFC validation, rule generation, endpoint behavior, and expected output structure.

- Work reference: test coverage, contract verification, regression protection.

Deployment / repo alignment

## 28 — Create production deployment config for Render ([#28](https://github.com/maicen/bim-guard/issues/28))

Body: Add deployment settings such as `render.yaml` or equivalent to host the FastHTML app in production.

- Work reference: production readiness, deployment config.

## 29 — Deploy BIM Guard backend and verify health endpoint ([#29](https://github.com/maicen/bim-guard/issues/29))

Body: Deploy the app, then verify the health endpoint returns `200` and the application is reachable.

- Work reference: deployment verification, operational check.

## 30 — Update `api_contract.md` with live deployment details ([#30](https://github.com/maicen/bim-guard/issues/30))

Body: Document the deployed API base URL and the expected request/response contract for `/check`, `/check/bcf`, and `/generate-rules`.

- Work reference: API docs and team handoff.

## 31 — Record an end-to-end demo of the deployed BIM Guard app ([#31](https://github.com/maicen/bim-guard/issues/31))

Body: Capture a short demo that shows upload, compliance check, results review, and BCF/PDF downloads.

- Work reference: demo evidence, stakeholder visibility.

## 32 — Document the BIM Guard repo setup and architecture ([#32](https://github.com/maicen/bim-guard/issues/32))

Body: Replace the external Lovable.ai setup task with a repo-focused task: document the actual FastHTML/MonsterUI full-stack architecture, routes, modules, and environment setup. Include how the app is launched with `uv run uvicorn main:app` and how FastHTML serves both UI and backend routes.

- Work reference: repo architecture documentation.

## 33 — Align backlog with the actual BIM Guard implementation ([#33](https://github.com/maicen/bim-guard/issues/33))

Body: Remove references to Lovable.ai export workflow and replace with real repo onboarding work for `maicen/bim-guard`. Emphasize that this repo is a FastHTML full-stack Python app, not a separate React frontend.

- Work reference: backlog cleanup and task alignment.

## 34 — Deploy the BIM Guard app to a public host and verify it works ([#34](https://github.com/maicen/bim-guard/issues/34))

Body: Publish the app to a production host and confirm the full workflow is operational from the public URL.

- Work reference: public deployment and live validation.

## 35 — Connect the FastHTML full-stack UI to live backend API instead of mock data ([#35](https://github.com/maicen/bim-guard/issues/35))

Body: Update the app so the FastHTML upload form and results views call real backend endpoints instead of placeholder mock data. Confirm the UI receives real compliance results from the backend.

- Work reference: FastHTML frontend/backend integration.

## 36 — Record a full demo video of the completed workflow ([#36](https://github.com/maicen/bim-guard/issues/36))

Body: Capture the full user flow from upload through report export, using the live app.

- Work reference: final demo capture.

Frontend / UI experience

## 37 — Build the IFC file upload component with drag-and-drop support ([#37](https://github.com/maicen/bim-guard/issues/37))

Body: Create the upload UI for IFC files, including a drag/drop zone and validation messaging.

- Work reference: file upload UI component.

## 38 — Add optional BEP/building code PDF upload ([#38](https://github.com/maicen/bim-guard/issues/38))

Body: Extend the upload screen so users can optionally upload a PDF with building code or regulation documents.

- Work reference: optional PDF upload support.

## 39 — Add project name and environment class metadata fields ([#39](https://github.com/maicen/bim-guard/issues/39))

Body: Add form fields for project name and environment class selection to the upload UI.

- Work reference: metadata capture.

## 40 — Connect the upload screen to the Python Gemini backend ([#40](https://github.com/maicen/bim-guard/issues/40))

Body: Replace the old client-side Claude integration with the repository's Python backend flow. The FastHTML upload form should submit to a backend route and trigger `app/modules/orchestrator.py` and `app/modules/module3_rule_builder.py` to parse IFC, extract rules via Gemini, and render results. Avoid React/Claude frontend calls.

- Work reference: FastHTML route wiring, Gemini integration, backend compliance workflow.

## 41 — Use HTMX loading state for compliance check processing ([#41](https://github.com/maicen/bim-guard/issues/41))

Body: Implement the loading experience using HTMX indicators on the FastHTML upload form. While the backend processes IFC parsing and Gemini extraction, show an animated spinner or progress state with `hx-indicator` instead of React state.

- Work reference: HTMX loading UX for Python-backed processing.

## 42 — Build summary cards row using FastHTML components ([#42](https://github.com/maicen/bim-guard/issues/42))

Body: Render summary cards for total issues and risk counts (High / Medium / Low) in the FastHTML results page. Use the project’s existing FastHTML/MonsterUI components, not React.

- Work reference: server-side result dashboard UI.

## 43 — Build the compliance issues table using FastHTML ([#43](https://github.com/maicen/bim-guard/issues/43))

Body: Render validation findings in a FastHTML-generated table and make rows interactive. Use HTMX and server-rendered HTML for row actions, rather than React state management.

- Work reference: FastHTML issue list display and HTMX interactions.

## 44 — Add HTMX filter buttons for issue risk levels ([#44](https://github.com/maicen/bim-guard/issues/44))

Body: Implement High/Medium/Low filter buttons that use HTMX requests to reload the issue list from the backend. Filtering should be handled server-side and swapped into the page dynamically.

- Work reference: HTMX filtering controls and backend rendering.

## 45 — Add a FastHTML empty state for no issues found ([#45](https://github.com/maicen/bim-guard/issues/45))

Body: Render a friendly empty state from the backend when there are no compliance findings. The empty state should display in the results area using FastHTML.

- Work reference: backend-rendered no-results UX.

## 46 — Add a New Check button and project header to results ([#46](https://github.com/maicen/bim-guard/issues/46))

Body: Add a results page header showing the project name and a `New Check` action that returns the user to the upload workflow. Use FastHTML and standard navigation or HTMX to reset the workflow.

- Work reference: workflow restart and context display.

## 47 — Build issue detail side panel with HTMX partial swaps ([#47](https://github.com/maicen/bim-guard/issues/47))

Body: Show issue details in a side panel loaded via HTMX when a row is clicked. Include rule name, violation details, risk score, and recommended action. Avoid React state and use Python-rendered HTML.

- Work reference: HTMX issue detail panel.

## 48 — Build backend BCF generation endpoint ([#48](https://github.com/maicen/bim-guard/issues/48))

Body: Implement backend BCF generation in Python and expose it through a FastHTML route or endpoint. Use Python XML/zip logic to produce a downloadable `.bcf` file returned via `FileResponse`.

- Work reference: server-side BCF export.

## 49 — Build backend PDF report generation endpoint ([#49](https://github.com/maicen/bim-guard/issues/49))

Body: Implement PDF report generation entirely in Python, using a library such as `fpdf2`. Expose a route that returns the generated PDF as a downloadable file response.

- Work reference: server-side PDF export.

## 50 — Add backend-powered BCF and PDF download actions ([#50](https://github.com/maicen/bim-guard/issues/50))

Body: Add buttons to the results page that call backend routes to download BCF and PDF exports. The exports must be generated server-side and returned as file downloads.

- Work reference: backend-driven download actions.

## 51 — Test the full FastHTML/HTMX/Gemini workflow with a sample IFC file ([#51](https://github.com/maicen/bim-guard/issues/51))

Body: Validate the complete BIM Guard workflow using the repository's actual architecture. Confirm IFC upload, Gemini-based rule extraction, HTMX-rendered results, and downloadable BCF/PDF output work correctly. Use the vanilla JS viewer in `static/js/ifc-viewer.js` rather than React or `@thatopen/components`.

- Work reference: end-to-end FastHTML/Gemini validation.

---

## Notes

This document now includes direct issue links to the GitHub backlog and a short reference for the work associated with each issue. Use it as the running tracker for progress in `docs/` while we work through the backlog.
