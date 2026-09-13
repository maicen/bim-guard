"""Unit tests for spatial adjacency fallback, envelope classification, and model healing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.ifc_reader.ifc_spatial import (
    IFCSpatialAdjacency,
    _element_matches_location,
    classify_envelope_elements,
    heal_spatial_boundaries,
    is_exterior_element,
)


class MockElement:
    def __init__(self, guid: str, ifc_type: str, psets: dict | None = None):
        self.GlobalId = guid
        self._type = ifc_type
        self._psets = psets or {}
        self.ContainedInStructure = []
        self.Decomposes = []

    def is_a(self, type_name: str | None = None) -> str | bool:
        if type_name is None:
            return self._type
        return self._type == type_name


class MockIFCFile:
    def __init__(self, spaces=None, walls=None, doors=None, boundaries=None):
        self._spaces = spaces or []
        self._walls = walls or []
        self._doors = doors or []
        self._boundaries = boundaries or []

    def by_type(self, ifc_type: str) -> list:
        if ifc_type == "IfcSpace":
            return list(self._spaces)
        elif ifc_type == "IfcWall":
            return [w for w in self._walls if w.is_a() == "IfcWall"]
        elif ifc_type == "IfcWallStandardCase":
            return [w for w in self._walls if w.is_a() == "IfcWallStandardCase"]
        elif ifc_type == "IfcDoor":
            return list(self._doors)
        elif ifc_type == "IfcRelSpaceBoundary":
            return list(self._boundaries)
        elif ifc_type in ("IfcSlab", "IfcRoof"):
            return []
        return []

    def create_entity(self, entity_type: str, **kwargs) -> MagicMock:
        entity = MagicMock()
        entity.is_a.return_value = entity_type
        for k, v in kwargs.items():
            setattr(entity, k, v)
        if entity_type == "IfcRelSpaceBoundary":
            self._boundaries.append(entity)
        return entity


def test_spatial_adjacency_with_explicit_boundaries():
    space = MockElement("SPACE-01", "IfcSpace")
    wall = MockElement("WALL-01", "IfcWall")

    rel = MagicMock()
    rel.RelatingSpace = space
    rel.RelatedBuildingElement = wall
    rel.PhysicalOrVirtualBoundary = "PHYSICAL"

    mock_file = MockIFCFile(spaces=[space], walls=[wall], boundaries=[rel])
    adj = IFCSpatialAdjacency(mock_file, fallback_to_geometric=False).build()

    assert adj.has_boundaries is True
    assert adj.is_geometric_fallback is False
    assert len(adj.get_space_elements("SPACE-01", "IfcWall")) == 1
    assert adj.get_space_elements("SPACE-01", "IfcWall")[0].GlobalId == "WALL-01"


def test_spatial_adjacency_geometric_fallback():
    space = MockElement("SPACE-01", "IfcSpace")
    wall1 = MockElement("WALL-01", "IfcWall")
    wall2 = MockElement("WALL-02", "IfcWall")

    mock_file = MockIFCFile(spaces=[space], walls=[wall1, wall2], boundaries=[])

    # Mock bounding boxes: space touches wall1, but not wall2
    def mock_get_bbox(element):
        if element.GlobalId == "SPACE-01":
            return {"min_x": 0.0, "max_x": 5000.0, "min_y": 0.0, "max_y": 5000.0, "min_z": 0.0, "max_z": 3000.0}
        elif element.GlobalId == "WALL-01":
            # Right next to space (touching at x=5000)
            return {"min_x": 5000.0, "max_x": 5200.0, "min_y": 0.0, "max_y": 5000.0, "min_z": 0.0, "max_z": 3000.0}
        elif element.GlobalId == "WALL-02":
            # Far away
            return {"min_x": 20000.0, "max_x": 20200.0, "min_y": 0.0, "max_y": 5000.0, "min_z": 0.0, "max_z": 3000.0}
        return None

    with patch("app.modules.ifc_reader.ifc_geometry.IFCGeometryExtractor") as mock_extractor_cls:
        mock_extractor = MagicMock()
        mock_extractor.get_bounding_box.side_effect = mock_get_bbox
        mock_extractor_cls.return_value = mock_extractor

        adj = IFCSpatialAdjacency(mock_file, fallback_to_geometric=True).build()

        assert adj.has_boundaries is True
        assert adj.is_geometric_fallback is True
        elements = adj.get_space_elements("SPACE-01", "IfcWall")
        assert len(elements) == 1
        assert elements[0].GlobalId == "WALL-01"
        assert "WALL-01" in adj._wall_spaces


def test_heal_spatial_boundaries():
    space = MockElement("SPACE-01", "IfcSpace")
    wall = MockElement("WALL-01", "IfcWall")
    mock_file = MockIFCFile(spaces=[space], walls=[wall], boundaries=[])

    def mock_get_bbox(element):
        if element.GlobalId == "SPACE-01":
            return {"min_x": 0.0, "max_x": 5000.0, "min_y": 0.0, "max_y": 5000.0, "min_z": 0.0, "max_z": 3000.0}
        elif element.GlobalId == "WALL-01":
            return {"min_x": 5000.0, "max_x": 5200.0, "min_y": 0.0, "max_y": 5000.0, "min_z": 0.0, "max_z": 3000.0}
        return None

    with patch("app.modules.ifc_reader.ifc_geometry.IFCGeometryExtractor") as mock_extractor_cls:
        mock_extractor = MagicMock()
        mock_extractor.get_bounding_box.side_effect = mock_get_bbox
        mock_extractor_cls.return_value = mock_extractor

        result = heal_spatial_boundaries(mock_file)

        assert result["healed_spaces"] == 1
        assert result["created_boundaries"] == 1
        assert result["total_boundaries"] == 1
        assert result["status"] == "success"

        # Subsequent heal call on same model is already healed
        result2 = heal_spatial_boundaries(mock_file)
        assert result2["created_boundaries"] == 0
        assert result2["status"] == "already_healed"


def test_classify_envelope_elements():
    exterior_wall_1 = MockElement("WALL-EXT-1", "IfcWall")
    exterior_wall_2 = MockElement("WALL-EXT-2", "IfcWall")
    interior_wall = MockElement("WALL-INT", "IfcWall")

    mock_file = MockIFCFile(walls=[exterior_wall_1, exterior_wall_2, interior_wall])

    def mock_get_bbox(element):
        if element.GlobalId == "WALL-EXT-1":
            # Left outer envelope
            return {"min_x": 0.0, "max_x": 200.0, "min_y": 0.0, "max_y": 10000.0, "min_z": 0.0, "max_z": 3000.0}
        elif element.GlobalId == "WALL-EXT-2":
            # Right outer envelope
            return {"min_x": 9800.0, "max_x": 10000.0, "min_y": 0.0, "max_y": 10000.0, "min_z": 0.0, "max_z": 3000.0}
        elif element.GlobalId == "WALL-INT":
            # Inside building
            return {"min_x": 5000.0, "max_x": 5200.0, "min_y": 2000.0, "max_y": 8000.0, "min_z": 0.0, "max_z": 3000.0}
        return None

    with patch("app.modules.ifc_reader.ifc_geometry.IFCGeometryExtractor") as mock_extractor_cls:
        mock_extractor = MagicMock()
        mock_extractor.get_bounding_box.side_effect = mock_get_bbox
        mock_extractor_cls.return_value = mock_extractor

        classification = classify_envelope_elements(mock_file)
        assert classification.get("WALL-EXT-1") == "exterior_wall"
        assert classification.get("WALL-EXT-2") == "exterior_wall"
        assert classification.get("WALL-INT") == "interior_wall"

        assert is_exterior_element(exterior_wall_1, mock_file) is True
        assert is_exterior_element(exterior_wall_2, mock_file) is True
        assert is_exterior_element(interior_wall, mock_file) is False
        assert _element_matches_location(exterior_wall_1, "exterior", mock_file) is True
        assert _element_matches_location(interior_wall, "interior", mock_file) is True
