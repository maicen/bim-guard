-- Migration: Add ruleset and creator identity to report_artifacts
-- Date: 2026-09-22
-- Purpose: BCF/PDF/CSV report artifacts saved from the compliance audit page
--          need to record which ruleset was run and who ran it, so
--          Reports & Exports can show project + ruleset + user + time for
--          every saved report. rule_folder/ruleset_name stay NULL for an
--          unscoped ("All Rules") run and for existing rows. ruleset_name
--          and created_by_email are snapshots taken at save time (same
--          precedent as profiles.email in 20260905100808_add_email_to_profiles.sql)
--          so a saved report still reads correctly if the ruleset is later
--          renamed/deleted or the user's email changes.
--
-- Idempotent: safe to re-run.

BEGIN;

ALTER TABLE public.report_artifacts
    ADD COLUMN IF NOT EXISTS rule_folder TEXT NULL,
    ADD COLUMN IF NOT EXISTS ruleset_name TEXT NULL,
    ADD COLUMN IF NOT EXISTS created_by UUID NULL
        REFERENCES auth.users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS created_by_email TEXT NULL;

CREATE INDEX IF NOT EXISTS idx_report_artifacts_rule_folder
    ON public.report_artifacts(rule_folder);

COMMIT;

-- Verify:
--   SELECT column_name FROM information_schema.columns
--    WHERE table_name = 'report_artifacts'
--      AND column_name IN ('rule_folder', 'ruleset_name', 'created_by', 'created_by_email');
