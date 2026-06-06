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


def test_tools_list_exposes_all_seven_tools():
    resp = handle_jsonrpc_message(FakeCache(), _req("tools/list"))
    names = {t["name"] for t in resp["result"]["tools"]}
    assert names == {
        "ptpge_search_terms", "ptpge_get_term", "ptpge_get_version",
        "ptpge_browse", "ptpge_get_product_envelope",
        "ptpge_validate_config", "ptpge_fingerprint",
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
