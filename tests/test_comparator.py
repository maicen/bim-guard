"""
Unit tests for Module4_Comparator operators.

Tests 10 operators across 3 dispatch paths (exists, numeric compare, string
compare), the boolean fast path, status aggregation (5 outcomes), and four
known defects that currently cause silent passes.

Run: uv run pytest tests/test_comparator.py -v
"""

import pytest

from app.modules.module4_comparator import Module4_Comparator


@pytest.fixture
def cmp():
    """Return a comparator instance; it is stateless, so one per test is cheap."""
    return Module4_Comparator()


def verdict(cmp, operator, actual, check_val=None, val_min=None, val_max=None, unit=""):
    """Call _compare and return only the boolean verdict."""
    ok, _reason = cmp._compare(operator, actual, check_val, val_min, val_max, unit)
    return ok


def element(actual_value, **extra):
    """Build a Module 2-shaped element dict."""
    el = {"name": "E1", "guid": "guid-1", "actual_value": actual_value}
    el.update(extra)
    return el


def evaluate(cmp, operator, elements, **rule):
    """Run one rule through the public entry point and return its record."""
    item = {"operator": operator, "elements": elements}
    item.update(rule)
    return cmp.validate_metadata([item])[0]


class TestExistsOperators:
    """Path A: _evaluate_rule handles exists/not_exists before _compare."""

    def test_exists_with_none(self, cmp):
        """Operator exists: None should fail."""
        assert evaluate(cmp, "exists", [element(None)])["status"] == "FAIL"

    def test_exists_with_string(self, cmp):
        """Operator exists: non-empty string passes."""
        assert evaluate(cmp, "exists", [element("value")])["status"] == "PASS"

    def test_exists_with_empty_string(self, cmp):
        """Operator exists: empty string passes (presence, not truthiness)."""
        assert evaluate(cmp, "exists", [element("")])["status"] == "PASS"

    def test_exists_with_false(self, cmp):
        """Operator exists: False passes (presence, not truthiness)."""
        assert evaluate(cmp, "exists", [element(False)])["status"] == "PASS"

    def test_exists_with_zero(self, cmp):
        """Operator exists: 0 passes (presence, not truthiness)."""
        assert evaluate(cmp, "exists", [element(0)])["status"] == "PASS"

    def test_not_exists_with_none(self, cmp):
        """Operator not_exists: None should pass."""
        assert evaluate(cmp, "not_exists", [element(None)])["status"] == "PASS"

    def test_not_exists_with_value(self, cmp):
        """Operator not_exists: any value fails."""
        assert evaluate(cmp, "not_exists", [element("value")])["status"] == "FAIL"

    def test_exists_never_counts_as_missing(self, cmp):
        """Rules using exists bypass the missing-data branch entirely."""
        result = evaluate(cmp, "exists", [element(None)])
        assert result["missing_count"] == 0
        assert result["fail_count"] == 1


class TestNumericOperators:
    """Path B: _compare numeric branch (>= <= > <, ==, !=, between)."""

    @pytest.mark.parametrize(
        "op,actual,check_val,expected",
        [
            (">=", 5, 5, True),
            (">=", 4.9, 5, False),
            ("<=", 5, 5, True),
            ("<=", 5.1, 5, False),
            (">", 5.1, 5, True),
            (">", 5, 5, False),
            ("<", 4.9, 5, True),
            ("<", 5, 5, False),
            ("==", 5, 5, True),
            ("==", 5.1, 5, False),
            ("!=", 5.1, 5, True),
            ("!=", 5, 5, False),
        ],
    )
    def test_comparison_operators(self, cmp, op, actual, check_val, expected):
        """Numeric comparison operators with boundary cases."""
        assert verdict(cmp, op, actual, check_val) is expected

    @pytest.mark.parametrize("op", [">=", "<=", ">", "<", "==", "!="])
    def test_comparison_with_none_check_val(self, cmp, op):
        """Numeric comparison with check_val=None should fail, not crash."""
        assert verdict(cmp, op, 5, None) is False

    def test_numeric_string_actual_is_coerced(self, cmp):
        """Actual values arrive as strings from some IFC property sets."""
        assert verdict(cmp, ">=", "900", 900) is True

    def test_numeric_equality_bool_is_int(self, cmp):
        """Numeric == : 1 == True (bool is an int subclass)."""
        assert verdict(cmp, "==", 1, True) is True

    def test_non_numeric_threshold_fails_cleanly(self, cmp):
        """A malformed rule threshold must fail, not raise TypeError."""
        assert verdict(cmp, ">=", 900, "eight hundred") is False

    def test_between_basic(self, cmp):
        """Operator between: value in range."""
        assert verdict(cmp, "between", 150, None, 100, 200) is True

    @pytest.mark.parametrize(
        "actual,expected", [(100, True), (200, True), (99, False), (201, False)]
    )
    def test_between_boundaries(self, cmp, actual, expected):
        """Operator between is inclusive at both ends."""
        assert verdict(cmp, "between", actual, None, 100, 200) is expected

    def test_between_missing_bound_fails(self, cmp):
        """Operator between with an unset bound fails rather than passing vacuously."""
        assert verdict(cmp, "between", 150, None, 100, None) is False

    def test_between_with_resolved_override(self, cmp):
        """Per-element resolved bounds override the rule-level bounds.

        Resolution happens in _evaluate_rule, so this must go through
        validate_metadata rather than _compare directly.
        """
        el = element(300, resolved_value_min=250, resolved_value_max=350)
        result = evaluate(cmp, "between", [el], value_min=100, value_max=200)
        assert result["status"] == "PASS"

    def test_rule_bounds_used_when_no_resolved_bounds(self, cmp):
        """Falls back to rule-level bounds when the element resolved none."""
        result = evaluate(cmp, "between", [element(300)], value_min=100, value_max=200)
        assert result["status"] == "FAIL"


class TestStringOperators:
    """Path C: _compare string fallback, reached only when float() raises."""

    def test_string_equality_case_sensitive(self, cmp):
        """String == : case sensitive."""
        assert verdict(cmp, "==", "TRUE", "True") is False

    def test_string_equality_match(self, cmp):
        """String == : identical strings pass."""
        assert verdict(cmp, "==", "FD30S", "FD30S") is True

    def test_string_inequality(self, cmp):
        """String != : differing strings pass."""
        assert verdict(cmp, "!=", "FD30S", "FD60S") is True

    def test_matches_valid_regex(self, cmp):
        """Operator matches: valid regex."""
        assert verdict(cmp, "matches", "abc123", r"[a-z]+\d+") is True

    def test_matches_no_match(self, cmp):
        """Operator matches: non-matching pattern fails."""
        assert verdict(cmp, "matches", "abc", r"^\d+$") is False

    def test_matches_invalid_regex(self, cmp):
        """Operator matches: invalid regex returns False."""
        assert verdict(cmp, "matches", "test", r"[invalid") is False


class TestBooleanFastPath:
    """Boolean shortcut in _compare, active when actual is a real bool."""

    @pytest.mark.parametrize("alias", ["TRUE", "true", "True", "yes", "YES"])
    def test_bool_equals_true_alias(self, cmp, alias):
        """Boolean == : True matches any truthy alias, any case."""
        assert verdict(cmp, "==", True, alias) is True

    @pytest.mark.parametrize("alias", ["FALSE", "false", "no"])
    def test_bool_equals_false_alias(self, cmp, alias):
        """Boolean == : True does not match a falsy alias."""
        assert verdict(cmp, "==", True, alias) is False

    def test_bool_not_equals_alias(self, cmp):
        """Boolean != : inverse of the alias comparison."""
        assert verdict(cmp, "!=", True, "FALSE") is True

    def test_bool_equals_non_alias_int(self, cmp):
        """Boolean == : True == 1 fails (1 is not in the alias table)."""
        assert verdict(cmp, "==", True, 1) is False


class TestStatusAggregation:
    """_evaluate_rule rolls per-element verdicts into one of 5 statuses."""

    def test_no_elements(self, cmp):
        """A rule matching nothing reports NO_ELEMENTS."""
        assert evaluate(cmp, ">=", [], check_value=900)["status"] == "NO_ELEMENTS"

    def test_all_pass(self, cmp):
        """Every element passing reports PASS."""
        result = evaluate(cmp, ">=", [element(1000), element(950)], check_value=900)
        assert result["status"] == "PASS"
        assert (result["pass_count"], result["fail_count"]) == (2, 0)

    def test_any_fail(self, cmp):
        """One failure is enough to report FAIL."""
        result = evaluate(cmp, ">=", [element(800), element(950)], check_value=900)
        assert result["status"] == "FAIL"
        assert (result["pass_count"], result["fail_count"]) == (1, 1)

    def test_all_missing(self, cmp):
        """No readable values at all reports MISSING_DATA."""
        result = evaluate(cmp, ">=", [element(None), element(None)], check_value=900)
        assert result["status"] == "MISSING_DATA"
        assert result["missing_count"] == 2

    def test_missing_alongside_pass(self, cmp):
        """Partial data with no failures reports PARTIAL."""
        result = evaluate(cmp, ">=", [element(None), element(950)], check_value=900)
        assert result["status"] == "PARTIAL"

    def test_fail_outranks_missing(self, cmp):
        """FAIL wins over MISSING when both are present."""
        result = evaluate(cmp, ">=", [element(None), element(800)], check_value=900)
        assert result["status"] == "FAIL"

    def test_failure_detail_recorded(self, cmp):
        """Failures carry element identity through for Module 5 reporting."""
        result = evaluate(cmp, ">=", [element(800)], check_value=900, unit="mm")
        assert len(result["failures"]) == 1
        assert result["failures"][0]["guid"] == "guid-1"
        assert "900" in result["failures"][0]["reason"]

    def test_all_elements_records_every_verdict(self, cmp):
        """all_elements holds one entry per element regardless of verdict."""
        elements = [element(1000), element(800), element(None)]
        result = evaluate(cmp, ">=", elements, check_value=900)
        assert [e["status"] for e in result["all_elements"]] == ["PASS", "FAIL", "MISSING"]


class TestDefects:
    """Tests exposing known defects. Each currently returns a silent PASS."""

    @pytest.mark.xfail(reason="DEFECT: matches unreachable for numeric-looking strings")
    def test_matches_numeric_string_defect(self, cmp):
        r"""DEFECT: matches doesn't work on numeric-looking strings.

        actual="900" parses as a float, so it takes the numeric branch and
        never reaches the string fallback where matches lives. It should fail
        pattern ^\d{2}$ but hits the catch-all else and silently passes.
        """
        assert verdict(cmp, "matches", "900", r"^\d{2}$") is False

    @pytest.mark.xfail(reason="DEFECT: unknown operator silently passes")
    def test_unknown_operator_should_fail(self, cmp):
        """DEFECT: a typo'd operator falls through the else and passes."""
        assert verdict(cmp, "typo_operator", 100, 50) is False

    @pytest.mark.xfail(reason="DEFECT: empty operator silently passes")
    def test_empty_operator_should_fail(self, cmp):
        """DEFECT: operator='' passes; reachable from create_rule defaults."""
        assert verdict(cmp, "", 100, 50) is False

    @pytest.mark.xfail(reason="DEFECT: comma stripping mangles European decimals")
    def test_european_decimal_not_mangled(self, cmp):
        """DEFECT: float parsing strips commas unconditionally.

        "1,2" (1.2 in European notation) becomes 12.0, a 10x error. Against a
        threshold of 10 the true value fails and the mangled value passes, so
        the corruption silently converts a violation into compliance.
        """
        assert verdict(cmp, ">=", "1,2", 10) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
