"""
Unit tests for the Module 2 PipingElement producer.

Covers the classifiers (material, system, environment, subtype, joint, media)
and the three-tier connectivity resolution: IFC ports, centerline endpoint
proximity, and the indeterminable fallback.

Run: uv run pytest tests/test_piping_producer.py -v
"""

import pytest

from app.modules.module2_ifc_read import piping_producer as pp
from app.modules.module2_ifc_read.piping_schema import (
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
