"""Round-trip tests for the .dclx (DocLang Archive) OPC packaging."""

from __future__ import annotations

import io
import zipfile

from app.services.documents_service import DocumentService

SAMPLE_XML = "<doclang version=\"0.7\"><body><heading level=\"1\">Title</heading></body></doclang>"


def _sample_doc() -> dict:
    return {
        "id": 1,
        "filename": "spec.pdf",
        "project_code": "PRJ",
        "originator": "ACME",
        "cde_state": "WIP",
        "suitability_code": "S0",
        "revision_code": "P01.01",
    }


def test_build_archive_produces_opc_package() -> None:
    """build_doclang_archive writes [Content_Types].xml and _rels/.rels alongside document.xml."""
    archive_bytes = DocumentService.build_doclang_archive(_sample_doc(), SAMPLE_XML)

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        names = set(zf.namelist())
        assert "[Content_Types].xml" in names
        assert "_rels/.rels" in names
        assert "document.xml" in names
        assert "manifest.json" in names

        content_types = zf.read("[Content_Types].xml").decode("utf-8")
        assert "document.xml" in content_types
        assert "openxmlformats-package.relationships" in content_types

        rels = zf.read("_rels/.rels").decode("utf-8")
        assert 'Target="document.xml"' in rels


def test_build_then_extract_round_trip_with_assets() -> None:
    """extract_doclang_archive recovers the original XML and asset bytes from a built archive."""
    assets = [{"filename": "asset_1.png", "asset_bytes": b"\x89PNG\r\n\x1a\nfake"}]
    archive_bytes = DocumentService.build_doclang_archive(_sample_doc(), SAMPLE_XML, assets=assets)

    xml, extracted_assets = DocumentService.extract_doclang_archive(archive_bytes)

    assert xml == SAMPLE_XML
    assert extracted_assets == assets


def test_extract_tolerates_legacy_flat_archive_without_opc_parts() -> None:
    """extract_doclang_archive still reads archives built before OPC parts were added."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("document.xml", SAMPLE_XML.encode("utf-8"))
        zf.writestr(
            "manifest.json",
            '{"format": "doclang-archive", "version": "1.0", "entrypoint": "document.xml"}',
        )
        zf.writestr("assets/legacy.png", b"legacy-bytes")

    xml, assets = DocumentService.extract_doclang_archive(buf.getvalue())

    assert xml == SAMPLE_XML
    assert assets == [{"filename": "legacy.png", "asset_bytes": b"legacy-bytes"}]
