# BIM-Guard demo runbook

For the person driving the demo. Every command is PowerShell, run from the repo
root unless a step says otherwise. Numbers quoted here were measured on
2026-09-05/06 and are recorded in `docs/validation/final-audit-2026-09-06.md`.

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

Confirm it came up on the database rather than the fallback — the second number
must be 0:

```powershell
curl.exe -s http://127.0.0.1:8000/api/health
```

Watch the startup log for lines reading
`static_data_assets?...asset_key=eq.ruleset:BIMGUARD-GC-001 ... 200 OK`. A line
reading `Using hardcoded fallback ruleset` means the backend cannot see the
database: stop, fix `.env`, start again.

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

```powershell
uv run python scripts/prewarm_demo.py --piping <PIPING_PROJECT_ID> --seismic <SEISMIC_PROJECT_ID>
```

For the projects used below that is:

```powershell
uv run python scripts/prewarm_demo.py --piping 1541 1540 --seismic 1542
```

What to expect:

- **31 combinations per Piping project** (2⁵ − 1 — every chip selection except
  the empty one, which the Run button refuses).
- A small project such as 1541 warms all 31 in about 3 minutes. West Riverside
  (1540) is minutes per uncached combination; warm it only if the demo will
  touch its chips, or pass `--combinations full-only` to warm just the default
  five-engine view.
- Seismic on 1542 takes about **10 minutes** on a cold cache (measured 577 s).
- The script then reads every entry back. Each must print `cached=true`. Any
  line prefixed `WARN` is an entry that will recompute in front of the audience;
  the script exits non-zero if there are any.

`cached=true` on the second pass means the result is held in the backend's
in-memory store, keyed on the model's SHA-256 plus the engine selection. The
store lives **inside the uvicorn process**: restart the backend and every entry
is gone. Do not restart it after warming. Entries last 24 hours
(`BIMGUARD_CACHE_TTL_SECONDS`, default 86400) and the store holds 64 of them
(`BIMGUARD_CACHE_ENTRIES`), so a morning warm-up survives an afternoon demo.

Mind the ceiling: two Piping projects warmed in full plus one Seismic project is
31 + 31 + 1 = 63 entries against a limit of 64, and the 65th eviction is the
least recently used. Warming a third Piping project in full will push earlier
entries out — use `--combinations full-only` for the projects whose chips you
will not touch, or raise `BIMGUARD_CACHE_ENTRIES` before starting the backend.

---

## The walkthrough

### 1. Piping audit on the data-bearing project (1541)

Open **Compliance Audit → Piping**, project *FINAL AUDIT Piping MEP Scenario*.
The page loads its stored result on mount — no need to press Run Audit.

Expect: **14 findings**, stat cards reading TOTAL FINDINGS 9, CRITICAL 0, HIGH
RISK 0, MEDIUM RISK 5, LOW RISK 4, DATA QUALITY 5.

- **Five engine chips** (GC-001, CC-001, MC-001, MM-001, XM-001) are lit. Each
  is a separate compliance kernel reading rules from the database.
- **Untick a chip** — say XM-001 — and the table reloads from cache. Tick it
  back to restore.
- **Severity filter**: switch to Medium to show only the 5 scored verdicts.
- **CSV** downloads the asset register: 14 rows, every assessed element plus
  every data-quality note.
- **BCF 2.1** downloads **5 topics** — the 4 CC-001 and 1 MM-001 Medium
  verdicts. BCF carries Medium and above only, because the rulesets define a Low
  verdict as "asset register only — no BCF issue" and a data-quality note is a
  modelling gap for the BIM coordinator rather than a coordination task to
  assign in Revit or Solibri.

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
loads its stored result on mount.

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

## Known limitations

State these plainly if asked; every one is measured, not estimated.

- **MC-001 produces no verdicts without hydraulic data.** 8,539 of 8,539
  elements on West Riverside and 4 of 4 on the MEP scenario returned
  `hydraulics_unavailable`. No *real-world* model in the corpus carries flow
  velocity, dead-leg length or operating temperature. The generated demo model
  (`scripts/generate_demo_mep_model.py` → `data/test_hospital_mep_demo.ifc`)
  does carry them, and the parser reads `FlowVelocity`, `OperatingTemperature`
  and `DeadLegLength` from the Psets — so demonstrate MC-001 on that model, and
  be straight that the data is authored rather than found in the wild.
- **MC-001 temperature classes are pending a migration.**
  `supabase/migrations/20260905220000_mc001_temperature_bounds.sql` supplies the
  numeric `t_min`/`t_max` bounds; until it is applied the live catalog exposes
  only `T5_UNKNOWN` with no bounds, so temperature cannot be classified.
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
