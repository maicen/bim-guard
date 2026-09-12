# Entry points for the offline engine showcase

Everything below was read from the working tree at `957de2f`
(branch `docs/engine-showcase-2026-09-08`, cut from `origin/main`). Line numbers
are that commit's. No HTTP layer and no `scripts/prewarm_demo.py` was used.

---

## 1. The piping audit for a parsed model

| What | Where |
| --- | --- |
| Public entry the API calls | `run_analysis(slug, project_id, *, use_cache, engines, include_low)` — `app/services/analysis_runner.py:369` |
| Project lookup it does first | `model_bytes(project_id)` — `app/services/analysis_runner.py:83` (seismic uses `model_bytes_all`, `:126`) |
| **The orchestration beneath the lookup — what this showcase calls** | `_run_corrosion_tracked(content, project_id, engines, include_low)` — `app/services/analysis_runner.py:166` |
| Parse step it consumes | `parse_ifc_bytes(content, source_ref=..., with_piping=True)` — `app/modules/phase_6/phase_6b_parsing.py:215`, called at `analysis_runner.py:220` |
| Assessment it then calls | `run_corrosion_analysis(parsed, *, include_low, run_id, engines)` — `app/modules/phase_6/phase_6c_corrosion_ui.py:1133`, called at `analysis_runner.py:241` |

`_run_corrosion_tracked` is the correct seam: it is exactly what `run_analysis`
invokes once the project's bytes are in hand (`analysis_runner.py:461`), so
passing a local file's bytes in place of the project's stored model reproduces a
real run from the parse onward, including the pipeline-tracker stages.

### How the engine set is expressed

`resolve_engine_codes(engines) -> tuple[str, ...]` —
`app/modules/phase_6/phase_6c_corrosion_ui.py:200`. It reduces `None`, `["gc"]`
and `["GC-001"]` to the codes that actually execute. This is the canonical form
the cache key uses: `run_analysis` builds `CacheKey(..., engines=engine_codes,
include_low=include_low, source_sha256=...)` at `analysis_runner.py:420-434`.
The showcase records the same canonical tuple in each run's summary.

## 2. SB-001 over a federated file list

`run_seismic_analysis(ifc_bytes, *, primary_label, extra_models, config_path,
brace_type, seismic_zone, building_type, run_id)` —
`app/modules/phase_6/phase_6d_seismic.py:371`, called from `run_analysis` at
`analysis_runner.py:449`. The primary model is passed as bytes and every other
model as `extra_models=[(file_name, bytes), ...]`; geometry from all of them is
unioned before clash detection. `primary_label` exists so a cross-model clash
names both files rather than the literal "primary model".

## 3. Export and validation

| Format | Function |
| --- | --- |
| CSV | `to_csv(result)` — `app/modules/phase_6/phase_6e_export.py:139` |
| JSON | `to_json(result, *, indent)` — `app/modules/phase_6/phase_6e_export.py:187` |
| BCF 2.1 | `to_bcf(result, *, include_data_quality)` — `app/modules/phase_6/phase_6e_export.py:727` |
| One dispatcher for all three | `export(result, fmt)` — `app/modules/phase_6/phase_6e_export.py:792` |

CSV columns are the module constant `CSV_COLUMNS` —
`app/modules/phase_6/phase_6e_export.py:77-105`, sixteen columns:

```
id, element_id, rule_id, mechanism, band, score, title, description,
mitigation, assignee_role, status, is_data_quality, check,
overlap_volume_mm3, clearance_mm, standards
```

**XSD validation** used by `tests/test_phase_6e_export.py`: the `xmlschema`
package, loading `tests/schemas/bcf21/markup.xsd` and reporting
`schema.iter_errors(markup)` — see `tests/test_phase_6e_export.py:466-475`,
`:559-574`, `:700-708`. The showcase validates each `markup.bcf` entry in the
produced archive the same way.

## 4. Field names on a finding

Findings are `Issue` dataclasses — `app/modules/comparator/issue_schema.py:52`.
The API converts them to `AuditIssueContract` in `_format_result` —
`app/api/analyze.py:175`, where `details = dict(i.metadata)`
(`app/api/analyze.py:209`).

| Wanted | Field | Where it is set |
| --- | --- | --- |
| Engine id | `rule_id` (e.g. `GC-001.03`), `mechanism` (`"GC-001 galvanic"`), and `metadata["mechanism_code"]` (`"GC-001"`) | `phase_6c_corrosion_ui.py:1093`, `:1095`, `:1101` |
| Band | `band` — a `RiskBand` enum; `.value` is lowercase | `issue_schema.py:69`, normalised by `normalise_band` `phase_6c_corrosion_ui.py:210` |
| Score | `score` — float 0.0–1.0 | `issue_schema.py:70`, set `phase_6c_corrosion_ui.py:1097` |
| Verdict vs data-quality | `mechanism == "data_quality"` (constant `DATA_QUALITY`, `phase_6c_corrosion_ui.py:130`). The specific status is `metadata["check"]` — e.g. `material_unresolved`, `hydraulics_unavailable`, `network_unassessed` | `_data_quality_issue` `phase_6c_corrosion_ui.py:889-930`, `:966` |
| `ruleset_version` | `metadata["ruleset_version"]` | `phase_6c_corrosion_ui.py:1102`; backfilled at `:804` and `:841` |
| Element GUID | `element_id` (the IFC GlobalId) | `issue_schema.py:61`, set `phase_6c_corrosion_ui.py:1092` |
| Element type | `metadata["ifc_type"]` | `phase_6c_corrosion_ui.py:1105` |
| System | `metadata["system"]` | `phase_6c_corrosion_ui.py:1104` |
| Storey | `metadata["floor"]` | `phase_6c_corrosion_ui.py:1103` |
| `material_source` | `metadata["material_source"]`, with `material_confidence`, `environment_source`, `environment_confidence` | `_provenance` `phase_6c_corrosion_ui.py:871-876` |
| Galvanic couple basis | `metadata["galvanic_couple"]` — GC-001 only | `phase_6c_corrosion_ui.py:1114`, `:1127` |

### Two gaps worth stating plainly

1. **A verdict does not carry the element's name.** The name appears only inside
   `title`, as `f"{spec.label} risk on {element.name or element.guid[:8]}"`
   (`phase_6c_corrosion_ui.py:1094`). There is no `element_name` key.
2. **A verdict does not carry the material value.** `_provenance` records
   `material_source` and `material_confidence` — *where* the material came from
   — but not `material_a` itself (`phase_6c_corrosion_ui.py:871-876`). Only some
   data-quality notes carry `material_a_raw` (`:513`, `:521`), and GC-001
   verdicts carry anode/cathode materials inside the engine result.

Both are why this showcase joins findings back to the parsed `ServiceElement`
(`app/modules/ifc_reader/ifc_parser.py:75-105`, fields `guid`, `name`,
`ifc_type`, `material_a`, `material_b`, `system`, `floor`, `material_source`,
`material_confidence`) to show a name and a material next to each finding. Every
such column is labelled in the report as joined from the parse, not read from
the finding.
