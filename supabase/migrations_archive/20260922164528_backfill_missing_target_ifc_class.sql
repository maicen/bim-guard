-- Backfill target_ifc_class for rules that were promoted with it blank.
--
-- RuleDraftService.promote_draft() (app/services/rule_draft_service.py) built
-- its RuleService.create_rule() call from every field on the accepted draft's
-- proposed_rule EXCEPT target_ifc_class, so it was silently dropped on every
-- rule ever promoted through the extraction-review workflow: create_rule()'s
-- default of '' was written instead of the LLM's actual answer. Fixed in the
-- application code in the same change as this migration.
--
-- A rule with target_ifc_class = '' can never match an IFC element (the
-- compliance engine and the frontend's per-category cards both filter
-- strictly on that field), so every affected rule was silently inert --
-- present in its ruleset, never evaluated. Surfaced by ruleset
-- EXTRACTED-20260920-044830 ("Doors - Synthetic IFC Test Rule Pack", 30
-- rules, source_document_id 1163): the whole pack showed "No applicable
-- checks found" for Doors despite containing well-formed checks (e.g.
-- DR-012: IfcDoor.OverallWidth >= 800mm).
--
-- Values below are not guesses: for every row except 7448, they are the
-- target_ifc_class the LLM actually extracted, read back from the matching
-- rule_extraction_drafts.proposed_rule (the value promote_draft() had but
-- didn't write) -- so this migration restores exactly what should have been
-- written the first time, not a new judgment call. Rule 7448 has no matching
-- draft row (pre-dates draft tracking); it is an unreferenced duplicate of
-- 7449 (same reference "REQ-AI-private-stair-max-rise", same
-- property_name=RiserHeight, empty ruleset_id) and is set to the same
-- IfcStairFlight for consistency.
--
-- Each UPDATE is guarded on target_ifc_class = '' so re-running this
-- migration is a no-op once applied, and it never overwrites a value set by
-- hand since.

UPDATE public.rules AS r
SET target_ifc_class = v.target_ifc_class,
    updated_at = NOW()::text
FROM (VALUES
    (7448, 'IfcStairFlight'),  -- REQ-AI-private-stair-max-rise, dup of 7449, no draft row
    (7449, 'IfcStairFlight'),  -- REQ-AI-private-stair-max-rise
    (9068, 'IfcDoor'),  -- DR-001
    (9069, 'IfcDoor'),  -- DR-002
    (9070, 'IfcDoor'),  -- DR-003
    (9071, 'IfcDoor'),  -- DR-004
    (9072, 'IfcDoor'),  -- DR-005
    (9073, 'IfcBuildingStorey'),  -- DR-006
    (9074, 'IfcDoor'),  -- DR-007
    (9075, 'IfcDoor'),  -- DR-008
    (9076, 'IfcOpeningElement'),  -- DR-009
    (9077, 'IfcOpeningElement'),  -- DR-010
    (9078, 'IfcDoor'),  -- DR-011
    (9079, 'IfcDoor'),  -- DR-012
    (9080, 'IfcDoor'),  -- DR-013
    (9081, 'IfcDoor'),  -- DR-014
    (9082, 'IfcDoor'),  -- DR-015
    (9083, 'IfcDoor'),  -- DR-016
    (9084, 'IfcDoor'),  -- DR-017
    (9085, 'IfcDoor'),  -- DR-018
    (9086, 'IfcDoorType'),  -- DR-019
    (9087, 'IfcDoor'),  -- DR-020
    (9088, 'IfcDoor'),  -- DR-021
    (9089, 'IfcDoor'),  -- DR-022
    (9090, 'IfcDoorType'),  -- DR-023
    (9091, 'IfcDoor'),  -- DR-024
    (9092, 'IfcDoor'),  -- DR-025
    (9093, 'IfcDoor'),  -- DR-026
    (9094, 'IfcDoor'),  -- DR-027
    (9095, 'IfcDoor'),  -- DR-028
    (9096, 'IfcDoor'),  -- DR-029
    (9097, 'IfcDoor')  -- DR-030
) AS v(id, target_ifc_class)
WHERE r.id = v.id
  AND r.target_ifc_class = '';
