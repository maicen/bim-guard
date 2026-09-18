# Security Controls

This page inventories BIM-Guard's current security controls, written down explicitly for
compliance evidence (SOC 2 / ISO 27001) rather than left implicit in code. See
[docs/planning](../planning/) (if present) or the compliance roadmap for the broader
certification plan this supports.

## Authentication

- All API access is authenticated via Supabase-issued JWTs, verified server-side against
  Supabase's published JWKS (never trusted from the client without signature verification).
  See [app/auth.py](../../app/auth.py).
- No unconditional auth bypass exists anywhere in the codebase. The only development
  shortcut is a seeded, low-trust Supabase Auth test account (`dev@bim-guard.local`) that
  still authenticates through the real password-grant + JWT verification path — see
  [CLAUDE.md](../../CLAUDE.md)'s "Local Dev Sign-In" section.

## Authorization (RBAC & multi-tenancy)

- Organizations and memberships establish tenant boundaries
  (`supabase/migrations/20260904235344_create_organizations_and_memberships.sql`).
- A superadmin-configurable role-permission matrix (owner/admin/member) gates every
  role-sensitive action platform-wide, with per-organization overrides
  (`supabase/migrations/20260915091908_create_role_permissions.sql`,
  [app/services/permission_service.py](../../app/services/permission_service.py)).
- Project- and document-level access grants scope visibility below the organization level
  (`supabase/migrations/20260905123245_project_and_document_access_grants.sql`).

## Row-Level Security

Every application table has RLS enabled. The backend connects with the Supabase
service-role key (which bypasses RLS), so enabling RLS on each table exists specifically to
**deny all direct access from anon/authenticated clients** — every read/write must go
through the FastAPI layer's own authorization checks, never a direct table query from the
browser. This is the consistent pattern across every migration in `supabase/migrations/`
(see `role_permissions`, `parsing_engine_instances`, and the new `audit_log` table below
for representative examples), and was actively maintained, not bolted on once — see
`supabase/migrations/20260902144438_fix_github_repositories_rls_and_cde_function_search_path.sql`.

## Audit logging

`public.audit_log` (`supabase/migrations/20260915100001_create_audit_log.sql`) is an
append-only record of sensitive mutations: organization role changes, role-permission
matrix edits, and project/document deletion. Written via
[app/services/audit_log_service.py](../../app/services/audit_log_service.py), called from
the API route layer where the authenticated actor is known
(`app/api/organizations.py`, `app/api/permissions.py`, `app/api/documents.py`,
`app/api/projects.py`). The table grants `service_role` `SELECT, INSERT` only — no
`UPDATE`/`DELETE` — so entries cannot be altered or removed even by a compromised backend
process. Readable via `GET /api/audit-log` (superadmin-only,
[app/api/audit_log.py](../../app/api/audit_log.py)).

This currently covers a representative set of high-sensitivity mutations, not every
mutation in the system. Extending coverage (e.g. document/ruleset access-grant changes,
LLM/parsing engine credential edits) is a straightforward follow-up: call
`AuditLogService.record(...)` from the relevant route after the mutation succeeds.

## CI security scanning

`.github/workflows/security-scan.yml` runs on every push/PR to `main`:

- `pip-audit` against the resolved Python dependency set (`uv sync` + `uvx pip-audit --local`).
- `npm audit` against `frontend/`'s dependency tree.
- `gitleaks` secret scanning across the diff.

## Encryption

- **In transit**: all Supabase Postgres and Auth traffic is TLS-terminated by Supabase;
  the FastAPI app itself sits behind HTTPS in production deployment.
- **At rest**: Supabase-managed Postgres storage is encrypted at rest by the platform.

No BIM-Guard-specific encryption-at-rest configuration exists beyond what Supabase provides
by default — this is documented here as a control the team relies on, not one implemented
in this codebase.

## Data deletion (GDPR "right to be forgotten")

`ProjectsService.delete_project` (`app/services/projects_service.py`) cascades deletion of
a project's IFC models, client documents, graph-database nodes, and RDF triplestore data.
`DocumentService.delete_document_with_file` (`app/services/documents_service.py`)
best-effort removes stored files alongside the document row.

Project deletion now reaches:

- **Graph data** (Neo4j/Kuzu): IFC element nodes are ingested with a `project_id` property
  (`app/modules/ifc_reader/ifc_graph.py`). `GraphService.delete_project_data(project_id)`
  removes them — `Neo4jDatabaseProvider.delete_by_project` runs a single label-agnostic
  `MATCH (n {project_id: ...}) DETACH DELETE n`; `KuzuDatabaseProvider.delete_by_project`
  iterates the strictly-typed node-table catalog and deletes from only the tables that
  actually carry a `project_id` column, leaving global reference data (`Rule`, `IfcClass`)
  untouched.
- **RDF triplestore**: each project's triples live in their own named graph
  (`https://bimguard.io/graphs/{project_id}`) in `GraphTriplestoreService`.
  `delete_project_graph(project_id)` clears that graph without touching any other
  project's.

Both are wired into `ProjectsService` via `bind_graph_services(...)`, called from
`app/bootstrap.py` after the graph/triplestore services are constructed (the same
late-binding pattern `ModelsService.bind_project_mirror` already uses). Both are
best-effort: a graph/triplestore failure is logged, not raised, so it never blocks
deleting the project row itself.

Document deletion does not need the same treatment — documents are never ingested into
the graph or triplestore, only projects' IFC models are.

## SSRF hardening

`app/services/ssrf_protection.py` validates outbound URLs (e.g. GitHub repo imports,
Google Drive imports) against private/internal address ranges before the backend fetches
them.

## HTTP security headers

`SecurityHeadersMiddleware` (`app/main.py`) sets `X-Content-Type-Options`,
`X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and a `Content-Security-Policy`
(including `worker-src` and `child-src` allowing `'self'` and `blob:` for `@thatopen/fragments`
3D viewer web workers, and `https://static.cloudflareinsights.com` for Cloudflare Web Analytics)
on every response.
