"""Rule-configuration snapshot persistence (RuleSnapshotService)."""

import pytest

from app.services.rule_snapshot_service import RuleSnapshotService


class FakeTable:
    """Minimal in-memory stand-in for a PersistenceService table adapter."""

    def __init__(self) -> None:
        self._rows: dict[int, dict] = {}
        self._next_id = 1

    @property
    def rows(self):
        return list(self._rows.values())

    def insert(self, payload: dict) -> dict:
        row = {"id": self._next_id, **payload}
        self._rows[self._next_id] = row
        self._next_id += 1
        return dict(row)

    def get(self, pk):
        row = self._rows.get(pk)
        return dict(row) if row is not None else None

    def delete(self, pk) -> None:
        self._rows.pop(pk, None)


class FakeRuleService:
    """Stand-in for RuleService — serves fixed rules for one ruleset_id."""

    def __init__(self, rules_by_ruleset: dict[str, list[dict]], folder: dict | None = None) -> None:
        self._rules_by_ruleset = rules_by_ruleset
        self._folder = folder

    def list_by_ruleset(self, ruleset_id: str) -> list[dict]:
        return list(self._rules_by_ruleset.get(ruleset_id, []))

    def get_folder(self, ruleset_id: str) -> dict | None:
        return self._folder


def _rules() -> list[dict]:
    return [
        {"id": 1, "reference": "R-1", "target_ifc_class": "IfcWindow", "property_name": "FireRating"},
        {"id": 2, "reference": "R-2", "target_ifc_class": "IfcWindow", "property_name": "AcousticRating"},
    ]


def _service(rules_by_ruleset: dict[str, list[dict]] | None = None, folder: dict | None = None):
    table = FakeTable()
    rule_service = FakeRuleService(rules_by_ruleset or {"FOLDER-A": _rules()}, folder)
    return RuleSnapshotService(snapshots_repo=table, rule_service=rule_service), table, rule_service


def test_create_snapshot_from_empty_ruleset_raises():
    service, _, _ = _service(rules_by_ruleset={})
    with pytest.raises(ValueError):
        service.create_snapshot(ruleset_id="NO-SUCH-FOLDER")


def test_create_snapshot_freezes_current_rules():
    service, _, _ = _service()
    snap = service.create_snapshot(ruleset_id="FOLDER-A", name="My Config", source_mode="manual")
    assert snap["rule_count"] == 2
    assert snap["source_ruleset_id"] == "FOLDER-A"
    assert snap["name"] == "My Config"


def test_create_snapshot_invalid_source_mode_falls_back_to_manual():
    service, _, _ = _service()
    snap = service.create_snapshot(ruleset_id="FOLDER-A", source_mode="not-a-real-mode")
    assert snap["source_mode"] == "manual"


def test_create_snapshot_uses_folder_category_when_available():
    service, _, _ = _service(folder={"category": "Piping"})
    snap = service.create_snapshot(ruleset_id="FOLDER-A")
    assert snap["category"] == "Piping"


def test_list_get_delete_round_trip():
    service, _, _ = _service()
    snap = service.create_snapshot(ruleset_id="FOLDER-A", name="Config 1")
    snap_id = snap["id"]

    listed = service.list_snapshots()
    assert any(s["id"] == snap_id for s in listed)

    got = service.get_snapshot(snap_id)
    assert got is not None
    assert got["name"] == "Config 1"

    assert service.get_snapshot(999) is None

    assert service.delete_snapshot(snap_id) is True
    assert service.get_snapshot(snap_id) is None
    assert service.delete_snapshot(snap_id) is False


def test_get_snapshot_rules_returns_frozen_copy_not_live_reference():
    """The core requirement: a snapshot must survive later edits/deletes to
    the source ruleset — it freezes a copy, not a live pointer."""
    rules_by_ruleset = {"FOLDER-A": _rules()}
    service, _, rule_service = _service(rules_by_ruleset=rules_by_ruleset)

    snap = service.create_snapshot(ruleset_id="FOLDER-A")
    frozen = service.get_snapshot_rules(snap["id"])
    assert len(frozen) == 2

    # Mutate the "live" source after the snapshot was taken.
    rules_by_ruleset["FOLDER-A"].clear()
    assert rule_service.list_by_ruleset("FOLDER-A") == []

    still_frozen = service.get_snapshot_rules(snap["id"])
    assert len(still_frozen) == 2, "snapshot rules must be unaffected by later edits to the source ruleset"


def test_get_snapshot_rules_decodes_json_string_from_sqlite_backend():
    """The SQLite adapter round-trips rules_json as a JSON string, not a
    native list (see rule_snapshot_service.get_snapshot_rules docstring) —
    confirm the string case is handled, not just the native-list case."""
    table = FakeTable()
    rule_service = FakeRuleService({"FOLDER-A": _rules()})
    service = RuleSnapshotService(snapshots_repo=table, rule_service=rule_service)

    snap = service.create_snapshot(ruleset_id="FOLDER-A")
    # Simulate what the SQLite backend actually returns: a JSON string.
    import json

    table._rows[snap["id"]]["rules_json"] = json.dumps(_rules())

    rules = service.get_snapshot_rules(snap["id"])
    assert rules == _rules()


def test_get_snapshot_rules_handles_malformed_json_gracefully():
    table = FakeTable()
    rule_service = FakeRuleService({"FOLDER-A": _rules()})
    service = RuleSnapshotService(snapshots_repo=table, rule_service=rule_service)

    snap = service.create_snapshot(ruleset_id="FOLDER-A")
    table._rows[snap["id"]]["rules_json"] = "{not valid json"

    assert service.get_snapshot_rules(snap["id"]) == []
