-- Migration: Add ISO 19650 Naming Fields & CDE State Tracking
-- Date: 2026-09-01
-- Purpose: Extend projects and project_ifc_files tables to support ISO 19650 National Annex
--          naming containers, suitability/revision codes, and CDE state workflow tracking.

BEGIN;

-- Extend public.projects table
ALTER TABLE public.projects
    ADD COLUMN IF NOT EXISTS project_code     TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS originator       TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS volume_system    TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS level            TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS type             TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS role             TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS number           TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS suitability_code TEXT NOT NULL DEFAULT 'S0',
    ADD COLUMN IF NOT EXISTS revision_code    TEXT NOT NULL DEFAULT 'P01.01',
    ADD COLUMN IF NOT EXISTS cde_state        TEXT NOT NULL DEFAULT 'WIP' CHECK (cde_state IN ('WIP', 'SHARED', 'PUBLISHED', 'ARCHIVED')),
    ADD COLUMN IF NOT EXISTS cde_approved_by  TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS cde_approved_at  TIMESTAMP WITH TIME ZONE NULL;

-- Extend public.project_ifc_files table
ALTER TABLE public.project_ifc_files
    ADD COLUMN IF NOT EXISTS project_code     TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS originator       TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS volume_system    TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS level            TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS type             TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS role             TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS number           TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS suitability_code TEXT NOT NULL DEFAULT 'S0',
    ADD COLUMN IF NOT EXISTS revision_code    TEXT NOT NULL DEFAULT 'P01.01',
    ADD COLUMN IF NOT EXISTS cde_state        TEXT NOT NULL DEFAULT 'WIP' CHECK (cde_state IN ('WIP', 'SHARED', 'PUBLISHED', 'ARCHIVED')),
    ADD COLUMN IF NOT EXISTS cde_approved_by  TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS cde_approved_at  TIMESTAMP WITH TIME ZONE NULL;

-- Create Indexes for CDE State and ISO Naming queries
CREATE INDEX IF NOT EXISTS idx_projects_cde_state ON public.projects(cde_state);
CREATE INDEX IF NOT EXISTS idx_project_ifc_files_cde_state ON public.project_ifc_files(cde_state);
CREATE INDEX IF NOT EXISTS idx_projects_suitability_revision ON public.projects(suitability_code, revision_code);

-- RLS Enforcement: Mutation Guard Trigger function to prevent modification of PUBLISHED or ARCHIVED rows
CREATE OR REPLACE FUNCTION public.prevent_published_cde_mutation()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.cde_state IN ('PUBLISHED', 'ARCHIVED') THEN
        -- Allow state transition from PUBLISHED/ARCHIVED if explicitly archiving or updating state,
        -- but block payload/attribute mutations on finalized records.
        IF NEW.cde_state = OLD.cde_state AND (
            NEW.name IS DISTINCT FROM OLD.name OR
            NEW.ifc_file_path IS DISTINCT FROM OLD.ifc_file_path OR
            NEW.revision_code IS DISTINCT FROM OLD.revision_code
        ) THEN
            RAISE EXCEPTION 'Cannot modify % project record in state %', OLD.id, OLD.cde_state;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_projects_cde_guard ON public.projects;
CREATE TRIGGER trg_projects_cde_guard
    BEFORE UPDATE ON public.projects
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_published_cde_mutation();

COMMENT ON COLUMN public.projects.project_code IS 'ISO 19650 Project Code string';
COMMENT ON COLUMN public.projects.originator IS 'ISO 19650 Originator / Authoring organization code';
COMMENT ON COLUMN public.projects.volume_system IS 'ISO 19650 Volume / Spatial system identifier';
COMMENT ON COLUMN public.projects.level IS 'ISO 19650 Level / Location breakdown';
COMMENT ON COLUMN public.projects.type IS 'ISO 19650 Type designation (e.g. M3, DR, RP)';
COMMENT ON COLUMN public.projects.role IS 'ISO 19650 Discipline role code (e.g. A, S, M)';
COMMENT ON COLUMN public.projects.number IS 'ISO 19650 Sequential document number';
COMMENT ON COLUMN public.projects.suitability_code IS 'ISO 19650 Suitability Code (S0-S4, A1-A4, B1-B4)';
COMMENT ON COLUMN public.projects.revision_code IS 'ISO 19650 Revision Code (e.g. P01.01, C01)';
COMMENT ON COLUMN public.projects.cde_state IS 'CDE Workflow State: WIP, SHARED, PUBLISHED, ARCHIVED';

COMMIT;
