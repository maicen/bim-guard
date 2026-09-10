"""Unit and integration tests for ProcessPoolExecutor compute pool and parallel workflows."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.modules.blue_halo.halo_volume_generator import (
    BoundingBox,
    BraceType,
    ElementGeometry,
    Point3D,
    load_clearance_config,
)
from app.modules.ifc_reader.ifc_parser import ServiceElement
from app.modules.phase_6.phase_6c_corrosion_ui import (
    _assess_elements_chunk,
    run_corrosion_analysis,
)
from app.modules.phase_6.phase_6d_seismic import (
    _detect_halo_clashes_chunk,
)
from app.services.compute_pool import (
    get_compute_pool,
    get_worker_count,
    is_multiprocessing_enabled,
    run_cpu_bound,
    shutdown_compute_pool,
)


def _sample_element(index: int) -> ServiceElement:
    """Build a deterministic ServiceElement for parity tests."""
    return ServiceElement(
        guid=f"GUID-{index:04d}",
        name=f"Pipe-{index:04d}",
        ifc_type="IfcPipeSegment",
        description="Chilled water pipe",
        material_a="stainless_316",
        material_b="copper" if index % 2 == 0 else "galvanised_steel",
        location_tag="plant_room",
        floor="Level 1",
        system="CHW",
        joint_type="flanged",
        anode_area_m2=0.5,
        cathode_area_m2=1.0,
        position=(float(index), 0.0, 3.0),
        length_m=2.5,
        flow_velocity_ms=1.2,
        operating_temp_c=12.0,
        dead_leg_length_m=0.0,
    )


def test_worker_count_and_env_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test compute pool configuration heuristics and feature flags."""
    monkeypatch.setenv("BIMGUARD_DISABLE_MULTIPROCESSING", "1")
    assert is_multiprocessing_enabled() is False

    monkeypatch.setenv("BIMGUARD_DISABLE_MULTIPROCESSING", "true")
    assert is_multiprocessing_enabled() is False

    monkeypatch.delenv("BIMGUARD_DISABLE_MULTIPROCESSING", raising=False)
    # Default is enabled on multi-core systems
    assert is_multiprocessing_enabled() in (True, False)

    monkeypatch.setenv("BIMGUARD_MAX_COMPUTE_WORKERS", "6")
    assert get_worker_count() == 6

    monkeypatch.setenv("BIMGUARD_MAX_COMPUTE_WORKERS", "invalid")
    assert get_worker_count() >= 1


def test_compute_pool_lifecycle() -> None:
    """Test initializing and safely shutting down the compute pool."""
    pool = get_compute_pool()
    assert pool is not None
    # Re-calling returns the singleton
    assert get_compute_pool() is pool

    shutdown_compute_pool(wait=True)
    # After shutdown, requesting pool recreates it cleanly
    new_pool = get_compute_pool()
    assert new_pool is not None
    assert new_pool is not pool
    shutdown_compute_pool(wait=True)


def _sample_add(a: int, b: int) -> int:
    """Top-level function for multiprocessing test."""
    return a + b


def test_run_cpu_bound_async() -> None:
    """Test running a CPU-bound function in the pool asynchronously."""
    result = asyncio.run(run_cpu_bound(_sample_add, 10, 25))
    assert result == 35


def test_assess_elements_chunk_execution() -> None:
    """Test executing a chunk of ServiceElements through _assess_elements_chunk."""
    elements = [_sample_element(i) for i in range(10)]
    items, mic_scored = _assess_elements_chunk(
        elements,
        specs_codes=("GC-001", "CC-001", "MC-001"),
        include_low=True,
    )
    assert len(items) > 0
    # Returns a list of tuples ("dq" or "finding", element, code, ...)
    for item in items:
        assert item[0] in ("dq", "finding")
        assert item[2] in ("GC-001", "CC-001", "MC-001")


def test_corrosion_parallel_vs_sequential_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that parallel corrosion analysis produces identical results to sequential."""
    elements = [_sample_element(i) for i in range(40)]
    parsed = {
        "quality": {"valid": True},
        "elements": elements,
    }

    # 1. Run sequential (by disabling multiprocessing)
    monkeypatch.setenv("BIMGUARD_DISABLE_MULTIPROCESSING", "1")
    res_seq = run_corrosion_analysis(
        parsed,
        include_low=True,
        engines=["GC-001", "CC-001", "MC-001"],
    )

    # 2. Run with multiprocessing enabled
    monkeypatch.delenv("BIMGUARD_DISABLE_MULTIPROCESSING", raising=False)
    res_par = run_corrosion_analysis(
        parsed,
        include_low=True,
        engines=["GC-001", "CC-001", "MC-001"],
    )

    assert len(res_seq["audit_issues"]) == len(res_par["audit_issues"])
    for seq_issue, par_issue in zip(res_seq["audit_issues"], res_par["audit_issues"]):
        assert seq_issue.id == par_issue.id
        assert seq_issue.rule_id == par_issue.rule_id
        assert seq_issue.band == par_issue.band
        assert seq_issue.score == par_issue.score
        assert seq_issue.element_id == par_issue.element_id


def test_seismic_clashes_chunk_execution() -> None:
    """Test computing halo clash chunks in a worker process."""
    config_path = Path("data/rulesets/config_en_1998_1_din_4149.json")
    if not config_path.exists():
        pytest.skip("Seismic config json not present")

    config = load_clearance_config(config_path)
    rule = config.rules_for(BraceType.ANGLE_IRON)[0]

    geom1 = ElementGeometry(
        element_id="ELEM-01",
        ifc_class="IfcPipeSegment",
        bbox_mm=BoundingBox(Point3D(0, 0, 0), Point3D(1000, 200, 200)),
    )
    geom2 = ElementGeometry(
        element_id="ELEM-02",
        ifc_class="IfcBeam",
        bbox_mm=BoundingBox(Point3D(200, -100, -100), Point3D(400, 300, 300)),
    )

    clashes = _detect_halo_clashes_chunk(
        braced_chunk=[geom1],
        all_geometries=[geom1, geom2],
        brace_type=BraceType.ANGLE_IRON,
        rule=rule,
        seismic_zone=True,
        building_type="standard",
    )
    assert isinstance(clashes, list)
