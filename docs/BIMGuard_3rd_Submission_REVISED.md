MODULE 10 — FINAL MASTER'S PROJECT · 3rd PARTIAL SUBMISSION

# BIMGUARD AI
### An openBIM Compliance Platform: AI Rule Extraction, Generic Rule Comparison, and Corrosion Risk Validation
*Comprehensive Technical Draft (Near-Final Report) — Revised for factual accuracy against the current codebase*

**Group 5**
Letícia Cristovam Clemente · Malak Yaseen · Marc Azzam · Mark Shane Haines · Osama Ata

Master's in Artificial Intelligence for Architecture & Construction (MAICEN-1125)
ZIGURAT Institute of Technology · 2026

---

> **Editorial note on this revision.** This draft was produced by auditing the codebase file-by-file against every specific claim made in earlier versions of this report. Two corrections matter most. First, an earlier draft described "Module 4" as if it were a single corrosion-checking component; the codebase actually contains **two conceptually distinct engines** sharing that folder — a generic, source-independent **compliance comparator** (any extracted rule vs. any IFC/Revit property) and a specialist **corrosion risk-scoring engine** (weighted, standards-derived composite scores for galvanic/crevice/MIC mechanisms). This revision treats them as the separate concepts they are, each with its own methods subsection, results, and validation status. Second, historical run-history records now stored in `public.issue_history` show the project's headline corrosion figures (9 Critical / 7 High / 9 Medium, 25 open issues) are **genuine measured output from an earlier working version of the pipeline**, not invented numbers — though that version predates the current FastHTML architecture and its exact code path is no longer present in this repository, so the run cannot yet be reproduced on demand. Both corrections are explained in detail where they arise below, and every remaining gap is named explicitly rather than smoothed over, consistent with a 3rd partial submission being a near-complete draft, not a finished one.

---

## Table of Contents
1. Abstract
2. Introduction
3. 1.1 Research and Technology Review
4. 1.2 Methods and Tools
5. 1.3 Development Process
6. 1.4 Results and Discussion
7. 1.5 References and Appendices

---

## Abstract

BIMGuard AI is an openBIM automated compliance-checking platform that ingests vendor-neutral IFC models — from any authoring tool, Revit included — alongside regulatory PDF documents, and returns vendor-neutral BCF 2.1 issues. An optional live pyRevit integration additionally lets Revit users push element data directly, without an IFC export step, but this is a convenience layered on top of the IFC-first pipeline, not a dependency of it. It addresses two persistent gaps in AECO digital delivery — the *interpretation gap* (existing BIM tools cannot derive checks from unstructured regulatory text — building codes, BEPs — written as prose, not from software code) and the *corrosion-blindness gap* (no mainstream BIM coordination tool evaluates material compatibility or corrosion risk at design stage) — through **three distinct, purpose-built computational components**, not a single undifferentiated pipeline:

1. An **LLM-assisted rule-extraction service** (Docling document parsing, spaCy/TF-IDF candidate filtering, a semantic-annotation layer, and a provider-agnostic LLM converter built on `litellm`) that turns regulatory PDF text into structured, machine-readable rules.
2. A **generic compliance comparator** (`Module4_Comparator`) that evaluates *any* structured rule — however it was authored — against IFC or Revit element properties using ten comparison operators, and is source-independent: the same evaluator runs unchanged whether elements arrive via an uploaded IFC file or a live pyRevit push from inside Revit.
3. A **standards-based corrosion risk engine** that computes weighted composite risk scores (0–1 scale, four risk bands) for three electrochemical/biological degradation mechanisms — galvanic, crevice, and microbially-influenced corrosion (MIC) — each term traceable to a named engineering standard.

These three components are architecturally and conceptually separate because they solve different problems with different logic: component 2 is deterministic *threshold evaluation* against rules of arbitrary origin; component 3 is deterministic *multi-factor weighted scoring* against a fixed, standards-derived model that has no notion of a "rule" at all. Today, component 1 and component 2 are fully live in the web application; two of the three corrosion mechanisms (galvanic, crevice) are live via a dedicated compliance runner, while the third (MIC) is implemented and standards-referenced but not yet wired into the live pipeline. A persisted issue-history log shows the corrosion engine has previously produced a genuine, measured result of 25 open issues (9 Critical, 7 High, 9 Medium) — real output from an earlier version of the pipeline — but reproducing that run on today's codebase, and completing the rule-extraction accuracy evaluation (precision/recall/F1 and LLM-as-judge scoring), are the two work items scheduled ahead of final submission. This draft reports only what is genuinely implemented and evidenced today, and states what remains open rather than presenting it as already achieved.

**Keywords:** BIM compliance checking; openBIM; IFC; BCF 2.1; NLP rule extraction; rule-based compliance comparator; automated code compliance; galvanic corrosion; crevice corrosion; MIC; MEP coordination; responsible AI.

---

## Introduction

This document is the comprehensive technical draft (3rd partial submission) of the BIMGuard AI Final Master's Project. It consolidates the research context, methods, development history, results and references. The project targets the weekly BIM coordination cycle of large, MEP-intensive buildings, where "model-drop day" compliance is still verified by manual checklists against the BIM Execution Plan and technical codes. BIMGuard AI reframes that manual gatekeeping as an automated, traceable, tool-independent service.

A methodological point carried through the whole document: **rule extraction, rule comparison, and corrosion risk scoring are three separate concerns**, and conflating them (as an earlier draft did, by describing all of "Module 4" as "the corrosion engine") obscures what each component actually contributes. Rule extraction (§1.2.2) is about *authorship* — turning prose into structured rules. Rule comparison (§1.2.3) is about *evaluation* — checking any structured rule, from any source, against a model. Corrosion risk scoring (§1.2.4) is about *domain-specific engineering judgement* — a fixed, standards-derived scoring model that does not consume "rules" in the rule-extraction sense at all. Keeping these three separate in the write-up mirrors how they are separate in the code, and makes it possible to assess each on its own merits. The remainder follows the required structure: research and technology review (1.1), methods and tools (1.2), development process (1.3), results and discussion (1.4), and references and appendices (1.5).

---

## 1.1 Research and Technology Review

### 1.1.1 Context: the cost of fragmented compliance in AECO

The Architecture, Engineering, Construction and Operations (AECO) sector loses an estimated USD 15.8 billion annually in the U.S. capital-facilities segment to inadequate interoperability, driven by rework, manual data re-entry and fragmented information flows (Gallaher et al., 2004). A substantial share of this waste originates not in geometry but in compliance verification — the manual, error-prone reconciliation of a model against requirements held in building codes, standards and BIM Execution Plans (BEPs). As openBIM delivery matures under ISO 19650 (ISO, 2018) and the IFC schema (ISO 16739-1; buildingSMART, 2020), the industry has standardised how models are exchanged, but not how they are checked.

### 1.1.2 State of practice: model-coordination and clash-detection tools

Commercial coordination platforms — Autodesk Navisworks, Solibri Model Checker and BIMcollab — represent the current state of practice for automated model review. They are mature at hard-clash detection and support clearance-based soft clashes through manually configured tests. Two limitations recur in the literature and in practice. First, the rules these tools enforce must be authored by hand: they cannot ingest a code or BEP document and derive checks automatically — this is the limitation BIMGuard's rule-extraction service (§1.2.2) targets. Second, their checks are predominantly geometric; they do not reason over material, electrochemical or information-completeness properties — this is the limitation the corrosion risk engine (§1.2.4) targets. Notably, once a rule exists (by any authoring route), the *evaluation* of that rule against a model — Solibri's rule-checking core, for instance — is itself a well-understood, largely solved problem; BIMGuard's own generic comparator (§1.2.3) occupies this same solved space, deliberately kept simple and separate from the two harder, more novel problems either side of it. The buildingSMART BCF standard (buildingSMART, 2020) established a vendor-neutral issue-exchange format that this project adopts as its output, but the rule-authoring bottleneck and the corrosion-blindness gap remain unaddressed by commercial tooling.

### 1.1.3 Automated rule-based compliance checking (research lineage)

Automated code compliance checking (ACCC) has a two-decade research history. Eastman et al. (2009) formalised the four-stage ACCC pipeline — rule interpretation, building-model preparation, rule execution, reporting — and identified rule interpretation as the persistent bottleneck, while noting that rule *execution* (comparing a formalised rule to a model) is comparatively tractable once the rule exists in structured form. Early systems (Singapore's CORENET, the SMARTcodes initiative) relied on hard-coded or manually structured rules, costly to maintain and brittle across jurisdictions (Eastman et al., 2009; Dimyadi & Amor, 2013). Subsequent work explored semantic-web representations (SHACL/RDF) and, more recently, Natural Language Processing to automate the interpretation stage specifically: from rule-based/machine-learning extraction (Zhang & El-Gohary, 2017) to transformer- and LLM-based extraction that better handles the linguistic variability of regulatory text (Zheng et al., 2022; Fuchs et al., 2023). The consensus is that LLMs materially reduce interpretation effort but require human-in-the-loop verification before rules enter production, owing to hallucination and traceability risk — a finding this project's own architecture had to contend with directly (see §1.4.5).

### 1.1.4 Technologies and datasets leveraged

The project builds on an open-source stack, verified against `pyproject.toml` and the modules that actually import each library: **IfcOpenShell** — including its `geom` and `util.shape` native mesh engine — for IFC parsing, geometry derivation and spatial-adjacency analysis (used throughout `app/modules/module2_ifc_read/`, detailed in §1.2.5), supplemented by **shapely** for 2-D polygon analysis (room/corridor width) and **numpy** for the underlying array math (`trimesh` is not currently used but is recorded as a planned future geometry backend, §1.2.5, §1.4.5); **Docling** for PDF document-structure extraction (`docling_extractor.py`); **spaCy** for lemmatisation and sentence segmentation in the live extraction path; **litellm** as the provider-agnostic LLM transport for the production rule-extraction service (`app/services/llm_client.py`), supporting OpenAI, Gemini and Anthropic model strings; and **FastHTML/MonsterUI** with a **Supabase** (Postgres + object storage) backend. A `transformers`-based BERT/DistilBERT classifier is also implemented (`bert_classifier.py`) but is not yet part of the active dependency set or the production pipeline (§1.2.2). No ML/statistical model is used anywhere in the compliance-comparison or corrosion-scoring components — both are deterministic, rule-/formula-based systems by design (§1.2.3, §1.2.4).

Test data comprises openly available IFC reference models on disk in `data/uploads/ifc/`: the buildingSMART/IFC sample set, the Pacific Continental Residence model in both IFC4.3 Reference View and IFC2x3 Coordination View, `AC20-Institute`, and `Infra-Plumbing`, among others. The Ontario Building Code (CODE), Part 9 and selected Part 3 clauses, is the regulatory corpus for rule extraction, seeded as 45 machine-readable rules at application startup (§1.2.2). Corrosion knowledge is drawn from primary engineering standards rather than learned data: NASA-STD-6012 (galvanic voltage thresholds), EN ISO 15329 and ASTM G48 (crevice corrosion), CIBSE TM13/HSE HSG274/BS 8552 (microbially-influenced corrosion), and the IMOA PREN formulation for stainless-steel grade adequacy — plus, less commonly cited elsewhere in the literature, the AUCSC Basic Corrosion Course (2024) and American Galvanizers Association (2023) as sources for galvanic-series and coating-life data respectively (stored as DB-backed static assets in `public.static_data_assets`).

Notably, no corrosion-science or materials-science library is used anywhere in the codebase — a repo-wide check of every corrosion engine file's imports (`bimguard_corrosion_engine.py`, `bimguard_crevice_engine.py`, `bimguard_mic_engine.py`, `compliance_runner.py`, `galvanic.py`) shows only Python's standard library (`csv`, `dataclasses`, `datetime`, `enum`, `typing`, `uuid`, `zipfile`). The engineering knowledge itself — galvanic-series potentials, PREN formulas, CCT/environment-class thresholds, risk-band-to-BCF-action rules — is transcribed directly into versioned JSON specifications (now persisted as DB-backed static assets, each carrying a `ruleset_id` such as `"BIMGUARD-GC-001"` and a semantic `ruleset_version`) and Python constants, rather than computed by any external numerical or domain package. This makes the "white-box, standards-traceable" claim in the abstract literal at the implementation level: every scored term is a lookup or a documented formula over data, not logic hidden inside a black-box dependency. The one data-modelling library used is Python's own `enum`/`dataclasses` — `piping_schema.py`'s `EnvironmentClass`, `PipingSystem` and `JointType` are all string-backed enums (`class X(str, Enum)`), serialising as plain strings with no separate mapping layer, alongside a mix of frozen (`Point3D`, `BoundingBox`) and mutable (`PipingElement`) dataclasses and a small hand-written recursive JSON serialiser — no schema-validation library such as Pydantic is used.

### 1.1.5 The knowledge gaps this project addresses

Two gaps emerge, and BIMGuard AI addresses each with a purpose-fit pair or single component rather than one monolithic engine:

1. **The interpretation gap.** Existing BIM tools enforce only hand-authored, geometric rules and cannot derive checks from unstructured regulatory text — building codes and BEPs, written as prose for human readers, not as software code or a structured rule format. This is closed by *two* cooperating components: rule extraction (§1.2.2) turns text into structured rules, and the generic comparator (§1.2.3) evaluates those rules — or any manually authored rule of the same shape — against a model. Separating them means the extraction quality and the evaluation correctness can be assessed independently: a rule can fail because the LLM mis-read the code section, or because the comparator mis-applied a correct rule, and the architecture makes it possible to tell which.
2. **The corrosion-blindness gap.** Despite corrosion being a leading cause of premature MEP failure (corrosion costing ~3.4% of global GDP; Koch et al., 2016), no automated BIM coordination tool evaluates material compatibility, galvanic potential or crevice/MIC risk at the design stage, when mitigation is cheapest. This is closed by the corrosion risk engine (§1.2.4), a self-contained scoring system that does not route through the rule-extraction or generic-comparator components at all — it consumes element material/geometry/environment data directly and applies a fixed, published scoring formula.

---

## 1.2 Methods and Tools

### 1.2.1 System architecture: three components, two shared infrastructure modules

BIMGuard AI is implemented as a modular pipeline. The diagram below groups the codebase by what each part actually is, not by folder name — this matters because the real repository structure puts the generic comparator and the corrosion engine in the same `module4_comparator/` package even though they share no code and solve different problems.

```
┌─ COMPONENT 1: Rule extraction (turns text into structured rules) ─────────┐
│ Web app (LIVE):                                                            │
│   PDF upload → RuleExtractionService (M1 components + M1b annotator)       │
│              → LiteLLMRuleExtractor (litellm, provider-agnostic)           │
│              → RuleService.create_rule() → rules table (Supabase)           │
│ CLI prototype :                              │
│   PDF path  → orchestrator.run_pipeline()                                  │
│              → DoclingExtractor → TableRuleBuilder → SectionChunker        │
│              → KeywordFilter → RuleConverter / RegexRuleConverter          │
│              → RuleGenerator (validate/enrich) → RuleStore                 │
└──────────────────────────────────────────────────────────────────────────┘
                                    │  structured rules (any source)
                                    ▼
┌─ COMPONENT 2: Generic compliance comparator (evaluates rules vs a model) ──┐
│  IFC upload — any authoring tool: Revit, ArchiCAD, Tekla, Vectorworks, …   │
│              → Module 2 (ifc_parser.py, ifc_geometry.py, ifc_spatial.py) ─┐│
│                                            ├─→ extraction_results (list)  ││
│  pyRevit push (optional, Revit-only convenience, not the primary path) ──┘│
│              → RevitSyncService              (source-independent shape)   │
│                                            │                                │
│                                            ▼                                │
│                          Module4_Comparator.validate_metadata()            │
│                          (>=, <=, >, <, ==, !=, between, exists, …)         │
│                                            │                                │
│                                            ▼                                │
│         Module5_Reporter.render_visual_report(), grouped by discipline     │
│                    (Architecture / MEP — RuleService.list_by_theme)        │
└──────────────────────────────────────────────────────────────────────────┘

┌─ COMPONENT 3: Corrosion risk engine (weighted scoring, no "rules") ────────┐
│   IFC/element data → Module4_Comparator's sibling: compliance_runner.py    │
│                       (galvanic GC-001 + crevice CC-001, LIVE)             │
│                       — MIC MC-001 implemented separately in app/engines/, │
│                         standards-referenced, not yet wired in             │
│                                            │                                │
│                                            ▼                                │
│                       BCF issue + cost (£) + schedule (days) generation    │
└──────────────────────────────────────────────────────────────────────────┘
```

Three honest notes on this diagram. First, rule extraction (Component 1) exists as two parallel implementations, and only the `RuleExtractionService` path is reachable from the web UI — the CLI orchestrator (`app/modules/orchestrator.py::run_pipeline`) is complete and offline-capable but nothing in `app/routes/` calls it. Second, `orchestrator.py` also contains a class called `BIMGuard_App`, which *is* live and drives both Component 2 (generic comparator) and Component 3 (corrosion engine) from the same web request — this is why an earlier draft blurred the two together. This revision treats them separately from here on. Third, and worth stating plainly since it is easy to misread the pyRevit integration as central: BIMGuard's primary and only required input is a standard IFC file, exportable from any authoring tool that supports the schema — Revit, ArchiCAD, Tekla Structures, Vectorworks, Bentley, and others — which is what makes the platform openBIM and vendor-neutral in the first place. The pyRevit push described below is an additional, optional convenience for teams already working natively in Revit who want to skip the export step; it is not a dependency of the IFC-reading pipeline, and removing it entirely would not change how BIMGuard reads or checks an IFC file.

### 1.2.2 Component 1 — AI-assisted rule extraction (Modules 1, 1b, 3)

**Document structure extraction (M1).** `DoclingExtractor` genuinely parses source PDFs into prose text and per-table `DataFrame`s using Docling's `DocumentConverter`; used by both the live and CLI paths. `TableRuleBuilder` converts requirement tables directly into rules deterministically (no LLM call), also wired into both paths.

**Sectioning and filtering (M1).** `SectionChunker` segments a document into up to 13 fixed CODE sections via a regex-based heading detector. `KeywordFilter` performs spaCy lemmatisation and weighted keyword/bigram scoring, classifying paragraphs into HIGH/MEDIUM/LOW confidence bands. A `TfidfAnalyzer` (`sklearn.feature_extraction.text.TfidfVectorizer`) compares rule vs non-rule paragraph vocabularies — in the live service this runs in **discovery/reporting mode only** and does not change which paragraphs are routed to the LLM. A `confidence_scorer` combines keyword, dependency-parser and (optionally) BERT signals into a weighted SEND/SKIP decision, wired into the live service.

**Semantic annotation (M1b).** The `module1b_nlp_annotator` package is wired into the *live* web pipeline (not the CLI orchestrator). A `deontic_extractor` identifies obligation modality ("shall/must/should", with negation handling); a `dimension_extractor` captures quantities, units, and min/max/range/exact constraint types via regex; a `condition_parser` splits applicability/exception/qualification clauses; a `cross_ref_resolver` resolves seven families of inter-clause references. Together these build a structured "NLP pre-analysis" block prepended to the LLM prompt.

**Rule conversion — a dual-path design that exists, but in two different places.** A `USE_GPT4O` flag genuinely exists in the CLI path and switches between `RegexRuleConverter` (free, offline, deterministic) and `RuleConverter` (OpenAI SDK directly, default `gpt-4o-mini`). The live web service instead uses `LiteLLMRuleExtractor`, genuinely provider-agnostic — the UI lets a user select `openai`/`gemini`/`anthropic` model strings per request, defaulting to `gpt-4o-mini`. The regex-vs-LLM comparison central to the project's narrative is currently only demonstrable end-to-end through the CLI script; the live path has no regex-only fallback yet.

**Validation, enrichment and persistence.** `RuleGenerator` validates required fields per rule type and enriches target/property-set defaults before calling `RuleStore.save_rule`, but this gate is exercised only by the CLI path and the test suite — the live web save flow calls `RuleService.create_rule()` directly, bypassing `RuleGenerator`. The live rule schema (`rules_service.py`) has roughly 19 fields (including `property_set`, `value_min`/`value_max`, `applies_when`, `compliance_type`, `confidence`, `extraction_method`), materially larger than a minimal `{target_ifc_class, property_name, operator, check_value, unit, reference, severity, needs_review}` subset.

**Human-in-the-loop.** A `needs_review` field exists end-to-end: set by the LLM extractor, editable in the rule-review UI, shown as a warning badge before saving. What is not yet implemented is a "pending vs. active" rulebase gate — once a rule is saved, `needs_review=True` does not exclude it from the rule set the comparator (§1.2.3) checks against.

**Seed rules.** `code_seed_rules.py` contains 31 pre-built CODE Part 9 rules, and `code_extended_rules.py` adds 14 more CODE Part 9/Part 3 rules, both seeded automatically at application startup — **45 pre-built rules** in total, each with a real CODE section reference. These seed rules are consumed identically by the generic comparator in §1.2.3, regardless of whether they were seeded, LLM-extracted, or regex-extracted — a direct benefit of keeping extraction and evaluation separate.

### 1.2.3 Component 2 — the generic compliance comparator (Module 4: `Module4_Comparator`)

This component answers one question only: *given a structured rule and a set of model elements, does each element pass?* It has no knowledge of where the rule came from (LLM, regex, seed file, or a person typing it into the Rule Library UI) and no domain-specific corrosion logic — it is a general-purpose evaluator, and this generality is its main design value.

**Supported operators.** `>=`, `<=`, `>`, `<`, `==`, `!=`, `between`, `exists`, `not_exists`, `matches` (regex). Numeric comparisons coerce the property's actual value to `float` (stripping thousands separators); non-numeric values fall back to string equality/inequality or regex matching for `matches`.

**Per-rule result status.** Each rule, evaluated against every matching element, resolves to one of five statuses: `PASS` (all elements satisfy the rule), `FAIL` (at least one element violates it — the dominant status), `MISSING_DATA` (the property is absent on every matching element), `PARTIAL` (present-but-failing plus some missing), or `NO_ELEMENTS` (no elements of the target IFC class exist in the model). Each `FAIL`/`PARTIAL` result carries a per-element failure list (element name, GUID, storey, space, actual value, and a human-readable reason string, e.g. `"820mm < required 860mm"`).

**Property resolution (feeding the comparator from Module 2).** For each rule, `Module2_IFCRead.extract_for_compliance()` searches, in order: (1) the rule's nominated property set, (2) all Psets and `Qto_` quantity sets on the element, (3) direct IFC schema attributes (e.g. `OverallHeight`, `OverallWidth`). This fallback order is what lets a single CODE rule match property data authored inconsistently across different IFC exporters.

**Source-independence — a genuine, distinctive architectural feature, with IFC as the primary and only required path.** The comparator's default and primary input is a standard, vendor-neutral IFC file — from Revit, ArchiCAD, Tekla, Vectorworks, or any other IFC-exporting tool — parsed by Module 2 (§1.2.5). A second, optional input path exists for teams already working natively in Revit; the comparator is invoked from two different live routes, on two structurally different inputs, without any change to `Module4_Comparator` itself:
- `app/routes/analyze.py` → `Module2_IFCRead.extract_for_compliance(library_rules)` (from an uploaded IFC file — the primary, tool-agnostic path) → `Module4_Comparator().validate_metadata(extraction)`.
- `app/routes/revit_sync.py` → an *optional* pyRevit script running inside Revit POSTs live element JSON (`{"ifc_class": "IfcStairFlight", "properties": {"Width": 900.0, "RiserHeight": 175.0}, ...}`) to `/revit-sync` → `RevitSyncService.build_extraction_results()` reshapes it into the *same* `list[dict]` contract `extract_for_compliance()` produces → `Module4_Comparator().validate_metadata(...)` runs unchanged. `RevitSyncService`'s own docstring states the intent directly: *"Converts pyRevit push data into Module 4's expected input format so the compliance pipeline runs unchanged regardless of whether data came from an IFC file... or directly from Revit."*

`Module4_Comparator` itself has no notion of "Revit" anywhere in its code — it only ever consumes the same generic `list[dict]` shape, however it was produced. This is what makes the IFC path and the Revit convenience path equally valid, rather than the platform being a Revit-first tool with an IFC side door.

**Measures covered today.** Across the 45 seed rules (§1.2.2), the comparator already checks five categories of regulatory measure: *dimensional* (Width, OverallWidth/Height, RiserHeight, TreadLength, FlightHeight, HandrailHeight, RequiredHeadroom, Area/NetFloorArea), *angular* (PitchAngle, WinderTurnAngle, IndividualWinderAngle), *fire/life-safety* (FireRating, present on three explicit rules covering doors, walls and slabs), *slope* (RequiredSlope), and *boolean/classification* (IsExternal, HasNonSkidSurface, PredefinedType, OperationType). One notable gap: wall/slab **thickness** is not yet an explicit checked rule, even though the `ifc_quality` improver already carries a default `Thickness: 0.15` m for `IfcWall` (§1.2.5) — extending the seed set to check thickness against fire-compartmentation or structural minimums is a natural, low-effort addition (§1.4.5).

**Discipline-based result sorting (Architecture / MEP) — real and live.** `RuleService` defines `THEMES = {"Architecture", "MEP"}` and an `infer_theme()` classifier: a rule is tagged MEP if its `mechanism` is one of the corrosion codes (`GC-001`/`CC-001`/`MC-001`) or its target IFC class starts with an MEP prefix (`IfcFlow*`, `IfcPipe*`, `IfcDuct*`, `IfcCable*`, `IfcDistribution*`); everything else defaults to Architecture. `list_by_theme()` filters the active rule set before a compliance run, and both `analyze.py` and `revit_sync.py` accept a `theme` parameter, so a run's results are already scoped to one discipline by construction. Not yet built: a single combined report view that runs both themes together and groups the results side by side — today a user selects one discipline per run rather than seeing an Architecture/MEP-sorted breakdown of one combined run. This is scoped as a near-term UI improvement (§1.4.5); the classification logic behind it already exists and does not need to be rebuilt.

**Rule and modelling-guidance hyperlinks — planned, not yet built.** Today, a rule's source citation (`ref`, e.g. `"9.8.2.1.(2)"`) is a plain text string, not a link — confirmed against the rule schema and the Rule Library UI. The planned feature adds two hyperlinks per checked rule in the results view: (1) a citation link back to the specific source clause (the regulatory PDF section, or an official code portal where licensing permits), extending the same traceability the `needs_review` workflow already gives at the extraction stage through to the results the user actually reads; and (2) a modelling-guidance link, combining buildingSMART's own official IFC/MVD authoring documentation with BIMGuard's own written guidance, explaining how to model the relevant element correctly (e.g., which property set a stair flight's `RiserHeight` should be authored under) so that a `MISSING_DATA` result becomes actionable rather than opaque. This directly targets the false-negative risk described in §1.2.5 — many `MISSING_DATA`/`NO_ELEMENTS` results are a modelling-quality problem rather than a genuine compliance failure, and the UI does not currently help a user tell the difference or fix it.

**Extending human-in-the-loop from rules to results — planned.** `needs_review` (§1.2.2) currently covers only extracted *rules*, before they are saved. The planned extension applies the same review discipline to *results*: a reviewer would be able to mark an individual comparator or corrosion-engine issue as reviewed/accepted/dismissed, with a comment, before it is included in a finalised report or BCF export — mirroring the rule-review workflow at the results end of the pipeline. No such field or workflow currently exists on `Module4_Comparator`'s result objects or the corrosion engine's issue objects (§1.2.4); this is a design gap listed in §1.4.5, not a partially-built feature.

**Worked example.** CODE seed rule (`code_seed_rules.py`): *"Private stair riser height — min 125 mm, max 200 mm"*, `target_ifc_class="IfcStairFlight"`, `property_name="RiserHeight"`, `operator="between"`, `value_min=125`, `value_max=200`. Given an uploaded model containing a stair flight with `RiserHeight=175mm`, the comparator resolves `actual=175`, evaluates `125 <= 175 <= 200` → `True`, and the rule status is `PASS` for that element. A second stair flight with `RiserHeight=210mm` would fail with reason `"210mm outside [125mm–200mm]"`, contributing to a `FAIL` status for the rule and a `Module5_Reporter` entry citing the specific element GUID and storey.

**Current validation status.** No dedicated unit tests currently assert `Module4_Comparator`'s operator logic against hand-picked cases in isolation (the closest existing test, `test_compliance.py`, targets a `/api/v1/compliance/...` REST shape that does not exist in the current FastHTML app and predates this architecture). This is flagged as a concrete, low-effort item for §1.4.5 — the class itself is short and pure-functional, so covering all ten operators with unit tests is a same-day task.

### 1.2.4 Component 3 — standards-based corrosion risk engines (galvanic, crevice, MIC)

This component answers a structurally different question: *given an element's material, its neighbours' materials, its geometry, and its service environment, what is the deterministic, standards-derived risk that it will corrode?* There is no "rule" being checked here in the Component-2 sense — the scoring model, its weights, and its risk bands are fixed by engineering standards, not authored per-project.

Three engines are designed and implemented, each computing a weighted composite score on a 0–1 scale mapped to four risk bands. Every term is traceable to a published standard; there is no trained model and no hidden weighting.

| Engine | Composite score | Risk bands | Key standards | Status |
|---|---|---|---|---|
| Galvanic (GC-001) | 0.50·voltage + 0.30·area-ratio + 0.20·environment | Low <0.35 / Med / High / Crit >0.85 | NASA-STD-6012; WorldStainless galvanic series; IMOA PREN; Prosoco TN-104 | **Live** (production tables) + fuller reference implementation |
| Crevice (CC-001) | 0.35·geometry + 0.40·CCT-adequacy + 0.25·environment | Low <0.30 / Med / High / Crit >0.80 | EN ISO 15329; ASTM G48 Method B; CIRIA C692; CIBSE Guide G; EN 1993-1-4 | **Live** (production tables) + fuller reference implementation |
| MIC (MC-001) | 0.35·flow + 0.30·temperature + 0.25·dead-leg + 0.10·material | Low <0.25 / Med / High / Crit >0.75 | CIBSE TM13; HSE HSG274; BS 8552; ASTM G-187; WHO DWQ | Implemented, **not yet integrated** into the live pipeline |

*Table 1. The three corrosion engines: composite scoring formulas, risk bands and referenced standards, as implemented in `app/engines/`.*

**Two implementations exist for galvanic and crevice.** A fuller, standards-annotated *reference implementation* of all three mechanisms lives in `app/engines/` (`bimguard_corrosion_engine.py`, `bimguard_crevice_engine.py`, `bimguard_mic_engine.py`) with matching documentation payloads now persisted as static assets in `public.static_data_assets`. This is where the formulas in Table 1 are drawn from, including the galvanic voltage-risk normalisation `voltage_risk = min(1.0, gap / (2 × threshold))` and the PREN-failure floor of 0.35. **This reference implementation is not currently imported by any live route** — reachable only by running its files directly, and a broken relative import between the crevice and galvanic reference files means even its own cross-engine logic degrades silently outside `app/engines/`.

Each ruleset JSON is a versioned specification, not just a data dump: `galvanic_corrosion_ruleset.json` carries a `ruleset_id` (`"BIMGUARD-GC-001"`), a semantic `ruleset_version` (`"1.0.0"`), a `standards_referenced` list of eight named, described sources, the composite formula written both as a human-readable string and a machine-readable `weights` dict, and — the most operationally significant part — an explicit mapping from each risk band to a BCF action: Low → *"Asset register only — no BCF issue"*, Medium → *"BCF Normal priority"*, High → *"BCF Major priority"*, Critical → *"BCF Critical priority — immediate remediation"*. This is the exact, auditable rule connecting a numeric composite score to an output decision, and it is documented as data rather than buried in conditional code.

The engine actually invoked when a user runs a compliance check in the web app is `app/modules/module4_comparator/compliance_runner.py` (a sibling file to, but sharing no logic with, `Module4_Comparator`), called from `BIMGuard_App.orchestrate_workflow()`. It independently implements galvanic and crevice scoring against its own, hand-authored material/PREN/CCT tables — numerically close to, but not identical to, the reference implementation's tables — and **does not implement MIC**.

A fourth implementation, `module4_comparator/galvanic.py`, is more substantial than a simple superseded stub and deserves its own mention: it is a complete, correct galvanic comparator built against `app/modules/module2_ifc_read/piping_schema.py`, a genuinely rich `PipingElement` data contract — 22 canonical materials, a 23-member `PipingSystem` enum (covering everything from domestic hot water to medical gases and pool circulation), a `T0`–`T5` `EnvironmentClass` wetting scale, a 14-member `JointType` enum matching a dedicated `JT-001`–`JT-014` ruleset, and explicit mass/area fields for both galvanic and seismic checks. This is the most rigorously modelled data contract in the codebase. Implementation-wise, `EnvironmentClass`, `PipingSystem` and `JointType` are all string-backed Python enums (`class X(str, Enum)`) — type-checked in code but serialising as plain strings with no separate translation layer — alongside a deliberate split between frozen, immutable dataclasses for geometric primitives (`Point3D`, `BoundingBox`) and a mutable dataclass for the element record itself (`PipingElement`), with a small hand-written recursive `to_json()` walker rather than a schema library such as Pydantic. It is, however, entirely disconnected from the live pipeline in both directions: nothing in `ifc_parser.py` constructs a `PipingElement` from real IfcOpenShell data (only three hand-written example fixtures exist, inside `piping_schema.py` itself), and `galvanic.py` is never imported by `compliance_runner.py` or any route. Closing this gap — having `ifc_parser.py` populate real `PipingElement` objects and routing them through `galvanic.py` — would be a more standards-faithful path to a unified corrosion engine than continuing to maintain `compliance_runner.py`'s separate hand-authored tables (§1.4.5).

**Worked logic (galvanic, reference implementation).** For a dissimilar-metal pair, the engine looks up each metal's potential in a galvanic series (V vs. Ag/AgCl), computes the voltage gap, and normalises it against an environment-class threshold (controlled 0.50 V → normal 0.25 V → harsh 0.15 V): `voltage_risk = min(1.0, gap / (2 × threshold))`. A small anode-to-cathode area ratio escalates risk (Prosoco TN-104), and a PREN adequacy failure for the specified stainless grade floors the composite score at 0.35 (Medium).

**Current validation status.** No unit tests currently assert engine output against hand-calculated ground truth for known material pairs — this is the methodology the assignment expects (§1.2.8) but it is not yet coded. What does exist is a persisted historical run (§1.4.2) showing the engine has previously executed and produced measured, non-trivial results — real evidence the design works, even without a repeatable test suite behind it yet.

### 1.2.5 Shared infrastructure — IFC ingestion, geometry and spatial analysis (Module 2)

This module is fully implemented and live, and feeds both Component 2 and Component 3. It has also grown well beyond a simple property reader, and is described here in more depth than earlier drafts gave it.

**Core parsing.** `ifc_parser.py` (built on a genuine `ifcopenshell.open()` call) extracts service elements, materials, property sets and spatial structure into a `ServiceElement` schema. The `ifc_quality` sub-package (`validator.py`, `improver.py`, `generator.py`) checks and repairs missing/under-specified attributes before checking, and `validator.py` produces a genuine 0–100% completeness score. The parser explicitly branches on IFC schema version and flags IFC4-only MEP classes unavailable when reading an IFC2x3 file — dual-schema support is a real, handled code path.

**Geometry stack — corrected from an earlier draft.** BIMGuard does not use `trimesh` today; the real, verified stack (`ifc_geometry.py`, `ifc_spatial.py`) is `ifcopenshell.geom` and `ifcopenshell.util.shape` — IfcOpenShell's own native mesh-processing engine (v0.8+) — for 3-D mesh operations, `shapely` for 2-D polygon analysis (room/corridor minimum-width via minimum-rotated-rectangle), and `numpy` for the underlying array math. Adding `trimesh` as a further geometry backend — for boolean mesh operations or watertightness checks the current stack does not cover, relevant to the planned "Halo" volumetric-clearance feature (§1.4.5) — is recorded here as a named future addition, not a currently-used library.

**Tier 1 — architectural geometry derivation (`ifc_geometry.py`).** This module has two responsibilities, per its own header docstring: (1) pipe surface-area estimation for the galvanic corrosion engine (Component 3), reading actual mesh geometry where available and falling back to nominal-diameter estimation otherwise; and (2) deriving architectural measurements — `Height`, `Width`, `SillHeight`, `HandrailHeight`, `Slope`, `Volume`, `FootprintArea`, `SurfaceArea`, and `CorridorWidth` — directly from element geometry *when those values are absent from property sets*. In practice this means a rule such as the riser-height check (§1.2.3) can still be evaluated even when an IFC export omits the `RiserHeight` property outright, because the geometry engine derives it from the stair flight's mesh instead of requiring it to be authored. This is a genuine, non-trivial fallback layer, not simple bounding-box math.

**Tier 2 — spatial adjacency engine (`ifc_spatial.py`).** A second, structurally different capability: this module parses `IfcRelSpaceBoundary` relationships to map every `IfcSpace` to the walls, doors and windows that bound it, and identifies party walls shared between two spaces. Three compliance checks are built on top of this adjacency map, and are genuinely wired into the live pipeline (`module2_ifc_read/__init__.py` imports and calls all three): `check_daylight_ratios()` (CODE 9.7.2 — window area ÷ floor area ≥ 1/10), `check_fire_separation()` (CODE 9.10.9 — party walls must carry `FireRating` ≥ 45 minutes), and `check_garage_separation()`. These are relationship-aware checks that Component 2's simple operator-based comparator (§1.2.3) cannot express on its own, since they depend on which elements bound which spaces, not just a single element's own properties — a good illustration of why Module 2 has grown beyond being "just" an IFC reader.

**Tier 3 — egress and circulation analysis (`ifc_egress.py`) — real, live, and graph-based.** This is the most algorithmically sophisticated part of Module 2 and was absent from earlier drafts of this report. It builds a `networkx` graph of the building's circulation topology: nodes are `IfcSpace` GUIDs weighted by the square root of floor area (an estimated per-space traversal cost), edges connect spaces that share a physical `IfcDoor` boundary, and spaces touching an exterior door are marked as exits. Two CODE checks run on top of this graph: `check_exit_count()` (CODE 9.9.4.1 — at least one exit per storey, checked directly from `IsExternal` doors without needing the graph) and `check_egress_travel_distance()` (CODE 9.9.10.1 — runs Dijkstra's shortest-path algorithm from every habitable space to its nearest exit, flagging any path over 25 m). Habitable-space classification uses a keyword list (bedroom/living-room-type names count, bathroom/corridor-type names don't, ambiguous names default to habitable). This is genuinely wired into the live pipeline — `module2_ifc_read/__init__.py` builds the egress graph on IFC load and exposes `extract_egress_checks()`, which `app/routes/analyze.py` calls and renders on the results page. Unlike Component 2's per-element rule checks (§1.2.3) or even Tier 2's pairwise adjacency checks, this is a genuinely global, path-based analysis — no other part of the platform reasons about the building as a connected graph the way this module does.

**A related, complete capability that exists but is currently switched off: the IFC relationship graph (`ifc_graph.py`).** Separately from egress, `ifc_graph.py` builds a full `networkx` directed graph of the model's containment, aggregation and connectivity relationships (`IfcRelContainedInSpatialStructure`, `IfcRelAggregates`, `IfcRelConnectsElements`) and renders it as an interactive `pyvis` HTML visualisation, with violated elements highlighted in red. The code is complete and correct, but `app/routes/analyze.py` currently renders a hardcoded placeholder card ("Graph visualisation is temporarily disabled") in its place, behind an explicit `# TODO: Re-enable the PyVis IFC graph` comment — `ifc_graph.py` itself is never imported. Re-enabling it is a low-effort, high-visual-value improvement (§1.4.5), since the underlying graph-building logic already works.

**Architectural element detection — a known limitation, under active development.** Both tiers above assume an element is already correctly classified in the source IFC (a real `IfcDoor`, a real `IfcStairFlight`, and so on) and, at most, is missing a *property*. The `ifc_quality` improver already handles that specific case well: it carries default-property tables for `IfcWall` (including `Thickness: 0.15` m), `IfcDoor` (`FireRating`, `SmokeStop`, `IsExternal`, `Acoustic`), `IfcWindow` (`FireRating`, `IsExternal`, `Acoustic`, `ThermalTransmittance`), `IfcSpace`, and `IfcSlab`, injecting sensible defaults when a recognised element is missing a property. What is **not** yet handled, and is a genuine, currently unmitigated source of false negatives, is an element that is missing or *mis-classified* altogether — for example, a door modelled as an undifferentiated `IfcBuildingElementProxy` or a generic opening rather than a proper `IfcDoor`, a common real-world authoring error, especially from tools with weaker IFC mapping. In that case, Component 2 does not fail the rule — it reports `NO_ELEMENTS` (§1.2.3), silently under-counting rather than flagging a problem. Improving architectural-element detection — heuristics or geometry-based reclassification to catch elements that behave like a door/window/stair but are not tagged as one — to close this false-negative path is scoped as priority work ahead of final submission (§1.4.5).

### 1.2.6 Shared infrastructure — reporting: BCF, cost and schedule (Module 5)

Module 5 provides two distinct outputs, consumed differently by Components 2 and 3. `Module5_Reporter.render_visual_report()` renders an on-screen HTML summary of comparator results (§1.2.3) — pass/fail counts, per-rule failure detail — and is genuinely called from both `analyze.py` and `revit_sync.py`. For BCF export, `bcf_generator.py` implements a well-formed BCF 2.1 ZIP writer (GlobalId, viewpoint, risk score, mitigation text per issue; `snapshot.png` is currently a hardcoded 1×1 placeholder pixel, a known limitation). A second BCF writer, `app/services/bcf_exporter.py`, is **broken, not just unused**: it imports `ComplianceIssue` from `app.models.compliance_models`, a module that does not exist anywhere in the repository, so this file would raise `ModuleNotFoundError` if anything tried to call it — which nothing does (zero callers found anywhere). **Neither writer is currently invoked by the live download route**: `app/routes/analyze.py`'s `/reports/bcf/{project_id}` endpoint only reads a pre-existing file named `data/compliance_project_{id}.bcf` from disk if one happens to exist — it does not generate one. The two such files that do exist (`compliance_project_1.bcf`, `compliance_project_3.bcf`, both genuine, well-formed, non-empty BCF archives) were produced by an earlier version of the pipeline whose write step is not present in the current codebase (§1.4.2). `cost_model.py` implements a configurable `CostModel` with CSV-upload support, shipping with UK MEP default rates hardcoded in Python rather than a checked-in CSV. `schedule_impact.py` computes cost (£) and programme-delay (days) per issue, keyed by risk band × mechanism, against a 10-activity baseline MEP programme (a modelling assumption, not measured project data).

### 1.2.7 Software and environment

Python 3.12, managed with `uv`. Application: FastHTML + MonsterUI (server-rendered UI + HTMX), with a full supporting application shell beyond the three compliance components — project management (`projects.py`/`projects_service.py`: create/edit/delete, MD5-hashed IFC upload) and document management (`library.py`/`documents_service.py`: MD5-based upload de-duplication, no versioning) — both genuinely wired and functional. Data: Supabase (Postgres + object storage) is the backend for both data and file storage, with a transparent local cache for remote Supabase Storage objects (`data/cache/supabase-storage/`, `object_storage.py`) so files can be parsed/served locally without re-downloading on every request. Production hosting is Render.com (`render.yaml`: single Docker web service, starter plan, autoDeploy from the repository) — there is no separate managed database container in either deployment config, since Supabase is an external hosted dependency. AI/ML: Docling, spaCy, scikit-learn (TF-IDF), `litellm`; a `transformers`-based BERT classifier is implemented but not active in production. Note on default LLM model: `docker-compose.yml`/`render.yaml` set `BIM_GUARD_RULE_MODEL=gemini/gemini-2.0-flash` for the deployed environment, distinct from `config.py`'s `gpt-4o-mini` default used by the CLI path (§1.2.2) — the two rule-extraction implementations do not currently share a default model, a further argument for reconciling them (§1.4.5). BIM: IfcOpenShell. Testing: a real pytest suite exists (`app/modules/tests/`, 57 test functions across `test_module1.py`, `test_module3.py`, `test_compliance.py`, `test_integration.py`) with genuine `@pytest.mark.slow`/`llm`/`integration` markers (not yet registered in `pyproject.toml`); one file (`test_compliance.py`) targets a REST API shape that predates the current FastHTML architecture and needs rewriting. A custom LLM-as-judge evaluation harness (`eval_harness.py`) also exists (§1.2.8). Containerisation: a working multi-stage `Dockerfile` exists at the repo root, orchestrated locally by `docker-compose.yml`. **Continuous integration is not yet implemented** — no `.github/workflows/` directory exists, so the test suite runs manually only. An in-browser IFC 3D viewer (`app/routes/viewer.py`, `static/js/ifc-viewer.js`) supports visual issue inspection — corrected from an earlier draft, which repeated an inaccurate claim from `CLAUDE.md` that it uses `@thatopen/fragments`/`@thatopen/components`; the real, verified stack is **three.js r160 + `web-ifc-three@0.0.126` + `web-ifc@0.0.68`**, loaded from CDN, with orbit controls and automatic camera-fit to the loaded model.

### 1.2.8 Data analysis and validation metrics, per component

**Component 1 (rule extraction).** `eval_harness.py` implements a golden set of 8 hand-authored `EVAL_CASES` and a genuine LLM-as-judge harness scoring each generated rule 1–5 on Correctness, Completeness and Executability. **Precision/recall/F1 per rule field is not yet implemented** — the methodology (confusion matrix over element/property/operator/value/unit) is specified but not coded, and a call to a `RuleGenerator.generate_rules()` method that does not exist on the current class would raise an `AttributeError` if the harness were run as-is. Both must be fixed before a live evaluation run (§1.4.3).

**Component 2 (generic comparator).** Intended validation regime: unit tests exercising all ten operators against synthetic element/rule pairs, plus integration coverage confirming identical output whether elements arrive via `Module2_IFCRead` or `RevitSyncService`. Neither currently exists as passing, up-to-date test coverage (§1.2.3).

**Component 3 (corrosion engines).** Intended validation regime: agreement with hand-calculated ground truth for known material pairs, environments and geometries (unit tests), plus expert review of aggregate risk-band distribution on a benchmark element set. Hand-calculated unit tests do not yet exist. A real, measured historical run does exist, evidenced by a persisted issue-history log (§1.4.2) — genuine output, but not yet reproducible from the current codebase on demand, and not backed by a repeatable automated test.

---

## 1.3 Development Process

### 1.3.1 Model iterations and experimental evolution

- **Iteration 0, Streamlit prototype.** The team's first working end-to-end system was a Streamlit application. It is not present in this repository's git history, but its influence is: the corrosion module's own `issue_tracker.py` file still carries a `"Usage in Streamlit: from modules.issue_tracker import IssueTracker"` docstring and an embedded Streamlit integration snippet, and it produced historical run-history data now represented in `public.issue_history` (see §1.4.2).
- **Iteration 1, Mock-first pipeline.** The rule-extraction path was first built with `module3_rule_builder_mock.py` and the CODE seed rules, letting Components 2 and 3 be developed end-to-end before the NLP layer was reliable. This mock module is now orphaned dead code.
- **Iteration 2, Regex baseline; Iteration 3, LLM converter.** As described in §1.2.2 — a free offline regex baseline, then an OpenAI-SDK-based GPT converter behind a `USE_GPT4O` flag (CLI path), later superseded in the live web app by a separate, `litellm`-based, genuinely provider-agnostic converter. The two have not yet been reconciled (§1.4.5).
- **Iteration 4, NLP enrichment.** Module 1 grew from keyword filtering to a layered approach, and a Module 1b semantic-annotation layer was added and wired into the live extraction service.
- **Iteration 5, splitting the comparator from the corrosion engine.** Originally, a single galvanic-only file (`module4_comparator/galvanic.py`) handled both roles implicitly. As crevice and MIC logic were added, the team recognised these needed a fundamentally different evaluation model (weighted composite scoring against fixed standards) from ordinary rule checking (threshold evaluation against extracted rules) — leading to `Module4_Comparator` being generalised into the operator-based evaluator described in §1.2.3, while corrosion-specific logic moved into its own `compliance_runner.py`. A fuller three-mechanism reference implementation was developed separately in `app/engines/`, but has not yet been re-integrated as the pipeline's single source of truth for corrosion (§1.4.5).
- **Iteration 6, source-independence.** `RevitSyncService` was added specifically so `Module4_Comparator` could serve a live pyRevit integration without any change to the comparator itself — the clearest evidence in the codebase that the team was deliberately designing Component 2 as a generic, reusable evaluator rather than an IFC-only or corrosion-only tool.
- **Iteration 7, reporting & commercial impact.** The reporter matured to include a configurable `cost_model` and `schedule_impact`, connecting each corrosion issue to a £ cost and programme-delay figure.
- **Iteration 8, geometry-derivation and spatial-adjacency tiers.** As real IFC exports proved inconsistent about which properties were authored, `ifc_geometry.py` was extended to derive architectural dimensions (height, width, sill height, slope, corridor width, and others) directly from mesh geometry when a property was absent, and `ifc_spatial.py` was added as a separate spatial-adjacency layer (`IfcRelSpaceBoundary` parsing) to support relationship-aware checks — daylight ratio, fire separation, garage separation — that a single-element operator rule cannot express (§1.2.5).
- **Iteration 9, discipline-based rule sorting.** As the rule library grew to include both CODE dimensional rules and corrosion mechanisms, `RuleService` gained a `THEMES`/`infer_theme()` classifier so a compliance run can be scoped to Architecture or MEP rules specifically, rather than always evaluating the full combined rule set (§1.2.3).
- **Iteration 10, egress and graph analysis.** `ifc_egress.py` and `ifc_graph.py` were added to reason about the model as a connected graph rather than a flat element list — the former (live) for exit-count and travel-distance life-safety checks, the latter (currently disabled in the UI) for general relationship visualisation (§1.2.5).
- **A note on internal documentation drift.** A dated internal planning document, `docs/enhancements-plan-20260407.md`, records Modules 3, 4 and 5 as returning placeholders as of 2026-04-07; as of this submission, all three have substantial real implementations (§1.2.2–§1.2.4). This is left in the repository as an accurate record of the project's state at that date, and is cited here only to show how much of the current implementation work happened after it was written — it should not be read as a current architecture reference, and neither should `docs/INTEGRATION_GUIDE.md`, which is self-labelled as describing the pre-migration Streamlit architecture.

### 1.3.2 Technical challenges and mitigation strategies

- **Messy, incomplete IFC models.** Mitigation: the `ifc_quality` sub-package detects and, where safe, repairs or flags missing attributes before checking (Component 2's input quality).
- **Architectural elements missing or mis-classified in the source model.** Beyond missing properties (handled by `ifc_quality`), some real IFC exports omit or mis-tag entire elements — a door authored as a generic proxy rather than `IfcDoor`, for instance — which silently produces a `NO_ELEMENTS` result rather than a flagged failure. Mitigation: not yet implemented; this is an open, acknowledged risk (§1.2.5) rather than a solved one, and is prioritised in §1.4.5 because it directly undermines the white-box/auditability claim if a real non-compliance goes unflagged simply because an element was tagged incorrectly upstream.
- **Distinguishing "checking a rule" from "scoring a corrosion risk."** Not an anticipated challenge — it emerged during development, when corrosion logic outgrew what a simple operator-based rule (`>=`, `between`, etc.) could express (a composite of four weighted, standards-derived sub-scores has no natural representation as a single threshold rule). Mitigation: accept them as two separate computational models, described separately here rather than forced into one abstraction.
- **LLM hallucination and traceability.** Mitigation in place: every extracted rule carries a `needs_review` flag and a source-clause reference, shown to a human reviewer before saving. **Not yet in place:** the flag does not currently prevent a saved-but-unreviewed rule from being evaluated by Component 2 — an open gap, prioritised in §1.4.5.
- **LLM cost and reproducibility.** Mitigation: a regex converter provides a zero-cost, fully reproducible default in the CLI path; the live path currently always calls an LLM, so this trade-off is designed but not fully realised end-to-end in production yet.
- **Cross-jurisdiction variability.** Mitigation: rulesets are stored as named static assets in `public.static_data_assets`, so jurisdictions can in principle be added without touching engine logic — though today these assets are consumed mainly for documentation/Rule Library display, not as the live parametrisation of the corrosion engine (§1.2.4), so this mitigation is partially realised.
- **Corrosion knowledge without training data.** Mitigation: the engines are deterministic and standards-derived, sidestepping the need for training data while remaining fully auditable.
- **Legacy data artifacts from the Streamlit-to-FastHTML migration.** The corrosion issue-history log and the two on-disk BCF files are real but were generated by code no longer present in this repository. Mitigation in progress: treat them as historical validation evidence (§1.4.2), and re-wire `IssueTracker.record_run()` (currently defined but never called by the live app) into `compliance_runner.py` so future runs persist their own history going forward.
- **Distributed team, many time zones.** Mitigation: a GitHub-centred workflow (issue templates, agent instruction files, Docker for reproducibility) and modular ownership per member.

### 1.3.3 Key design decisions

1. openBIM (IFC-in / BCF-out) over a proprietary plugin, for tool-independence and vendor-neutrality — extended by a live pyRevit push path (§1.2.3) that adds convenience without weakening the IFC-first, vendor-neutral default.
2. **Keep rule extraction, rule comparison, and corrosion scoring as three separate components**, not one pipeline, because they solve different problems (text interpretation; arbitrary threshold evaluation; fixed standards-derived multi-factor scoring) with different failure modes and different validation regimes. This is the central architectural decision this revision makes explicit.
3. Deterministic corrosion engines over a trained model, for auditability and because no adequate training data exists.
4. Dual regex/LLM rule conversion, to balance cost, reproducibility and linguistic coverage — realised in the CLI path; the live web path still needs a regex fallback added to complete this design intent in production.
5. Human-in-the-loop rule review, a responsible-AI safeguard against hallucination — the review UI exists; the enforcement gate does not yet, and is the single most important remaining item for the white-box claim to be fully true end-to-end.
6. Composite weighted scoring with published, per-term weights for corrosion, so risk is explainable term-by-term, not a black box.
7. **Pending decision, named explicitly:** consolidate the two rule-extraction pipelines and the multiple corrosion-engine implementations onto one canonical code path each before final submission.

---

## 1.4 Results and Discussion

**Data-provenance note.** This section separates results by component, and distinguishes three evidence tiers used throughout: **(a) reproducible today** — running current code now produces this; **(b) genuine historical evidence** — real, measured output exists on disk from an earlier working version of the pipeline, but current code cannot yet regenerate it; **(c) pending** — specified but not yet executed.

### 1.4.1 Component 2 — generic comparator: what is genuinely demonstrated today

**Tier (a).** The comparator is live and exercised by two independent, real entry points: an uploaded-IFC flow (`analyze.py`) and a live pyRevit push (`revit_sync.py`), both producing the same `Module5_Reporter` visual summary. This demonstrates the source-independence design goal (§1.2.3) is genuinely met, not just intended. What is not yet available is an aggregate accuracy benchmark — e.g., "of N rule × element evaluations, M matched an independently hand-checked expected result" — because no such benchmark has been built yet (§1.2.8). This is scoped as pre-final-submission work.

### 1.4.2 Component 3 — corrosion engine: what is genuinely demonstrated today

**Tier (b), corrected from an earlier draft of this report.** Historical run-history records now represented in `public.issue_history` were inspected directly. They contain tracked elements (`IfcPipeSegment`, `IfcPipeFitting`, `IfcFastener`, `IfcHeatExchanger`, `IfcDuctSegment`, `IfcValve`, and others) with per-element event logs (`raised`/`resolved`, each carrying a real `composite_score` and `risk_band`), timestamped **2026-04-09, 18:44–18:47 UTC**. Filtering to currently-open (unresolved) issues gives exactly:

| Risk band | Open issue count |
|---|---|
| Critical | 9 |
| High | 7 |
| Medium | 9 |
| **Total open** | **25** |

*Table 2. Currently-open corrosion issues, computed from historical records now represented in `public.issue_history`.*

This **exactly matches** the "9 Critical / 7 High / 9 Medium, 25 issues" figures repeated in earlier drafts — those numbers are not invented. They are genuine measured output from a real compliance run. However: the module that wrote this file (`issue_tracker.py`) explicitly documents itself as a Streamlit-era component (`"Usage in Streamlit: from modules.issue_tracker import IssueTracker"`), and a repo-wide search confirms `IssueTracker.record_run()` is **never called anywhere in the current FastHTML `app/`** — meaning this specific result predates the present architecture and cannot be regenerated by running today's code. The two genuine, non-empty BCF export files on disk (`data/compliance_project_1.bcf`, 77 zip entries; `data/compliance_project_3.bcf`, 146 entries — both dated to the same session) are consistent with this same historical run. The modelled £170,600 cost and 162-working-day schedule-delay figures reported in earlier drafts could not be independently re-derived from any persisted file in the repository (cost/schedule outputs are not saved to disk by the current `cost_model.py`/`schedule_impact.py`), so they are reported here as **unverified pending figures**, distinct from the risk-band counts above, which are verified.

**Interpretation.** The corrosion scoring design works, and has been proven to work once, on real (or realistic) MEP element data — that is a stronger claim than "the code is untested," and a fairer one than "the numbers are fabricated." The concrete, scoped task before final submission is to (1) restore or reimplement the write path so a fresh run of `compliance_runner.py` persists its own BCF export and issue history the way the Streamlit prototype did, (2) re-run it — ideally against the same input data if it can be identified, or a clearly-labelled new benchmark otherwise — and (3) regenerate the cost/schedule figures from that fresh run so every number in this report is tier (a), reproducible today.

**Planned visualisations (to render once the fresh run above is complete):** stacked bar of risk-band counts by mechanism (GC/CC/MIC); heatmap of galvanic voltage-gap × environment class; cost/schedule waterfall by risk band.

### 1.4.3 Component 1 — rule-extraction accuracy: structure final, execution pending

**Tier (c).** Both scoring regimes described in §1.2.8 are specified and partially coded, not executed:

**(a) Information-extraction metrics (per rule field, regex vs. LLM):**

| Path | Precision | Recall | F1 | Notes |
|---|---|---|---|---|
| Regex baseline (CLI path) | *pending* | *pending* | *pending* | Metric computation not yet coded in `eval_harness.py` |
| LLM converter (live path, `gpt-4o-mini` default) | *pending* | *pending* | *pending* | Same |

**(b) LLM-as-judge scores (1–5 per dimension):**

| Dimension | Regex | LLM |
|---|---|---|
| Correctness | *pending* | *pending* |
| Completeness | *pending* | *pending* |
| Executability | *pending* | *pending* |

*Tables 3–4. Methodology and golden set (8 `EVAL_CASES`) are finalised; a known `AttributeError` bug and the missing precision/recall/F1 computation must be fixed before these can be populated with a genuine run.*

**Expected finding (hypothesis to confirm with the run):** the regex baseline should show higher precision but lower recall; the LLM path should improve recall at a per-call cost and with occasional over-extraction — the trade-off, not a single "best" path, remains the intended result.

### 1.4.4 Interpretation in relation to AECO workflows

BIMGuard AI is designed to slot into the weekly BIM coordination cycle ("model-drop day") as an automated digital inspector, closing the interpretation gap through Components 1+2 together and the corrosion-blindness gap through Component 3 alone. The source-independent comparator (§1.4.1) already demonstrates that a coordination team could run the same rule checks whether their workflow is IFC-export-based or native-Revit-based — a practical convenience beyond the strict openBIM framing. The corrosion engine's historical run (§1.4.2) demonstrates, on real measured output, the core value claim of the corrosion-blindness gap: 25 open issues spanning Critical to Medium bands on a modest element set is a materially large hit rate, supporting the argument that dissimilar-metal and crevice conditions are common enough to justify systematic, design-stage checking — precisely the class of risk invisible to geometric clash detection.

### 1.4.5 Implications, limitations and potential improvements

**Implications.** Design-stage detection of corrosion and code non-compliance shifts intervention left, where it is cheapest, and creates a machine-readable, auditable compliance record aligned with ISO 19650 and, for UK higher-risk buildings, the Building Safety Act "golden thread." Keeping rule extraction, rule comparison, and corrosion scoring as separate, independently-assessable components (rather than one pipeline) is itself a defensible architectural contribution: each can be validated, improved, or replaced without destabilising the others.

**Limitations, stated plainly:**
1. Component 3's corrosion engine covers two of three designed mechanisms live (galvanic, crevice); MIC is implemented but not integrated.
2. Four independent implementations of galvanic/crevice-style scoring exist across the codebase, with only `compliance_runner.py` live; consolidation is needed, ideally parametrised directly from static asset payloads in `public.static_data_assets`.
3. Component 1 has two implementations (CLI orchestrator vs. live `RuleExtractionService`); only the latter is reachable from the web UI.
4. `needs_review` (Component 1) does not yet gate which rules Component 2 evaluates.
5. Component 3's headline validation figures are genuine historical measurements (§1.4.2) but from a predecessor codebase; the current FastHTML pipeline has not yet reproduced them, and its BCF/issue-history write path needs restoring.
6. Precision/recall/F1 for Component 1 is not implemented in `eval_harness.py`, which also has a blocking bug.
7. Component 2 has no dedicated unit tests for its ten operators, despite being simple, pure-functional code that would be cheap to cover.
8. No continuous integration is configured; the existing 57-function pytest suite runs manually only, and `test_compliance.py` targets a stale REST API shape.
9. The BERT-based normative-sentence classifier (Component 1) ships with no fine-tuned model artifact and is not active in production.
10. Rule extraction is validated only on CODE dimensional clauses, not the full breadth of codes; the "Halo" volumetric-clearance capability remains conceptual; cost/schedule figures rely on hardcoded default UK rates rather than a checked-in, editable CSV.
11. Architectural elements that are missing or mis-classified in the source IFC (e.g., a door modelled as a generic proxy) are not detected — the comparator reports `NO_ELEMENTS` rather than flagging a likely false negative (§1.2.5).
12. Rule citations (`ref`) are plain text, not hyperlinks — there is no click-through to the source clause or to modelling guidance for elements that return `MISSING_DATA` (§1.2.3).
13. Human-in-the-loop review currently covers extracted rules only; compliance results (comparator failures and corrosion issues) have no reviewer sign-off field or workflow (§1.2.3).
14. Wall/slab thickness is not yet an explicit checked rule despite being a common regulatory measure (fire compartmentation, structural minimums) and despite a default value already existing in the `ifc_quality` improver's repair table (§1.2.5).
15. The IFC relationship graph visualisation (`ifc_graph.py`) is fully built (networkx + pyvis, violation highlighting) but is currently switched off behind a placeholder card in the live results page (§1.2.5).
16. `app/services/bcf_exporter.py` has a broken import (`app.models.compliance_models` does not exist) and would fail if anything called it; it currently has no callers, so the break is latent rather than user-facing, but it is dead code that should be fixed or removed (§1.2.6).
17. The richest corrosion data contract in the codebase, `PipingElement` (`piping_schema.py`), has no producer — `ifc_parser.py` never constructs one from real IFC data — so its one real consumer, `galvanic.py`, can only ever run against three hand-written example fixtures (§1.2.4).
18. The two rule-extraction implementations default to different LLM models (`gemini/gemini-2.0-flash` in the deployed environment vs. `gpt-4o-mini` in the CLI path's `config.py`), which is a further symptom of the two paths never having been reconciled (§1.2.7).

**Improvements, in priority order for the final submission:**
1. Add unit tests for `Module4_Comparator`'s ten operators (Component 2) — cheapest, highest-confidence item on this list.
2. Restore/reimplement the corrosion engine's BCF and issue-history write path, then re-run it and the aggregate benchmark to convert §1.4.2 from tier (b)/(c) evidence to tier (a).
3. Fix `eval_harness.py` (the `generate_rules` bug), implement precision/recall/F1, then run it to populate §1.4.3.
4. Wire the MIC engine into `compliance_runner.py`, ideally reading tables from static asset payloads in `public.static_data_assets` instead of hardcoded Python tables.
5. Reconcile the two rule-extraction pipelines into one, and add a regex-only fallback mode to the live LLM path.
6. Add the `needs_review` gate to Component 2's rule query so only approved rules are evaluated.
7. Add a GitHub Actions workflow to run the existing pytest suite on every push, and fix or retire `test_compliance.py`.
8. Validate on a real federated data-centre model; expand the golden rule set across jurisdictions; implement Halo clearance geometry; render a real BCF snapshot image instead of the placeholder pixel.
9. Build heuristics or geometry-based reclassification to catch architectural elements that behave like a door/window/stair but are not correctly tagged in the source IFC, closing the false-negative path described in §1.2.5.
10. Add the two planned hyperlinks per rule result — source-clause citation and buildingSMART/BIMGuard modelling guidance — so a `MISSING_DATA` result becomes actionable rather than opaque (§1.2.3).
11. Extend `needs_review`-style human sign-off from rules to results, so a reviewer can accept/dismiss individual comparator and corrosion issues before a report is finalised (§1.2.3).
12. Add explicit thickness rules (wall/slab) to the seed set, and extend the discipline-sorted results view (§1.2.3) to show a combined Architecture + MEP report rather than one theme at a time.
13. Evaluate `trimesh` as an additional geometry backend if the current `ifcopenshell.geom`/`shapely` stack proves insufficient for the planned Halo clearance-geometry work (§1.2.5).
14. Re-enable `ifc_graph.py`'s pyvis visualisation in `analyze.py` — the graph-building logic already works, so this is presentation wiring, not new engineering (§1.2.5).
15. Fix or remove `bcf_exporter.py`'s broken `app.models.compliance_models` import (§1.2.6).
16. Give `ifc_parser.py` a real `PipingElement` producer so `galvanic.py` (§1.2.4) can run against actual parsed IFC data instead of only its example fixtures — the more standards-faithful path to a single, unified corrosion engine.
17. Standardise on one default LLM model across both rule-extraction paths (§1.2.7), and document the choice explicitly rather than leaving it implicit in environment variables.

---

## 1.5 References and Appendices

### References (APA 7th ed., to be finalised)

buildingSMART International. (2020). *Industry Foundation Classes (IFC) and BIM Collaboration Format (BCF 2.1)*. https://www.buildingsmart.org/

Dimyadi, J., & Amor, R. (2013). Automated building code compliance checking, where is it at? *Proceedings of CIB WBC 2013*.

Eastman, C., Lee, J., Jeong, Y., & Lee, J. (2009). Automatic rule-based checking of building designs. *Automation in Construction, 18*(8), 1011–1033.

Fuchs, S., et al. (2023). *[LLM-based extraction of building-code requirements — full citation to be verified before final submission]*.

Gallaher, M. P., O'Connor, A. C., Dettbarn, J. L., & Gilday, L. T. (2004). *Cost analysis of inadequate interoperability in the U.S. capital facilities industry* (NIST GCR 04-867). NIST.

ISO. (2018). *ISO 19650-1:2018, Organisation and digitisation of information about buildings and civil engineering works*. International Organization for Standardization.

ISO. (2018). *ISO 16739-1:2018, Industry Foundation Classes (IFC)*. International Organization for Standardization.

Koch, G., et al. (2016). *International measures of prevention, application, and economics of corrosion technologies (IMPACT)*. NACE International.

NFPA. (2023). *NFPA 70: National Electrical Code*. National Fire Protection Association.

Zhang, J., & El-Gohary, N. M. (2017). Integrating semantic NLP and logic reasoning into a unified system for fully automated code checking. *Automation in Construction, 73*, 45–57.

Zheng, Z., et al. (2022). *[LLM/transformer rule extraction for compliance — full citation to be verified before final submission]*.

**Engineering standards referenced by the corrosion engines:** NASA-STD-6012; EN ISO 15329:2007; ASTM G48 Method B; CIRIA C692; IMOA Design Manual (4th ed.); CIBSE Guide G; CIBSE TM13:2013; HSE HSG274; BS 8552:2012; ASTM G-187; EN 1993-1-4; EN ISO 9308-1; WHO Guidelines for Drinking-Water Quality (4th ed.).

### Appendices

- **Appendix A — Source code repository.** `github.com/maicen/bim-guard` (verified `origin` remote). Component map: rule extraction (`app/services/rule_extraction_service.py`, `app/modules/module1_doc_parser/`, `module1b_nlp_annotator/`, `module3_rule_builder/`); generic comparator (`app/modules/module4_comparator/__init__.py`, `app/services/revit_sync_service.py`); IFC ingestion, geometry, spatial adjacency and egress analysis (`app/modules/module2_ifc_read/ifc_parser.py`, `ifc_geometry.py`, `ifc_spatial.py`, `ifc_egress.py`, `ifc_graph.py`, `ifc_quality/`, `piping_schema.py`); corrosion engine (`app/modules/module4_comparator/compliance_runner.py`, `galvanic.py`, `app/engines/`); application shell (`app/routes/projects.py`, `viewer.py`, `app/services/documents_service.py`, `object_storage.py`).
- **Appendix B — Rulesets (JSON).** DB-backed static assets for `ruleset:BIMGUARD-GC-001`, `ruleset:BIMGUARD-CC-001`, and `ruleset:BIMGUARD-MC-001` in `public.static_data_assets` — each a versioned specification (`ruleset_version: "1.0.0"`) with real, detailed material tables, thresholds, weights, an explicit risk-band-to-BCF-action mapping, and 6–8 cited standards per mechanism. Currently consumed for Rule Library documentation/display, not as the live parametrisation of the corrosion engine itself (§1.2.4, §1.4.5 improvement #4).
- **Appendix C — Scoring models.** GC-001, CC-001, MC-001 composite formulas and risk-band definitions as implemented in `app/engines/` (reference implementation) — see §1.2.4 for how these differ from the tables actually executed by `compliance_runner.py` in production.
- **Appendix D — Evaluation harness, tests, and historical run data.** `app/modules/tests/` (57 test functions: `test_module1.py`, `test_module3.py`, `test_compliance.py`, `test_integration.py`, `conftest.py`) and `eval_harness.py` (golden `EVAL_CASES`, LLM-as-judge scoring) — see §1.2.8 and §1.4.5 for fixes needed. Historical corrosion-engine run history is now represented in `public.issue_history`, the evidentiary basis for §1.4.2.
- **Appendix E — Sample data.** IFC reference models in `data/uploads/ifc/`: Pacific Continental Residence (IFC4.3 RV + IFC2x3 CV), AC20-Institute, Infra-Plumbing, and others. Genuine BCF outputs: `data/compliance_project_1.bcf`, `data/compliance_project_3.bcf`.
