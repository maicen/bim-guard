import time
import urllib.error
from unittest.mock import MagicMock, patch

from app.services.bsdd_client import BSDDClient
from app.services.bsdd_ontology_repository import BSDDOntologyRepository


def test_bsdd_outage_fallback_performance():
    """Verify bSDD outage fallback happens within 500ms target."""
    # 1. Setup mock repository that skips the expensive DB full-refresh
    repo = BSDDOntologyRepository(db=MagicMock())
    repo._refresh_if_stale = MagicMock()
    repo._classes_by_uri = {}  # force cache miss
    
    client = BSDDClient(enable_network=True, timeout_seconds=0.4)
    
    start_time = time.time()
    
    # 2. Mock network to raise a timeout (e.g. socket timeout converted to URLError)
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.URLError("timed out")
        
        # 3. Request class that doesn't exist locally
        result = repo.get_class_cached(
            client, 
            "https://identifier.buildingsmart.org/uri/buildingsmart/ifc-4.3", 
            "IfcPipeSegment"
        )
        
    duration_ms = (time.time() - start_time) * 1000
    
    # 4. Assert fallback returns the offline built-in class in <500ms
    assert result is not None
    assert result.code == "IfcPipeSegment"
    assert duration_ms <= 500.0


def test_bsdd_local_runtime_cache(tmp_path):
    """Verify that BSDDOntologyRepository persists runtime classes directly to local JSON without any database."""
    from app.modules.contracts import BSDDClassItem, BSDDPropertyItem

    repo = BSDDOntologyRepository()
    repo._cache_dir = tmp_path / "cache" / "bsdd"

    test_item = BSDDClassItem(
        uri="https://identifier.buildingsmart.org/uri/test/dict/1.0/class/CustomSensor",
        code="CustomSensor",
        name="Custom Sensor",
        dictionary_uri="https://identifier.buildingsmart.org/uri/test/dict/1.0",
        class_type="Class",
        properties=[
            BSDDPropertyItem(
                uri="https://identifier.buildingsmart.org/uri/test/dict/1.0/prop/BatteryLife",
                name="BatteryLife",
                property_set="Pset_SensorCommon",
                data_type="IfcTimeMeasure",
                units="year",
            )
        ],
    )

    # Persist the item locally
    repo.persist_class(test_item)

    # Verify JSON files exist on disk
    runtime_classes_file = repo._cache_dir / "runtime_classes.json"
    runtime_props_file = repo._cache_dir / "runtime_properties.json"
    runtime_edges_file = repo._cache_dir / "runtime_class_properties.json"

    assert runtime_classes_file.exists()
    assert runtime_props_file.exists()
    assert runtime_edges_file.exists()

    # Create a fresh repository pointing to the same cache directory
    fresh_repo = BSDDOntologyRepository()
    fresh_repo._cache_dir = repo._cache_dir
    fresh_repo._refresh_if_stale()

    # Assert class was reloaded into memory from local JSON cache
    cached_class = fresh_repo.get_class_by_uri(test_item.uri)
    assert cached_class is not None
    assert cached_class.code == "CustomSensor"
    assert len(cached_class.properties) == 1
    assert cached_class.properties[0].name == "BatteryLife"

