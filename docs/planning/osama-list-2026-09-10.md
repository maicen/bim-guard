# Osama's measured list — 2026-09-10

Supersedes `osama-list-2026-09-09.md` (branch `docs/osama-list-2026-09-09`).
Three changes from that revision: a new item 1 for the Project Registry
deletion, item 5 expanded with a fifth unapplied migration and the ten that
have landed since, and item 9's runbook line reference corrected. Every other
item is carried over unchanged.

## Items

1. **Project Registry deletion removed two demo projects.** On 2026-09-08 at
   21:58 five projects were deleted by hand through the SPA
   (`DELETE /api/projects/{id}` → 204: 322, 1540, 1541, 1591, 1542). Two of
   them — 1540 and 1542 — are steps in the demo walkthrough. The per-row Delete
   is live and its confirmation is weak. 1540 and 1542 were restored on
   2026-09-09 with their original ids by direct insert, then re-attached
   through the API; all three models verified byte-identical by SHA-256 on
   2026-09-10. 1541, 1591 and 322 were not restored. Restoring the ids is what
   makes the analysis cache reachable, but it does not resurrect the entries:
   the store is per-process and in-memory, so the 2026-09-10 re-warm cost 158.7
   minutes for 63 of 63 entries. **Where:**
   `docs/validation/sql/20260909_restore_projects_1540_1542.sql`,
   `docs/demo/RUNBOOK.md:449` (restore procedure) and `:504` (limitation),
   `app/services/analysis_cache.py` (`CacheKey`), commit `bc1c88b`. **Fix must
   show:** either a soft delete with a recovery path, or a confirmation that
   names the project and requires typing it, tested against a project that has
   cached analyses.

2. **Health probe uses dashboard stats, not /api/health.** `/api/dashboard/stats` called on 45 s interval (20 s before ba714e0, 45 s after); measured 5.7–7.6 s per call in 8 Sept runbook (142 calls in 80 min, 111 off-route). `/api/health` at `app/api/__init__.py:68` is unused. **Where:** `frontend/src/App.svelte:127` (checkHealth), `ba714e0` (interval change). **Fix must show:** measured time split by layer (auth/org lookup, cache, query).

3. **Cached reads carry a ~3 s floor.** 1917 paginated 50 rows in 3,240 ms; 1542 in 3,197 ms (8 Sept runbook). Bottleneck not located in code; measurement only. **Where:** `docs/demo/RUNBOOK.md` (pre-warm section, measured values). **Fix must show:** layer timing (network/auth/org/query) from code inspection or instrumentation.

4. **Auth changes broke exports until fixed.** `47cf29b` (fix(security): require auth on every route) broke browser navigation; `9e37275` (fix(export): send session token on export URLs) restored it. **Where:** `app/api/analyze.py` (auth route), test at `tests/test_export_download_auth.py`. **Fix must show:** the test suite now covers the pattern (auth changes tested against export paths).

5. **Five migrations in code, not applied — and ten more have landed since.**
   Files in `supabase/migrations/`:
   `20260907202655_add_org_code_to_organizations.sql`,
   `20260908141146_add_ifc_model_summary_metadata.sql`,
   `20260908143524_cascade_model_enhancement_lineage_on_project_delete.sql`,
   `20260908144003_add_ifc_file_id_to_model_enhancement_lineage.sql`,
   `20260908144010_add_ifc_file_id_to_report_artifacts.sql`. The fifth was
   missed in the 9 Sept revision; it is seven seconds after the fourth, in the
   same 8 Sept batch and the same `add_ifc_file_id_to_*` family. Since that
   revision a further **ten** migrations have landed on `main`
   (`20260909052852` through `20260910144900`, mostly DocLang and
   LLM-provider work), whose applied state has not been checked — so the count
   in this item is a floor, not a total. **Where:** directory listing;
   `supabase_migrations.schema_migrations` for the applied set. **Fix must
   show:** `list_migrations` output reconciled against the directory, with each
   file either applied to production or explicitly deferred.

6. **Test creates and deletes rows in live Supabase.** `tests/test_api_rules.py` (lines 62, 71, 113–114, 176, 194–195, 220) creates/deletes rules and rulesets; four orphaned rows after 7 Sept cleanup (615 rows → 602 with 9 deleted SQL). **Where:** `tests/test_api_rules.py`. **Fix must show:** either test isolation (temp project key) or documented cleanup.

7. **Svelte type errors in ArchAnalyzeView.** ArchAnalyzeView.svelte line 400 column 34: "Property 'rule_compliance_summary' does not exist on type 'never'"; line 406:42 'building_summary'; line 408:13 'rule_folder'. **Where:** `frontend/src/routes/ArchAnalyzeView.svelte`. **Fix must show:** types resolved or the view integrated.

8. **401-on-mount race in project/rules loads.** `b20a0de` (fix(frontend): resolve org-scoped project list races) addresses live-testing failures; races on project/rules loads from unauthenticated mounts. **Where:** `b20a0de` commit message. **Fix must show:** the race resolved or isolated to specific conditions.

9. **Storage limit mismatch: code vs provider.** `MAX_UPLOAD_BYTES` in `app/modules/phase_6/phase_6a_upload.py:57` is 512 MB; Supabase returns 413 on uploads over ~50 MB (documented in `docs/demo/RUNBOOK.md:551`). West Riverside mechanical model is 69.7 MB and will not upload. **Where:** `app/modules/phase_6/phase_6a_upload.py:57`, `docs/demo/RUNBOOK.md:551`. **Fix must show:** either raise Supabase limit or lower MAX_UPLOAD_BYTES, tested on 50–70 MB models.

10. **ProjectsView.svelte removed; runbook revised.** `9d818c9` (feat(frontend): fold project registry into dashboard) removed the Projects view and moved model attach to Models page. Runbook rewritten 8 Sept for the new flow. **Where:** `9d818c9` commit. **Fix must show:** navigation changes require runbook review at merge time (note for next three months until October).

---

## Note

The demo runs from tag `fmp-demo` at `a55b70a` and nothing on this list requires
a change before 12 October. Item 1 is the exception worth reading twice: the
deletion it records has already been repaired, but the mechanism that allowed it
is unchanged and still live in the build the demo runs from.
