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
| AGENTS.md, CLAUDE.md, .github\instructions\project-specific.instructions.md | Coding agents | How to build the project |
| DESIGN.md | Design agents | How the project should look and feel |

## Repository Structure

- `app/` - main application package
  - `main.py` - FastHTML app and route initialization
  - `routes/` - HTTP route handlers for dashboard, library, projects, analysis, viewer
  - `components/` - reusable UI components and page layout helpers
  - `services/` - business logic, persistence, IFC parsing, rule extraction, and document handling
  - `modules/` - pipeline modules for document reading, IFC parsing, rule building, comparison, and reporting
  - `views/` - shared view components for layouts and page rendering
- `data/` - runtime data storage
  - `uploads/` - uploaded files and stored documents
- `docs/` - supporting documentation, enhancement plans, and resources
- `engines/` - experimental or domain-specific engine scripts and demo data
- `IFC-Sample-Test-Files/` - sample IFC models for testing and exploration
- `modules/` - additional BIM-related utilities, report generators, and integration helpers
- `rulesets/` - predefined compliance rule set JSON files
- `static/` - static web assets (CSS, JavaScript, viewer scripts)
- root files
  - `main.py` - app entrypoint used by uvicorn
  - `pyproject.toml` - Python project metadata and dependencies
  - `example.env` - environment variable template
  - `README.md` - project overview and usage guide

## Getting Started

```bash
# Install dependencies
uv sync

# Run the app
uv run uvicorn main:app --reload

```

## Environment Setup

Create a local `.env` from `example.env` and configure Gemini credentials:

```bash
# PowerShell
Copy-Item example.env .env
```

Required variables:

- `GEMINI_API_KEY` (or `GOOGLE_API_KEY`)
- `BIM_GUARD_RULE_MODEL` (optional, defaults to `gemini/gemini-1.5-flash`)

The app loads `.env` at startup using `python-dotenv`.

## Rule Extraction (AI)

Rule extraction is available at `/library/rules/extract`.

Current flow:

1. Upload a BEP/regulation PDF.
2. `Module1_DocReader` extracts PDF text.
3. Text is normalized and chunked for long documents.
4. `RuleExtractionService` sends each chunk to Gemini through LiteLLM.
5. Extracted rules are normalized and de-duplicated.

Output rule fields:

- `ref`
- `desc`
- `target`

## Notes

- If `.env` is not loaded (for custom scripts/tests), call `load_env_file()` from `app.utils` before creating AI extraction services.
- Document upload validation includes extension, MIME type, and content checks.
