-- Migration: Add IFC-derived summary metadata to public.project_ifc_files
-- Date: 2026-09-08
-- Purpose: The Models table only ever showed upload bookkeeping (file name,
--          role, upload date) -- nothing read from the IFC file's own
--          content. These columns hold cheap header/type-count reads
--          (schema version, authoring application, storey/element counts, a
--          discipline breakdown) taken once at attach time, so the table can
--          show them without re-opening the model on every page load.
--
-- Idempotent: safe to re-run.

BEGIN;

ALTER TABLE public.project_ifc_files
    ADD COLUMN IF NOT EXISTS ifc_schema             TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS authoring_application  TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS storey_count            INTEGER NULL,
    ADD COLUMN IF NOT EXISTS element_count           INTEGER NULL,
    ADD COLUMN IF NOT EXISTS discipline_summary      JSONB NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN public.project_ifc_files.ifc_schema IS
    'IFC schema version read from the model header, e.g. IFC4, IFC2X3; blank if extraction failed';
COMMENT ON COLUMN public.project_ifc_files.authoring_application IS
    'IfcApplication.ApplicationFullName + Version from the model that produced this file; blank if absent or unreadable';
COMMENT ON COLUMN public.project_ifc_files.storey_count IS
    'Count of IfcBuildingStorey entities; NULL if extraction failed rather than the model genuinely having none';
COMMENT ON COLUMN public.project_ifc_files.element_count IS
    'Count of IfcElement occurrences; NULL if extraction failed rather than the model genuinely having none';
COMMENT ON COLUMN public.project_ifc_files.discipline_summary IS
    'Heuristic element-count breakdown by discipline (architectural/structural/mep/other), keyed by category name';

COMMIT;

-- Verify:
--   SELECT column_name, data_type
--     FROM information_schema.columns
--    WHERE table_schema='public' AND table_name='project_ifc_files'
--    ORDER BY ordinal_position;
