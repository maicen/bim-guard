# BIM-Guard Data Processing Agreement (Template — Draft)

> **Status: DRAFT — requires legal review before use.**
> This is a template DPA drafted to reflect BIM-Guard's actual current architecture
> (Supabase-backed multi-tenant SaaS, configurable LLM/parsing sub-processors, RBAC —
> see `docs/architecture/security-controls.md`). It follows the standard shape of a
> GDPR Article 28 processor agreement but is **not** a substitute for review by
> qualified legal counsel, and is not legal advice. Bracketed placeholders (`[...]`)
> must be completed, and the sub-processor list (Annex II) must be kept current as
> organizations enable/disable integrations.

This Data Processing Agreement ("**DPA**") is entered into between:

- **[Company Legal Name]** ("**Processor**", "**we**"), and
- **[Customer Legal Name]** ("**Controller**", "**you**"),

(each a "**Party**") and forms part of the agreement governing your use of the
BIM-Guard Service (the "**Principal Agreement**"). Capitalized terms not defined here
have the meaning given in the Principal Agreement.

## 1. Subject matter and duration

This DPA governs the Processor's processing of personal data on the Controller's
behalf in connection with the Service, for the duration of the Principal Agreement.

## 2. Nature and purpose of processing

The Processor processes personal data to provide the BIM-Guard compliance platform:
account/authentication management, project and document storage, IFC model analysis,
rule extraction, and related features described in the Principal Agreement.

## 3. Categories of data subjects

- The Controller's authorized users (employees, contractors) who access the Service.
- Individuals whose personal data may be embedded in uploaded content (e.g. names in
  IFC file metadata, document authorship metadata) — solely as incidental content of
  files the Controller chooses to upload; the Processor does not target or specifically
  process this category.

## 4. Categories of personal data

- Identity and contact data: name, email address.
- Authentication data: Supabase-issued identifiers, session metadata.
- Usage data: role assignments, actions taken within the Service (see `public.audit_log`
  in `docs/architecture/security-controls.md`).
- Any personal data incidentally contained within uploaded IFC models or documents.

No special category data (Art. 9 GDPR) is intentionally processed by the Service. If the
Controller uploads content containing special category data, the Controller is solely
responsible for ensuring it has a lawful basis to do so and for informing the Processor
in advance so appropriate safeguards can be assessed.

## 5. Processor obligations

The Processor shall:

1. Process personal data only on the Controller's documented instructions (including
   regarding international transfers), unless required otherwise by law.
2. Ensure persons authorized to process the personal data are subject to confidentiality
   obligations.
3. Implement appropriate technical and organizational measures per Art. 32 GDPR — see
   Annex I.
4. Not engage a sub-processor without the Controller's prior general or specific
   authorization — see Section 6 and Annex II.
5. Assist the Controller, taking into account the nature of processing, in responding
   to data subject rights requests (Art. 12–23 GDPR).
6. Assist the Controller with its Art. 32–36 obligations (security, breach
   notification, DPIAs), taking into account the information available to the
   Processor.
7. At the Controller's choice, delete or return all personal data after the end of the
   provision of services, and delete existing copies, unless retention is required by
   law. See Section 8 (deletion mechanics).
8. Make available to the Controller information necessary to demonstrate compliance
   with this DPA, and allow for and contribute to audits, including inspections,
   conducted by the Controller or an auditor mandated by the Controller, subject to
   reasonable notice, frequency limits, and confidentiality terms [negotiate specifics].
9. Notify the Controller without undue delay after becoming aware of a personal data
   breach affecting the Controller's data. [Set a specific notification SLA, e.g.
   "within 72 hours of becoming aware," and confirm against actual incident-response
   capability before finalizing.]

## 6. Sub-processors

The Controller provides general authorization for the Processor to engage the
sub-processors listed in **Annex II**. The Processor shall:

- Impose data protection obligations on each sub-processor equivalent to those in this
  DPA.
- Remain fully liable to the Controller for a sub-processor's performance of its
  obligations.
- Notify the Controller of any intended addition or replacement of a sub-processor,
  giving the Controller the opportunity to object on reasonable grounds. [Set a specific
  notice period, e.g. 30 days, and an objection/termination mechanism.]

BIM-Guard's parsing-engine and LLM-provider integrations are per-organization
configurable (`app/services/parsing_engine_instances_service.py`,
`app/services/llm_provider_instances_service.py`); Annex II should be read alongside the
specific integrations the Controller's own organization has enabled, since enabling an
optional integration (a specific LLM provider, GitHub import, Google Drive import) adds
that vendor as a sub-processor for that Controller's data.

## 7. International transfers

Where personal data is transferred outside the EEA/UK/Switzerland (e.g. to a
sub-processor hosted elsewhere), the Processor shall ensure an appropriate transfer
mechanism is in place — Standard Contractual Clauses, an adequacy decision, or another
valid mechanism under Chapter V GDPR. [Confirm and document per sub-processor in
Annex II; this varies by which integrations a given Controller has enabled and by the
Supabase project's hosting region.]

## 8. Deletion and return of data

On termination, or on the Controller's request, the Processor shall delete or return
personal data as instructed. As implemented in the Service:

- `ProjectsService.delete_project` cascades deletion of a project's IFC models, client
  documents, graph-database records (Neo4j/Kùzu), and RDF triplestore data.
- `DocumentService.delete_document_with_file` deletes a document row and its stored
  file.
- `MembershipService.delete_organization` / `UserAdminService.delete_user` remove
  organization/account records.

See `docs/architecture/security-controls.md` for the current technical detail and any
known gaps at the time of reading (that document is kept up to date; this DPA should be
reviewed against it periodically rather than treated as a standalone source of truth on
deletion mechanics).

## 9. Liability

[Standard liability/indemnification clauses — align with the Principal Agreement's
liability cap and insurance terms; requires negotiation between the Parties.]

## 10. Governing law

[Specify, consistent with the Principal Agreement.]

---

## Annex I — Technical and organizational measures

Summarized from `docs/architecture/security-controls.md` (kept as the canonical source;
update there first, then reflect changes here):

- Authentication via Supabase-issued JWTs, verified server-side against JWKS.
- Role-based access control with organization-scoped, superadmin-configurable
  permission matrix.
- Row-Level Security enabled on every database table, denying all direct
  anon/authenticated client access — all access goes through the authenticated API layer.
- Append-only audit logging (`public.audit_log`) of sensitive mutations (role changes,
  permission edits, project/document deletion), insert-only privileges (no
  update/delete, even for the application's own service role).
- Encryption in transit (TLS) and at rest (Supabase-managed Postgres).
- SSRF protection on outbound integration fetches.
- Standard HTTP security headers (CSP, X-Frame-Options, etc.).
- CI security scanning on every change: dependency vulnerability scanning
  (`pip-audit`, `npm audit`) and secret scanning (`gitleaks`).

## Annex II — Sub-processors

| Sub-processor | Purpose | Location / hosting | Transfer mechanism |
|---|---|---|---|
| Supabase | Database, authentication, object storage | [Supabase project region] | [confirm] |
| Docling (hosted or self-hosted) | Document parsing | [depends on deployment] | [confirm if applicable] |
| Anthropic / OpenAI / Google / OpenRouter (whichever the Controller's org has enabled) | LLM inference for rule extraction and Q&A | [per-provider] | [confirm per provider] |
| Neo4j Aura (if enabled) | Graph database for spatial analysis | [confirm] | [confirm if applicable] |
| GitHub (if the Controller links a repo) | IFC model import from source control | [confirm] | [confirm if applicable] |
| Google Drive (if the Controller links it) | Document import | [confirm] | [confirm if applicable] |

This table must be kept current as an organization enables or disables integrations, and
reviewed against `app/services/llm_provider_instances_service.py` and
`app/services/parsing_engine_instances_service.py` configuration at the time of each
customer's onboarding and periodically thereafter.
