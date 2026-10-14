"""SD-0107 — a PDF binds what it states (trim, pages, colour spaces, named inks, output intent); never the rest."""
import io
import pytest

pikepdf = pytest.importorskip("pikepdf")
rl = pytest.importorskip("reportlab")
from reportlab.lib.colors import CMYKColor, PCMYKColorSep, black
from reportlab.pdfgen import canvas as rl_canvas

from ptpge_mcp import artwork as A

MM = 72 / 25.4


def _pdf(pages, size_mm=(148, 210), bleed_mm=3.0, spot=None, cmyk=True, gray_pages=(), outcond=None):
    w, h = size_mm[0] * MM, size_mm[1] * MM
    b = bleed_mm * MM
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(w + 2 * b, h + 2 * b))
    for i in range(pages):
        c.setCropBox((0, 0, w + 2 * b, h + 2 * b)); c.setTrimBox((b, b, b + w, b + h))
        if (i + 1) in gray_pages:
            c.setFillGray(0.2); c.rect(b + 20, b + 20, 100, 50, fill=1, stroke=0)
        else:
            if cmyk:
                c.setFillColor(CMYKColor(0, 1, 1, 0)); c.rect(b + 20, b + 20, 100, 50, fill=1, stroke=0)
            if spot and (i == 0 or pages <= 2):
                c.setFillColor(PCMYKColorSep(100, 50, 0, 0, spotName=spot)); c.rect(b + 20, b + 100, 100, 50, fill=1, stroke=0)
        c.showPage()
    c.save()
    data = buf.getvalue()
    if outcond:
        p = pikepdf.open(io.BytesIO(data))
        p.Root.OutputIntents = pikepdf.Array([pikepdf.Dictionary(Type=pikepdf.Name("/OutputIntent"), S=pikepdf.Name("/GTS_PDFX"),
                                              OutputConditionIdentifier=pikepdf.String(outcond), Info=pikepdf.String(outcond))])
        out = io.BytesIO(); p.save(out); data = out.getvalue()
    return data


def _cache():
    from ptpge_mcp.config import Config
    from ptpge_mcp.data import VocabularyCache
    c = VocabularyCache(Config.from_env()); c.load()
    return c


def test_a5_booklet_with_pantone_and_fogra():
    r = A.read_pdf(_pdf(16, spot="PANTONE 300 C", outcond="FOGRA39"), _cache())
    assert "error" not in r, r
    by = {(b["variable"], b.get("surface")): b for b in r["bindings"]}
    assert by[(A.FORMAT_VAR, None)]["value"].endswith("/a-series/a5")
    assert by[(A.ORIENT_VAR, None)]["value"].endswith("/orientation/portrait")   # 0.38.8: orientation is stated by the trim
    assert by[(A.PAGES_VAR, None)]["value"] == 16
    assert r["page"]["bleedMm"] == 3.0 and r["page"]["uniform"]
    assert A.SPOT in by[(A.COLOR_VAR, None)]["values"] and A.CMYK in by[(A.COLOR_VAR, None)]["values"]
    assert by[(A.INK_VAR, None)]["value"].endswith("pantone-matching-system/300-c")
    assert by[(A.STD_VAR, None)]["value"].endswith("print-standards/fogra39")
    asked = {q["variable"] for q in r["toAsk"]}
    assert "variables/finishing/binding" in asked and "variables/substrate/substrate-weight" in asked and "variables/order/quantity" in asked
    assert all(b["provenance"] == "artwork" for b in r["bindings"])
    assert len(r["artwork"]["sha256"]) == 64


def test_custom_size_two_sided_black_back():
    r = A.read_pdf(_pdf(2, size_mm=(120, 180), gray_pages=(2,)), _cache())
    by = {(b["variable"], b.get("surface")): b for b in r["bindings"]}
    assert by[(A.FORMAT_VAR, None)]["value"] == A.CUSTOMIZED
    assert by[(A.WIDTH_VAR, None)]["value"] == 120 and by[(A.HEIGHT_VAR, None)]["value"] == 180
    assert by[(A.COLOR_VAR, "front")]["values"] == [A.CMYK] and by[(A.COLOR_VAR, "back")]["values"] == [A.BLACK]


def test_unknown_separation_is_asked_not_guessed_and_nothing_is_stored():
    r = A.read_pdf(_pdf(1, spot="Gold Foil Varnish"), _cache())
    assert any(q["variable"] == A.INK_VAR for q in r["toAsk"])
    assert not any(b["variable"] == A.INK_VAR for b in r["bindings"])
    assert any(q["variable"] == A.COLOR_VAR and q.get("surface") == "back" for q in r["toAsk"])


def test_not_a_pdf():
    assert A.read_pdf(b"hello", None)["error"] == "not_a_pdf"


def test_artwork_endpoint_roundtrip():
    """POST /artwork with the PDF as body → reading; GET /playground/pdf serves the hidden page."""
    from starlette.testclient import TestClient
    from ptpge_mcp.server import build_app
    app = build_app()
    c = TestClient(app)
    data = _pdf(1, spot="PANTONE 485 C")
    r = c.post("/artwork", content=data, headers={"Content-Type": "application/pdf", "Origin": "https://gutenlex.com"})
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert j["artwork"]["pages"] == 1 and any(b["variable"] == A.INK_VAR for b in j["bindings"])
    assert r.headers.get("access-control-allow-origin") == "https://gutenlex.com" and r.headers.get("cache-control") == "no-store"
    assert c.post("/artwork", content=b"nope", headers={"Content-Type": "application/pdf"}).status_code == 400
    p = c.get("/playground/pdf")
    assert p.status_code == 200 and "Drop your PDF" in p.text and 'noindex' in p.text


def test_mixed_colour_and_black_pages_bind_cmyk_only_and_ask_per_part():
    r = A.read_pdf(_pdf(8, gray_pages=(3, 4, 5, 6)), _cache())
    cm = [b for b in r["bindings"] if b["variable"] == A.COLOR_VAR][0]
    assert cm["values"] == [A.CMYK] and "surface" not in cm
    assert any(q["variable"] == A.COLOR_VAR and "cover" in q["hint"] for q in r["toAsk"])
