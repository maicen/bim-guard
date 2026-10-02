-- Migration: Extend Published/Archived Immutability Guard to documents and project_ifc_files
-- Purpose: public.prevent_published_cde_mutation() (added by
--          20260902144333_add_iso19650_cde_schema.sql) only guards
--          public.projects, even though public.documents and
--          public.project_ifc_files carry the same cde_state column and are
--          just as subject to ISO 19650-2 FR-02.4 (published-state
--          immutability). Both tables can currently be mutated post-publication.
--
-- The original function's column list (name, ifc_file_path, revision_code)
-- is specific to public.projects' schema and does not apply to documents or
-- project_ifc_files (different column names). Rather than duplicate a
-- hand-written column list per table -- which silently misses a table's own
-- future columns -- this adds a generic guard that diffs the entire row
-- (excluding bookkeeping columns that are expected to change even on a
-- finalized record: updated_at, cde_approved_by, cde_approved_at) whenever
-- cde_state stays PUBLISHED/ARCHIVED across the update.

BEGIN;

CREATE OR REPLACE FUNCTION public.prevent_published_cde_mutation_generic()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    old_row jsonb;
    new_row jsonb;
BEGIN
    IF OLD.cde_state IN ('PUBLISHED', 'ARCHIVED') AND NEW.cde_state = OLD.cde_state THEN
        old_row := to_jsonb(OLD) - 'updated_at' - 'cde_approved_by' - 'cde_approved_at';
        new_row := to_jsonb(NEW) - 'updated_at' - 'cde_approved_by' - 'cde_approved_at';
        IF old_row IS DISTINCT FROM new_row THEN
            RAISE EXCEPTION 'Cannot modify record % in state %', OLD.id, OLD.cde_state;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_documents_cde_guard ON public.documents;
CREATE TRIGGER trg_documents_cde_guard
    BEFORE UPDATE ON public.documents
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_published_cde_mutation_generic();

DROP TRIGGER IF EXISTS trg_project_ifc_files_cde_guard ON public.project_ifc_files;
CREATE TRIGGER trg_project_ifc_files_cde_guard
    BEFORE UPDATE ON public.project_ifc_files
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_published_cde_mutation_generic();

COMMIT;
