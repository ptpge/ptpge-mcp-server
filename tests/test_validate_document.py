"""ptpge_validate_document / POST /validate-document (0.40.0) — the PTPGE Ready document check.

Schemas are fetched from ptpge.org (as the server does in production); the vocabulary comes from
the test cache. Skips cleanly when the network is not there."""
import copy
import json
import pathlib

import pytest

from ptpge_mcp.check import validate_document

ROOT = pathlib.Path(__file__).resolve().parents[2]
REQ = json.loads((ROOT / "tests/fixtures/request-brochure-a4.json").read_text())
QUO = json.loads((ROOT / "tests/fixtures/quote-trykkverk-brochure-a4.json").read_text())


def _online():
    import httpx
    try:
        return httpx.get("https://ptpge.org/v1/schemas/request/1.schema.json", timeout=6).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _online(), reason="schemas on ptpge.org not reachable")


def test_request_fixture_is_valid():
    out = validate_document(REQ, None)
    assert out["schema"] == "request/1"
    assert out["valid"], out["errors"]
    assert out["checked"]["fingerprint"]["request"] == REQ["fingerprint"]["request"]


def test_quote_fixture_is_valid_and_offer_recomputed():
    out = validate_document(QUO, None)
    assert out["valid"], out["errors"]
    assert out["checked"]["fingerprint"]["offer"] == QUO["fingerprint"]["offer"]


def test_tampered_quantity_breaks_request_fingerprint_not_spec():
    d = copy.deepcopy(REQ)
    for b in d["configuration"]["bindings"]:
        if b["variable"].endswith("/order/quantity"):
            b["value"] = 999
    out = validate_document(d, None)
    assert not out["valid"]
    assert any(e.startswith("fingerprint.request") for e in out["errors"])
    assert not any(e.startswith("fingerprint.spec") for e in out["errors"])


def test_wrong_vendor_breaks_offer_fingerprint():
    d = copy.deepcopy(QUO)
    d["vendor"] = "https://ptpge.org/v1/vendors/someone-else"
    out = validate_document(d, None)
    assert any(e.startswith("fingerprint.offer") for e in out["errors"])


def test_unknown_schema_and_non_object():
    assert "$.schema" in validate_document({"schema": "https://example.org/x"}, None)["errors"][0]
    assert not validate_document(["not", "an", "object"], None)["valid"]


def test_shape_error_is_reported():
    d = copy.deepcopy(REQ); d.pop("quantity")
    out = validate_document(d, None)
    assert not out["valid"] and any("quantity" in e for e in out["errors"])
