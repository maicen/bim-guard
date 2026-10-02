-- Migration: Cascade-delete model_enhancement_lineage rows with their project
-- Date: 2026-09-08
-- Purpose: model_enhancement_lineage_project_id_fkey was created with the
--          default NO ACTION delete rule -- the only project_id foreign key
--          in the schema that isn't ON DELETE CASCADE (every sibling child
--          table -- client_documents, project_ifc_files, uploaded_files,
--          report_artifacts, etc. -- cascades). Deleting a project that has
--          any enhancement lineage rows therefore hit the FK's RESTRICT
--          behavior and raised an unhandled postgrest APIError, crashing
--          ProjectsService.delete_project / bulk_delete_projects with a 500
--          instead of either succeeding or failing with a clear message.
--
-- 20260822131000_enforce_append_only_model_lineage.sql revoked UPDATE/DELETE
-- grants from service_role so the app itself cannot edit or delete individual
-- lineage rows during a project's lifetime -- that append-only guarantee is
-- about protecting the audit trail while the project exists, not about
-- surviving the project's own deletion. A lineage row for a project that no
-- longer exists is not a durable record of anything; it is orphaned data a
-- NO ACTION delete rule turns into "project deletion permanently fails"
-- instead of "the row goes with its project", so this fixes the rule to
-- match every other per-project table rather than changing app-level grants.
--
-- Idempotent: safe to re-run.

BEGIN;

ALTER TABLE public.model_enhancement_lineage
    DROP CONSTRAINT model_enhancement_lineage_project_id_fkey,
    ADD CONSTRAINT model_enhancement_lineage_project_id_fkey
        FOREIGN KEY (project_id) REFERENCES public.projects(id) ON DELETE CASCADE;

COMMIT;

-- Verify:
--   SELECT tc.constraint_name, rc.delete_rule
--     FROM information_schema.table_constraints tc
--     JOIN information_schema.referential_constraints rc
--       ON tc.constraint_name = rc.constraint_name
--    WHERE tc.constraint_name = 'model_enhancement_lineage_project_id_fkey';
