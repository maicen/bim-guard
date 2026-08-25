# ISO 19650 Findings — Navisworks Clash Intelligence Platform

**Source repository:** `Aspiring-Design-3D-Consultancy-Ltd/nw-clash-platform` (public)
**Inspected:** 25 Aug 2026 · shallow clone, default branch
**Repo shape:** 96 files — `working.html` (18,585 lines, the entire application), 18 governance markdown docs, 8 `.cline` role definitions, 56 Playwright specs, 2 Node scripts.

---

## 0. Where the ISO 19650 material actually lives

**All of it is in `working.html`.** Nothing else in the repository defines naming conventions, metadata standards, or export rules.

This is worth stating plainly because the task brief expected `docs/governance/` to hold information-delivery specifications. It does not. Those 18 documents govern the *AI engineering workflow* used to build the application — decision logs, investigation logs, workflow routing, release snapshots. Their "role-based" language (`DECISION_LOG.md:24`, `WORKING_AGREEMENTS.md:163`, `.cline/roles/*`) refers to **architect / developer / QA-investigator / release-manager** engineering roles, **not** to ISO 19650 information management roles or RBAC over project information.

Grep confirms the split: `19650` appears **17 times, all in `working.html`**, and zero times in any `.md` file.

Likewise absent from the whole repository: **EIR, BEP, MIDP, TIDP, handover, asset information requirements, COBie, IDS**. `EIR` and `BEP` appear only as prose inside `working.html` — one UI info-box (line 15203) telling the user to align their codes with their EIR and BEP, and two demo clash records citing "BEP §4.2" as a tolerance note. There is no EIR/BEP artefact, template, or data structure.

---

## 1. Naming conventions

### 1.1 The five presets

Defined in the `S.iso.conventions` array (`working.html:829–833`). Every one carries `id`, `name`, `preset`, `separator`, `format`, `description`.

| id | Name | Sep | Format string |
|---|---|---|---|
| `iso19650` | ISO 19650-1:2018 | `_` | `{project}_{originator}_{volume}_{level}_{type}_{disciplines}_{sequence}_{status}_{revision}` |
| `iso19650_date` | ISO 19650-1:2018 + Date | `_` | `{project}_{originator}_{volume}_{level}_{type}_{disciplines}_{sequence}_{status}_{revision}_{date}` |
| `simple` | Simple — Source vs Service | `_` | `[{clashType}]_{sourceA}_vs_{system}_{zone}_{date}` |
| `descriptive` | Descriptive — Full detail | `-` | `{sourceA}-vs-{sourceB}-[{system}]-{zone}-{date}` |
| `uniclass` | Uniclass 2015 | `_` | `{project}_{originator}_{classA}_{classB}_{level}_{sequence}_{date}` |

**Default:** `activeConvention:'iso19650_date'` (line 828) — described in-source as "recommended default".

Presets carry `preset:true` and **cannot be deleted or edited** in the UI; only custom conventions get Edit/✕ controls. Deleting the active custom convention falls back to `iso19650_date` (line 15677).

### 1.2 Token vocabulary — 19 tokens

`{project}` `{originator}` `{volume}` `{level}` `{type}` `{disciplines}` `{disciplineA}` `{disciplineB}` `{sequence}` `{status}` `{revision}` `{date}` `{sourceA}` `{sourceB}` `{system}` `{zone}` `{clashType}` `{classA}` `{classB}`

Substitution is a naive global regex replace per key (`applyConvFormat`, ~line 7300): unmatched tokens resolve to empty string, so a malformed format silently yields a name with empty segments.

> **Gap worth noting:** the Uniclass 2015 convention is offered, but `classA` and `classB` are **hardcoded to empty strings** in the value map (`genTestName`, line ~7274: `classA:'',classB:''`). Selecting Uniclass therefore produces a name with two empty segments. The convention is present in the UI but not actually wired to any classification data. There is no Uniclass or OmniClass code table anywhere in the repo.

### 1.3 Base codes (the `S.iso` object, line 827)

| Field | Default | Meaning |
|---|---|---|
| `projCode` | empty (required, e.g. `A1234`) | Unique project identifier |
| `origCode` | empty (required, e.g. `BIM01`) | Author / issuing organisation |
| `typeCode` | `CO` | Information type |
| `suitability` | `S1` | CDE status |
| `revision` | `01` | `P01` = preliminary, `C01` = contract |
| `separator` | `_` | `_` or `-` (custom conventions also allow `.`) |

**Type codes:** `CO` Coordination · `RP` Report · `MO` Model.

### 1.4 Master code library

`ISO_MASTER_CODES` (line 852) is explicitly commented *"never modified — project codes are separate"*. Projects select from it or add custom codes scoped to that project only.

- **Disciplines (12):** S Structural · M MEP/Mechanical · A Architectural · E Electrical · C Civil · F Fire Protection · G Geotechnical · L Landscape · I Interior Design · P Public Health/Plumbing · T Telecommunications · X External Works
- **Volumes (9):** ZZ Multi-system/All · 10 Structural Frame · 20 Architectural · 30 MEP Services · 40 Electrical · 50 Civil/External · 60 Façade/Envelope · 70 Infrastructure · XX Not applicable
- **Levels (18):** ZZ All · B03–B01 Basements · G00 Ground · M00 Mezzanine · L01–L10 · RF Roof · XX Not applicable

Cited in the UI as *ISO 19650-1 §12, Annex A*.

### 1.5 CDE status codes — "ISO 19650-2 Table 1"

Rendered as a 7-row reference grid (line ~15278), each mapped to a platform status:

| Code | Meaning | Platform status | Colour |
|---|---|---|---|
| `S0` | Work in progress | New | `#94A3B8` |
| `S1` | Suitable for coordination | Active | `#FF8000` |
| `S2` | Suitable for information | Reviewed | `#00AEEF` |
| `S3` | Suitable for review | — | `#2563EB` |
| `A` | Authorised for use | Approved | `#00B050` |
| `B` | Partially authorised | — | `#FFC000` |
| `S7` | Archived / superseded | Resolved | `#6B7280` |

Only `S0 S1 S2 S3 A` are selectable in the Suitability dropdown; `B` and `S7` appear in the reference table only.

### 1.6 Date formats

Five options in the name generator: `YYMMDD` (default) · `DDMMYY` · `YYYYMMDD` · `DD-MM-YY` · `ISO` (`YYYY-MM-DD`).

### 1.7 Dual output

`genTestName()` emits **two** names simultaneously:

- **ISO name** — the convention applied, for information containers and BCF export
- **Navisworks label** — informal, `[H] SourceA vs SourceB [System] Zone YYMMDD`, where the type tag is `[H]` Hard · `[CL]` Clearance · `[DUP]` Duplicate

The `simple` convention is explicitly annotated *"not ISO compliant"* — it exists for Navisworks test names, which have their own practical constraints.

---

## 2. Metadata requirements

### 2.1 BCF 2.1 topic metadata

Consistent across all six BCF writer sites (lines 6847, 12704, 13256, 13272, 13353, 17489):

| Field | Required | Value |
|---|---|---|
| `Topic@Guid` | yes | generated GUID |
| `Topic@TopicType` | yes | always `Clash` |
| `Topic@TopicStatus` | yes | clash status |
| `Title` | yes | `<UID> — <name>` |
| `Priority` | yes | defaults `Medium` |
| `CreationDate` | yes | ISO 8601 + `+00:00` |
| `CreationAuthor` | yes | `bcfAuthor()` |
| `Description` | yes | disciplines, elements, element IDs, penetration in mm |
| `AssignedTo` | conditional | **omitted entirely when blank** |
| `Labels/Label` | group exports only | group name |
| `Viewpoints/ViewPoint` | yes | `viewpoint.bcfv` + snapshot |

A source comment at line 12590 records that `CreationAuthor` is *"REQUIRED by BCF 2.1 spec"* and was previously missing — a fixed defect. A second comment (line 17487) records empty `IfcGuid` attributes as an **XSD violation**; `Components` are written with `IfcGuid=""` and the Navisworks element ID in `AuthoringToolId` instead, because Navisworks XML carries no IFC GUIDs.

### 2.2 Element identity attributes

`working.html:7544` defines the element-ID attribute resolution order, built from field incidents:

```
['Element ID', 'GUID', '要素ID', '要素 ID', '元素 ID', 'Entity Handle']
```

Covering English, Japanese and Chinese Navisworks installs plus AutoCAD entity handles. `.idSrc` records which attribute actually yielded the value.

### 2.3 Clash register fields (CSV export, line 17469)

```
ID, Name, Test, Discipline A, Discipline B, Element A, Element B,
Penetration, Status, Priority, Assigned To, Notes, Date
```

### 2.4 Project-level metadata

`project.bcfp` carries only `ProjectId` (GUID) + `Name`. Application state holds `projName` and `projWeek` — no client, no location, no contract reference.

---

## 3. Export standards

| Export | Format | Filename pattern |
|---|---|---|
| Clash register | CSV | `ClashRegister_<date>.csv` |
| Issues | BCF 2.1 ZIP | ISO name from active convention |
| Group issues | ZIP | `<primaryTestName> Groups.zip` |
| Report | HTML | `<projName>_Report_<date>.html` |
| Weekly report | HTML | `<projName>_WeeklyReport_<date>.html` |
| Slides | PPTX | — |
| Backup | JSON | — |

`projName` is sanitised with `replace(/[^\w]/g,'_')`.

**BCF 2.1 container structure:** `bcf.version` (`VersionId="2.1"`, `DetailedVersion 2.1`, `xsi:noNamespaceSchemaLocation="version.xsd"`) · `project.bcfp` · then per-topic GUID folders holding `markup.bcf`, `viewpoint.bcfv`, `snapshot.png`.

Stated interoperability target (About box, line 15420): **BIMCollab Zoom, Autodesk BIM Collaborate, Revit native BCF plugins**.

**No IFC export exists** — the platform consumes Navisworks Clash Detective XML and emits BCF/CSV/PPTX/PDF/HTML. There is no IFC naming standard setting anywhere in the repo.

---

## 4. Role and permission framework

`working.html:876–905`. This is genuine RBAC over application actions — the only RBAC in the repository.

**Four roles, ranked:**

| Role | Label | Rank |
|---|---|---|
| `admin` | Administrator | 4 |
| `manager` | Space Planning Manager | 3 |
| `projectManager` | Project Manager | 2 |
| `viewer` | Viewer | 1 |

**Thirteen permissions**, each a minimum rank:

| Permission | Min rank |
|---|---|
| `data_manager`, `settings_full`, `role_management` | 4 — Admin only |
| `edit_register`, `import_xml`, `bcf_tools`, `add_clash`, `export_csv`, `export_bcf`, `settings_project`, `board_move`, `edit_notes` | 3 — Manager+ |
| `export_reports` | 2 — Project Manager+ |

Enforced by `can(perm)` (rank comparison) and `applyRoleUI()`, which hides any element carrying `data-minrole` and re-renders toolbar actions. Viewers see a read-only notice: *"Read-only access — contact your BIM Coordinator to make changes"*.

Authentication is a 4-digit PIN, SHA-256 hashed, stored in browser `localStorage`.

---

## 5. Compliance claim and its limits

The About box (line 15417) claims compliance with **BS EN ISO 19650-1:2018** and **BS EN ISO 19650-2:2018** *information container naming conventions* — scoped to naming, not to the standard as a whole. That scoping is accurate to what is implemented.

**Present:** naming conventions, code libraries, CDE status mapping, BCF 2.1 metadata, RBAC.

**Absent:** EIR/BEP artefacts · MIDP/TIDP delivery planning · handover / asset information requirements · document classification taxonomy (Uniclass tokens exist but resolve empty) · COBie · IDS · any IFC naming standard · federation strategy · security-mindedness (ISO 19650-5).

---

## 6. What was carried into BIMGUARD

The BIMGUARD **Settings → ISO 19650 Compliance** section reproduces, as configurable fields: the five naming conventions and their format strings, the 19-token vocabulary, the base-code fields, the type/suitability/revision code sets, the discipline/volume/level master library counts, the CDE status table, the BCF 2.1 metadata field lists, the export filename patterns, and the four-role permission matrix.

Three fields are **BIMGUARD additions, not found in the Navisworks repo**, and are labelled as such in the UI: the IFC naming standard dropdown, the information delivery plan template, and the document classification taxonomy. BIMGUARD is IFC-native where the Navisworks platform is not, so an IFC naming setting has somewhere to attach here; the other two fill gaps section 5 identifies.
