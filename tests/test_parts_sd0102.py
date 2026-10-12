"""SD-0102 — substrate axes scoped to a PART of a multi-page setup (cover / inside)."""
from ptpge_mcp.server import validate_payload, fingerprint_payload

BASE = [{"variable": "variables/configuration/format", "value": "printing/configurations/formats/a-series/a5"},
        {"variable": "variables/configuration/orientation", "value": "printing/configurations/orientation/portrait"},
        {"variable": "variables/configuration/page-count", "value": 16},
        {"variable": "variables/finishing/binding", "value": "printing/completions/binding/saddle-stitching"},
        {"variable": "variables/features/color-mode", "value": "printing/features/colors/cmyk"}]
W = "variables/substrate/substrate-weight"


def _cache():
    from ptpge_mcp.config import Config
    from ptpge_mcp.data import VocabularyCache
    c = VocabularyCache(Config.from_env()); c.load()
    t = c.get_term("https://ptpge.org/v1/printing/configurations/setup-models/multi-page")
    t.setdefault("parts", [{"id": "cover", "surfaces": ["front-cover", "inside-front-cover", "inside-back-cover", "back-cover"]},
                           {"id": "inside", "surfaces": ["inside-pages"]}])
    return c


def test_cover_and_inside_are_two_statements_in_one_identity():
    c = _cache()
    b = BASE + [{"variable": W, "value": 300, "surface": "cover"}, {"variable": W, "value": 130, "surface": "inside"}]
    r = validate_payload(c, {"product": "ordering/products/booklets", "bindings": b})
    assert r["validInEnvelope"] and r["complete"] and r["setup"]["parts"] == ["cover", "inside"]
    fp = fingerprint_payload({"product": "ordering/products/booklets", "bindings": b}, c)
    canon = fp["profiles"]["spec"]["canonical"]
    assert f"{W}@cover=300" in canon and f"{W}@inside=130" in canon


def test_one_part_only_is_an_open_question_not_a_default():
    c = _cache()
    r = validate_payload(c, {"product": "ordering/products/booklets", "bindings": BASE + [{"variable": W, "value": 300, "surface": "cover"}]})
    assert r["validInEnvelope"] and not r["complete"]
    assert any(q["reason"] == "part_unbound" and q["surface"] == "inside" for q in r["needs_disambiguation"])


def test_a_surface_is_not_a_part():
    c = _cache()
    r = validate_payload(c, {"product": "ordering/products/booklets", "bindings": BASE + [{"variable": W, "value": 300, "surface": "front-cover"}]})
    assert not r["validInEnvelope"]
    assert any(e.get("status") == "surface_not_in_setup" and e["variable"] == W for e in r["bindings"])


def test_whole_product_binding_unchanged():
    c = _cache()
    b = BASE + [{"variable": W, "value": 170}]
    r = validate_payload(c, {"product": "ordering/products/booklets", "bindings": b})
    assert r["validInEnvelope"] and r["complete"]
    fp = fingerprint_payload({"product": "ordering/products/booklets", "bindings": b}, c)
    assert f"{W}=170" in fp["profiles"]["spec"]["canonical"] and "@cover" not in fp["profiles"]["spec"]["canonical"]


def test_flat_sheet_has_no_parts():
    c = _cache()
    r = validate_payload(c, {"product": "ordering/products/flyers", "bindings": [
        {"variable": "variables/configuration/format", "value": "printing/configurations/formats/a-series/a5"},
        {"variable": W, "value": 170, "surface": "cover"}]})
    assert not r["validInEnvelope"]
