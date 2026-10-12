"""SD-0102: pair notation on a multi-page setup — equal pair = every face, unequal pair = ask per part."""
from ptpge_mcp import colornotation as C


def test_equal_pair_binds_every_face():
    sup = ["https://ptpge.org/v1/printing/features/colors/cmyk", "https://ptpge.org/v1/printing/features/colors/black"]
    ch = {sup[0]: 4, sup[1]: 1}
    faces = ["front-cover", "inside-front-cover", "inside-pages", "inside-back-cover", "back-cover"]
    r = C.resolve_many("4/4", sup, ch, faces)
    assert r.resolved and set(r.surfaces) == set(faces)
    assert all(s.binding == (sup[0],) for s in r.surfaces.values())


def test_unequal_pair_asks_per_part():
    sup = ["https://ptpge.org/v1/printing/features/colors/cmyk", "https://ptpge.org/v1/printing/features/colors/black"]
    ch = {sup[0]: 4, sup[1]: 1}
    r = C.resolve_many("4/1", sup, ch, ["front-cover", "inside-pages"])
    assert not r.resolved
    d = r.to_dict()
    assert d["needs_disambiguation"] and "cover 4/4, inside 1/1" in d["needs_disambiguation"][0]["question"]
