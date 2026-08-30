"""Worded sided-notation (coverage run 2026-08-30): buyers say the words."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from ptpge_mcp import colornotation as cn

SUP = [cn.CMYK, cn.BLACK, cn.NONE, cn.SPOT]
CH = {cn.CMYK: 4, cn.BLACK: 1, cn.SPOT: 1}


def test_single_sided_binds_back_to_none_and_asks_front():
    r = cn.resolve("single-sided", SUP, CH)
    assert r.surfaces["back"].binding == (cn.NONE,)
    assert r.surfaces["front"].binding is None
    assert not r.resolved
    q = r.to_dict()["needs_disambiguation"]
    assert len(q) == 1 and q[0]["surface"] == "front"


def test_double_sided_asks_for_the_pair_never_guesses():
    r = cn.resolve("double-sided", SUP, CH)
    assert not r.resolved
    needs = r.to_dict()["needs_disambiguation"]
    assert {n["surface"] for n in needs} == {"front", "back"}


def test_word_variants_parse():
    for t in ("one-sided", "simplex", "two sided", "duplex", "both sides",
              "Single sided printing", "2-sided"):
        cn.parse_pair(t)  # må ikke kaste


def test_numeric_pairs_unchanged():
    assert cn.resolve("4/4", SUP, CH).resolved
    assert cn.resolve("4/0", SUP, CH).resolved


def test_unrelated_text_still_rejected():
    import pytest
    with pytest.raises(cn.NotationError):
        cn.parse_pair("matte lamination")
