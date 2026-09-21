# app/modules — Compliance Pipeline

Framework-agnostic Python pipeline stages that sit behind the FastAPI gateway
(`app/api/`). Nothing here is domain-specific to one building code or
standard: rule content is stored in and read from the database (Supabase
`rules` table via `RuleService`), never hardcoded in these modules.

## Pipeline Overview

```
app/modules/
├── config.py                 # Shared constants for the document/rule pipeline
├── contracts.py               # Strict Pydantic data contracts (inter-module exchange)
├── orchestrator.py             # BIMGuard_App — dashboard stats + orchestrate_workflow()
├── permissions.py              # Catalogue of role-gated, superadmin-configurable actions
├── property_confidence.py      # Confidence classification for a resolved IFC property's provenance
├── room_types.py               # Room-type vocabulary/classifier for IfcSpace names
├── rule_reliability.py         # How far a rule can be trusted to run against a real IFC model
├── scim_contracts.py           # SCIM 2.0 wire-format contracts for IdP-driven provisioning
├── llm_providers/               # LLM driver adapters (Anthropic, Gemini, Ollama, OpenAI, OpenRouter)
├── document_parsing/           # Document → structured text/nodes
│   ├── docling_extractor.py       — Docling-backed PDF/table extraction
│   ├── document_extractor.py      — generic document text extraction
│   ├── section_chunker.py         — splits extracted text into clause-scoped sections
│   ├── section_tree.py / section_tree_enhancer.py — hierarchical section structure
│   ├── doclang_*.py               — Docling-derived layout element ID/asset/text/chunking helpers
│   ├── pdf_page_range.py          — PDF page-range utilities
│   ├── iso_validator.py           — ISO 19650 document/container validation helpers
│   ├── llamaindex_ingestor.py      — LlamaIndex ingestion (table/layout-aware chunking,
│   │                                 clause metadata), gated by
│   │                                 BIM_GUARD_USE_LLAMAINDEX_INGESTION
│   ├── llamaindex_program.py      — deontic statement extraction (shall/must/should)
│   ├── engines/                   — parsing-engine driver adapters (Docling today)
│   └── keywords/                  — keyword reference data used by extraction heuristics
├── rule_builder/                # Structured text → compliance rules
│   ├── llamaindex_rule_generator.py — the live LLM rule-extraction engine: a typed
│   │                                  LlamaIndex Pydantic program producing schema-validated
│   │                                  rule drafts. Wired in via app/services/rule_extraction_service.py.
│   ├── rule_generator.py          — validates and saves rule dicts
│   ├── rule_store.py              — adapter forwarding all reads/writes to RuleService
│   │                                (Supabase-backed `rules` table)
│   ├── code_seed_rules.py         — seeds baseline building-code rules from DB static assets
│   ├── code_extended_rules.py     — seeds extended building-code rules from DB static assets
│   ├── ids_exporter.py            — buildingSMART IDS 1.0 export/import via ifctester.ids
│   ├── aec3po_exporter.py         — AEC3PO export format support
│   ├── shacl_generator.py         — generates W3C SHACL shapes from DB-authored rules
│   ├── rule_converter.py          — legacy direct GPT-4o converter, kept only for its
│   │                                 existing LLM test coverage; not used by the live path
│   └── regex_rule_converter.py    — legacy free/offline regex converter, same status
├── ifc_reader/                  # IFC parsing, property resolution, quality gate
│   ├── ifc_parser.py               — raw IFC element reader
│   ├── ifc_geometry.py             — geometry-derived property extraction
│   ├── ifc_graph.py                — spatial/topological graph traversal (NetworkX)
│   ├── bot_graph.py / bot_graph_enrichment.py — BOT (Building Topology Ontology) RDF graph
│   │                                  construction and literal enrichment, consumed by
│   │                                  `ShaclComplianceEngine`
│   ├── ontology_namespaces.py      — RDF namespace constants for the BOT graph
│   ├── ifc_egress.py               — means-of-egress path analysis
│   ├── ifc_spatial.py              — daylight/spatial boundary checks
│   ├── ifc_stair.py                — stair geometry extraction
│   ├── ifc_supports.py             — support/bracing element extraction
│   ├── ifc_penetrations.py         — penetration/fire-separation extraction
│   ├── ifc_rooms.py                — room/space extraction and classification
│   └── ifc_quality/                — score labeling, GUID/property validation, and
│                                      auto-improvement of IFC files (used only by the
│                                      separately authorized enhancement pipeline, never
│                                      by the audit/analysis path)
├── comparator/                  # IFC element data vs. rule library
│   ├── engine_registry.py          — RuleEvaluator registry (ARCH-EGRESS-001, ARCH-SPATIAL-001, CODE-SHACL)
│   ├── ids_verification.py         — buildingSMART IDS-based verification path
│   ├── issue_adapter.py            — maps engine results onto the shared issue contract
│   └── issue_schema.py             — Issue data contract (comparator → reporter)
├── reporter/                     # Report generation
│   └── bcf_generator.py             — BCF 2.1 ZIP output
├── pipeline_io/                  # Upload, parsing, and export pipeline stages
│                                    — see docs/PIPELINE_IO_DATA_CONTRACTS.md for stage
│                                    boundaries
└── tests/
    ├── conftest.py
    ├── test_document_extractor.py
    ├── test_document_parsing.py
    ├── test_rule_builder.py
    └── test_iso19650_cde.py
```

`app/modules/reporter/` now holds only BCF export (`bcf_generator.py`); report
artifact persistence lives in `app/services/report_artifacts.py`, and
configuration-only PDF rendering lives in `app/services/pdf_report_service.py`.
The earlier Word/PDF compliance report, cost model, and schedule-impact
modules (`report_generator.py`, `cost_model.py`, `schedule_impact.py`) and
the `comparator/compliance_runner.py` / `compliance_orchestrator.py` engine
coordinators no longer exist on disk.

## Rule Extraction: LLM-Only

The live rule-extraction path is entirely LLM-based, with **zero hardcoded
building-code content**:

1. A document is ingested via `LlamaIndexIngestor`, which produces
   table/layout-aware, clause-scoped nodes (`DocumentNodeContract`) carrying
   clause ID, page number, and parent section metadata.
2. `SectionChunker` splits extracted text into clause-scoped sections.
3. `LlamaIndexRuleGenerator` (`rule_builder/llamaindex_rule_generator.py`) runs
   a typed LlamaIndex Pydantic program per node/section, producing zero or
   more schema-validated rule drafts — a malformed LLM response fails Pydantic
   validation rather than being silently coerced.
4. Drafts persist as `pending_review` rows (`rule_extraction_drafts` table)
   with an approve/reject/edit workflow before promotion into the canonical
   `public.rules` table (`RuleDraftService`).

This whole path is fronted by `app/services/rule_extraction_service.py`
(`RuleExtractionService`), which any caller (API route, agent tool) depends on
through the `RuleExtractionProvider` protocol — the extraction algorithm can be
swapped without touching callers.

`rule_converter.py` (direct GPT-4o) and `regex_rule_converter.py` (free/offline
regex) are earlier, superseded converters. They are not wired into the live
extraction path — they remain only because `tests/test_rule_builder.py` still
exercises them directly.

## Seeding Baseline Rules

Seeded rulesets (e.g. `BUILDING-CODE-PART9`, `BUILDING-CODE-PART9-EXT`) live as
JSON static assets in the database, loaded by `code_seed_rules.py` and
`code_extended_rules.py`:

```bash
uv run python -m app.services.ruleset_seeder
```

See `app/services/ruleset_seeder.py` for the full list of seeded rulesets.

## Rules Table (Supabase `public.rules`)

| Field | Type | Description |
|---|---|---|
| rule_id | UUID | Primary key |
| ruleset_id | TEXT | Groups rules into a selectable rule folder |
| category | TEXT | `Arch` (only value the DB check constraint allows) |
| target_ifc_class | TEXT | IFC class e.g. `IfcStairFlight` |
| property_name / property_set | TEXT | IFC property to read |
| operator | TEXT | `>=` / `<=` / `==` / `!=` / `between` / `exists` / … |
| value | JSONB | Threshold: number, string, or `[min, max]` |
| unit | TEXT | `mm` / `m` / `m2` / `deg` / `ratio` |
| priority | INT | 1 = critical, 0 = standard |
| description | TEXT | Plain-English explanation |

## Run Tests

```bash
uv run pytest app/modules/tests -v
```

## Next Steps

- **Module 2** (`ifc_reader/`) reads IFC files and extracts element properties.
- **Module 4** (`comparator/`) compares IFC properties against database rules
  and flags failures via the registered `RuleEvaluator`s.
- **Module 5** (`reporter/`) generates BCF / CSV / PDF compliance reports.
