-- Migration: Add the wizard's building-code choice to public.projects
-- Date: 2026-08-30
-- Purpose: The setup wizard moved the building code out of step 1 (where it sat
--          beside the jurisdiction as an unselectable label) into step 3, where
--          it is a real choice filtered by the project's jurisdiction. The
--          answer needs a column to land in.
--
-- Nullable on purpose, and deliberately without a foreign key or an enum check:
--   * A corrosion (Piping) project is judged against material and media rules,
--     not a jurisdiction's code, so having no building code is a valid answer
--     rather than a missing one.
--   * The catalog of codes lives in app.constants.BUILDING_CODES and grows as
--     jurisdictions are added; a CHECK constraint here would have to be
--     migrated in lockstep with a Python list, and the service already rejects
--     an unknown ID before the insert reaches Postgres.
--
-- Idempotent: safe to re-run. Wrapped in a transaction so a failure rolls back
-- cleanly rather than leaving the table half-migrated.

BEGIN;

ALTER TABLE public.projects
    ADD COLUMN IF NOT EXISTS building_code TEXT;

COMMENT ON COLUMN public.projects.building_code IS
    'Building code chosen in wizard step 3; an id from app.constants.BUILDING_CODES, '
    'or NULL where the analysis domain does not need one (e.g. Piping corrosion)';

COMMIT;
