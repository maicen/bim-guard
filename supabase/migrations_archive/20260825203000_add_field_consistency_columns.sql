begin;

-- Two new rule-check operators (Module 4): field_consistency compares a
-- property to a second property fetched from the SAME element (e.g. a
-- wall's Name must embed the same code stored in its Cod_Object
-- parameter); unique_within_scope flags elements that share a property
-- value with another element in the same storey/space/model (e.g. two
-- doors on the same floor both coded "1").
alter table public.rules
    add column if not exists compare_property text not null default '',
    add column if not exists name_pattern text not null default '',
    add column if not exists uniqueness_scope text not null default '';

commit;
