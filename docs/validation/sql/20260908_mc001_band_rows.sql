-- BIM-Guard — make public.rules authoritative for the MC-001 band boundaries
-- Audit reference: docs/validation/final-godmode-audit-2026-09-07.md, F1 and A2
-- Written 2026-09-08. Run the four steps IN ORDER in the Supabase SQL Editor.
--
-- WHAT IS WRONG WITH THE ROWS TODAY
--
--   * MC-001.BAND.MEDIUM and MC-001.BAND.HIGH hold the JSON text 'null'. Their
--     published boundaries (0.25 and 0.50) reached the MIC engine only as
--     literals inside app/engines/bimguard_mic_engine.py, so editing them here
--     changed nothing.
--   * Every GC-001, CC-001 and MC-001 band row holds a JSON-QUOTED number --
--     the seven characters "0.85", quotes included -- because the seeder passed
--     a string and rules.check_value is stored JSON-encoded. MM-001 and XM-001
--     store bare numbers and are correct already.
--   * The GC/CC/MC band rows exist twice: ids 228-236 seeded 2026-08-06, and
--     ids 7117-7125 seeded 2026-09-06 after migration 20260903100400 had
--     deduplicated the table. Keep the lower id of each pair.
--
-- COUNTS. The audit's F1 text says "18 expected" but enumerates GC 6 + CC 6 +
-- MC 6 + MM 3 + XM 3, which is the 24 rows it measured, not the expectation.
-- Five engines band a composite score, three boundaries each (Medium, High,
-- Critical -- Low has no lower bound of its own and is never seeded), so the
-- expectation is 5 x 3 = 15. Step 1 should show 24 rows and step 4 should show
-- 15.
--
-- The application-side fixes ship in the same commit as this file: the range
-- parser now reads the en dash the MC-001 payload uses, _coerce_float decodes a
-- JSON-quoted number, the seeder writes check_value as a bare number, and the
-- catalog loaders raise RulesetIncompleteError rather than letting an engine
-- fill a missing boundary from a literal. This file repairs the rows that were
-- written before those fixes existed.


-- ── 1. BEFORE ────────────────────────────────────────────────────────────────
-- Expect 24 rows: GC 6, CC 6, MC 6, MM 3, XM 3.
-- Expect MC-001.BAND.MEDIUM and .HIGH to read 'null', and every GC/CC/MC row
-- to be quoted.

select id,
       ruleset_id,
       reference,
       check_value,
       keyword,
       category,
       created_at
from public.rules
where reference like '%.BAND.%'
order by reference, id;


-- ── 2. DELETE the duplicate band rows, keeping the lowest id per reference ───
-- Expect 9 rows deleted (ids 7117-7125).

delete from public.rules r
using (
    select id,
           row_number() over (
               partition by ruleset_id, reference
               order by id
           ) as rn
    from public.rules
    where reference like '%.BAND.%'
) dup
where r.id = dup.id
  and dup.rn > 1;


-- ── 3a. MC-001 Medium and High: the published boundaries, as numbers ─────────
-- 0.25 and 0.50 are the MC-001 ruleset's own values (risk_bands Medium
-- "0.25 – 0.50", High "0.50 – 0.75"). Written the way json.dumps writes them,
-- so a re-seed would produce byte-identical rows. Expect 2 rows updated.

update public.rules
set check_value = '0.25',
    updated_at  = now()
where reference = 'MC-001.BAND.MEDIUM';

update public.rules
set check_value = '0.5',
    updated_at  = now()
where reference = 'MC-001.BAND.HIGH';


-- ── 3b. Unquote every remaining GC/CC/MC band threshold ──────────────────────
-- Strips the JSON quotes and normalises the text to what json.dumps(float)
-- produces. No value changes: '"0.80"' becomes '0.8', the same number.
-- Expect 7 rows updated (GC 3, CC 3, MC critical 1).

update public.rules
set check_value = (trim(both '"' from check_value))::double precision::text,
    updated_at  = now()
where reference like '%.BAND.%'
  and check_value like '"%"';


-- ── 4. AFTER ─────────────────────────────────────────────────────────────────
-- Expect 15 rows: GC 3, CC 3, MC 3, MM 3, XM 3.
-- Expect no 'null', no quotes, and MC-001 reading 0.25 / 0.5 / 0.75.

select id,
       ruleset_id,
       reference,
       check_value,
       keyword,
       category,
       created_at
from public.rules
where reference like '%.BAND.%'
order by reference, id;

-- One-line verification of the same thing. Expect: total 15, nulls 0, quoted 0.
select count(*)                                             as total,
       count(*) filter (where check_value is null
                           or check_value = 'null')         as nulls,
       count(*) filter (where check_value like '"%')        as quoted
from public.rules
where reference like '%.BAND.%';
