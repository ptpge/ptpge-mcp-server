"""Artwork as a source — SD-0107 (13.10.2026).

A print PDF knows some things about the product it is the pages of. This module reads those —
deterministically, from the file's own structures, never from pictures — and returns vocabulary
bindings with provenance "artwork", plus the questions the file cannot answer.

    read_pdf(data: bytes, cache) -> {
        "artwork":   {sha256, size, pages, mediaType},
        "page":      {trimMm: [w, h], bleedMm, uniform: bool, boxes: "TrimBox"|"MediaBox"},
        "bindings":  [ {variable, value|values, surface?, provenance: "artwork", from: "..."} ],
        "fromFile":  [ "format: A5 (148 × 210 mm) — TrimBox", ... ],
        "toAsk":     [ {variable, hint} ],
        "warnings":  [ ... ],
        "colour":    {perPage: [...], faces: {...}},
    }

Binds (SD-0107 §1): format or customized + custom-width/height; page-count; colour per face
(cmyk / black / spot-color with named inks → spot-ink); print-standard from a PDF/X output
intent. Never binds (§2): fold, binding, paper, finish, quantity — those are returned as toAsk
with the file's hint. Never stores (§3): the caller passes bytes; nothing is written.
"""
from __future__ import annotations

import hashlib
import io
import re

BASE = "https://ptpge.org/v1/"
MM = 25.4 / 72.0
FORMAT_VAR = "variables/configuration/format"
WIDTH_VAR = "variables/configuration/custom-width"
HEIGHT_VAR = "variables/configuration/custom-height"
PAGES_VAR = "variables/configuration/page-count"
COLOR_VAR = "variables/features/color-mode"
INK_VAR = "variables/features/spot-ink"
STD_VAR = "variables/compliance/print-standard"
CUSTOMIZED = "printing/configurations/formats/customized"
CMYK = "printing/features/colors/cmyk"
BLACK = "printing/features/colors/black"
SPOT = "printing/features/colors/spot-color"
WHITE = "printing/features/colors/white"
SYSTEMS = "printing/standards/color-systems/color-matching-systems/"
STANDARDS = "printing/standards/print-standards/"
PROCESS_NAMES = {"cyan", "magenta", "yellow", "black", "all", "none", "registration"}
MAX_BYTES = 25 * 1024 * 1024

# OutputConditionIdentifier / Info substrings → print-standard term tail
_OUTPUT_INTENTS = [
    ("fogra39", "fogra39"), ("fogra 39", "fogra39"), ("fogra51", "fogra51"), ("fogra 51", "fogra51"),
    ("fogra52", "fogra52"), ("fogra 52", "fogra52"), ("gracol", "gracol-2013"), ("swop", "swop"),
    ("japan color 2011", "japan-color-2011"), ("japancolor2011", "japan-color-2011"),
    ("crpc1", "crpc1"), ("crpc2", "crpc2"), ("crpc3", "crpc3"), ("crpc4", "crpc4"), ("crpc5", "crpc5"),
    ("crpc6", "crpc6"), ("crpc7", "crpc7"), ("iso 12647-2", "iso-12647-2"), ("iso12647-2", "iso-12647-2"),
]


def _ink_system(name: str) -> tuple[str, str] | None:
    """'PANTONE 300 C' → ('pantone-matching-system', '300-c'); 'HKS 43 K' → ('hks', '43-k'); 'RAL 5015' → ('ral', '5015')."""
    n = name.strip()
    m = re.match(r"^(?:pantone|pms)\s*[®]?\s*(.+)$", n, re.I)
    if m:
        code = re.sub(r"[\s_]+", "-", m.group(1).strip().lower())
        code = re.sub(r"[^a-z0-9-]", "", code).strip("-")
        return ("pantone-matching-system", code) if code else None
    m = re.match(r"^hks\s*(.+)$", n, re.I)
    if m:
        code = re.sub(r"[^a-z0-9-]", "", re.sub(r"[\s_]+", "-", m.group(1).strip().lower())).strip("-")
        return ("hks", code) if code else None
    m = re.match(r"^ral\s*(\d{4})\b", n, re.I)
    if m:
        return ("ral", m.group(1))
    return None


def _walk_colorspaces(pdf, page, seen_xobj: set) -> tuple[set, list, bool]:
    """→ (process set {'cmyk','gray','rgb'}, [separation names], has_image). Walks the page's resources
    and its form XObjects (one level deep, by object id) — the structures a RIP reads, not the pixels."""
    import pikepdf
    process: set = set()
    seps: list = []
    has_image = False

    def cs_name(cs):
        try:
            if isinstance(cs, pikepdf.Name):
                return str(cs)
            if isinstance(cs, pikepdf.Array) and len(cs):
                return str(cs[0])
        except Exception:
            pass
        return ""

    def note_cs(cs):
        nonlocal process, seps
        try:
            fam = cs_name(cs)
            if fam in ("/DeviceCMYK",):
                process.add("cmyk")
            elif fam in ("/DeviceGray", "/CalGray"):
                process.add("gray")
            elif fam in ("/DeviceRGB", "/CalRGB", "/Lab"):
                process.add("rgb")
            elif fam == "/ICCBased" and isinstance(cs, pikepdf.Array) and len(cs) > 1:
                n = int(cs[1].get("/N", 0))
                process.add({4: "cmyk", 3: "rgb", 1: "gray"}.get(n, "rgb"))
            elif fam == "/Separation" and isinstance(cs, pikepdf.Array) and len(cs) > 1:
                seps.append(str(cs[1]).lstrip("/").replace("#20", " "))
            elif fam == "/DeviceN" and isinstance(cs, pikepdf.Array) and len(cs) > 1:
                for nm in cs[1]:
                    seps.append(str(nm).lstrip("/").replace("#20", " "))
            elif fam == "/Indexed" and isinstance(cs, pikepdf.Array) and len(cs) > 1:
                note_cs(cs[1])
        except Exception:
            pass

    def walk(res, depth=0):
        nonlocal has_image
        if res is None or depth > 2:
            return
        try:
            for _k, cs in (res.get("/ColorSpace") or {}).items():
                note_cs(cs)
        except Exception:
            pass
        try:
            for _k, xo in (res.get("/XObject") or {}).items():
                try:
                    oid = xo.objgen
                except Exception:
                    oid = None
                if oid in seen_xobj:
                    continue
                if oid is not None:
                    seen_xobj.add(oid)
                st = str(xo.get("/Subtype", ""))
                if st == "/Image":
                    has_image = True
                    if "/ColorSpace" in xo:
                        note_cs(xo["/ColorSpace"])
                elif st == "/Form":
                    walk(xo.get("/Resources"), depth + 1)
        except Exception:
            pass

    walk(page.get("/Resources"))
    return process, seps, has_image


def _content_uses_colour_ops(page) -> set:
    """Operators in the content stream say which device spaces are painted with: k/K → CMYK, g/G → gray, rg/RG → RGB."""
    import pikepdf
    used: set = set()
    try:
        for _operands, op in pikepdf.parse_content_stream(page):
            o = str(op)
            if o in ("k", "K"):
                used.add("cmyk")
            elif o in ("g", "G"):
                used.add("gray")
            elif o in ("rg", "RG"):
                used.add("rgb")
    except Exception:
        pass
    return used


def _format_match(cache, w: float, h: float):
    """The vocabulary format whose stated width/height equal the trim (±1 mm), either way round. None if none."""
    best = None
    for uri, t in (cache.all_terms() if cache is not None else {}).items():
        if "/configurations/formats/" not in uri:
            continue
        p = t.get("properties") or {}
        fw, fh = p.get("width"), p.get("height")
        if not isinstance(fw, (int, float)) or not isinstance(fh, (int, float)):
            continue
        unit = str(p.get("unit") or "mm").lower()
        if unit == "cm":
            fw, fh = fw * 10, fh * 10
        elif unit in ("in", "inch"):
            fw, fh = fw * 25.4, fh * 25.4
        elif unit == "ft":
            fw, fh = fw * 304.8, fh * 304.8
        elif unit != "mm":
            continue
        if (abs(fw - w) <= 1 and abs(fh - h) <= 1) or (abs(fw - h) <= 1 and abs(fh - w) <= 1):
            lab = (t.get("label") or t.get("prefLabel") or {}).get("en") or uri.rsplit("/", 1)[-1]
            cand = {"uri": uri[len(BASE):], "label": lab, "width": fw, "height": fh}
            # prefer the exact orientation, then the shortest URI (series member over oddities)
            score = (0 if (abs(fw - w) <= 1 and abs(fh - h) <= 1) else 1, len(uri))
            if best is None or score < best[0]:
                best = (score, cand)
    return best[1] if best else None


def read_pdf(data: bytes, cache=None, language: str = "en") -> dict:
    import pikepdf
    if len(data) > MAX_BYTES:
        return {"error": "too_large", "note": f"PDF larger than {MAX_BYTES // (1024 * 1024)} MB"}
    sha = hashlib.sha256(data).hexdigest()
    try:
        pdf = pikepdf.open(io.BytesIO(data))
    except Exception as e:
        return {"error": "not_a_pdf", "note": str(e)[:200]}
    out: dict = {"artwork": {"sha256": sha, "size": len(data), "mediaType": "application/pdf", "pages": len(pdf.pages)},
                 "bindings": [], "fromFile": [], "toAsk": [], "warnings": []}
    n = len(pdf.pages)
    if n == 0:
        return {"error": "empty_pdf"}

    # --- geometry: TrimBox (else MediaBox), per page --------------------------------------------
    sizes, bleeds, box_used = [], [], "TrimBox"
    for pg in pdf.pages:
        tb = pg.get("/TrimBox") or pg.get("/CropBox") or pg.get("/MediaBox")
        mb = pg.get("/MediaBox")
        if "/TrimBox" not in pg:
            box_used = "MediaBox"
        try:
            x0, y0, x1, y1 = [float(v) for v in tb]
            w, h = abs(x1 - x0) * MM, abs(y1 - y0) * MM
            rot = int(pg.get("/Rotate", 0)) % 360
            if rot in (90, 270):
                w, h = h, w
            sizes.append((round(w, 1), round(h, 1)))
            if "/TrimBox" in pg and mb is not None:
                mx0, my0, mx1, my1 = [float(v) for v in mb]
                bleeds.append(round(max(0.0, (abs(mx1 - mx0) * MM - abs(x1 - x0) * MM) / 2), 1))
        except Exception:
            sizes.append((0.0, 0.0))
    first = sizes[0]
    uniform = all(abs(s[0] - first[0]) <= 1 and abs(s[1] - first[1]) <= 1 for s in sizes)
    out["page"] = {"trimMm": [first[0], first[1]], "boxes": box_used, "uniform": uniform,
                   "bleedMm": (round(sum(bleeds) / len(bleeds), 1) if bleeds else None), "sizes": sizes[:8]}
    if not uniform:
        out["warnings"].append("Pages differ in size — the first page's trim is used; check whether this is one product.")
    if box_used == "MediaBox":
        out["warnings"].append("No TrimBox in the file — the MediaBox is read as the trim; bleed cannot be told from trim.")

    w, h = first
    fm = _format_match(cache, w, h) if w and h else None
    if fm:
        out["bindings"].append({"variable": FORMAT_VAR, "value": fm["uri"], "provenance": "artwork", "from": box_used})
        out["fromFile"].append(f"format: {fm['label']} — {w:g} × {h:g} mm ({box_used})")
    elif w and h:
        out["bindings"].append({"variable": FORMAT_VAR, "value": CUSTOMIZED, "provenance": "artwork", "from": box_used})
        out["bindings"].append({"variable": WIDTH_VAR, "value": min(w, h), "provenance": "artwork", "from": box_used})
        out["bindings"].append({"variable": HEIGHT_VAR, "value": max(w, h), "provenance": "artwork", "from": box_used})
        out["fromFile"].append(f"size: {w:g} × {h:g} mm — no named format of that size, bound as customized ({box_used})")
    if out["page"]["bleedMm"]:
        out["fromFile"].append(f"bleed: {out['page']['bleedMm']:g} mm (MediaBox − TrimBox)")

    # --- pages ------------------------------------------------------------------------------------
    out["bindings"].append({"variable": PAGES_VAR, "value": n, "provenance": "artwork", "from": "page tree"})
    out["fromFile"].append(f"pages: {n}")

    # --- colour per page ----------------------------------------------------------------------------
    seen_xobj: set = set()
    per_page = []
    for i, pg in enumerate(pdf.pages):
        process, seps, has_img = _walk_colorspaces(pdf, pg, seen_xobj)
        process |= _content_uses_colour_ops(pg)
        inks = []
        for s in seps:
            if s.lower() in PROCESS_NAMES:
                if s.lower() in ("cyan", "magenta", "yellow"):
                    process.add("cmyk")
                elif s.lower() == "black":
                    process.add("gray")
                continue
            if s not in inks:
                inks.append(s)
        per_page.append({"page": i + 1, "process": sorted(process), "spotInks": inks, "hasImage": has_img})
    out["colour"] = {"perPage": per_page[:64]}
    rgb_pages = [p["page"] for p in per_page if "rgb" in p["process"]]
    if rgb_pages:
        out["warnings"].append(f"RGB colour on page(s) {', '.join(str(x) for x in rgb_pages[:6])} — not a print colour space; read as process colour, confirm with the printer.")

    def layers(p):
        vals = []
        if "cmyk" in p["process"] or "rgb" in p["process"]:
            vals.append(CMYK)
        elif "gray" in p["process"]:
            vals.append(BLACK)
        vals += [SPOT] * len(p["spotInks"])
        return vals

    # faces: 1 page → front; 2 pages → front/back; n>2 → cover/inside by first & rest (reported, bound without surface)
    if n == 1:
        p = per_page[0]
        vals = layers(p)
        if vals:
            out["bindings"].append({"variable": COLOR_VAR, "values": vals, "surface": "front", "provenance": "artwork", "from": "page 1 colour spaces"})
            out["fromFile"].append("colour, front: " + _say(vals, p["spotInks"]))
        out["toAsk"].append({"variable": COLOR_VAR, "surface": "back", "hint": "One page in the file — is the back blank (4/0), or printed?"})
    elif n == 2:
        for face, p in zip(("front", "back"), per_page):
            vals = layers(p)
            if vals:
                out["bindings"].append({"variable": COLOR_VAR, "values": vals, "surface": face, "provenance": "artwork", "from": f"page {p['page']} colour spaces"})
                out["fromFile"].append(f"colour, {face}: " + _say(vals, p["spotInks"]))
    else:
        allv: list = []
        for p in per_page:
            for v in layers(p):
                if v not in allv or v == SPOT:
                    allv.append(v)
        # one binding without a surface — applies to every face (SD-0083 D5); a per-part colour is a question
        uniq = []
        for v in allv:
            if v not in uniq:
                uniq.append(v)
        spots = sum(1 for p in per_page for _ in p["spotInks"])
        vals = [v for v in uniq if v != SPOT] + ([SPOT] * len({s for p in per_page for s in p["spotInks"]}))
        if vals:
            out["bindings"].append({"variable": COLOR_VAR, "values": vals, "provenance": "artwork", "from": "colour spaces across pages"})
            out["fromFile"].append("colour, all pages: " + _say(vals, sorted({s for p in per_page for s in p["spotInks"]})))
        if any("cmyk" in p["process"] for p in per_page) and any(p["process"] == ["gray"] for p in per_page):
            out["toAsk"].append({"variable": COLOR_VAR, "hint": "Some pages are colour, some black only — is the cover 4/4 and the inside 1/1?"})
    # named inks → spot-ink (SD-0104)
    all_inks = []
    for p in per_page:
        for s in p["spotInks"]:
            if s not in all_inks:
                all_inks.append(s)
    for s in all_inks:
        sysc = _ink_system(s)
        if sysc:
            v = SYSTEMS + sysc[0] + "/" + sysc[1]
            b = {"variable": INK_VAR, "value": v, "provenance": "artwork", "from": f"Separation «{s}»"}
            if n == 1:
                b["surface"] = "front"
            elif n == 2:
                b["surface"] = "front" if s in per_page[0]["spotInks"] else "back"
            out["bindings"].append(b)
            out["fromFile"].append(f"spot ink: {s} → {sysc[0]}/{sysc[1]}")
        else:
            out["toAsk"].append({"variable": INK_VAR, "hint": f"The file names a separation «{s}» — which matching system is that (Pantone, HKS, RAL)?"})
    if not any("cmyk" in p["process"] or "gray" in p["process"] or "rgb" in p["process"] or p["spotInks"] for p in per_page):
        out["warnings"].append("The file declares no colour spaces — colour must be asked.")
        out["toAsk"].append({"variable": COLOR_VAR, "hint": "Printed in which colours? The file does not say."})

    # --- output intent → print standard ---------------------------------------------------------------
    try:
        intents = pdf.Root.get("/OutputIntents") or []
        for it in intents:
            ident = str(it.get("/OutputConditionIdentifier", "")) + " " + str(it.get("/Info", "")) + " " + str(it.get("/OutputCondition", ""))
            low = ident.lower()
            for key, tail in _OUTPUT_INTENTS:
                if key in low:
                    out["bindings"].append({"variable": STD_VAR, "value": STANDARDS + tail, "provenance": "artwork", "from": "PDF/X OutputIntent"})
                    out["fromFile"].append(f"print standard: {tail.upper()} (OutputIntent «{ident.strip()[:60]}»)")
                    break
            else:
                if ident.strip():
                    out["warnings"].append(f"OutputIntent «{ident.strip()[:60]}» is not a print standard the vocabulary names.")
            break
    except Exception:
        pass

    # --- what the file cannot say (SD-0107 §2) ------------------------------------------------------
    if n > 2:
        out["toAsk"].append({"variable": "variables/configuration/setup-model", "hint": f"{n} pages of {w:g} × {h:g} mm — a booklet or book (multi-page)? The file does not say how it is bound."})
        out["toAsk"].append({"variable": "variables/finishing/binding", "hint": "Saddle-stitched, perfect bound, wire-o?"})
    elif n == 2 and w and h:
        out["toAsk"].append({"variable": "variables/configuration/setup-model", "hint": "Two pages — a flat sheet printed both sides, or a folded sheet? The file does not say."})
    else:
        out["toAsk"].append({"variable": "variables/configuration/setup-model", "hint": "Flat sheet, or folded? The file does not say."})
    out["toAsk"].append({"variable": "variables/substrate/substrate-weight", "hint": "Which paper and weight (gsm)? A PDF never says."})
    out["toAsk"].append({"variable": "variables/features/surface-finish", "hint": "Lamination or varnish? Not in the file."})
    out["toAsk"].append({"variable": "variables/order/quantity", "hint": "How many copies?"})
    out["note"] = ("Bound only what the file states in its own structures (boxes, colour spaces, output intent). "
                   "Folds, binding, paper, finish and quantity are never inferred from a PDF — they are asked (SD-0107). "
                   "Nothing is stored; only the hash travels.")
    return out


def _say(vals: list, inks: list) -> str:
    parts = []
    if CMYK in vals:
        parts.append("CMYK")
    if BLACK in vals:
        parts.append("black")
    ns = vals.count(SPOT)
    if ns:
        parts.append(f"{ns} spot" + ("s" if ns > 1 else "") + (" (" + ", ".join(inks) + ")" if inks else ""))
    return " + ".join(parts) if parts else "—"
