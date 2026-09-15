# BIM-Guard Privacy Policy (Draft)

> **Status: DRAFT — requires legal review before publication.**
> This document was drafted from the current BIM-Guard codebase and architecture
> (`app/`, `frontend/`, `supabase/migrations/`) to give counsel an accurate starting
> point, not to serve as-is. Bracketed placeholders (`[...]`) must be filled in, and the
> whole document must be reviewed by qualified legal counsel — including counsel
> licensed in every jurisdiction where BIM-Guard has customers or processes personal
> data — before it is published or relied upon. It is not legal advice.

**Last updated:** [DATE]

## 1. Who we are

[Company Legal Name] ("BIM-Guard", "we", "us") operates the BIM-Guard compliance
platform (the "Service") at [company domain]. [Company Legal Name] is the data
controller for personal data collected through the Service's own marketing/account
surfaces, and acts as a **data processor** on behalf of our organization customers for
the project, document, and rule data those customers upload and manage within the
Service — see Section 8.

Contact: [privacy@company-domain] · [Registered business address]
Data Protection Officer (if appointed): [DPO name/contact, or "not currently required
under Art. 37 GDPR — reassess if processing volume/type changes"]

## 2. Scope

This policy covers personal data processed through:

- Account creation and authentication (Supabase Auth — Google OAuth and email/password).
- The BIM-Guard web application (`frontend/`) and its API (`app/api/`).
- Data you upload to the Service: IFC building models, specification documents, and any
  personal data those files or their metadata happen to contain (e.g. author names in
  IFC file headers, document metadata, uploader identity captured in audit trails).

It does not cover third-party sites we merely link to, or data our customers' own
end users provide directly to those customers outside the Service.

## 3. What personal data we collect

| Category | Examples | Source |
|---|---|---|
| Account data | Name, email address, authentication identifier (Supabase user id) | You, at sign-up (Google OAuth or email/password) |
| Organization/role data | Organization membership, role (owner/admin/member), group assignment | You or your organization admin |
| Usage/audit data | Actions taken (role changes, deletions, permission edits), timestamps, IP-derived request metadata | Automatically, via `public.audit_log` and request logging |
| Uploaded content | IFC models, specification documents (PDF, etc.), and any personal data embedded in them | You, when you upload |
| Support/communications data | Anything you send us directly (e.g. support requests) | You |

We do **not** intentionally collect payment card data, government ID numbers, or health
information through the Service in its current form. If a customer's organization
processes such data in uploaded documents, that customer — not [Company Legal Name] —
determines the lawful basis and appropriate safeguards for doing so; see Section 8.

## 4. How we use personal data

- To provide, maintain, and secure the Service (authentication, authorization, audit
  logging — see `docs/architecture/security-controls.md`).
- To communicate with you about your account or the Service.
- To investigate and prevent abuse, fraud, or security incidents.
- To comply with legal obligations.

We do not sell personal data. We do not use uploaded project/document content to train
third-party foundation models beyond what is strictly necessary to fulfil an
organization-configured LLM feature (see Section 6) — [confirm actual policy on training
data opt-out with each configured LLM provider before finalizing this sentence].

## 5. Legal basis (EU/UK GDPR)

- **Contract** (Art. 6(1)(b)): processing account and project data to provide the
  Service you've signed up for.
- **Legitimate interests** (Art. 6(1)(f)): security monitoring, audit logging, abuse
  prevention.
- **Consent** (Art. 6(1)(a)): where required, e.g. optional marketing communications.
- **Legal obligation** (Art. 6(1)(c)): where we must retain or disclose data to comply
  with law.

## 6. Sub-processors and third-party services

BIM-Guard relies on the following categories of sub-processor. The exact set is
configurable per organization (parsing engines and LLM providers are admin-configured —
see `app/services/parsing_engine_instances_service.py`,
`app/services/llm_provider_instances_service.py`), so this table lists the categories and
current default/available options rather than a single fixed list. See
[data-processing-agreement.md](data-processing-agreement.md) for the contractual
sub-processor list format offered to enterprise customers.

| Category | Purpose | Current option(s) |
|---|---|---|
| Database, authentication, object storage | Core application data, user auth, file storage | Supabase |
| Document parsing | Extracting text/structure from uploaded PDFs | Docling (hosted or self-hosted instance, per-org configurable) |
| LLM inference | Rule extraction, natural-language Q&A (Digital Inspector) | Configurable per organization: Anthropic, OpenAI, Google (Gemini), OpenRouter, or a self-hosted Ollama instance |
| Graph database (optional) | Spatial/topological analysis | Neo4j (Aura or self-hosted), or embedded Kùzu (no external sub-processor) |
| Source control import (optional) | Importing IFC models from a linked GitHub repo | GitHub |
| Document import (optional) | Importing documents from a linked Google Drive | Google |

For any organization that enables an optional integration (GitHub import, Google Drive
import, a specific LLM provider), that provider becomes a sub-processor for that
organization's data. [Confirm each vendor's DPA/SCC status before finalizing — Anthropic,
OpenAI, Google, and Supabase all publish standard DPAs; verify current terms rather than
assuming.]

## 7. International data transfers

[Fill in based on where Supabase and each configured sub-processor actually host data —
this depends on the Supabase project region and which LLM/parsing providers an
organization has enabled. Where a transfer leaves the EU/UK/Switzerland, it relies on
[Standard Contractual Clauses / adequacy decision / other safeguard — confirm per
sub-processor].]

## 8. If you are an end user of a BIM-Guard customer

If you access BIM-Guard because an organization (your employer or a firm you work with)
has an account, that organization is the **data controller** for the project and
document data it manages in the Service, and [Company Legal Name] is a **data
processor** acting on that organization's instructions (see
[data-processing-agreement.md](data-processing-agreement.md)). Questions about how your
data is used should go to that organization first.

## 9. Data retention

- Account data: retained while your account is active, deleted on account/organization
  deletion (`MembershipService.delete_organization`, `UserAdminService.delete_user`).
- Project/document data: retained until deleted by the organization; deletion cascades
  to IFC models, client documents, graph-database records, and triplestore data (see
  `ProjectsService.delete_project`, documented in `docs/architecture/security-controls.md`).
- Audit log entries (`public.audit_log`): append-only, retained for [X months/years —
  set a retention period appropriate to your audit/compliance needs] before periodic
  purge. [Not yet automated — track as a follow-up if a fixed retention period is
  required.]

## 10. Your rights

Subject to applicable law (GDPR, CCPA, etc.), you may have the right to:

- Access the personal data we hold about you.
- Correct inaccurate data.
- Request deletion ("right to be forgotten").
- Object to or restrict certain processing.
- Data portability.
- Withdraw consent, where processing is consent-based.

To exercise these rights, contact [privacy@company-domain]. If your data is managed by
an organization using BIM-Guard (Section 8), we will typically direct you to that
organization, or assist them in fulfilling your request under our processor obligations.

## 11. Security

See `docs/architecture/security-controls.md` for the technical and organizational
measures currently in place (authentication, RBAC, RLS, audit logging, encryption in
transit/at rest, CI security scanning).

## 12. Changes to this policy

[Describe your change-notification process — e.g. "We will post material changes here
and, where required by law, notify account owners by email."]

## 13. Contact

[Company Legal Name]
[Registered address]
[privacy@company-domain]
