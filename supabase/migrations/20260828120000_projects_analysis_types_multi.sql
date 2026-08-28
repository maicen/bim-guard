-- Migration: projects.analysis_type (TEXT) -> projects.analysis_types (TEXT[])
-- Date: 2026-08-28
-- Purpose: a project can be checked by more than one analysis. The single-value
--          column could only ever name one, so a project needing both corrosion
--          and seismic had to be created twice.
--
-- Supersedes the analysis_type half of 20260827001000_add_country_analysis_type.sql.
-- The country column that migration added is untouched here.
--
-- Idempotent: safe to re-run. Wrapped in a transaction so a failure rolls back
-- cleanly rather than leaving the schema half-migrated.

BEGIN;

-- 1. New column, empty by default. Backfilled below, so no data default that
--    would silently give an untouched row a type it was never assigned.
ALTER TABLE public.projects
    ADD COLUMN IF NOT EXISTS analysis_types TEXT[] NOT NULL DEFAULT '{}';

-- 2. Carry every existing value across as a single-element array. Guarded on the
--    old column still existing so a re-run after step 5 is a no-op rather than
--    an error.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'projects'
          AND column_name = 'analysis_type'
    ) THEN
        UPDATE public.projects
           SET analysis_types = ARRAY[analysis_type]
         WHERE analysis_types = '{}'
           AND analysis_type IS NOT NULL
           AND analysis_type <> '';
    END IF;
END $$;

-- 3. Every element must be a recognised type, and the list must not be empty.
--    Mirrors app.constants.ANALYSIS_TYPES; the two are expected to agree, and
--    this constraint is what catches it when they do not.
--    ADD CONSTRAINT has no IF NOT EXISTS, so guard it.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'valid_analysis_types'
          AND conrelid = 'public.projects'::regclass
    ) THEN
        ALTER TABLE public.projects
            ADD CONSTRAINT valid_analysis_types
            CHECK (
                array_length(analysis_types, 1) >= 1
                AND analysis_types <@ ARRAY['Piping (Corrosive)', 'Halo', 'Architecture']::TEXT[]
            );
    END IF;
END $$;

-- 4. GIN, not btree: queries against an array column ask "does it contain X",
--    which a btree index on the whole array cannot answer.
DROP INDEX IF EXISTS public.idx_projects_analysis_type;
CREATE INDEX IF NOT EXISTS idx_projects_analysis_types
    ON public.projects USING GIN (analysis_types);

-- 5. Retire the single-value column and the constraint that policed it. Done
--    last so every step above can still read it.
ALTER TABLE public.projects DROP CONSTRAINT IF EXISTS valid_analysis_type;
ALTER TABLE public.projects DROP COLUMN IF EXISTS analysis_type;

COMMENT ON COLUMN public.projects.analysis_types IS
    'Analyses this project is checked by, one or more of: Piping (Corrosive) '
    '[GC-001+CC-001+MC-001], Halo [Blue Halo bracing], Architecture. '
    'Order is meaningful: the first element is the project''s primary analysis '
    'and is where project setup redirects after creation.';

COMMIT;

-- Verify:
--   SELECT column_name, data_type
--     FROM information_schema.columns
--    WHERE table_schema = 'public' AND table_name = 'projects'
--      AND column_name LIKE 'analysis_type%';
--   -- expect exactly one row: analysis_types | ARRAY
--
--   SELECT id, analysis_types FROM public.projects ORDER BY id LIMIT 10;
--   -- expect every row to carry at least one recognised value
