-- Add original_source_element_id: snapshots which element a draft was
-- originally linked to (the LLM's pick), captured only the first time a
-- reviewer relinks it to a different element -- mirrors
-- original_proposed_rule's before/after shape for rule-content edits, so
-- the evaluation companion repo can score localization accuracy the same way.
ALTER TABLE public.rule_extraction_drafts ADD COLUMN IF NOT EXISTS original_source_element_id text;
