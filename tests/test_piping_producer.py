"""
Unit tests for the Module 2 PipingElement producer.

Covers the classifiers (material, system, environment, subtype, joint, media)
and the three-tier connectivity resolution: IFC ports, centerline endpoint
proximity, and the indeterminable fallback.

Run: uv run pytest tests/test_piping_producer.py -v
"""

import pytest

from app.modules.ifc_reader import piping_producer as pp
from app.modules.ifc_reader.piping_schema import (
    CANONICAL_MATERIALS,
    Centerline,
    EnvironmentClass,
    PipingElement,
    PipingSystem,
    Point3D,
)


def element(element_id: str, points=None, centroid=None) -> PipingElement:
    """Build a minimal PipingElement for adjacency tests."""
    return PipingElement(
        id=element_id,
        ifc_class="IfcPipeSegment",
        subtype="pipe_segment",
        centerline=Centerline(points=[Point3D(*p) for p in points]) if points else None,
        centroid=Point3D(*centroid) if centroid else None,
    )


class FakeModel:
    """Minimal stand-in for an ifcopenshell model, for port-tier tests."""

    def __init__(self, entities: dict):
        self._entities = entities

    def by_type(self, name: str):
        return self._entities.get(name, [])


class FakePort:
    """A port with a stable entity id."""

    def __init__(self, entity_id: int):
        self._id = entity_id

    def id(self) -> int:
        return self._id

    def is_a(self, name: str = "") -> str | bool:
        return "IfcPort" if not name else name in ("IfcPort", "IfcDistributionPort")


class FakeOwner:
    """An element that owns ports."""

    def __init__(self, global_id: str):
        self.GlobalId = global_id


class FakeRelPortToElement:
    """IfcRelConnectsPortToElement stand-in."""

    def __init__(self, port, owner):
        self.RelatingPort = port
        self.RelatedElement = owner


class FakeRelConnectsPorts:
    """IfcRelConnectsPorts stand-in."""

    def __init__(self, a, b):
        self.RelatingPort = a
        self.RelatedPort = b


class TestMaterialNormalisation:
    """normalise_material maps free text onto CANONICAL_MATERIALS."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Stainless Steel 316L", "SS316L"),
            ("SS 1.4401", "SS316"),
            ("EN 1.4301", "SS304"),
            ("Super Duplex 2507", "SuperDuplex2507"),
            ("Duplex 2205", "Duplex2205"),
            ("Hot Dip Galvanised Steel", "GalvanisedSteel"),
            ("HDG", "GalvanisedSteel"),
            ("Mild Steel", "CarbonSteel"),
            ("S355 structural", "CarbonSteel"),
            ("Copper C12200", "Copper_C12200"),
            ("Naval Brass", "Brass_C46400"),
            ("CuNi 70/30", "CuNi_7030"),
            ("Cupronickel", "CuNi_9010"),
            ("Ductile Iron", "DuctileIron"),
            ("Grey Iron", "CastIron"),
            ("uPVC", "PVC"),
            ("PEX-a", "PEX"),
            ("HDPE SDR11", "HDPE"),
            ("Titanium Grade 2", "Titanium"),
        ],
    )
    def test_known_materials(self, raw, expected):
        """Recognised material text maps to its canonical key."""
        assert pp.normalise_material(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "   ", "Unobtainium", "concrete_reinforced_prefab"])
    def test_unrecognised_is_unknown(self, raw):
        """Unrecognised or empty material text yields the Unknown sentinel."""
        assert pp.normalise_material(raw) == "Unknown"

    def test_specific_beats_generic(self):
        """Ordering puts specific grades ahead of the bare-metal fallbacks."""
        assert pp.normalise_material("Super Duplex 2507") != "Duplex2205"
        assert pp.normalise_material("Galvanised steel pipe") == "GalvanisedSteel"

    def test_every_output_is_canonical(self):
        """No rule may emit a key the rule packs cannot score."""
        emitted = {key for _, key in pp._MATERIAL_RULES}
        assert emitted <= CANONICAL_MATERIALS


class TestClassifiers:
    """System, environment, subtype, joint, and media classification."""

    @pytest.mark.parametrize(
        "hint,expected",
        [
            ("Domestic Hot Water Return", PipingSystem.DOMESTIC_HOT_WATER_RETURN),
            ("CHW Flow", PipingSystem.CHILLED_WATER_FLOW),
            ("Pool Circulation", PipingSystem.POOL_CIRCULATION),
            ("Pool Chemical Dosing", PipingSystem.POOL_CHEMICAL_DOSING),
            ("Medical Gas Oxygen", PipingSystem.MEDICAL_GAS_OXYGEN),
            ("Sprinkler Main", PipingSystem.FIRE_SPRINKLER),
            ("HP Steam", PipingSystem.STEAM_HP),
            ("nothing recognisable", PipingSystem.UNKNOWN),
        ],
    )
    def test_system(self, hint, expected):
        """System classification picks the most specific matching rule."""
        assert pp.classify_system(hint) is expected

    def test_system_uses_first_matching_hint(self):
        """Earlier hints take precedence over later ones."""
        assert pp.classify_system("Chilled Water", "Hot Water") is PipingSystem.CHILLED_WATER_FLOW

    def test_system_skips_empty_hints(self):
        """None and empty hints are ignored rather than short-circuiting."""
        assert pp.classify_system(None, "", "Pool Circulation") is PipingSystem.POOL_CIRCULATION

    @pytest.mark.parametrize(
        "hint,expected",
        [
            ("Swimming Pool Hall", EnvironmentClass.T3_CHLORIDE),
            ("Marine Splash Deck", EnvironmentClass.T4_MARINE),
            ("Coastal Plant Room", EnvironmentClass.T3_CHLORIDE),
            ("Industrial Process Hall", EnvironmentClass.T5_INDUSTRIAL),
            ("Basement Plant Room", EnvironmentClass.T1_INDOOR_DAMP),
            ("Open Plan Office", EnvironmentClass.T0_DRY),
        ],
    )
    def test_environment(self, hint, expected):
        """Environment severity is inferred from spatial naming."""
        assert pp.classify_environment(hint) is expected

    def test_environment_unknown_is_not_dry(self):
        """Absent spatial names give UNCLASSIFIED, never a false T0_DRY.

        T0_DRY asserts the environment is benign. Conflating "we do not know"
        with "it is dry" would silently suppress corrosion findings.
        """
        assert pp.classify_environment(None, "") is EnvironmentClass.UNCLASSIFIED

    @pytest.mark.parametrize(
        "ifc_class,name,expected",
        [
            ("IfcPipeSegment", "Pipe run A", "pipe_segment"),
            ("IfcValve", None, "valve"),
            ("IfcFlowTerminal", "FCU-03", "fcu"),
            ("IfcFlowSegment", "Y-Strainer 50mm", "strainer"),
            ("IfcDistributionElement", None, "other"),
            ("IfcSomethingUnmapped", None, "other"),
        ],
    )
    def test_subtype(self, ifc_class, name, expected):
        """Subtype derives from name hints first, then the IFC class."""
        assert pp.classify_subtype(ifc_class, name) == expected

    def test_joint_type_none_when_absent(self):
        """No joint hint yields None, distinct from JointType.UNKNOWN."""
        assert pp.classify_joint_type(None, "Pipe run") is None

    def test_joint_type_dielectric(self):
        """Dielectric unions are recognised — they break galvanic continuity."""
        assert pp.classify_joint_type("Dielectric Union DN50").name == "JT014_DIELECTRIC_UNION"

    def test_media_covers_every_system(self):
        """Every PipingSystem member must resolve to a media key."""
        for system in PipingSystem:
            assert pp.media_for_system(system), f"no media for {system}"

    def test_media_derives_from_system(self):
        """Media is a function of system, not a stored field."""
        assert pp.media_for_system(PipingSystem.POOL_CIRCULATION) == "pool_water"
        assert pp.media_for_system(PipingSystem.STEAM_HP) == "steam"
        assert pp.media_for_system(PipingSystem.HEATING_RETURN) == "hot_water"


class TestTier1Ports:
    """Tier 1 — authored IFC port connectivity is authoritative."""

    def test_ports_link_elements(self):
        """Two elements joined through connected ports become adjacent."""
        port_a, port_b = FakePort(1), FakePort(2)
        owner_a, owner_b = FakeOwner("GUID-A"), FakeOwner("GUID-B")
        model = FakeModel(
            {
                "IfcRelConnectsPortToElement": [
                    FakeRelPortToElement(port_a, owner_a),
                    FakeRelPortToElement(port_b, owner_b),
                ],
                "IfcRelConnectsPorts": [FakeRelConnectsPorts(port_a, port_b)],
            }
        )
        assert pp._port_adjacency(model) == {"GUID-A": {"GUID-B"}, "GUID-B": {"GUID-A"}}

    def test_self_connection_ignored(self):
        """A port pair owned by one element is not self-adjacency."""
        port_a, port_b = FakePort(1), FakePort(2)
        owner = FakeOwner("GUID-A")
        model = FakeModel(
            {
                "IfcRelConnectsPortToElement": [
                    FakeRelPortToElement(port_a, owner),
                    FakeRelPortToElement(port_b, owner),
                ],
                "IfcRelConnectsPorts": [FakeRelConnectsPorts(port_a, port_b)],
            }
        )
        assert pp._port_adjacency(model) == {}

    def test_no_ports_yields_empty(self):
        """A model without port connectivity produces no Tier 1 adjacency."""
        assert pp._port_adjacency(FakeModel({})) == {}

    def test_tier1_wins_over_geometry(self):
        """Port-resolved elements are tagged 'ports', not 'centerline'."""
        port_a, port_b = FakePort(1), FakePort(2)
        model = FakeModel(
            {
                "IfcRelConnectsPortToElement": [
                    FakeRelPortToElement(port_a, FakeOwner("A")),
                    FakeRelPortToElement(port_b, FakeOwner("B")),
                ],
                "IfcRelConnectsPorts": [FakeRelConnectsPorts(port_a, port_b)],
            }
        )
        # Geometrically far apart — only the ports say they are joined.
        a = element("A", points=[(0, 0, 0), (1, 0, 0)])
        b = element("B", points=[(500, 0, 0), (501, 0, 0)])
        counts = pp._build_adjacency(model, [a, b], 0.05)

        assert counts["ports"] == 2
        assert counts["pairs"] == 1
        assert a.joined_to == ["B"]
        assert a.properties[pp.CONNECTIVITY_SOURCE_KEY] == "ports"


class TestTier2Centerline:
    """Tier 2 — endpoint proximity within tolerance."""

    def test_endpoints_within_tolerance_link(self):
        """Pipes meeting end to end within 50 mm are adjacent."""
        a = element("A", points=[(0, 0, 0), (2.5, 0, 0)])
        b = element("B", points=[(2.53, 0, 0), (5.0, 0, 0)])
        counts = pp._build_adjacency(FakeModel({}), [a, b], 0.05)

        assert counts["pairs"] == 1
        assert counts["centerline"] == 2
        assert b.id in a.joined_to and a.id in b.joined_to

    def test_endpoints_beyond_tolerance_do_not_link(self):
        """A 1.3 m gap is not adjacency, matching the real drainage model."""
        a = element("A", points=[(0, 0, 0), (2.5, 0, 0)])
        b = element("B", points=[(3.8, 0, 0), (6.0, 0, 0)])
        counts = pp._build_adjacency(FakeModel({}), [a, b], 0.05)

        assert counts["pairs"] == 0
        assert a.joined_to == []

    def test_origins_far_apart_still_link(self):
        """Endpoint testing catches joins that origin-proximity would miss.

        Both origins sit 2.5 m apart — the bug that made the first
        implementation report zero adjacencies on every long run.
        """
        a = element("A", points=[(0, 0, 0), (2.5, 0, 0)])
        b = element("B", points=[(2.5, 0, 0), (5.0, 0, 0)])
        pp._build_adjacency(FakeModel({}), [a, b], 0.05)
        assert a.joined_to == ["B"]

    def test_adjacency_is_symmetric(self):
        """Every link appears on both elements exactly once."""
        a = element("A", points=[(0, 0, 0), (1, 0, 0)])
        b = element("B", points=[(1, 0, 0), (2, 0, 0)])
        c = element("C", points=[(2, 0, 0), (3, 0, 0)])
        pp._build_adjacency(FakeModel({}), [a, b, c], 0.05)

        assert a.joined_to == ["B"]
        assert sorted(b.joined_to) == ["A", "C"]
        assert c.joined_to == ["B"]

    def test_centroid_fallback_when_no_centerline(self):
        """An element with only a centroid still participates in Tier 2."""
        a = element("A", centroid=(0, 0, 0))
        b = element("B", centroid=(0.02, 0, 0))
        counts = pp._build_adjacency(FakeModel({}), [a, b], 0.05)
        assert counts["pairs"] == 1


class TestTier3Indeterminable:
    """Tier 3 — neither ports nor geometry available."""

    def test_no_geometry_is_flagged(self):
        """Elements with no geometry get the XM-001 skip warning."""
        a = element("A")
        counts = pp._build_adjacency(FakeModel({}), [a], 0.05)

        assert counts["indeterminable"] == 1
        assert a.joined_to == []
        assert pp.CONNECTIVITY_INDETERMINABLE in a.extraction_warnings
        assert a.properties[pp.CONNECTIVITY_SOURCE_KEY] == "indeterminable"

    def test_empty_joined_to_is_disambiguated(self):
        """An isolated element and an unknowable one both have joined_to == [].

        The only thing separating them is the tier marker, which is why
        XM-001 must read that rather than the empty list.
        """
        isolated = element("ISO", points=[(0, 0, 0), (1, 0, 0)])
        unknown = element("UNK")
        pp._build_adjacency(FakeModel({}), [isolated, unknown], 0.05)

        assert isolated.joined_to == unknown.joined_to == []
        assert isolated.properties[pp.CONNECTIVITY_SOURCE_KEY] == "centerline"
        assert unknown.properties[pp.CONNECTIVITY_SOURCE_KEY] == "indeterminable"
        assert pp.CONNECTIVITY_INDETERMINABLE not in isolated.extraction_warnings

    def test_warning_text_is_ascii(self):
        """The warning must print on a cp1252 console without raising."""
        pp.CONNECTIVITY_INDETERMINABLE.encode("cp1252")




if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestMaterialInferenceFromSystem:
    """infer_material_from_system deduces a material from the piping system.

    The table is a statement about ordinary design practice, not a reading of
    any model, so these tests pin two things equally: that the conventions it
    does encode are the right ones, and that the systems it deliberately
    leaves out stay out.
    """

    @pytest.mark.parametrize(
        "system,expected",
        [
            (PipingSystem.DOMESTIC_HOT_WATER, "Copper_C12200"),
            (PipingSystem.DOMESTIC_HOT_WATER_RETURN, "Copper_C12200"),
            (PipingSystem.DOMESTIC_COLD_WATER, "Copper_C12200"),
            (PipingSystem.MEDICAL_GAS_OXYGEN, "Copper_C12200"),
            (PipingSystem.CHILLED_WATER_FLOW, "CarbonSteel"),
            (PipingSystem.HEATING_RETURN, "CarbonSteel"),
            (PipingSystem.STEAM_HP, "CarbonSteel"),
            (PipingSystem.CONDENSATE_RETURN, "CarbonSteel"),
            (PipingSystem.NATURAL_GAS, "CarbonSteel"),
            (PipingSystem.FIRE_SPRINKLER, "GalvanisedSteel"),
            (PipingSystem.FIRE_WET_RISER, "GalvanisedSteel"),
            (PipingSystem.FOUL_DRAINAGE, "CastIron"),
            (PipingSystem.POOL_CIRCULATION, "SS316"),
            (PipingSystem.POOL_CHEMICAL_DOSING, "SS316"),
        ],
    )
    def test_conventional_systems_infer(self, system, expected):
        assert pp.infer_material_from_system(system) == expected

    @pytest.mark.parametrize(
        "system",
        [
            PipingSystem.UNKNOWN,
            PipingSystem.RAINWATER,          # PVC, cast iron and aluminium all ordinary
            PipingSystem.COMPRESSED_AIR,     # steel, copper and aluminium all standard
            PipingSystem.MEDICAL_GAS_VACUUM, # plastics permitted in some codes
        ],
    )
    def test_ambiguous_systems_infer_nothing(self, system):
        """No single ordinary material means no guess. None is the answer."""
        assert pp.infer_material_from_system(system) is None

    @pytest.mark.parametrize("system", [None, "", "not_a_system", 42])
    def test_unusable_input_infers_nothing(self, system):
        assert pp.infer_material_from_system(system) is None

    def test_accepts_the_enum_value_as_a_string(self):
        """Callers holding the serialised form get the same answer."""
        assert pp.infer_material_from_system("fire_sprinkler") == "GalvanisedSteel"
        assert pp.infer_material_from_system("DOMESTIC_HOT_WATER".lower()) == "Copper_C12200"

    def test_every_inference_is_canonical(self):
        """An off-vocabulary key would fail silently as a data-quality issue."""
        emitted = {material for material, _ in pp._SYSTEM_MATERIAL_INFERENCE.values()}
        assert emitted <= CANONICAL_MATERIALS
        assert "Unknown" not in emitted

    def test_confidence_is_declared_for_every_entry(self):
        levels = {conf for _, conf in pp._SYSTEM_MATERIAL_INFERENCE.values()}
        assert levels <= {"established", "provisional"}


class TestResolveMaterialProvenance:
    """resolve_material must say where each answer came from."""

    def test_ifc_metadata_wins_over_inference(self, monkeypatch):
        """A material in the file is never overridden by a convention."""
        monkeypatch.setattr(pp, "extract_normalized_material", lambda _: "SS316")
        material, source, confidence = pp.resolve_material(
            object(), PipingSystem.FIRE_SPRINKLER
        )
        assert material == "SS316"
        assert source == pp.MATERIAL_SOURCE_IFC
        assert confidence is None

    def test_property_fallback_still_counts_as_read_from_ifc(self, monkeypatch):
        """Material in a Pset is a reading of the model, not an assumption.

        This is the only source that resolves anything on the Clinic models,
        where the material sits in a property and no association exists.
        """
        monkeypatch.setattr(pp, "extract_normalized_material", lambda _: None)
        material, source, _ = pp.resolve_material(
            object(), PipingSystem.FIRE_SPRINKLER, properties={"Material": "Copper"}
        )
        assert material == "Copper_C12200"
        assert source == pp.MATERIAL_SOURCE_IFC

    def test_inference_is_tagged_with_the_system_that_drove_it(self, monkeypatch):
        monkeypatch.setattr(pp, "extract_normalized_material", lambda _: None)
        material, source, confidence = pp.resolve_material(
            object(), PipingSystem.FIRE_SPRINKLER
        )
        assert material == "GalvanisedSteel"
        assert source == f"{pp.MATERIAL_SOURCE_INFERENCE}:fire_sprinkler"
        assert confidence == "provisional"

    def test_unresolvable_stays_none(self, monkeypatch):
        """Neither source resolving is Undetermined, not a default material."""
        monkeypatch.setattr(pp, "extract_normalized_material", lambda _: None)
        material, source, confidence = pp.resolve_material(object(), PipingSystem.UNKNOWN)
        assert material is None
        assert source is None
        assert confidence is None

    def test_inference_can_be_switched_off(self, monkeypatch):
        """allow_inference=False gives the reading of the file alone."""
        monkeypatch.setattr(pp, "extract_normalized_material", lambda _: None)
        material, source, _ = pp.resolve_material(
            object(), PipingSystem.FIRE_SPRINKLER, allow_inference=False
        )
        assert material is None
        assert source is None

    def test_never_returns_a_falsy_non_none_material(self, monkeypatch):
        """Missing data must be None - never False, "" or "Unknown"."""
        monkeypatch.setattr(pp, "extract_normalized_material", lambda _: None)
        material, _, _ = pp.resolve_material(object(), PipingSystem.RAINWATER)
        assert material is None
        assert material is not False
        assert material != "Unknown"


class TestMaterialCoverage:
    """material_coverage counts the two sources separately."""

    def _element(self, element_id, source):
        properties = {pp.MATERIAL_SOURCE_KEY: source} if source else {}
        return PipingElement(
            id=element_id,
            ifc_class="IfcPipeSegment",
            subtype="pipe_segment",
            properties=properties,
        )

    def test_counts_each_source(self):
        elements = [
            self._element("a", pp.MATERIAL_SOURCE_IFC),
            self._element("b", f"{pp.MATERIAL_SOURCE_INFERENCE}:fire_sprinkler"),
            self._element("c", f"{pp.MATERIAL_SOURCE_INFERENCE}:domestic_hot_water"),
            self._element("d", None),
        ]
        assert pp.material_coverage(elements) == {
            "total": 4, "from_ifc": 1, "inferred": 2, "unknown": 1,
        }

    def test_inferred_is_never_folded_into_from_ifc(self):
        """The headline number must not let an assumption pass for a reading."""
        elements = [self._element("a", f"{pp.MATERIAL_SOURCE_INFERENCE}:fire_sprinkler")]
        counts = pp.material_coverage(elements)
        assert counts["from_ifc"] == 0
        assert counts["inferred"] == 1

    def test_empty_network(self):
        assert pp.material_coverage([]) == {
            "total": 0, "from_ifc": 0, "inferred": 0, "unknown": 0,
        }


# ---------------------------------------------------------------------------
# Environment provenance and the T1 indoor default
# ---------------------------------------------------------------------------


class TestEnvironmentProvenance:
    """Environment resolves in three tiers: IFC property, spatial names, default.

    EnvironmentClass is the atmosphere around the pipe, never the fluid in it,
    so a potable-water system must not push an indoor pipe towards marine.
    """

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("T1", EnvironmentClass.T1_INDOOR_DAMP),
            ("t0", EnvironmentClass.T0_DRY),
            ("T3 chloride", EnvironmentClass.T3_CHLORIDE),
            ("T4_marine", EnvironmentClass.T4_MARINE),
            ("T5_INDUSTRIAL", EnvironmentClass.T5_INDUSTRIAL),
            ("T2-humid", EnvironmentClass.T2_HUMID),
            ("unclassified", None),
            ("T10", None),
            ("marine", None),
            ("", None),
            (None, None),
        ],
    )
    def test_parse_environment_class(self, raw, expected):
        assert pp.parse_environment_class(raw) is expected

    def test_explicit_ifc_property_wins_and_is_high_confidence(self):
        env, source, confidence, warning = pp.resolve_environment(
            {"EnvironmentClass": "T4"}, "Open Plan Office"
        )
        assert env is EnvironmentClass.T4_MARINE
        assert source == pp.ENVIRONMENT_SOURCE_IFC
        assert confidence == "high"
        assert warning is None

    def test_spatial_names_are_medium_confidence(self):
        env, source, confidence, warning = pp.resolve_environment({}, "Pool Hall", "L01", None)
        assert env is EnvironmentClass.T3_CHLORIDE
        assert source == pp.ENVIRONMENT_SOURCE_SPATIAL
        assert confidence == "medium"
        assert warning is None

    def test_default_is_t1_indoor_damp_low_confidence_with_warning(self):
        env, source, confidence, warning = pp.resolve_environment({}, None, "Level 1", None)
        assert env is EnvironmentClass.T1_INDOOR_DAMP
        assert env is pp.DEFAULT_ENVIRONMENT_CLASS
        assert source == pp.ENVIRONMENT_SOURCE_DEFAULT
        assert confidence == "low"
        assert warning == pp.ENVIRONMENT_DEFAULTED_WARNING
        assert "T1_indoor_damp" in warning and "low confidence" in warning

    def test_default_can_be_switched_off(self):
        env, source, confidence, warning = pp.resolve_environment(
            {}, None, "Level 1", None, allow_default=False
        )
        assert env is EnvironmentClass.UNCLASSIFIED
        assert source is None and confidence is None
        assert warning == pp.ENVIRONMENT_UNCLASSIFIED_WARNING

    def test_media_never_drives_the_atmosphere_class(self):
        """Potable water in an unnamed room is indoor by default, not marine."""
        env, source, _, _ = pp.resolve_environment({}, None, None, "Domestic Cold Water")
        assert env is EnvironmentClass.T1_INDOOR_DAMP
        assert source == pp.ENVIRONMENT_SOURCE_DEFAULT

    def test_a_property_saying_unclassified_is_not_a_classification(self):
        env, source, _, _ = pp.resolve_environment({"EnvironmentClass": "unclassified"}, None)
        assert env is EnvironmentClass.T1_INDOOR_DAMP
        assert source == pp.ENVIRONMENT_SOURCE_DEFAULT

    def test_confidence_ladder(self):
        assert pp.ENVIRONMENT_CONFIDENCE == {
            pp.ENVIRONMENT_SOURCE_IFC: "high",
            pp.ENVIRONMENT_SOURCE_SPATIAL: "medium",
            pp.ENVIRONMENT_SOURCE_DEFAULT: "low",
        }


MEP_SCENARIO_MODEL = "data/test_hospital_mep_scenario.ifc"


@pytest.fixture(scope="module")
def elements():
    """Producer output for the small hospital MEP scenario model."""
    from pathlib import Path

    if not Path(MEP_SCENARIO_MODEL).exists():
        pytest.skip(f"{MEP_SCENARIO_MODEL} not available")
    return pp.produce_piping_elements(MEP_SCENARIO_MODEL)


class TestEnvironmentCoverageOnModel:
    """On a real MEP model every element ends up classified, with provenance."""

    MODEL = MEP_SCENARIO_MODEL

    def test_every_element_is_classified_with_provenance(self, elements):
        assert elements
        for element in elements:
            assert element.environment_class is not EnvironmentClass.UNCLASSIFIED
            assert element.environment_source in (
                pp.ENVIRONMENT_SOURCE_IFC,
                pp.ENVIRONMENT_SOURCE_SPATIAL,
                pp.ENVIRONMENT_SOURCE_DEFAULT,
            )
            assert element.environment_confidence in ("high", "medium", "low")

        counts = pp.environment_coverage(elements)
        assert counts["unclassified"] == 0
        assert counts["from_ifc"] + counts["spatial"] + counts["defaulted"] == counts["total"]

    def test_defaulted_elements_are_low_confidence_and_warned(self, elements):
        defaulted = [e for e in elements if e.environment_source == pp.ENVIRONMENT_SOURCE_DEFAULT]
        assert defaulted, "an MEP model without IfcSpace containment must hit the default"
        for element in defaulted:
            assert element.environment_class is EnvironmentClass.T1_INDOOR_DAMP
            assert element.environment_confidence == "low"
            assert pp.ENVIRONMENT_DEFAULTED_WARNING in element.extraction_warnings

    def test_switching_the_default_off_reproduces_the_raw_reading(self):
        from pathlib import Path

        if not Path(self.MODEL).exists():
            pytest.skip(f"{self.MODEL} not available")
        raw = pp.produce_piping_elements(self.MODEL, environment_default=False)
        counts = pp.environment_coverage(raw)
        assert counts["defaulted"] == 0
        assert counts["unclassified"] == counts["total"] - counts["from_ifc"] - counts["spatial"]
        for element in raw:
            if element.environment_class is EnvironmentClass.UNCLASSIFIED:
                assert element.environment_source is None
                assert pp.ENVIRONMENT_UNCLASSIFIED_WARNING in element.extraction_warnings

    def test_summary_line_reports_the_default_count(self, elements):
        summary = pp.summarise(elements)
        counts = pp.environment_coverage(elements)
        assert f"{counts['defaulted']} environment defaulted to T1_indoor_damp" in summary
        assert f"{counts['unclassified']} unclassified environment" in summary


class TestTemperatureInferenceFromSystem:
    """infer_temperature_from_system deduces a design temperature.

    The table is a statement about ordinary MEP design practice, not a reading
    of any model. These tests pin the conventions it encodes, the systems it
    deliberately leaves out, and - most importantly - which MM-001 stress band
    each value lands in. The 60 C zinc-polarity-reversal edge is a step, not a
    gradient, so a value drifting across a band edge changes a verdict.
    """

    @pytest.mark.parametrize(
        "system,expected",
        [
            (PipingSystem.DOMESTIC_HOT_WATER, 60.0),
            (PipingSystem.DOMESTIC_HOT_WATER_RETURN, 55.0),
            (PipingSystem.DOMESTIC_COLD_WATER, 15.0),
            (PipingSystem.CHILLED_WATER_FLOW, 6.0),
            (PipingSystem.CHILLED_WATER_RETURN, 12.0),
            (PipingSystem.HEATING_FLOW, 82.0),
            (PipingSystem.HEATING_RETURN, 71.0),
            (PipingSystem.CONDENSER_WATER, 30.0),
            (PipingSystem.STEAM_LP, 120.0),
            (PipingSystem.STEAM_HP, 180.0),
            (PipingSystem.CONDENSATE_RETURN, 90.0),
            (PipingSystem.POOL_CIRCULATION, 29.0),
            (PipingSystem.FIRE_SPRINKLER, 20.0),
            (PipingSystem.FIRE_WET_RISER, 20.0),
            (PipingSystem.MEDICAL_GAS_OXYGEN, 20.0),
            (PipingSystem.NATURAL_GAS, 20.0),
            (PipingSystem.COMPRESSED_AIR, 20.0),
        ],
    )
    def test_design_temperatures(self, system, expected):
        assert pp.infer_temperature_from_system(system) == expected

    @pytest.mark.parametrize(
        "system",
        [
            PipingSystem.FOUL_DRAINAGE,  # normally empty, intermittent discharges
            PipingSystem.RAINWATER,      # external, follows the weather
            PipingSystem.UNKNOWN,
        ],
    )
    def test_systems_without_a_design_temperature_infer_nothing(self, system):
        assert pp.infer_temperature_from_system(system) is None

    @pytest.mark.parametrize("system", [None, "", "not_a_system", 42])
    def test_unusable_input_infers_nothing(self, system):
        assert pp.infer_temperature_from_system(system) is None

    def test_accepts_the_enum_value_as_a_string(self):
        assert pp.infer_temperature_from_system("domestic_hot_water") == 60.0

    def test_dhw_sits_on_the_zinc_reversal_edge(self):
        """60 C is the band edge, and DHW must land in the band ABOVE it.

        The MM-001 bands are inclusive of their lower bound, so 60.0 falls in
        60-80 (stress 0.80), not 40-60 (0.55). Dropping DHW below 60 would
        score a galvanised hot-water line one band too kindly - the exact
        failure mode the reversal threshold exists to catch.
        """
        assert pp.infer_temperature_from_system(PipingSystem.DOMESTIC_HOT_WATER) >= 60.0

    def test_chilled_flow_stays_below_the_kinetics_floor(self):
        """Chilled flow belongs in the <10 C band the pack names for it."""
        assert pp.infer_temperature_from_system(PipingSystem.CHILLED_WATER_FLOW) < 10.0

    def test_confidence_is_declared_for_every_entry(self):
        levels = {conf for _, conf in pp._SYSTEM_TEMPERATURE_INFERENCE.values()}
        assert levels <= {"established", "provisional"}

    def test_every_temperature_is_physically_plausible(self):
        """A stray value would silently push elements into the wrong band."""
        for system, (temperature, _) in pp._SYSTEM_TEMPERATURE_INFERENCE.items():
            assert -50.0 < temperature < 400.0, system


class TestResolveTemperatureProvenance:
    """resolve_temperature must say where each answer came from."""

    def test_stated_property_wins_over_inference(self):
        temperature, source, confidence, warning = pp.resolve_temperature(
            {"OperatingTemperature": 45.0}, PipingSystem.DOMESTIC_HOT_WATER
        )
        assert temperature == 45.0
        assert source == pp.TEMPERATURE_SOURCE_IFC
        assert confidence == "high"
        assert warning is None

    @pytest.mark.parametrize(
        "key",
        ["OperatingTemperature", "WorkingTemperature", "FluidTemperature",
         "DesignTemperature", "MediumTemperature"],
    )
    def test_every_documented_property_key_is_read(self, key):
        temperature, source, _, _ = pp.resolve_temperature({key: 33.0})
        assert temperature == 33.0
        assert source == pp.TEMPERATURE_SOURCE_IFC

    def test_inference_is_tagged_and_warned(self):
        temperature, source, confidence, warning = pp.resolve_temperature(
            {}, PipingSystem.FIRE_SPRINKLER
        )
        assert temperature == 20.0
        assert source == pp.TEMPERATURE_SOURCE_INFERENCE
        assert confidence == "established"
        assert warning and "assumed from system" in warning

    def test_unresolvable_stays_none(self):
        """No property and no convention is Undetermined, not a default ambient.

        MM-001 raises temperature_missing for this rather than scoring, which
        is the whole point: a defaulted 20 C would score every unclassified
        element as though its service were known.
        """
        temperature, source, confidence, warning = pp.resolve_temperature(
            {}, PipingSystem.UNKNOWN
        )
        assert temperature is None
        assert source is None
        assert confidence is None
        assert warning == pp.TEMPERATURE_MISSING_WARNING

    def test_inference_can_be_switched_off(self):
        temperature, source, _, _ = pp.resolve_temperature(
            {}, PipingSystem.DOMESTIC_HOT_WATER, allow_inference=False
        )
        assert temperature is None
        assert source is None

    def test_zero_celsius_is_a_reading_not_a_miss(self):
        """0 C is falsy; it must not be mistaken for an absent value."""
        temperature, source, _, _ = pp.resolve_temperature({"OperatingTemperature": 0.0})
        assert temperature == 0.0
        assert source == pp.TEMPERATURE_SOURCE_IFC


class TestTemperatureCoverage:
    """temperature_coverage counts the two sources separately."""

    def _element(self, element_id, source):
        return PipingElement(
            id=element_id,
            ifc_class="IfcPipeSegment",
            subtype="pipe_segment",
            temperature_source=source,
        )

    def test_counts_each_source(self):
        elements = [
            self._element("a", pp.TEMPERATURE_SOURCE_IFC),
            self._element("b", pp.TEMPERATURE_SOURCE_INFERENCE),
            self._element("c", pp.TEMPERATURE_SOURCE_INFERENCE),
            self._element("d", None),
        ]
        assert pp.temperature_coverage(elements) == {
            "total": 4, "from_ifc": 1, "inferred": 2, "unknown": 1,
        }

    def test_inferred_is_never_folded_into_from_ifc(self):
        counts = pp.temperature_coverage([self._element("a", pp.TEMPERATURE_SOURCE_INFERENCE)])
        assert counts["from_ifc"] == 0
        assert counts["inferred"] == 1

    def test_empty_network(self):
        assert pp.temperature_coverage([]) == {
            "total": 0, "from_ifc": 0, "inferred": 0, "unknown": 0,
        }
