# Running an Analysis

1. Open a project with an uploaded IFC model.
2. Select **Run Analysis** (or the equivalent action on the project view).
3. Optionally choose a specific ruleset (`rule_folder`) to scope the run.
4. Analysis progresses through stages, shown live via real-time updates:

      **Validation → Parsing → Engine Run → Scoring → Reporting**

5. When finished, results appear under **Reports & BCF Topics** — findings are scored by severity and can be exported (CSV/JSON/BCF).

## Reading results

Each finding shows:

- The rule that was triggered and its severity band (critical / warning / caution / success / info)
- The affected IFC element(s), viewable directly in the 3D viewer
- Suggested mitigations, drawn from the rule's database record

## Next steps

- [Rules Catalog](../rules/rules-catalog.md) — understand what each rule checks
