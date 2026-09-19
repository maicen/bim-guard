-- Same rename-prefix duplication as BUILDING-CODE-PART9 (see
-- 20260918160022_dedupe_part9_rename_prefix_duplicates.sql), found in the
-- sibling BUILDING-CODE-PART9-EXT ruleset: 5 clauses seeded twice, once
-- under an "OBC ..." reference and once under a "CODE ..." reference for
-- the identical check. Verified before writing this migration: all 5
-- pairs have byte-identical descriptions, differing only in the reference
-- prefix -- no legitimately-distinct clauses in this ruleset collide on
-- content the way 9.8.2.1.(2)/(4) did in BUILDING-CODE-PART9.

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
    where ruleset_id = 'BUILDING-CODE-PART9-EXT'
) dup
where r.id = dup.id
  and dup.rn > 1;
