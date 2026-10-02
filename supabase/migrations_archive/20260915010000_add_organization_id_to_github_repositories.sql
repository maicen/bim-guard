-- Scope github_repositories to an owning organization.
--
-- app/api/repositories.py previously gated every route (including update and
-- delete) on nothing but "is this a signed-in caller" -- the table carried no
-- organization_id at all, so any authenticated user could rename, disable, or
-- delete another organization's registered repository source. This backfills
-- every existing row to the same default organization every pre-multi-tenant
-- project was assigned (see 20260904235344_create_organizations_and_memberships.sql),
-- then requires it going forward, matching the public.projects pattern.

alter table public.github_repositories
	add column if not exists organization_id bigint references public.organizations (id);

update public.github_repositories
set organization_id = (select id from public.organizations where slug = 'default')
where organization_id is null;

alter table public.github_repositories
	alter column organization_id set not null;

create index if not exists github_repositories_organization_id_idx
	on public.github_repositories (organization_id);
