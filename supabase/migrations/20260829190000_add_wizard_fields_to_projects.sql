-- Migration: Add the project setup wizard's step-1 fields to public.projects
-- Date: 2026-08-29
-- Purpose: Restore the four descriptive fields the wizard collected before the
--          FastHTML layer was removed in a48a4f1. The Svelte wizard asks for
--          them again; without these columns the answers have nowhere to go.
--
-- Nullable on purpose. Projects created through the plain API, and every row
-- that predates this migration, legitimately have no opinion about building
-- type or floor count, and a NOT NULL default would invent one for them.
--
-- Counts are INTEGER rather than SMALLINT to match buildings/floors elsewhere
-- in the schema, and area is NUMERIC rather than a float so that a gross floor
-- area entered as 5000.5 comes back as 5000.5 rather than 5000.499999.
--
-- Idempotent: safe to re-run. Wrapped in a transaction so a failure rolls back
-- cleanly rather than leaving the table half-migrated.

BEGIN;

ALTER TABLE public.projects
    ADD COLUMN IF NOT EXISTS project_type      TEXT,
    ADD COLUMN IF NOT EXISTS project_size_sqm  NUMERIC,
    ADD COLUMN IF NOT EXISTS buildings_count   INTEGER,
    ADD COLUMN IF NOT EXISTS floors_count      INTEGER;

-- Guard against negatives without rejecting NULL: a project may legitimately
-- not say how many floors it has, but it may never say minus two.
ALTER TABLE public.projects
    DROP CONSTRAINT IF EXISTS projects_wizard_counts_non_negative;
ALTER TABLE public.projects
    ADD CONSTRAINT projects_wizard_counts_non_negative CHECK (
        (project_size_sqm IS NULL OR project_size_sqm >= 0)
        AND (buildings_count IS NULL OR buildings_count >= 0)
        AND (floors_count   IS NULL OR floors_count   >= 0)
    );

COMMENT ON COLUMN public.projects.project_type IS
    'Building type chosen in wizard step 1; one of app.constants.PROJECT_TYPES';
COMMENT ON COLUMN public.projects.project_size_sqm IS
    'Gross floor area in square metres, as entered in wizard step 1';
COMMENT ON COLUMN public.projects.buildings_count IS
    'Number of buildings in the project';
COMMENT ON COLUMN public.projects.floors_count IS
    'Number of floors in the project';

COMMIT;
