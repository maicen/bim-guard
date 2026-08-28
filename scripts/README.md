# Scripts

This directory contains standalone scripts, utilities, and runner tools that are outside the main application runtime.

## Directory Structure

- **`eval/`**: Scripts used for evaluation, scoring, and testing the real IFC pipeline across datasets (e.g., the 38-model verified dataset). These are typically print-based standalone scripts mirroring tests, but are meant to be run directly for validation output rather than via `pytest`.
- **`build/`**: Utility scripts for building presentation decks, processing templates, or automating build-time asset generation.
- **`benchmarks/`**: Scripts for load testing and running performance benchmarks against the compliance engines.

## Usage

Most scripts here are designed to be run from the repository root to ensure python paths resolve correctly:

```bash
uv run python scripts/eval/test_all_38_models.py
```
