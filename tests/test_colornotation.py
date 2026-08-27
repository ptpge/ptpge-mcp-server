"""Tests for SD-0071 color pair notation resolution."""

from __future__ import annotations

import json
import pathlib

import pytest

from ptpge_mcp import colornotation as cn
from ptpge_mcp.colornotation import BLACK, CMYK, NONE, SPOT

WHITE = cn.BASE + "printing/features/colors/white"
CMYKOG = cn.BASE + "printing/features/colors/cmykog"
CMYKOGV = cn.BASE + "printing/features/colors/cmykogv"

CHANNELS = {NONE: 0, BLACK: 1, WHITE: 1, SPOT: 1, CMYK: 4, CMYKOG: 6, CMYKOGV: 7}

PLAIN = [BLACK, CMYK, NONE]                       # business-card class
WITH_SPOT = [BLACK, CMYK, SPOT, NONE]             # commercial print
WIDE = [CMYK, WHITE, SPOT, NONE]                  # wide format, white ink
GAMUT = [CMYK, CMYKOG, CMYKOGV, WHITE, SPOT, NONE]


# --- parsing ---------------------------------------------------------------

@pytest.mark.parametrize("text,front,back,sep", [
    ("4/4", 4, 4, "/"), ("4 / 4", 4, 4, "/"), ("4+4", 4, 4, "+"),
    ("4 + 4", 4, 4, "+"), ("4/1", 4, 1, "/"), ("4/0", 4, 0, "/"),
    ("  1/1  ", 1, 1, "/"),
])
def test_parse_forms(text, front, back, sep):
    pair = cn.parse_pair(text)
    assert (pair.front, pair.back, pair.separator) == (front, back, sep)


@pytest.mark.parametrize("text", ["cmyk", "", "4", "4/4/4", "A/1", None])
def test_parse_rejects_non_notation(text):
    with pytest.raises(cn.NotationError):
        cn.parse_pair(text)


def test_plus_safe_when_equal_ambiguous_when_not():
    assert not cn.plus_is_ambiguous(cn.parse_pair("4+4"))
    assert cn.plus_is_ambiguous(cn.parse_pair("4+1"))
    # the slash never forks
    assert not cn.plus_is_ambiguous(cn.parse_pair("4/1"))


# --- the two declared conventions -----------------------------------------

def test_four_is_cmyk_by_convention():
    r = cn.resolve_surface(4, WITH_SPOT, CHANNELS)
    assert r.binding == (CMYK,)          # not black + 3 spots, not 4 spots


def test_zero_is_none_and_is_invalid_without_none():
    assert cn.resolve_surface(0, PLAIN, CHANNELS).binding == (NONE,)
    assert cn.resolve_surface(0, [CMYK], CHANNELS).invalid


# --- the template decides --------------------------------------------------

def test_one_is_deterministic_without_spot_support():
    r = cn.resolve_surface(1, PLAIN, CHANNELS, "back")
    assert r.binding == (BLACK,)
    assert r.question is None


def test_one_is_ambiguous_with_spot_support():
    r = cn.resolve_surface(1, WITH_SPOT, CHANNELS, "back")
    assert r.binding is None
    assert set(r.candidates) == {(BLACK,), (SPOT,)}
    assert "named spot color" in r.question and "which spot color" in r.question


def test_same_count_three_different_outcomes():
    """5 is deterministic, ambiguous or invalid depending on the template."""
    deterministic = cn.resolve_surface(5, [CMYK, WHITE, NONE], CHANNELS)
    assert deterministic.binding == (CMYK, WHITE)

    ambiguous = cn.resolve_surface(5, WIDE, CHANNELS)
    assert ambiguous.binding is None
    assert (CMYK, WHITE) in ambiguous.candidates
    assert (CMYK, SPOT) in ambiguous.candidates

    invalid = cn.resolve_surface(5, PLAIN, CHANNELS)
    assert invalid.invalid and not invalid.candidates


def test_black_is_never_added_to_cmyk():
    """K is already in CMYK, so 5 must not resolve to CMYK + black."""
    r = cn.resolve_surface(5, [CMYK, BLACK, NONE], CHANNELS)
    assert r.invalid
    assert all(not (CMYK in c and BLACK in c) for c in r.candidates)


def test_seven_enumerates_from_the_template_not_a_list():
    r = cn.resolve_surface(7, GAMUT, CHANNELS)
    assert r.binding is None
    for expected in [(CMYKOGV,), (CMYKOG, WHITE), (CMYKOG, SPOT),
                     (CMYK, SPOT, SPOT, SPOT), (CMYK, SPOT, SPOT, WHITE)]:
        assert tuple(sorted(expected, key=lambda u: (-CHANNELS[u], u))) in r.candidates


def test_six_includes_cmyk_spot_white():
    r = cn.resolve_surface(6, GAMUT, CHANNELS)
    combos = {frozenset(c) for c in r.candidates}
    assert frozenset({CMYKOG}) in combos
    assert frozenset({CMYK, SPOT, WHITE}) in combos


# --- full pair resolution --------------------------------------------------

def test_four_four_resolves_both_surfaces():
    res = cn.resolve("4/4", WITH_SPOT, CHANNELS)
    assert res.resolved
    assert res.surfaces["front"].binding == (CMYK,)
    assert res.surfaces["back"].binding == (CMYK,)
    assert "needs_disambiguation" not in res.to_dict()


def test_four_one_asks_only_about_the_back():
    res = cn.resolve("4/1", WITH_SPOT, CHANNELS)
    assert not res.resolved
    payload = res.to_dict()
    needs = payload["needs_disambiguation"]
    assert len(needs) == 1
    assert needs[0]["surface"] == "back" and needs[0]["count"] == 1
    assert payload["surfaces"]["front"]["binding"] == [CMYK]


def test_four_one_is_deterministic_where_the_template_allows_only_black():
    res = cn.resolve("4/1", PLAIN, CHANNELS)
    assert res.resolved
    assert res.surfaces["back"].binding == (BLACK,)


def test_plus_with_unequal_numbers_asks_about_the_separator():
    res = cn.resolve("4+1", PLAIN, CHANNELS)
    assert not res.resolved
    reasons = [n["reason"] for n in res.to_dict()["needs_disambiguation"]]
    assert "separator" in reasons


def test_plus_with_equal_numbers_does_not():
    res = cn.resolve("4+4", PLAIN, CHANNELS)
    assert res.resolved and not res.ambiguous_separator


def test_invalid_count_is_reported_separately():
    payload = cn.resolve("9/9", PLAIN, CHANNELS).to_dict()
    assert payload["invalid_for_template"] == {"front": 9, "back": 9}


def test_two_needs_no_special_rule():
    """Duotone, black+spot and two spots all fall out of the same search."""
    assert cn.resolve_surface(2, PLAIN, CHANNELS).invalid
    r = cn.resolve_surface(2, WITH_SPOT, CHANNELS)
    combos = {frozenset(c) for c in r.candidates}
    assert frozenset({BLACK, SPOT}) in combos
    assert frozenset({SPOT}) in combos          # two named inks


# --- against the real vocabulary ------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parents[2]
COLORS = ROOT / "terms" / "printing" / "features" / "colors"


@pytest.mark.skipif(not COLORS.exists(), reason="term data not available")
def test_real_terms_carry_channel_counts():
    terms = [json.loads(p.read_text(encoding="utf-8"))
             for p in COLORS.glob("*.jsonld") if p.stem != "_index"]
    channels = cn.channels_from_terms(terms)
    assert channels[CMYK] == 4 and channels[BLACK] == 1
    assert channels[CMYKOG] == 6 and channels[CMYKOGV] == 7
    assert channels[NONE] == 0 and channels[SPOT] == 1
    assert len(channels) == 7, "every color term needs colorChannelCount"


@pytest.mark.skipif(not COLORS.exists(), reason="term data not available")
def test_pair_notation_is_not_an_altlabel_anywhere():
    """SD-0071: pair forms are resolved, never looked up as synonyms."""
    for path in COLORS.glob("*.jsonld"):
        labels = json.loads(path.read_text(encoding="utf-8")).get("altLabels") or {}
        for lang, values in labels.items():
            for value in values:
                assert not cn._PAIR.match(value), (
                    f"{path.name} [{lang}] carries pair notation {value!r}")


@pytest.mark.skipif(not (ROOT / "terms" / "ordering" / "products").exists(),
                    reason="term data not available")
def test_resolves_against_real_product_templates():
    products = ROOT / "terms" / "ordering" / "products"
    terms = [json.loads(p.read_text(encoding="utf-8"))
             for p in COLORS.glob("*.jsonld") if p.stem != "_index"]
    channels = cn.channels_from_terms(terms)

    checked = 0
    for path in sorted(products.glob("*.jsonld")):
        supported = json.loads(path.read_text(encoding="utf-8")).get(
            "perSurfaceSupportsColorMode")
        if not supported:
            continue
        checked += 1
        res = cn.resolve("4/4", supported, channels)
        if CMYK in supported:
            assert res.resolved, f"{path.stem}: 4/4 should resolve"
        # 4/1 must never silently pick a color when several are possible
        back = cn.resolve("4/1", supported, channels).surfaces["back"]
        if BLACK in supported and SPOT in supported:
            assert back.binding is None, f"{path.stem}: 4/1 must ask, not guess"
    assert checked >= 40, "expected the templates to carry per-surface color"
