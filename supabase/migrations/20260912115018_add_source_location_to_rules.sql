-- Carry the exact extraction source location (node id, page, bounding box)
-- from a rule_extraction_drafts row through to the promoted rules row, so
-- "View Source" on a promoted rule can jump straight to the right page/box
-- instead of falling back to fuzzy text-to-page matching.
alter table public.rules
    add column if not exists source_node_id text,
    add column if not exists source_page_number integer,
    add column if not exists source_bbox jsonb;
