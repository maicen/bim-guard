from pathlib import Path
from types import SimpleNamespace

from app.modules.pipeline_services import (
    AnalysisService,
    EnhancementService,
    enhance_model,
    execute_model_enhancement,
    run_compliance_analysis,
)
from app.services.persistence import PersistenceService, _MemoryClient


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

    analysis = AnalysisService().run([element])
    assert analysis["pipeline"] == "analysis"
    assert analysis["element_count"] == 1
    assert "results" in analysis
    assert isinstance(analysis["results"], list)

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
    assert analysis["pipeline"] == "analysis"
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

        def record(self, **payload):
            self.payload = payload
            return {"id": 41, **payload}

    def fake_improver(input_path: str, output_path: str):
        assert Path(input_path).read_bytes() == source_content
        Path(output_path).write_bytes(b"ISO-10303-21;ENHANCED")
        return {"names_added": 3}

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
        version=2,
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
        "output_reference": "sb://models/enhancements/7/source_v2.ifc",
        "version": 2,
        "summary": {"names_added": 3},
    }
    assert result["lineage"]["id"] == 41


def test_enhancement_execution_rejects_non_positive_version():
    service = EnhancementService(storage=object(), lineage_ledger=object(), improver=lambda *_: {})

    try:
        service.execute(project_id=7, source_reference="sb://models/source.ifc", version=0)
    except ValueError as exc:
        assert str(exc) == "version must be greater than zero"
    else:
        raise AssertionError("Expected a non-positive model version to be rejected")


def test_lineage_repository_uses_offline_persistence_fallback(monkeypatch):
    from app.services.model_lineage import SupabaseModelLineageRepository

    monkeypatch.setattr(PersistenceService, "_db", _MemoryClient())
    repository = SupabaseModelLineageRepository()

    row = repository.record(
        project_id=3,
        source_reference="sb://models/source.ifc",
        output_reference="sb://models/output.ifc",
        version=1,
        summary={"names_added": 2},
    )

    assert row["id"] == 1
    assert row["project_id"] == 3
    assert row["summary"] == {"names_added": 2}
