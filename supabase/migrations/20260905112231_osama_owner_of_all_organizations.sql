-- eng.superosama@gmail.com already bypasses org checks as a superadmin, but
-- should also hold 'owner' membership in every existing organization -- an
-- explicit ownership record, not just an implicit backend bypass.

update public.memberships
set role = 'owner'
where user_id = (select id from auth.users where email = 'eng.superosama@gmail.com')
	and organization_id = (select id from public.organizations where slug = 'default');

insert into public.memberships (organization_id, user_id, role)
select o.id, u.id, 'owner'
from public.organizations o
cross join (select id from auth.users where email = 'eng.superosama@gmail.com') u
where o.slug in ('archinova', 'aspiring-design-3d')
on conflict (organization_id, user_id) do update set role = 'owner';
