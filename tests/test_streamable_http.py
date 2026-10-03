"""Tests for the Streamable HTTP transport (v0.3.0) — stateless JSON mode.

These exercise the pure JSON-RPC layer (handle_jsonrpc_message / tool_payload)
with a fake cache, so they run without network access or a live app.
"""

import json

from ptpge_mcp import __version__
from ptpge_mcp.server import (
    LATEST_PROTOCOL_VERSION,
    handle_jsonrpc_message,
    negotiate_protocol_version,
    tool_payload,
)


class FakeCache:
    """Minimal stand-in for VocabularyCache."""

    version = {
        "version": "2026-06-04",
        "apiVersion": "1.0.0",
        "terms": 708,
        "by_level": {"element": 525},
        "by_group": {"configurations": 136},
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "scheme_url": "https://api.ptpge.org/v1/scheme",
    }

    def search(self, query, limit, groups, language):
        return [{"uri": "https://ptpge.org/v1/printing/configurations/formats/a-series/a4",
                 "notation": "P:CF§A4", "score": 1.0}]

    def get_term(self, id_or_path):
        if "a4" in id_or_path:
            return {"id": "https://ptpge.org/v1/printing/configurations/formats/a-series/a4",
                    "label": {"en": "A4", "nb": "A4"}}
        return None


def _req(method, msg_id=1, params=None):
    msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


# --------------------------------------------------------------------------
# Protocol negotiation
# --------------------------------------------------------------------------

def test_negotiate_known_version_is_echoed():
    assert negotiate_protocol_version("2025-03-26") == "2025-03-26"


def test_negotiate_unknown_version_falls_back_to_latest():
    assert negotiate_protocol_version("2099-01-01") == LATEST_PROTOCOL_VERSION
    assert negotiate_protocol_version(None) == LATEST_PROTOCOL_VERSION


# --------------------------------------------------------------------------
# Handshake + discovery
# --------------------------------------------------------------------------

def test_initialize():
    resp = handle_jsonrpc_message(FakeCache(), _req(
        "initialize", params={"protocolVersion": "2025-06-18",
                              "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}))
    assert resp["id"] == 1
    result = resp["result"]
    assert result["protocolVersion"] == "2025-06-18"
    assert result["serverInfo"]["version"] == __version__
    assert "tools" in result["capabilities"]


def test_initialized_notification_gets_no_response():
    msg = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    assert handle_jsonrpc_message(FakeCache(), msg) is None


def test_ping():
    resp = handle_jsonrpc_message(FakeCache(), _req("ping"))
    assert resp["result"] == {}


def test_tools_list_exposes_all_nine_tools():
    resp = handle_jsonrpc_message(FakeCache(), _req("tools/list"))
    names = {t["name"] for t in resp["result"]["tools"]}
    assert names == {
        "ptpge_search_terms", "ptpge_get_term", "ptpge_get_version",
        "ptpge_browse", "ptpge_get_product_envelope",
        "ptpge_validate_config", "ptpge_fingerprint",
        "ptpge_resolve_color_notation",          # SD-0071
        "ptpge_expand_fingerprint",              # 0.25.0 — read-back over MCP
    }
    # inputSchema must survive serialisation (camelCase alias)
    assert all("inputSchema" in t for t in resp["result"]["tools"])


def test_empty_resources_and_prompts():
    assert handle_jsonrpc_message(FakeCache(), _req("resources/list"))["result"] == {"resources": []}
    assert handle_jsonrpc_message(FakeCache(), _req("prompts/list"))["result"] == {"prompts": []}


# --------------------------------------------------------------------------
# tools/call
# --------------------------------------------------------------------------

def test_call_get_version():
    resp = handle_jsonrpc_message(FakeCache(), _req(
        "tools/call", params={"name": "ptpge_get_version", "arguments": {}}))
    result = resp["result"]
    assert result["isError"] is False
    payload = json.loads(result["content"][0]["text"])
    assert payload["dataVersion"] == "2026-06-04"
    assert payload["serverVersion"] == __version__


def test_call_search():
    resp = handle_jsonrpc_message(FakeCache(), _req(
        "tools/call", params={"name": "ptpge_search_terms", "arguments": {"query": "a4"}}))
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["count"] == 1


def test_call_get_term_not_found_is_payload_not_error():
    resp = handle_jsonrpc_message(FakeCache(), _req(
        "tools/call", params={"name": "ptpge_get_term", "arguments": {"id_or_path": "nope"}}))
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["error"] == "not_found"
    assert resp["result"]["isError"] is False


def test_call_unknown_tool_is_invalid_params():
    resp = handle_jsonrpc_message(FakeCache(), _req(
        "tools/call", params={"name": "bogus", "arguments": {}}))
    assert resp["error"]["code"] == -32602


def test_tool_execution_error_becomes_isError_result():
    class ExplodingCache(FakeCache):
        def search(self, **kwargs):
            raise RuntimeError("boom")

    resp = handle_jsonrpc_message(ExplodingCache(), _req(
        "tools/call", params={"name": "ptpge_search_terms", "arguments": {"query": "x"}}))
    assert resp["result"]["isError"] is True


# --------------------------------------------------------------------------
# Error handling
# --------------------------------------------------------------------------

def test_unknown_method():
    resp = handle_jsonrpc_message(FakeCache(), _req("nonsense/method"))
    assert resp["error"]["code"] == -32601


def test_invalid_message():
    resp = handle_jsonrpc_message(FakeCache(), {"not": "jsonrpc"})
    assert resp["error"]["code"] == -32600


def test_tool_payload_localizes_term():
    payload = tool_payload(FakeCache(), "ptpge_get_term",
                           {"id_or_path": "printing/.../a4", "language": "nb"})
    assert payload["label"] == "A4"
    assert payload["label_all"] == {"en": "A4", "nb": "A4"}


# --------------------------------------------------------------------------
# ETag validation (MCP roadmap: HTTP-Native Transport Unification)
# --------------------------------------------------------------------------

def test_etag_is_stable_for_the_same_request_and_dataset():
    from ptpge_mcp.server import _result_etag
    reply = handle_jsonrpc_message(FakeCache(), _req("tools/list"))
    a = _result_etag(FakeCache(), "tools/list", reply)
    b = _result_etag(FakeCache(), "tools/list", reply)
    assert a and a == b
    assert a.startswith('"') and a.endswith('"')      # strong validator


def test_etag_ignores_the_jsonrpc_id():
    """The id identifies the call, not the answer."""
    from ptpge_mcp.server import _result_etag
    r1 = handle_jsonrpc_message(FakeCache(), _req("tools/list", msg_id=1))
    r2 = handle_jsonrpc_message(FakeCache(), _req("tools/list", msg_id=99))
    assert r1["id"] != r2["id"]
    assert _result_etag(FakeCache(), "tools/list", r1) == \
           _result_etag(FakeCache(), "tools/list", r2)


def test_etag_changes_when_the_dataset_changes():
    from ptpge_mcp.server import _result_etag

    class Newer(FakeCache):
        version = dict(FakeCache.version, generated="2026-08-27T14:00:00+02:00")

    reply = handle_jsonrpc_message(FakeCache(), _req("tools/list"))
    assert _result_etag(FakeCache(), "tools/list", reply) != \
           _result_etag(Newer(), "tools/list", reply)


def test_no_etag_for_errors_or_uncacheable_methods():
    from ptpge_mcp.server import _result_etag
    err = handle_jsonrpc_message(FakeCache(), _req("no/such/method"))
    assert _result_etag(FakeCache(), "no/such/method", err) is None
    ok = handle_jsonrpc_message(FakeCache(), _req("tools/list"))
    assert _result_etag(FakeCache(), "ping", ok) is None


def test_if_none_match_parsing():
    from ptpge_mcp.server import _if_none_match
    assert _if_none_match('"abc"', '"abc"')
    assert _if_none_match('"x", "abc" , "y"', '"abc"')
    assert _if_none_match("*", '"abc"')
    assert not _if_none_match('"other"', '"abc"')
    assert not _if_none_match(None, '"abc"')
    assert not _if_none_match("", '"abc"')


def test_mcp_cors_preflight_and_headers():
    """0.28.8 — a browser on another origin (trykkverk.no/prompt/) may call /mcp."""
    import os, pytest
    from starlette.testclient import TestClient
    from ptpge_mcp import server as srv
    os.environ.setdefault("PTPGE_API_BASE", "https://internal.ptpge.org/v1")   # the open mirror — no credentials
    os.environ.setdefault("PTPGE_LEARNING_FILE", "")
    try:
        app = srv.build_app()
    except Exception as e:  # no network in this sandbox → skip, the unit tests above still cover the handler
        pytest.skip(f"live vocabulary not reachable: {e}")
    c = TestClient(app)
    r = c.options("/mcp", headers={"Origin": "https://trykkverk.no", "Access-Control-Request-Method": "POST"})
    assert r.status_code == 204
    assert r.headers.get("access-control-allow-origin") == "*"
    r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers={"Origin": "https://trykkverk.no"})
    assert r.status_code == 200 and r.headers.get("access-control-allow-origin") == "*"
    assert "tools" in r.json()["result"]
