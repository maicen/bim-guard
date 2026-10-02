"""The per-run element memo in IFCReader: scoped to one extraction run."""

from __future__ import annotations

from app.modules.ifc_reader import IFCReader


class _El:
    def __init__(self, eid: int) -> None:
        self._eid = eid

    def id(self) -> int:
        return self._eid


def _reader() -> IFCReader:
    reader = IFCReader.__new__(IFCReader)
    reader._element_memo = None
    return reader


def test_memo_is_inactive_outside_an_extraction_run():
    reader = _reader()
    calls = []
    for _ in range(3):
        reader._memo("k", _El(1), lambda e: calls.append(e.id()) or "v")
    assert calls == [1, 1, 1]


def test_memo_computes_once_per_element_and_kind_during_a_run():
    reader = _reader()
    reader._element_memo = {}
    calls = []

    def compute(e):
        calls.append(e.id())
        return {"value": e.id()}

    assert reader._memo("psets", _El(1), compute) == {"value": 1}
    assert reader._memo("psets", _El(1), compute) == {"value": 1}
    reader._memo("psets", _El(2), compute)
    reader._memo("rich", _El(1), compute)
    assert calls == [1, 2, 1]


def test_memo_caches_none_but_not_exceptions():
    reader = _reader()
    reader._element_memo = {}
    calls = []

    def none_compute(e):
        calls.append("none")
        return None

    reader._memo("type", _El(1), none_compute)
    reader._memo("type", _El(1), none_compute)
    assert calls == ["none"]

    def failing(e):
        calls.append("fail")
        raise RuntimeError("boom")

    for _ in range(2):
        try:
            reader._memo("direct", _El(1), failing)
        except RuntimeError:
            pass
    assert calls.count("fail") == 2


def test_extract_for_compliance_drops_the_memo_afterwards(monkeypatch):
    reader = _reader()
    seen = {}

    def fake_extract(rules):
        seen["memo_during_run"] = reader._element_memo
        return []

    monkeypatch.setattr(reader, "_extract_for_compliance", fake_extract)
    reader.extract_for_compliance([])
    assert seen["memo_during_run"] == {}
    assert reader._element_memo is None
