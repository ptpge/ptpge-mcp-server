"""/agent/status and /agent/messages — the sponsored-run proxy (0.34.0). No network: the upstream call is monkeypatched."""
from __future__ import annotations

import json
import pytest
from starlette.testclient import TestClient

from ptpge_mcp import agent as A
from ptpge_mcp.server import build_app

SYSTEM = A.AGENT_MARKER + " test"
TOOLS = [{"name": "ptpge_search_terms", "description": "x", "input_schema": {"type": "object"}}]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PTPGE_AGENT_STORE", str(tmp_path / "usage.json"))
    monkeypatch.setenv("PTPGE_AGENT_PER_IP", "2")
    monkeypatch.setenv("PTPGE_AGENT_MAX_ROUNDS", "3")
    return TestClient(build_app())


def _fake_upstream(monkeypatch):
    class R:
        def __init__(self): self._b = json.dumps({"content": [{"type": "text", "text": "hi"}], "stop_reason": "end_turn", "usage": {"input_tokens": 10, "output_tokens": 2}}).encode()
        def read(self): return self._b
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(A.urllib.request, "urlopen", lambda req, timeout=60: R())


def test_status_off_without_key(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    j = client.get("/agent/status").json()
    assert j["enabled"] is False and j["paid_by"] == "PTPGE" and j["per_ip"] == 2


def test_messages_503_without_key(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = client.post("/agent/messages", json={"system": SYSTEM, "messages": [{"role": "user", "content": "x"}], "tools": TOOLS})
    assert r.status_code == 503


def test_marker_and_tools_are_enforced(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    r = client.post("/agent/messages", json={"system": "no marker", "messages": [{"role": "user", "content": "x"}], "tools": TOOLS})
    assert r.status_code == 400
    r = client.post("/agent/messages", json={"system": SYSTEM, "messages": [{"role": "user", "content": "x"}], "tools": [{"name": "other_tool"}]})
    assert r.status_code == 400


def test_runs_counted_per_ip_and_rounds_per_run(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    _fake_upstream(monkeypatch)
    body = {"system": SYSTEM, "messages": [{"role": "user", "content": "x"}], "tools": TOOLS}
    r = client.post("/agent/messages", json=body, headers={"X-Agent-Run": "run-a"})
    assert r.status_code == 200 and r.json()["_sponsored"]["paid_by"] == "PTPGE" and r.json()["_sponsored"]["remaining_today"] == 1
    for _ in range(2):  # same run: rounds, not runs
        assert client.post("/agent/messages", json=body, headers={"X-Agent-Run": "run-a"}).status_code == 200
    assert client.post("/agent/messages", json=body, headers={"X-Agent-Run": "run-a"}).status_code == 429  # 4th round > 3
    assert client.post("/agent/messages", json=body, headers={"X-Agent-Run": "run-b"}).status_code == 200  # 2nd run
    assert client.post("/agent/messages", json=body, headers={"X-Agent-Run": "run-c"}).status_code == 429  # 3rd run > per_ip 2
    assert client.get("/agent/status").json()["remaining_today"] == 0


def test_cors_preflight(client):
    r = client.options("/agent/messages", headers={"Origin": "https://ptpge.org"})
    assert r.status_code == 204 and r.headers["access-control-allow-origin"] == "https://ptpge.org"
