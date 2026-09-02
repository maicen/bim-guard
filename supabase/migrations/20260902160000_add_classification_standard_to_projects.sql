-- Migration: Add a bSDD classification standard choice to public.projects
-- Date: 2026-09-02
-- Purpose: Project settings can now select the classification standard (e.g.
--          Uniclass 2015, OmniClass 2020, or the IFC 4.3 dictionary itself)
--          a project's elements and properties are coded against, resolved
--          against the buildingSMART Data Dictionary (bSDD) via
--          app/services/bsdd_client.py and GET /api/bsdd/dictionaries.
--
-- Nullable/free-text on purpose: the dictionary catalog is served live from
-- bSDD (with an offline fallback catalog), not enumerated in Postgres, so a
-- CHECK constraint here would have to track that external catalog. The value
-- stored is a bSDD dictionary `code` (e.g. "uniclass_2015").
--
-- Idempotent: safe to re-run. Wrapped in a transaction so a failure rolls back
-- cleanly rather than leaving the table half-migrated.

BEGIN;

ALTER TABLE public.projects
    ADD COLUMN IF NOT EXISTS classification_standard TEXT;

COMMENT ON COLUMN public.projects.classification_standard IS
    'bSDD dictionary code (e.g. uniclass_2015, omniclass_2020, ifc_4.3) this '
    'project is classified against; NULL when no standard has been chosen yet';

COMMIT;
