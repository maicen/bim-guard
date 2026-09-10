-- Cache columns for cheap document-list rendering now that full text is no
-- longer persisted (see 20260910093100_drop_documents_extracted_text.sql):
-- char_count/text_preview are derived once from DocLang XML at
-- generation time and cached here, the same pattern already used for
-- doclang_size_bytes, so listing documents never has to materialize
-- offloaded DocLang XML from storage per row.
alter table public.documents
	add column if not exists char_count integer not null default 0,
	add column if not exists text_preview text not null default '';
