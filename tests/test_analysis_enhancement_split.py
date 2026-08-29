from pathlib import Path
from types import SimpleNamespace

import app.modules.module2_ifc_read as ifc_read_module
from app.services.persistence import PersistenceService, _MemoryClient
from app.services.pipeline_services import (
    AnalysisService,
    EnhancementService,
    enhance_model,
    execute_model_enhancement,
    run_compliance_analysis,
)
from app.services.projects_service import ProjectsService


def test_low_quality_reader_reports_warning_without_improving(tmp_path, monkeypatch):
    source_path = tmp_path / "source.ifc"
    source_path.write_bytes(b"ISO-10303-21;SOURCE")
    opened_paths = []

    class FakeValidator:
        def __init__(self, path):
            assert Path(path) == source_path

        def validate(self):
            return {"overall": {"score": 42}}

    def fake_open(path):
        opened_path = Path(path)
        assert opened_path.exists()
        assert opened_path.read_bytes() == b"ISO-10303-21;SOURCE"
        opened_paths.append(opened_path)
        return object()

    monkeypatch.setattr(ifc_read_module, "IFCValidator", FakeValidator)
    monkeypatch.setattr(ifc_read_module, "ifcopenshell", SimpleNamespace(open=fake_open))
    monkeypatch.setattr(ifc_read_module, "_IFCOPENSHELL_AVAILABLE", True)
    monkeypatch.setattr(ifc_read_module, "_QUALITY_TOOLS_AVAILABLE", True)
    monkeypatch.setattr(ifc_read_module, "_GEOMETRY_AVAILABLE", False)
    monkeypatch.setattr(ifc_read_module, "_SPATIAL_AVAILABLE", False)
    monkeypatch.setattr(ifc_read_module, "_EGRESS_AVAILABLE", False)

    reader = ifc_read_module.Module2_IFCRead(source_path)

    assert reader.quality_improvements == []
    assert "Run Quality Improvements from the Projects page" in reader.quality_warnings[0]
    assert len(opened_paths) == 1
    assert opened_paths[0] == source_path


def test_analysis_and_enhancement_services_are_separated():
    element = SimpleNamespace(
        GlobalId="GUID-001",
        Name="Carbon Steel Pipe",
        material="carbon_steel",
        environment="normal",
        system_type="Cooling Water",
        zone="Zone A",
        floor="Level 1",
        nominal_diameter_m=0.2,
        flow_velocity_ms=1.0,
        operating_temp_c=30.0,
        dead_leg_length_m=0.5,
        insulation_condition="poor",
    )

    source_before = dict(vars(element))
    analysis = AnalysisService().run([element])
    assert analysis["pipeline"] == "audit"
    assert analysis["element_count"] == 1
    assert "results" in analysis
    assert isinstance(analysis["results"], list)
    assert isinstance(analysis["issues"], list)
    assert len(analysis["bcf_topics"]) == len(analysis["issues"])
    assert vars(element) == source_before

    enhancement = EnhancementService().plan(
        [element],
        changes={"material": "stainless_steel", "insulation_condition": "improved"},
    )
    assert enhancement["pipeline"] == "enhancement"
    assert enhancement["version"] == 1
    assert enhancement["items"][0]["element_id"] == "GUID-001"
    assert enhancement["items"][0]["changes"]["material"] == "stainless_steel"


def test_phase_1_analysis_and_enhancement_entry_points_are_explicit():
    element = SimpleNamespace(
        GlobalId="GUID-002",
        Name="Carbon Steel Valve",
        material="carbon_steel",
        environment="normal",
        system_type="Cooling Water",
        zone="Zone B",
        floor="Level 2",
        nominal_diameter_m=0.15,
        flow_velocity_ms=0.8,
        operating_temp_c=35.0,
        dead_leg_length_m=0.3,
        insulation_condition="poor",
    )

    analysis = run_compliance_analysis([element])
    assert analysis["pipeline"] == "audit"
    assert analysis["element_count"] == 1
    assert analysis["results"][0]["guid"] == "GUID-002"

    enhancement = enhance_model(
        [element],
        changes={"material": "duplex_steel", "insulation_condition": "improved"},
        version=2,
    )
    assert enhancement["pipeline"] == "enhancement"
    assert enhancement["version"] == 2
    assert enhancement["items"][0]["changes"]["material"] == "duplex_steel"


def test_enhancement_execution_creates_versioned_artifact_and_lineage(tmp_path):
    source_path = tmp_path / "source.ifc"
    source_content = b"ISO-10303-21;SOURCE"
    source_path.write_bytes(source_content)

    class FakeStorage:
        def __init__(self):
            self.upload = None

        def materialize_local_path(self, reference: str) -> Path | None:
            assert reference == "sb://models/source.ifc"
            return source_path

        def save_upload(self, filename: str, content: bytes, subdir: str) -> str:
            self.upload = (filename, content, subdir)
            return f"sb://models/{subdir}/{filename}"

    class FakeLineageLedger:
        def __init__(self):
            self.payload = None

        def find_by_source_sha256(self, project_id: int, source_sha256: str):
            assert project_id == 7
            assert len(source_sha256) == 64
            return None

        def allocate_next_version(self, project_id: int) -> int:
            assert project_id == 7
            return 2

        def record(self, **payload):
            self.payload = payload
            return {"id": 41, **payload}

    def fake_improver(input_path: str, output_path: str):
        assert Path(input_path).read_bytes() == source_content
        Path(output_path).write_bytes(b"ISO-10303-21;ENHANCED")
        return {
            "names_added": 3,
            "improvements": ["Names added: 3", f"Improved file saved: {output_path}"],
        }

    storage = FakeStorage()
    ledger = FakeLineageLedger()
    service = EnhancementService(
        storage=storage,
        lineage_ledger=ledger,
        improver=fake_improver,
    )

    result = execute_model_enhancement(
        project_id=7,
        source_reference="sb://models/source.ifc",
        service=service,
    )

    assert source_path.read_bytes() == source_content
    assert storage.upload == (
        "source_v2.ifc",
        b"ISO-10303-21;ENHANCED",
        "enhancements/7",
    )
    assert ledger.payload == {
        "project_id": 7,
        "source_reference": "sb://models/source.ifc",
        "source_sha256": "e58a58c9d2696b420664ea94919d1e68e2738d8d9f97d4a1e8691f950eb3a3e3",
        "source_version": 0,
        "output_reference": "sb://models/enhancements/7/source_v2.ifc",
        "version": 2,
        "summary": {
            "names_added": 3,
            "improvements": ["Names added: 3"],
            "generated_filename": "source_v2.ifc",
        },
    }
    assert result["lineage"]["id"] == 41
    assert "bim-guard-enhancement-" not in str(result["summary"])


def test_enhancement_reuses_persisted_result_for_identical_source(tmp_path: Path):
    source_content = b"ISO-10303-21;SAME-SOURCE"
    source_path = tmp_path / "source.ifc"
    source_path.write_bytes(source_content)

    class FakeStorage:
        def materialize_local_path(self, reference: str) -> Path | None:
            assert reference == "sb://models/source.ifc"
            return source_path

        def save_upload(self, filename: str, content: bytes, subdir: str) -> str:
            raise AssertionError("A repeated source must not create another artifact")

    existing = {
        "id": 42,
        "project_id": 7,
        "source_reference": "sb://models/source.ifc",
        "source_sha256": "ae4faabdf30c1fc45998f838ec549e221275b2f8356e252ea8460e3cd393af86",
        "output_reference": "sb://models/enhancements/7/source_v2.ifc",
        "version": 2,
        "summary": {"improvements": ["Names added: 3"]},
    }

    class FakeLineageLedger:
        def find_by_source_sha256(self, project_id: int, source_sha256: str):
            assert project_id == 7
            assert source_sha256 == existing["source_sha256"]
            return existing

        def allocate_next_version(self, project_id: int) -> int:
            raise AssertionError("A repeated source must not allocate another version")

        def record(self, **payload):
            raise AssertionError("A repeated source must not create another lineage row")

    service = EnhancementService(
        storage=FakeStorage(),
        lineage_ledger=FakeLineageLedger(),
        improver=lambda *_: (_ for _ in ()).throw(
            AssertionError("A repeated source must not run the improver")
        ),
    )

    result = service.execute(project_id=7, source_reference="sb://models/source.ifc")

    assert result["reused"] is True
    assert result["version"] == 2
    assert result["output_reference"] == existing["output_reference"]
    assert result["lineage"] == existing


def test_project_analysis_resolves_persisted_improved_ifc(tmp_path: Path):
    source_path = tmp_path / "source.ifc"
    improved_path = tmp_path / "source_v1.ifc"
    source_path.write_bytes(b"ISO-10303-21;CURRENT-SOURCE")
    improved_path.write_bytes(b"ISO-10303-21;PERSISTED-IMPROVED")
    source_sha256 = "c00361d22dbbeb6683f5c201159b7eef98267afd72ad3c704982fe899514422b"
    lineage = {
        "id": 21,
        "project_id": 7,
        "source_sha256": source_sha256,
        "output_reference": "sb://models/enhancements/7/source_v1.ifc",
        "version": 1,
        "summary": {"improvements": ["Names added: 1"]},
    }

    class FakeStorage:
        def materialize_local_path(self, reference: str) -> Path | None:
            assert reference == lineage["output_reference"]
            return improved_path

    class FakeLineage:
        def find_by_source_sha256(self, project_id: int, actual_sha256: str):
            assert project_id == 7
            assert actual_sha256 == source_sha256
            return lineage

    service = ProjectsService.__new__(ProjectsService)
    service._storage = FakeStorage()
    service._lineage = FakeLineage()
    service.resolve_ifc_file = lambda project_id: source_path

    resolved_path, resolved_lineage = service.resolve_analysis_ifc(7)

    assert resolved_path == improved_path
    assert resolved_lineage == lineage


def test_enhancement_execution_does_not_accept_caller_version():
    service = EnhancementService(storage=object(), lineage_ledger=object(), improver=lambda *_: {})

    try:
        service.execute(project_id=7, source_reference="sb://models/source.ifc", version=99)
    except TypeError as exc:
        assert "version" in str(exc)
    else:
        raise AssertionError("Caller-supplied model versions must be rejected")


def test_lineage_repository_uses_offline_persistence_fallback(monkeypatch):
    from app.services.model_lineage import SupabaseModelLineageRepository

    monkeypatch.setattr(PersistenceService, "_db", _MemoryClient())
    repository = SupabaseModelLineageRepository()

    row = repository.record(
        project_id=3,
        source_reference="sb://models/source.ifc",
        source_sha256="abc123",
        source_version=0,
        output_reference="sb://models/output.ifc",
        version=1,
        summary={"names_added": 2},
    )

    assert row["id"] == 1
    assert row["project_id"] == 3
    assert row["source_sha256"] == "abc123"
    assert row["summary"] == {"names_added": 2}
