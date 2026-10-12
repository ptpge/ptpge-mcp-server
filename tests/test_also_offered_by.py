"""alsoOfferedBy — the validator names the template that takes what this one rejects (12.10.2026)."""
from ptpge_mcp.server import validate_payload, also_offered_by


def _cache():
    from ptpge_mcp.config import Config
    from ptpge_mcp.data import VocabularyCache
    c = VocabularyCache(Config.from_env()); c.load()
    return c


def test_poster_on_aluminium_composite_points_to_panel_prints():
    c = _cache()
    r = validate_payload(c, {"product": "ordering/products/posters", "bindings": [
        {"variable": "variables/configuration/format", "value": "printing/configurations/formats/a-series/a1"},
        {"variable": "variables/substrate/substrate-type", "value": "printing/substrates/board-materials/metal/aluminium/composite"},
        {"variable": "variables/features/color-mode", "value": "printing/features/colors/cmyk", "surface": "front"}]})
    assert r["validInEnvelope"] is False
    ids = [a["id"].rsplit("/", 1)[-1] for a in r["alsoOfferedBy"]]
    assert ids[0] == "panel-prints" and "posters" not in ids
    assert all(a["acceptsBindings"] == 3 for a in r["alsoOfferedBy"])
    assert "Panel Prints" in r["switchHint"]


def test_no_alternative_when_valid_or_when_nothing_fits():
    c = _cache()
    ok = validate_payload(c, {"product": "ordering/products/posters", "bindings": [
        {"variable": "variables/configuration/format", "value": "printing/configurations/formats/a-series/a1"}]})
    assert "alsoOfferedBy" not in ok
    assert also_offered_by(c, "https://ptpge.org/v1/ordering/products/posters",
                           [{"variable": "variables/substrate/substrate-type", "value": "printing/substrates/no-such-thing"}], "en") == []
