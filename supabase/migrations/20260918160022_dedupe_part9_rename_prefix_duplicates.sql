-- Follow-up to 20260918155453_dedupe_part9_rules_by_content.sql.
--
-- That migration's dedupe key (content only, no reference) was too broad:
-- it collapsed 9.8.2.1.(2) and 9.8.2.1.(4) -- two genuinely distinct Part 9
-- sub-clauses that happen to both require an 860mm stair width -- into one
-- row. app/services/ruleset_seeder.py's own idempotent seeder (correctly,
-- from its perspective) re-created rows for references it no longer found,
-- during an unrelated local test run, which is how this was caught.
--
-- The correct identity for "same rule, cited under a renamed reference
-- prefix" needs the reference too, normalized to ignore only the known
-- "OBC " / "CODE " prefix rename (see _normalize_reference in
-- ruleset_seeder.py, fixed alongside this migration so the seeder no longer
-- re-creates these). Keeps the earliest row (lowest id) per group.
--
-- Verified before writing this migration (see conversation): exactly 10 of
-- the 12 remaining content-duplicate groups are true prefix-renamed
-- duplicates (same clause number); the other 2 groups are legitimately
-- distinct clauses and are left untouched by this WHERE/partition.
-- No FK references into public.rules point at any of the removed rows
-- (rule_extraction_drafts.promoted_rule_id is ON DELETE SET NULL regardless;
-- confirmed no draft rows reference these ids).

delete from public.rules r
using (
    select id,
           row_number() over (
               partition by ruleset_id, target_ifc_class, property_name, operator,
                            check_value, value_min, value_max,
                            regexp_replace(reference, '^(OBC|CODE)\s+', '', 'i')
               order by id
           ) as rn
    from public.rules
    where ruleset_id = 'BUILDING-CODE-PART9'
) dup
where r.id = dup.id
  and dup.rn > 1;
