-- Migration: Add ISO 19650 Fields to Documents & Backfill Existing Rows
-- Date: 2026-09-01
-- Purpose: Extend public.documents table with ISO 19650 container naming, suitability,
--          and CDE state fields. Backfill default values on existing project & document rows.

BEGIN;

-- Extend public.documents table
ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS project_code     TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS originator       TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS volume_system    TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS level            TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS type             TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS role             TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS number           TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS suitability_code TEXT NOT NULL DEFAULT 'S0',
    ADD COLUMN IF NOT EXISTS revision_code    TEXT NOT NULL DEFAULT 'P01.01',
    ADD COLUMN IF NOT EXISTS cde_state        TEXT NOT NULL DEFAULT 'WIP' CHECK (cde_state IN ('WIP', 'SHARED', 'PUBLISHED', 'ARCHIVED'));

-- Indexes for ISO documents queries
CREATE INDEX IF NOT EXISTS idx_documents_cde_state ON public.documents(cde_state);
CREATE INDEX IF NOT EXISTS idx_documents_suitability ON public.documents(suitability_code);

-- Backfill existing rows with default values
UPDATE public.projects
SET suitability_code = 'S0'
WHERE COALESCE(suitability_code, '') = '';

UPDATE public.projects
SET revision_code = 'P01.01'
WHERE COALESCE(revision_code, '') = '';

UPDATE public.projects
SET cde_state = 'WIP'
WHERE COALESCE(cde_state, '') = '';

UPDATE public.documents
SET suitability_code = 'S0'
WHERE COALESCE(suitability_code, '') = '';

UPDATE public.documents
SET revision_code = 'P01.01'
WHERE COALESCE(revision_code, '') = '';

UPDATE public.documents
SET cde_state = 'WIP'
WHERE COALESCE(cde_state, '') = '';

COMMENT ON COLUMN public.documents.project_code IS 'ISO 19650 Project Code string';
COMMENT ON COLUMN public.documents.originator IS 'ISO 19650 Originator / Authoring organization code';
COMMENT ON COLUMN public.documents.suitability_code IS 'ISO 19650 Suitability Code (S0-S4, A1-A4, B1-B4)';
COMMENT ON COLUMN public.documents.revision_code IS 'ISO 19650 Revision Code (e.g. P01.01, C01)';
COMMENT ON COLUMN public.documents.cde_state IS 'CDE Workflow State: WIP, SHARED, PUBLISHED, ARCHIVED';

COMMIT;
