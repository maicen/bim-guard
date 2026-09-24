-- Add source_element_id: links a rule / rule extraction draft to the exact
-- DocLang element (heading/paragraph/table/picture) it was extracted from,
-- matching documents.element_bboxes[].element_id. Nullable -- rows created
-- before this column existed have no exact element-level link and fall back
-- to their existing source_page_number/source_bbox for an approximate match.
ALTER TABLE public.rules ADD COLUMN IF NOT EXISTS source_element_id text;
ALTER TABLE public.rule_extraction_drafts ADD COLUMN IF NOT EXISTS source_element_id text;
