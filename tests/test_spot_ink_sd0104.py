"""SD-0104 — named spot inks: n spot-color layers = n spot-ink values per face; code checked for form only."""
from ptpge_mcp import spotink
from ptpge_mcp.server import validate_payload, fingerprint_payload

P = "ordering/products/business-cards"
SYS = "printing/standards/color-systems/color-matching-systems/"
BASE = [{"variable": "variables/configuration/format", "value": "printing/configurations/formats/business-cards/eu-85x55"},
        {"variable": "variables/configuration/setup-model", "value": "printing/configurations/setup-models/flat-sheet"}]


def _cache():
    from ptpge_mcp.config import Config
    from ptpge_mcp.data import VocabularyCache
    c = VocabularyCache(Config.from_env()); c.load()
    return c


def _base(c):
    # the business-card format may differ by data version — take the first supported format
    prod = c.get_term("https://ptpge.org/v1/" + P)
    fmt = str((prod.get("supportsFormat") or [])[0]); su = str((prod.get("supportsSetupModel") or [])[0])
    ori = str((prod.get("supportsOrientation") or ["printing/configurations/orientation/landscape"])[0])
    return [{"variable": "variables/configuration/format", "value": fmt},
            {"variable": "variables/configuration/setup-model", "value": su},
            {"variable": "variables/configuration/orientation", "value": ori}]


def test_make_and_parse_value():
    v = spotink.make_value(SYS + "pantone-matching-system", "300 C")
    assert v == SYS + "pantone-matching-system/300-c"
    p = spotink.parse_value("https://ptpge.org/v1/" + v)
    assert p["system"].endswith("pantone-matching-system") and p["code"] == "300-c"
    assert spotink.parse_value(SYS + "pantone-matching-system/300 C") is None      # not normalized
    assert spotink.parse_value("printing/features/colors/cmyk") is None            # not a system


def test_spot_layer_without_ink_asks_and_refuses_identity():
    c = _cache()
    b = _base(c) + [{"variable": "variables/features/color-mode", "values": ["printing/features/colors/cmyk", "printing/features/colors/spot-color"], "surface": "front"},
                    {"variable": "variables/features/color-mode", "value": "printing/features/colors/cmyk", "surface": "back"}]
    r = validate_payload(c, {"product": P, "bindings": b})
    assert r["validInEnvelope"], r
    q = [x for x in r["needs_disambiguation"] if x["reason"] == "spot_ink_missing"]
    assert q and q[0]["surface"] == "front" and q[0]["missing"] == 1
    fp = fingerprint_payload({"product": P, "bindings": b}, c)
    assert fp.get("error") == "not_fingerprintable"


def test_named_ink_completes_and_is_in_the_identity():
    c = _cache()
    ink = SYS + "pantone-matching-system/300-c"
    b = _base(c) + [{"variable": "variables/features/color-mode", "values": ["printing/features/colors/cmyk", "printing/features/colors/spot-color"], "surface": "front"},
                    {"variable": "variables/features/color-mode", "value": "printing/features/colors/cmyk", "surface": "back"},
                    {"variable": "variables/features/spot-ink", "value": ink, "surface": "front"}]
    r = validate_payload(c, {"product": P, "bindings": b})
    assert r["validInEnvelope"] and not any(x["reason"] == "spot_ink_missing" for x in r.get("needs_disambiguation", []))
    e = [x for x in r["bindings"] if x["variable"] == "variables/features/spot-ink"][0]
    assert e["status"] == "named_ink" and e["inks"][0]["code"] == "300-c"
    fp = fingerprint_payload({"product": P, "bindings": b}, c)
    assert "error" not in fp, fp
    assert "variables/features/spot-ink@front=" + ink in fp["profiles"]["spec"]["canonical"]


def test_two_spots_need_two_inks_and_ink_without_layer_is_an_error():
    c = _cache()
    cm = {"variable": "variables/features/color-mode", "values": ["printing/features/colors/cmyk", "printing/features/colors/spot-color", "printing/features/colors/spot-color"], "surface": "front"}
    r = validate_payload(c, {"product": P, "bindings": _base(c) + [cm, {"variable": "variables/features/spot-ink", "value": SYS + "hks/43-k", "surface": "front"}]})
    q = [x for x in r["needs_disambiguation"] if x["reason"] == "spot_ink_missing"]
    assert q and q[0]["missing"] == 1
    r2 = validate_payload(c, {"product": P, "bindings": _base(c) + [{"variable": "variables/features/color-mode", "value": "printing/features/colors/cmyk", "surface": "front"},
                                                                  {"variable": "variables/features/spot-ink", "value": SYS + "hks/43-k", "surface": "front"}]})
    assert not r2["validInEnvelope"] and any(x.get("status") == "ink_without_spot_layer" for x in r2["bindings"])


def test_invalid_code_form_is_rejected():
    c = _cache()
    r = validate_payload(c, {"product": P, "bindings": _base(c) + [{"variable": "variables/features/color-mode", "values": ["printing/features/colors/cmyk", "printing/features/colors/spot-color"], "surface": "front"},
                                                                 {"variable": "variables/features/spot-ink", "value": SYS + "pantone-matching-system/300 C", "surface": "front"}]})
    assert not r["validInEnvelope"] and any(x.get("status") == "invalid_ink_value" for x in r["bindings"])


def test_custom_size_in_cm_is_the_same_identity_as_mm():
    """12 × 18 cm and 120 × 180 mm are one booklet (identity in mm; input in any unit)."""
    c = _cache()
    base = [{"variable": "variables/configuration/format", "value": "printing/configurations/formats/customized"},
            {"variable": "variables/configuration/orientation", "value": "printing/configurations/orientation/portrait"},
            {"variable": "variables/configuration/page-count", "value": 16},
            {"variable": "variables/finishing/binding", "value": "printing/completions/binding/saddle-stitching"},
            {"variable": "variables/features/color-mode", "value": "printing/features/colors/cmyk"}]
    mm = base + [{"variable": "variables/configuration/custom-width", "value": 120}, {"variable": "variables/configuration/custom-height", "value": 180}]
    cm = base + [{"variable": "variables/configuration/custom-width", "value": 12, "unit": "cm"}, {"variable": "variables/configuration/custom-height", "value": 18, "unit": "cm"}]
    r = validate_payload(c, {"product": "ordering/products/booklets", "bindings": cm})
    w = [b for b in r["bindings"] if b["variable"].endswith("custom-width")][0]
    assert r["validInEnvelope"] and w["status"] == "in_range" and w["value"] == 120 and w["stated"] == "12 cm"
    a = fingerprint_payload({"product": "ordering/products/booklets", "bindings": mm}, c)
    b = fingerprint_payload({"product": "ordering/products/booklets", "bindings": cm}, c)
    assert "error" not in a and a["profiles"]["spec"]["canonical"] == b["profiles"]["spec"]["canonical"]
    inch = base + [{"variable": "variables/configuration/custom-width", "value": 5, "unit": "in"}, {"variable": "variables/configuration/custom-height", "value": 7, "unit": "in"}]
    r2 = validate_payload(c, {"product": "ordering/products/booklets", "bindings": inch})
    assert [x["value"] for x in r2["bindings"] if x["variable"].endswith("custom-width")] == [127]
