# Clause grounding indexes

Per-clause bSDD grounding hints, built and promoted from
[bim-guard-evaluation](https://github.com/maicen/bim-guard-evaluation)'s
knowledge-graph R&D pipeline (`kg/` — see `kg/grounding.py` for the trust
rule and `kg/export_grounding.py` for the export step).

Loaded by `app/services/clause_grounding_index.py`, consulted by
`RuleExtractionService._search_classes_grounded` when the clause being
grounded (`ClauseMetadata.clause_id`) is present in the loaded index.

## Files

- `obc_app_a_grounding_index.json` — built from `sources/OBC_2023.App-A_docling.dclx`
  in bim-guard-evaluation: clause candidates scored by a multi-signal lexical
  matcher (TF-IDF cosine, Jaccard, fuzzy ratio, substring), with
  borderline-confidence candidates additionally verified by
  `anthropic/claude-haiku-4.5` via OpenRouter. Only `llm_verdict=correct` and
  lexically-high-confidence (never sent to the LLM) candidates are included;
  see the source repo's `research/kg/obc_app_a_correction_report.json` for
  the full run's parameters.

## Promoting a new/updated index

1. Build and iterate the graph in bim-guard-evaluation (`kg/build_kg.py`,
   `kg/correct_graph.py`, `kg/export_grounding.py`).
2. Copy the resulting `*_grounding_index.json` here.
3. Update this README's file list.
