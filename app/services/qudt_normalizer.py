"""QUDT unit normalization service.

Standardizes units from varying sources (e.g., metric, imperial, time scales)
into W3C QUDT SI base units. This aligns custom regulatory rule bounds with
the canonical units stored in the semantic graph.
"""

from typing import Optional, Tuple

QUDT_NAMESPACE = "http://qudt.org/schema/qudt/"
UNIT_NAMESPACE = "http://qudt.org/vocab/unit/"

# Maps common unit strings to (conversion_factor_to_SI, SI_QUDT_Unit_URI).
# The factor is what we multiply the raw value by to get the SI value, and
# the URI names THAT SI value's unit -- e.g. "mm" -> (0.001, unit:M), never
# unit:MilliM, since the paired numeric value returned by normalize_to_qudt()
# is already in meters. Pairing the SI value with its SOURCE unit's URI would
# make the two disagree by orders of magnitude for any non-1.0 factor.
_UNIT_TABLE = {
    # Length -> SI: unit:M (meters)
    "mm": (0.001, f"{UNIT_NAMESPACE}M"),
    "millimeter": (0.001, f"{UNIT_NAMESPACE}M"),
    "millimeters": (0.001, f"{UNIT_NAMESPACE}M"),
    "cm": (0.01, f"{UNIT_NAMESPACE}M"),
    "centimeter": (0.01, f"{UNIT_NAMESPACE}M"),
    "centimeters": (0.01, f"{UNIT_NAMESPACE}M"),
    "m": (1.0, f"{UNIT_NAMESPACE}M"),
    "meter": (1.0, f"{UNIT_NAMESPACE}M"),
    "meters": (1.0, f"{UNIT_NAMESPACE}M"),
    "in": (0.0254, f"{UNIT_NAMESPACE}M"),
    "inch": (0.0254, f"{UNIT_NAMESPACE}M"),
    "inches": (0.0254, f"{UNIT_NAMESPACE}M"),
    "ft": (0.3048, f"{UNIT_NAMESPACE}M"),
    "foot": (0.3048, f"{UNIT_NAMESPACE}M"),
    "feet": (0.3048, f"{UNIT_NAMESPACE}M"),

    # Time -> SI: unit:SEC (seconds)
    "s": (1.0, f"{UNIT_NAMESPACE}SEC"),
    "sec": (1.0, f"{UNIT_NAMESPACE}SEC"),
    "second": (1.0, f"{UNIT_NAMESPACE}SEC"),
    "seconds": (1.0, f"{UNIT_NAMESPACE}SEC"),
    "min": (60.0, f"{UNIT_NAMESPACE}SEC"),
    "minute": (60.0, f"{UNIT_NAMESPACE}SEC"),
    "minutes": (60.0, f"{UNIT_NAMESPACE}SEC"),
    "h": (3600.0, f"{UNIT_NAMESPACE}SEC"),
    "hr": (3600.0, f"{UNIT_NAMESPACE}SEC"),
    "hour": (3600.0, f"{UNIT_NAMESPACE}SEC"),
    "hours": (3600.0, f"{UNIT_NAMESPACE}SEC"),

    # Area -> SI: unit:M2 (square meters)
    "m2": (1.0, f"{UNIT_NAMESPACE}M2"),
    "sqm": (1.0, f"{UNIT_NAMESPACE}M2"),
    "mm2": (0.000001, f"{UNIT_NAMESPACE}M2"),

    # Mass -> SI: unit:KiloGM (kilograms)
    "kg": (1.0, f"{UNIT_NAMESPACE}KiloGM"),
    "g": (0.001, f"{UNIT_NAMESPACE}KiloGM"),
    "gram": (0.001, f"{UNIT_NAMESPACE}KiloGM"),
    "grams": (0.001, f"{UNIT_NAMESPACE}KiloGM"),
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
