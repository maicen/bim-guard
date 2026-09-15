"""Parse a BCF 2.1 ``.bcfzip`` archive back into plain dicts.

Reads what :mod:`app.modules.reporter.bcf_generator` writes -- and, best
effort, archives from other BCF 2.1 tools -- so ``POST
/api/bcf/v2.1/projects/{project_id}/import`` can round-trip an exported
archive or accept one from Revit/Solibri/BlenderBIM. Not a schema validator:
elements the spec allows and this parser does not recognise are ignored
rather than rejected, so a well-formed archive this codebase's own exporter
never produces (e.g. a viewpoint with no camera) still imports.
"""

from __future__ import annotations

import base64
import io
import zipfile
from typing import Any
from xml.etree import ElementTree as ET

from app.logging_config import get_logger

logger = get_logger(__name__)


class BCFImportError(ValueError):
    """Raised when a ``.bcfzip`` archive cannot be parsed at all."""


def _text(el: ET.Element | None, tag: str) -> str:
    """Return the stripped text of ``el``'s first ``tag`` child, or ``""``."""
    if el is None:
        return ""
    child = el.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _float(el: ET.Element | None, tag: str) -> float:
    try:
        return float(_text(el, tag))
    except ValueError:
        return 0.0


def _parse_camera(vector_root: ET.Element, camera_tag: str) -> dict[str, Any] | None:
    """Parse a ``PerspectiveCamera``/``OrthogonalCamera`` block, or ``None`` if absent."""
    cam = vector_root.find(camera_tag)
    if cam is None:
        return None
    view_point = cam.find("CameraViewPoint")
    direction = cam.find("CameraDirection")
    up_vector = cam.find("CameraUpVector")
    result: dict[str, Any] = {
        "camera_view_point": {
            "x": _float(view_point, "X"),
            "y": _float(view_point, "Y"),
            "z": _float(view_point, "Z"),
        },
        "camera_direction": {
            "x": _float(direction, "X"),
            "y": _float(direction, "Y"),
            "z": _float(direction, "Z"),
        },
        "camera_up_vector": {
            "x": _float(up_vector, "X"),
            "y": _float(up_vector, "Y"),
            "z": _float(up_vector, "Z"),
        },
    }
    if camera_tag == "PerspectiveCamera":
        fov = cam.find("FieldOfView")
        result["field_of_view"] = float(fov.text) if fov is not None and fov.text else 60.0
    else:
        scale = cam.find("ViewToWorldScale")
        result["view_to_world_scale"] = float(scale.text) if scale is not None and scale.text else 1.0
    return result


def _parse_components(components_el: ET.Element | None) -> dict[str, Any]:
    """Parse ``VisualizationInfo/Components`` into the ``components`` JSON shape used internally."""
    if components_el is None:
        return {"selection": [], "coloring": [], "visibility": {"default_visibility": True, "exceptions": []}}

    selection = [
        {"ifc_guid": c.get("IfcGuid", "")}
        for c in components_el.findall("Selection/Component")
        if c.get("IfcGuid")
    ]

    coloring = []
    for color_el in components_el.findall("Coloring/Color"):
        members = [
            {"ifc_guid": c.get("IfcGuid", "")}
            for c in color_el.findall("Component")
            if c.get("IfcGuid")
        ]
        coloring.append({"color": color_el.get("Color", ""), "components": members})

    visibility_el = components_el.find("Visibility")
    default_visibility = True
    if visibility_el is not None:
        default_visibility = (visibility_el.get("DefaultVisibility") or "true").lower() == "true"
    exceptions = [
        {"ifc_guid": c.get("IfcGuid", "")}
        for c in components_el.findall("Visibility/Exceptions/Component")
        if c.get("IfcGuid")
    ]

    return {
        "selection": selection,
        "coloring": coloring,
        "visibility": {"default_visibility": default_visibility, "exceptions": exceptions},
    }


def _parse_viewpoint_xml(data: bytes) -> dict[str, Any]:
    """Parse one ``viewpoint.bcfv`` file into the fields ``BCFViewpointCreatePayload`` expects."""
    root = ET.fromstring(data)
    return {
        "perspective_camera": _parse_camera(root, "PerspectiveCamera"),
        "orthogonal_camera": _parse_camera(root, "OrthogonalCamera"),
        "components": _parse_components(root.find("Components")),
    }


def _parse_topic_folder(zf: zipfile.ZipFile, folder: str, names: set[str]) -> dict[str, Any] | None:
    """Parse one topic's ``markup.bcf`` (+ viewpoint/snapshot if present) into a plain dict."""
    markup_path = f"{folder}/markup.bcf"
    try:
        root = ET.fromstring(zf.read(markup_path))
    except (ET.ParseError, KeyError) as exc:
        logger.warning("Skipping unreadable BCF topic folder=%s error=%s", folder, exc)
        return None

    topic_el = root.find("Topic")
    if topic_el is None:
        return None

    guid = (topic_el.get("Guid") or folder).strip().upper()
    due_date = _text(topic_el, "DueDate")
    topic: dict[str, Any] = {
        "guid": guid,
        "topic_type": topic_el.get("TopicType") or "Issue",
        "topic_status": topic_el.get("TopicStatus") or "Open",
        "title": _text(topic_el, "Title") or "Untitled Topic",
        "priority": _text(topic_el, "Priority") or "Normal",
        "description": _text(topic_el, "Description") or None,
        "due_date": due_date.split("T", 1)[0] if due_date else None,
        "assigned_to": _text(topic_el, "AssignedTo") or None,
        "creation_author": _text(topic_el, "CreationAuthor"),
        "creation_date": _text(topic_el, "CreationDate"),
        "modified_date": _text(topic_el, "ModifiedDate") or None,
        "modified_author": _text(topic_el, "ModifiedAuthor") or None,
        "labels": [lbl.text.strip() for lbl in topic_el.findall("Labels") if lbl.text and lbl.text.strip()],
        "component_guids": [
            c.get("IfcGuid", "") for c in root.findall(".//Component") if c.get("IfcGuid")
        ],
        "comments": [],
        "viewpoints": [],
    }

    for comment_el in root.findall("Comment"):
        vp_ref = comment_el.find("Viewpoint")
        topic["comments"].append(
            {
                "guid": (comment_el.get("Guid") or "").strip().upper() or None,
                "date": _text(comment_el, "Date"),
                "author": _text(comment_el, "Author"),
                "comment": _text(comment_el, "Comment"),
                "viewpoint_guid": (vp_ref.get("Guid") or "").strip().upper() if vp_ref is not None else None,
            }
        )

    for vp_el in root.findall("Viewpoints"):
        vp_guid = (vp_el.get("Guid") or "").strip().upper() or None
        viewpoint: dict[str, Any] = {"guid": vp_guid}

        vp_filename = _text(vp_el, "Viewpoint")
        vp_path = f"{folder}/{vp_filename}" if vp_filename else ""
        if vp_path in names:
            try:
                viewpoint.update(_parse_viewpoint_xml(zf.read(vp_path)))
            except ET.ParseError as exc:
                logger.warning("Skipping unreadable viewpoint path=%s error=%s", vp_path, exc)

        snapshot_filename = _text(vp_el, "Snapshot")
        snapshot_path = f"{folder}/{snapshot_filename}" if snapshot_filename else ""
        if snapshot_path in names:
            viewpoint["snapshot_base64"] = base64.b64encode(zf.read(snapshot_path)).decode("ascii")

        topic["viewpoints"].append(viewpoint)

    return topic


def parse_bcfzip(data: bytes) -> list[dict[str, Any]]:
    """Parse a BCF 2.1 ``.bcfzip`` archive into a list of topic dicts.

    Each dict carries the topic's own fields plus nested ``comments`` and
    ``viewpoints`` lists, shaped to match what
    :meth:`app.services.bcf_sync_service.BCFSyncService.import_topic` expects.

    Raises:
        BCFImportError: ``data`` is not a readable zip archive, or contains no
            topic folder with a ``markup.bcf``.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise BCFImportError(f"Not a valid BCF zip archive: {exc}") from exc

    with zf:
        names = set(zf.namelist())
        folders = sorted({n.split("/", 1)[0] for n in names if n.endswith("/markup.bcf")})
        if not folders:
            raise BCFImportError("Archive contains no topic folder with a markup.bcf file")

        topics = [_parse_topic_folder(zf, folder, names) for folder in folders]
        return [t for t in topics if t is not None]
