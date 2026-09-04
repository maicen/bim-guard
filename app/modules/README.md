# BIMGuard Modules — Module 1 + 3 (CODE Example)

Automated building-code compliance rule extraction pipeline.
Converts building-code PDFs (any jurisdiction or standard) into structured rules stored in `rules.db`,
ready for IFC model compliance checking in Module 4.

This module documentation uses an CODE example dataset, but the BIM-Guard app architecture is domain-agnostic and supports other standards/rulesets.

---

## Pipeline Overview

```
app/modules/
├── config.py
├── orchestrator.py
├── document_parsing/          (unchanged)
├── ifc_reader/            ← was ifc_reader.py
│   ├── __init__.py              (IFCReader + quality gate)
│   ├── ifc_parser.py
│   ├── ifc_geometry.py
│   ├── piping_schema.py
│   └── ifc_quality/
│       ├── validator.py
│       ├── improver.py
│       └── generator.py
├── rule_builder/        (unchanged)
├── comparator/          ← was comparator.py
│   ├── __init__.py              (ComplianceComparator)
│   ├── compliance_runner.py
│   ├── galvanic.py
│   ├── issue_schema.py
│   └── issue_tracker.py
└── reporter/            ← was reporter.py
    ├── __init__.py              (ComplianceReporter)
    ├── bcf_generator.py
    ├── report_generator.py
    ├── schedule_impact.py
    └── cost_model.py
All 11 import checks pass, the web app imports cleanly, and the structure is better than before.

c:\Users\Malak\OneDrive\Desktop\Masters course materials\FMP\repo\bim-guard\app\modules\README.md
list the new structure for all modules
Bash List full modules directory tree
IN
find "/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules" -not -path "*/__pycache__/*" -not -name "*.pyc" | sort

OUT
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/README.md
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/__init__.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/__pycache__
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/config.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/__init__.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/__pycache__
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/bert_classifier.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/confidence_scorer.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/dependency_parser.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/docling_extractor.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/enhanced_orchestrator.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/keyword_filter.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/keywords
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/keywords/__init__.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/keywords/__pycache__
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/keywords/keyword_master.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/section_chunker.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/table_rule_builder.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/document_parsing/tfidf_analyzer.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/ifc_reader
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/ifc_reader/__init__.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/ifc_reader/__pycache__
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/ifc_reader/ifc_geometry.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/ifc_reader/ifc_parser.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/ifc_reader/ifc_quality
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/ifc_reader/ifc_quality/__init__.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/ifc_reader/ifc_quality/__pycache__
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/ifc_reader/ifc_quality/generator.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/ifc_reader/ifc_quality/improver.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/ifc_reader/ifc_quality/validator.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/ifc_reader/piping_schema.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/rule_builder
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/rule_builder/__init__.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/rule_builder/__pycache__
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/rule_builder/rule_builder_mock.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/rule_builder/code_seed_rules.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/rule_builder/rule_converter.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/rule_builder/rule_generator.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/rule_builder/rule_store.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/comparator
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/comparator/__init__.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/comparator/__pycache__
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/comparator/compliance_runner.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/comparator/galvanic.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/comparator/issue_schema.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/comparator/issue_tracker.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/reporter
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/reporter/__init__.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/reporter/__pycache__
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/reporter/bcf_generator.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/reporter/cost_model.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/reporter/report_generator.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/reporter/schedule_impact.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/orchestrator.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/requirements.txt
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/tests
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/tests/TEST_README.md
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/tests/conftest.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/tests/eval_harness.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/tests/pdf_stairs_mock.pdf
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/tests/test_compliance.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/tests/test_integration.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/tests/test_document_parsing.py
/c/Users/Malak/OneDrive/Desktop/Masters course materials/FMP/repo/bim-guard/app/modules/tests/test_rule_builder.py

app/modules/
│
├── orchestrator.py              — pipeline entry point & BIMGuard_App
├── config.py                    — shared constants (M1 + M3)
├── __init__.py
├── requirements.txt
├── README.md
│
├── document_parsing/          — PDF extraction → structured rules
│   ├── __init__.py
│   ├── docling_extractor.py
│   ├── enhanced_orchestrator.py
│   ├── section_chunker.py
│   ├── keyword_filter.py
│   ├── table_rule_builder.py
│   ├── tfidf_analyzer.py
│   ├── confidence_scorer.py
│   ├── dependency_parser.py
│   ├── bert_classifier.py
│   └── keywords/
│       ├── __init__.py
│       └── keyword_master.py
│
├── ifc_reader/            — IFC parsing + quality gate
│   ├── __init__.py              ← IFCReader (with auto quality check)
│   ├── ifc_parser.py            — raw IFC element reader (ServiceElement)
│   ├── ifc_geometry.py          — geometry extraction from pipe segments
│   ├── piping_schema.py         — M2→M4 data contract (PipingElement)
│   └── ifc_quality/             — IFC file quality toolkit
│       ├── __init__.py
│       ├── validator.py         — score labeling / GUIDs / properties (0–100%)
│       ├── improver.py          — auto-add missing GUIDs, names, Psets
│       └── generator.py        — generate well-formed test IFC files
│
├── rule_builder/        — NLP → structured compliance rules
│   ├── __init__.py
│   ├── rule_generator.py
│   ├── rule_converter.py        — OpenAI GPT-4o rule extractor
│   ├── rule_store.py            — shared rule persistence via app services
│   ├── code_seed_rules.py        — 25+ CODE baseline rules
│   └── rule_builder_mock.py
│
├── comparator/          — IFC data vs rule library validation
│   ├── __init__.py              ← ComplianceComparator
│   ├── compliance_runner.py     — GC-001 / CC-001 engine orchestrator
│   ├── galvanic.py              — galvanic corrosion comparator
│   ├── issue_schema.py          — Issue data contract (M4 → M5)
│   └── issue_tracker.py         — issue history across runs
│
├── reporter/            — report generation
│   ├── __init__.py              ← ComplianceReporter
│   ├── bcf_generator.py         — BCF 2.1 ZIP output
│   ├── report_generator.py      — Word / PDF compliance report
│   ├── schedule_impact.py       — delay days + Gantt data
│   └── cost_model.py            — configurable cost/duration model
│
└── tests/
    ├── test_document_parsing.py
    ├── test_rule_builder.py
    ├── test_compliance.py
    ├── test_integration.py
    ├── conftest.py
    └── eval_harness.py




---

## Switching Between Regex and GPT-4o

Open `orchestrator.py` and change one line:

```python
USE_GPT4O = False   # regex — free, no API key, works offline
USE_GPT4O = True    # GPT-4o — more accurate, costs per API call
```

---

## Setup

### 1. Run commands from the project root

All commands below assume you are in the repository root (`bim-guard/`).

### 2. Install Python dependencies

```bash
uv sync --group ml-pipeline
```

> The spaCy English model (`en_core_web_sm`) is included in the `ml-pipeline` dependency group in `pyproject.toml` and installed automatically.

> **First run:** Docling will download its vision models (~2 min, one-time only).
> Use a GPU runtime for faster processing if available.

### 3. Set your API key (only needed if USE_GPT4O = True)

```bash
cp example.env .env
# Edit .env and add your Gemini API key
GEMINI_API_KEY=your_key_here
```

---

## Run the Pipeline

```bash
# Full pipeline — all 13 CODE sections
uv run python -m app.modules.orchestrator data/input_docs/BuildingCode_Part9.pdf

# Test on one section first (recommended)
uv run python -m app.modules.orchestrator data/input_docs/BuildingCode_Part9.pdf
```

Or from Python:

```python
from app.modules.orchestrator import run_pipeline

result = run_pipeline(
    pdf_path      = "data/input_docs/BuildingCode_Part9.pdf",
    run_sections  = ["4"],   # test Section 4 (Stairs) first
    seed_db_first = True,
)
print(result)
```

---

## Seed Pre-built Rules

25 pre-built CODE Part 9 rules are included.
Seed them without uploading a PDF:

```bash
uv run python -m app.modules.rule_builder.code_seed_rules
```

---

## Run Tests

```bash
uv run pytest app/modules/tests -v
```

---

## File Structure

```
bim-guard/
├── app/
│   └── modules/
│       ├── document_parsing/
│       │   ├── docling_extractor.py        ← Step 1: PDF → text + tables
│       │   ├── table_rule_builder.py       ← Step 2: tables → rules directly
│       │   ├── section_chunker.py          ← Step 3: text → 13 sections
│       │   ├── keyword_filter.py           ← Step 4: spaCy scoring
│       │   ├── tfidf_analyzer.py           ← Improvement 1: keyword discovery
│       │   ├── dependency_parser.py        ← Improvement 2: grammar signals
│       │   ├── confidence_scorer.py        ← Improvement 3: SEND/SKIP decision
│       │   ├── bert_classifier.py          ← Improvement 4: sentence classifier
│       │   ├── enhanced_orchestrator.py    ← runs all 4 improvements
│       │   └── keywords/
│       │       └── keyword_master.py       ← 193 keywords, 12 groups
│       ├── rule_builder/
│       │   ├── rule_store.py               ← shared CRUD via RuleService
│       │   ├── rule_generator.py           ← validate + save rules
│       │   ├── rule_converter.py           ← GPT-4o + RAG NLP engine
│       │   ├── regex_rule_converter.py     ← regex engine (default)
│       │   └── code_seed_rules.py           ← 25 pre-built CODE rules
│       └── orchestrator.py                 ← single entry point
├── data/
│   └── cache/                              ← runtime local cache for remote storage objects
├── example.env                              ← copy to .env, add API key
└── pyproject.toml                           ← dependency and tool config
```

---

## rules.db Schema

| Field | Type | Description |
|---|---|---|
| rule_id | TEXT | UUID primary key |
| source_doc | TEXT | BuildingCode_Part9_PDF / BuildingCode_Table_Direct / BuildingCode_Part9_Seed |
| section_ref | TEXT | CODE section e.g. 9.8.2.1.(2) |
| rule_type | TEXT | json_check / range_check / regex / exists_check |
| entity_type | TEXT | IFC class e.g. IfcStairFlight |
| property_name | TEXT | IFC property name |
| operator | TEXT | >= / <= / == / != / between / exists |
| value | TEXT | JSON-encoded number, string, or [min, max] |
| unit | TEXT | mm / m / m2 / deg / ratio |
| priority | INT | 1 = critical, 0 = standard |
| description | TEXT | plain English explanation |

---

## Converter Comparison

| | Regex | GPT-4o |
|---|---|---|
| Cost | Free | Per API call |
| API key needed | No | Yes |
| Works offline | Yes | No |
| Catches all phrasing | No | Yes |
| Hallucinations | Never | Occasionally |
| Speed | Instant | 1–3 sec per chunk |
| Best for | Development / testing | Production accuracy |

---

## Next Steps (Module 2 + 4)

Once rules.db is populated:

- **Module 2** reads IFC files and extracts element properties
- **Module 4** compares IFC properties against rules.db and flags failures
- **Module 5** generates BCF / CSV / PDF compliance reports
