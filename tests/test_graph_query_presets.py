"""Tests for the GraphRAG query console's server-scoped Cypher presets.

Runs against a real embedded KùzuDB (not mocked) -- these presets exist
specifically because free-form Cypher would leak across projects, so the
thing worth verifying is that the *preset* text is both syntactically valid
against a real backend and actually scopes to the given project_id, not
just that the Python around it behaves.
"""

from __future__ import annotations

import pytest

from app.services.graph_database import GraphService
from app.services.graph_query_presets import (
    GRAPH_QUERY_PRESETS,
    get_preset,
    run_preset,
)
from app.services.kuzu_provider import KuzuDatabaseProvider


@pytest.fixture
def graph_service(tmp_path) -> GraphService:
    provider = KuzuDatabaseProvider(db_path=str(tmp_path / "graph"))
    service = GraphService(provider=provider)

    # Two projects' worth of data, deliberately interleaved, so any preset
    # that forgot to filter by project_id would show up immediately.
    service.add_nodes_batch(
        "IfcWall",
        [
            {"id": "P1-W1", "guid": "W1", "name": "Wall 1", "ifc_type": "IfcWall", "project_id": "1"},
            {"id": "P2-W1", "guid": "W1", "name": "Other Wall", "ifc_type": "IfcWall", "project_id": "2"},
        ],
    )
    service.add_nodes_batch(
        "IfcDoor",
        [
            {"id": "P1-D1", "guid": "D1", "name": "Door 1", "ifc_type": "IfcDoor", "project_id": "1"},
            {"id": "P1-D2", "guid": "D2", "name": "Door 2", "ifc_type": "IfcDoor", "project_id": "1"},
        ],
    )
    service.add_edges_batch(
        "CONTAINS",
        [
            {"source_id": "P1-W1", "target_id": "P1-D1", "properties": {}},
            {"source_id": "P1-W1", "target_id": "P1-D2", "properties": {}},
        ],
        from_label="IfcWall",
        to_label="IfcDoor",
    )
    return service


def test_every_preset_is_registered_with_a_unique_key():
    keys = [preset.key for preset in GRAPH_QUERY_PRESETS]
    assert len(keys) == len(set(keys))
    assert len(keys) >= 1


def test_get_preset_returns_none_for_an_unknown_key():
    assert get_preset("not-a-real-preset") is None


def test_element_counts_by_type_is_scoped_to_the_given_project(graph_service):
    preset = get_preset("element-counts-by-type")

    rows = run_preset(graph_service, preset, project_id=1, params={})

    counts = {row["type"]: row["count"] for row in rows}
    assert counts == {"IfcWall": 1, "IfcDoor": 2}  # not project 2's wall


def test_most_connected_elements_is_scoped_to_the_given_project(graph_service):
    preset = get_preset("most-connected-elements")

    rows = run_preset(graph_service, preset, project_id=1, params={})

    names = {row["name"] for row in rows}
    assert names == {"Wall 1", "Door 1", "Door 2"}
    assert "Other Wall" not in names


def test_element_neighbors_requires_its_declared_guid_param(graph_service):
    preset = get_preset("element-neighbors")

    rows = run_preset(graph_service, preset, project_id=1, params={"guid": "W1"})

    names = {row["name"] for row in rows}
    assert names == {"Door 1", "Door 2"}


def test_run_preset_rejects_a_missing_required_param(graph_service):
    preset = get_preset("element-neighbors")

    with pytest.raises(ValueError, match="missing required params"):
        run_preset(graph_service, preset, project_id=1, params={})


def test_run_preset_rejects_an_undeclared_extra_param(graph_service):
    preset = get_preset("element-counts-by-type")

    with pytest.raises(ValueError, match="does not accept params"):
        run_preset(graph_service, preset, project_id=1, params={"guid": "W1"})


def test_run_preset_never_accepts_project_id_as_a_param(graph_service):
    """project_id is always the function's own keyword arg.

    A caller cannot smuggle a different one through `params` to read
    another project's data.
    """
    preset = get_preset("element-counts-by-type")

    with pytest.raises(ValueError, match="does not accept params"):
        run_preset(graph_service, preset, project_id=1, params={"project_id": "2"})
