"""Tests for Session D's Blue Halo wiring.

Blue Halo itself is tested by ``validate_blue_halo.py`` and the benchmark suite
on the thesis branch. This file tests the *wiring*: that clearance envelopes are
generated from real model geometry, that clashes become Issues in the shared
shape, and that an element whose geometry cannot be read produces a
``data_quality`` Issue instead of vanishing or being given an invented envelope.

NO LIVE DATABASE, NO CACHED FILES. Models are synthesised in memory, so the
geometry under test is the geometry asserted.

Run: uv run pytest tests/test_phase_6d_seismic.py -v
"""

from __future__ import annotations

import pytest

from app.modules.comparator.issue_schema import RiskBand
from app.modules.phase_6.phase_6d_seismic import (
    BRACED_CLASSES,
    DATA_QUALITY,
    DEFAULT_CONFIG_PATH,
    MECHANISM_CODE,
    PRIMARY_MODEL_LABEL,
    SEVERITY_TO_BAND,
    _severity_band,
    issue_stats,
    run_seismic_analysis,
)

ifcopenshell = pytest.importorskip("ifcopenshell", reason="Blue Halo needs ifcopenshell")


def minimal_ifc(schema: str = "IFC4") -> bytes:
    """A model with two elements and no geometry representations.

    Enough to exercise config loading, element enumeration and the
    geometry-unavailable path — which is the branch that matters most here.
    """
    model = ifcopenshell.file(schema=schema)
    model.create_entity("IfcPipeSegment", GlobalId=ifcopenshell.guid.new(), Name="CHW-01")
    model.create_entity("IfcDuctSegment", GlobalId=ifcopenshell.guid.new(), Name="SA-01")
    return model.to_string().encode("utf-8")


@pytest.fixture
def result():
    return run_seismic_analysis(minimal_ifc())


# ---------------------------------------------------------------------------
# AnalysisResult shape — identical to Session C
# ---------------------------------------------------------------------------


class TestResultShape:
    def test_keys_match_session_c(self, result):
        """A seismic result and a corrosion result must be interchangeable."""
        assert set(result) == {
            "audit_issues",
            "issue_stats",
            "cost_impact",
            "compliance_error",
            "compliance_is_demo",
        }

    def test_stats_keys_match_session_c(self, result):
        assert set(result["issue_stats"]) == {
            "total",
            "critical",
            "high",
            "medium",
            "low",
            "data_quality",
        }

    def test_output_is_never_flagged_demo(self, result):
        """There is no synthetic-issue generator; nothing here is demo data."""
        assert result["compliance_is_demo"] is False

    def test_cost_impact_is_none_not_invented(self, result):
        assert result["cost_impact"] is None

    def test_issues_are_a_list(self, result):
        assert isinstance(result["audit_issues"], list)


# ---------------------------------------------------------------------------
# Failures are values
# ---------------------------------------------------------------------------


class TestFailuresAreValues:
    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param(b"", id="empty"),
            pytest.param(b"not an ifc file", id="plain-text"),
            pytest.param(b"\x00\x01\x02", id="binary-noise"),
        ],
    )
    def test_unreadable_model_does_not_raise(self, payload):
        outcome = run_seismic_analysis(payload)
        assert outcome["compliance_error"]
        assert outcome["audit_issues"] == []

    def test_missing_config_is_reported_not_raised(self):
        outcome = run_seismic_analysis(minimal_ifc(), config_path="does/not/exist.json")
        assert outcome["compliance_error"]
        assert "config could not be loaded" in outcome["compliance_error"]

    def test_valid_run_has_no_error(self, result):
        assert result["compliance_error"] is None


# ---------------------------------------------------------------------------
# Geometry is read, never invented
# ---------------------------------------------------------------------------


class TestGeometryIsNotInvented:
    def test_elements_without_geometry_do_not_produce_clashes(self, result):
        """No bounding box means no envelope, so there is nothing to clash."""
        findings = [i for i in result["audit_issues"] if i.mechanism != DATA_QUALITY]
        assert findings == [], (
            "a clash was reported for an element with no readable geometry, "
            "which means an envelope was invented"
        )

    def test_braced_classes_are_the_halo_sources(self):
        assert "IfcPipeSegment" in BRACED_CLASSES
        assert "IfcDuctSegment" in BRACED_CLASSES

    def test_no_findings_means_no_worst_band(self, result):
        assert result["issue_stats"]["total"] == 0


# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------


class TestSeverityMapping:
    @pytest.mark.parametrize(
        "severity,band",
        [
            ("critical", RiskBand.CRITICAL),
            ("major", RiskBand.HIGH),
            ("minor", RiskBand.MEDIUM),
            ("CRITICAL", RiskBand.CRITICAL),
            ("  Major  ", RiskBand.HIGH),
        ],
    )
    def test_known_severities_map(self, severity, band):
        assert _severity_band(severity, element="E") is band

    @pytest.mark.parametrize("severity", ["", "severe", "high", "unknown"])
    def test_unknown_severity_raises(self, severity):
        """Defaulting would quietly downgrade a finding to the mildest band."""
        with pytest.raises(ValueError):
            _severity_band(severity, element="E")

    def test_error_names_the_element(self):
        with pytest.raises(ValueError) as excinfo:
            _severity_band("severe", element="Riser-07")
        assert "Riser-07" in str(excinfo.value)
        assert MECHANISM_CODE in str(excinfo.value)

    def test_every_mapped_band_is_a_riskband_member(self):
        assert all(isinstance(b, RiskBand) for b in SEVERITY_TO_BAND.values())

    def test_mapping_never_yields_low(self):
        """A detected clash is a finding; none of them are 'low'."""
        assert RiskBand.LOW not in SEVERITY_TO_BAND.values()


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


class TestStats:
    def test_empty_is_all_zero(self):
        assert issue_stats([]) == {
            "total": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "data_quality": 0,
        }

    def test_stats_track_the_issue_list(self, result):
        stats = result["issue_stats"]
        issues = result["audit_issues"]
        assert stats["total"] == len([i for i in issues if i.mechanism != DATA_QUALITY])
        assert stats["data_quality"] == len(
            [i for i in issues if i.mechanism == DATA_QUALITY]
        )


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestConfig:
    def test_default_config_is_present(self):
        """The jurisdiction config ships with the Halo modules."""
        assert DEFAULT_CONFIG_PATH.exists()

    def test_config_declares_standards(self):
        from app.modules.blue_halo.halo_volume_generator import load_clearance_config

        config = load_clearance_config(DEFAULT_CONFIG_PATH)
        assert config.standards_cited, "citations are built from these"
        assert config.jurisdiction


# ---------------------------------------------------------------------------
# Federation provenance — which file each side of a clash came from
# ---------------------------------------------------------------------------


class TestSourceModelNaming:
    """A federated finding must name files, not roles.

    The 2026-09-06 audit found 886 cross-model clashes reporting
    ``clashing_source_model: "primary model"``. A coordinator cannot open a
    role, so the primary is now named by the file the project has attached.
    """

    def test_primary_label_names_the_file(self):
        """The label the caller supplies is what lands on the issue."""
        outcome = run_seismic_analysis(
            minimal_ifc(), primary_label="west_riverside_hospital_str_ifc4.ifc"
        )
        sources = {
            issue.metadata.get("source_model")
            for issue in outcome["audit_issues"]
        }
        assert sources == {"west_riverside_hospital_str_ifc4.ifc"}

    def test_no_label_still_falls_back_to_the_role(self):
        """A caller with no file name — a fixture — is not broken by the change."""
        outcome = run_seismic_analysis(minimal_ifc())
        sources = {issue.metadata.get("source_model") for issue in outcome["audit_issues"]}
        assert sources == {PRIMARY_MODEL_LABEL}

    def test_clash_issue_names_both_files(self):
        """Both sides of a cross-model clash are attributed to their own file."""
        from app.modules.blue_halo.halo_volume_generator import (
            BoundingBox,
            BraceType,
            ClashReport,
            HaloVolume,
            Point3D,
            load_clearance_config,
        )
        from app.modules.comparator.issue_adapter import IssueIdAllocator
        from app.modules.phase_6.phase_6d_seismic import _clash_issue

        box = BoundingBox(min=Point3D(0.0, 0.0, 0.0), max=Point3D(100.0, 100.0, 100.0))
        halo = HaloVolume(
            id="halo-1",
            source_element_id="HALO-ELEMENT",
            source_ifc_class="IfcPipeSegment",
            brace_type=BraceType.ANGLE_IRON,
            element_bbox_mm=box,
            halo_bbox_mm=box,
            clearance_mm=200.0,
        )
        clash = ClashReport(
            id="clash-1",
            halo_id="halo-1",
            halo_source_element_id="HALO-ELEMENT",
            clashing_element_id="CLASHING-ELEMENT",
            clashing_element_class="IfcBeam",
            overlap_bbox_mm=box,
            overlap_volume_mm3=1000.0,
            severity="major",
            description="beam intrudes into the bracing halo",
        )
        issue = _clash_issue(
            clash,
            halo,
            load_clearance_config(DEFAULT_CONFIG_PATH),
            IssueIdAllocator("BGR"),
            {
                "HALO-ELEMENT": "west_riverside_hospital_plumb_ifc4.ifc",
                "CLASHING-ELEMENT": "west_riverside_hospital_str_ifc4.ifc",
            },
        )

        assert issue.metadata["source_model"] == "west_riverside_hospital_plumb_ifc4.ifc"
        assert issue.metadata["clashing_source_model"] == "west_riverside_hospital_str_ifc4.ifc"
        assert "primary model" not in issue.metadata.values()
