"""
BIMGUARD AI — BCF Generator Module
Standard: BIM Collaboration Format (BCF) 2.1 — buildingSMART International
Output: BCF-ZIP file containing XML topics, viewpoints, and snapshots
"""

import datetime
import io
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from xml.sax.saxutils import escape as _escape


@dataclass
class BCFIssue:
    guid: str
    title: str
    description: str
    priority: str  # Critical / Major / Normal / Minor
    status: str  # Active / Open / Info
    assigned_to: str
    due_date: str
    labels: list
    component_guid: str
    component_name: str
    service_type: str
    floor: str
    risk_band: str
    mechanism: str  # galvanic / crevice / combined
    risk_score: float
    mitigation: str
    camera_x: float = 0.0
    camera_y: float = 0.0
    camera_z: float = 5.0
    target_x: float = 0.0
    target_y: float = 0.0
    target_z: float = 0.0
    # ISO 19650 metadata fields
    project_code: str = ""
    originator: str = ""
    suitability_code: str = ""
    revision_code: str = ""
    cde_state: str = ""
    #: Further IFC GlobalIds implicated in the finding (e.g. the cathode of a
    #: galvanic couple). They are selected and coloured in the viewpoint
    #: alongside ``component_guid``; blanks and duplicates are dropped.
    related_component_guids: list = field(default_factory=list)
    #: ``Topic/CreationAuthor``. Names the engine that raised the finding and,
    #: where the finding carries one, its ruleset revision, so a coordinator
    #: can tell which kernel and which rule revision produced the topic.
    #: Empty falls back to :data:`DEFAULT_CREATION_AUTHOR` rather than naming
    #: an engine that did not run.
    creation_author: str = ""
    #: ``Topic/@TopicType``. One of :data:`TOPIC_TYPES`. Defaults to ``Issue``,
    #: which is right for a compliance verdict; a clash and a data-quality note
    #: are different kinds of thing and say so.
    topic_type: str = "Issue"
    #: Source models this finding came from, as
    #: ``[{"filename": str, "date": str}, ...]``. One ``Header/File`` is
    #: written per entry, so a cross-model clash names both models instead of
    #: one placeholder. ``date`` is the model's upload timestamp and is
    #: omitted where unknown. Empty falls back to
    #: :data:`PLACEHOLDER_MODEL_FILENAME`.
    source_files: list = field(default_factory=list)
    #: Standards this finding was assessed against, as
    #: ``[{"description": str, "referenced_document": str}, ...]``. One
    #: ``Topic/DocumentReference`` is written per entry.
    #: ``referenced_document`` is a URL and is omitted when empty — the
    #: repository holds no URL or DOI for any of these standards, and
    #: inventing one would be a fabricated citation.
    document_references: list = field(default_factory=list)
    #: The finding as JSON text. When set, it is written into the topic folder
    #: as :data:`SNIPPET_FILENAME` and referenced by ``Topic/BimSnippet``, so
    #: the archive carries the machine-readable record behind the prose and a
    #: consumer need not re-request the JSON export to get it.
    snippet_json: str = ""


#: Used when a caller supplies no ``creation_author``. Deliberately generic:
#: naming a specific engine here is what made every archive claim GC-001/CC-001
#: authorship, seismic clashes included.
DEFAULT_CREATION_AUTHOR = "BIMGUARD AI"

#: The complete set of ``TopicType`` values BIMGUARD emits, and the only values
#: ``extensions.xsd`` will declare. A coordinator filtering by type gets three
#: meaningful buckets rather than one.
#:
#:   ``Clash``   a geometric interference — SB-001 seismic bracing clearance
#:   ``Issue``   a compliance verdict against a scored element
#:   ``Warning`` a data-quality note: something could not be assessed
TOPIC_TYPES: tuple[str, ...] = ("Clash", "Issue", "Warning")

#: The complete set of ``TopicStatus`` values BIMGUARD emits.
TOPIC_STATUSES: tuple[str, ...] = ("Open",)

#: The complete set of ``Priority`` values BIMGUARD emits, most severe first.
TOPIC_PRIORITIES: tuple[str, ...] = ("Critical", "Major", "Normal", "Minor")

#: ``BimSnippet/@SnippetType`` for the machine-readable finding record, and the
#: only snippet type BIMGUARD emits.
SNIPPET_TYPE = "JSON"

#: Name the snippet takes inside the topic folder.
SNIPPET_FILENAME = "finding.json"


def _utc_now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")


#: BCF 2.1 ``IfcGuid`` (markup.xsd / visinfo.xsd): exactly 22 characters from
#: the IFC base-64 alphabet. The commas in the published XSD pattern are a
#: quirk of the upstream schema, not part of the alphabet.
_IFC_GUID_RE = re.compile(r"^[0-9A-Za-z_$]{22}$")

#: BCF 2.1 ``Guid`` (topic, comment and viewpoint identifiers): hyphenated UUID.
_BCF_GUID_RE = re.compile(
    r"^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$"
)

#: Namespace for deriving stable topic GUIDs from non-UUID finding ids such
#: as ``BGR-0007``. Fixed so the same finding always exports to the same topic.
_TOPIC_GUID_NAMESPACE = uuid.UUID("6f1c0a5e-8d2b-4c47-9a3e-2b7d1e4f9c01")


def is_ifc_guid(value) -> bool:
    """Return True when *value* is a schema-legal BCF ``IfcGuid`` (22-char IFC GlobalId)."""
    return bool(_IFC_GUID_RE.match(str(value or "")))


def bcf_topic_guid(raw_id) -> str:
    """Return a schema-legal BCF ``Guid`` for a finding identifier.

    A value that already is a UUID (optionally wrapped in braces) is returned
    verbatim -- case included, because callers such as the pipeline and the
    BCF sync service compare topic GUIDs as strings against what they minted.
    Anything else -- ``BGR-0007``, an IFC GlobalId, a label -- is mapped to a
    version-5 UUID under a fixed namespace, so the mapping is deterministic:
    re-exporting the same finding yields the same topic GUID, which is what
    BCF round-tripping tools key on. An empty id carries no identity to
    preserve and gets a fresh random UUID instead, so two blank findings never
    collapse into one topic folder.
    """
    text = str(raw_id or "").strip().strip("{}")
    if _BCF_GUID_RE.match(text):
        return text
    if not text:
        return str(uuid.uuid4()).upper()
    return str(uuid.uuid5(_TOPIC_GUID_NAMESPACE, text)).upper()


def _ifc_guid_attr(value) -> str:
    """Render the optional ``IfcGuid`` attribute for a viewpoint ``Component``.

    The attribute is omitted when *value* is not a real IFC GlobalId: an empty
    string, a UUID or a label like ``COMP-001`` would each fail the schema's
    22-character restriction and get the whole archive rejected by strict
    readers. The raw value still travels in ``AuthoringToolId`` so nothing is
    lost, and a ``Component`` without ``IfcGuid`` is legal in visinfo.xsd.
    """
    return f' IfcGuid="{_xml_attr(value)}"' if is_ifc_guid(value) else ""


def _component_guids(issue: "BCFIssue") -> list[str]:
    """Return the component ids a viewpoint should select, primary first.

    Blank and duplicate ids are dropped. The list is never empty: with no ids
    at all it holds one blank entry, which renders as a ``Component`` without
    ``IfcGuid`` so ``Selection`` and ``Color`` keep their mandatory child.
    """
    seen: set[str] = set()
    guids: list[str] = []
    for raw in [issue.component_guid, *(issue.related_component_guids or [])]:
        guid = str(raw or "").strip()
        if guid and guid not in seen:
            seen.add(guid)
            guids.append(guid)
    return guids or [""]


def _xml_text(value) -> str:
    """Escape a value for safe inclusion as BCF XML element text content."""
    return _escape(str(value))


def _xml_attr(value) -> str:
    """Escape a value for safe inclusion inside a double-quoted BCF XML attribute."""
    return _escape(str(value), {'"': "&quot;"})


#: Emitted when a caller supplies no ``source_files``. Kept only so callers
#: that predate the field still produce a well-formed Header; every live path
#: names the real model.
PLACEHOLDER_MODEL_FILENAME = "BIMGUARD_AI_Model.ifc"


def _header_xml(issue: "BCFIssue", project_attr: str) -> str:
    """Render ``Markup/Header`` naming the model(s) the finding came from.

    ``markup.xsd`` declares ``File`` with ``maxOccurs="unbounded"``, so a
    cross-model finding names both models rather than picking one. The
    sequence inside ``File`` is ``Filename, Date, Reference``; ``Date`` is an
    ``xs:dateTime`` and is emitted only when the caller supplied one, since an
    invented upload time is a fabricated value.
    """
    files = [f for f in (issue.source_files or []) if (f or {}).get("filename")]
    if not files:
        files = [{"filename": PLACEHOLDER_MODEL_FILENAME}]

    blocks = []
    for entry in files:
        date = str(entry.get("date") or "").strip()
        date_xml = f"\n      <Date>{_xml_text(date)}</Date>" if date else ""
        blocks.append(
            f"    <File{project_attr}>\n"
            f"      <Filename>{_xml_text(entry['filename'])}</Filename>"
            f"{date_xml}\n"
            f"    </File>"
        )
    joined = "\n".join(blocks)
    return f"  <Header>\n{joined}\n  </Header>"


def _document_references_xml(issue: "BCFIssue", topic_guid: str) -> str:
    """Render ``Topic/DocumentReference`` for each standard the finding cites.

    ``markup.xsd`` places ``DocumentReference`` after ``Description`` and
    ``BimSnippet`` and before ``RelatedTopic``; the sequence inside it is
    ``ReferencedDocument, Description``.

    ``ReferencedDocument`` is a URL and is emitted only when the caller has a
    real one. The repository holds no URL or DOI for any of the standards in
    ``app.constants.NOTEBOOK_STANDARDS``, so today every reference carries the
    ``Description`` alone: naming the standard and clause truthfully, rather
    than pointing at an invented link. ``isExternal`` follows suit — false
    when nothing external is referenced.

    Guids are derived from the topic and the description so a regenerated
    archive reuses them instead of churning identifiers on every export.
    """
    blocks = []
    for entry in issue.document_references or []:
        description = str((entry or {}).get("description") or "").strip()
        if not description:
            continue
        url = str(entry.get("referenced_document") or "").strip()
        ref_guid = str(uuid.uuid5(_TOPIC_GUID_NAMESPACE, f"{topic_guid}:{description}")).upper()
        inner = f"      <ReferencedDocument>{_xml_text(url)}</ReferencedDocument>\n" if url else ""
        blocks.append(
            f'    <DocumentReference Guid="{_xml_attr(ref_guid)}" '
            f'isExternal="{"true" if url else "false"}">\n'
            f"{inner}"
            f"      <Description>{_xml_text(description)}</Description>\n"
            f"    </DocumentReference>"
        )
    return ("\n".join(blocks) + "\n") if blocks else ""


def _markup_xml(
    issue: BCFIssue, index: int, viewpoint_guid: str, topic_guid: str | None = None
) -> str:
    """Generate BCF 2.1 markup.bcf XML for one issue.

    Element order follows the buildingSMART ``markup.xsd`` sequences exactly:
    ``Markup`` is ``Header, Topic, Comment, Viewpoints`` and ``Topic`` places
    ``DueDate`` ahead of ``AssignedTo``. XSD sequences are ordered, so a
    document carrying every required element in the wrong order is still
    rejected — reordering here is not cosmetic.

    ``topic_guid`` is the schema-legal ``Topic/@Guid``; it defaults to
    :func:`bcf_topic_guid` of ``issue.guid`` and is passed explicitly by
    :func:`generate_bcf` so the topic folder and the attribute always agree.
    """
    topic_guid = topic_guid or bcf_topic_guid(issue.guid)
    # Enrich labels with ISO 19650 suitability, originator, and CDE state tags if provided
    combined_labels = list(issue.labels or [])
    if issue.suitability_code and f"Suitability:{issue.suitability_code}" not in combined_labels:
        combined_labels.append(f"Suitability:{issue.suitability_code}")
    if issue.originator and f"Originator:{issue.originator}" not in combined_labels:
        combined_labels.append(f"Originator:{issue.originator}")
    if issue.cde_state and f"CDE:{issue.cde_state}" not in combined_labels:
        combined_labels.append(f"CDE:{issue.cde_state}")

    labels_xml = "\n".join(f"    <Labels>{_xml_text(label)}</Labels>" for label in combined_labels)

    # An absent due date is omitted rather than emitted as a bare
    # "T00:00:00Z", which is not a valid xs:dateTime.
    due_date_xml = (
        f"    <DueDate>{_xml_text(issue.due_date)}T00:00:00Z</DueDate>\n"
        if issue.due_date
        else ""
    )

    # ISO 19650 comment block
    iso_info_str = (
        f"\nISO 19650 Container: {issue.project_code or 'PRJ'}-{issue.originator or 'BIMG'} | "
        f"Suitability: {issue.suitability_code or 'S0'} | Rev: {issue.revision_code or 'P01.01'} | CDE State: {issue.cde_state or 'WIP'}"
        if (issue.suitability_code or issue.originator or issue.project_code)
        else ""
    )

    # When the caller's id was not a UUID (e.g. "BGR-0007") the topic GUID is
    # derived from it; keep the original in the comment so reviewers can trace
    # the topic back to the finding it came from.
    source_id = str(issue.guid or "")
    source_id_str = (
        f"\nSource finding id: {source_id}" if source_id and source_id != topic_guid else ""
    )

    related = _component_guids(issue)[1:]
    related_str = f"Related components: {', '.join(related)}\n" if related else ""

    comment_body = _xml_text(
        "Issue automatically generated by BIMGUARD AI corrosion compliance engine."
        f"{iso_info_str}{source_id_str}\n"
        f"Mechanism: {issue.mechanism} | Risk score: {issue.risk_score:.4f} | Band: {issue.risk_band}\n"
        f"Component: {issue.component_name} ({issue.component_guid or 'no IFC GlobalId'})\n"
        f"{related_str}"
        f"Service type: {issue.service_type} | Floor/zone: {issue.floor}\n"
        f"Mitigation: {issue.mitigation}"
    )
    comment_guid = str(uuid.uuid4()).upper()

    # Header/File/@IfcProject is typed IfcGuid (22-char IFC GlobalId), not a
    # free-text project code. An ISO 19650 code such as "PRJ1" or "ZIG-001"
    # fails the length facet, so it is only emitted when it really is the
    # IfcProject's GlobalId; the code itself is already carried in the comment
    # body's ISO 19650 container line.
    project_attr = (
        f' IfcProject="{_xml_attr(issue.project_code)}"' if is_ifc_guid(issue.project_code) else ""
    )

    header_xml = _header_xml(issue, project_attr)
    doc_refs_xml = _document_references_xml(issue, topic_guid)

    # markup.xsd sequences Topic as ... Description, BimSnippet,
    # DocumentReference, RelatedTopic -- so the snippet precedes the references.
    # ReferenceSchema is a required element but no schema is published for this
    # payload, so it is emitted empty rather than pointing at a URL that does
    # not exist.
    snippet_xml = (
        f'    <BimSnippet SnippetType="{_xml_attr(SNIPPET_TYPE)}" isExternal="false">\n'
        f"      <Reference>{_xml_text(SNIPPET_FILENAME)}</Reference>\n"
        f"      <ReferenceSchema></ReferenceSchema>\n"
        f"    </BimSnippet>\n"
        if issue.snippet_json
        else ""
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Markup xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
{header_xml}
  <Topic Guid="{topic_guid}" TopicType="{_xml_attr(issue.topic_type or 'Issue')}" TopicStatus="{_xml_attr(issue.status)}">
    <ReferenceLink></ReferenceLink>
    <Title>{_xml_text(issue.title)}</Title>
    <Priority>{_xml_text(issue.priority)}</Priority>
    <Index>{index}</Index>
{labels_xml}
    <CreationDate>{_utc_now()}</CreationDate>
    <CreationAuthor>{_xml_text(issue.creation_author or DEFAULT_CREATION_AUTHOR)}</CreationAuthor>
    <ModifiedDate>{_utc_now()}</ModifiedDate>
{due_date_xml}    <AssignedTo>{_xml_text(issue.assigned_to)}</AssignedTo>
    <Description>{_xml_text(issue.description)}</Description>
{snippet_xml}{doc_refs_xml}  </Topic>
  <Comment Guid="{_xml_attr(comment_guid)}">
    <Date>{_utc_now()}</Date>
    <Author>BIMGUARD AI</Author>
    <Comment>{comment_body}</Comment>
  </Comment>
  <Viewpoints Guid="{_xml_attr(viewpoint_guid)}">
    <Viewpoint>viewpoint.bcfv</Viewpoint>
    <Snapshot>snapshot.png</Snapshot>
    <Index>0</Index>
  </Viewpoints>
</Markup>"""


#: The dataclass camera defaults. A BCFIssue still carrying all six means the
#: caller supplied no position, so there is no viewpoint to write.
_DEFAULT_CAMERA = (0.0, 0.0, 5.0, 0.0, 0.0, 0.0)


def _has_real_camera(issue: "BCFIssue") -> bool:
    """Report whether the caller supplied real camera coordinates.

    ``phase_6e_export`` supplies none, because no finding records the
    element's position or bounding box — the corrosion engines take a position
    as input but never write it onto the Issue, and the seismic path records
    its bounding boxes only inside the clash detector. Until one of those
    surfaces the geometry, a camera here would be invented.
    """
    return (
        issue.camera_x,
        issue.camera_y,
        issue.camera_z,
        issue.target_x,
        issue.target_y,
        issue.target_z,
    ) != _DEFAULT_CAMERA


def _viewpoint_xml(issue: BCFIssue, viewpoint_guid: str) -> str:
    """Generate BCF 2.1 viewpoint.bcfv XML with camera position and component selection.

    ``Components`` is an ordered sequence — ``ViewSetupHints, Selection,
    Visibility, Coloring`` — so ``Visibility`` must precede ``Coloring`` even
    though the two are independent in meaning.

    One ``Component`` is written per id from :func:`_component_guids`
    (``component_guid`` first, then ``related_component_guids``), in both the
    selection and the colouring. ``Component/@IfcGuid`` is only written when
    the id is a real 22-character IFC GlobalId (see :func:`_ifc_guid_attr`);
    the raw id always travels in ``AuthoringToolId``.
    """
    guids = _component_guids(issue)
    selection_xml = "\n".join(
        f"      <Component{_ifc_guid_attr(guid)}>\n"
        f"        <OriginatingSystem>BIMGUARD AI</OriginatingSystem>\n"
        f"        <AuthoringToolId>{_xml_text(guid)}</AuthoringToolId>\n"
        f"      </Component>"
        for guid in guids
    )
    coloring_xml = "\n".join(f"        <Component{_ifc_guid_attr(guid)}/>" for guid in guids)

    # PerspectiveCamera is optional in visinfo.xsd and is written only when the
    # caller supplied real coordinates. Left at the dataclass defaults it
    # produced the identical camera -- viewpoint (5, -8, 8) aimed at
    # (-5, 8, -8) -- on every topic in every archive, a position unrelated to
    # the element that would send a coordinator to the same spot 4,321 times.
    # Omitting it lets a viewer frame the selected components itself.
    camera_xml = (
        f"""
  <PerspectiveCamera>
    <CameraViewPoint>
      <X>{issue.camera_x + 5.0}</X>
      <Y>{issue.camera_y - 8.0}</Y>
      <Z>{issue.camera_z + 3.0}</Z>
    </CameraViewPoint>
    <CameraDirection>
      <X>{issue.target_x - issue.camera_x - 5.0}</X>
      <Y>{issue.target_y - issue.camera_y + 8.0}</Y>
      <Z>{issue.target_z - issue.camera_z - 3.0}</Z>
    </CameraDirection>
    <CameraUpVector>
      <X>0</X>
      <Y>0</Y>
      <Z>1</Z>
    </CameraUpVector>
    <FieldOfView>60</FieldOfView>
  </PerspectiveCamera>"""
        if _has_real_camera(issue)
        else ""
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<VisualizationInfo Guid="{_xml_attr(viewpoint_guid)}">
  <Components>
    <ViewSetupHints SpacesVisible="false"/>
    <Selection>
{selection_xml}
    </Selection>
    <Visibility DefaultVisibility="true"/>
    <Coloring>
      <Color Color="{_risk_colour(issue.risk_band)}">
{coloring_xml}
      </Color>
    </Coloring>
  </Components>{camera_xml}
</VisualizationInfo>"""


#: Band -> ARGB colour for the viewpoint's Coloring block.
_BAND_COLOURS: dict[str, str] = {
    "LOW": "FF107C10",
    "MEDIUM": "FFFF8C00",
    "HIGH": "FFC05000",
    "CRITICAL": "FFC00000",
}

#: Used for a band this table does not know.
UNKNOWN_BAND_COLOUR = "FF888888"


def _risk_colour(band: str) -> str:
    """Return the ARGB colour for ``band``, case-insensitively.

    The case fold is the fix for a silent defect: this table is keyed in upper
    case while ``Issue.band.value`` — what the exporter passes — is lower case
    ("medium"), so every lookup missed and every topic in every archive was
    coloured the grey fallback. Measured before the fix: 4,321 of 4,321 topics
    across the 1917 and 1542 demo archives were FF888888.
    """
    return _BAND_COLOURS.get(str(band or "").strip().upper(), UNKNOWN_BAND_COLOUR)


def _priority_int(priority: str) -> str:
    return {"Critical": "1", "Major": "2", "Normal": "3", "Minor": "4"}.get(priority, "3")


def _placeholder_png() -> bytes:
    """
    Returns a minimal valid 1×1 PNG as a placeholder snapshot.
    In production this would be a rendered viewpoint screenshot from the 3D viewer.
    """
    # Minimal 1×1 red PNG (valid PNG binary)
    import base64

    b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+h"
        "HgAHggJ/PchI6QAAAABJRU5ErkJggg=="
    )
    return base64.b64decode(b64)


def _extensions_xsd(issues: list["BCFIssue"]) -> str:
    """Build the ``extensions.xsd`` ``project.bcfp`` has always declared.

    ``project.bcfp`` names ``<ExtensionSchema>extensions.xsd</ExtensionSchema>``
    and the file was never written, so every archive referenced a schema it did
    not contain.

    BCF 2.1 leaves ``TopicType``, ``TopicStatus``, ``Priority``, ``TopicLabel``,
    ``SnippetType`` and ``Stage`` as unrestricted strings in ``markup.xsd`` and
    expects the project's own extension schema to enumerate them. This
    enumerates exactly the values this archive actually emits — computed from
    the issues, not a fixed list — so the schema cannot drift from the content.

    ``Stage`` is emitted with no enumerated values: BIMGUARD publishes none,
    because no project record carries a stage.
    """

    def enumeration(name: str, values) -> str:
        body = "\n".join(
            f'      <xs:enumeration value="{_xml_attr(v)}"/>' for v in values
        )
        inner = f"\n{body}\n    " if body else ""
        return (
            f'  <xs:simpleType name="{name}">\n'
            f'    <xs:restriction base="xs:string">{inner}</xs:restriction>\n'
            f"  </xs:simpleType>"
        )

    topic_types = sorted({i.topic_type or "Issue" for i in issues}) or list(TOPIC_TYPES)
    statuses = sorted({i.status for i in issues if i.status}) or list(TOPIC_STATUSES)
    priorities = sorted(
        {i.priority for i in issues if i.priority},
        key=lambda p: TOPIC_PRIORITIES.index(p) if p in TOPIC_PRIORITIES else 99,
    ) or list(TOPIC_PRIORITIES)
    labels = sorted({str(label) for i in issues for label in (i.labels or []) if label})
    snippet_types = sorted({SNIPPET_TYPE for i in issues if i.snippet_json})

    blocks = "\n".join(
        [
            enumeration("TopicType", topic_types),
            enumeration("TopicStatus", statuses),
            enumeration("Priority", priorities),
            enumeration("TopicLabel", labels),
            enumeration("SnippetType", snippet_types),
            enumeration("Stage", ()),
        ]
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"'
        ' elementFormDefault="qualified">\n'
        f"{blocks}\n"
        "</xs:schema>"
    )


def generate_bcf(issues: list[BCFIssue], filename: str = "BIMGUARD_AI_Issues.bcf") -> bytes:
    """
    Generates a BCF 2.1 compliant ZIP archive from a list of BCFIssue objects.

    Args:
        issues:   List of BCFIssue dataclass instances
        filename: Output filename (for reference only — returns bytes)

    Returns:
        BCF ZIP file as bytes — write to disk or offer as download
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # BCF version file (required by spec)
        zf.writestr(
            "bcf.version",
            """<?xml version="1.0" encoding="UTF-8"?>
<Version VersionId="2.1" xsi:noNamespaceSchemaLocation="version.xsd"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <DetailedVersion>2.1</DetailedVersion>
</Version>""",
        )

        # Project file
        project_guid = str(uuid.uuid4()).upper()
        zf.writestr(
            "project.bcfp",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<ProjectExtension xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Project ProjectId="{project_guid}">
    <Name>BIMGUARD AI — Corrosion Compliance Report</Name>
  </Project>
  <ExtensionSchema>extensions.xsd</ExtensionSchema>
</ProjectExtension>""",
        )

        # The schema project.bcfp has always declared. Written from the values
        # this archive actually emits, so it cannot drift from the content.
        zf.writestr("extensions.xsd", _extensions_xsd(issues))

        # One folder per issue. The folder name is the topic GUID (BCF 2.1
        # convention), which is derived from issue.guid when that is not
        # already a UUID so that the folder and Topic/@Guid always agree.
        for i, issue in enumerate(issues):
            topic_guid = bcf_topic_guid(issue.guid)
            folder = topic_guid + "/"
            viewpoint_guid = str(uuid.uuid4()).upper()
            zf.writestr(
                folder + "markup.bcf",
                _markup_xml(issue, i, viewpoint_guid, topic_guid=topic_guid),
            )
            zf.writestr(folder + "viewpoint.bcfv", _viewpoint_xml(issue, viewpoint_guid))
            zf.writestr(folder + "snapshot.png", _placeholder_png())
            if issue.snippet_json:
                zf.writestr(folder + SNIPPET_FILENAME, issue.snippet_json)

    return buf.getvalue()


def issues_from_results(results: list[dict]) -> list[BCFIssue]:
    """
    Converts BIMGUARD AI engine check results into BCFIssue objects.

    Args:
        results: List of dicts from run_compliance_checks()

    Returns:
        List of BCFIssue objects (filtered to Medium risk and above)
    """
    issues = []
    priority_map = {
        "LOW": "Minor",
        "MEDIUM": "Normal",
        "HIGH": "Major",
        "CRITICAL": "Critical",
    }
    status_map = {
        "LOW": "Info",
        "MEDIUM": "Open",
        "HIGH": "Open",
        "CRITICAL": "Active",
    }
    engineer_map = {
        "LOW": "BIM Manager",
        "MEDIUM": "Mechanical / Structural Engineer",
        "HIGH": "Lead Engineer",
        "CRITICAL": "Design Lead + Client Representative",
    }

    for r in results:
        band = r.get("overall_band", "LOW")
        if band == "LOW":
            continue  # Only raise issues for Medium and above

        days = {"MEDIUM": 21, "HIGH": 7, "CRITICAL": 2}.get(band, 21)
        due = (datetime.date.today() + datetime.timedelta(days=days)).isoformat()

        pos = r.get("position", (0, 0, 0))
        mech = r.get("dominant_mechanism", "galvanic")
        score = r.get("overall_score", 0)

        labels = [
            "BIMGUARD-AI",
            f"Risk-{band}",
            r.get("environment", "unknown"),
            mech.capitalize(),
            r.get("floor", ""),
        ]

        issues.append(
            BCFIssue(
                guid=str(uuid.uuid4()).upper(),
                title=f"[BIMGUARD-AI] {band} corrosion risk — {r.get('name', 'Component')}",
                description=(
                    f"Corrosion compliance failure detected by BIMGUARD AI.\n\n"
                    f"Component: {r.get('name', '')}\n"
                    f"Service type: {r.get('description', '')}\n"
                    f"Floor / zone: {r.get('floor', '')}\n"
                    f"Material A: {r.get('material_a', '')}\n"
                    f"Material B: {r.get('material_b', '')}\n"
                    f"Environment: {r.get('environment', '')}\n"
                    f"Galvanic score: {r.get('galvanic_score', 0):.4f} → {r.get('galvanic_band', '')}\n"
                    f"Crevice score:  {r.get('crevice_score', 0):.4f} → {r.get('crevice_band', '')}\n"
                    f"Overall score:  {score:.4f} → {band}\n"
                    f"Dominant mechanism: {mech}\n\n"
                    f"Required action: {r.get('action', '')}\n"
                    f"Mitigation: {r.get('mitigation', '')}\n\n"
                    f"Standards: NASA-STD-6012, EN ISO 15329, ISO 19650\n"
                    f"Ruleset: BIMGUARD-GC-001 + BIMGUARD-CC-001 v1.0.0"
                ),
                priority=priority_map[band],
                status=status_map[band],
                assigned_to=engineer_map[band],
                due_date=due,
                labels=labels,
                # A result with no IFC GlobalId gets an empty component
                # GUID, not a random UUID: the viewpoint then omits IfcGuid
                # (schema-legal) instead of pointing at a GUID no model has.
                component_guid=str(r.get("guid") or ""),
                component_name=r.get("name", "Component"),
                service_type=r.get("description", ""),
                floor=r.get("floor", ""),
                risk_band=band,
                mechanism=mech,
                risk_score=score,
                mitigation=r.get("mitigation", ""),
                camera_x=float(pos[0]),
                camera_y=float(pos[1]),
                camera_z=float(pos[2]),
                target_x=float(pos[0]),
                target_y=float(pos[1]),
                target_z=float(pos[2]),
            )
        )

    return issues
