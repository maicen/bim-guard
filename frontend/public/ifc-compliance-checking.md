# Automated IFC compliance checking

> Check IFC models against architectural building-code rules automatically: egress travel distance, exit counts and daylight ratios, with results as BCF issues.

Manual code review of a building model is slow and hard to repeat. BIM Guard reads your IFC file, applies rules from a managed catalog and reports each finding against the element that caused it.

## How an audit works

- **Create a project** and attach an IFC model (IFC2X3, IFC4 or IFC4.3).
- **Choose a ruleset** - an existing catalog or one extracted from your own code document.
- **Run the audit.** Progress streams live while the model is validated, parsed, checked and scored.
- **Review findings** in the report and 3D viewer, then export them as BCF issues.

## What gets checked

- **Egress** - the shortest path from each habitable space to an exterior exit is computed over the building's space-boundary graph, then compared with travel-distance and exit-count limits from the active ruleset.
- **Daylight** - glazing area relative to room floor area, compared with the ruleset's ratio threshold.

Thresholds come from the rule database, so switching jurisdiction or code edition means switching ruleset, not changing code.

## Model quality gate

Before analysis, an IFC pre-flight service checks STEP syntax, schema compatibility and core buildingSMART rules such as a single project root, valid 22-character GUIDs, spatial containment and material association.

## Related

[All features](/features) · [BCF and IDS](/bcf-and-ids) · [Documentation](/docs)

## Frequently asked questions

### Which IFC schema versions can BIM Guard check?

IFC2X3, IFC4 and IFC4.3 models can be attached to a project.

### How is egress travel distance calculated?

The shortest path from each habitable space to an exterior exit is computed over the building's space-boundary graph, then compared with the travel-distance and exit-count limits from the active ruleset.

### What is checked before an audit runs?

An IFC pre-flight service checks STEP syntax, schema compatibility and core buildingSMART rules such as a single project root, valid 22-character GUIDs, spatial containment and material association.

### How do I apply a different jurisdiction or code edition?

Switch the ruleset. Thresholds come from the rule database, so no code change is needed.

Canonical page: https://bim-guard.xyz/ifc-compliance-checking
