"""
tests/conftest.py
------------------
Shared fixtures and pytest configuration for all BIMGuard tests.
"""

import os
import sys

import pytest

# Test modules use bare imports (e.g. `from document_parsing...`) written for
# `python -m tests.x` run with cwd=app/modules/, while some of those modules in
# turn use absolute imports (e.g. `from app.services...`) that need the repo
# root on sys.path instead. Add both so either style resolves under pytest,
# regardless of the cwd pytest itself was invoked from.
_MODULES_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(os.path.dirname(_MODULES_DIR))
sys.path.insert(0, _MODULES_DIR)
sys.path.insert(0, _REPO_ROOT)

# ═══════════════════════════════════════════════════════════════════════════════
# Register custom markers so pytest doesn't warn about them
# ═══════════════════════════════════════════════════════════════════════════════


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests that need real PDFs and are slow")
    config.addinivalue_line("markers", "llm: marks tests that call the LLM (slow, costs tokens)")
    config.addinivalue_line("markers", "integration: marks end-to-end pipeline tests")


# ═══════════════════════════════════════════════════════════════════════════════
# Shared paths
# ═══════════════════════════════════════════════════════════════════════════════

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), "snapshots")


@pytest.fixture(scope="session", autouse=True)
def ensure_directories():
    """Create test output directories if they don't exist."""
    for d in [FIXTURES_DIR, SNAPSHOTS_DIR]:
        os.makedirs(d, exist_ok=True)
