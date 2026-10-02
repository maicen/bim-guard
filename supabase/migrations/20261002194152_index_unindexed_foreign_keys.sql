-- Index foreign-key columns that had no covering index, plus invite email.
--
-- WHY: Postgres does not index the referencing side of a foreign key. Every
-- DELETE (or key UPDATE) on the referenced table must find the referencing
-- rows to apply ON DELETE SET NULL / CASCADE, and without an index that is a
-- sequential scan of the child table per deleted parent row. Deleting a rule,
-- document, model, user or check category therefore scanned these tables in
-- full. Each index below makes that lookup an index probe.
--
-- Rule of thumb for future migrations: when adding a FOREIGN KEY, add an index
-- on the referencing column(s) in the same migration unless an existing
-- index already leads with them.
--
-- IF NOT EXISTS keeps the migration safe to re-run against an environment
-- where an index was created by hand.

CREATE INDEX IF NOT EXISTS rule_extraction_drafts_promoted_rule_id_idx
    ON public.rule_extraction_drafts USING btree (promoted_rule_id);

CREATE INDEX IF NOT EXISTS report_artifacts_created_by_idx
    ON public.report_artifacts USING btree (created_by);

CREATE INDEX IF NOT EXISTS chat_conversations_document_id_idx
    ON public.chat_conversations USING btree (document_id);

CREATE INDEX IF NOT EXISTS evaluation_findings_ifc_file_id_idx
    ON public.evaluation_findings USING btree (ifc_file_id);

CREATE INDEX IF NOT EXISTS rule_check_category_properties_check_category_id_idx
    ON public.rule_check_category_properties USING btree (check_category_id);

-- The unique key (organization_id, task_key, provider_instance_id, model_id)
-- does not lead with provider_instance_id, so it cannot serve this FK.
CREATE INDEX IF NOT EXISTS llm_task_model_assignments_provider_instance_id_idx
    ON public.llm_task_model_assignments USING btree (provider_instance_id);

-- MembershipService._consume_invites filters `email = ?` through PostgREST,
-- which cannot express lower(email), so the existing expression index
-- organization_invites_email_idx (on lower(email)) is never used.
-- MembershipService.create_invite already stores emails trimmed and
-- lowercased, so a plain index on the column matches every lookup.
CREATE INDEX IF NOT EXISTS organization_invites_email_plain_idx
    ON public.organization_invites USING btree (email);
