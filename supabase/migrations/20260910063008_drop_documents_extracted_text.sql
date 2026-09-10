-- DocLang XML is now the only persisted text representation of a document
-- (doclang_xml / doclang_storage_path / doclang_archive_path); plain text is
-- derived from it on demand (app/modules/document_parsing/doclang_text.py)
-- instead of being stored. All backend readers were repointed to that
-- helper before this migration, so it is safe to drop the column.
alter table public.documents
	drop column if exists extracted_text;
