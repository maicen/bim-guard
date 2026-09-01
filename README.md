# BIMGUARD AI: Agentic RAG Pipeline for OpenBIM Compliance

BIMGUARD AI is an Automated Code Compliance Checking (ACCC) platform that bridges OpenBIM standards (IFC, BCF, IDS) with large language models. This repository contains the Python-based compliance engines and the data ingestion pipeline used to evaluate structural and material integrity against international building codes.

## Project Scope
This project focuses on two primary compliance modules:
*   **GC-001 (Seismic):** Evaluates nonstructural component clearance volumes and clash detection against seismic bracing standards (e.g., FEMA E-74, ASCE 7-22).
*   **CC-001 (Piping & Corrosion):** Evaluates material degradation, galvanic mismatch, and environmental exposure against atmospheric standards (e.g., ISO 9223, MBIE B2).

## The Agentic RAG Methodology
To eliminate AI hallucination and ensure strict engineering accuracy, this project utilizes a "Walled Garden" Retrieval-Augmented Generation (RAG) architecture:
1.  **Retrieval (`fetch_standards.py`):** An LLM-native web scraping script powered by the Firecrawl API dynamically retrieves open-access government building codes and manufacturer material specifications, converting them into clean Markdown.
2.  **Augmentation (`compile_for_notebooklm.py`):** A custom compilation pipeline packages the OpenBIM Python logic (`IfcOpenShell`), static JSON rule packs, and scraped standards into targeted, domain-isolated Markdown exports (`bimguard_seismic_rules.md` and `bimguard_corrosion_rules.md`).
3.  **Generation (Gemini Notebooks):** The compiled domains are fed into isolated Google Gemini Notebook (NotebookLM) workspaces. The AI reasoning engine evaluates the Python codebase strictly against the ingested facts (and uploaded proprietary, IP-protected PDFs) to identify gaps in the compliance algorithms.

## Repository Structure
*   `/app/engines/` - Core Python kernels for galvanic, crevice, and seismic clearance analysis.
*   `/data/rulesets/` - Static JSON configurations defining fallback rules for material mismatch (MM-001) and cross-material (XM-001) interactions.
*   `/scripts/` - The AI data ingestion and Markdown compilation pipeline.

## Usage
To pull a new open-access standard and recompile the AI workspace:
```bash
# 1. Search and extract an online standard via Firecrawl
python scripts/fetch_standards.py "MBIE B2 durability for metal components" mbie_durability --corrosion --search

# 2. Compile the updated codebase and standards for NotebookLM
python scripts/compile_for_notebooklm.py
```
