"""Domain check — what an agent finds when it looks for PTPGE on a domain.

One function, ``check_domain(domain, cache)``, used by three doors:

* ``GET /check``            — the browser page (checkpage.py)
* ``GET /check.json?domain=`` — raw JSON for curl and other tools
* the MCP tool ``ptpge_check_domain``

It follows exactly the path an agent follows (SD-0101):

1. ``https://<domain>/.well-known/ucp``                — the UCP manifest; does it carry a ``ptpge`` block?
2. ``ptpge.declaration`` → ``/.well-known/ptpge/declaration.json`` — the vendor declaration
3. ``ptpge.identity``    → ``https://ptpge.org/v1/vendors/<slug>``  — the register entry; does it point back?
4. ``/.well-known/ptpge/catalogue.json``                — a supplier catalogue, if the domain is a maker
5. every term URI in the documents                     — exists in the vocabulary, not deprecated

Each document is validated against its published JSON Schema, fetched from
the API (``/v1/schemas/<name>/<n>.schema.json``) and cached in-process —
the schemas are never copied into this package. Vocabulary checks use the
server's own term index (VocabularyCache).

Nothing here writes anything anywhere. The check is read-only and leaves
no trace on the domain beyond the GETs.
"""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

TERM_PREFIX = "https://ptpge.org/v1/"
SCHEMA_BASE = "https://ptpge.org/v1/schemas/"
SCHEMAS = {
    "ucp-manifest/1":       ("ucp-manifest", 1),
    "vendor-declaration/1": ("vendor-declaration", 1),
    "supplier-catalogue/1": ("supplier-catalogue", 1),
    "request/1":            ("request", 1),
    "quote/1":              ("quote", 1),
}
UCP_PATH = "/.well-known/ucp"
DECL_PATH = "/.well-known/ptpge/declaration.json"
CAT_PATH = "/.well-known/ptpge/catalogue.json"
UA = "ptpge.org check (SD-0101; https://ptpge.org/check/)"
TIMEOUT = 8.0
MAX_BYTES = 2 * 1024 * 1024
_HOST_RE = re.compile(r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


# ---------------------------------------------------------------- result

@dataclass
class Step:
    id: str
    title: str
    status: str = "pending"          # ok | warn | fail | skip
    detail: str = ""
    url: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = {"id": self.id, "title": self.title, "status": self.status, "detail": self.detail}
        if self.url:
            d["url"] = self.url
        if self.errors:
            d["errors"] = self.errors
        if self.warnings:
            d["warnings"] = self.warnings
        return d


@dataclass
class Report:
    domain: str
    steps: list[Step] = field(default_factory=list)
    sees: dict[str, Any] = field(default_factory=dict)      # what an agent sees
    missing: list[dict[str, str]] = field(default_factory=list)  # what is missing, with where to fix it
    verdict: str = "none"                                   # none | partial | ready
    checked_at: str = ""
    ms: int = 0

    def as_dict(self) -> dict:
        return {
            "domain": self.domain,
            "verdict": self.verdict,
            "summary": VERDICT_TEXT[self.verdict],
            "steps": [s.as_dict() for s in self.steps],
            "agentSees": self.sees,
            "missing": self.missing,
            "checkedAt": self.checked_at,
            "durationMs": self.ms,
            "how": "https://ptpge.org/adopt/",
        }


VERDICT_TEXT = {
    "none": "Nothing found — an agent looking for PTPGE on this domain finds no manifest and no declaration.",
    "partial": "Partly there — an agent finds PTPGE on this domain, but something is missing or invalid.",
    "ready": "Agent-ready — manifest, declaration and identity all resolve and validate.",
}


# ---------------------------------------------------------------- schema cache

_schema_lock = threading.Lock()
_schema_cache: dict[str, tuple[float, dict]] = {}
_SCHEMA_TTL = 3600.0


def _schema(client: httpx.Client, key: str) -> dict:
    name, ver = SCHEMAS[key]
    url = f"{SCHEMA_BASE}{name}/{ver}.schema.json"
    now = time.time()
    with _schema_lock:
        hit = _schema_cache.get(url)
        if hit and now - hit[0] < _SCHEMA_TTL:
            return hit[1]
    r = client.get(url, headers={"Accept": "application/schema+json, application/json"})
    r.raise_for_status()
    sch = r.json()
    with _schema_lock:
        _schema_cache[url] = (now, sch)
    return sch


def _registry(client: httpx.Client):
    from referencing import Registry, Resource  # type: ignore
    reg = Registry()
    for key in SCHEMAS:
        sch = _schema(client, key)
        reg = reg.with_resource(sch["$id"], Resource.from_contents(sch))
    return reg


def shape_errors(client: httpx.Client, key: str, doc: Any) -> list[str]:
    """Validate ``doc`` against the published schema ``key``; return error strings ($.path: message)."""
    import jsonschema  # type: ignore
    sch = _schema(client, key)
    v = jsonschema.Draft202012Validator(sch, format_checker=jsonschema.FormatChecker(), registry=_registry(client))
    out = []
    for e in sorted(v.iter_errors(doc), key=lambda e: list(e.absolute_path)):
        where = "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in e.absolute_path)
        out.append(f"{where}: {e.message[:200]}")
    return out


# ---------------------------------------------------------------- fetch

def _client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, follow_redirects=True, max_redirects=3,
                        headers={"User-Agent": UA, "Accept": "application/json, application/ld+json;q=0.9, */*;q=0.1"})


def _get_json(client: httpx.Client, url: str) -> tuple[int | None, Any, str | None]:
    """(status, parsed-or-None, error-text-or-None)."""
    try:
        r = client.get(url)
    except httpx.HTTPError as exc:
        return None, None, f"{type(exc).__name__}: {str(exc)[:160]}"
    if r.status_code != 200:
        return r.status_code, None, f"HTTP {r.status_code}"
    if len(r.content) > MAX_BYTES:
        return 200, None, f"larger than {MAX_BYTES // 1024} KB"
    try:
        return 200, r.json(), None
    except ValueError:
        return 200, None, "not JSON"


# ---------------------------------------------------------------- vocabulary walk

def _iter_term_uris(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str) and k.startswith(TERM_PREFIX):
                yield (f"{path}.{k}", k)
            yield from _iter_term_uris(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _iter_term_uris(v, f"{path}[{i}]")
    elif isinstance(node, str) and node.startswith(TERM_PREFIX):
        yield (path, node)


def _vocab_check(doc: dict, cache, step: Step, skip: set[str]) -> int:
    """Every term URI in ``doc`` must exist in the vocabulary; deprecated ones warn. Returns count checked."""
    n = 0
    if cache is None:
        return 0
    seen: set[str] = set()
    for path, uri in _iter_term_uris(doc):
        if uri in skip or uri.startswith((TERM_PREFIX + "suppliers/", TERM_PREFIX + "vendors/", TERM_PREFIX + "schemas/")):
            continue
        if uri in seen:
            continue
        seen.add(uri)
        n += 1
        term = cache.get_term(uri) if cache is not None else None
        if term is None:
            step.errors.append(f"{path}: unknown term {uri.removeprefix(TERM_PREFIX)}")
        elif term.get("status") == "deprecated":
            succ = term.get("replacedBy")
            step.warnings.append(f"{path}: {uri.removeprefix(TERM_PREFIX)} is deprecated" + (f" → {str(succ).removeprefix(TERM_PREFIX)}" if succ else ""))
    return n


def _label(cache, uri: str) -> str:
    t = cache.get_term(uri) if cache is not None else None
    if not t:
        return uri.removeprefix(TERM_PREFIX)
    lab = t.get("prefLabel") or t.get("label") or {}
    if isinstance(lab, dict):
        return lab.get("en") or next(iter(lab.values()), uri.removeprefix(TERM_PREFIX))
    return str(lab)


# ---------------------------------------------------------------- the check

def normalise_domain(raw: str) -> str | None:
    s = (raw or "").strip().lower()
    if "://" in s:
        s = urlparse(s).hostname or ""
    s = s.split("/", 1)[0].split(":", 1)[0].strip(".")
    if s.startswith("www."):
        s = s[4:]
    return s if _HOST_RE.match(s) else None


def check_domain(domain: str, cache=None) -> dict:
    t0 = time.time()
    host = normalise_domain(domain)
    rep = Report(domain=host or domain)
    rep.checked_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not host:
        rep.steps.append(Step("domain", "Domain", "fail", "Not a valid hostname — try e.g. trykkverk.no"))
        rep.ms = int((time.time() - t0) * 1000)
        return rep.as_dict()

    with _client() as client:
        decl_url_from_manifest: str | None = None
        identity_from_manifest: str | None = None

        # 1 — UCP manifest -------------------------------------------------
        s1 = Step("ucp", "UCP manifest", url=f"https://{host}{UCP_PATH}")
        status, manifest, err = _get_json(client, s1.url)
        if manifest is None:
            s1.status = "fail"
            s1.detail = f"Not found ({err})." if status != 200 else f"Found, but {err}."
            rep.missing.append({"what": f"A UCP manifest at {UCP_PATH}", "why": "This is the first thing a checkout agent fetches; without it the shop is invisible to UCP.", "where": "https://ptpge.org/adopt/"})
        elif not isinstance(manifest, dict) or "ptpge" not in manifest:
            s1.status = "warn"
            s1.detail = "Found a UCP manifest, but it has no `ptpge` block — the agent sees a shop, not a printer."
            rep.missing.append({"what": "A `ptpge` block in the UCP manifest", "why": "The block tells the agent where the printer's identity, declaration and vocabulary are.", "where": "https://ptpge.org/v1/schemas/ucp-manifest/1"})
        else:
            try:
                errs = shape_errors(client, "ucp-manifest/1", manifest)
            except Exception as exc:  # schema fetch failed — report, do not crash the check
                errs = [f"schema unavailable: {exc}"]
            s1.errors = errs
            blk = manifest.get("ptpge") or {}
            decl_url_from_manifest = blk.get("declaration") if isinstance(blk, dict) else None
            identity_from_manifest = blk.get("identity") if isinstance(blk, dict) else None
            if decl_url_from_manifest and (urlparse(decl_url_from_manifest).hostname or "") != host:
                s1.errors.append(f"ptpge.declaration points at {urlparse(decl_url_from_manifest).hostname}, not {host} — same domain expected")
            if "print_profile" in manifest:
                s1.warnings.append("`print_profile` found — capability belongs in the declaration, not the manifest (SD-0101)")
            caps = (manifest.get("ucp") or {}).get("capabilities") or {}
            has_cap = "org.ptpge.print.identity" in caps if isinstance(caps, dict) else False
            if not has_cap:
                s1.warnings.append("capability org.ptpge.print.identity not declared under ucp.capabilities")
            s1.status = "fail" if s1.errors else ("warn" if s1.warnings else "ok")
            s1.detail = ("Valid ucp-manifest/1 with a ptpge block." if s1.status == "ok"
                         else f"ucp-manifest/1: {len(s1.errors)} error(s), {len(s1.warnings)} warning(s).")
            if s1.errors:
                rep.missing.append({"what": "A manifest that validates against ucp-manifest/1", "why": "; ".join(s1.errors[:3]), "where": "https://ptpge.org/v1/schemas/ucp-manifest/1"})
        rep.steps.append(s1)

        # 2 — vendor declaration ------------------------------------------
        decl_url = decl_url_from_manifest or f"https://{host}{DECL_PATH}"
        s2 = Step("declaration", "Vendor declaration", url=decl_url)
        status, decl, err = _get_json(client, decl_url)
        declared_identity: str | None = None
        if decl is None:
            s2.status = "fail"
            s2.detail = f"Not found ({err})." if status != 200 else f"Found, but {err}."
            rep.missing.append({"what": f"A vendor declaration at {DECL_PATH}", "why": "This is where the agent reads presses, substrates and offerings — the printer's own statement of what it can do.", "where": "https://ptpge.org/adopt/"})
        elif not isinstance(decl, dict):
            s2.status = "fail"
            s2.detail = "Found, but not a JSON object."
        else:
            try:
                errs = shape_errors(client, "vendor-declaration/1", decl)
            except Exception as exc:
                errs = [f"schema unavailable: {exc}"]
            s2.errors = errs
            if not errs:
                declared_identity = decl.get("identity")
                if decl.get("domain") != host:
                    s2.errors.append(f"domain says {decl.get('domain')!r}, but the document is served from {host}")
                if urlparse(decl_url).path != DECL_PATH:
                    s2.errors.append(f"served from {urlparse(decl_url).path}, the known path is {DECL_PATH}")
                if identity_from_manifest and declared_identity and identity_from_manifest != declared_identity:
                    s2.errors.append(f"manifest says identity {identity_from_manifest}, declaration says {declared_identity}")
                # semantic checks mirrored from tools/validate_declaration.py
                lines = ((decl.get("capability") or {}).get("lines")) or []
                for i, off in enumerate(decl.get("offerings") or []):
                    pt = cache.get_term(off.get("product", "")) if cache is not None else None
                    if pt is not None and pt.get("elementType") != "product":
                        s2.errors.append(f"offerings[{i}].product is not a product template")
                    if isinstance(off.get("line"), int) and off["line"] >= len(lines):
                        s2.errors.append(f"offerings[{i}].line = {off['line']} but capability.lines has {len(lines)} entries")
                    for var in (off.get("supports") or {}):
                        vt = cache.get_term(var) if cache is not None else None
                        if vt is not None and vt.get("level") != "element":
                            s2.errors.append(f"offerings[{i}].supports: {var.removeprefix(TERM_PREFIX)} is not a variable")
                n = _vocab_check(decl, cache, s2, skip={declared_identity} if declared_identity else set())
                s2.detail = f"Valid vendor-declaration/1 · {n} term URIs checked." if not s2.errors else f"vendor-declaration/1: {len(s2.errors)} error(s)."
                if cache is None:
                    s2.warnings.append("vocabulary not checked (no term index)")
                # what the agent sees
                offs = decl.get("offerings") or []
                presses = ((decl.get("capability") or {}).get("presses")) or []
                subs = ((decl.get("capability") or {}).get("substrates")) or []
                rep.sees = {
                    "name": decl.get("name"),
                    "identity": declared_identity,
                    "country": decl.get("country"),
                    "vendorTypes": decl.get("vendorTypes"),
                    "products": [{"template": _label(cache, o.get("product", "")), "uri": o.get("product")} for o in offs],
                    "productCount": len(offs),
                    "pressCount": len(presses),
                    "substrateCount": len(subs),
                    "lineCount": len(lines),
                    "modified": decl.get("modified"),
                }
            else:
                s2.detail = f"Does not validate against vendor-declaration/1: {len(errs)} error(s)."
                rep.missing.append({"what": "A declaration that validates against vendor-declaration/1", "why": "; ".join(errs[:3]), "where": "https://ptpge.org/v1/schemas/vendor-declaration/1"})
            s2.status = "fail" if s2.errors else ("warn" if s2.warnings else "ok")
        rep.steps.append(s2)

        # 3 — identity in the register -------------------------------------
        ident = declared_identity or identity_from_manifest
        s3 = Step("identity", "Identity in the register", url=ident)
        if not ident:
            s3.status = "skip"
            s3.detail = "No identity to check — none declared."
        elif not ident.startswith(TERM_PREFIX + "vendors/"):
            s3.status = "fail"
            s3.detail = f"{ident} is not a vendor identity (expected https://ptpge.org/v1/vendors/<slug>)."
        else:
            api_ident = ident.replace("https://ptpge.org/v1/", "https://api.ptpge.org/v1/", 1)
            status, entry, err = _get_json(client, api_ident + ".jsonld")
            if entry is None:
                status, entry, err = _get_json(client, api_ident)
            if not isinstance(entry, dict):
                s3.status = "fail"
                s3.detail = f"Not in the register ({err}). The identity is claimed in the declaration but ptpge.org does not know it."
                rep.missing.append({"what": "A register entry for the identity", "why": "An identity is permanent only once the register points at the domain; claim it on the adopt page.", "where": "https://ptpge.org/adopt/"})
            else:
                reg_domain = (entry.get("domain") or "").strip().lower()
                if reg_domain and reg_domain != host:
                    s3.status = "fail"
                    s3.detail = f"Register entry exists but points at {reg_domain}, not {host}."
                else:
                    s3.status = "ok"
                    s3.detail = f"Register entry found and it points at {host}." if reg_domain else "Register entry found."
                    rep.sees.setdefault("registerName", entry.get("name") or entry.get("prefLabel"))
        rep.steps.append(s3)

        # 4 — supplier catalogue (optional) ---------------------------------
        s4 = Step("catalogue", "Supplier catalogue (makers only)", url=f"https://{host}{CAT_PATH}")
        status, cat, err = _get_json(client, s4.url)
        if cat is None:
            s4.status = "skip"
            s4.detail = "None — expected only for mills, press and equipment makers."
        elif not isinstance(cat, dict):
            s4.status = "fail"
            s4.detail = "Found, but not a JSON object."
        else:
            try:
                errs = shape_errors(client, "supplier-catalogue/1", cat)
            except Exception as exc:
                errs = [f"schema unavailable: {exc}"]
            s4.errors = errs
            if not errs:
                items = cat.get("items") or []
                ids = [it.get("id") for it in items]
                dup = sorted({x for x in ids if ids.count(x) > 1})
                if dup:
                    s4.errors.append(f"duplicate item ids {dup}")
                for i, it in enumerate(items):
                    if it.get("parent") and it["parent"] not in ids:
                        s4.errors.append(f"items[{i}].parent {it['parent']} is not an item in this catalogue")
                n = _vocab_check(cat, cache, s4, skip={cat.get("identity")})
                s4.detail = f"Valid supplier-catalogue/1 · {len(items)} items · {n} term URIs checked."
                rep.sees["catalogueItems"] = len(items)
            else:
                s4.detail = f"Does not validate against supplier-catalogue/1: {len(errs)} error(s)."
            s4.status = "fail" if s4.errors else ("warn" if s4.warnings else "ok")
        rep.steps.append(s4)

    # verdict ----------------------------------------------------------------
    core = [s for s in rep.steps if s.id in ("ucp", "declaration", "identity")]
    if all(s.status == "fail" or s.status == "skip" for s in core) and rep.steps[1].status == "fail":
        rep.verdict = "none"
    elif all(s.status in ("ok", "warn") for s in core) and rep.steps[3].status != "fail" and not rep.missing:
        rep.verdict = "ready"
    else:
        rep.verdict = "partial"
    rep.ms = int((time.time() - t0) * 1000)
    return rep.as_dict()
