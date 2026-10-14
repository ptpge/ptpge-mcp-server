"""0.39.0 — POST /validate and POST /fingerprint mirror the MCP tools for web pages (ptpge.org/mapping)."""
from starlette.testclient import TestClient
from ptpge_mcp.server import build_app

BOOKLET = {"product": "ordering/products/booklets", "bindings": [
    {"variable": "variables/configuration/format", "value": "printing/configurations/formats/customized"},
    {"variable": "variables/configuration/custom-width", "value": 200.1},
    {"variable": "variables/configuration/custom-height", "value": 269.8},
    {"variable": "variables/configuration/orientation", "value": "printing/configurations/orientation/portrait"},
    {"variable": "variables/configuration/setup-model", "value": "printing/configurations/setup-models/multi-page"},
    {"variable": "variables/features/color-mode", "values": ["printing/features/colors/cmyk", "printing/features/colors/spot-color"]},
    {"variable": "variables/features/spot-ink", "value": "printing/standards/color-systems/color-matching-systems/pantone-matching-system/130-c"},
]}


def test_validate_and_fingerprint_json_roundtrip():
    c = TestClient(build_app())
    r = c.post("/validate", json=BOOKLET, headers={"Origin": "https://ptpge.org"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "https://ptpge.org"
    v = r.json()
    assert v["validInEnvelope"] and not v["complete"]
    asked = {q["field"] for q in v["needs_disambiguation"]}
    assert {"variables/configuration/page-count", "variables/finishing/binding"} <= asked
    r = c.post("/fingerprint", json=BOOKLET)
    assert r.status_code == 200 and r.json().get("error") == "not_fingerprintable"
    full = dict(BOOKLET); full["bindings"] = BOOKLET["bindings"] + [
        {"variable": "variables/configuration/page-count", "value": 8},
        {"variable": "variables/finishing/binding", "value": "printing/completions/binding/saddle-stitching"}]
    r = c.post("/fingerprint", json=full)
    f = r.json(); assert r.status_code == 200, f
    canon = f["profiles"]["spec"]["canonical"]
    assert "custom-width=200.1" in canon and "cmyk+printing/features/colors/spot-color" in canon, canon
    assert f["profiles"]["spec"].get("short") or f["profiles"]["spec"].get("sha256")


def test_json_endpoints_reject_bad_body():
    c = TestClient(build_app())
    assert c.post("/validate", content=b"not json", headers={"Content-Type": "application/json"}).status_code == 400
    assert c.post("/fingerprint", json={"bindings": []}).status_code == 400
    assert c.options("/validate", headers={"Origin": "https://ptpge.org"}).status_code == 204
