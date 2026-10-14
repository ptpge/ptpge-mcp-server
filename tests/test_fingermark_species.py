"""ptpge-mark/3 species grammar (SD-0060 + amendment 2 in SD-0108).

cross        = points at a product definition      (spec, request, offer)
capped cross = ... with an order cluster            (request, offer)
breath       = with a vendor                        (offer, job)
brand        = none of the above
"""
import hashlib
import re

import pytest

from ptpge_mcp import fingermark as fm

H = hashlib.sha256(b"test").hexdigest()
V = hashlib.sha256(b"ptpge-id/1:https://ptpge.org/v1/vendors/example-print").hexdigest()


def _lines(svg):
    return re.findall(r"<line [^>]*/>", svg)


def _cross(svg):
    """The four cross arms: lines that start/end on the centre axis (x=50 or y=50)."""
    return [l for l in _lines(svg) if ('x1="50"' in l and 'x2="50"' in l) or ('y1="50"' in l and 'y2="50"' in l)]


def _caps(svg):
    """The four end bars: perpendicular to the arms, sitting at 6 / 94."""
    return [l for l in _lines(svg) if l not in _cross(svg)]


def _breath(svg):
    return 'stroke-linecap="round"' in "".join(re.findall(r"<path [^>]*/>", svg))


@pytest.mark.parametrize("species,cross,caps,breath", [
    ("brand", 0, 0, False),
    ("spec", 4, 0, False),
    ("request", 4, 4, False),
    ("offer", 4, 4, True),
    ("job", 0, 0, True),
])
def test_species_grammar(species, cross, caps, breath):
    vendor = V if species in ("offer", "job") else None
    svg = fm.mark_svg(H, species=species, vendor=vendor)
    assert len(_cross(svg)) == cross
    assert len(_caps(svg)) == caps
    assert _breath(svg) is breath


def test_caps_sit_at_cross_ends_and_are_symmetric():
    svg = fm.mark_svg(H, species="request")
    caps = _caps(svg)
    assert len(caps) == 4
    c = fm.CAP_HALF
    assert any(f'x1="{50 - c:g}" y1="6"' in l for l in caps)
    assert any(f'x1="{50 - c:g}" y1="94"' in l for l in caps)
    assert any(f'x1="6" y1="{50 - c:g}"' in l for l in caps)
    assert any(f'x1="94" y1="{50 - c:g}"' in l for l in caps)


def test_offer_and_job_require_vendor():
    with pytest.raises(ValueError):
        fm.mark_svg(H, species="offer")
    with pytest.raises(ValueError):
        fm.mark_svg(H, species="job")


def test_request_needs_no_vendor_and_differs_from_spec_and_brand():
    spec = fm.mark_svg(H, species="spec")
    req = fm.mark_svg(H, species="request")
    brand = fm.mark_svg(H, species="brand")
    assert spec != req != brand
    # same rings — the species only adds strokes around them
    rings = lambda s: re.findall(r"<path [^>]*/>", s)
    assert rings(spec) == rings(req) == rings(brand)


def test_legacy_frames_still_map():
    assert len(_cross(fm.mark_svg(H, frame="square"))) == 4          # spec
    assert len(_caps(fm.mark_svg(H, frame="round", vendor=V))) == 4  # offer
    assert len(_cross(fm.mark_svg(H, frame="corners", vendor=V))) == 0  # job


def test_scan_frame_is_orthogonal_to_species():
    for sp in ("brand", "spec", "request"):
        with_dots = fm.mark_svg(H, species=sp, scan_frame=True)
        without = fm.mark_svg(H, species=sp, scan_frame=False)
        assert with_dots.count('r="2.94"') == without.count('r="2.94"') + 4
