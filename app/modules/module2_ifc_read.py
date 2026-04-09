from pathlib import Path

try:
    import ifcopenshell
    import ifcopenshell.util.element

    _IFCOPENSHELL_AVAILABLE = True
except ImportError:
    _IFCOPENSHELL_AVAILABLE = False


class Module2_IFCRead:
    """
    Module 2: IFC Reader
    Extracts attributes and properties from IFC models using IfcOpenShell.
    """

    def __init__(self, file_path: Path | str | None = None):
        self.file_path = Path(file_path) if file_path else None
        self.ifc_file = None
        if self.file_path:
            self.load_ifc_file()

    def load_ifc_file(self):
        """Open and load the IFC file from disk."""
        if not _IFCOPENSHELL_AVAILABLE:
            raise ImportError("ifcopenshell is not installed. Run: uv add ifcopenshell")
        if not self.file_path or not self.file_path.exists():
            raise FileNotFoundError(f"IFC file not found: {self.file_path}")
        self.ifc_file = ifcopenshell.open(str(self.file_path))
        return self.ifc_file

    def get_all_elements(self, ifc_type: str = "IfcBuildingElement") -> list:
        """Return all IFC elements of the given type."""
        if not self.ifc_file:
            raise ValueError("No IFC file loaded.")
        return self.ifc_file.by_type(ifc_type)

    def _resolve_building_elements(self) -> list:
        """Return building-related elements across IFC schema variants."""
        if not self.ifc_file:
            raise ValueError("No IFC file loaded.")

        # IFC4X3 replaced IfcBuildingElement with IfcBuiltElement.
        # Keep ordered fallbacks for broad compatibility across schemas.
        type_fallbacks = ("IfcBuildingElement", "IfcBuiltElement", "IfcElement")
        for ifc_type in type_fallbacks:
            try:
                return self.ifc_file.by_type(ifc_type)
            except Exception:
                continue
        return []

    def extract_properties(self, element) -> dict:
        """Return all property sets for a single IFC element."""
        return ifcopenshell.util.element.get_psets(element)

    def extract_geometry(self) -> list[dict]:
        """Return a flat list of {id, type, properties} for all building elements."""
        if not self.ifc_file:
            raise ValueError("No IFC file loaded.")
        results = []
        for element in self._resolve_building_elements():
            results.append(
                {
                    "id": element.id(),
                    "type": element.is_a(),
                    "properties": self.extract_properties(element),
                }
            )
        return results

    def _count_by_type(self, ifc_type: str) -> int:
        """Return entity count for a type; 0 when type is unavailable in current schema."""
        if not self.ifc_file:
            raise ValueError("No IFC file loaded.")
        try:
            return len(self.ifc_file.by_type(ifc_type))
        except Exception:
            return 0

    def extract_summary_counts(
        self,
        include_openings: bool = True,
        include_spaces: bool = True,
        include_type_definitions: bool = False,
    ) -> dict:
        """Return IFC totals with optional inclusion flags for selected categories."""
        if not self.ifc_file:
            raise ValueError("No IFC file loaded.")

        built_elements = len(self._resolve_building_elements())
        all_physical_elements = self._count_by_type("IfcElement")
        all_products = self._count_by_type("IfcProduct")

        openings_count = self._count_by_type("IfcOpeningElement")
        spaces_count = self._count_by_type("IfcSpace")
        type_definitions_count = self._count_by_type("IfcElementType")

        adjusted_physical = all_physical_elements
        adjusted_products = all_products

        if not include_openings:
            adjusted_physical = max(0, adjusted_physical - openings_count)
            adjusted_products = max(0, adjusted_products - openings_count)
        if not include_spaces:
            adjusted_products = max(0, adjusted_products - spaces_count)
        if include_type_definitions:
            adjusted_products += type_definitions_count

        return {
            "built_elements": built_elements,
            "all_physical_elements": all_physical_elements,
            "all_products": all_products,
            "adjusted_physical_elements": adjusted_physical,
            "adjusted_products": adjusted_products,
            "filters": {
                "include_openings": include_openings,
                "include_spaces": include_spaces,
                "include_type_definitions": include_type_definitions,
            },
            "excluded_or_added": {
                "openings": openings_count,
                "spaces": spaces_count,
                "type_definitions": type_definitions_count,
            },
        }
