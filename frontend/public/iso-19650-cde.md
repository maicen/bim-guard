# ISO 19650 and CDE governance

> Validate ISO 19650 container naming, suitability and revision codes, and enforce CDE state transitions from WIP to SHARED, PUBLISHED and ARCHIVED.

ISO 19650 asks teams to manage information in a Common Data Environment with consistent naming and controlled status changes. BIM Guard enforces both so the rules are applied by the system rather than by memory.

## Container naming and metadata

Project and document names are validated against the field structure `[Project]-[Originator]-[Volume]-[Level]-[Type]-[Role]-[Number]` (UK National Annex).

- Suitability codes: `S0`-`S4` and `A1`-`A4`.
- Revision codes such as `P01.01` and `C01`.

## CDE state machine

Workflow state moves through **WIP**, **SHARED**, **PUBLISHED** and **ARCHIVED**. Transitions are validated by a state machine, and database triggers restrict changes to published models.

## Metadata carried into issues

BCF issue reports are enriched with the ISO 19650 container label, suitability code and revision tag, so coordination issues stay traceable to the exact information container.

## Related

[All features](/features) · [BCF and IDS](/bcf-and-ids) · [Documentation](/docs)

Canonical page: https://bim-guard.xyz/iso-19650-cde
