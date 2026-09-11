-- Migration: Backfill ISO 19650 Defaults for Phase 2
-- Date: 2026-09-11
-- Purpose: 
-- 1. Backfill default CDE state and ISO 19650 versioning fields for existing project_ifc_files.
-- 2. Backfill a default project_naming_config row for any project missing one, ensuring the 
--    strict '-' separator and 'iso19650_national_annex' convention are set.

BEGIN;

-- 1. Backfill project_ifc_files
UPDATE public.project_ifc_files
SET suitability_code = 'S0'
WHERE COALESCE(suitability_code, '') = '';

UPDATE public.project_ifc_files
SET revision_code = 'P01.01'
WHERE COALESCE(revision_code, '') = '';

UPDATE public.project_ifc_files
SET cde_state = 'WIP'
WHERE COALESCE(cde_state, '') = '';

-- 2. Backfill project_naming_config for existing projects
INSERT INTO public.project_naming_config (
    project_id, 
    separator, 
    active_convention, 
    project_code, 
    originator_code
)
SELECT 
    p.id, 
    '-', 
    'iso19650_national_annex', 
    COALESCE(p.project_code, ''), 
    COALESCE(p.originator, '')
FROM public.projects p
WHERE NOT EXISTS (
    SELECT 1 
    FROM public.project_naming_config c 
    WHERE c.project_id = p.id
);

COMMIT;
