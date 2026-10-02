-- Migration: Add optional ifc_file_id to model_enhancement_lineage
-- Date: 2026-09-08
-- Purpose: Enhancement lineage has always been project-scoped only, with no
--          way to say which of a project's several attached models a version
--          came from. This adds a nullable FK into project_ifc_files so
--          future enhancement runs can record that, without touching any
--          existing row (they simply stay NULL) or the table's append-only
--          guarantees (only INSERT is granted on this table; this migration
--          changes schema, not grants).
--
-- Idempotent: safe to re-run.

BEGIN;

ALTER TABLE public.model_enhancement_lineage
    ADD COLUMN IF NOT EXISTS ifc_file_id BIGINT NULL
        REFERENCES public.project_ifc_files(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_model_enhancement_lineage_ifc_file_id
    ON public.model_enhancement_lineage(ifc_file_id);

COMMIT;

-- Verify:
--   SELECT column_name FROM information_schema.columns
--    WHERE table_name = 'model_enhancement_lineage' AND column_name = 'ifc_file_id';
