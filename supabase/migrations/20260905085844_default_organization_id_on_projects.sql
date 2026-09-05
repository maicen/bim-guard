-- projects.organization_id is NOT NULL, but nothing in the application layer
-- sets it yet (schema-only phase — see 20260904235344). Without a DB-side
-- default, every project insert made by existing code fails with a
-- not-null violation. A stable function backs the default so it can be
-- resolved at insert time rather than baked in as a literal id.

create or replace function public.default_organization_id()
returns bigint
language sql
stable
as $$
	select id from public.organizations where slug = 'default' limit 1;
$$;

alter table public.projects
	alter column organization_id set default public.default_organization_id();
