# BIM Guard features

> Automated architectural code compliance for IFC models, ISO 19650 CDE governance, BCF issue coordination, IDS validation and bSDD classification.

BIM Guard is an OpenBIM compliance platform. Upload IFC models and regulatory documents, extract rules, run audits and route the findings as BCF issues, with every step tracked under ISO 19650.

## Architectural code compliance

Compliance engines read the IFC model directly and evaluate it against rules stored in the database, so thresholds are data, not hardcoded constants.

- **Means of egress** - topological graph traversal from habitable spaces to exterior exits, checking travel distance and exit-count thresholds.
- **Daylight** - window glazing area against room floor area, checked against configurable ratio thresholds.

## Rules from your own standards

Upload PDF building codes and standards. They are parsed with structured layout analysis, rules are extracted with an LLM, and each rule is reviewed and grounded against its source clause before it joins your rule catalog.

## ISO 19650 and CDE governance

Validate container naming and metadata, and guard workflow state transitions (WIP, SHARED, PUBLISHED, ARCHIVED).

Read more: [ISO 19650 and CDE governance](/iso-19650-cde).

## BCF, IDS and bSDD

Findings export as BCF issues. Information requirements can be checked against buildingSMART IDS specifications, and classifications are validated against the buildingSMART Data Dictionary.

Read more: [BCF issue management and IDS validation](/bcf-and-ids).

## Live progress and reporting

Audits stream stage-by-stage progress in real time, and results are available as reports and exports for your team.

Accuracy claims are scored independently and published with their limits: [validation and research](/research).

Canonical page: https://bim-guard.xyz/features
