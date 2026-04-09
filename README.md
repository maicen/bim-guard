# BIM-Guard

## Project Overview

**BIM Guard** is a BIM compliance application built with FastHTML (Python) and MonsterUI. It lets users upload IFC models, define compliance rules from documents, and generate reports.

**Tech stack:** FastHTML · MonsterUI · FastLite (SQLite) · IfcOpenShell · HTMX · LiteLLM (Gemini)

## Instructions Files Map

| File | Who reads it | What it defines |
| --- | --- | --- |
| README.md | Humans | What the project is |
| AGENTS.md, CLAUDE.md, .github\instructions\project-specific.instructions.md | Coding agents | How to build the project |
| DESIGN.md | Design agents | How the project should look and feel |

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
