"""In-process progress tracking for document rule-draft extraction."""

from app.services import extraction_progress


def setup_function(_fn):
    extraction_progress.STORE.clear()


def test_unstarted_document_has_no_snapshot():
    assert extraction_progress.snapshot(999) is None


def test_start_then_increment_tracks_progress():
    extraction_progress.start(1, total=5)
    extraction_progress.increment(1)
    extraction_progress.increment(1)

    snap = extraction_progress.snapshot(1)
    assert snap.total == 5
    assert snap.completed == 2
    assert snap.status == "running"


def test_complete_sets_status():
    extraction_progress.start(2, total=3)
    extraction_progress.increment(2)
    extraction_progress.complete(2)

    snap = extraction_progress.snapshot(2)
    assert snap.status == "complete"
    assert snap.completed == 1


def test_fail_records_error():
    extraction_progress.start(3, total=4)
    extraction_progress.fail(3, "boom")

    snap = extraction_progress.snapshot(3)
    assert snap.status == "failed"
    assert snap.error == "boom"


def test_start_resets_a_prior_run_for_the_same_document():
    extraction_progress.start(4, total=10)
    extraction_progress.increment(4)
    extraction_progress.increment(4)

    extraction_progress.start(4, total=2)

    snap = extraction_progress.snapshot(4)
    assert snap.total == 2
    assert snap.completed == 0
    assert snap.status == "running"


def test_increment_and_complete_are_no_ops_when_untracked():
    extraction_progress.increment(12345)
    extraction_progress.complete(12345)
    extraction_progress.fail(12345, "boom")

    assert extraction_progress.snapshot(12345) is None
