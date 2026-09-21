-- Purge the piping (corrosion) and seismic analysis domains.
--
-- BIM Guard is architectural-only going forward. This removes every rule,
-- ruleset, grant and binding for the GC-001 (galvanic), CC-001 (crevice),
-- MC-001 (microbiological), MM-001 (material/media), XM-001 (cross-material),
-- PC-001 (NFPA 13 pipe clearance), SB-001 (Blue Halo seismic clearance),
-- NOTEBOOKLM-TEST-NZ and SEISMIC-GLOBAL rulesets, reassigns any project or
-- rule left pointing at the retired 'Piping'/'seismic' domains onto 'Arch',
-- and narrows the domain check constraints so those values can no longer be
-- written.

-- ── Retired rulesets ──────────────────────────────────────────────────────
-- A literal list rather than a WHERE category IN ('Piping','seismic') join,
-- so this migration is explicit about exactly which rulesets it removes and
-- does not silently widen its own scope if a future ruleset is miscategorised.
do $$
declare
  retired_rulesets text[] := array[
    'BIMGUARD-GC-001',
    'BIMGUARD-CC-001',
    'BIMGUARD-MC-001',
    'BIMGUARD-MM-001',
    'BIMGUARD-XM-001',
    'BIMGUARD-PC-001',
    'BIMGUARD-SB-001',
    'NOTEBOOKLM-TEST-NZ',
    'SEISMIC-GLOBAL'
  ];
begin
  delete from public.project_ruleset_bindings where ruleset_id = any(retired_rulesets);
  delete from public.organization_ruleset_grants where ruleset_id = any(retired_rulesets);
  delete from public.rules where ruleset_id = any(retired_rulesets);
  delete from public.rule_folders where ruleset_id = any(retired_rulesets);
  delete from public.static_data_assets
    where asset_key = any(
      array(select 'ruleset:' || unnest(retired_rulesets))
    );
end $$;

-- ── Reassign any project or rule still carrying a retired domain ──────────
update public.projects
  set analysis_type = 'Arch'
  where analysis_type not in ('Arch', 'Architectural', 'Architecture', 'arch');

update public.rule_folders
  set category = 'Arch'
  where category not in ('Arch');

update public.rules
  set category = 'Arch'
  where category is not null and category not in ('Arch');

-- ── Narrow the domain check constraints to Arch only ───────────────────────
alter table public.projects drop constraint if exists valid_analysis_type;
alter table public.projects add constraint valid_analysis_type
  check (analysis_type in ('Arch', 'Architectural', 'Architecture', 'arch'));

alter table public.rule_folders drop constraint if exists valid_rule_folder_category;
alter table public.rule_folders add constraint valid_rule_folder_category
  check (category = 'Arch');

alter table public.rules drop constraint if exists valid_rule_category_domain;
alter table public.rules add constraint valid_rule_category_domain
  check (category is null or category = 'Arch');
