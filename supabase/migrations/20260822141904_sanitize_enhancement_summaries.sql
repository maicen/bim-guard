update public.model_enhancement_lineage
set summary = jsonb_set(
	summary,
	'{improvements}',
	coalesce(
		(
			select jsonb_agg(item)
			from jsonb_array_elements(summary -> 'improvements') as item
			where item #>> '{}' not like 'Improved file saved:%'
		),
		'[]'::jsonb
	),
	true
)
where jsonb_typeof(summary -> 'improvements') = 'array';