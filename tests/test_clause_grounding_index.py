"""ClauseGroundingIndex: loads bim-guard-evaluation's promoted clause grounding JSON."""

import json

from app.services.clause_grounding_index import ClauseGroundingIndex


def _write_index(tmp_path, data: dict) -> ClauseGroundingIndex:
    path = tmp_path / "grounding_index.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return ClauseGroundingIndex(path=path)


def test_class_uris_for_known_clause(tmp_path):
    index = _write_index(
        tmp_path,
        {"A-1.1.2.7": {"classes": [{"uri": "urn:a", "score": 0.9}, {"uri": "urn:b", "score": 0.5}], "properties": []}},
    )

    assert index.class_uris_for("A-1.1.2.7") == ["urn:a", "urn:b"]


def test_class_uris_for_unknown_clause_is_empty(tmp_path):
    index = _write_index(tmp_path, {"A-1.1.2.7": {"classes": [{"uri": "urn:a"}], "properties": []}})

    assert index.class_uris_for("H999") == []


def test_class_uris_for_none_clause_id_is_empty_and_does_not_load(tmp_path):
    index = _write_index(tmp_path, {"A-1.1.2.7": {"classes": [{"uri": "urn:a"}], "properties": []}})

    assert index.class_uris_for(None) == []
    assert index._loaded is False  # short-circuits before ever touching disk


def test_property_hints_for_known_clause(tmp_path):
    entries = [{"uri": "urn:p", "name": "Fire Protection Class", "score": 0.85}]
    index = _write_index(tmp_path, {"H9": {"classes": [], "properties": entries}})

    assert index.property_hints_for("H9") == entries


def test_missing_file_is_tolerated(tmp_path):
    index = ClauseGroundingIndex(path=tmp_path / "does-not-exist.json")

    assert index.class_uris_for("A-1.1.2.7") == []
    assert index.property_hints_for("A-1.1.2.7") == []


def test_malformed_file_is_tolerated(tmp_path):
    path = tmp_path / "grounding_index.json"
    path.write_text("{not valid json", encoding="utf-8")
    index = ClauseGroundingIndex(path=path)

    assert index.class_uris_for("A-1.1.2.7") == []


def test_loads_only_once(tmp_path):
    path = tmp_path / "grounding_index.json"
    path.write_text(json.dumps({"A-1.1.2.7": {"classes": [{"uri": "urn:a"}], "properties": []}}), encoding="utf-8")
    index = ClauseGroundingIndex(path=path)

    index.class_uris_for("A-1.1.2.7")
    path.write_text(json.dumps({"A-1.1.2.7": {"classes": [{"uri": "urn:changed"}], "properties": []}}), encoding="utf-8")

    assert index.class_uris_for("A-1.1.2.7") == ["urn:a"]  # first load is cached, file change ignored
