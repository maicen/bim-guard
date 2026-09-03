"""BCF 2.1 export for compliance issues - OpenBIM standard (buildingSMART).

Turns Module 4 :class:`Issue` findings into BCF 2.1 artefacts so that Walled
Garden results can be routed into standard issue-tracking and model-review
workflows (Revit, Solibri, Archicad, BlenderBIM, BIMcollab).

BCF 2.1 spec: https://github.com/buildingSMART/BCF-XML

Two output paths are provided:

* :meth:`BCFExporter.generate_bcf_markup_xml` -- a single flat ``Markup``
  document holding every topic. This is *not* a spec-valid archive (BCF 2.1
  permits exactly one ``Topic`` per ``markup.bcf``); it is retained because
  existing callers and tests depend on it, and it is useful for quick
  inspection and diffing.
* :meth:`BCFExporter.export` -- a spec-valid ``.bcfzip`` archive containing
  ``bcf.version``, ``project.bcfp`` and one folder per topic holding
  ``markup.bcf``, ``viewpoint.bcfv`` and ``snapshot.png``.

Multi-element findings
----------------------
A galvanic couple (GC-001) implicates *two* elements -- an anode and a
cathode -- and a clearance breach implicates the offending element plus what
it clashes with. :class:`Issue` carries a single ``element_id``, so any
additional IFC GUIDs are read out of ``Issue.metadata`` by
:meth:`BCFExporter.collect_elements`. The resulting viewpoint selects and
colours every implicated element, not just the primary one.

Relationship to ``reporter.bcf_generator``
--------------------------------------------------
``app/modules/reporter/bcf_generator.py`` writes an equivalent
archive from its own ``BCFIssue`` dataclass on the Blue Halo path, but its
viewpoint selects a single component. This module is the services-layer
entry point, works directly off the Module 4 ``Issue`` contract, and supports
multi-component selection. The two are candidates for consolidation; the
GUID rules they share (``bcf_topic_guid``, ``is_ifc_guid``) already live in
``bcf_generator`` and are imported here rather than duplicated.

GUID hygiene
------------
BCF 2.1 types ``Topic/@Guid`` as a hyphenated UUID and ``Component/@IfcGuid``
and ``File/@IfcProject`` as a 22-character IFC GlobalId. Module 4 finding ids
(``BGR-0007``) are neither, and a project code is not an IfcProject GUID, so
the archive path derives a deterministic UUID5 topic GUID from the finding id
(recorded as ``Finding ID`` in the description) and only writes ``IfcGuid`` /
``IfcProject`` for values that really are IFC GlobalIds.
"""

from __future__ import annotations

import io
import uuid
import xml.etree.ElementTree as ET
import zipfile
from base64 import b64decode
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from app.modules.comparator.issue_schema import Issue, RiskBand
from app.modules.reporter.bcf_generator import bcf_topic_guid, is_ifc_guid

#: Repository root, resolved from this file so exports work from any cwd.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Default destination for generated archives.
DEFAULT_EXPORT_DIR = REPO_ROOT / "docs" / "bcf_exports"

MARKUP_NS = "http://www.buildingsmart-tech.org/bcf/2.1/markup"

#: ``Issue.metadata`` keys inspected for additional IFC GUIDs, in priority
#: order. Values may be a single GUID string or a sequence of them. Engines
#: are free to populate whichever key reads naturally for their mechanism.
RELATED_GUID_KEYS: tuple[str, ...] = (
    "related_element_ids",
    "related_element_guids",
    "anode_guid",
    "cathode_guid",
    "clashing_element_id",
    "counterpart_guid",
)

#: Human labels for the roles the above keys imply, used in the topic body.
GUID_KEY_ROLES: dict[str, str] = {
    "anode_guid": "anode",
    "cathode_guid": "cathode",
    "clashing_element_id": "clashing element",
    "counterpart_guid": "counterpart",
}

#: ARGB fills applied to selected components in the viewpoint.
RISK_COLOURS: dict[RiskBand, str] = {
    RiskBand.CRITICAL: "FFC00000",
    RiskBand.HIGH: "FFC05000",
    RiskBand.MEDIUM: "FFFF8C00",
    RiskBand.LOW: "FF107C10",
}

#: Smallest valid PNG (1x1, transparent). BCF readers expect a snapshot to be
#: present; a real thumbnail can be substituted once the viewer can render one.
_PLACEHOLDER_PNG = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


@dataclass(frozen=True)
class ElementRef:
    """One IFC element implicated in a finding.

    Attributes:
        ifc_guid: The IFC ``GlobalId`` of the element.
        role: What the element contributes to the finding, e.g. ``"anode"``.
            ``"primary"`` marks the element the issue is filed against.
    """

    ifc_guid: str
    role: str = "primary"


class BCFExporter:
    """Export compliance issues as BCF 2.1 archives and markup."""

    def __init__(self, export_dir: Optional[Path] = None) -> None:
        """Create an exporter writing to *export_dir* (default ``docs/bcf_exports``)."""
        self.export_dir = Path(export_dir) if export_dir else DEFAULT_EXPORT_DIR

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _risk_band_to_bcf_priority(band: RiskBand) -> str:
        """Map BIMGUARD risk band to BCF priority level."""
        mapping = {
            RiskBand.CRITICAL: "Critical",
            RiskBand.HIGH: "High",
            RiskBand.MEDIUM: "Medium",
            RiskBand.LOW: "Low",
        }
        return mapping.get(band, "Medium")

    @staticmethod
    def collect_elements(issue: Issue) -> List[ElementRef]:
        """Return every IFC element implicated in *issue*, primary element first.

        The primary element comes from ``issue.element_id``. Additional GUIDs
        are read from the ``issue.metadata`` keys listed in
        :data:`RELATED_GUID_KEYS`; each key may hold one GUID or a sequence.
        Duplicates and blanks are dropped, and ordering is stable so that
        repeated exports of the same issue produce identical viewpoints.
        """
        elements: List[ElementRef] = []
        seen: set[str] = set()

        primary = (issue.element_id or "").strip()
        if primary:
            elements.append(ElementRef(primary, "primary"))
            seen.add(primary)

        metadata = issue.metadata if isinstance(issue.metadata, dict) else {}
        for key in RELATED_GUID_KEYS:
            raw = metadata.get(key)
            if raw is None:
                continue
            values: Sequence = raw if isinstance(raw, (list, tuple, set)) else [raw]
            role = GUID_KEY_ROLES.get(key, "related")
            for value in values:
                guid = str(value).strip()
                if not guid or guid in seen:
                    continue
                elements.append(ElementRef(guid, role))
                seen.add(guid)

        return elements

    # ------------------------------------------------------------------
    # Flat markup (legacy / inspection format)
    # ------------------------------------------------------------------

    def generate_bcf_markup_xml(self, issues: List[Issue]) -> str:
        """Generate a single Markup document holding every issue as a topic.

        Retained for existing callers. Prefer :meth:`export` for anything that
        must be read by a BCF-compliant tool.
        """
        root = ET.Element("Markup")
        root.set("xmlns", MARKUP_NS)

        header = ET.SubElement(root, "Header")
        file_elem = ET.SubElement(header, "File")
        file_elem.set("IfcProject", "BIMGuard Compliance Analysis")
        file_elem.set("IfcSpatialStructureElement", "Multiple")
        ET.SubElement(file_elem, "Date").text = self._timestamp()

        for issue in issues:
            root.append(self._issue_to_bcf_topic(issue))

        return ET.tostring(root, encoding="unicode")

    def _issue_to_bcf_topic(self, issue: Issue) -> ET.Element:
        """Convert a single Issue to a BCF Topic XML element."""
        elements = self.collect_elements(issue)

        topic = ET.Element("Topic")
        topic.set("Guid", issue.id)
        topic.set("TopicType", "Issue")
        topic.set("TopicStatus", issue.status)

        title = ET.SubElement(topic, "Title")
        title.text = issue.title or f"{issue.mechanism} - {issue.element_id[:8]}"

        description = ET.SubElement(topic, "Description")
        description.text = self._describe(issue, elements)

        created_at = issue.created_at or self._timestamp()
        ET.SubElement(topic, "CreationDate").text = created_at
        ET.SubElement(topic, "CreationUser").text = "BIMGUARD-AI"
        ET.SubElement(topic, "ModifiedDate").text = issue.updated_at or created_at
        ET.SubElement(topic, "ModifiedUser").text = "BIMGUARD-AI"
        ET.SubElement(topic, "Priority").text = self._risk_band_to_bcf_priority(issue.band)

        for label_val in self._labels(issue):
            ET.SubElement(topic, "Labels").text = label_val

        references = ET.SubElement(topic, "References")
        for element in elements:
            ref = ET.SubElement(references, "Reference")
            ref.set("ReferencedSheet", element.ifc_guid)
            ref.text = f"IfcElement(GlobalId={element.ifc_guid}, role={element.role})"

        comments = ET.SubElement(topic, "Comments")
        comment = ET.SubElement(comments, "Comment")
        comment.set("Guid", str(uuid.uuid4()))
        ET.SubElement(comment, "Date").text = created_at
        ET.SubElement(comment, "Author").text = "BIMGUARD-AI"
        ET.SubElement(comment, "Comment").text = self._format_issue_details(issue)
        comment_topic = ET.SubElement(comment, "Topic")
        comment_topic.set("Guid", issue.id)

        return topic

    def _describe(self, issue: Issue, elements: Sequence[ElementRef]) -> str:
        """Build the topic description body for *issue*."""
        lines = [
            f"Finding ID: {issue.id}",
            f"Mechanism: {issue.mechanism}",
            f"Score: {issue.score:.2f} ({issue.band.value})",
            f"Element ID: {issue.element_id}",
            f"Rule ID: {issue.rule_id}",
        ]
        related = [e for e in elements if e.role != "primary"]
        if related:
            joined = ", ".join(f"{e.ifc_guid} ({e.role})" for e in related)
            lines.append(f"Related elements: {joined}")
        if issue.description:
            lines.append(f"\n{issue.description}")
        if issue.mitigation:
            lines.append(f"\nMitigation: {issue.mitigation}")
        return "\n".join(lines)

    def _labels(self, issue: Issue) -> List[str]:
        """Return the BCF labels for *issue*, including ISO 19650 governance tags."""
        labels = [issue.mechanism, issue.band.value]
        if issue.metadata and isinstance(issue.metadata, dict):
            if issue.metadata.get("suitability_code"):
                labels.append(f"Suitability:{issue.metadata['suitability_code']}")
            if issue.metadata.get("cde_state"):
                labels.append(f"CDE:{issue.metadata['cde_state']}")
        return labels

    def _format_issue_details(self, issue: Issue) -> str:
        """Format issue metadata as human-readable comment text."""
        lines = [
            f"Compliance Mechanism: {issue.mechanism}",
            f"Composite Score: {issue.score:.3f}",
            f"Risk Band: {issue.band.value.upper()}",
        ]

        if issue.metadata:
            lines.append("\nMechanism-Specific Data:")
            for key, value in issue.metadata.items():
                if isinstance(value, float):
                    lines.append(f"  {key}: {value:.4f}")
                else:
                    lines.append(f"  {key}: {value}")

        if issue.citations:
            lines.append("\nStandards References:")
            for citation in issue.citations:
                standard = citation.get("standard", "?")
                clause = citation.get("clause", "?")
                reason = citation.get("reason", "")
                lines.append(f"  - {standard} Clause {clause}")
                if reason:
                    lines.append(f"    Reason: {reason}")

        lines.append(f"\nAssignee Role: {issue.assignee_role}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Spec-valid archive
    # ------------------------------------------------------------------

    def _topic_markup_xml(
        self, issue: Issue, viewpoint_guid: str, topic_guid: Optional[str] = None
    ) -> str:
        """Render one topic's ``markup.bcf`` document.

        Element order follows the BCF 2.1 schema, which is a strict sequence:
        ``Header, Topic, Comment*, Viewpoints*``. Within ``Topic``, ``Title``
        precedes ``Priority``, which precedes ``Labels`` and the audit dates.

        ``topic_guid`` is the schema-legal ``Topic/@Guid``; it defaults to
        :func:`bcf_topic_guid` of ``issue.id`` and is passed explicitly by
        :meth:`build_archive` so the folder name and attribute always agree.
        """
        elements = self.collect_elements(issue)
        created_at = issue.created_at or self._timestamp()
        topic_guid = topic_guid or bcf_topic_guid(issue.id)

        # BCF 2.1's markup.xsd declares no targetNamespace, so Markup and its
        # children are unqualified. Only the xsi prefix is bound, matching the
        # archives written by reporter.bcf_generator.
        root = ET.Element(
            "Markup", {"xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"}
        )

        header = ET.SubElement(root, "Header")
        file_elem = ET.SubElement(header, "File")
        # File/@IfcProject is typed IfcGuid; a project code ("ZIG-001") or a
        # product name fails its 22-character facet, so only a real GlobalId
        # is written. The code still reaches reviewers through the labels.
        project_code = str(issue.metadata.get("project_code", "") or "")
        if is_ifc_guid(project_code):
            file_elem.set("IfcProject", project_code)
        ET.SubElement(file_elem, "Filename").text = str(
            issue.metadata.get("source_filename", "") or "model.ifc"
        )
        ET.SubElement(file_elem, "Date").text = created_at

        topic = ET.SubElement(root, "Topic")
        topic.set("Guid", topic_guid)
        topic.set("TopicType", "Issue")
        topic.set("TopicStatus", issue.status)

        ET.SubElement(topic, "Title").text = issue.title or issue.mechanism
        ET.SubElement(topic, "Priority").text = self._risk_band_to_bcf_priority(issue.band)
        for label_val in self._labels(issue):
            ET.SubElement(topic, "Labels").text = label_val
        ET.SubElement(topic, "CreationDate").text = created_at
        ET.SubElement(topic, "CreationAuthor").text = "BIMGUARD-AI"
        ET.SubElement(topic, "ModifiedDate").text = issue.updated_at or created_at
        ET.SubElement(topic, "ModifiedAuthor").text = "BIMGUARD-AI"
        ET.SubElement(topic, "AssignedTo").text = issue.assignee_role
        ET.SubElement(topic, "Description").text = self._describe(issue, elements)

        comment = ET.SubElement(root, "Comment")
        comment.set("Guid", str(uuid.uuid4()))
        ET.SubElement(comment, "Date").text = created_at
        ET.SubElement(comment, "Author").text = "BIMGUARD-AI"
        ET.SubElement(comment, "Comment").text = self._format_issue_details(issue)

        viewpoints = ET.SubElement(root, "Viewpoints")
        viewpoints.set("Guid", viewpoint_guid)
        ET.SubElement(viewpoints, "Viewpoint").text = "viewpoint.bcfv"
        ET.SubElement(viewpoints, "Snapshot").text = "snapshot.png"

        return self._serialise(root)

    def _viewpoint_xml(self, issue: Issue, viewpoint_guid: str) -> str:
        """Render one topic's ``viewpoint.bcfv``, selecting every implicated element.

        ``Components`` is an ordered sequence -- ``ViewSetupHints, Selection,
        Visibility, Coloring`` -- so ``Visibility`` must precede ``Coloring``
        even though the two are independent in meaning.
        """
        elements = self.collect_elements(issue)
        colour = RISK_COLOURS.get(issue.band, "FF888888")

        root = ET.Element("VisualizationInfo", {"Guid": viewpoint_guid})
        components = ET.SubElement(root, "Components")

        hints = ET.SubElement(components, "ViewSetupHints")
        hints.set("SpacesVisible", "false")
        hints.set("SpaceBoundariesVisible", "false")
        hints.set("OpeningsVisible", "false")

        # Component/@IfcGuid is optional in visinfo.xsd but, when present,
        # must be a 22-character IFC GlobalId. Anything else (an empty id, a
        # UUID, a label) is left off the attribute and kept in AuthoringToolId
        # so the reader still sees what the finding pointed at.
        selection = ET.SubElement(components, "Selection")
        for element in elements:
            component = ET.SubElement(selection, "Component")
            if is_ifc_guid(element.ifc_guid):
                component.set("IfcGuid", element.ifc_guid)
            ET.SubElement(component, "OriginatingSystem").text = "BIMGUARD AI"
            ET.SubElement(component, "AuthoringToolId").text = f"{element.role}:{element.ifc_guid}"

        visibility = ET.SubElement(components, "Visibility")
        visibility.set("DefaultVisibility", "true")

        coloring = ET.SubElement(components, "Coloring")
        colour_elem = ET.SubElement(coloring, "Color")
        colour_elem.set("Color", colour)
        for element in elements:
            coloured = ET.SubElement(colour_elem, "Component")
            if is_ifc_guid(element.ifc_guid):
                coloured.set("IfcGuid", element.ifc_guid)

        self._append_camera(root, issue)
        return self._serialise(root)

    def _append_camera(self, root: ET.Element, issue: Issue) -> None:
        """Attach a perspective camera, honouring ``metadata['camera']`` if present.

        The camera is offset from the element so the selection is framed rather
        than sitting on the near plane. Once the IFC parser reports element
        centroids, pass them through ``metadata['camera']`` as
        ``{"x": .., "y": .., "z": ..}`` to aim the view at the real geometry.
        """
        camera_meta = issue.metadata.get("camera") if isinstance(issue.metadata, dict) else None
        camera_meta = camera_meta if isinstance(camera_meta, dict) else {}
        target_x = float(camera_meta.get("x", 0.0))
        target_y = float(camera_meta.get("y", 0.0))
        target_z = float(camera_meta.get("z", 0.0))

        eye = (target_x + 5.0, target_y - 8.0, target_z + 3.0)
        direction = (-5.0, 8.0, -3.0)

        camera = ET.SubElement(root, "PerspectiveCamera")
        point = ET.SubElement(camera, "CameraViewPoint")
        for axis, value in zip(("X", "Y", "Z"), eye):
            ET.SubElement(point, axis).text = f"{value:.4f}"
        heading = ET.SubElement(camera, "CameraDirection")
        for axis, value in zip(("X", "Y", "Z"), direction):
            ET.SubElement(heading, axis).text = f"{value:.4f}"
        up = ET.SubElement(camera, "CameraUpVector")
        for axis, value in zip(("X", "Y", "Z"), (0.0, 0.0, 1.0)):
            ET.SubElement(up, axis).text = f"{value:.4f}"
        ET.SubElement(camera, "FieldOfView").text = "60"

    def build_archive(self, issues: Iterable[Issue], project_name: str = "") -> bytes:
        """Build a BCF 2.1 ``.bcfzip`` archive in memory and return its bytes."""
        issue_list = list(issues)
        buf = io.BytesIO()

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("bcf.version", self._version_xml())
            archive.writestr("project.bcfp", self._project_xml(project_name))

            # Folder name is the topic GUID (BCF 2.1 convention), derived from
            # the finding id when that is not already a UUID.
            for issue in issue_list:
                topic_guid = bcf_topic_guid(issue.id)
                folder = f"{topic_guid}/"
                viewpoint_guid = str(uuid.uuid4()).upper()
                archive.writestr(
                    folder + "markup.bcf",
                    self._topic_markup_xml(issue, viewpoint_guid, topic_guid=topic_guid),
                )
                archive.writestr(folder + "viewpoint.bcfv", self._viewpoint_xml(issue, viewpoint_guid))
                archive.writestr(folder + "snapshot.png", _PLACEHOLDER_PNG)

        return buf.getvalue()

    def export(
        self,
        issues: Iterable[Issue],
        filename: str = "",
        project_name: str = "",
    ) -> Path:
        """Write a ``.bcfzip`` into the export directory and return its path.

        Args:
            issues: Findings to export, one BCF topic each.
            filename: Archive name. Defaults to a UTC-stamped name; a missing
                ``.bcfzip`` suffix is appended.
            project_name: Name recorded in ``project.bcfp``.

        Returns:
            The path the archive was written to.
        """
        if not filename:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            filename = f"bimguard_findings_{stamp}.bcfzip"
        if not filename.lower().endswith(".bcfzip"):
            filename = f"{filename}.bcfzip"

        self.export_dir.mkdir(parents=True, exist_ok=True)
        path = self.export_dir / filename
        path.write_bytes(self.build_archive(issues, project_name))
        return path

    def generate_bcf_zip(self, issues: List[Issue], output_path: str) -> None:
        """Write a BCF 2.1 archive to *output_path*."""
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(self.build_archive(issues))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _timestamp() -> str:
        """UTC timestamp in ISO 8601 with a trailing Z."""
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _serialise(root: ET.Element) -> str:
        """Serialise *root* as a UTF-8 XML document with a declaration."""
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")

    @staticmethod
    def _version_xml() -> str:
        """Render the mandatory ``bcf.version`` descriptor."""
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Version VersionId="2.1" xsi:noNamespaceSchemaLocation="version.xsd"\n'
            '  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
            "  <DetailedVersion>2.1</DetailedVersion>\n"
            "</Version>"
        )

    @staticmethod
    def _project_xml(project_name: str = "") -> str:
        """Render ``project.bcfp`` for the archive."""
        root = ET.Element("ProjectExtension")
        project = ET.SubElement(root, "Project")
        project.set("ProjectId", str(uuid.uuid4()).upper())
        ET.SubElement(project, "Name").text = (
            project_name or "BIMGUARD AI - Compliance Findings"
        )
        ET.SubElement(root, "ExtensionSchema").text = "extensions.xsd"
        return BCFExporter._serialise(root)
