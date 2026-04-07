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

    def extract_properties(self, element) -> dict:
        """Return all property sets for a single IFC element."""
        return ifcopenshell.util.element.get_psets(element)

    def extract_geometry(self) -> list[dict]:
        """Return a flat list of {id, type, properties} for all building elements."""
        if not self.ifc_file:
            raise ValueError("No IFC file loaded.")
        results = []
        for element in self.ifc_file.by_type("IfcBuildingElement"):
            results.append(
                {
                    "id": element.id(),
                    "type": element.is_a(),
                    "properties": self.extract_properties(element),
                }
            )
        return results
