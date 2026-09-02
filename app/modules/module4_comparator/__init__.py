"""
module4_comparator.py
----------------------
Compares IFC property values extracted by Module 2 against the rule library.

For each rule:
  - Applies operator + threshold(s) to every matching element
  - Returns PASS / FAIL / MISSING_DATA / PARTIAL / NO_ELEMENTS per rule
  - Collects per-element failure details for Module 5 reporting

Operators: >= <= > < == != between exists not_exists matches documented
           field_consistency unique_within_scope

`exists`/`not_exists` treat a missing property as FAIL — use them for fields
that must always be authored (e.g. GlobalId). `documented` is for fields that
are frequently left blank by authoring tools and aren't being checked against
a real threshold here: a present value (of any kind) is PASS, and a missing
one flows through the normal actual-is-None path below as MISSING_DATA/
PARTIAL rather than an asserted FAIL.
"""

import re

# Case-insensitive string forms a rule's check_value might use for a boolean
# IFC property (IsExternal, SelfClosing, SmokeStop, HandicapAccessible, …).
_BOOL_ALIASES = {"true": True, "false": False, "yes": True, "no": False}

# ── Scope and waiver predicates ───────────────────────────────────────────────
# A rule may carry `applies_when` (narrowing which elements it governs) and
# `exceptions` (conditions that waive a failure). Both are dicts of predicate
# key -> expected value, evaluated per element against the element record
# Module 2 built.
#
# Every predicate resolves to one of three outcomes, and the third is the
# reason this is not a plain boolean: a predicate whose data Module 2 does not
# supply is UNDETERMINED, not False. The two gates then fail in opposite
# directions, both toward reporting rather than silence:
#
#   scope  — UNDETERMINED keeps the element IN scope, so an unevaluable
#            narrowing can never silently suppress a check.
#   waiver — UNDETERMINED does NOT waive, so an unevaluable exemption can
#            never silently suppress a finding.
#
# Anything undetermined is counted and surfaced on the result rather than
# discarded, so a ruleset that depends on data the extractor cannot yet
# provide is visible instead of quietly inert.
MATCH = "MATCH"
NO_MATCH = "NO_MATCH"
UNDETERMINED = "UNDETERMINED"

#: Predicate key -> IFC property whose per-element value Module 2 resolves into
#: `scope_values`. Keys carry their unit so a rule reads as the standard writes
#: it; the value is compared in that unit.
_SCOPE_NUMERIC_PROPERTIES = {
    "nominal_diameter_mm": "NominalDiameter",
    "nominal_diameter_below_mm": "NominalDiameter",
    # Support-derived, resolved by module2_ifc_read.ifc_supports into
    # `scope_values` alongside the Pset-derived ones, so they need no separate
    # machinery here. HangerRodLength is the LONGEST rod on the run: an
    # exemption for "rods shorter than 150 mm" is only earned when every rod
    # clears it.
    "hanger_rod_length_below_mm": "HangerRodLength",
    "hanger_rod_length_mm": "HangerRodLength",
    "lateral_brace_spacing_mm": "LateralBraceSpacing",
    "longitudinal_brace_spacing_mm": "LongitudinalBraceSpacing",
}

#: Predicate keys matched against a list-valued field of the element record.
#: Matching is case-insensitive and accepts a substring, so "IfcWall" in a
#: `penetrates` list also matches a host typed IfcWallStandardCase, and
#: "gypsum" matches a material named "5/8in Type X Gypsum Board".
_SCOPE_LIST_FIELDS = {
    "element_type_any_of": "element_type",
    "storey_any_of": "storey",
    "space_any_of": "space",
    "material_any_of": "materials",
    # Host predicates. `host_*` describes what the element passes THROUGH, as
    # resolved by module2_ifc_read.ifc_penetrations, and is a different
    # question from `material_any_of`, which is the element's own material.
    # Confusing the two is how a steel pipe in a gypsum wall looks like a
    # gypsum pipe.
    "penetrates": "host_classes",
    "host_class_any_of": "host_classes",
    "host_material_any_of": "host_materials",
    "host_name_any_of": "host_names",
}

#: Predicate keys matched against a tri-state boolean field of the element
#: record. None means the model did not say, which is UNDETERMINED -- never
#: False. Treating "unknown" as "not breakaway" would be safe here by luck,
#: but the same shortcut on an inverted predicate would waive silently.
_SCOPE_BOOL_FIELDS = {
    "host_is_breakaway": "host_is_breakaway",
    # True when at least one of the supports found is a hanger. None -- and so
    # UNDETERMINED -- when no supports were found at all, since an exporter
    # that writes no relationships looks exactly like a genuinely unsupported
    # run.
    "is_suspended": "is_suspended",
}

#: Predicate keys that are structurally meaningful but carry no per-element
#: test: the extraction already guarantees them, so they are satisfied by
#: construction rather than evaluated.
_SCOPE_TRIVIAL_KEYS = {"target_ifc_class"}

#: Predicate keys that annotate the rule rather than test the element -- prose
#: recording how a measurement is defined, not a condition to evaluate. They
#: are neutral: they neither narrow scope nor grant a waiver, and reporting
#: them as "unsupported by the extractor" would be misleading, since they were
#: never a predicate to support.
_SCOPE_ANNOTATION_KEYS = {"measured_from", "note", "notes", "source", "citation"}

#: Operators marking a rule as a waiver definition rather than a requirement.
#: Mirrors ``module2_ifc_read._WAIVER_ONLY_OPERATORS``; Module 2 skips
#: extracting them, this side skips evaluating whatever still arrives.
_WAIVER_ONLY_OPERATORS = {"exempt", "exemption", "waiver"}


class Module4_Comparator:
    """Validates IFC model data against the BIMGuard rule library."""

    # ── Public API ────────────────────────────────────────────────────────────

    def validate_metadata(self, extraction_results: list[dict]) -> list[dict]:
        """
        Main entry point. Takes Module2_IFCRead.extract_for_compliance() output
        and returns one compliance record per rule.

        Waiver definitions are dropped rather than evaluated. A rule whose
        operator marks it a waiver states the condition under which some other
        rule is excused; standing alone it asserts nothing about the model, so
        there is no verdict to return and any status it were given would be
        read as one. Module 2 already declines to extract them, so this is the
        second of two gates -- it catches extraction produced elsewhere, such
        as a fixture or a cached run predating the skip.

        Args:
            extraction_results: list[dict] from Module 2

        Returns:
            list[dict] with status, counts, and per-element failures
        """
        return [
            self._evaluate_rule(item)
            for item in extraction_results
            if not self._is_waiver_only(item.get("operator"))
        ]

    @staticmethod
    def _is_waiver_only(operator) -> bool:
        """Return True when a rule defines a waiver, not a requirement."""
        return str(operator or "").strip().lower() in _WAIVER_ONLY_OPERATORS

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

        # Scope narrowing and waivers. A rule carrying neither -- which is
        # every rule seeded before BIMGUARD-PC-001 -- takes the original path
        # untouched: `scope` stays empty, `_evaluate_predicate` returns MATCH
        # for it without inspecting the element, and no waiver is consulted
        # because failures only look at `exceptions` when it is non-empty.
        scope = item.get("applies_when") or {}
        exceptions = item.get("exceptions") or []

        not_applicable_count = waived_count = 0
        undetermined_notes: list[str] = []
        waivers: list[dict] = []

        pass_count = fail_count = missing_count = 0
        failures: list[dict] = []
        missing_elements: list[dict] = []
        all_elements: list[dict] = []
        name_pattern = str(item.get("name_pattern") or "")
        compare_property = str(item.get("compare_property") or "")
        property_name = str(item.get("property_name") or "")

        for el in elements:
            actual = el.get("actual_value")

            # Scope gate. Runs before the operator so an out-of-scope element
            # is never measured against a threshold that does not govern it.
            if scope:
                outcome, details = self._evaluate_predicate(scope, el)
                if outcome == NO_MATCH:
                    not_applicable_count += 1
                    all_elements.append(
                        self._entry(el, actual, "NOT_APPLICABLE", "outside rule scope")
                    )
                    continue
                if outcome == UNDETERMINED:
                    # Kept in scope deliberately: an unevaluable narrowing must
                    # not suppress the check.
                    undetermined_notes.extend(details)

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
                # Waiver gate. Only a failing element is worth testing against
                # the exemptions, and only this comparison path carries them
                # today -- the exists/not_exists and field_consistency paths
                # above are reached only by rules with no `exceptions`, so
                # routing them through the same gate would be dead code.
                waiver, notes = self._waiver_for(exceptions, el)
                undetermined_notes.extend(notes)
                if waiver is not None:
                    ref = waiver.get("reference") or "exemption"
                    label = waiver.get("label") or ref
                    waived_count += 1
                    waivers.append(
                        {
                            "element_name": el.get("name"),
                            "guid": el.get("guid"),
                            "exemption_ref": ref,
                            "exemption_label": label,
                            "waived_reason": reason,
                        }
                    )
                    all_elements.append(
                        self._entry(el, actual, "WAIVED", f"{reason} — waived by {ref} ({label})")
                    )
                else:
                    fail_count += 1
                    failures.append(self._failure(el, actual, reason))
                    all_elements.append(self._entry(el, actual, "FAIL", reason))

        # Status roll-up. The first four branches are the original ladder,
        # still reached first and in the same order, so a rule carrying
        # neither scope nor waivers resolves exactly as it did before. The two
        # new terminal states are reachable only once every element has been
        # gated away.
        if fail_count > 0:
            status = "FAIL"
        elif missing_count > 0 and pass_count == 0:
            status = "MISSING_DATA"
        elif missing_count > 0:
            status = "PARTIAL"
        elif pass_count > 0:
            status = "PASS"
        elif waived_count > 0:
            # Every failure was waived and nothing passed: a real outcome,
            # distinct from PASS, that a reviewer must be able to see.
            status = "WAIVED"
        elif not_applicable_count > 0:
            status = "NOT_APPLICABLE"
        else:
            status = "PASS"

        result = self._result(item, status, pass_count, fail_count,
                              missing_count, len(elements), failures, missing_elements,
                              all_elements)
        result["not_applicable_count"] = not_applicable_count
        result["waived_count"] = waived_count
        result["waivers"] = waivers
        # Deduplicated so one unsupported predicate is reported once, not once
        # per element.
        result["undetermined_predicates"] = sorted(set(undetermined_notes))
        return result

    # ── Scope / waiver predicate evaluation ───────────────────────────────────

    @staticmethod
    def _predicate_key(key: str, expected, el: dict) -> tuple[str, str]:
        """Evaluate one predicate key against one element.

        Returns (outcome, detail) where outcome is MATCH, NO_MATCH or
        UNDETERMINED and detail names the reason when it is not a clean match.
        """
        if key in _SCOPE_TRIVIAL_KEYS or key in _SCOPE_ANNOTATION_KEYS:
            return MATCH, ""

        if key in _SCOPE_BOOL_FIELDS:
            actual = el.get(_SCOPE_BOOL_FIELDS[key])
            if actual is None:
                return UNDETERMINED, f"{key} not resolved on element"
            return (MATCH if bool(actual) == bool(expected) else NO_MATCH), ""

        scope_values = el.get("scope_values") or {}

        if key in _SCOPE_NUMERIC_PROPERTIES:
            prop = _SCOPE_NUMERIC_PROPERTIES[key]
            raw = scope_values.get(prop)
            if raw is None:
                return UNDETERMINED, f"{prop} not resolved on element"
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return UNDETERMINED, f"{prop}={raw!r} is not numeric"

            # "<key>_below_mm": a bare numeric ceiling, exclusive.
            if key.endswith("_below_mm"):
                try:
                    limit = float(expected)
                except (TypeError, ValueError):
                    return UNDETERMINED, f"{key} bound {expected!r} is not numeric"
                return (MATCH if value < limit else NO_MATCH), ""

            # A bare number is a single nominated size -- "NB50", "DN65" --
            # rather than a band. Standards tabulate rules that way (NZS 4219
            # Table 6a is per nominal bore), so the scalar form is read as the
            # degenerate band {min: v, max: v}.
            #
            # That is an EXACT match on a float, and deliberately so: widening
            # it by some tolerance would silently pull neighbouring sizes into
            # a rule written for one. The cost is that a model authoring the
            # true outside diameter (50.8 for NB50) will not match a rule
            # written against the nominal designation (50.0); such a rule
            # states NO_MATCH, not a wrong verdict, and the mismatch belongs in
            # rule review rather than in a fudge factor here.
            if isinstance(expected, (int, float)) and not isinstance(expected, bool):
                expected = {"min": expected, "max": expected}
            elif not isinstance(expected, dict):
                return UNDETERMINED, f"{key} expects a number or a min/max object"
            low = expected.get("min")
            high = expected.get("max")
            try:
                if low is not None and value < float(low):
                    return NO_MATCH, ""
                if high is not None and value > float(high):
                    return NO_MATCH, ""
            except (TypeError, ValueError):
                return UNDETERMINED, f"{key} bounds are not numeric"
            return MATCH, ""

        if key in _SCOPE_LIST_FIELDS:
            field = _SCOPE_LIST_FIELDS[key]
            actual = el.get(field)
            if actual is None:
                return UNDETERMINED, f"{field} not resolved on element"
            haystack = actual if isinstance(actual, list) else [actual]
            wanted = expected if isinstance(expected, list) else [expected]
            wanted_cf = {str(w).strip().casefold() for w in wanted}
            for candidate in haystack:
                text = str(candidate).strip().casefold()
                if text in wanted_cf or any(w in text for w in wanted_cf):
                    return MATCH, ""
            return NO_MATCH, ""

        # An unrecognised key is data the extractor does not supply -- a
        # relational predicate such as the host element's material or the
        # proximity of a flexible coupling. Undetermined, never assumed.
        return UNDETERMINED, f"predicate {key!r} is not supported by the extractor"

    @classmethod
    def _evaluate_predicate(cls, predicate: dict, el: dict) -> tuple[str, list[str]]:
        """Evaluate a whole predicate dict (AND across its keys) for one element.

        NO_MATCH on any key settles the predicate immediately. Otherwise an
        undetermined key leaves the whole predicate undetermined, because a
        condition that cannot be tested cannot be asserted.
        """
        if not predicate:
            return MATCH, []
        undetermined: list[str] = []
        for key, expected in predicate.items():
            outcome, detail = cls._predicate_key(key, expected, el)
            if outcome == NO_MATCH:
                return NO_MATCH, []
            if outcome == UNDETERMINED:
                undetermined.append(detail)
        if undetermined:
            return UNDETERMINED, undetermined
        return MATCH, []

    @staticmethod
    def _testable_keys(predicate: dict) -> set:
        """Return the predicate keys that actually test the element.

        Annotation and trivially-true keys are excluded: both always match, so
        a predicate consisting only of them asserts nothing.
        """
        return set(predicate or {}) - _SCOPE_ANNOTATION_KEYS - _SCOPE_TRIVIAL_KEYS

    @classmethod
    def _waiver_for(cls, exceptions: list[dict], el: dict) -> tuple[dict | None, list[str]]:
        """Return the first exception waiving this element, plus undetermined notes.

        Exceptions arrive already resolved by Module 2 from the references on
        the rule, each carrying its own predicate.
        """
        notes: list[str] = []
        for exception in exceptions or []:
            ref = exception.get("reference") or "exception"
            predicate = exception.get("predicate") or {}
            # An empty predicate is the asymmetry between the two gates. For
            # scope, "no condition" means the rule governs everything; for a
            # waiver it would mean "waives everything", which is how an
            # exemption reference that resolved to nothing would silently
            # erase real findings. An exemption must state a condition to
            # suppress anything.
            #
            # "Empty" means empty of anything TESTABLE, not merely of keys. An
            # annotation ("measured_from: each face...") and a key the
            # extraction already guarantees ("target_ifc_class") both evaluate
            # to MATCH for every element by design, so a predicate made only
            # of them would waive the entire model while looking like a
            # considered condition.
            if not cls._testable_keys(predicate):
                notes.append(f"{ref}: no testable predicate, cannot waive")
                continue
            outcome, details = cls._evaluate_predicate(predicate, el)
            if outcome == MATCH:
                return exception, notes
            if outcome == UNDETERMINED:
                notes.extend(f"{ref}: {d}" for d in details)
        return None, notes

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
        # `_compare` only runs once the caller has already confirmed
        # `actual is not None` (the None case is MISSING_DATA territory,
        # handled before this is called) — so any value reaching here for a
        # "documented" rule already satisfies the check, whatever its type.
        if operator == "documented":
            return True, ""

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
