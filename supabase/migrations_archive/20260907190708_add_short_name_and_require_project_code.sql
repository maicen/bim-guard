-- Adds projects.short_name (a human-readable nickname the header/breadcrumbs
-- now display instead of a project switcher) and caps project_code to the
-- length ISO 19650 container naming keeps that segment to. Both are enforced
-- as required, ISO-length-bounded fields at the application layer
-- (ProjectCreateRequest in app/modules/contracts.py) for every new project;
-- the columns here stay NOT NULL DEFAULT '' -- the same pattern already used
-- for every other ISO 19650 field on this table -- so older rows and
-- internal service callers that do not set one are not broken.
alter table public.projects
  add column short_name varchar(24) not null default '';

alter table public.projects
  alter column project_code type varchar(6);

-- Backfill: every project that existed before this migration had project_code
-- unset, so pick a short, distinct nickname and a 2-6 character ISO 19650
-- project code for each from its existing name.
update public.projects set short_name = 'Pacific Residence',       project_code = 'PCR'    where id = 3;
update public.projects set short_name = 'Updated Project',         project_code = 'UPD'    where id = 5;
update public.projects set short_name = 'BG HQ 1',                 project_code = 'BGHQ1'  where id = 8;
update public.projects set short_name = 'Door Mock',                project_code = 'DOOR'  where id = 11;
update public.projects set short_name = 'NeoGarden',                project_code = 'NEOG'  where id = 14;
update public.projects set short_name = 'Golden Ref',               project_code = 'GOLD'  where id = 18;
update public.projects set short_name = 'Golden Ref v2',            project_code = 'GOLD2' where id = 19;
update public.projects set short_name = 'Broken Twin v2',           project_code = 'BTW2'  where id = 20;
update public.projects set short_name = 'Golden Ref v3',            project_code = 'GOLD3' where id = 21;
update public.projects set short_name = 'Broken Twin v3',           project_code = 'BTW3'  where id = 22;
update public.projects set short_name = 'Test 1',                   project_code = 'TST1'  where id = 24;
update public.projects set short_name = 'Fefefg',                   project_code = 'FEFEFG' where id = 25;
update public.projects set short_name = 'Multi Upload Test',        project_code = 'MUDZ'  where id = 26;
update public.projects set short_name = 'E2E Test',                 project_code = 'E2E1'  where id = 29;
update public.projects set short_name = 'E2E Full Test 2',          project_code = 'E2E2'  where id = 30;
update public.projects set short_name = 'SPA E2E Test',             project_code = 'SPAE2' where id = 31;
update public.projects set short_name = 'Wizard Restore',           project_code = 'WZRT'  where id = 38;
update public.projects set short_name = 'Wizard Full Restore',      project_code = 'WZFR'  where id = 40;
update public.projects set short_name = 'Nav Test Arch',            project_code = 'NAVA'  where id = 46;
update public.projects set short_name = 'Nav Test Piping',          project_code = 'NAVP'  where id = 47;
update public.projects set short_name = 'Nav Test Seismic',         project_code = 'NAVS'  where id = 48;
update public.projects set short_name = 'Clinic Arch Seed',         project_code = 'CLASV' where id = 83;
update public.projects set short_name = 'Clinic Plumbing',          project_code = 'CLPLM' where id = 119;
update public.projects set short_name = 'Test',                     project_code = 'TEST'  where id = 144;
update public.projects set short_name = 'KLK Test',                 project_code = 'KLKSD' where id = 155;
update public.projects set short_name = 'Dsadasd',                  project_code = 'DSADA' where id = 167;
update public.projects set short_name = 'MM-XM Checkbox',           project_code = 'MMXMC' where id = 322;
update public.projects set short_name = 'Clinic Arch Import',       project_code = 'CLAIM' where id = 1005;
update public.projects set short_name = 'Clinic Arch Import 2',     project_code = 'CLAI2' where id = 1120;
update public.projects set short_name = 'Final Piping WR IFC4',     project_code = 'FPWR4' where id = 1540;
update public.projects set short_name = 'Final Piping MEP',         project_code = 'FPMEP' where id = 1541;
update public.projects set short_name = 'Final Seismic Federated',  project_code = 'FSWRF' where id = 1542;
update public.projects set short_name = 'Final Seismic IFC2X3',     project_code = 'FSWR2' where id = 1591;
update public.projects set short_name = 'Hospital MEP Demo',        project_code = 'HMEPD' where id = 1917;

-- Any project created between the query that produced the list above and this
-- migration running gets a short name derived from its own name/id rather
-- than being left blank.
update public.projects
  set short_name = left(name, 24),
      project_code = upper(left(regexp_replace(name, '[^A-Za-z0-9]', '', 'g'), 6))
  where short_name = ''
    and project_code = '';

-- A project whose name had no alphanumeric characters at all (rare, but the
-- expression above can produce an empty string) still needs a valid code.
update public.projects
  set project_code = left('P' || id::text, 6)
  where project_code = '';
