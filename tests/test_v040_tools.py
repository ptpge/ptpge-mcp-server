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
    B + "ordering/products/brochures": {
        "id": B + "ordering/products/brochures",
        "level": "element", "elementType": "product", "notation": "O:PR§BROCHURE",
        "label": {"en": "Brochure", "nb": "Brosjyre"},
        "supportsSetupModel": [B + "printing/configurations/setup-models/folded-sheet/single-fold"],
        "supportsFormat": [B + "printing/configurations/formats/a-series/a5"],
        "supportsSubstrateWeight": [B + "printing/substrates/sheet-materials/paper/paper-weights/medium-paper"],
        "perSurfaceSupportsColorMode": [B + "printing/features/colors/cmyk",
                                        B + "printing/features/colors/black"],
        "supportsSubstrate": [B + "printing/substrates/sheet-materials/paper"],
        "perSurfaceSupportsSurfaceFinish": [B + "printing/features/surface-finish/lamination/matte",
                                            B + "printing/features/embellishments/spot-uv-varnish"],
        # SD-0083
        "requiredVariables": [B + "variables/configuration/setup-model",
                              B + "variables/configuration/format",
                              B + "variables/features/color-mode"],
        "recommendedVariables": [B + "variables/substrate/substrate-type",
                                 B + "variables/substrate/substrate-weight",
                                 B + "variables/features/surface-finish"],
        "typicalPageCount": 6, "fulfilmentClass": "folded",
    },
    # — values —
    B + "printing/configurations/setup-models/folded-sheet/single-fold": {
        "id": B + "printing/configurations/setup-models/folded-sheet/single-fold",
        "level": "element", "elementType": "value", "notation": "P:CF§ACCORDION-FOLD",
        "label": {"en": "Accordion-Fold Setup", "nb": "Trekkspill-fold oppsett"},
        "surfaces": [{"id": "outside", "panels": [{"id": "outside-left"}, {"id": "outside-right"}]},
                     {"id": "inside", "panels": [{"id": "inside-left"}, {"id": "inside-right"}]}]},
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
    # — SD-0084 R6 machinery: the colour-mode variable with its process group —
    B + "variables/features/color-mode": {
        "id": B + "variables/features/color-mode", "level": "element",
        "elementType": "variable", "datatype": "enum", "cardinality": "multiple", "scope": "surface",
        "label": {"en": "Color Mode"}, "valueDomain": B + "printing/features/colors",
        "exclusiveGroups": [{"name": "process", "rule": "at-most-one",
                             "values": [B + "printing/features/colors/black", B + "printing/features/colors/cmyk"]}]},
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
    B + "printing/completions/structural-finishing/scoring": {
        "id": B + "printing/completions/structural-finishing/scoring", "level": "element",
        "elementType": "value", "notation": "P:CP§SCORING",
        "label": {"en": "Scoring", "nb": "Rilling"},
        "properties": {"recommendedFromWeight": 170, "standardFromWeight": 250,
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


PRODUCT = "ordering/products/brochures"


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
        {"variable": "variables/configuration/setup-model",
         "value": "printing/configurations/setup-models/folded-sheet/single-fold"},
        {"variable": "variables/configuration/format",
         "value": "printing/configurations/formats/a-series/a5"},
        {"variable": "variables/substrate/substrate-weight", "value": 170},
        {"variable": "variables/features/color-mode", "surface": "outside",
         "value": "printing/features/colors/cmyk"},
        {"variable": "variables/configuration/page-count", "value": 6},
        {"variable": "variables/order/quantity", "value": 500},
    ]


def test_validate_all_in_envelope_with_band_mapping_and_advisory():
    out = tool_payload(FakeCache(), "ptpge_validate_config",
                       {"product": PRODUCT, "bindings": _bindings_ok()})
    assert out["validInEnvelope"] is True
    by_var = {r["variable"]: r for r in out["bindings"]}
    w = by_var["variables/substrate/substrate-weight"]
    assert w["status"] == "in_envelope"
    assert w["band"]["notation"] == "P:SB§MEDIUM-PAPER"
    assert by_var["variables/configuration/page-count"]["status"] == "not_checked"
    # 170 gsm is the inclusive lower bound (>=170) — creasing recommended
    assert out["advisories"][0]["type"] == "creasing_recommended"


def test_validate_weight_advisory_recommended_and_standard():
    out = tool_payload(FakeCache(), "ptpge_validate_config", {
        "product": PRODUCT,
        "bindings": [{"variable": "variables/substrate/substrate-weight", "value": 175}]})
    assert out["advisories"][0]["type"] == "creasing_recommended"
    out2 = tool_payload(FakeCache(), "ptpge_validate_config", {
        "product": PRODUCT,
        "bindings": [{"variable": "variables/substrate/substrate-weight", "value": 300}]})
    # 300 gsm: band heavy-paper is NOT in the product envelope -> invalid,
    # but the advisory still fires (standard practice at or above 250).
    assert out2["validInEnvelope"] is False
    assert out2["advisories"][0]["type"] == "creasing_standard"


def test_validate_weight_advisory_boundaries():
    """Inclusive rule: 170-249 -> recommended, >=250 -> standard, <170 -> none."""
    def adv(gsm):
        out = tool_payload(FakeCache(), "ptpge_validate_config", {
            "product": PRODUCT,
            "bindings": [{"variable": "variables/substrate/substrate-weight", "value": gsm}]})
        return [a["type"] for a in out["advisories"] if a["type"].startswith("creasing")]
    assert adv(169) == []                          # below the recommended floor
    assert adv(170) == ["creasing_recommended"]    # inclusive lower bound
    assert adv(249) == ["creasing_recommended"]    # just under standard
    assert adv(250) == ["creasing_standard"]       # inclusive standard bound


def test_validate_rejects_value_outside_envelope():
    out = tool_payload(FakeCache(), "ptpge_validate_config", {
        "product": PRODUCT,
        "bindings": [{"variable": "variables/configuration/format",
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
        "product": "ordering/products/brochures",
        "bindings": [
            {"variable": "variables/configuration/setup-model",
             "value": "printing/configurations/setup-models/folded-sheet/single-fold"},
            {"variable": "variables/configuration/page-count", "value": 8},
            {"variable": "variables/configuration/format",
             "value": "printing/configurations/formats/a-series/a5"},
            {"variable": "variables/substrate/substrate-type",
             "value": "printing/substrates/sheet-materials/paper"},
            {"variable": "variables/substrate/substrate-weight", "value": 170},
            {"variable": "variables/features/color-mode", "surface": "outside",
             "value": "printing/features/colors/cmyk"},
            {"variable": "variables/features/color-mode", "surface": "inside",
             "value": "printing/features/colors/black"},
            {"variable": "variables/features/surface-finish", "surface": "outside",
             "values": ["printing/features/surface-finish/lamination/matte",
                        "printing/features/embellishments/spot-uv-varnish"]},
            {"variable": "variables/order/quantity", "value": 500},
        ],
    }
    out = tool_payload(FakeCache(), "ptpge_fingerprint", args)
    assert out["profiles"]["spec"]["sha256"] == (
        "ad3f18593fe2547dc9c59ed70d92a22aa59fc4e053881777fc69bda179a3c125")
    assert out["profiles"]["offer"]["sha256"] == (
        "93c50214d5e1f4be035ab750d632cb35dab2301108e32089e29eba943974632e")
    assert out["profiles"]["spec"]["short"] == "ad3f18593fe2547d"


def test_fingerprint_deterministic_under_shuffle():
    import random
    args = {"product": PRODUCT, "bindings": [
        {"variable": "variables/configuration/format",
         "value": "printing/configurations/formats/a-series/a5"},
        {"variable": "variables/substrate/substrate-weight", "value": 170},
        {"variable": "variables/features/color-mode", "surface": "outside",
         "value": "printing/features/colors/cmyk"},
        {"variable": "variables/order/quantity", "value": 500},
    ]}
    ref = tool_payload(FakeCache(), "ptpge_fingerprint", args)
    # SD-0083 D1: the only setup is written into the identity as envelope-implied
    assert ref["envelopeImplied"] == [{"variable": "variables/configuration/setup-model",
                                       "value": B + "printing/configurations/setup-models/folded-sheet/single-fold"}]
    assert "setup-model=" in ref["profiles"]["spec"]["canonical"]
    shuffled = json.loads(json.dumps(args))
    random.shuffle(shuffled["bindings"])
    out = tool_payload(FakeCache(), "ptpge_fingerprint", shuffled)
    assert out["profiles"]["spec"]["sha256"] == ref["profiles"]["spec"]["sha256"]


def test_fingerprint_duplicate_binding_is_tool_error():
    args = {"product": PRODUCT, "bindings": [
        {"variable": "variables/configuration/format",
         "value": "printing/configurations/formats/a-series/a5"},
        {"variable": "variables/configuration/format",
         "value": "printing/configurations/formats/a-series/a5"},
        {"variable": "variables/features/color-mode", "surface": "outside",
         "value": "printing/features/colors/cmyk"},
    ]}
    with pytest.raises(ValueError):
        tool_payload(FakeCache(), "ptpge_fingerprint", args)


# -------------------- data integrity: thresholds must not drift --------------------

def test_scoring_thresholds_match_source_data():
    """Guard against the source->prod drift we hit once (150 vs the recorded 170).

    The published scoring term must keep the recorded creasing convention
    (recommended above 170 gsm, standard above 250 gsm), and the FakeCache fixture
    above must mirror it — otherwise the advisory tests silently test the wrong
    numbers while production drifts.
    """
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2]
           / "terms/printing/completions/structural-finishing/scoring.jsonld")
    props = json.loads(src.read_text())["properties"]
    assert props["recommendedFromWeight"] == 170
    assert props["standardFromWeight"] == 250
    fixture = TERMS[B + "printing/completions/structural-finishing/scoring"]["properties"]
    assert (fixture["recommendedFromWeight"], fixture["standardFromWeight"]) == (170, 250)


# --- SD-0076: substrate class ⟂ coating, spine thickness range ---------------
_PC = "https://ptpge.org/v1/printing/substrates/sheet-materials/paper/paper-classes/"
_CO = "https://ptpge.org/v1/printing/substrates/sheet-materials/paper/paper-coatings/"


class _SD76Cache(FakeCache):
    def get_term(self, id_or_path):
        t = super().get_term(id_or_path)
        if t and t.get("elementType") == "product":
            t = dict(t)
            t["supportsSubstrateClass"] = [_PC + "ps1-premium-coated", _PC + "ps5-wood-free-uncoated"]
            t["supportsSubstrateCoating"] = [_CO + "coated", _CO + "uncoated"]
            t["supportsSpineThickness"] = {"min": 3, "max": 120, "unit": "mm"}
        return t


def _first_product_path():
    for uri, t in FakeCache().terms.items() if hasattr(FakeCache(), "terms") else []:
        if t.get("elementType") == "product":
            return uri
    return "ordering/products/brochures"


def test_sd0076_class_coating_mismatch_is_a_violation():
    out = tool_payload(_SD76Cache(), "ptpge_validate_config", {
        "product": _first_product_path(),
        "bindings": [
            {"variable": "variables/substrate/substrate-class", "value": _PC + "ps1-premium-coated"},
            {"variable": "variables/substrate/substrate-coating", "value": _CO + "uncoated"},
        ]})
    assert out.get("validInEnvelope") is False
    assert any(r["rule"] == "substrate_class_coating_mismatch" for r in out.get("rules", []))


def test_sd0076_class_coating_consistent_passes_rule():
    out = tool_payload(_SD76Cache(), "ptpge_validate_config", {
        "product": _first_product_path(),
        "bindings": [
            {"variable": "variables/substrate/substrate-class", "value": _PC + "ps5-wood-free-uncoated"},
            {"variable": "variables/substrate/substrate-coating", "value": _CO + "uncoated"},
        ]})
    assert not any(r["rule"] == "substrate_class_coating_mismatch" for r in out.get("rules", []))


def test_sd0076_spine_thickness_range():
    out = tool_payload(_SD76Cache(), "ptpge_validate_config", {
        "product": _first_product_path(),
        "bindings": [{"variable": "variables/configuration/spine-thickness", "value": 23}]})
    st = [b for b in out["bindings"] if b["variable"].endswith("spine-thickness")][0]
    assert st["status"] == "in_range"
    out2 = tool_payload(_SD76Cache(), "ptpge_validate_config", {
        "product": _first_product_path(),
        "bindings": [{"variable": "variables/configuration/spine-thickness", "value": 500}]})
    assert out2["validInEnvelope"] is False


# --- Peter #9 (2026-09-05): winding direction (FINAT 1–8, XJDF Component/@WindingResult) --
_WD = "https://ptpge.org/v1/printing/configurations/winding-direction/"


class _WindingCache(FakeCache):
    def get_term(self, id_or_path):
        t = super().get_term(id_or_path)
        if t and t.get("elementType") == "product":
            t = dict(t)
            t["supportsWindingDirection"] = [_WD + f"finat-{n}" for n in range(1, 9)]
        return t


def test_winding_direction_is_checked_against_envelope():
    ok = tool_payload(_WindingCache(), "ptpge_validate_config", {
        "product": _first_product_path(),
        "bindings": [{"variable": "variables/configuration/winding-direction", "value": _WD + "finat-3"}]})
    wd = [b for b in ok["bindings"] if b["variable"].endswith("winding-direction")][0]
    assert wd["status"] != "unknown_variable"
    assert ok.get("validInEnvelope") is not False
    bad = tool_payload(_WindingCache(), "ptpge_validate_config", {
        "product": _first_product_path(),
        "bindings": [{"variable": "variables/configuration/winding-direction", "value": _WD + "finat-9"}]})
    assert bad["validInEnvelope"] is False


# --- 0.25.0: ptpge_expand_fingerprint --------------------------------------

def test_expand_fingerprint_rejects_non_hex():
    import pytest
    with pytest.raises(ValueError):
        tool_payload(FakeCache(), "ptpge_expand_fingerprint", {"fingerprint": "not-a-hash"})


def test_expand_fingerprint_unknown_is_a_status_not_an_error(monkeypatch):
    import urllib.error, urllib.request
    def boom(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    out = tool_payload(FakeCache(), "ptpge_expand_fingerprint", {"fingerprint": "0" * 64})
    assert out["status"] == "unknown" and out["resolverUrl"].endswith("0" * 64)


def test_expand_fingerprint_resolves_and_relabels(monkeypatch):
    import io, json as _json, urllib.request
    doc = {"algorithm": "ptpge-cfs/1", "matchedProfile": "spec",
           "product": {"uri": "https://ptpge.org/v1/ordering/products/brochures", "label": "Brochure"},
           "bindings": [{"variable": "variables/configuration/page-count", "value": 8, "label": "8"}],
           "canonical": "ptpge-cfs/1:spec;product=ordering/products/brochures;variables/configuration/page-count=8"}
    class R(io.BytesIO):
        def geturl(self): return "https://ptpge.org/f/" + "f" * 64
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: R(_json.dumps(doc).encode()))
    out = tool_payload(FakeCache(), "ptpge_expand_fingerprint", {"fingerprint": "ptpge.org/f/" + "f" * 16})
    assert out["status"] == "resolved" and out["profile"] == "spec"
    assert out["fingerprint"] == "f" * 64 and out["bindings"][0]["value"] == 8
    assert "never part of it" in out["note"]


# -------------------- SD-0083: one specified product, one identity --------------------

def _v(bindings):
    return tool_payload(FakeCache(), "ptpge_validate_config", {"product": PRODUCT, "bindings": bindings})


def test_sd0083_missing_colour_is_a_question_not_an_identity():
    out = _v([{"variable": "variables/configuration/format",
               "value": "printing/configurations/formats/a-series/a5"}])
    assert out["validInEnvelope"] is True and out["complete"] is False
    q = out["needs_disambiguation"]
    assert [e["field"] for e in q] == ["variables/features/color-mode"]
    assert q[0]["surface"] == "outside" and q[0]["reason"] == "required_axis_missing"
    assert [c["id"].rsplit("/", 1)[-1] for c in q[0]["candidates"]] == ["cmyk", "black"]
    fp = tool_payload(FakeCache(), "ptpge_fingerprint", {"product": PRODUCT, "bindings": [
        {"variable": "variables/configuration/format", "value": "printing/configurations/formats/a-series/a5"}]})
    assert fp["error"] == "not_fingerprintable" and fp["reason"] == "incomplete"
    assert fp["needs_disambiguation"][0]["field"] == "variables/features/color-mode"


def test_sd0083_surface_must_be_a_face_of_the_setup():
    out = _v([{"variable": "variables/configuration/format",
               "value": "printing/configurations/formats/a-series/a5"},
              {"variable": "variables/features/color-mode", "surface": "front",
               "value": "printing/features/colors/cmyk"}])
    bad = [b for b in out["bindings"] if b.get("status") == "surface_not_in_setup"]
    assert bad and bad[0]["allowed_surfaces"] == ["outside", "inside"]
    assert out["validInEnvelope"] is False
    fp = tool_payload(FakeCache(), "ptpge_fingerprint", {"product": PRODUCT, "bindings": [
        {"variable": "variables/configuration/format", "value": "printing/configurations/formats/a-series/a5"},
        {"variable": "variables/features/color-mode", "surface": "front", "value": "printing/features/colors/cmyk"}]})
    assert fp["error"] == "not_fingerprintable" and fp["reason"] == "not_valid_in_envelope"


def test_sd0083_panels_are_accepted_and_implied_setup_reported():
    out = _v([{"variable": "variables/configuration/format",
               "value": "printing/configurations/formats/a-series/a5"},
              {"variable": "variables/features/color-mode", "surface": "outside",
               "value": "printing/features/colors/cmyk"},
              {"variable": "variables/features/embellishment", "surface": "outside-left",
               "value": "printing/features/embellishments/spot-uv-varnish"}])
    assert out["complete"] is True
    assert out["setup"]["implied"] is True and out["setup"]["surfaces"] == ["outside", "inside"]
    implied = [b for b in out["bindings"] if b["status"] == "envelope_implied"]
    assert implied[0]["variable"] == "variables/configuration/setup-model"
    types = [a["type"] for a in out["advisories"]]
    assert "surface_unspecified" in types and "unspecified_axes" in types


def test_sd0083_same_identity_stated_or_implied():
    """An agent that states the only setup and one that omits it get the same hash (D1)."""
    common = [{"variable": "variables/configuration/format",
               "value": "printing/configurations/formats/a-series/a5"},
              {"variable": "variables/features/color-mode", "surface": "outside",
               "value": "printing/features/colors/cmyk"}]
    a = tool_payload(FakeCache(), "ptpge_fingerprint", {"product": PRODUCT, "bindings": common})
    b = tool_payload(FakeCache(), "ptpge_fingerprint", {"product": PRODUCT, "bindings": common + [
        {"variable": "variables/configuration/setup-model",
         "value": "printing/configurations/setup-models/folded-sheet/single-fold"}]})
    assert a["profiles"]["spec"]["sha256"] == b["profiles"]["spec"]["sha256"]
    assert a["validated"] is True and "envelopeImplied" in a and "envelopeImplied" not in b


def test_sd0083_colour_resolver_takes_faces_from_setup():
    out = tool_payload(FakeCache(), "ptpge_resolve_color_notation",
                       {"product": PRODUCT, "notation": "4/1"})
    assert list(out["surfaces"].keys()) == ["outside", "inside"]
    assert "single-fold" in out["surfaces_note"]


def test_sd0083_d5_unscoped_face_attribute_applies_to_every_face():
    """"matte lamination" with no face on a two-faced setup → one binding per face,
    and the same hash as stating both faces explicitly."""
    unscoped = [{"variable": "variables/configuration/format",
                 "value": "printing/configurations/formats/a-series/a5"},
                {"variable": "variables/features/color-mode", "value": "printing/features/colors/cmyk"},
                {"variable": "variables/features/surface-finish",
                 "value": "printing/features/surface-finish/lamination/matte"}]
    explicit = [unscoped[0]] + [
        {"variable": "variables/features/color-mode", "surface": f, "value": "printing/features/colors/cmyk"} for f in ("outside", "inside")] + [
        {"variable": "variables/features/surface-finish", "surface": f,
         "value": "printing/features/surface-finish/lamination/matte"} for f in ("outside", "inside")]
    v = tool_payload(FakeCache(), "ptpge_validate_config", {"product": PRODUCT, "bindings": unscoped})
    assert v["complete"] is True
    faces = sorted((b["variable"].rsplit("/", 1)[-1], b["surface"]) for b in v["bindings"] if b.get("surface_provenance") == "envelope-implied")
    assert faces == [("color-mode", "inside"), ("color-mode", "outside"), ("surface-finish", "inside"), ("surface-finish", "outside")]
    a = tool_payload(FakeCache(), "ptpge_fingerprint", {"product": PRODUCT, "bindings": unscoped})
    b = tool_payload(FakeCache(), "ptpge_fingerprint", {"product": PRODUCT, "bindings": explicit})
    assert a["profiles"]["spec"]["sha256"] == b["profiles"]["spec"]["sha256"]
    assert "@outside=" in a["profiles"]["spec"]["canonical"] and "@inside=" in a["profiles"]["spec"]["canonical"]


def test_surface_finish_stack_may_top_with_an_embellishment():
    """SD-0040 §9 worked example: surface-finish@outside = matte > spot-uv. The stack's
    top layer may be an embellishment; the validator checks both per-surface envelopes."""
    class C(FakeCache):
        def get_term(self, id_or_path):
            t = super().get_term(id_or_path)
            if t and t.get("elementType") == "product":
                t = dict(t)
                t["perSurfaceSupportsSurfaceFinish"] = [B + "printing/features/surface-finish/lamination/matte"]
                t["perSurfaceSupportsEmbellishment"] = [B + "printing/features/embellishments/spot-uv-varnish"]
            return t
    out = tool_payload(C(), "ptpge_validate_config", {"product": PRODUCT, "bindings": [
        {"variable": "variables/configuration/format", "value": "printing/configurations/formats/a-series/a5"},
        {"variable": "variables/features/color-mode", "surface": "outside", "value": "printing/features/colors/cmyk"},
        {"variable": "variables/features/surface-finish", "surface": "outside",
         "values": ["printing/features/surface-finish/lamination/matte",
                    "printing/features/embellishments/spot-uv-varnish"]}]})
    assert out["validInEnvelope"] is True and out["complete"] is True


# -------------------- SD-0083 R5 (2026-09-18) --------------------

def test_validate_entails_substrate_type_from_paper_value():
    """A value under a material entails the substrate type; a stated type under
    another material is a conflict."""
    silk = {"variable": "variables/substrate/substrate-finish",
            "value": "printing/substrates/sheet-materials/paper/paper-surfaces/silk-paper"}
    out = tool_payload(FakeCache(), "ptpge_validate_config",
                       {"product": PRODUCT, "bindings": _bindings_ok() + [silk]})
    ent = [r for r in out["bindings"] if r["variable"] == "variables/substrate/substrate-type"]
    assert ent and ent[0]["status"] == "entailed"
    assert ent[0]["value"] == "printing/substrates/sheet-materials/paper"
    assert ent[0]["entailedBy"] == "variables/substrate/substrate-finish"
    typed = {"variable": "variables/substrate/substrate-type",
             "value": "printing/substrates/sheet-materials/paper"}
    out2 = tool_payload(FakeCache(), "ptpge_validate_config",
                        {"product": PRODUCT, "bindings": _bindings_ok() + [silk, typed]})
    assert not [r for r in out2["bindings"] if r.get("status") == "entailed"]
    wrong = {"variable": "variables/substrate/substrate-type",
             "value": "printing/substrates/sheet-materials/cardstock"}
    out3 = tool_payload(FakeCache(), "ptpge_validate_config",
                        {"product": PRODUCT, "bindings": _bindings_ok() + [silk, wrong]})
    assert out3["validInEnvelope"] is False and out3["complete"] is False
    assert [r for r in out3["bindings"] if r.get("status") == "substrate_type_conflict"]


def test_validate_refuses_two_process_colours_on_one_face():
    """SD-0084 R6: black + CMYK on one face are two process colours — a
    violation named from the Standard's exclusiveGroups; no identity."""
    both = {"variable": "variables/features/color-mode", "surface": "outside",
            "values": ["printing/features/colors/cmyk", "printing/features/colors/black"]}
    bindings = [b for b in _bindings_ok() if b["variable"] != "variables/features/color-mode"] + [both]
    out = tool_payload(FakeCache(), "ptpge_validate_config", {"product": PRODUCT, "bindings": bindings})
    r6 = [r for r in out.get("rules", []) if r["rule"] == "exclusive_group_conflict"]
    assert r6 and r6[0]["group"] == "process" and out["complete"] is False
    fp = tool_payload(FakeCache(), "ptpge_fingerprint", {"product": PRODUCT, "bindings": bindings, "validate": True})
    assert fp.get("error") == "not_fingerprintable" and fp.get("reason") == "exclusive_group_conflict"


# -------------------- SD-0088: the null value is always in a feature envelope --------------------

def _with_null_terms():
    """A cache whose vocabulary also carries the «none» values (the fixture above has none of them)."""
    extra = {
        B + "printing/features/surface-finish/none": {
            "id": B + "printing/features/surface-finish/none", "level": "element", "elementType": "value",
            "notation": "P:FT§NO-SURFACE-FINISH", "label": {"en": "None (no surface finish)"}, "standalone": True},
        B + "printing/features/colors/none": {
            "id": B + "printing/features/colors/none", "level": "element", "elementType": "value",
            "notation": "P:FT§NONE", "label": {"en": "None (no color)"}, "standalone": True},
    }
    c = FakeCache()
    merged = dict(TERMS); merged.update(extra)
    c.get_term = lambda uri, _m=merged: _m.get(uri)
    return c


def test_sd0088_none_rides_in_envelope_payload():
    out = tool_payload(_with_null_terms(), "ptpge_get_product_envelope", {"id_or_path": PRODUCT, "language": "en"})
    # SD-0098 (2026-10-07): surface finish has no null value — absence means none; nothing appended
    sf = [r["id"] for r in out["perSurface"]["perSurfaceSupportsSurfaceFinish"]]
    assert B + "printing/features/surface-finish/none" not in sf and len(sf) == 2
    cm = [r["id"] for r in out["perSurface"]["perSurfaceSupportsColorMode"]]
    assert cm[-1] == B + "printing/features/colors/none"
    # the fixture without the terms: nothing appended (no dangling reference)
    out0 = tool_payload(FakeCache(), "ptpge_get_product_envelope", {"id_or_path": PRODUCT, "language": "en"})
    assert len(out0["perSurface"]["perSurfaceSupportsSurfaceFinish"]) == 2


def test_sd0088_none_validates_in_envelope():
    # SD-0098: an explicit «surface-finish/none» is no longer a value — the axis is left out instead
    b = _bindings_ok() + [{"variable": "variables/features/surface-finish", "surface": "outside",
                           "values": ["printing/features/surface-finish/none"]}]
    out = tool_payload(_with_null_terms(), "ptpge_validate_config", {"product": PRODUCT, "bindings": b})
    by_var = {r["variable"]: r for r in out["bindings"]}
    assert by_var["variables/features/surface-finish"]["status"] == "not_in_envelope"
    assert out["validInEnvelope"] is False
    # colour-mode/none (spoken blankness) still validates
    b2 = _bindings_ok() + [{"variable": "variables/features/color-mode", "surface": "inside",
                            "value": "printing/features/colors/none"}]
    out2 = tool_payload(_with_null_terms(), "ptpge_validate_config", {"product": PRODUCT, "bindings": b2})
    assert out2["validInEnvelope"] is True
