-- Adds an email column to profiles so organization admin screens can list
-- members by email without querying auth.users directly (not exposed via
-- PostgREST). Backfilled once from auth.users for every profile that already
-- exists; new profiles are given their email at provision time by the API.

alter table public.profiles
	add column if not exists email text;

update public.profiles p
set email = u.email
from auth.users u
where p.id = u.id
	and p.email is null;

create index if not exists profiles_email_idx on public.profiles (lower(email));
