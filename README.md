# BIM-Guard

## 🔗 Live Demo

👉 **[View the BIMGUARD AI Interactive Pipeline](https://maicen.github.io/bim-guard/)**

MAICEN-1125-M10 · Final Master's Project · Group 5 · Zigurat Global Institute of Technology

## Project Overview

**BIM Guard** is a BIM compliance application built with FastHTML (Python) and MonsterUI. It lets users upload IFC models, define compliance rules from documents, and generate reports.

**Tech stack:** FastHTML · MonsterUI · FastLite (SQLite) · IfcOpenShell · HTMX · LiteLLM (Gemini)

## Instructions Files Map

| File | Who reads it | What it defines |
| --- | --- | --- |
| README.md | Humans | What the project is |
| AGENTS.md, CLAUDE.md, .github/instructions/project-specific.instructions.md | Coding agents | How to build the project |
| DESIGN.md | Design agents | How the project should look and feel |

## Repository Structure

```
bim-guard/
├── app/                        # Main application package
│   ├── main.py                 # FastHTML app init and route mounting
│   ├── utils.py                # Shared utilities (env loading, helpers)
│   ├── components/             # Reusable FastHTML UI elements
│   │   ├── layout.py           # DashboardLayout, AppSidebar, AppHeader
│   │   ├── documents_ui.py
│   │   ├── projects_ui.py
│   │   ├── rules_ui.py
│   │   ├── rule_extraction_ui.py
│   │   ├── themed_ui.py
│   │   └── ui/                 # Low-level component primitives
│   │       ├── button.py, card.py, table.py, sidebar.py, ...
│   ├── routes/                 # HTTP handlers and HTMX responses
│   │   ├── dashboard.py
│   │   ├── library.py
│   │   ├── projects.py
│   │   ├── analyze.py
│   │   └── viewer.py           # In-browser IFC 3D viewer
│   ├── services/               # Business logic and persistence
│   │   ├── persistence.py      # SQLite schema via fastlite
│   │   ├── documents_service.py
│   │   ├── projects_service.py
│   │   ├── rules_service.py
│   │   ├── rule_extraction_service.py
│   │   ├── gemini_rule_extractor.py
│   │   └── ifc_parser.py
│   ├── modules/                # 5-step compliance pipeline
│   │   ├── module1_doc_reader.py
│   │   ├── module2_ifc_read.py
│   │   ├── module3_rule_builder.py
│   │   ├── module4_comparator.py
│   │   ├── module5_reporter.py
│   │   └── orchestrator.py
│   └── views/
│       └── layout.py
├── data/                       # Runtime data (SQLite DB + uploads)
│   └── uploads/
│       └── ifc/
├── docs/                       # Supporting documentation and resources
├── static/                     # CSS, JS, and IFC viewer assets
│   ├── css/
│   ├── js/
│   └── lib/
├── IFC-Sample-Test-Files/      # Sample IFC models for testing
├── main.py                     # Uvicorn entrypoint
├── pyproject.toml              # Python project metadata and dependencies
└── example.env                 # Environment variable template
```

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/maicen/bim-guard.git
cd bim-guard
```

### 2. Install uv

[uv](https://docs.astral.sh/uv/) is the package manager used by this project. Install it with:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 3. Install dependencies

**Step 3a — core app dependencies** (FastHTML, MonsterUI, pypdf, etc.):

```bash
uv sync
```

This creates a `.venv` and installs all dependencies declared in `pyproject.toml`. Python 3.12 or later is required.

**Step 3b — ML pipeline dependencies** (Docling, spaCy, scikit-learn, PyTorch, etc.):

```bash
uv pip install -r app/modules/requirements.txt
```

> This installs the heavier ML libraries used by the Module 1 document parser pipeline (docling, spacy + English model, torch, transformers, scikit-learn). First run will download model weights — allow a few minutes.

### 4. Configure environment variables (required for AI features)

Create a `.env` file from the template:

```bash
# PowerShell
Copy-Item example.env .env

# macOS / Linux
cp example.env .env
```

Open `.env` and set your Gemini API key — get one free at [aistudio.google.com/api-keys](https://aistudio.google.com/api-keys):

```
GEMINI_API_KEY=your_key_here
```

> Without this key the **Rule Extraction Studio** (`/library/rules/extract`) will show an error. Basic document upload and text extraction (pypdf) work without a key.

### 5. Run the app

```bash
uv run uvicorn main:app --reload
```

The app will be available at `http://127.0.0.1:8000`.

## Rule Extraction (AI)

Rule extraction is available at `/library/rules/extract`.

Current flow:

1. Upload a BEP/regulation PDF.
2. `Module1_DocReader` extracts PDF text.
3. Text is normalized and chunked for long documents.
4. `RuleExtractionService` sends each chunk to Gemini through LiteLLM.
5. Extracted rules are normalized and de-duplicated.

## Next Development Steps

- Verify the reported issues.
- Verify the BCF exported.



Output rule fields:

- `ref`
- `desc`
- `target`

## Notes

- If `.env` is not loaded (for custom scripts/tests), call `load_env_file()` from `app.utils` before creating AI extraction services.
- Document upload validation includes extension, MIME type, and content checks.
