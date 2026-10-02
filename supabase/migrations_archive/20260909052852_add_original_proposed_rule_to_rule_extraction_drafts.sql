-- Preserve the LLM's original proposed_rule when a reviewer edits a draft,
-- so the evaluation feedback loop can diff "what the model produced" against
-- "what the human corrected it to" instead of losing the original in place.
-- Nullable and only ever populated on the first edit of a given draft.
alter table public.rule_extraction_drafts
  add column if not exists original_proposed_rule jsonb null;

comment on column public.rule_extraction_drafts.original_proposed_rule is
  'The LLM-proposed rule as first extracted, captured only when a reviewer edits proposed_rule (status=edited). Null for drafts never edited.';
