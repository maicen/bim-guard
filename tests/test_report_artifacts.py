"""Tests for persistent generated report artifacts."""

import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO

from app.modules.module5_reporter.bcf_generator import bcf_topic_guid
from app.services.report_artifacts import ReportArtifactService


class FakeStorage:
    """Capture report objects without contacting Supabase Storage."""

    def __init__(self) -> None:
        self.content = b""
        self.reference = "sb://bim-guard-artifacts/reports/bcf/export.bcf"

    def save_upload(self, filename: str, content: bytes, subdir: str) -> str:
        assert filename == "compliance_project_14.bcf"
        assert subdir == "reports/bcf"
        self.content = content
        return self.reference

    def delete(self, reference: str) -> None:
        assert reference == self.reference


class FakeTable:
    """Store artifact metadata in memory for a focused service test."""

    def __init__(self) -> None:
        self.rows = []

    def insert(self, payload: dict) -> dict:
        row = {"id": len(self.rows) + 1, **payload}
        self.rows.append(row)
        return row

    def rows_where(self, where_sql: str, params: list) -> list[dict]:
        assert where_sql == "project_id = ?"
        return [row for row in self.rows if row["project_id"] == params[0]]

    def get(self, artifact_id: int) -> dict | None:
        return next((row for row in self.rows if row["id"] == artifact_id), None)


def test_persist_bcf_uploads_zip_and_records_metadata() -> None:
    storage = FakeStorage()
    table = FakeTable()
    service = ReportArtifactService(storage=storage, table=table)

    artifact = service.persist_bcf(
        14,
        [
            {
                "guid": "topic-guid",
                "title": "Clearance failure",
                "description": "Required clearance was not met.",
                "priority": "high",
                "status": "Open",
                "type": "Error",
                "element_guid": "ifc-guid",
                "rule_id": "CLR-001",
            }
        ],
    )

    assert artifact is not None
    assert artifact["storage_ref"] == storage.reference
    assert artifact["byte_size"] == len(storage.content)
    assert artifact["issue_count"] == 1
    assert service.latest_bcf(14) == artifact
    assert service.list_bcf() == [artifact]
    assert service.get_bcf(artifact["id"]) == artifact
    assert service.get_bcf(999) is None
    with zipfile.ZipFile(BytesIO(storage.content)) as archive:
        assert "bcf.version" in archive.namelist()
        # "topic-guid" is not a BCF 2.1 Guid (hyphenated UUID), so the
        # generator files the topic under the deterministic UUID5 it derives
        # from that id and records the original in the comment body.
        folder = bcf_topic_guid("topic-guid")
        assert f"{folder}/markup.bcf" in archive.namelist()
        markup = ET.fromstring(archive.read(f"{folder}/markup.bcf").decode())
        assert markup.find("Topic").get("Guid") == folder
        assert "Source finding id: topic-guid" in markup.find("./Comment/Comment").text