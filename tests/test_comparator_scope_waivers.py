"""Scope gating and waiver gating in ComplianceComparator.

Covers the two gates added for BIMGUARD-PC-001 (NFPA 13 Sec. 18.5 clearance):
``applies_when`` narrows which elements a rule governs, and ``exceptions``
waive a failure when an exemption predicate matches.

The first test is the important one: every rule seeded before PC-001 carries
neither field, and must evaluate exactly as it did before.
"""

from __future__ import annotations

from app.modules.comparator import ComplianceComparator


def _element(name: str, actual, **extra) -> dict:
    """Build a Module 2 element record."""
    element = {
        "guid": f"guid-{name}",
        "name": name,
        "actual_value": actual,
        "found": actual is not None,
        "storey": "L01",
        "space": "Plant Room",
        "materials": [],
        "scope_values": {},
    }
    element.update(extra)
    return element


def _rule(elements: list[dict], **extra) -> dict:
    """Build a Module 2 per-rule extraction record for the clearance check."""
    item = {
        "rule_ref": "PC-001.01",
        "rule_desc": "Annular clearance 50 mm",
        "target_ifc_class": "IfcPipeSegment",
        "property_name": "AnnularClearance",
        "operator": ">=",
        "check_value": 50.0,
        "unit": "mm",
        "elements": elements,
    }
    item.update(extra)
    return item


def _evaluate(item: dict) -> dict:
    return ComplianceComparator().validate_metadata([item])[0]


class TestBackwardCompatibility:
    """A rule declaring neither gate must behave exactly as before."""

    def test_plain_pass_unchanged(self):
        result = _evaluate(_rule([_element("pipe-a", 80.0)]))
        assert result["status"] == "PASS"
        assert result["pass_count"] == 1
        assert result["fail_count"] == 0

    def test_plain_fail_unchanged(self):
        result = _evaluate(_rule([_element("pipe-a", 10.0)]))
        assert result["status"] == "FAIL"
        assert result["fail_count"] == 1
        assert len(result["failures"]) == 1

    def test_missing_data_unchanged(self):
        result = _evaluate(_rule([_element("pipe-a", None)]))
        assert result["status"] == "MISSING_DATA"
        assert result["missing_count"] == 1

    def test_no_elements_unchanged(self):
        result = _evaluate(_rule([]))
        assert result["status"] == "NO_ELEMENTS"

    def test_new_counters_default_to_zero(self):
        result = _evaluate(_rule([_element("pipe-a", 10.0)]))
        assert result["not_applicable_count"] == 0
        assert result["waived_count"] == 0
        assert result["waivers"] == []
        assert result["undetermined_predicates"] == []


class TestScopeGating:
    """applies_when narrows the rule to the elements it governs."""

    BAND = {"nominal_diameter_mm": {"min": 25.4, "max": 88.9}}

    def test_element_outside_band_is_not_applicable(self):
        # 4" pipe (101.6 mm) is governed by PC-001.02, not this rule, and its
        # 10 mm clearance must not be reported as a failure here.
        pipe = _element("pipe-4in", 10.0, scope_values={"NominalDiameter": 101.6})
        result = _evaluate(_rule([pipe], applies_when=self.BAND))
        assert result["status"] == "NOT_APPLICABLE"
        assert result["not_applicable_count"] == 1
        assert result["fail_count"] == 0
        assert result["all_elements"][0]["status"] == "NOT_APPLICABLE"

    def test_element_inside_band_is_evaluated(self):
        pipe = _element("pipe-2in", 10.0, scope_values={"NominalDiameter": 50.8})
        result = _evaluate(_rule([pipe], applies_when=self.BAND))
        assert result["status"] == "FAIL"
        assert result["fail_count"] == 1

    def test_band_boundaries_are_inclusive(self):
        low = _element("low", 60.0, scope_values={"NominalDiameter": 25.4})
        high = _element("high", 60.0, scope_values={"NominalDiameter": 88.9})
        result = _evaluate(_rule([low, high], applies_when=self.BAND))
        assert result["pass_count"] == 2
        assert result["not_applicable_count"] == 0

    def test_mixed_scope_counts_separately(self):
        inside = _element("in", 10.0, scope_values={"NominalDiameter": 50.8})
        outside = _element("out", 10.0, scope_values={"NominalDiameter": 200.0})
        result = _evaluate(_rule([inside, outside], applies_when=self.BAND))
        assert result["status"] == "FAIL"
        assert result["fail_count"] == 1
        assert result["not_applicable_count"] == 1

    def test_unresolvable_scope_keeps_element_in_scope(self):
        # Diameter unknown: the check must still run. An unevaluable narrowing
        # must never silently suppress a compliance check.
        pipe = _element("pipe-unknown", 10.0, scope_values={})
        result = _evaluate(_rule([pipe], applies_when=self.BAND))
        assert result["status"] == "FAIL"
        assert result["fail_count"] == 1
        assert result["undetermined_predicates"]

    def test_unsupported_predicate_keeps_element_in_scope(self):
        pipe = _element("pipe-a", 10.0)
        scope = {"pipe_colour_any_of": ["red"]}
        result = _evaluate(_rule([pipe], applies_when=scope))
        assert result["status"] == "FAIL"
        assert any("not supported" in n for n in result["undetermined_predicates"])

    def test_flexible_coupling_is_evaluated_not_unsupported(self):
        # ifc_seismic resolves this one now. It is still UNDETERMINED for an
        # element that carries no value -- which is the safe direction -- but
        # for the different and more informative reason that the model did not
        # answer, rather than that nothing could ask.
        pipe = _element("pipe-a", 10.0)
        scope = {"flexible_coupling_within_mm": 300.0}
        result = _evaluate(_rule([pipe], applies_when=scope))
        assert result["status"] == "FAIL"
        notes = result["undetermined_predicates"]
        assert any("FlexibleCouplingWithin" in n for n in notes)
        assert not any("not supported" in n for n in notes)

    def test_flexible_coupling_within_limit_is_in_scope(self):
        # "within 300 mm" is INCLUSIVE, unlike the exclusive "_below_mm"
        # ceilings: a coupling at exactly 300 satisfies the standard's wording.
        at_limit = _element("pipe-at", 10.0, scope_values={"FlexibleCouplingWithin": 300.0})
        beyond = _element("pipe-far", 10.0, scope_values={"FlexibleCouplingWithin": 300.1})
        scope = {"flexible_coupling_within_mm": 300.0}
        result = _evaluate(_rule([at_limit, beyond], applies_when=scope))
        assert result["fail_count"] == 1
        assert result["not_applicable_count"] == 1


class TestWaiverGating:
    """exceptions waive a failure when an exemption predicate matches."""

    GYPSUM = [
        {
            "reference": "PC-001.03",
            "label": "Breakaway or frangible construction",
            "predicate": {"material_any_of": ["gypsum", "plasterboard"]},
        }
    ]

    def test_failure_is_waived_when_predicate_matches(self):
        pipe = _element("pipe-in-gypsum", 10.0, materials=["Gypsum Board"])
        result = _evaluate(_rule([pipe], exceptions=self.GYPSUM))
        assert result["status"] == "WAIVED"
        assert result["waived_count"] == 1
        assert result["fail_count"] == 0
        assert result["waivers"][0]["exemption_ref"] == "PC-001.03"
        assert result["all_elements"][0]["status"] == "WAIVED"

    def test_failure_stands_when_predicate_does_not_match(self):
        pipe = _element("pipe-in-concrete", 10.0, materials=["Concrete"])
        result = _evaluate(_rule([pipe], exceptions=self.GYPSUM))
        assert result["status"] == "FAIL"
        assert result["fail_count"] == 1
        assert result["waived_count"] == 0

    def test_passing_element_is_never_waived(self):
        pipe = _element("pipe-ok", 80.0, materials=["Gypsum Board"])
        result = _evaluate(_rule([pipe], exceptions=self.GYPSUM))
        assert result["status"] == "PASS"
        assert result["waived_count"] == 0

    def test_undetermined_exemption_does_not_waive(self):
        # The unverified flexible-coupling exemption: its data is not
        # extractable, so it must leave the failure standing rather than
        # silently suppress it.
        coupling = [
            {
                "reference": "PC-001.04",
                "label": "Flexible couplings adjacent",
                "predicate": {"flexible_coupling_within_mm": 300.0},
            }
        ]
        pipe = _element("pipe-a", 10.0)
        result = _evaluate(_rule([pipe], exceptions=coupling))
        assert result["status"] == "FAIL"
        assert result["waived_count"] == 0
        assert any("PC-001.04" in n for n in result["undetermined_predicates"])

    def test_unresolved_exemption_reference_does_not_waive(self):
        # An empty predicate must not read as "matches everything".
        unresolved = [{"reference": "PC-001.99", "predicate": {}, "unresolved": True}]
        pipe = _element("pipe-a", 10.0)
        result = _evaluate(_rule([pipe], exceptions=unresolved))
        assert result["status"] == "FAIL"
        assert result["waived_count"] == 0

    def test_partial_waiver_leaves_rule_failing(self):
        waived = _element("in-gypsum", 10.0, materials=["Gypsum Board"])
        failing = _element("in-concrete", 10.0, materials=["Concrete"])
        result = _evaluate(_rule([waived, failing], exceptions=self.GYPSUM))
        assert result["status"] == "FAIL"
        assert result["fail_count"] == 1
        assert result["waived_count"] == 1


class TestGatesCombined:
    """Scope runs before the operator; waivers run only on a failure."""

    def test_out_of_scope_element_never_reaches_the_waiver(self):
        scope = {"nominal_diameter_mm": {"min": 25.4, "max": 88.9}}
        exceptions = [
            {"reference": "PC-001.03", "predicate": {"material_any_of": ["gypsum"]}}
        ]
        pipe = _element(
            "big-pipe-in-gypsum",
            10.0,
            materials=["Gypsum Board"],
            scope_values={"NominalDiameter": 200.0},
        )
        result = _evaluate(_rule([pipe], applies_when=scope, exceptions=exceptions))
        assert result["status"] == "NOT_APPLICABLE"
        assert result["waived_count"] == 0
        assert result["not_applicable_count"] == 1


class TestHostPredicates:
    """`penetrates`, `host_material_any_of` and `host_is_breakaway`.

    These describe what the element passes THROUGH, resolved by
    ifc_reader.ifc_penetrations, and are a different question from
    `material_any_of`, which is the element's own material.
    """

    SCOPE = {"penetrates": ["IfcWall", "IfcSlab"]}

    def test_penetrating_a_listed_class_is_in_scope(self):
        pipe = _element("pipe-a", 10.0, host_classes=["IfcWall"])
        result = _evaluate(_rule([pipe], applies_when=self.SCOPE))
        assert result["status"] == "FAIL"

    def test_ifc_subtype_matches_its_supertype(self):
        # IfcWallStandardCase is what most exporters actually write.
        pipe = _element("pipe-a", 10.0, host_classes=["IfcWallStandardCase"])
        result = _evaluate(_rule([pipe], applies_when=self.SCOPE))
        assert result["status"] == "FAIL"

    def test_penetrating_an_unlisted_class_is_not_applicable(self):
        pipe = _element("pipe-a", 10.0, host_classes=["IfcBeam"])
        result = _evaluate(_rule([pipe], applies_when=self.SCOPE))
        assert result["status"] == "NOT_APPLICABLE"

    def test_unresolved_host_keeps_the_element_in_scope(self):
        # An exporter that omits IfcRelVoidsElement must not put every pipe in
        # the model quietly out of scope.
        pipe = _element("pipe-a", 10.0, host_classes=None)
        result = _evaluate(_rule([pipe], applies_when=self.SCOPE))
        assert result["status"] == "FAIL"
        assert result["undetermined_predicates"]

    def test_host_material_waives_independently_of_element_material(self):
        # The steel pipe is not gypsum; its host wall is. Keying on the wrong
        # one is how a steel pipe in a gypsum wall looks like a gypsum pipe.
        exceptions = [
            {
                "reference": "PC-001.03",
                "predicate": {"host_material_any_of": ["gypsum"], "host_is_breakaway": True},
            }
        ]
        pipe = _element(
            "pipe-a", 10.0,
            materials=["Carbon Steel"],
            host_materials=["Gypsum Board"],
            host_is_breakaway=True,
        )
        result = _evaluate(_rule([pipe], exceptions=exceptions))
        assert result["status"] == "WAIVED"

    def test_rigid_host_does_not_waive(self):
        exceptions = [
            {"reference": "PC-001.03", "predicate": {"host_is_breakaway": True}}
        ]
        pipe = _element("pipe-a", 10.0, host_is_breakaway=False)
        result = _evaluate(_rule([pipe], exceptions=exceptions))
        assert result["status"] == "FAIL"
        assert result["waived_count"] == 0

    def test_unknown_host_does_not_waive(self):
        exceptions = [
            {"reference": "PC-001.03", "predicate": {"host_is_breakaway": True}}
        ]
        pipe = _element("pipe-a", 10.0, host_is_breakaway=None)
        result = _evaluate(_rule([pipe], exceptions=exceptions))
        assert result["status"] == "FAIL"
        assert any("host_is_breakaway" in n for n in result["undetermined_predicates"])

    def test_false_predicate_is_honoured_not_treated_as_absent(self):
        # A predicate asking for host_is_breakaway=False must match a rigid
        # host, not be skipped because the expected value is falsy.
        exceptions = [
            {"reference": "X", "predicate": {"host_is_breakaway": False}}
        ]
        pipe = _element("pipe-a", 10.0, host_is_breakaway=False)
        result = _evaluate(_rule([pipe], exceptions=exceptions))
        assert result["status"] == "WAIVED"


class TestAnnotationKeys:
    """Prose keys annotate a rule; they neither narrow scope nor waive."""

    def test_annotation_key_does_not_narrow_scope(self):
        scope = {"measured_from": "each face of the penetrated element"}
        result = _evaluate(_rule([_element("pipe-a", 10.0)], applies_when=scope))
        assert result["status"] == "FAIL"
        assert result["undetermined_predicates"] == []

    def test_annotation_alone_cannot_waive(self):
        # An exemption whose only key is prose states no condition, so it must
        # not waive everything it is attached to. Annotation keys match every
        # element by design, which is exactly why a predicate made only of
        # them has to be rejected before it is evaluated.
        exceptions = [{"reference": "X", "predicate": {"measured_from": "anywhere"}}]
        result = _evaluate(_rule([_element("pipe-a", 10.0)], exceptions=exceptions))
        assert result["status"] == "FAIL"
        assert result["waived_count"] == 0
        assert any("no testable predicate" in n for n in result["undetermined_predicates"])

    def test_trivially_true_key_alone_cannot_waive(self):
        # target_ifc_class is guaranteed by the extraction, so an exemption
        # stating only it would waive the entire model.
        exceptions = [
            {"reference": "X", "predicate": {"target_ifc_class": "IfcPipeSegment"}}
        ]
        result = _evaluate(_rule([_element("pipe-a", 10.0)], exceptions=exceptions))
        assert result["status"] == "FAIL"
        assert result["waived_count"] == 0

    def test_annotation_alongside_a_real_condition_still_waives(self):
        # The annotation must not block a predicate that does test something.
        exceptions = [
            {
                "reference": "X",
                "predicate": {
                    "measured_from": "each face",
                    "host_is_breakaway": True,
                },
            }
        ]
        pipe = _element("pipe-a", 10.0, host_is_breakaway=True)
        result = _evaluate(_rule([pipe], exceptions=exceptions))
        assert result["status"] == "WAIVED"


class TestWaiverDefinitionsAreNotEvaluated:
    """A rule defining a waiver has no verdict of its own."""

    def test_exempt_operator_is_dropped(self):
        exemption = _rule([_element("pipe-a", 10.0)], operator="exempt", check_value=None)
        exemption["rule_ref"] = "PC-001.03"
        assert ComplianceComparator().validate_metadata([exemption]) == []

    def test_requirement_alongside_exemption_still_evaluates(self):
        requirement = _rule([_element("pipe-a", 10.0)])
        exemption = _rule([_element("pipe-a", 10.0)], operator="exempt", check_value=None)
        results = ComplianceComparator().validate_metadata([requirement, exemption])
        assert len(results) == 1
        assert results[0]["status"] == "FAIL"


class TestNzs4219_513RetiredProxyScope:
    """NZS-4219-5.13 after scripts/patch_nzs4219_513_scope.py --retire-proxy.

    The clause's own gate is `mass_kg >= 10`. While that was unresolvable the
    rule carried a nominal-bore band as an enforceable stand-in, and leaned on
    the asymmetry between NO_MATCH and UNDETERMINED: the diameter settled the
    scope when it failed, and the inert mass key never suppressed a check on
    its own.

    ifc_seismic resolves mass now, so the stand-in has been removed. Keeping
    it would have inverted its purpose -- the predicate keys are ANDed, so a
    heavy small-bore run would have been dropped from the rule by the very key
    that was added to make the rule enforceable. See
    `test_heavy_small_bore_run_is_no_longer_dropped` below, which is the
    regression this retirement exists to prevent.
    """

    #: Mirrors RETIRED_APPLIES_WHEN in scripts/patch_nzs4219_513_scope.py.
    SCOPE = {
        "target_ifc_class": "IfcPipeSegment",
        "location": "ceiling_void",
        "mass_kg": {"min": 10.0},
    }

    def _pipe(self, name, actual, mass=None, diameter=None):
        scope_values = {}
        if mass is not None:
            scope_values["MassKg"] = mass
        if diameter is not None:
            scope_values["NominalDiameter"] = diameter
        return _element(name, actual, scope_values=scope_values)

    def test_below_the_mass_threshold_is_out_of_scope(self):
        # The clause's own gate now does the narrowing a proxy used to do.
        pipe = self._pipe("pipe-light", 10.0, mass=4.0)
        result = _evaluate(_rule([pipe], applies_when=self.SCOPE))
        assert result["not_applicable_count"] == 1
        assert result["fail_count"] == 0
        assert result["status"] == "NOT_APPLICABLE"

    def test_at_the_threshold_stays_in_scope_and_fails(self):
        # 10.0 is inclusive, so a run of exactly 10 kg is governed.
        pipe = self._pipe("pipe-10kg", 10.0, mass=10.0)
        result = _evaluate(_rule([pipe], applies_when=self.SCOPE))
        assert result["fail_count"] == 1
        assert result["not_applicable_count"] == 0

    def test_above_the_threshold_passes_on_adequate_clearance(self):
        pipe = self._pipe("pipe-heavy", 80.0, mass=95.0)
        result = _evaluate(_rule([pipe], applies_when=self.SCOPE))
        assert result["status"] == "PASS"

    def test_heavy_small_bore_run_is_no_longer_dropped(self):
        # THE REGRESSION THIS RETIREMENT PREVENTS. A 25 mm run carrying 40 kg
        # is exactly what the clause is about, and exactly what the retired
        # nominal-bore band excluded: NO_MATCH on the diameter settled the
        # predicate before the mass gate was ever consulted, so the element
        # left the rule's scope and no verdict was produced for it.
        pipe = self._pipe("pipe-dn25-heavy", 10.0, mass=40.0, diameter=25.0)
        result = _evaluate(_rule([pipe], applies_when=self.SCOPE))
        assert result["fail_count"] == 1
        assert result["not_applicable_count"] == 0

        # And the proof that the old scope really did drop it, so this test
        # cannot quietly stop testing anything if the scope is edited back.
        retired = dict(self.SCOPE, nominal_diameter_mm={"min": 50.0})
        assert _evaluate(_rule([pipe], applies_when=retired))["fail_count"] == 0

    def test_unresolved_mass_keeps_the_element_in_scope(self):
        # A model that does not author or yield a mass must not have the check
        # silently suppressed -- an unevaluable narrowing never drops an
        # element, it only reports the gap.
        pipe = self._pipe("pipe-unknown-mass", 10.0)
        result = _evaluate(_rule([pipe], applies_when=self.SCOPE))
        assert result["fail_count"] == 1
        assert result["not_applicable_count"] == 0
        assert any("MassKg" in n for n in result["undetermined_predicates"])

    def test_location_remains_reported_as_unsupported(self):
        # `location` is still not a key the comparator can evaluate. It stays
        # in the predicate holding the clause's real condition, and surfaces
        # as an undetermined predicate rather than being quietly dropped.
        pipe = self._pipe("pipe-heavy", 10.0, mass=40.0)
        result = _evaluate(_rule([pipe], applies_when=self.SCOPE))
        assert any("location" in n for n in result["undetermined_predicates"])

    def test_scope_matches_the_patch_script_and_the_corpus(self):
        # The scope now lives in three places -- this test, the patch script
        # that writes the catalog, and the NotebookLM corpus the rule was
        # imported from. They are three copies of one fact, so assert they
        # agree rather than letting them drift the way the retired `note` did.
        import json
        import pathlib

        from scripts.patch_nzs4219_513_scope import REFERENCE, RETIRED_APPLIES_WHEN

        assert self.SCOPE == RETIRED_APPLIES_WHEN
        assert "nominal_diameter_mm" not in RETIRED_APPLIES_WHEN

        corpus = json.loads(
            pathlib.Path("data/notebooklm_exports/real_seismic_rules.json").read_text(
                encoding="utf-8"
            )
        )
        row = next(r for r in corpus if r["reference"] == REFERENCE)
        assert row["applies_when"] == RETIRED_APPLIES_WHEN
