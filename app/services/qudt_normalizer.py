"""QUDT unit normalization service.

Standardizes units from varying sources (e.g., metric, imperial, time scales)
into W3C QUDT SI base units. This aligns custom regulatory rule bounds with
the canonical units stored in the semantic graph.
"""

from typing import Optional, Tuple

QUDT_NAMESPACE = "http://qudt.org/schema/qudt/"
UNIT_NAMESPACE = "http://qudt.org/vocab/unit/"

# Maps common unit strings to their (conversion_factor_to_SI, QUDT_Unit_URI)
# The conversion factor is what we multiply the raw value by to get the SI value.
_UNIT_TABLE = {
    # Length -> SI: unit:M (meters)
    "mm": (0.001, f"{UNIT_NAMESPACE}MilliM"),
    "millimeter": (0.001, f"{UNIT_NAMESPACE}MilliM"),
    "millimeters": (0.001, f"{UNIT_NAMESPACE}MilliM"),
    "cm": (0.01, f"{UNIT_NAMESPACE}CentiM"),
    "centimeter": (0.01, f"{UNIT_NAMESPACE}CentiM"),
    "centimeters": (0.01, f"{UNIT_NAMESPACE}CentiM"),
    "m": (1.0, f"{UNIT_NAMESPACE}M"),
    "meter": (1.0, f"{UNIT_NAMESPACE}M"),
    "meters": (1.0, f"{UNIT_NAMESPACE}M"),
    "in": (0.0254, f"{UNIT_NAMESPACE}IN"),
    "inch": (0.0254, f"{UNIT_NAMESPACE}IN"),
    "inches": (0.0254, f"{UNIT_NAMESPACE}IN"),
    "ft": (0.3048, f"{UNIT_NAMESPACE}FT"),
    "foot": (0.3048, f"{UNIT_NAMESPACE}FT"),
    "feet": (0.3048, f"{UNIT_NAMESPACE}FT"),

    # Time -> SI: unit:SEC (seconds)
    "s": (1.0, f"{UNIT_NAMESPACE}SEC"),
    "sec": (1.0, f"{UNIT_NAMESPACE}SEC"),
    "second": (1.0, f"{UNIT_NAMESPACE}SEC"),
    "seconds": (1.0, f"{UNIT_NAMESPACE}SEC"),
    "min": (60.0, f"{UNIT_NAMESPACE}MIN"),
    "minute": (60.0, f"{UNIT_NAMESPACE}MIN"),
    "minutes": (60.0, f"{UNIT_NAMESPACE}MIN"),
    "h": (3600.0, f"{UNIT_NAMESPACE}HR"),
    "hr": (3600.0, f"{UNIT_NAMESPACE}HR"),
    "hour": (3600.0, f"{UNIT_NAMESPACE}HR"),
    "hours": (3600.0, f"{UNIT_NAMESPACE}HR"),

    # Area -> SI: unit:M2 (square meters)
    "m2": (1.0, f"{UNIT_NAMESPACE}M2"),
    "sqm": (1.0, f"{UNIT_NAMESPACE}M2"),
    "mm2": (0.000001, f"{UNIT_NAMESPACE}MilliM2"),
    
    # Mass -> SI: unit:KiloGM (kilograms)
    "kg": (1.0, f"{UNIT_NAMESPACE}KiloGM"),
    "g": (0.001, f"{UNIT_NAMESPACE}GM"),
    "gram": (0.001, f"{UNIT_NAMESPACE}GM"),
    "grams": (0.001, f"{UNIT_NAMESPACE}GM"),
}


def normalize_to_qudt(value: float, unit: str) -> Tuple[float, Optional[str]]:
    """Normalize a numerical value to its SI base unit representation.
    
    Args:
        value: The numerical threshold.
        unit: The unit string provided by the rule or extraction (e.g. "mm").
        
    Returns:
        A tuple of (si_value, qudt_unit_uri).
        If the unit is not recognized, it returns the original value and None.
    """
    if not unit:
        return float(value), None

    unit_lower = unit.strip().lower()
    
    if unit_lower in _UNIT_TABLE:
        factor, uri = _UNIT_TABLE[unit_lower]
        # Calculate the SI value (e.g. 850 mm -> 850 * 0.001 = 0.85 m)
        return float(value) * factor, uri
        
    # Unrecognized units are left unaltered.
    return float(value), None
