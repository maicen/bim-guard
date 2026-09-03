# Scripts

This directory contains standalone scripts, utilities, and runner tools that are outside the main application runtime.

## Directory Structure

- **`build/`**: Utility scripts for building presentation decks, processing templates, or automating build-time asset generation.
- **`benchmarks/`**: Scripts for load testing and running performance benchmarks against the compliance engines.

> [!NOTE]
> **Evaluation, Scoring & NLP Annotation Relocation:**
> All evaluation harnesses, linguistic NLP annotation scoring, multi-model validation sweeps (`test_all_38_models.py`), and research analyses (confusion matrices, etc.) have been moved to the dedicated companion repository:
> [bim-guard-evaluation](https://github.com/maicen/bim-guard-evaluation)

## Usage

Most scripts here are designed to be run from the repository root to ensure python paths resolve correctly:

```bash
uv run python scripts/run_full_pipeline.py
```

