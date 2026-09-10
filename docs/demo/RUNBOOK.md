# BIM-Guard demo runbook

For the person driving the demo. Every command is PowerShell, run from the repo
root unless a step says otherwise. Numbers quoted here were measured on
2026-09-05/06 and are recorded in `docs/validation/final-audit-2026-09-06.md`.

---

## The demo runs from a tagged worktree, not from `main`

`main` keeps moving. The demo runs from a detached worktree pinned to the
verified commit, so nothing merged this week can change what the audience sees.

| | |
| --- | --- |
| Tag | `fmp-demo` |
| Commit | `a55b70a` |
| Worktree | `D:\Zigurat Masters\bim-guard-fmpdemo` |
| Verified by | `docs/validation/final-verification-2026-09-09.md`, including the 2026-09-08 freeze spot-check |

The worktree was created with `git worktree add "D:\Zigurat Masters\bim-guard-fmpdemo" fmp-demo`,
then `.env` and `frontend\.env` copied in, `uv sync`, `npm ci` and
`npx vite build` run inside it. It already has its dependencies and its build.
Nothing below needs repeating unless the worktree is deleted.

**Everything in this runbook runs from the worktree, not from the repo root** --
with one exception, noted under Pre-warm.

## Start the demo servers (from the worktree)

Both servers run in their own window so you can read their logs. Run these two
commands verbatim; the working directory inside each is what makes
`python-dotenv` find `.env` and the rule catalogs come from the database rather
than the reduced fallback table.

```powershell
Start-Process powershell -ArgumentList '-NoExit','-Command',"cd 'D:\Zigurat Masters\bim-guard-fmpdemo'; `$env:BIMGUARD_CACHE_TTL_SECONDS='2592000'; `$env:BIMGUARD_CACHE_ENTRIES='128'; uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 *>&1 | Tee-Object -FilePath 'docs\validation\demo-backend.log'"
Start-Process powershell -ArgumentList '-NoExit','-Command',"cd 'D:\Zigurat Masters\bim-guard-fmpdemo\frontend'; npx vite --port 5173"
```

**Why the two cache variables.** Left alone, `analysis_cache` keeps entries for
24 hours (`BIMGUARD_CACHE_TTL_SECONDS`, default 86400) and holds only 64 of them
(`BIMGUARD_CACHE_ENTRIES`, default 64) — and a full warm is 63, one short of the
cap, so anything else analysed that day evicts a demo entry. The values above
raise the TTL to 30 days and the ceiling to 128, which takes both of those out
of the picture for a week of rehearsals. What they cannot do is survive a
restart: the cache lives *inside* the uvicorn process, so a reboot, a crash or a
deliberate restart empties it no matter how the variables are set. **Warm again
after every restart.**

PIDs from the 2026-09-10 restart: backend window **37452** (uvicorn worker
**41008**), frontend window **36736** (vite **34392**). These are the processes
holding the current warm cache — do not stop them. (Both earlier sets are gone
along with their caches: 2026-09-09 backend window 54648 / worker 26168 and
frontend window 74556 / vite 75828; 2026-09-08 backend window 33220 / worker
29148 and frontend window 68816 / vite 45348.) Yours will differ after any
restart; note them so you can stop the right windows afterwards.

Wait for `http://127.0.0.1:8000/api/health` to answer 200, then run the FALLBACK
gate before anything else:

```powershell
Select-String -Quiet -Path 'docs\validation\demo-backend.log' -Pattern "Using hardcoded fallback ruleset"
```

`False` means the database is reachable and the demo may proceed. `True` means
the rulesets came from the reduced hardcoded table — stop, fix `.env`, restart.

Neither `/api/health` nor the startup log echoes the two cache values back, so
there is nothing to read that confirms the backend picked them up. The proof
that matters is the pre-warm's own closing line: 63 of 63 entries verified.

**Restart = repeat this whole section, then Pre-warm.** The analysis cache lives
inside the uvicorn process, so restarting the backend empties it and every
number in the walkthrough becomes a cold multi-minute run.

---

## Before you start

Two files must exist. Neither is in git; both hold secrets, so check for them
without printing them.

**`.env` in the repo root** must define, by name:

| Key | What it is |
| --- | --- |
| `SUPABASE_URL` | The project's Supabase base URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side key. The backend reads rules and storage with it |
| `SUPABASE_JWKS_URL` | `<SUPABASE_URL>/auth/v1/.well-known/jwks.json`. Without it every signed-in endpoint returns 500 |

**`frontend\.env`** must define four keys:

| Key | What it is |
| --- | --- |
| `VITE_SUPABASE_URL` | Same project URL as above |
| `VITE_SUPABASE_ANON_KEY` | The browser-safe publishable key. The service-role key will not work here — Supabase refuses it from a browser |
| `VITE_DEV_AUTH_EMAIL` | `dev@bim-guard.local` |
| `VITE_DEV_AUTH_PASSWORD` | The shared dev account password |

`frontend\.env.example` ships the email and password. The URL and anon key are
placeholders you must fill from the team's shared values — copying the example
unchanged leaves sign-in returning `401 Invalid API key`.

Check both files exist and that each names the keys it should, without showing
any value:

```powershell
Test-Path .env
Test-Path frontend\.env
(Get-Content .env)          | ForEach-Object { ($_ -split '=')[0] } | Where-Object { $_ -match '^\w' }
(Get-Content frontend\.env) | ForEach-Object { ($_ -split '=')[0] } | Where-Object { $_ -match '^\w' }
```

Check the ports you need are free. Another session or an earlier backend may
still hold one:

```powershell
netstat -ano | Select-String ":8000 |:5173 "
```

If something is listening, find out what before killing it:

```powershell
Get-Process -Id <pid> | Select-Object Id, ProcessName, Path
```

---

## Start

**Backend — from the repo root, not from `app\`.** The working directory is how
`python-dotenv` finds `.env`; start it anywhere else and `SUPABASE_URL` is unset,
so the rule catalogs fall back to `_FALLBACK_RULESETS` — a reduced hardcoded
table with 8 galvanic materials instead of the stored 20, and 4 environment
classes instead of 7. The demo would still run and would still show verdicts;
they would be scored from the wrong table.

```powershell
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Confirm it came up on the database rather than the fallback — check the logs for
any `Using hardcoded fallback ruleset` line. The demo may proceed only if none
appears:

```powershell
Select-String -Quiet -Path docs\validation\demo-backend.log -Pattern "Using hardcoded fallback ruleset"
```

This returns `True` if the fallback was used (stop, fix `.env`, start again) or
`False` if the database is reachable. Alternatively watch the startup log for
lines reading `static_data_assets?...asset_key=eq.ruleset:BIMGUARD-GC-001 ... 200 OK`.

**Frontend — from `frontend\`:**

```powershell
cd frontend
npm run dev
```

Open **http://127.0.0.1:5173/** and click **Sign in as dev test user** on the
login screen. The button only appears in dev builds and only when
`VITE_DEV_AUTH_EMAIL` and `VITE_DEV_AUTH_PASSWORD` are set. It signs in with a
real Supabase password grant — the backend still verifies the JWT against the
JWKS, so nothing about authentication is bypassed.

---

## Pre-warm

Every engine chip combination is its own cache entry. Warm them before the
audience is watching, or unticking a chip mid-demo starts a fresh multi-minute
run.

**This is the one step that runs from the repo root, not the worktree** — it is
the fixed script that lives on `main`, pointed at the worktree's backend:

```powershell
uv run python scripts/prewarm_demo.py --base-url http://127.0.0.1:8000 --piping 1917 1540 --seismic 1542
```

It signs itself in. Every `/api/analyze` route has required a bearer token since
`47cf29b`, so the script reads `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`,
`VITE_DEV_AUTH_EMAIL` and `VITE_DEV_AUTH_PASSWORD` out of `frontend\.env` and
runs the same Supabase password grant as the SPA's "Sign in as dev test user"
button. Nothing is passed on the command line and no token is printed. Supabase
issues a one-hour token and a full warm runs longer than that, so the script
re-mints every 40 minutes and again on any 401, retrying that one request once.

What to expect:

- **31 combinations per Piping project** (2⁵ − 1 — every chip selection except
  the empty one, which the Run button refuses).
- Per-entry lines as it goes, naming the project, the slug, the combination
  index, the elapsed seconds, and `WARMED` (the engines just ran), `HIT` (it was
  already cached) or, on the verification pass, `MISS`.
- A small project such as 1541 warms all 31 in about 3 minutes. West Riverside
  (1540) is minutes per uncached combination and is the long pole; warm it only
  if the demo will touch its chips, or pass `--combinations full-only` to warm
  just the default five-engine view.
- Seismic on 1542 takes about **10 minutes** on a cold cache (measured 577 s).
- The script then reads every entry back and closes with its summary. The line
  to check is:

  ```text
  Entries verified 63/63; misses 0; warm errors 0; token mints N; wall-clock N min
  ```

  63 = 31 combinations × two Piping projects (1917, 1540) + 1 Seismic (1542).
  Any `MISS` is an entry that will recompute in front of the audience; the
  script exits non-zero if there are any.
- **Budget two hours from cold.** Measured 2026-09-08: 120.7 minutes for the
  full 63 with 34 of them already cached. 1917 warms all 31 in about 10 minutes
  (15–26 s each); 1540 is 205–283 s per uncached combination and is the long
  pole; 1542 seismic took 809.6 s. `token mints 3` in that summary is the
  40-minute re-mint doing its job across a two-hour run, not a fault.
- Measured again 2026-09-09, this time genuinely cold (62 of the 63 uncached,
  after the restore): **145.1 minutes**, `Entries verified 63/63; misses 0;
  warm errors 0; token mints 4`. Per project: 1917 30 combinations warmed in
  8.9 min (mean 17.8 s), 1540 all 31 in 118.3 min (mean 229.0 s), 1542 seismic
  one entry in 14.8 min (888.7 s). Treat 1540 as two hours on its own.
- Measured again 2026-09-10, fully cold — all 63 entries WARMED, none already
  held: **158.7 minutes** (9,520 s), `Entries verified 63/63; misses 0; warm
  errors 0; token mints 4`. Per engine set: 1917 piping 31 combinations in
  **9.3 min** (560.7 s, mean 18.1 s, range 12.7–23.4 s), 1540 piping all 31 in
  **131.4 min** (7,884.4 s, mean 254.3 s, range 213.4–290.9 s), 1542 seismic
  the single entry in **14.6 min** (877.9 s). The verification pass read all 63
  back as hits in 3.3 min, every entry 2.8–4.3 s. Three cold runs now agree on
  the shape: 1917 under ten minutes, 1542 about a quarter of an hour, and 1540
  more than two hours on its own — budget two and a half hours for the lot.

**Do not let the laptop sleep during the warm.** Windows Modern Standby drops
the network, and a warm that loses it mid-run cannot re-mint its token and
fails every remaining request — that is exactly how the first attempt on
2026-09-08 ended, with `Entries verified 0/63` after 229 minutes. Entries
already cached survive standby, so a re-run picks up where it left off and only
recomputes what is missing, but it is far cheaper to keep the machine awake.

A hit on the second pass means the result is held in the backend's in-memory
store, keyed on the model's SHA-256 plus the engine selection. The store lives
**inside the uvicorn process**: restart the backend and every entry is gone. Do
not restart it after warming.

Warm reads measured straight afterwards on 2026-09-08, all `cached=true`: 1917
piping 4,282 ms, 1540 piping 6,127 ms, 1542 seismic 3,588 ms. **1540 is over
the 5 s the demo budgets for**, and it is payload, not recomputation — the
un-paged response is 27.2 MB of findings. The same call paged at `limit=50`,
which is what the results table actually renders, takes about 3.5 s, and a
repeat of the un-paged call measured 4,622 ms, so 1540 straddles the threshold.
Note also that every cached read carries a floor of roughly 3 s even for a
50-row page.

With the two cache variables set as the start section shows, entries last 30
days and the store holds 128 of them, so the 63 warmed here sit well inside both
limits and a third Piping project could be warmed in full without evicting
anything. Start the backend *without* those variables and you are back to the
defaults — 24 hours and 64 entries — where 63 leaves a single slot free and the
next thing analysed evicts a demo entry.

---

## The walkthrough

### 1. Piping audit on the data-bearing project (1917)

Start on the Dashboard after sign-in. Its Project Registry table is the former
ALL PROJECTS list. The stats tiles take 5–8 s to fill on this build
(`/api/dashboard/stats`, known limitation, raised with Osama) — open project
1917 from the registry immediately; do not wait for the tiles.

Then **Compliance Audit → Piping**, project *BIMGUARD Demo — Hospital MEP
(data)*. The page loads its stored result on mount — no need to press Run Audit.

Expect: **1,988 findings** over 420 elements, stat cards reading TOTAL FINDINGS
1,706, CRITICAL 10, HIGH RISK 168, MEDIUM RISK 1,206, LOW RISK 322, DATA QUALITY
282.

Per engine (Critical / High / Medium / Low / Data Quality):

| Engine | Crit | High | Medium | Low | DQ | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GC-001 | 0 | 0 | 56 | 322 | 42 | 420 |
| CC-001 | 0 | 70 | 308 | 0 | 42 | 420 |
| MC-001 | 10 | 64 | 220 | 0 | 126 | 420 |
| MM-001 | 0 | 0 | 146 | 0 | 36 | 182 |
| XM-001 | 0 | 34 | 476 | 0 | 36 | 546 |

- **Five engine chips** (GC-001, CC-001, MC-001, MM-001, XM-001) are lit. Each
  is a separate compliance kernel reading rules from the database.
- **Untick a chip** — say XM-001 — and the table reloads from cache. Tick it
  back to restore.
- **Severity filter**: switch to Critical to show the 10 MC-001 verdicts. All
  ten are Condensate Drain elements, which run at ~30 °C and therefore land in
  the Legionella danger band `T2_DANGER` (25–45 °C, CIBSE TM13:2013).
- **CSV** downloads the asset register: **1,988 rows** — 1,706 verdicts plus 282
  data-quality notes, every assessed element covered.
- **BCF 2.1** downloads **1,384 topics** — Medium (1,206) + High (168) +
  Critical (10). BCF carries Medium and above only, because the rulesets define
  a Low verdict as "asset register only — no BCF issue" and a data-quality note
  is a modelling gap for the BIM coordinator rather than a coordination task to
  assign in Revit or Solibri.

This is the project to demo GC-001 provenance on: 151 of its 420 elements
declare a second material in `Pset_BimGuardCouple.SecondaryMaterial`, so their
findings carry `galvanic_couple = bimetallic_pair_from_model` and a real
`material_a`/`material_b` pair. The other 227 scored elements show
`single_material_self_couple`, and 42 are data-quality notes with no couple at
all.

Open one finding's Details to show the citations and the provenance fields —
`material_source`, `environment_source`, `ruleset_version` (e.g.
`BIMGUARD-CC-001 v1.0.0`), and on GC-001 the `galvanic_couple` basis.

### 2. Piping on a real model with no materials (1540)

Switch the project selector to *FINAL AUDIT Piping WR Plumb IFC4* — West
Riverside hospital plumbing, IFC4, 23.8 MB, **8,539 piping elements**.

Expect: **29,181 findings, all of them Data Quality**. Stat cards read TOTAL
FINDINGS 0 / CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 0 / DATA QUALITY 29,181.

This is the point worth making out loud: the model associates no material with
any element, so the engines return *Undetermined* rather than inventing a
verdict. Each note names the check and the reason —
`material_unresolved` for GC-001 and CC-001, `hydraulics_unavailable` for
MC-001. Exporting BCF here yields **0 topics**, which is correct: there is
nothing above Low to coordinate.

### 3. Seismic on 1542

Switch to the **Seismic** tab, project *FINAL AUDIT Seismic WR Federated*. It
loads its stored result on mount once the cache is warm; on a cold backend it
shows Run Audit — this is why pre-warm precedes the demo.

Expect: **2,937 clashes** — 783 Critical, 314 High, 1,840 Medium. The federation
is two models, `west_riverside_hospital_plumb_ifc4.ifc` and
`west_riverside_hospital_str_ifc4.ifc`: **2,051** clashes are within the
plumbing model and **886** are cross-model, pipework against structure. Each
cross-model finding names both files in `source_model` and
`clashing_source_model`, so a coordinator knows which model to open.

Each row carries the real measured overlap volume and the clearance that was
applied (200.0 mm, EN 1998-1:2020 + DIN 4149:2022).

### 4. Export and validate

CSV from the Seismic page: **2,937 rows**, every one carrying
`overlap_volume_mm3` and `clearance_mm`. BCF: **2,937 topics**.

Validate the archive in front of the audience if it helps:

```powershell
uv run python scripts/validate_bcf_corpus.py --roots <folder containing the .bcf>
```

Expect `0` XSD violations and every Component `IfcGuid` a 22-character IFC GUID.

---

## If something goes wrong

**Signed-in pages break; `/api/auth/me` or saving a project returns 500.**
Restart the backend, then re-run the pre-warm — the restart empties the cache.
This was seen once (audit F12) after two long analyses on one process and could
not be reproduced in three long runs the next morning, so treat it as a restart,
not a diagnosis. Check first that `SUPABASE_JWKS_URL` is set: if it is missing,
*every* signed-in request returns 500 from the first one onward, which is a
configuration fault rather than this one.

**The results page sits spinning for minutes.** The cache was emptied — the
backend restarted, or the entry aged past its TTL. Re-run the pre-warm for that
project. A cold five-engine run on West Riverside is 108–140 seconds; a cold
federated seismic run is about 10 minutes.

**BCF downloads with 0 topics.** Correct behaviour when the project has no
Medium, High or Critical verdicts — West Riverside (1540) is exactly this case.
Show the CSV instead: it carries the full asset register including the
data-quality notes. To put Low verdicts or notes in a BCF anyway, add
`&include_low=true&include_data_quality=true` to the export URL.

**Sign-in button does nothing / `401 Invalid API key`.** `frontend\.env` is
missing or still holds the example's placeholder anon key. Fill it from the
team's shared values.

**A model over ~50 MB will not attach.** Known limit, see below.

---

## Restoring a deleted demo project

Deleting a project from the Project Registry is immediate and irreversible
through the UI. Restoring one is a database insert plus a re-upload, and it only
works if the row comes back with **the same id** and the models with **the same
bytes**: the analysis cache is keyed on `project_id + slug + the model's
SHA-256 + the engine selection` (`app/services/analysis_cache.py`, `CacheKey`).
A restore that let the database allocate a fresh id — which is exactly what
`POST /api/projects` does — would be a different project to every cache entry,
every recorded audit number and every BCF topic id.

1. **Insert the rows with their original ids.**
   `docs/validation/sql/20260909_restore_projects_1540_1542.sql` is the worked
   example, for 1540 and 1542. Paste it into the Supabase SQL Editor and run it
   once; it is guarded, so a second run changes nothing and a half-restored pair
   raises rather than being papered over. `projects.id` is
   `generated by default as identity`, so an explicit id needs no
   `OVERRIDING SYSTEM VALUE`, and the sequence is already past these ids and is
   not touched. Every column's value is cited in the file's header against the
   migration or the `create_project` line it comes from.
2. **Re-attach the models through the API**, not by editing `ifc_file_path` by
   hand: `POST /api/projects/{id}/upload`, multipart field `files` repeated once
   per model, plus `primary_index`. This is the call the SPA's upload modal
   makes (`frontend/src/lib/api.ts`, `uploadIfcFiles`), and it writes the
   `project_ifc_files` rows a federated seismic run reads.
   1540 takes `west_riverside_hospital_plumb_ifc4.ifc` alone; 1542 takes that
   same plumbing model **plus** `west_riverside_hospital_str_ifc4.ifc` — the
   pair the 6 Sept audit federated, the 69.7 MB mech model having been rejected
   413.
   **Check `GET /api/projects/{id}/files` before posting this.** The route
   appends; it does not replace. Running it against a project whose models are
   already attached leaves 1540 holding two copies of the plumbing model and
   1542 holding four — and because a seismic cache key is a SHA-256 over *all*
   of a project's models, that silently moves 1542 off its 2,937 clashes. If
   the models are already there, verify rather than re-post: download each one
   back through `GET /api/projects/{id}/files/{file_id}/ifc` and compare its
   SHA-256 with the local file. Confirmed byte-identical on 2026-09-10 —
   file 207 on 1540, files 208 and 209 on 1542.
3. **Warm the cache again.** Same-id and same-bytes is what *allows* the warm
   entries to be reachable; it does not resurrect them. The cache lives inside
   the uvicorn process, so if the backend has restarted since they were made
   they are gone regardless, and Pre-warm has to run from the top.

---

## Known limitations

State these plainly if asked; every one is measured, not estimated.

- **`scripts/prewarm_demo.py` could not authenticate — fixed on `main` in
  `43780b5`.** It sent no `Authorization` header, and `47cf29b` made every
  `/api/analyze` route require one, so on 2026-09-08 all 63 warm requests
  returned `HTTP 401` and nothing was cached. It now mints and re-mints the dev
  token itself. The fix is on `main`, not in the `fmp-demo` worktree, which is
  why Pre-warm is the one step that runs from the repo root.
- **The Project Registry has a live per-row Delete with a weak confirmation.**
  On 2026-09-08 at 21:58 five projects were deleted by hand through the SPA
  (`DELETE /api/projects/{id}` → 204: 322, 1540, 1541, 1591, 1542), two of them
  — 1540 and 1542 — steps in this walkthrough. They were restored on 2026-09-09
  with their original ids; see *Restoring a deleted demo project* above. 1541,
  1591 and 322 were not restored. **During the demo, touch only the Audit
  action.**
- **The Dashboard stats tiles take 5–8 s** and the SPA re-requests
  `/api/dashboard/stats` roughly every 40 s for as long as the tab is open,
  including while you are inside a project. Measured over 80 minutes on
  2026-09-08: 142 requests, median 6.8 s, slowest 13.1 s. Raised with Osama;
  `386ff7b` does not fix it on this build. It costs nothing you can see once
  you are inside a project, but it is why the Dashboard itself feels slow.
- **Migration `20260907202655_add_org_code_to_organizations.sql` is in the build
  but not applied to Supabase, and is not needed for the demo.** Only
  new-organisation creation needs it, which the walkthrough never does. Do not
  apply it this week.
- **An export link carries the access token captured when its row rendered.**
  Supabase rotates the token about hourly. Interacting with the results table
  rebuilds the link, so this is invisible in normal use — but if the page has
  sat untouched for over an hour, click Run Audit again before clicking Export.

- **MC-001 produces no verdicts without hydraulic data.** 8,539 of 8,539
  elements on West Riverside and 4 of 4 on the MEP scenario returned
  `hydraulics_unavailable`. No *real-world* model in the corpus carries flow
  velocity, dead-leg length or operating temperature. The generated demo model
  (`scripts/generate_demo_mep_model.py` → `data/test_hospital_mep_demo.ifc`)
  does carry them, and the parser reads `FlowVelocity`, `OperatingTemperature`
  and `DeadLegLength` from the Psets — so demonstrate MC-001 on that model, and
  be straight that the data is authored rather than found in the wild.
- **MC-001 temperature classes depend on a manually-applied migration.**
  `supabase/migrations/20260905220000_mc001_temperature_bounds.sql` supplies the
  numeric `t_min`/`t_max` bounds; without them the live catalog exposes only
  `T5_UNKNOWN` and temperature cannot be classified. The bounds are live now —
  all six classes load and `temperature_bounds_missing` is empty.
  Migration 20260905220000_mc001_temperature_bounds.sql applied manually via the Supabase SQL Editor on 6 Sept 2026; not in Supabase's migration history.
- **GC-001 scores a real bimetallic couple only where the model declares a
  second material** — the parser reads it from the `SecondaryMaterial` property
  into `material_b`. With one material GC-001 scores a self-couple and records
  that basis as `single_material_self_couple` rather than staying silent; the
  generated demo model declares secondary materials, the real models do not.
- **The seismic score is a band-derived placeholder** — Critical 0.9, High 0.7,
  Medium 0.4, Low 0.1. The band is the finding; the score is not an independent
  measurement.
- **`/api/analyze/*` has no authentication.** Anyone who can reach the port can
  run an analysis and download any project's findings. Do not expose the demo
  machine's port 8000 to an untrusted network.
- **Models over roughly 50 MB cannot be attached.** Supabase storage returns
  `413 Payload too large`; the upload endpoint answers 500 and attaches the
  models that fit. This is why the seismic demo federates two West Riverside
  models rather than three — the 69.7 MB mechanical model will not upload
  (audit F4).
- **Repeated runs of the same model can differ by about two issues** — 29,181 /
  29,183 / 29,181 measured across three identical runs of project 1540, varying
  in MM-001's count. Band totals are unaffected (audit F5).
- **The 500-after-long-runs fault (F12) is unreproduced.** Three forced
  recomputes over 6.8 minutes on 2026-09-06 produced no failure, zero 5xx and
  zero tracebacks. If it recurs, restart and keep the backend log.
- **XM-001 is nearly silent on this corpus** — 1 issue across 8,539 elements on
  West Riverside, 0 on the 4-element MEP scenario.
- **The federated clash count is not comparable to the previously recorded
  19,552**, which covered three buildings; this federation is two models.
- **Parser non-determinism on West Riverside (1540)** — two elements may flip
  material assignment between identical runs; measured as MM-001 DQ count
  variation 29,181 / 29,183 / 29,181 across three sequential parses (audit F2).
- **`resolve_material` does not normalise underscores** — keys like
  `SS_316_passive` resolve to `carbon_steel` instead of their series entries.
  Latent on the demo corpus (0 affected of 420 elements on 1917; audit F3).
- **MC-001 issues Critical verdicts when material is absent** — the gate passes
  elements with no material, so they score with `material_source: absent` and
  `material_confidence: none`. By design; wording in the report should flag it
  (audit F6).
- **Absent flow velocity is scored as stagnant** — elements with temperature but
  no velocity coerce to 0.0 m/s and then to the worst class. Structurally
  reachable but 0 occurrences on this corpus (audit F8).
- **BCF export does not implement steps 11–12** — camera frame from bounding
  box and status-change comments are not generated.
- **"Missing bearer token" appears when viewing an audit with no project
  selected** — select a project name from the dropdown to recover.
