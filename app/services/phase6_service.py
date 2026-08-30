"""Phase 6 pipeline service facade for file parsing, analysis, and export."""

from __future__ import annotations

from typing import Any

from app.modules.phase_6.phase_6a_upload import FileUploadService
from app.modules.phase_6.phase_6b_parsing import parse_ifc_bytes
from app.modules.phase_6.phase_6c_corrosion_ui import run_corrosion_analysis
from app.modules.phase_6.phase_6d_seismic import run_seismic_analysis
from app.modules.phase_6.phase_6e_export import DATA_QUALITY, FORMATS, export, sort_issues


class Phase6Service:
    """Service facade wrapping Phase 6 pipeline capabilities for UI routes."""

    def __init__(self) -> None:
        self.upload_service = FileUploadService()

    @staticmethod
    def parse_ifc(content: bytes, *, with_piping: bool = False) -> dict[str, Any]:
        """Parse raw IFC file bytes into structured dictionary payload.

        Args:
            content: Raw bytes of an IFC file.
            with_piping: Also build the PipingElement view, which MM-001 and
                XM-001 need. Pass this when the result feeds
                :meth:`run_corrosion`; the other analyses do not read it.
        """
        return parse_ifc_bytes(content, with_piping=with_piping)

    @staticmethod
    def run_corrosion(parsed_ifc: dict[str, Any]) -> dict[str, Any]:
        """Run corrosion analysis pipeline on parsed IFC data."""
        return run_corrosion_analysis(parsed_ifc)

    @staticmethod
    def run_seismic(parsed_ifc: dict[str, Any]) -> dict[str, Any]:
        """Run seismic analysis pipeline on parsed IFC data."""
        return run_seismic_analysis(parsed_ifc)

    @staticmethod
    def export_summary(
        summary_payload: dict[str, Any], fmt: str, source_reference: str = ""
    ) -> tuple[bytes, str, str]:
        """Export summary results in requested format."""
        return export(summary_payload, fmt, source_reference=source_reference)

    @staticmethod
    def get_supported_formats() -> list[str]:
        """Return list of supported export format slugs."""
        return list(FORMATS)

    @staticmethod
    def get_data_quality_labels() -> dict[str, str]:
        """Return data quality rating labels map."""
        return dict(DATA_QUALITY)

    @staticmethod
    def sort_issues_list(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort issues by priority/severity."""
        return sort_issues(issues)

