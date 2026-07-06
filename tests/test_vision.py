"""Tests for the /vision extraction endpoint (Mapping-to-Standard v2)."""
import base64
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Route
from starlette.testclient import TestClient

from ptpge_mcp import server as server_mod

IMG = base64.b64encode(b"x" * 200).decode()


def _tokens_file():
    path = tempfile.mktemp(suffix=".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"users": [{"name": "T", "status": "active", "mcp_token": "glxt_T1"}]}, fh)
    return path


def _client():
    app = Starlette(
        routes=[Route("/vision", server_mod.make_vision_endpoint(), methods=["POST", "OPTIONS"])],
        middleware=[Middleware(server_mod.CapabilityTokenMiddleware,
                               tokens_file=_tokens_file(), allow_anon=True)],
    )
    return TestClient(app, raise_server_exceptions=False)


def _fake_anthropic(payload_text):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"content": [{"type": "text", "text": payload_text}]}
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.post.return_value = resp
    return client


def test_vision_requires_token_even_in_grace():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        r = _client().post("/vision", json={"image": IMG})
    assert r.status_code == 401
    assert r.json()["error"] == "token_required"


def test_vision_extracts_with_valid_token():
    extraction = {"page_language": "en", "vendor": "helloprint",
                  "product": "Half-Fold Leaflets",
                  "selected": [{"label": "Folded size", "value": "A5 portrait"}],
                  "offered": [{"label": "Material", "values": ["90 gsm", "135 gsm"]}],
                  "quantity": "500", "notes": ""}
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}), \
         patch.object(server_mod.httpx, "Client",
                      return_value=_fake_anthropic(json.dumps(extraction))):
        r = _client().post("/vision?t=glxt_T1", json={"image": IMG, "media_type": "image/png"})
    assert r.status_code == 200
    assert r.json()["extraction"]["selected"][0]["value"] == "A5 portrait"


def test_vision_fenced_json_is_unwrapped():
    fenced = "```json\n{\"product\": \"Flyers\", \"selected\": [], \"offered\": []}\n```"
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}), \
         patch.object(server_mod.httpx, "Client", return_value=_fake_anthropic(fenced)):
        r = _client().post("/vision?t=glxt_T1", json={"image": IMG})
    assert r.status_code == 200
    assert r.json()["extraction"]["product"] == "Flyers"


def test_vision_unparseable_returns_raw():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}), \
         patch.object(server_mod.httpx, "Client", return_value=_fake_anthropic("not json")):
        r = _client().post("/vision?t=glxt_T1", json={"image": IMG})
    assert r.status_code == 200
    assert "raw" in r.json() and "extraction" not in r.json()


def test_vision_503_without_api_key():
    env = dict(os.environ); env.pop("ANTHROPIC_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        r = _client().post("/vision?t=glxt_T1", json={"image": IMG})
    assert r.status_code == 503


def test_vision_rejects_oversized_and_bad_type():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        c = _client()
        assert c.post("/vision?t=glxt_T1", json={"image": IMG, "media_type": "image/tiff"}).status_code == 400
        assert c.post("/vision?t=glxt_T1", json={"image": "x" * 8_000_001}).status_code == 413


def test_invalid_token_rejected():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        r = _client().post("/vision?t=feil", json={"image": IMG})
    assert r.status_code == 401
    assert r.json()["error"] == "invalid_token"
