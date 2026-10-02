-- Adds organizations.org_code: the ISO 19650 "Originator" code identifying
-- the authoring organization in container naming (Project-Originator-Volume-
-- Level-Type-Role-Number). Required for every new organization going
-- forward (enforced in OrganizationCreateRequest), same 2-6 alphanumeric
-- character convention as projects.project_code. Column stays NOT NULL
-- DEFAULT '' -- the same pattern already used for every other ISO 19650
-- field -- so nothing else touching this table needs to change.
alter table public.organizations
  add column org_code varchar(6) not null default '';

update public.organizations set org_code = 'BIMG' where id = 1; -- Default Organization
update public.organizations set org_code = 'ARCN' where id = 2; -- Archinova
update public.organizations set org_code = 'AD3D' where id = 3; -- Aspiring Design 3D Consultancy Ltd

-- Any organization created between the query that produced the list above
-- and this migration running gets a code derived from its own name rather
-- than being left blank.
update public.organizations
  set org_code = upper(left(regexp_replace(name, '[^A-Za-z0-9]', '', 'g'), 6))
  where org_code = '';

update public.organizations
  set org_code = left('O' || id::text, 6)
  where org_code = '';
