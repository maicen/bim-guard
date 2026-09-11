import time
import urllib.error
from unittest.mock import patch, MagicMock

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
