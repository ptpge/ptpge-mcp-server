"""ptpge-mark/1 + QR helpers for ptpge_fingerprint visuals.

Mark: python port of tools/ptpge-fingermark.js (frozen spec ptpge-mark/1,
SD-0053) — deterministic, monochrome, recognition-only.
QR: encodes the resolver permalink https://ptpge.org/f/{hash} (SD-0052).
`qrcode` is an optional dependency: if absent, qr_svg() returns None and the
tool simply omits the QR — the service never breaks.
"""
from __future__ import annotations

import math

try:  # optional
    import qrcode
except ImportError:  # pragma: no cover
    qrcode = None

BRAND_INK = "#111111"   # the mark is always black on PTPGE (Patrik 12.10.2026); the tile around it white


AMP_CLASSES = (2.6, 3.5, 4.4)

# ptpge-mark/3 amendment 2 (SD-0108, 14.10.2026): the cross has two positions.
# In register (+, on the axes) = registered with the specification (spec,
# offer — as SD-0060 says). Out of register (×, turned 45°) = not registered:
# a request, which a vendor's offer turns into register. Breath = vendor
# (offer, job). Brand carries none. The × arms run from the outer ring to
# X_ARM_R on the diagonals — short of the corner register dots at 44·√2 ≈ 62 (Patrik 15.10: the longer arm).
X_ARM_R = 50.0
CROSS_W = 1.47
JOIN = 1.0   # the cross arms end this far INSIDE the outer ring's centreline — they join the ring, no air gap (Patrik 15.10)
SPECIES = ("brand", "spec", "request", "offer", "job")


def _params(hexstr: str):
    h = "".join(c for c in str(hexstr).lower() if c in "0123456789abcdef")
    b = [int(h[i:i + 2], 16) for i in range(0, len(h) - 1, 2)] or [0]
    L = len(b)
    rings = 3 + b[8 % L] % 3
    k1 = 2 + b[0] % 6
    k2 = 3 + b[3 % L] % 3
    p1 = b[4 % L] / 255 * 2 * math.pi
    p2 = b[5 % L] / 255 * 2 * math.pi
    a1c = (1.7 + b[6 % L] / 255 * 1.9) * 1.35
    a1 = min(AMP_CLASSES, key=lambda v: abs(v - a1c))
    a2 = (0.9 + b[7 % L] / 255 * 1.3) * 0.8
    return b, rings, k1, k2, p1, p2, a1, a2


def _breath_gaps(vbytes, ri, ring_count):
    gaps = []
    if ri >= ring_count - 1:
        return gaps
    for s in range(12):
        slot = ri * 12 + s
        th = (s / 12 + 0.04 * ri) * 2 * math.pi
        d_ax = min(th % (math.pi / 2), math.pi / 2 - (th % (math.pi / 2)))
        if d_ax < 0.16:
            continue
        if (vbytes[slot >> 3] >> (slot & 7)) & 1:
            gaps.append(th)
    return gaps


def _mark3_body(hexstr, ink, species, vendor, scan_frame):
    """ptpge-mark/3 (SD-0060, amendment 2 in SD-0108). Cross in register (+)
    = registered (spec, offer); cross out of register (×) = a request;
    breath = with a vendor (offer, job); brand = none. Outermost ring always
    whole."""
    legacy = {"square": "spec", "round": "offer", "corners": "job"}
    species = legacy.get(species, species)
    if species not in SPECIES:
        species = "spec"
    needs_vendor = species in ("offer", "job")
    if needs_vendor and not vendor:
        raise ValueError(f"ptpge-mark/3: species {species!r} requires a vendor hash")
    _, rings, k1, k2, p1, p2, a1, a2 = _params(hexstr)
    vb = None
    if needs_vendor:
        vh = "".join(c for c in str(vendor).lower() if c in "0123456789abcdef")
        vb = [int(vh[i:i + 2], 16) for i in range(0, len(vh) - 1, 2)] or [0]
    R0, R1 = 10, 33
    step = (R1 - R0) / (rings - 1)
    paths = ""
    for ri in range(rings):
        R = R0 + ri * step
        ph = p1 + ri * 0.08
        gaps = _breath_gaps(vb, ri, rings) if vb else []

        def in_gap(th):
            for g in gaps:
                d = abs(th - g)
                if d > math.pi:
                    d = 2 * math.pi - d
                if d < 2.6 / R:
                    return True
            return False

        seg = []
        segs = []
        for i in range(181):
            th = i / 180 * 2 * math.pi
            if in_gap(th):
                if len(seg) > 1:
                    segs.append(seg)
                seg = []
                continue
            rr = R + a1 * (0.5 + R / 50) * math.sin(k1 * th + ph) + a2 * math.sin(k2 * th + p2)
            seg.append(f"{50 + rr * math.cos(th):.2f} {50 + rr * math.sin(th):.2f}")
        if not gaps:
            paths += f'<path d="M{"L".join(seg)}Z" fill="none" stroke="{ink}" stroke-width="2.2"/>'
        else:
            if len(seg) > 1:
                segs.append(seg)
            for sg in segs:
                paths += f'<path d="M{"L".join(sg)}" fill="none" stroke="{ink}" stroke-width="2.2" stroke-linecap="round"/>'
    body = f'<circle cx="50" cy="50" r="2.94" fill="{ink}"/>' + paths
    phE = p1 + (rings - 1) * 0.08

    def _re(th):
        return R1 + a1 * (0.5 + R1 / 50) * math.sin(k1 * th + phE) + a2 * math.sin(k2 * th + p2)

    if species in ("spec", "offer"):
        body += (f'<line x1="50" y1="6" x2="50" y2="{50 - _re(3 * math.pi / 2) + JOIN:.1f}" stroke="{ink}" stroke-width="{CROSS_W}"/>'
                 f'<line x1="50" y1="{50 + _re(math.pi / 2) - JOIN:.1f}" x2="50" y2="94" stroke="{ink}" stroke-width="{CROSS_W}"/>'
                 f'<line x1="6" y1="50" x2="{50 - _re(math.pi) + JOIN:.1f}" y2="50" stroke="{ink}" stroke-width="{CROSS_W}"/>'
                 f'<line x1="{50 + _re(0) - JOIN:.1f}" y1="50" x2="94" y2="50" stroke="{ink}" stroke-width="{CROSS_W}"/>')
    if species == "request":  # cross out of register: four arms on the diagonals, ring edge → X_ARM_R
        for th in (math.pi / 4, 3 * math.pi / 4, 5 * math.pi / 4, 7 * math.pi / 4):
            r0 = _re(th) - JOIN
            body += (f'<line x1="{50 + r0 * math.cos(th):.1f}" y1="{50 + r0 * math.sin(th):.1f}" '
                     f'x2="{50 + X_ARM_R * math.cos(th):.1f}" y2="{50 + X_ARM_R * math.sin(th):.1f}" '
                     f'stroke="{ink}" stroke-width="{CROSS_W}"/>')
    if scan_frame:
        for x, y in ((6, 6), (94, 6), (94, 94), (6, 94)):
            body += f'<circle cx="{x}" cy="{y}" r="2.94" fill="{ink}"/>'
    return body


def mark_svg(hexstr: str, size: int = 120, ink: str = BRAND_INK, frame: str = "spec", scan_frame: bool = False, species: str | None = None, vendor: str | None = None) -> str:
    """Render the canonical fingerprint mark (ptpge-mark/3, SD-0060)."""
    body = _mark3_body(hexstr, ink, frame if species is None else species, vendor, scan_frame)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 100 100" '
            f'role="img" aria-label="PTPGE fingerprint mark {str(hexstr)[:16]}">{body}</svg>')


def qr_svg(url: str, px: int = 168, origin_dot: bool = True,
           ecc: str = "M", ink: str = "#111111") -> str | None:
    """QR for the resolver URL — white tile, quiet zone 4 modules (SD-0065).

    The ORIGIN DOT (SD-0065, adopted 2026-08-20) is the QR family identity:
    a dot of Ø 3 modules in a square 5×5-module white knockout at the centre
    (~2 % of the area — safe at ECC M). It is the same fixed fiducial that
    anchors every ptpge-mark (r 2.94 in the 100×100 frame). spec/offer URLs
    carry the complete 64-hex fingerprint at ECC M; job short URLs use ECC H.
    """
    if qrcode is None:
        return None
    levels = {"L": qrcode.constants.ERROR_CORRECT_L,
              "M": qrcode.constants.ERROR_CORRECT_M,
              "Q": qrcode.constants.ERROR_CORRECT_Q,
              "H": qrcode.constants.ERROR_CORRECT_H}
    q = qrcode.QRCode(error_correction=levels.get(ecc.upper(), levels["M"]), border=0)
    q.add_data(url)
    q.make(fit=True)
    m = q.modules
    n = len(m)
    c = (n - 1) / 2  # centre module index (18 for version 5, n=37)
    d = ""
    for y, row in enumerate(m):
        for x, cell in enumerate(row):
            if origin_dot and abs(x - c) <= 2 and abs(y - c) <= 2:
                continue  # square 5x5-module knockout
            if cell:
                d += f"M{x} {y}h1v1h-1z"
    pad = 4  # quiet zone, SD-0065
    vb = f"{-pad} {-pad} {n + 2 * pad} {n + 2 * pad}"
    dot = (f'<circle cx="{c + 0.5:g}" cy="{c + 0.5:g}" r="1.5" fill="{ink}"/>'
           if origin_dot else "")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" viewBox="{vb}" '
        f'shape-rendering="crispEdges" role="img" aria-label="QR — PTPGE fingerprint resolver">'
        f'<rect x="{-pad}" y="{-pad}" width="{n + 2 * pad}" height="{n + 2 * pad}" fill="#ffffff" rx="2"/>'
        f'<path d="{d}" fill="{ink}"/>{dot}</svg>'
    )


def stamp_svg(register_line: str, ident: str, qr_url: str, px: int = 360,
              ecc: str = "M", ink: str = "#111111") -> str | None:
    """The identity stamp (SD-0065): QR + two text lines BELOW —
    register line first, then the 16-char identifier in semibold.
    register_line e.g. 'spec: ptpge.org/f' · ident e.g. hash[:16]."""
    if qrcode is None:
        return None
    inner = qr_svg(qr_url, px=100, origin_dot=True, ecc=ecc, ink=ink)
    import re as _re
    mvb = _re.search(r'viewBox="([^"]+)"', inner)
    body = _re.search(r'>(.*)</svg>$', inner, _re.S).group(1)
    mono = 'font-family="ui-monospace, Menlo, Consolas, monospace"'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{int(px * 1.24)}" '
        f'viewBox="0 0 100 124" role="img" aria-label="GutenLex identity stamp {ident}">'
        f'<svg x="0" y="0" width="100" height="100" viewBox="{mvb.group(1)}" '
        f'shape-rendering="crispEdges">{body}</svg>'
        f'<text x="50" y="109" text-anchor="middle" {mono} font-size="6.2" '
        f'fill="{ink}">{register_line}</text>'
        f'<text x="50" y="119" text-anchor="middle" {mono} font-size="6" '
        f'font-weight="600" fill="{ink}">{ident}</text></svg>'
    )
