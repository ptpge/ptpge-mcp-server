"""Tests for the v0.4.0 tools: browse, product envelope, validate, fingerprint.

Fixture cache mirrors the real data shapes: the consolidated Brochure product
(SD-0038), contiguous weight bands with minWeight/maxWeight properties, the
scoring term with creasing thresholds, and the substrate-weight Variable.
"""

import json

import pytest

from ptpge_mcp.server import tool_payload

B = "https://ptpge.org/v1/"

TERMS = {
    B + "printing": {"id": B + "printing", "level": "top-concept",
                     "label": {"en": "Printing Process"},
                     "narrower": [B + "printing/completions"]},
    B + "ordering": {"id": B + "ordering", "level": "top-concept",
                     "label": {"en": "Ordering Process"}, "narrower": []},
    B + "variables": {"id": B + "variables", "level": "top-concept",
                      "label": {"en": "Variables"}, "narrower": []},
    B + "printing/completions": {
        "id": B + "printing/completions", "level": "group", "notation": "P:CP",
        "label": {"en": "Completions"}, "narrower": []},
    # — product (consolidated Brochure) —
    B + "ordering/products/buy-online/sheets/brochures": {
        "id": B + "ordering/products/buy-online/sheets/brochures",
        "level": "element", "elementType": "product", "notation": "O:PR§BROCHURE",
        "label": {"en": "Brochure", "nb": "Brosjyre"},
        "supportsSetupModel": [B + "printing/configurations/setup-models/folded-sheet/accordion-fold"],
        "supportsFormat": [B + "printing/configurations/formats/a-series/a5"],
        "supportsSubstrateWeight": [B + "printing/substrates/sheet-materials/paper/paper-weights/medium-paper"],
        "perSurfaceSupportsColorMode": [B + "printing/features/colors/cmyk",
                                        B + "printing/features/colors/black"],
        "typicalPageCount": 6, "fulfilmentClass": "folded",
    },
    # — values —
    B + "printing/configurations/setup-models/folded-sheet/accordion-fold": {
        "id": B + "printing/configurations/setup-models/folded-sheet/accordion-fold",
        "level": "element", "elementType": "value", "notation": "P:CF§ACCORDION-FOLD",
        "label": {"en": "Accordion-Fold Setup", "nb": "Trekkspill-fold oppsett"}},
    B + "printing/configurations/formats/a-series/a5": {
        "id": B + "printing/configurations/formats/a-series/a5",
        "level": "element", "elementType": "value", "notation": "P:CF§A5",
        "label": {"en": "A5 (148 x 210 mm)"}},
    B + "printing/configurations/formats/a-series/a4": {
        "id": B + "printing/configurations/formats/a-series/a4",
        "level": "element", "elementType": "value", "notation": "P:CF§A4",
        "label": {"en": "A4 (210 x 297 mm)"}},
    B + "printing/features/colors/cmyk": {
        "id": B + "printing/features/colors/cmyk", "level": "element",
        "elementType": "value", "notation": "P:FT§CMYK", "label": {"en": "CMYK"}},
    B + "printing/features/colors/black": {
        "id": B + "printing/features/colors/black", "level": "element",
        "elementType": "value", "notation": "P:FT§BLACK", "label": {"en": "Black"}},
    # — weight machinery —
    B + "variables/substrate/substrate-weight": {
        "id": B + "variables/substrate/substrate-weight", "level": "element",
        "elementType": "variable", "datatype": "numeric", "unit": "gsm",
        "label": {"en": "Substrate Weight"},
        "valueDomain": B + "printing/substrates/sheet-materials/paper/paper-weights"},
    B + "printing/substrates/sheet-materials/paper/paper-weights": {
        "id": B + "printing/substrates/sheet-materials/paper/paper-weights",
        "level": "sub-category", "label": {"en": "Paper Weights"},
        "narrower": [B + "printing/substrates/sheet-materials/paper/paper-weights/medium-paper",
                     B + "printing/substrates/sheet-materials/paper/paper-weights/heavy-paper"]},
    B + "printing/substrates/sheet-materials/paper/paper-weights/medium-paper": {
        "id": B + "printing/substrates/sheet-materials/paper/paper-weights/medium-paper",
        "level": "element", "elementType": "value", "notation": "P:SB§MEDIUM-PAPER",
        "label": {"en": "Medium Paper (150–179 gsm)"},
        "properties": {"minWeight": 150, "maxWeight": 179, "unit": "gsm"}},
    B + "printing/substrates/sheet-materials/paper/paper-weights/heavy-paper": {
        "id": B + "printing/substrates/sheet-materials/paper/paper-weights/heavy-paper",
        "level": "element", "elementType": "value", "notation": "P:SB§HEAVY-PAPER",
        "label": {"en": "Heavy Paper (240–309 gsm)"},
        "properties": {"minWeight": 240, "maxWeight": 309, "unit": "gsm"}},
    # — creasing advisory source —
    B + "printing/completions/finishing/scoring": {
        "id": B + "printing/completions/finishing/scoring", "level": "element",
        "elementType": "value", "notation": "P:CP§SCORING",
        "label": {"en": "Scoring", "nb": "Rilling"},
        "properties": {"recommendedAboveWeight": 170, "standardAboveWeight": 250,
                       "unit": "gsm"}},
}


class FakeCache:
    version = {"version": "2026-06-05"}

    def get_term(self, id_or_path):
        if id_or_path in TERMS:
            return TERMS[id_or_path]
        return TERMS.get(B + str(id_or_path).lstrip("/"))

    def search(self, **kw):
        return []


PRODUCT = "ordering/products/buy-online/sheets/brochures"


# -------------------- browse --------------------

def test_browse_roots():
    out = tool_payload(FakeCache(), "ptpge_browse", {})
    labels = [c["label"] for c in out["children"]]
    assert labels == ["Printing Process", "Ordering Process", "Variables"]
    assert out["children"][0]["hasChildren"] is True
    assert out["children"][1]["hasChildren"] is False


def test_browse_node():
    out = tool_payload(FakeCache(), "ptpge_browse", {"id_or_path": "printing"})
    assert out["node"]["label"] == "Printing Process"
    assert out["children"][0]["notation"] == "P:CP"


def test_browse_not_found():
    out = tool_payload(FakeCache(), "ptpge_browse", {"id_or_path": "nope/nope"})
    assert out["error"] == "not_found"


# -------------------- envelope --------------------

def test_envelope_resolves_labels():
    out = tool_payload(FakeCache(), "ptpge_get_product_envelope",
                       {"id_or_path": PRODUCT, "language": "en"})
    assert out["product"]["notation"] == "O:PR§BROCHURE"
    assert out["envelope"]["supportsSetupModel"][0]["label"] == "Accordion-Fold Setup"
    assert out["perSurface"]["perSurfaceSupportsColorMode"][1]["notation"] == "P:FT§BLACK"
    assert out["typical"]["typicalPageCount"] == 6


def test_envelope_rejects_non_product():
    out = tool_payload(FakeCache(), "ptpge_get_product_envelope",
                       {"id_or_path": "printing/features/colors/cmyk"})
    assert out["error"] == "not_a_product"


# -------------------- validate --------------------

def _bindings_ok():
    return [
        {"variable": "variables/structure/setup-model",
         "value": "printing/configurations/setup-models/folded-sheet/accordion-fold"},
        {"variable": "variables/dimensional/format",
         "value": "printing/configurations/formats/a-series/a5"},
        {"variable": "variables/substrate/substrate-weight", "value": 170},
        {"variable": "variables/color/color-mode", "surface": "outside",
         "value": "printing/features/colors/cmyk"},
        {"variable": "variables/structure/page-count", "value": 6},
        {"variable": "variables/commercial/quantity", "value": 500},
    ]


def test_validate_all_in_envelope_with_band_mapping_and_advisory():
    out = tool_payload(FakeCache(), "ptpge_validate_config",
                       {"product": PRODUCT, "bindings": _bindings_ok()})
    assert out["validInEnvelope"] is True
    by_var = {r["variable"]: r for r in out["bindings"]}
    w = by_var["variables/substrate/substrate-weight"]
    assert w["status"] == "in_envelope"
    assert w["band"]["notation"] == "P:SB§MEDIUM-PAPER"
    assert by_var["variables/structure/page-count"]["status"] == "not_checked"
    # 170 gsm is NOT above the 170 threshold — no advisory
    assert out["advisories"] == []


def test_validate_weight_advisory_recommended_and_standard():
    out = tool_payload(FakeCache(), "ptpge_validate_config", {
        "product": PRODUCT,
        "bindings": [{"variable": "variables/substrate/substrate-weight", "value": 175}]})
    assert out["advisories"][0]["type"] == "creasing_recommended"
    out2 = tool_payload(FakeCache(), "ptpge_validate_config", {
        "product": PRODUCT,
        "bindings": [{"variable": "variables/substrate/substrate-weight", "value": 300}]})
    # 300 gsm: band heavy-paper is NOT in the product envelope -> invalid,
    # but the advisory still fires (standard practice above 250).
    assert out2["validInEnvelope"] is False
    assert out2["advisories"][0]["type"] == "creasing_standard"


def test_validate_rejects_value_outside_envelope():
    out = tool_payload(FakeCache(), "ptpge_validate_config", {
        "product": PRODUCT,
        "bindings": [{"variable": "variables/dimensional/format",
                      "value": "printing/configurations/formats/a-series/a4"}]})
    assert out["validInEnvelope"] is False
    assert out["bindings"][0]["status"] == "not_in_envelope"


def test_validate_closed_semantics():
    out = tool_payload(FakeCache(), "ptpge_validate_config", {
        "product": PRODUCT,
        "bindings": [{"variable": "variables/production/technology",
                      "value": "printing/technologies/x"}]})
    assert out["bindings"][0]["status"] == "not_supported"
    assert out["validInEnvelope"] is False


# -------------------- fingerprint --------------------

def test_fingerprint_matches_spec_worked_example():
    """The spec § 9 worked example must reproduce byte-identically."""
    args = {
        "product": "ordering/products/buy-online/sheets/brochures",
        "bindings": [
            {"variable": "variables/structure/setup-model",
             "value": "printing/configurations/setup-models/folded-sheet/accordion-fold"},
            {"variable": "variables/structure/page-count", "value": 8},
            {"variable": "variables/dimensional/format",
             "value": "printing/configurations/formats/a-series/a5"},
            {"variable": "variables/substrate/substrate-type",
             "value": "printing/substrates/sheet-materials/paper"},
            {"variable": "variables/substrate/substrate-weight", "value": 170},
            {"variable": "variables/color/color-mode", "surface": "outside",
             "value": "printing/features/colors/cmyk"},
            {"variable": "variables/color/color-mode", "surface": "inside",
             "value": "printing/features/colors/black"},
            {"variable": "variables/embellishment/surface-finish", "surface": "outside",
             "values": ["printing/completions/finishing/laminations/matte",
                        "printing/features/embellishments/spot-uv-varnish"]},
            {"variable": "variables/commercial/quantity", "value": 500},
        ],
    }
    out = tool_payload(FakeCache(), "ptpge_fingerprint", args)
    assert out["profiles"]["spec"]["sha256"] == (
        "4b2482d846cee891fc280ca805b123b26c68f77b156f0005b79684fd4cc4646b")
    assert out["profiles"]["offer"]["sha256"] == (
        "39658b5f625127ab3dba5379d5662ea9cdedecff03257a72174b82bb5f7e97c3")
    assert out["profiles"]["spec"]["short"] == "4b2482d846cee891"


def test_fingerprint_deterministic_under_shuffle():
    import random
    args = {"product": PRODUCT, "bindings": [
        {"variable": "variables/dimensional/format",
         "value": "printing/configurations/formats/a-series/a5"},
        {"variable": "variables/substrate/substrate-weight", "value": 170},
        {"variable": "variables/commercial/quantity", "value": 500},
    ]}
    ref = tool_payload(FakeCache(), "ptpge_fingerprint", args)
    shuffled = json.loads(json.dumps(args))
    random.shuffle(shuffled["bindings"])
    out = tool_payload(FakeCache(), "ptpge_fingerprint", shuffled)
    assert out["profiles"]["spec"]["sha256"] == ref["profiles"]["spec"]["sha256"]


def test_fingerprint_duplicate_binding_is_tool_error():
    args = {"product": PRODUCT, "bindings": [
        {"variable": "variables/dimensional/format", "value": "x/a"},
        {"variable": "variables/dimensional/format", "value": "x/b"},
    ]}
    with pytest.raises(ValueError):
        tool_payload(FakeCache(), "ptpge_fingerprint", args)
