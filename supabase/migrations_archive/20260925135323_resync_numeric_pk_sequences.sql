-- Resync every integer/bigint identity sequence in the public schema to the
-- true max(id) of its owning table.
--
-- SupabaseTableAdapter.insert() (app/services/db_adapters.py) falls back to
-- a manual "SELECT max(id) + 1" insert whenever the identity sequence
-- produces a value that collides with an existing row (Postgres 23505). That
-- fallback never advances the sequence itself, so once a sequence drifts
-- behind max(id) -- e.g. from an earlier bulk import or explicit-PK insert
-- -- every subsequent identity-column insert keeps colliding and keeps
-- falling back, and concurrent requests hitting the fallback at the same
-- time can compute the same "next" id and collide with each other. This was
-- the proximate cause of duplicate "Residence X" project rows (ids 4945 and
-- 4946) being created from a single wizard submission after the attach-model
-- step 404'd on the first row.
--
-- This migration only calls setval(); it does not modify any table data.
DO $$
DECLARE
    rec RECORD;
    cur_max BIGINT;
BEGIN
    FOR rec IN
        SELECT
            c.oid::regclass::text AS table_name,
            a.attname AS column_name,
            pg_get_serial_sequence(c.oid::regclass::text, a.attname) AS seq_name
        FROM pg_class c
        JOIN pg_attribute a ON a.attrelid = c.oid
        WHERE c.relkind = 'r'
          AND c.relnamespace = 'public'::regnamespace
          AND a.attnum > 0
          AND NOT a.attisdropped
          AND pg_get_serial_sequence(c.oid::regclass::text, a.attname) IS NOT NULL
    LOOP
        EXECUTE format('SELECT COALESCE(MAX(%I), 0) FROM %s', rec.column_name, rec.table_name)
            INTO cur_max;

        IF cur_max > 0 THEN
            PERFORM setval(rec.seq_name, cur_max, true);
        END IF;
    END LOOP;
END $$;
