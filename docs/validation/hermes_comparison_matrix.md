> **⚠ AI-GENERATED — UNVERIFIED — DO NOT CITE.**
>
> This matrix was produced by "Hermes", an AI-assisted standards research pass, from
> `docs/validation/data/hermes_standards_research_summary.json`. No value below
> carries a quotation, a page reference or a verified clause, and none was checked
> against the standards named. Known defects: the research cited EN 1998-1 and
> DIN 4149 editions that do not exist; neither EN 1998-1 nor the German National
> Annex gives MEP brace spacing, clearance, pipe thresholds or brace angles, so the
> per-standard EU values are unsourced; no component importance factor of 1.6
> exists; and the NFPA 13 and ASCE 7-22 columns have the same unverified shape.
>
> Retained as historical evidence of how SB-001's earlier configuration was
> produced. The corrected ruleset is `data/rulesets/sb001_seismic_clearance.json`;
> see `docs/planning/sb001_provenance_2026-09-13.md`.

| Parameter               | EN 1998-1       | DIN 4149        | NFPA 13         | ASCE 7-22       |
|-------------------------|----------------|-----------------|-----------------|-----------------|
| **Restraint Spacing**   | 1.0 m (trans)  | 1.2 m (trans)   | 40 in (trans)   | 48 in (trans)   |
|                         | 1.5 m (long)   | 1.8 m (long)    | 60 in (long)    | 72 in (long)    |
| **Clearance from Structure** | 150 mm       | 200 mm          | 12 in           | 18 in           |
| **Pipe Threshold**      | 63 mm          | 75 mm           | 2.5 in          | [DATA GAP]      |
| **Duct Threshold**      | [DATA GAP]     | [DATA GAP]      | [DATA GAP]      | 8 in            |
| **Importance Factors**  | 1.0 (standard) | 1.6 (hospitals) | 1.5 (hospitals) | 1.5 (hospitals) |
| **Brace Types Allowed** | Diagonal, MRF  | Diagonal, Cross | Diagonal, Cross | Diagonal, Cross |

**Consensus Rules**: All standards require diagonal bracing for seismic restraint. Minimum clearance from structure is 150 mm (EU) vs 12 in (US), with DIN 4149 being most restrictive.

**Conflicts**: NFPA 13 and ASCE 7-22 specify pipe thresholds (2.5 in, 2.5 in) while EN 1998-1 and DIN 4149 omit this parameter. Duct thresholds are only specified in ASCE 7-22 (8 in).