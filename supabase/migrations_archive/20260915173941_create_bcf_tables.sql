-- Migration: create_bcf_tables
-- Description: Persist BCF-API 2.1 topics/comments/viewpoints (app/api/bcf_routes.py,
-- app/services/bcf_sync_service.py) to Supabase instead of an in-process dict.
-- The prior in-memory BCFSyncService singleton lost every topic/comment/viewpoint
-- on restart and was not shared across the multi-worker production uvicorn
-- processes started by run_production_server.sh/bat.
--
-- project_id is stored as text (not a FK to public.projects) because the BCF
-- routes also serve string/UUID project ids that have no row in public.projects
-- (see the fallback branch in app.api.bcf_routes.get_bcf_project).
--
-- Written and read exclusively by BCFSyncService via the service-role key
-- (same as public.audit_log / public.role_permissions); RLS denies
-- anon/authenticated direct access -- clients reach this data only through
-- the authenticated /api/bcf/v2.1/* routes.

create table if not exists public.bcf_topics (
	guid text primary key,
	project_id text not null,
	topic_type text not null default 'Issue',
	topic_status text not null default 'Open',
	title text not null default '',
	priority text not null default 'Normal',
	topic_index integer not null default 1,
	creation_date text not null default '',
	creation_author text not null default '',
	modified_date text,
	modified_author text,
	assigned_to text,
	description text,
	due_date text,
	labels jsonb not null default '[]'::jsonb,
	stage text,
	component_guids jsonb not null default '[]'::jsonb,
	project_code text,
	originator text,
	suitability_code text,
	revision_code text,
	cde_state text,
	created_at timestamptz not null default now()
);

create index if not exists idx_bcf_topics_project on public.bcf_topics (project_id);

create table if not exists public.bcf_comments (
	guid text primary key,
	topic_guid text not null references public.bcf_topics (guid) on delete cascade,
	comment_date text not null default '',
	author text not null default '',
	comment text not null default '',
	modified_date text,
	modified_author text,
	viewpoint_guid text,
	created_at timestamptz not null default now()
);

create index if not exists idx_bcf_comments_topic on public.bcf_comments (topic_guid);

create table if not exists public.bcf_viewpoints (
	guid text primary key,
	topic_guid text not null references public.bcf_topics (guid) on delete cascade,
	viewpoint_index integer not null default 0,
	perspective_camera jsonb,
	orthogonal_camera jsonb,
	lines jsonb not null default '[]'::jsonb,
	clipping_planes jsonb not null default '[]'::jsonb,
	components jsonb not null default '{}'::jsonb,
	snapshot_base64 text,
	created_at timestamptz not null default now()
);

create index if not exists idx_bcf_viewpoints_topic on public.bcf_viewpoints (topic_guid);

alter table public.bcf_topics enable row level security;
alter table public.bcf_comments enable row level security;
alter table public.bcf_viewpoints enable row level security;

revoke all privileges on table public.bcf_topics from anon, authenticated;
revoke all privileges on table public.bcf_comments from anon, authenticated;
revoke all privileges on table public.bcf_viewpoints from anon, authenticated;

grant select, insert, update, delete on table public.bcf_topics to service_role;
grant select, insert, update, delete on table public.bcf_comments to service_role;
grant select, insert, update, delete on table public.bcf_viewpoints to service_role;
