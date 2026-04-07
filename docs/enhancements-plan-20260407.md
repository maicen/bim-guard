## BIM-Guard Enhancements Plan (Updated 2026-04-07)

This document was refreshed against the current codebase state in this workspace.

## Status Snapshot

Completed since the original draft:

- `orchestrator.run_dashboard()` and `orchestrator.orchestrate_workflow()` are implemented.
- `/analysis/run` now has a working form and `/analysis/results` executes workflow calls.
- IFC analysis output now includes per-type counts (`ifc_type_counts`) instead of only a single total.
- `RuleExtractionService.extract_rules()` is no longer a fake sleep + hardcoded return.
- Gemini via LiteLLM is integrated through `LiteLLMGeminiRuleExtractor`.
- PDF text chunking is now more robust than simple double-newline splitting.
- Document upload validation now includes extension + MIME + content-signature checks.
- `.env` loading is wired through `python-dotenv` at startup.

Still pending:

- Real logic in Modules 3, 4, and 5 (currently placeholder return values).
- AuthN/AuthZ.
- `.sesskey` remediation.
- Deeper IFC geometry/spatial validation and reporting exports.

## 1) Core Modules and Workflow

### Current state

- **Module 3 (RuleBuilder):** methods return placeholders (`[]` / `None`) and are not yet production logic.
- **Module 4 (Comparator):** methods return placeholders (`[]`).
- **Module 5 (Reporter):** methods return placeholders (`""` / `None`).
- **Orchestrator:** implemented and wired; executes modules in sequence and returns structured result payloads.

### Remaining enhancements

- Implement RuleBuilder output schema that can feed comparator checks.
- Implement comparator checks against:
  - metadata constraints
  - naming conventions
  - spatial/clearance checks
- Implement reporter outputs:
  - CSV summary
  - BCF topic generation
  - visual report payloads for UI

## 2) AI Rule Extraction

### Current state

- `RuleExtractionService` orchestrates:
  - PDF parse (`Module1_DocReader.parse_pdf`)
  - chunk generation (`extract_text_sections`)
  - chunk-wise provider calls
  - de-duplication of extracted rules
- `LiteLLMGeminiRuleExtractor` calls Gemini using LiteLLM (`acompletion`) with JSON response format.
- Env-driven config is active:
  - `GEMINI_API_KEY` or `GOOGLE_API_KEY`
  - `BIM_GUARD_RULE_MODEL` (default: `gemini/gemini-1.5-flash`)

### Remaining enhancements

- Add OCR fallback for scanned/image-only PDFs (current parser relies on extractable text).
- Add retry/backoff and structured error types for provider failures.
- Add prompt+schema versioning for predictable upgrades.
- Persist extraction provenance (chunk id, source span, confidence).

## 3) IFC Parsing and Validation Depth

### Current state

- Module 2 extracts `IfcBuildingElement` entries with properties and supports type counting.
- Pipeline surfaces IFC parsing errors and no-file cases safely in UI.

### Remaining enhancements

- Extend to IFC4/IFC4.3-aware handling.
- Add spatial structure traversal (`IfcSite`, `IfcBuilding`, `IfcBuildingStorey`, `IfcSpace`).
- Add type-level checks (`Ifc*Type` classes).
- Add geometry primitives needed for clearance rules.
- Revisit `ifc_parser.py` toy behavior and align with module pipeline.

## 4) Analysis and Reports UX

### Current state

- `/analysis/run` is functional (project/doc selection, HTMX submit, results rendering).
- `/analysis/results` calls orchestrator and renders IFC/doc summaries.
- `/reports` is still a placeholder page.

### Remaining enhancements

- Add rule-set selection and run configuration in analysis UI.
- Add progressive run status for long-running operations.
- Implement report filtering, history, and export actions (CSV/PDF/BCF).

## 5) Security

### Current state

- `documents_upload` now validates extension + MIME + content signature/shape.

### Critical gaps

- `.sesskey` exists in repo and should be rotated/removed from source control.
- No authentication/authorization yet.
- No per-project access control boundaries.

## 6) Database and Persistence

### Current state

- SQLite/fastlite remains suitable for local/dev workflows.

### Remaining enhancements

- Introduce explicit migrations instead of opportunistic startup column adds.
- Improve rule parameter storage/queryability (SQLite JSON functions or structured columns).
- Add relational links for run history (project + documents + ruleset + output artifacts).

## 7) Performance and Architecture

### Current state

- Route modules use singleton-like service/module instances at module scope.
- Workflow remains synchronous for heavy tasks.

### Remaining enhancements

- Move large IFC processing and LLM extraction to background jobs.
- Add caching for repeated analyses on unchanged inputs.
- Revisit viewer script data handoff hardening (even with JSON encoding).

## Revised Priority Matrix

| Priority | Area | Effort |
|---|---|---|
| 🔴 Critical | Rotate/remove `.sesskey`, add auth/authz | Medium |
| 🔴 Critical | Implement Module 3/4/5 real logic | High |
| 🟠 High | IFC geometry + spatial validation depth | High |
| 🟠 High | Reporting exports (CSV/BCF/PDF) | Medium |
| 🟡 Medium | Background jobs for IFC/LLM workloads | Medium |
| 🟡 Medium | OCR fallback for scanned PDFs | Medium |
| 🟢 Low | Migration framework and DB normalization | Medium |

## Suggested Next Milestone

1. Security baseline: remove `.sesskey` from repo, rotate secrets, and add auth gate.
2. Vertical slice: implement one real comparator rule end-to-end (extract -> compare -> report).
3. Reporting MVP: CSV export + persisted run history.
4. Reliability pass: retries/timeouts/telemetry for Gemini calls.
