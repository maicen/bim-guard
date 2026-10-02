-- Migration: Add country and analysis_type columns to public.projects
-- Date: 2026-08-26
-- Purpose: Enable jurisdiction-aware compliance and analysis type routing
--
-- Idempotent: safe to re-run. Wrapped in a transaction so a failure rolls back
-- cleanly rather than leaving the schema half-migrated.

BEGIN;

ALTER TABLE public.projects
    ADD COLUMN IF NOT EXISTS country TEXT NOT NULL DEFAULT 'UK',
    ADD COLUMN IF NOT EXISTS analysis_type TEXT NOT NULL DEFAULT 'Piping (Corrosive)';

-- Valid analysis types. ADD CONSTRAINT has no IF NOT EXISTS, so guard it.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'valid_analysis_type'
          AND conrelid = 'public.projects'::regclass
    ) THEN
        ALTER TABLE public.projects
            ADD CONSTRAINT valid_analysis_type
            CHECK (analysis_type IN ('Piping (Corrosive)', 'Halo', 'Architecture'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_projects_analysis_type ON public.projects(analysis_type);
CREATE INDEX IF NOT EXISTS idx_projects_country       ON public.projects(country);

COMMENT ON COLUMN public.projects.country IS
    'Country/jurisdiction for project (affects applicable standards and building codes)';
COMMENT ON COLUMN public.projects.analysis_type IS
    'Analysis type: Piping (Corrosive) [GC-001+CC-001], Halo [Blue Halo], or Architecture [future]';

COMMIT;

-- Verify:
--   SELECT column_name, data_type, is_nullable, column_default
--     FROM information_schema.columns
--    WHERE table_schema = 'public' AND table_name = 'projects'
--      AND column_name IN ('country', 'analysis_type');
