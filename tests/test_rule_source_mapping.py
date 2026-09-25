"""Tests for group_rows_by_element (rule-source map grouping helper)."""

from app.modules.contracts import DocumentElementBbox
from app.services.rule_source_mapping import group_rows_by_element


def _elements() -> list[DocumentElementBbox]:
    return [
        DocumentElementBbox(element_id="elem-1", kind="heading", page_number=1, order=0),
        DocumentElementBbox(element_id="elem-2", kind="paragraph", page_number=1, order=1),
    ]


def test_group_rows_by_element_exact_match():
    rows = [{"id": 1, "source_element_id": "elem-2"}]
    by_element, unmapped, orphaned = group_rows_by_element(_elements(), rows)

    assert by_element == {"elem-2": [rows[0]]}
    assert unmapped == []
    assert orphaned == []


def test_group_rows_by_element_unmapped_when_no_source_element_id():
    rows = [{"id": 1, "source_element_id": None}, {"id": 2}]
    by_element, unmapped, orphaned = group_rows_by_element(_elements(), rows)

    assert by_element == {}
    assert unmapped == rows
    assert orphaned == []


def test_group_rows_by_element_orphaned_when_element_id_no_longer_exists():
    """A row with a stale source_element_id must be surfaced, never dropped.

    Happens when the source document is re-parsed/re-uploaded and element
    ids shift.
    """
    rows = [{"id": 1, "source_element_id": "elem-99"}]
    by_element, unmapped, orphaned = group_rows_by_element(_elements(), rows)

    assert by_element == {}
    assert unmapped == []
    assert orphaned == rows


def test_group_rows_by_element_every_row_accounted_for():
    rows = [
        {"id": 1, "source_element_id": "elem-1"},
        {"id": 2, "source_element_id": None},
        {"id": 3, "source_element_id": "elem-404"},
        {"id": 4, "source_element_id": "elem-1"},
    ]
    by_element, unmapped, orphaned = group_rows_by_element(_elements(), rows)

    total = sum(len(v) for v in by_element.values()) + len(unmapped) + len(orphaned)
    assert total == len(rows)
    assert by_element["elem-1"] == [rows[0], rows[3]]
    assert unmapped == [rows[1]]
    assert orphaned == [rows[2]]
