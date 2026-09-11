
from app.services.qudt_normalizer import UNIT_NAMESPACE, normalize_to_qudt


def test_normalize_recognized_units():
    # Length
    assert normalize_to_qudt(850.0, "mm") == (0.85, f"{UNIT_NAMESPACE}MilliM")
    assert normalize_to_qudt(10.0, "m") == (10.0, f"{UNIT_NAMESPACE}M")
    assert normalize_to_qudt(1.0, "in") == (0.0254, f"{UNIT_NAMESPACE}IN")
    
    # Time
    assert normalize_to_qudt(120.0, "min") == (7200.0, f"{UNIT_NAMESPACE}MIN")
    assert normalize_to_qudt(1.5, "hours") == (5400.0, f"{UNIT_NAMESPACE}HR")

def test_normalize_unrecognized_units():
    # Unrecognized unit should return the original value and None
    assert normalize_to_qudt(10.0, "lightyears") == (10.0, None)
    
def test_normalize_empty_units():
    # Empty unit should return the original value and None
    assert normalize_to_qudt(15.0, "") == (15.0, None)
    assert normalize_to_qudt(20.0, None) == (20.0, None)
