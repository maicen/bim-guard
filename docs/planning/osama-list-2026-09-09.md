# Osama's measured list — 2026-09-09

## Items

1. **Health probe uses dashboard stats, not /api/health.** `/api/dashboard/stats` called on 45 s interval (20 s before ba714e0, 45 s after); measured 5.7–7.6 s per call in 8 Sept runbook (142 calls in 80 min, 111 off-route). `/api/health` at `app/api/__init__.py:68` is unused. **Where:** `frontend/src/App.svelte:127` (checkHealth), `ba714e0` (interval change). **Fix must show:** measured time split by layer (auth/org lookup, cache, query).

2. **Cached reads carry a ~3 s floor.** 1917 paginated 50 rows in 3,240 ms; 1542 in 3,197 ms (8 Sept runbook). Bottleneck not located in code; measurement only. **Where:** `docs/demo/RUNBOOK.md` (pre-warm section, measured values). **Fix must show:** layer timing (network/auth/org/query) from code inspection or instrumentation.

3. **Auth changes broke exports until fixed.** `47cf29b` (fix(security): require auth on every route) broke browser navigation; `9e37275` (fix(export): send session token on export URLs) restored it. **Where:** `app/api/analyze.py` (auth route), test at `tests/test_export_download_auth.py`. **Fix must show:** the test suite now covers the pattern (auth changes tested against export paths).

4. **Four migrations in code, not applied.** Files in `supabase/migrations/`: `20260907202655_add_org_code_to_organizations.sql`, `20260908141146_add_ifc_model_summary_metadata.sql`, `20260908143524_cascade_model_enhancement_lineage_on_project_delete.sql`, `20260908144003_add_ifc_file_id_to_model_enhancement_lineage.sql`. **Where:** directory listing. **Fix must show:** applied to production or explicitly deferred.

5. **Test creates and deletes rows in live Supabase.** `tests/test_api_rules.py` (lines 62, 71, 113–114, 176, 194–195, 220) creates/deletes rules and rulesets; four orphaned rows after 7 Sept cleanup (615 rows → 602 with 9 deleted SQL). **Where:** `tests/test_api_rules.py`. **Fix must show:** either test isolation (temp project key) or documented cleanup.

6. **Svelte type errors in ArchAnalyzeView.** ArchAnalyzeView.svelte line 400 column 34: "Property 'rule_compliance_summary' does not exist on type 'never'"; line 406:42 'building_summary'; line 408:13 'rule_folder'. **Where:** `frontend/src/routes/ArchAnalyzeView.svelte`. **Fix must show:** types resolved or the view integrated.

7. **401-on-mount race in project/rules loads.** `b20a0de` (fix(frontend): resolve org-scoped project list races) addresses live-testing failures; races on project/rules loads from unauthenticated mounts. **Where:** `b20a0de` commit message. **Fix must show:** the race resolved or isolated to specific conditions.

8. **Storage limit mismatch: code vs provider.** `MAX_UPLOAD_BYTES` in `app/modules/phase_6/phase_6a_upload.py:57` is 512 MB; Supabase returns 413 on uploads over ~50 MB (documented in `docs/demo/RUNBOOK.md:425`). West Riverside mechanical model is 69.7 MB and will not upload. **Where:** `app/modules/phase_6/phase_6a_upload.py:57`, `docs/demo/RUNBOOK.md:425`. **Fix must show:** either raise Supabase limit or lower MAX_UPLOAD_BYTES, tested on 50–70 MB models.

9. **ProjectsView.svelte removed; runbook revised.** `9d818c9` (feat(frontend): fold project registry into dashboard) removed the Projects view and moved model attach to Models page. Runbook rewritten 8 Sept for the new flow. **Where:** `9d818c9` commit. **Fix must show:** navigation changes require runbook review at merge time (note for next three months until October).

---

## Note

The demo runs from tag `fmp-demo` at `a55b70a` and nothing on this list requires a change before 12 October.
