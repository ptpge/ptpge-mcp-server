"""ptpge-mark/3 species grammar (SD-0060 + amendment 2 in SD-0108).

cross                      = a description (spec, request, offer); job = a thing, no cross
cross in register (+)      = public with content on ptpge.org/f   (spec)
cross out of register (×)  = held by the parties                  (request, offer)
breath                     = a vendor stands behind it            (offer, job)
brand                      = none of the above
"""
import hashlib
import math
import re

import pytest

from ptpge_mcp import fingermark as fm

H = hashlib.sha256(b"test").hexdigest()
V = hashlib.sha256(b"ptpge-id/1:https://ptpge.org/v1/vendors/example-print").hexdigest()


def _lines(svg):
    out = []
    for l in re.findall(r"<line [^>]*/>", svg):
        g = {k: float(v) for k, v in re.findall(r'(x1|y1|x2|y2)="([-\d.]+)"', l)}
        out.append(g)
    return out


def _plus(svg):
    return [l for l in _lines(svg) if l["x1"] == l["x2"] == 50 or l["y1"] == l["y2"] == 50]


def _x(svg):
    return [l for l in _lines(svg) if abs(abs(l["x2"] - 50) - abs(l["y2"] - 50)) < 0.2 and l not in _plus(svg)]


def _breath(svg):
    return 'stroke-linecap="round"' in "".join(re.findall(r"<path [^>]*/>", svg))


@pytest.mark.parametrize("species,plus,x,breath", [
    ("brand", 0, 0, False),
    ("spec", 4, 0, False),
    ("request", 0, 4, False),
    ("offer", 0, 4, True),
    ("job", 0, 0, True),
])
def test_species_grammar(species, plus, x, breath):
    vendor = V if species in ("offer", "job") else None
    svg = fm.mark_svg(H, species=species, vendor=vendor)
    assert len(_plus(svg)) == plus
    assert len(_x(svg)) == x
    assert _breath(svg) is breath


def test_x_arms_stop_short_of_the_register_dots():
    arms = _x(fm.mark_svg(H, species="request", scan_frame=True))
    assert len(arms) == 4
    for a in arms:
        r_end = math.hypot(a["x2"] - 50, a["y2"] - 50)
        assert abs(r_end - fm.X_ARM_R) < 0.2
        assert r_end <= 44 * math.sqrt(2) - 8           # the corner dots sit at 44·√2 ≈ 62.2 on the diagonal; ≥ 8 u (0.8 mm at 10 mm) of air
        assert math.hypot(a["x1"] - 50, a["y1"] - 50) < r_end   # arm starts at the outer ring, points outward


def test_offer_and_job_require_vendor():
    with pytest.raises(ValueError):
        fm.mark_svg(H, species="offer")
    with pytest.raises(ValueError):
        fm.mark_svg(H, species="job")


def test_request_needs_no_vendor_and_shares_the_rings():
    spec = fm.mark_svg(H, species="spec")
    req = fm.mark_svg(H, species="request")
    brand = fm.mark_svg(H, species="brand")
    assert spec != req != brand
    rings = lambda s: re.findall(r"<path [^>]*/>", s)
    assert rings(spec) == rings(req) == rings(brand)


def test_legacy_frames_still_map():
    assert len(_plus(fm.mark_svg(H, frame="square"))) == 4            # spec
    assert len(_x(fm.mark_svg(H, frame="round", vendor=V))) == 4      # offer
    assert len(_plus(fm.mark_svg(H, frame="corners", vendor=V))) == 0  # job


def test_scan_frame_is_orthogonal_to_species():
    for sp in ("brand", "spec", "request"):
        with_dots = fm.mark_svg(H, species=sp, scan_frame=True)
        without = fm.mark_svg(H, species=sp, scan_frame=False)
        assert with_dots.count('r="2.94"') == without.count('r="2.94"') + 4
