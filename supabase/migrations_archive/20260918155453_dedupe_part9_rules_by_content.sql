-- Remove duplicate BUILDING-CODE-PART9 rows left by the ruleset seeder
-- (app/services/ruleset_seeder.py) re-seeding equivalent content under a
-- renamed `reference` string ("OBC 9.x" -> "CODE 9.x"). The prior dedupe
-- migration (20260903100400_dedupe_seeded_rules.sql) partitioned on
-- (ruleset_id, reference, target_ifc_class, property_name), so it could not
-- catch these: same check, different reference text.
--
-- This migration partitions on the actual check content instead --
-- (ruleset_id, target_ifc_class, property_name, operator, check_value,
-- value_min, value_max) -- and keeps the earliest row (lowest id) per group.
-- Confirmed before writing this migration:
--   - 51 rows in BUILDING-CODE-PART9 collapse to 33 distinct checks (18 rows
--     removed here, one group -- IfcWall.FireRating "exists" -- had 4 copies).
--   - No public.rule_extraction_drafts.promoted_rule_id row points at any of
--     the 18 ids being removed (that FK is ON DELETE SET NULL regardless).
--   - No other table holds a foreign key into public.rules.

delete from public.rules r
using (
    select id,
           row_number() over (
               partition by ruleset_id, target_ifc_class, property_name, operator,
                            check_value, value_min, value_max
               order by id
           ) as rn
    from public.rules
    where ruleset_id = 'BUILDING-CODE-PART9'
) dup
where r.id = dup.id
  and dup.rn > 1;
