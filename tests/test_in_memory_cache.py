"""Unit and integration tests for the in-memory TTLCache implementation."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.cache import (
    cache_db_query,
    cache_stats,
    clear_cache,
    invalidate_cache,
    local_cache,
)
from app.services.projects_service import ProjectsService
from app.services.rules_service import RulesService


@pytest.fixture(autouse=True)
def _reset_cache():
    """Reset the global cache before and after every test."""
    clear_cache()
    yield
    clear_cache()


def test_cache_hit_and_miss():
    """Verify decorated sync functions cache results and increment stats."""
    call_count = 0

    @cache_db_query(key_prefix="test:query")
    def fetch_data(item_id: int) -> dict:
        nonlocal call_count
        call_count += 1
        return {"id": item_id, "name": f"item_{item_id}"}

    first = fetch_data(42)
    assert first == {"id": 42, "name": "item_42"}
    assert call_count == 1

    # Second call should hit local RAM cache
    second = fetch_data(42)
    assert second == {"id": 42, "name": "item_42"}
    assert call_count == 1

    stats = cache_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["size"] == 1


@pytest.mark.anyio
async def test_cache_async_coroutine():
    """Verify decorated async functions cache results properly."""
    call_count = 0

    @cache_db_query(key_prefix="test:async")
    async def fetch_async(user_id: str) -> dict:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return {"user": user_id}

    r1 = await fetch_async("alice")
    r2 = await fetch_async("alice")
    assert r1 == r2 == {"user": "alice"}
    assert call_count == 1

    stats = cache_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1


def test_cache_invalidation_exact_and_prefix():
    """Verify invalidate_cache supports both exact keys and prefix patterns."""
    call_count = 0

    @cache_db_query(key_prefix="bimguard:entity")
    def get_entity(pk: int):
        nonlocal call_count
        call_count += 1
        return {"pk": pk}

    get_entity(1)
    get_entity(2)
    assert call_count == 2
    assert "bimguard:entity:pk=1" in local_cache
    assert "bimguard:entity:pk=2" in local_cache

    # Invalidate exact key
    evicted = invalidate_cache("bimguard:entity:pk=1")
    assert evicted >= 1
    assert "bimguard:entity:pk=1" not in local_cache
    assert "bimguard:entity:pk=2" in local_cache

    # Re-call pk=1 triggers call, pk=2 hits cache
    get_entity(1)
    assert call_count == 3
    get_entity(2)
    assert call_count == 3

    # Invalidate all under prefix
    evicted_prefix = invalidate_cache("bimguard:entity")
    assert evicted_prefix >= 2
    assert len(local_cache) == 0


def test_concurrent_access_thread_safety():
    """Verify concurrent reads and writes across threads do not corrupt the cache."""

    @cache_db_query(key_prefix="test:concurrent")
    def compute(val: int) -> int:
        return val * 2

    def worker(val: int):
        for _ in range(50):
            res = compute(val)
            assert res == val * 2
            if val % 2 == 0:
                invalidate_cache(f"test:concurrent:val={val}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(worker, i) for i in range(20)]
        for f in futures:
            f.result()

    assert cache_stats()["size"] >= 0


def test_projects_service_caching_and_invalidation():
    """Verify ProjectsService reads are cached and invalidated upon updates."""
    service = ProjectsService()
    p = service.create_project(
        name="Cache Test Project",
        description="Cache verification",
        country="Canada",
        analysis_type="Arch",
    )

    project_id = p["id"]

    try:
        # First read - misses cache
        p1 = service.get_project(project_id)
        assert p1["name"] == "Cache Test Project"

        # Check key in cache
        key = f"bimguard:projects:item:project_id={project_id}"
        assert key in local_cache

        # Update project - invalidates old cache and get_project re-populates with updated data
        updated = service.update_project(
            project_id=project_id,
            name="Updated Cache Project",
            description="Updated description",
        )
        assert updated["name"] == "Updated Cache Project"
        # Cache now holds the updated project
        assert local_cache[key]["name"] == "Updated Cache Project"

        # Explicit invalidation removes it
        invalidate_cache(key)
        assert key not in local_cache

        # Re-fetch returns updated project and re-populates cache
        p2 = service.get_project(project_id)
        assert p2["name"] == "Updated Cache Project"
        assert key in local_cache
    finally:
        service.delete_project(project_id)
        assert f"bimguard:projects:item:project_id={project_id}" not in local_cache


def test_rules_service_caching_and_invalidation():
    """Verify RulesService queries are cached and wiped on rule mutations."""
    rules_svc = RulesService()

    rule = rules_svc.create_rule(
        reference="CACHE-TEST-001",
        rule_type="numeric_comparison",
        description="Cache rule test",
        target_ifc_class="IfcWall",
        mechanism="GC-001",
        ruleset_id="TEST-CACHE-RULESET",
    )
    rule_id = rule["id"]

    try:
        # Read through service
        r1 = rules_svc.get_rule(rule_id)
        assert r1["reference"] == "CACHE-TEST-001"
        assert f"bimguard:rules:item:rule_id={rule_id}" in local_cache

        # Summary query should be cached
        _ = rules_svc.summary()
        assert "bimguard:rules:summary" in local_cache


        # Delete rule - must invalidate rules cache
        rules_svc.delete_rule(rule_id)
        assert f"bimguard:rules:item:rule_id={rule_id}" not in local_cache
        assert "bimguard:rules:summary" not in local_cache
    finally:
        # Cleanup in case delete_rule failed
        if rules_svc.get_rule(rule_id) is not None:
            rules_svc.delete_rule(rule_id)
