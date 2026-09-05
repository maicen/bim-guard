-- User profiles: display identity and per-user preferences layered on top of
-- auth.users, which only carries what Google's OAuth handed Supabase.

create table if not exists public.profiles (
	id uuid primary key references auth.users (id) on delete cascade,
	full_name text not null default '',
	avatar_url text not null default '',
	title text not null default '',
	default_organization_id bigint references public.organizations (id),
	preferences jsonb not null default '{}'::jsonb,
	created_at timestamptz not null default now(),
	updated_at timestamptz not null default now()
);

create index if not exists profiles_default_organization_id_idx on public.profiles (default_organization_id);

alter table public.profiles enable row level security;

revoke all privileges on table public.profiles from anon, authenticated;
grant select, insert, update, delete on table public.profiles to service_role;
