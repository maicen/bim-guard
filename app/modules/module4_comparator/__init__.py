"""
module4_comparator.py
----------------------
Compares IFC property values extracted by Module 2 against the rule library.

For each rule:
  - Applies operator + threshold(s) to every matching element
  - Returns PASS / FAIL / MISSING_DATA / PARTIAL / NO_ELEMENTS per rule
  - Collects per-element failure details for Module 5 reporting

Operators: >= <= > < == != between exists not_exists matches
           field_consistency unique_within_scope
"""

import re

# Case-insensitive string forms a rule's check_value might use for a boolean
# IFC property (IsExternal, SelfClosing, SmokeStop, HandicapAccessible, …).
_BOOL_ALIASES = {"true": True, "false": False, "yes": True, "no": False}


class Module4_Comparator:
    """Validates IFC model data against the BIMGuard rule library."""

    # ── Public API ────────────────────────────────────────────────────────────

    def validate_metadata(self, extraction_results: list[dict]) -> list[dict]:
        """
        Main entry point. Takes Module2_IFCRead.extract_for_compliance() output
        and returns one compliance record per rule.

        Args:
            extraction_results: list[dict] from Module 2

        Returns:
            list[dict] with status, counts, and per-element failures
        """
        return [self._evaluate_rule(item) for item in extraction_results]

    def check_naming_conventions(self, elements: list, patterns: list[str]) -> list[dict]:
        """Check element names against regex naming patterns."""
        issues = []
        for el in elements:
            name = el.get("name", "")
            for pattern in patterns:
                try:
                    if not re.fullmatch(pattern, name):
                        issues.append({"guid": el.get("guid"), "name": name,
                                       "pattern": pattern, "status": "FAIL"})
                except re.error:
                    pass
        return issues

    def check_spatial_clearances(self, extraction_results: list[dict]) -> list[dict]:
        """Evaluate spatial clearance rules — delegates to validate_metadata."""
        clearance = [r for r in extraction_results if r.get("operator") == "between"]
        return self.validate_metadata(clearance)

    # ── Private ───────────────────────────────────────────────────────────────

    def _evaluate_rule(self, item: dict) -> dict:
        operator  = item.get("operator", "")
        check_val = item.get("check_value")
        val_min   = item.get("value_min")
        val_max   = item.get("value_max")
        unit      = item.get("unit", "")
        elements  = item.get("elements", [])

        # unique_within_scope compares elements to EACH OTHER (grouped by
        # location), not to a fixed threshold — it can't share the per-element
        # loop below, which only ever looks at one element at a time.
        if operator == "unique_within_scope":
            return self._evaluate_uniqueness_rule(item)

        if not elements:
            return self._result(item, "NO_ELEMENTS", 0, 0, 0, 0, [], [], [])

        pass_count = fail_count = missing_count = 0
        failures: list[dict] = []
        missing_elements: list[dict] = []
        all_elements: list[dict] = []
        name_pattern = str(item.get("name_pattern") or "")
        compare_property = str(item.get("compare_property") or "")
        property_name = str(item.get("property_name") or "")

        for el in elements:
            actual = el.get("actual_value")

            if operator in ("exists", "not_exists"):
                present = actual is not None
                wanted  = operator == "exists"
                if present == wanted:
                    pass_count += 1
                    all_elements.append(self._entry(el, actual, "PASS", ""))
                else:
                    reason = "property missing" if wanted else "property should not exist"
                    fail_count += 1
                    failures.append(self._failure(el, actual, reason))
                    all_elements.append(self._entry(el, actual, "FAIL", reason))
                continue

            if operator == "field_consistency":
                # Compare prop_name's value (optionally transformed by
                # name_pattern, e.g. extracting "CVO14" out of the longer
                # Name "CVO_90cm_FSR_TES_14") against compare_property's own
                # value, both fetched from this SAME element by Module 2.
                compare_val = el.get("resolved_compare_value")
                derived = (
                    self._apply_name_pattern(actual, name_pattern)
                    if actual is not None
                    else None
                )
                if derived is None or compare_val is None:
                    missing_count += 1
                    which = property_name if derived is None else compare_property
                    missing_elements.append({
                        "element_name": el.get("name", ""),
                        "guid": el.get("guid", ""),
                        "storey": el.get("storey") or "—",
                        "space": el.get("space") or "—",
                    })
                    all_elements.append(
                        self._entry(el, actual, "MISSING", f"{which} not found")
                    )
                    continue
                ok = str(derived).strip().casefold() == str(compare_val).strip().casefold()
                reason = (
                    "" if ok else
                    f'{property_name}="{derived}" does not match '
                    f'{compare_property}="{compare_val}"'
                )
                if ok:
                    pass_count += 1
                    all_elements.append(self._entry(el, actual, "PASS", ""))
                else:
                    fail_count += 1
                    failures.append(self._failure(el, actual, reason))
                    all_elements.append(self._entry(el, actual, "FAIL", reason))
                continue

            if actual is None:
                missing_count += 1
                missing_elements.append({
                    "element_name": el.get("name", ""),
                    "guid": el.get("guid", ""),
                    "storey": el.get("storey") or "—",
                    "space": el.get("space") or "—",
                })
                all_elements.append(self._entry(el, actual, "MISSING", "property not found"))
                continue

            # Property-referencing bounds (value_min_property / value_max_property)
            # are resolved per-element by Module 2 since each element can have a
            # different reference value (e.g. each stair flight's own Run).
            # Fall back to the rule-level numeric bound when no per-element
            # bound was resolved (either the rule uses a fixed value, or the
            # referenced property wasn't found on this element).
            el_val_min = el.get("resolved_value_min")
            el_val_min = el_val_min if el_val_min is not None else val_min
            el_val_max = el.get("resolved_value_max")
            el_val_max = el_val_max if el_val_max is not None else val_max

            passed, reason = self._compare(operator, actual, check_val, el_val_min, el_val_max, unit)
            if passed:
                pass_count += 1
                all_elements.append(self._entry(el, actual, "PASS", ""))
            else:
                fail_count += 1
                failures.append(self._failure(el, actual, reason))
                all_elements.append(self._entry(el, actual, "FAIL", reason))

        if fail_count > 0:
            status = "FAIL"
        elif missing_count > 0 and pass_count == 0:
            status = "MISSING_DATA"
        elif missing_count > 0:
            status = "PARTIAL"
        else:
            status = "PASS"

        return self._result(item, status, pass_count, fail_count,
                            missing_count, len(elements), failures, missing_elements,
                            all_elements)

    @staticmethod
    def _apply_name_pattern(value, pattern: str):
        """Derive the comparable string from `value` for field_consistency.

        No pattern -> compare the raw value as-is. With a pattern -> run
        re.search and join whatever capture groups matched (or the whole
        match when the pattern has no groups). Lets a rule pull just the
        code out of a longer Name (e.g. the trailing "14" and prefix "CVO"
        out of "CVO_90cm_FSR_TES_14") before comparing it to a separate
        stored ID field. Returns None when the pattern doesn't match at all,
        which the caller treats as MISSING rather than a false FAIL.
        """
        text = str(value)
        if not pattern:
            return text
        try:
            m = re.search(pattern, text)
        except re.error:
            return None
        if not m:
            return None
        groups = [g for g in m.groups() if g is not None]
        return "".join(groups) if groups else m.group(0)

    def _evaluate_uniqueness_rule(self, item: dict) -> dict:
        """unique_within_scope: flag elements that share a property value
        with another element in the same scope (storey / space / whole
        model) — e.g. two doors on the same floor both coded "1", which
        breaks a downstream O&M database that keys off that code to
        identify one specific object. Unlike every other operator this
        compares elements to EACH OTHER, so it can't reuse the per-element
        loop in _evaluate_rule, which only ever sees one element at a time
        against a fixed threshold.
        """
        elements = item.get("elements", [])
        scope = str(item.get("uniqueness_scope") or "building").strip().lower()

        if not elements:
            return self._result(item, "NO_ELEMENTS", 0, 0, 0, 0, [], [], [])

        def _scope_key(el):
            if scope == "storey":
                return (el.get("storey") or "—",)
            if scope == "space":
                return (el.get("storey") or "—", el.get("space") or "—")
            return ("__building__",)

        buckets: dict[tuple, list[dict]] = {}
        missing_els: list[dict] = []
        for el in elements:
            actual = el.get("actual_value")
            if actual is None:
                missing_els.append(el)
                continue
            key = (_scope_key(el), str(actual).strip().casefold())
            buckets.setdefault(key, []).append(el)

        pass_count = fail_count = 0
        failures: list[dict] = []
        missing_elements: list[dict] = []
        all_elements: list[dict] = []

        for el in missing_els:
            missing_elements.append({
                "element_name": el.get("name", ""),
                "guid": el.get("guid", ""),
                "storey": el.get("storey") or "—",
                "space": el.get("space") or "—",
            })
            all_elements.append(self._entry(el, None, "MISSING", "property not found"))

        scope_label = {"storey": "storey", "space": "storey+space", "building": "model"}.get(
            scope, scope
        )
        for group in buckets.values():
            if len(group) > 1:
                others = len(group) - 1
                for el in group:
                    actual = el.get("actual_value")
                    reason = (
                        f'"{actual}" is shared by {others} other element(s) in the '
                        f"same {scope_label} — values must be unique within scope"
                    )
                    fail_count += 1
                    failures.append(self._failure(el, actual, reason))
                    all_elements.append(self._entry(el, actual, "FAIL", reason))
            else:
                el = group[0]
                actual = el.get("actual_value")
                pass_count += 1
                all_elements.append(self._entry(el, actual, "PASS", ""))

        missing_count = len(missing_els)
        if fail_count > 0:
            status = "FAIL"
        elif missing_count > 0 and pass_count == 0:
            status = "MISSING_DATA"
        elif missing_count > 0:
            status = "PARTIAL"
        else:
            status = "PASS"

        return self._result(item, status, pass_count, fail_count,
                            missing_count, len(elements), failures, missing_elements,
                            all_elements)

    def _compare(self, operator, actual, check_val, val_min, val_max, unit):
        # Boolean-aware ==/!= — ifcopenshell returns real Python bool for any
        # IfcBoolean property, but rule check_values are usually authored as
        # text ("TRUE"/"FALSE", any case) straight from spec wording. A literal
        # string match ("True" == "TRUE") fails despite meaning the same thing,
        # so compare as booleans whenever both sides normalize to one — this
        # covers every boolean property/rule, not just one specific case.
        if isinstance(actual, bool) and operator in ("==", "!="):
            check_bool = (
                check_val if isinstance(check_val, bool)
                else _BOOL_ALIASES.get(str(check_val).strip().lower()) if check_val is not None
                else None
            )
            if check_bool is not None:
                ok = (actual == check_bool) if operator == "==" else (actual != check_bool)
                return ok, ("" if ok else f"{actual} fails {operator} {check_val}")

        try:
            a = float(str(actual).replace(",", "").strip())
        except (ValueError, TypeError):
            if operator == "==":
                ok = str(actual) == str(check_val)
            elif operator == "!=":
                ok = str(actual) != str(check_val)
            elif operator == "matches" and check_val:
                try:
                    ok = bool(re.search(str(check_val), str(actual)))
                except re.error:
                    ok = False
            else:
                ok = False
            return ok, ("" if ok else f'"{actual}" fails {operator} "{check_val}"')

        u = f" {unit}" if unit else ""
        try:
            if operator == ">=":
                ok, reason = check_val is not None and a >= check_val, \
                             f"{a}{u} < required {check_val}{u}"
            elif operator == "<=":
                ok, reason = check_val is not None and a <= check_val, \
                             f"{a}{u} > maximum {check_val}{u}"
            elif operator == ">":
                ok, reason = check_val is not None and a > check_val, \
                             f"{a}{u} <= required {check_val}{u}"
            elif operator == "<":
                ok, reason = check_val is not None and a < check_val, \
                             f"{a}{u} >= maximum {check_val}{u}"
            elif operator == "==":
                ok, reason = check_val is not None and a == check_val, \
                             f"{a}{u} != {check_val}{u}"
            elif operator == "!=":
                ok, reason = check_val is not None and a != check_val, \
                             f"{a}{u} equals excluded value {check_val}{u}"
            elif operator == "between":
                ok = val_min is not None and val_max is not None and val_min <= a <= val_max
                reason = f"{a}{u} outside [{val_min}{u} - {val_max}{u}]"
            else:
                ok, reason = True, ""
        except TypeError:
            # check_val/val_min/val_max is a non-numeric string against a
            # numeric actual (e.g. a malformed rule) — ordering operators
            # can't compare mixed types; fail cleanly instead of crashing
            # the whole compliance run.
            ok, reason = False, f"{a}{u} cannot be compared to non-numeric threshold {check_val!r}"

        return ok, ("" if ok else reason)

    @staticmethod
    def _failure(el, actual, reason) -> dict:
        return {
            "element_name": el.get("name"),
            "guid": el.get("guid"),
            "storey": el.get("storey") or "—",
            "space": el.get("space") or "—",
            "actual": actual,
            "reason": reason,
            # (x, y, z) mm from Module 2, or None — consumed by Module 5's
            # BCF export to aim the viewpoint camera at the failing element.
            "position_mm": el.get("position_mm"),
        }

    @staticmethod
    def _entry(el, actual, status, reason) -> dict:
        """Per-element record kept for every evaluated element (pass, fail, or missing)."""
        return {
            "element_name": el.get("name"),
            "guid": el.get("guid"),
            "storey": el.get("storey") or "—",
            "space": el.get("space") or "—",
            "actual": actual,
            "status": status,
            "reason": reason,
            # (x, y, z) mm from Module 2, or None — carried through so any
            # per-element view built from all_elements (not just failures)
            # can still offer a "View in 3D" link.
            "position_mm": el.get("position_mm"),
        }

    @staticmethod
    def _result(item, status, pass_count, fail_count, missing_count, total, failures,
                missing_elements=None, all_elements=None) -> dict:
        return {
            "rule_id":         item.get("rule_id"),
            "rule_ref":        item.get("rule_ref", ""),
            "rule_desc":       item.get("rule_desc", ""),
            "target":          item.get("target_ifc_class", ""),
            "property_name":   item.get("property_name", ""),
            "property_set":    item.get("property_set", ""),
            "egress_direction": item.get("egress_direction", "outside"),
            "operator":        item.get("operator", ""),
            "check_value":     item.get("check_value"),
            "value_min":       item.get("value_min"),
            "value_max":       item.get("value_max"),
            "unit":            item.get("unit", ""),
            "severity":        item.get("severity", "mandatory"),
            "status":          status,
            "pass_count":      pass_count,
            "fail_count":      fail_count,
            "missing_count":   missing_count,
            "total_count":     total,
            "failures":        failures,
            "missing_elements": missing_elements or [],
            "all_elements":    all_elements or [],
        }
