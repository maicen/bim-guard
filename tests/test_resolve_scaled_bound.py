"""Unit tests for app.modules.ifc_reader._resolve_scaled_bound.

The arithmetic behind value_min_property/value_max_property's per-element
resolution (extract_for_compliance) -- lets a rule bound be expressed as
"K times a same-element property, plus/minus a fixed amount" (e.g. riser
height <= 0.5 * tread going), not just "that property plus/minus a fixed
amount" (scale always 1).
"""

from app.modules.ifc_reader import _resolve_scaled_bound


def test_scale_one_offset_zero_reproduces_the_raw_value():
    """A rule written before value_min_scale/value_max_scale existed is unaffected."""
    assert _resolve_scaled_bound(280.0, 1.0, 0.0) == 280.0


def test_offset_only_matches_pre_scale_behaviour():
    """'tread going + 25mm' -- the offset-only case this field already supported."""
    assert _resolve_scaled_bound(280.0, 1.0, 25.0) == 305.0


def test_scale_only_applies_the_multiplier():
    """'0.5x the tread going' -- riser height <= 0.5 * TreadGoing."""
    assert _resolve_scaled_bound(280.0, 0.5, 0.0) == 140.0


def test_scale_and_offset_combine_scale_first():
    """'0.5x the diagonal, plus 100mm' -- scale is applied before the offset is added."""
    assert _resolve_scaled_bound(1000.0, 0.5, 100.0) == 600.0


def test_result_is_rounded_to_four_decimal_places():
    assert _resolve_scaled_bound(1.0, 1.0 / 3.0, 0.0) == 0.3333
