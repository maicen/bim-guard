-- Remove duplicate rows accumulated by the ruleset seeder before it was made
-- idempotent (app/services/ruleset_seeder.py). Every application boot that ran
-- the pre-fix seeder re-inserted the GC-001/CC-001/MC-001 risk-band rows and
-- the BUILDING-CODE-PART9 / BIMGUARD-WINDOW-DATA rows because they lacked an
-- existence check, leaving up to ~159 copies of the same logical rule.
--
-- Keeps the earliest row (lowest id) per (ruleset_id, reference,
-- target_ifc_class, property_name) and deletes the rest. No FK references
-- into public.rules point at any of the deleted rows (verified against
-- rule_extraction_drafts.promoted_rule_id before writing this migration).

delete from public.rules r
using (
    select id,
           row_number() over (
               partition by ruleset_id, reference, target_ifc_class, property_name
               order by id
           ) as rn
    from public.rules
) dup
where r.id = dup.id
  and dup.rn > 1;
