create table public.model_enhancement_version_counters (
	project_id bigint primary key references public.projects(id) on delete cascade,
	next_version bigint not null check (next_version > 0)
);

alter table public.model_enhancement_version_counters enable row level security;

revoke all privileges on table public.model_enhancement_version_counters
from anon, authenticated, service_role;

create or replace function public.allocate_model_enhancement_version(target_project_id bigint)
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
	allocated_version bigint;
begin
	insert into public.model_enhancement_version_counters (project_id, next_version)
	values (
		target_project_id,
		(
			select coalesce(max(lineage.version), 0) + 2
			from public.model_enhancement_lineage as lineage
			where lineage.project_id = target_project_id
		)
	)
	on conflict (project_id) do update
	set next_version = public.model_enhancement_version_counters.next_version + 1
	returning next_version - 1 into allocated_version;

	return allocated_version;
end;
$$;

revoke all on function public.allocate_model_enhancement_version(bigint)
from public, anon, authenticated;
grant execute on function public.allocate_model_enhancement_version(bigint) to service_role;