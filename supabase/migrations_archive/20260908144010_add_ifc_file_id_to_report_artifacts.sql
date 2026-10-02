-- Migration: Add optional ifc_file_id to report_artifacts
-- Date: 2026-09-08
-- Purpose: BCF/report exports have always been project-scoped only, even
--          though a project can hold several models. This adds a nullable
--          FK into project_ifc_files so a future single-model export can
--          record which model it came from, without touching any existing
--          row (they simply stay NULL).
--
-- Idempotent: safe to re-run.

BEGIN;

ALTER TABLE public.report_artifacts
    ADD COLUMN IF NOT EXISTS ifc_file_id BIGINT NULL
        REFERENCES public.project_ifc_files(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_report_artifacts_ifc_file_id
    ON public.report_artifacts(ifc_file_id);

COMMIT;

-- Verify:
--   SELECT column_name FROM information_schema.columns
--    WHERE table_name = 'report_artifacts' AND column_name = 'ifc_file_id';
