"""ptpge_find_vendors / ptpge_find_suppliers — the answer to «who can make this?» (0.42.0, 2026-11-04).

The register (api.ptpge.org/v1/vendors, /v1/suppliers) names companies and points at their own documents. This module
reads the register, fetches every claimed vendor's declaration (or supplier's catalogue) from the company's domain —
the file is the source — and filters on what the documents say: country, product template, printing technology,
certification, substrate. It never ranks by price and never quotes: PTPGE says *who can*, the shop's own UCP/MCP door
says *for how much*. Results carry the doors an agent needs next (manifest, declaration, identity).

Everything is read-only and cached in-process for ten minutes; nothing is stored.
"""
from __future__ import annotations

import re
import threading
import time
from typing import Any
from urllib.parse import urlparse

import httpx

API = "https://api.ptpge.org/v1/"
V1 = "https://ptpge.org/v1/"
_TTL = 600.0
_lock = threading.Lock()
_cache: dict[str, tuple[float, Any]] = {}


def _get(client: httpx.Client, url: str) -> Any:
    now = time.time()
    with _lock:
        hit = _cache.get(url)
        if hit and hit[0] > now:
            return hit[1]
    try:
        r = client.get(url, headers={"Accept": "application/json, application/ld+json"})
        data = r.json() if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        data = None
    with _lock:
        _cache[url] = (now + (_TTL if data is not None else 60.0), data)
    return data


def _tail(uri: str) -> str:
    return str(uri or "").rstrip("/").rsplit("/", 1)[-1].lower()


def _path(uri: str) -> str:
    u = str(uri or "").strip()
    return u[len(V1):] if u.startswith(V1) else u.lstrip("/")


def _wants(value: str | None, uri: str) -> bool:
    """Does a term URI satisfy a filter given as full URI, /v1/ path, or bare slug? Parents match children
    (printing-technologies/digital matches digital/laser)."""
    if not value:
        return True
    v = _path(value).strip("/").lower()
    p = _path(uri).lower()
    return p == v or p.startswith(v + "/") or _tail(p) == v or p.endswith("/" + v)


def _register(client: httpx.Client, kind: str) -> list[dict]:
    idx = _get(client, f"{API}{kind}.jsonld") or {}
    out = []
    for uri in idx.get("narrower") or []:
        e = _get(client, uri.replace(V1, API) + ".jsonld")
        if isinstance(e, dict):
            out.append(e)
    return out


def _doc_url(entry: dict, kind: str) -> str | None:
    doc = entry.get("document") or {}
    if doc.get("url"):
        return str(doc["url"])
    d = (entry.get("domain") or "").strip().lower()
    if not d:
        return None
    return f"https://{d}/.well-known/ptpge/{'declaration' if kind == 'vendors' else 'catalogue'}.json"


def find_vendors(args: dict, cache=None) -> dict:
    country = (args.get("country") or "").strip().upper() or None
    product = args.get("product") or None
    technology = args.get("technology") or None
    certification = args.get("certification") or None
    substrate = args.get("substrate") or None
    text = (args.get("text") or "").strip().lower() or None
    limit = max(1, min(int(args.get("limit") or 20), 50))
    lang = args.get("language") or "en"

    results: list[dict] = []
    considered = 0
    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        for entry in _register(client, "vendors"):
            considered += 1
            ident = entry.get("id") or ""
            if not entry.get("identityClaimed"):
                continue
            url = _doc_url(entry, "vendors")
            decl = _get(client, url) if url else None
            if not isinstance(decl, dict):
                continue
            cap = decl.get("capability") or {}
            lines = [l for l in (cap.get("lines") or []) if isinstance(l, dict)]
            sites = [s for s in (decl.get("sites") or []) if isinstance(s, dict)]
            offers = [o for o in (decl.get("offerings") or []) if isinstance(o, dict)]
            countries = sorted({str(s.get("country") or "").upper() for s in sites if s.get("country")} | ({str(decl.get("country")).upper()} if decl.get("country") else set()))
            if country and country not in countries:
                continue
            techs = sorted({str(l.get("technology")) for l in lines if l.get("technology")})
            if technology and not any(_wants(technology, t) for t in techs):
                continue
            certs = sorted({str(c) for s in sites for c in (s.get("certifications") or [])} | {str(c) for c in (cap.get("certifications") or [])})
            if certification and not any(_wants(certification, c) for c in certs):
                continue
            subs = sorted({str(x.get("substrate") if isinstance(x, dict) else x) for l in lines for x in (l.get("substrates") or [])})
            if substrate and not any(_wants(substrate, s) for s in subs):
                continue
            products = sorted({str(o.get("product")) for o in offers if o.get("product")})
            # TN-2: a certification reaches an offering through its production line (lines[].certifications narrows the
            # site; absent = inherits) — a Swan-licensed shop whose UV flatbed is outside the licence does not match
            # «posters + nordic-swan». Likewise technology and substrate are judged on the offering's own line.
            def _line_of(o):
                li = o.get("line")
                return lines[li] if isinstance(li, int) and 0 <= li < len(lines) else None
            def _offer_certs(o):
                ln = _line_of(o)
                lc = ln.get("certifications") if ln else None
                return {str(c) for c in lc} if isinstance(lc, list) else set(certs)
            def _offer_ok(o):
                if product and not (o.get("product") and _wants(product, str(o["product"]))):
                    return False
                ln = _line_of(o)
                if technology and ln and not _wants(technology, str(ln.get("technology") or "")):
                    return False
                if substrate and ln and not any(_wants(substrate, str(x.get("substrate") if isinstance(x, dict) else x)) for x in (ln.get("substrates") or [])):
                    return False
                if certification and not any(_wants(certification, c) for c in _offer_certs(o)):
                    return False
                return True
            matched_offers = [o for o in offers if _offer_ok(o)]
            if (product or technology or substrate or certification) and offers and not matched_offers:
                continue
            hay = " ".join([str(decl.get("name") or ""), str(decl.get("legalName") or ""), str(decl.get("domain") or "")] + [str(s.get("city") or "") for s in sites]).lower()
            if text and text not in hay:
                continue
            host = urlparse(url).hostname if url else (decl.get("domain") or "")
            results.append({
                "identity": ident,
                "name": decl.get("name") or entry.get("label", {}).get(lang) if isinstance(entry.get("label"), dict) else decl.get("name"),
                "domain": decl.get("domain") or entry.get("domain"),
                "website": decl.get("website"),
                "countries": countries,
                "cities": sorted({str(s.get("city")) for s in sites if s.get("city")}),
                "products": products,
                "technologies": techs,
                "certifications": certs,
                "offerings": [{"product": o.get("product"), "name": o.get("name"), "minimumQuantity": o.get("minimumQuantity"),
                               "leadTimeWorkingDays": o.get("leadTimeWorkingDays")} for o in matched_offers[:12]],
                "doors": {"declaration": url, "manifest": f"https://{host}/.well-known/ucp", "register": ident},
                "modified": decl.get("modified"),
            })
            if len(results) >= limit:
                break
    return {
        "query": {k: v for k, v in (("country", country), ("product", product), ("technology", technology), ("certification", certification),
                                     ("substrate", substrate), ("text", text)) if v},
        "considered": considered, "count": len(results), "vendors": results,
        "note": ("Who can — from each shop's own published declaration (the file is the source), never ranked, never priced. "
                 "For price, lead time and an order: fetch the shop's manifest at doors.manifest and use the MCP endpoint it declares; "
                 "the spec fingerprint (ptpge_fingerprint) is the same key in every shop."),
    }


def find_suppliers(args: dict, cache=None) -> dict:
    """Makers in the register, with what their catalogue says they make (press models, paper series)."""
    makes = args.get("makes") or None           # a term path under printing/… the maker's `makes` covers
    text = (args.get("text") or "").strip().lower() or None
    limit = max(1, min(int(args.get("limit") or 20), 50))
    out: list[dict] = []
    considered = 0
    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        for entry in _register(client, "suppliers"):
            considered += 1
            mk = [str(m) for m in (entry.get("makes") or [])]
            if makes and not any(_wants(makes, m) for m in mk):
                continue
            label = entry.get("label", {}).get("en") if isinstance(entry.get("label"), dict) else entry.get("label")
            hay = " ".join([str(label or ""), str(entry.get("definition", {}).get("en", "") if isinstance(entry.get("definition"), dict) else "")] + [_tail(m).replace("-", " ") for m in mk]).lower()
            if text and text not in hay:
                continue
            url = _doc_url(entry, "suppliers") if entry.get("identityClaimed") else None
            cat = _get(client, url) if url else None
            items = [i for i in ((cat or {}).get("items") or []) if isinstance(i, dict)] if isinstance(cat, dict) else []
            out.append({"identity": entry.get("id"), "name": label, "website": entry.get("website"), "makes": mk,
                        "identityClaimed": bool(entry.get("identityClaimed")),
                        "catalogue": url if isinstance(cat, dict) else None,
                        "items": [{"kind": i.get("kind"), "name": i.get("name") or i.get("model") or i.get("label")} for i in items[:20]],
                        "itemCount": len(items)})
            if len(out) >= limit:
                break
    return {"query": {k: v for k, v in (("makes", makes), ("text", text)) if v}, "considered": considered, "count": len(out), "suppliers": out,
            "note": "Makers from the register; the catalogue (supplier-catalogue/1) is the maker's own file when the identity is claimed."}
