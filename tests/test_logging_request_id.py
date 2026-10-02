"""Request-id propagation and log formats."""

import json
import logging

from fastapi.testclient import TestClient

from app import logging_config
from app.main import app


def test_response_carries_generated_request_id():
    resp = TestClient(app).get("/api/health")
    assert len(resp.headers["x-request-id"]) == 12


def test_incoming_request_id_is_echoed():
    resp = TestClient(app).get("/api/health", headers={"X-Request-ID": "abc-123"})
    assert resp.headers["x-request-id"] == "abc-123"


def test_overlong_request_id_is_replaced():
    resp = TestClient(app).get("/api/health", headers={"X-Request-ID": "x" * 200})
    assert resp.headers["x-request-id"] != "x" * 200


def test_records_carry_request_id_and_json_format(monkeypatch):
    monkeypatch.setenv("BIM_GUARD_LOG_FORMAT", "json")
    formatter = logging_config._build_formatter(logging.INFO)
    token = logging_config.set_request_id("rid-42")
    try:
        record = logging.LogRecord("bimguard.t", logging.INFO, __file__, 1, "hello %s", ("w",), None)
        logging_config._RequestIdFilter().filter(record)
        out = json.loads(formatter.format(record))
    finally:
        logging_config.reset_request_id(token)
    assert out["rid"] == "rid-42" and out["msg"] == "hello w" and out["level"] == "INFO"


def test_health_access_lines_are_filtered():
    f = logging_config._HealthAccessFilter()
    ok = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '127.0.0.1 - "GET /api/health HTTP/1.1" 200', (), None)
    other = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '127.0.0.1 - "GET /api/projects HTTP/1.1" 200', (), None)
    assert f.filter(ok) is False and f.filter(other) is True
