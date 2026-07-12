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

BRAND_INK = "#046A38"


def mark_svg(hexstr: str, size: int = 120, ink: str = BRAND_INK, frame: str = "spec") -> str:
    """Render the canonical fingerprint mark (ptpge-mark/2, SD-0056).

    frame/variant: "brand" | "spec" | "offer" | "job"
    (legacy: "square"->spec, "round"->offer, "corners"->job)
    """
    variant = {"square": "spec", "round": "offer", "corners": "job"}.get(frame, frame)
    h = "".join(c for c in str(hexstr).lower() if c in "0123456789abcdef")
    b = [int(h[i:i + 2], 16) for i in range(0, len(h) - 1, 2)] or [0]
    n = len(b)
    two = math.pi * 2
    rings = 3 + b[8 % n] % 3
    k1, k2 = 2 + b[0] % 6, 3 + b[3 % n] % 3
    p1, p2 = (b[4 % n] / 255) * two, (b[5 % n] / 255) * two
    a1 = (1.7 + (b[6 % n] / 255) * 1.9) * 1.35
    a2 = (0.9 + (b[7 % n] / 255) * 1.3) * 0.8
    step = 24 / (rings - 1)
    paths = ""
    for ri in range(rings):
        R, ph = 9 + ri * step, p1 + ri * 0.08
        d = ""
        for i in range(91):
            th = (i / 90) * two
            rr = R + a1 * (0.5 + R / 50) * math.sin(k1 * th + ph) + a2 * math.sin(k2 * th + p2)
            d += ("L" if i else "M") + f"{50 + rr * math.cos(th):.2f} {50 + rr * math.sin(th):.2f}"
        paths += f'<path d="{d}Z" fill="none" stroke="{ink}" stroke-width="2.2"/>'
    body = (f'<circle cx="50" cy="50" r="1.4" fill="{ink}"/>'
            f'<g transform="translate(50 50) scale(.85) translate(-50 -50)">{paths}</g>')
    if variant != "brand":
        phE = p1 + (rings - 1) * 0.08

        def _re(th):
            return (33 + a1 * (0.5 + 33 / 50) * math.sin(k1 * th + phE) + a2 * math.sin(k2 * th + p2)) * 0.85

        rt, rr_, rb, rl = _re(3 * math.pi / 2), _re(0.0), _re(math.pi / 2), _re(math.pi)
        body += (f'<line x1="50" y1="6" x2="50" y2="{50 - rt:.1f}" stroke="{ink}" stroke-width="1.5"/>'
                 f'<line x1="50" y1="{50 + rb:.1f}" x2="50" y2="94" stroke="{ink}" stroke-width="1.5"/>'
                 f'<line x1="6" y1="50" x2="{50 - rl:.1f}" y2="50" stroke="{ink}" stroke-width="1.5"/>'
                 f'<line x1="{50 + rr_:.1f}" y1="50" x2="94" y2="50" stroke="{ink}" stroke-width="1.5"/>')
    if variant == "offer":
        body += f'<circle cx="50" cy="50" r="39" fill="none" stroke="{ink}" stroke-width="1.8"/>'
    elif variant == "job":
        body += (f'<path d="M11 24V11H24" fill="none" stroke="{ink}" stroke-width="1.8"/>'
                 f'<path d="M76 11H89V24" fill="none" stroke="{ink}" stroke-width="1.8"/>'
                 f'<path d="M89 76V89H76" fill="none" stroke="{ink}" stroke-width="1.8"/>'
                 f'<path d="M24 89H11V76" fill="none" stroke="{ink}" stroke-width="1.8"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 100 100" '
            f'role="img" aria-label="PTPGE fingerprint mark">{body}</svg>')

def qr_svg(url: str, px: int = 168) -> str | None:
    """QR for the resolver URL — white tile with quiet zone, dark modules."""
    if qrcode is None:
        return None
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0)
    q.add_data(url)
    q.make(fit=True)
    m = q.modules
    n = len(m)
    d = ""
    for y, row in enumerate(m):
        for x, cell in enumerate(row):
            if cell:
                d += f"M{x} {y}h1v1h-1z"
    pad = 3
    vb = f"{-pad} {-pad} {n + 2 * pad} {n + 2 * pad}"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" viewBox="{vb}" '
        f'shape-rendering="crispEdges" role="img" aria-label="QR — PTPGE fingerprint resolver">'
        f'<rect x="{-pad}" y="{-pad}" width="{n + 2 * pad}" height="{n + 2 * pad}" fill="#ffffff" rx="2"/>'
        f'<path d="{d}" fill="#1a1a1a"/></svg>'
    )
