"""ptpge_check_domain / check.py — offline tests with a fake HTTP layer.

The real check talks to the domain and to ptpge.org; here every GET is
served from a dict so the logic (steps, verdict, missing) is tested
without the network. Schemas come from the repo next door when present,
otherwise the test is skipped.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ptpge_mcp import check as C

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"
FIX = ROOT / "tests" / "fixtures"
pytestmark = pytest.mark.skipif(not (SCHEMAS / "vendor-declaration-1.schema.json").exists(), reason="schemas not next door")


class FakeCache:
    """Enough of VocabularyCache for the check: get_term by URI."""
    def __init__(self, terms: dict[str, dict]):
        self._t = terms
    def get_term(self, uri):
        return self._t.get(uri)


def _vocab_from_fixture(*docs) -> FakeCache:
    """Every term URI in the fixtures exists; products are product templates; variables are elements."""
    terms = {}
    for d in docs:
        for _, uri in C._iter_term_uris(d):
            if uri.startswith(C.TERM_PREFIX + ("vendors/", "suppliers/", "schemas/")[0]) or "/vendors/" in uri or "/suppliers/" in uri or "/schemas/" in uri:
                continue
            t = {"id": uri, "prefLabel": {"en": uri.rsplit("/", 1)[-1].replace("-", " ").title()}, "status": "active"}
            if "/ordering/products/" in uri:
                t["elementType"] = "product"
            if "/variables/" in uri:
                t["level"] = "element"
            terms[uri] = t
    return FakeCache(terms)


def _transport(routes: dict[str, object]):
    """httpx MockTransport: url → dict (200 JSON) | int (status) | str (200 non-JSON)."""
    def handler(req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        if url.startswith(C.SCHEMA_BASE):
            name = url[len(C.SCHEMA_BASE):].replace("/", "-")          # vendor-declaration/1.schema.json → vendor-declaration-1.schema.json
            f = SCHEMAS / name
            return httpx.Response(200, json=json.loads(f.read_text("utf-8"))) if f.exists() else httpx.Response(404)
        v = routes.get(url)
        if v is None:
            return httpx.Response(404)
        if isinstance(v, int):
            return httpx.Response(v)
        if isinstance(v, str):
            return httpx.Response(200, text=v)
        return httpx.Response(200, json=v)
    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def _patch_client(monkeypatch):
    """Each test sets `routes`; _client() returns a client over the mock transport."""
    state = {"routes": {}}
    monkeypatch.setattr(C, "_client", lambda: httpx.Client(transport=_transport(state["routes"]), follow_redirects=True))
    C._schema_cache.clear()
    yield state


def _trykkverk():
    decl = json.loads((FIX / "vendor-declaration-trykkverk-norge.json").read_text("utf-8"))
    man = json.loads((FIX / "ucp-manifest-trykkverk.json").read_text("utf-8"))
    return decl, man


def test_ready_domain(_patch_client):
    decl, man = _trykkverk()
    host = decl["domain"]
    _patch_client["routes"] = {
        f"https://{host}/.well-known/ucp": man,
        f"https://{host}/.well-known/ptpge/declaration.json": decl,
        decl["identity"].replace("https://ptpge.org/", "https://api.ptpge.org/") + ".jsonld": {"id": decl["identity"], "domain": host, "name": decl["name"]},
    }
    r = C.check_domain(host, _vocab_from_fixture(decl, man))
    assert r["verdict"] == "ready", r
    assert [s["status"] for s in r["steps"]] == ["ok", "ok", "ok", "skip"]
    assert r["agentSees"]["name"] == decl["name"]
    assert r["agentSees"]["productCount"] == len(decl["offerings"])
    assert r["missing"] == []


def test_nothing_found(_patch_client):
    _patch_client["routes"] = {}
    r = C.check_domain("example.org", FakeCache({}))
    assert r["verdict"] == "none"
    assert r["steps"][0]["status"] == "fail" and r["steps"][1]["status"] == "fail"
    assert r["steps"][2]["status"] == "skip"
    assert {m["what"][:5] for m in r["missing"]} == {"A UCP", "A ven"}


def test_manifest_without_ptpge_block_is_partial(_patch_client):
    decl, man = _trykkverk()
    host = decl["domain"]
    _patch_client["routes"] = {
        f"https://{host}/.well-known/ucp": {"ucp": man["ucp"]},
        f"https://{host}/.well-known/ptpge/declaration.json": decl,
        decl["identity"].replace("https://ptpge.org/", "https://api.ptpge.org/") + ".jsonld": {"domain": host},
    }
    r = C.check_domain(host, _vocab_from_fixture(decl, man))
    assert r["verdict"] == "partial"
    assert r["steps"][0]["status"] == "warn"
    assert any("ptpge` block" in m["what"] for m in r["missing"])


def test_invalid_declaration_reports_schema_errors(_patch_client):
    decl, man = _trykkverk()
    host = decl["domain"]
    bad = dict(decl); bad.pop("capability")
    _patch_client["routes"] = {
        f"https://{host}/.well-known/ucp": man,
        f"https://{host}/.well-known/ptpge/declaration.json": bad,
    }
    r = C.check_domain(host, _vocab_from_fixture(decl, man))
    assert r["verdict"] == "partial"
    s = r["steps"][1]
    assert s["status"] == "fail" and any("capability" in e for e in s["errors"])
    assert r["steps"][2]["status"] == "ok" or r["steps"][2]["status"] == "fail"  # identity from manifest still checked


def test_unknown_term_is_an_error(_patch_client):
    decl, man = _trykkverk()
    host = decl["domain"]
    _patch_client["routes"] = {
        f"https://{host}/.well-known/ucp": man,
        f"https://{host}/.well-known/ptpge/declaration.json": decl,
        decl["identity"].replace("https://ptpge.org/", "https://api.ptpge.org/") + ".jsonld": {"domain": host},
    }
    vocab = _vocab_from_fixture(decl, man)
    dropped = decl["capability"]["technologies"][0]
    del vocab._t[dropped]
    r = C.check_domain(host, vocab)
    assert r["steps"][1]["status"] == "fail"
    assert any("unknown term" in e for e in r["steps"][1]["errors"])


def test_register_pointing_elsewhere_fails_identity(_patch_client):
    decl, man = _trykkverk()
    host = decl["domain"]
    _patch_client["routes"] = {
        f"https://{host}/.well-known/ucp": man,
        f"https://{host}/.well-known/ptpge/declaration.json": decl,
        decl["identity"].replace("https://ptpge.org/", "https://api.ptpge.org/") + ".jsonld": {"domain": "someone-else.example"},
    }
    r = C.check_domain(host, _vocab_from_fixture(decl, man))
    assert r["steps"][2]["status"] == "fail"
    assert r["verdict"] == "partial"


def test_supplier_catalogue_is_validated(_patch_client):
    cat = json.loads((FIX / "supplier-catalogue-lessebo.json").read_text("utf-8"))
    host = cat["domain"]
    _patch_client["routes"] = {f"https://{host}/.well-known/ptpge/catalogue.json": cat}
    r = C.check_domain(host, _vocab_from_fixture(cat))
    s = r["steps"][3]
    assert s["status"] == "ok", s
    assert r["agentSees"]["catalogueItems"] == len(cat["items"])


@pytest.mark.parametrize("raw,want", [
    ("trykkverk.no", "trykkverk.no"), ("https://www.Trykkverk.no/shop", "trykkverk.no"),
    ("TRYKKVERK.NO:443", "trykkverk.no"), ("not a domain", None), ("localhost", None), ("", None),
])
def test_normalise_domain(raw, want):
    assert C.normalise_domain(raw) == want


def test_tool_dispatch_routes_to_check(monkeypatch):
    from ptpge_mcp import server as S
    monkeypatch.setattr(C, "check_domain", lambda d, cache, document=None: {"domain": d, "verdict": "none", "document": document})
    assert S.tool_payload(None, "ptpge_check_domain", {"domain": "x.example"})["verdict"] == "none"
    assert S.tool_payload(None, "ptpge_check_domain", {"domain": "x.example", "document": "https://h/x.json"})["document"] == "https://h/x.json"


def test_supplier_only_domain_is_maker_ready(_patch_client):
    cat = json.loads((FIX / "supplier-catalogue-lessebo.json").read_text("utf-8"))
    host = cat["domain"]
    _patch_client["routes"] = {
        f"https://{host}/.well-known/ptpge/catalogue.json": cat,
        cat["identity"].replace("https://ptpge.org/", "https://api.ptpge.org/") + ".jsonld": {"domain": host, "name": cat["name"]},
    }
    r = C.check_domain(host, _vocab_from_fixture(cat))
    assert r["verdict"] == "maker", r
    assert r["steps"][2]["status"] == "ok" and "suppliers/" in r["steps"][2]["detail"]
    assert r["agentSees"]["catalogueIdentity"] == cat["identity"]
    assert r["missing"] == []


def test_hosted_document_override(_patch_client):
    decl, man = _trykkverk()
    host = decl["domain"]
    hosted = "https://files.example.org/trykkverk/declaration.json"
    _patch_client["routes"] = {
        f"https://{host}/.well-known/ucp": man,
        hosted: decl,
        decl["identity"].replace("https://ptpge.org/", "https://api.ptpge.org/") + ".jsonld": {"domain": host},
    }
    r = C.check_domain(host, _vocab_from_fixture(decl, man), document=hosted)
    s = r["steps"][1]
    assert s["url"] == hosted and s["status"] == "warn", s
    assert any("hosted" in w for w in s["warnings"])
    assert r["agentSees"]["identity"] == decl["identity"]
