-- Constrain documents.doc_type to the same governed list already enforced
-- on client_documents.category (see 20260831173329_add_doc_type_to_documents.sql),
-- now that the Add Rule Source modal's Document Type dropdown offers the
-- full list instead of a 3-value subset.
alter table public.documents
	add constraint documents_doc_type_check
	check (doc_type in (
		'Specification', 'Code', 'Manual', 'Standard', 'Drawing', 'Schedule',
		'O&M Manual', 'Warranty', 'Assessment', 'Report', 'RFI Log', 'Other'
	));
