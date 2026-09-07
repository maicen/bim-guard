-- BIM-Guard — make public.rules authoritative for the MC-001 band boundaries
-- Audit reference: docs/validation/final-godmode-audit-2026-09-07.md, F1 and A2
-- Written 2026-09-08. Paste the whole file into the Supabase SQL Editor and run
-- it once. Safe to run again: a second run changes nothing.
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
-- expectation is 5 x 3 = 15.
--
-- HOW IT PROTECTS ITSELF. Every step below is inside one DO block, which is one
-- transaction: any RAISE EXCEPTION rolls back the whole repair and leaves the
-- table exactly as it was. The block refuses to run at all unless it finds the
-- 24 rows it expects, and refuses to finish unless it leaves 15 clean ones.
--
-- No threshold value changes. 0.30 rewritten as 0.3 is the same number, in the
-- form json.dumps produces, so a re-seed would write a byte-identical row.
--
-- The application-side fixes ship in commit 377442b: the range parser now reads
-- the en dash the MC-001 payload uses, _coerce_float decodes a JSON-quoted
-- number, the seeder writes check_value as a bare number, and the catalog
-- loaders raise RulesetIncompleteError rather than letting an engine fill a
-- missing boundary from a literal. This file repairs the rows that were written
-- before those fixes existed.


do $$
declare
    v_total    integer;
    v_dirty    integer;
    v_mc_ok    integer;
    v_deleted  integer;
    v_updated  integer;
    v_mc_set   integer := 0;
begin
    -- ── State of the table before anything is touched ────────────────────────
    select count(*) into v_total
    from public.rules
    where reference like '%.BAND.%';

    -- "dirty" = a band row whose check_value is not a bare number: SQL NULL,
    -- the JSON text 'null', or a quoted number.
    select count(*) into v_dirty
    from public.rules
    where reference like '%.BAND.%'
      and (check_value is null or check_value = 'null' or check_value like '"%');

    select count(*) into v_mc_ok
    from public.rules
    where (reference = 'MC-001.BAND.MEDIUM'   and check_value = '0.25')
       or (reference = 'MC-001.BAND.HIGH'     and check_value = '0.5')
       or (reference = 'MC-001.BAND.CRITICAL' and check_value = '0.75');

    -- ── Idempotency: already repaired, so change nothing ─────────────────────
    if v_total = 15 and v_dirty = 0 and v_mc_ok = 3 then
        raise notice 'already applied: 15 clean band rows, MC-001 reads 0.25 / 0.5 / 0.75, nothing changed';
        return;
    end if;

    if v_total <> 24 then
        raise exception
            'expected 24 band rows before the repair, found %. The table is in neither the pre-repair nor the repaired state -- nothing has been changed; inspect it before running this again.',
            v_total;
    end if;

    -- ── 1. Delete the duplicate band rows, keeping the lowest id ─────────────
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

    get diagnostics v_deleted = row_count;
    if v_deleted <> 9 then
        raise exception
            'expected to delete 9 duplicate band rows, deleted %. Rolled back.',
            v_deleted;
    end if;

    -- ── 2. MC-001 Medium and High: the published boundaries, as numbers ──────
    -- 0.25 and 0.50 are the MC-001 ruleset's own values (risk_bands Medium
    -- "0.25 – 0.50", High "0.50 – 0.75"), written the way json.dumps writes
    -- them.
    update public.rules
    set check_value = '0.25',
        updated_at  = now()
    where reference = 'MC-001.BAND.MEDIUM';
    get diagnostics v_updated = row_count;
    v_mc_set := v_mc_set + v_updated;

    update public.rules
    set check_value = '0.5',
        updated_at  = now()
    where reference = 'MC-001.BAND.HIGH';
    get diagnostics v_updated = row_count;
    v_mc_set := v_mc_set + v_updated;

    if v_mc_set <> 2 then
        raise exception
            'expected to set 2 MC-001 boundaries, set %. Rolled back.',
            v_mc_set;
    end if;

    -- ── 3. Unquote every remaining GC/CC/MC band threshold ───────────────────
    update public.rules
    set check_value = (trim(both '"' from check_value))::double precision::text,
        updated_at  = now()
    where reference like '%.BAND.%'
      and check_value like '"%"';

    get diagnostics v_updated = row_count;
    if v_updated <> 7 then
        raise exception
            'expected to unquote 7 band thresholds (GC 3, CC 3, MC critical 1), updated %. Rolled back.',
            v_updated;
    end if;

    -- ── 4. Refuse to commit anything but the intended end state ──────────────
    select count(*) into v_total
    from public.rules
    where reference like '%.BAND.%';

    select count(*) into v_dirty
    from public.rules
    where reference like '%.BAND.%'
      and (check_value is null or check_value = 'null' or check_value like '"%');

    select count(*) into v_mc_ok
    from public.rules
    where (reference = 'MC-001.BAND.MEDIUM'   and check_value = '0.25')
       or (reference = 'MC-001.BAND.HIGH'     and check_value = '0.5')
       or (reference = 'MC-001.BAND.CRITICAL' and check_value = '0.75');

    if v_total <> 15 then
        raise exception 'expected 15 band rows after the repair, found %. Rolled back.', v_total;
    end if;
    if v_dirty <> 0 then
        raise exception 'expected 0 null or quoted band thresholds after the repair, found %. Rolled back.', v_dirty;
    end if;
    if v_mc_ok <> 3 then
        raise exception 'expected MC-001 to read 0.25 / 0.5 / 0.75 after the repair, % of 3 match. Rolled back.', v_mc_ok;
    end if;

    raise notice 'applied: 9 duplicates deleted, MC-001 set to 0.25 / 0.5 / 0.75, 7 thresholds unquoted, 15 clean band rows remain';
end
$$;


-- ── The result ───────────────────────────────────────────────────────────────
-- Expect 15 rows: GC 3, CC 3, MC 3, MM 3, XM 3. No 'null', no quotes, and
-- MC-001 reading 0.25 / 0.5 / 0.75.

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
