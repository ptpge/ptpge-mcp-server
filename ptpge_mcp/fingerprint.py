"""ptpge-cfs/1 — canonical configuration serialization + SHA-256 fingerprint.

Server-side port of the reference implementation in the PTPGE main repo
(`tools/fingerprint.py`). Spec: docs/CONFIGURATION-FINGERPRINT.md (SD-0040).
Keep the two in sync — the spec is the contract; both implementations must
produce byte-identical canonical strings for the same resolved configuration.
"""

from __future__ import annotations

import hashlib
import re

BASE = "https://ptpge.org/v1/"
ALGORITHM = "ptpge-cfs/1"

# Variables whose multi-values are ORDER-SIGNIFICANT (layer stacks).
KNOWN_ORDERED = {
    "variables/features/surface-finish",
}

# `spec` profile excludes the commercial cluster (quantity, ...).
COMMERCIAL_PREFIX = "variables/order/"

# ptpge-cfs/1 profiles (SD-0108, 2026-10-14):
#   spec    = the product — no variables/order/* at all
#   request = spec + the order cluster (quantity, delivery, ...) — but never the vendor
#   offer   = request + variables/order/vendor (a ptpge-id/1 identity URI); one per vendor
# Each string contains the previous one. 'job' (offer + artwork sha256) follows with SD-0108 part C.
PROFILES = ("spec", "request", "offer")
VENDOR_VARIABLE = "variables/order/vendor"

_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9./-]*$")
_SURFACE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _token(uri: str) -> str:
    t = str(uri).strip()
    if t.startswith(BASE):
        t = t[len(BASE):]
    t = t.strip("/")
    if not _TOKEN_RE.match(t):
        raise ValueError(f"Invalid token (charset/case): {uri!r}")
    return t


def _number(v) -> str:
    if isinstance(v, bool):
        raise ValueError("Booleans are not valid binding values")
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("Non-finite number")
        s = repr(v)
        if "e" in s or "E" in s:
            s = format(v, "f")
        s = s.rstrip("0").rstrip(".") if "." in s else s
        return s
    raise ValueError(f"Not a number: {v!r}")


def _value_token(v) -> str:
    return _number(v) if isinstance(v, (int, float)) else _token(v)


def canonical_string(config: dict, profile: str = "spec") -> str:
    """Canonical serialization of a *resolved* configuration.

    config = {"product": <uri>, "bindings": [
        {"variable": <uri>, "value": <uri|number>},
        {"variable": <uri>, "surface": <slug>, "value": ...},
        {"variable": <uri>, "values": [...], "ordered": bool},
    ]}

    Only `variable`, `surface`, `value`/`values` and `ordered` are read. Any
    other key on a binding is deliberately ignored — notably `provenance`
    (SD-0071), which records whether a value was confirmed by the buyer or
    inferred by an agent. That describes the conversation, not the product:
    two buyers who arrive at the same configuration hold the same product
    however they got there, so provenance references the identity instead of
    constituting it, exactly as price and vendor do. Guarded by
    tests/test_cfs_conformance.py::test_provenance_never_reaches_the_hash.
    """
    if profile not in PROFILES:
        if profile == "quote":
            raise ValueError("profile 'quote' is not a cfs/1 profile; a quote carries the request fingerprint")
        raise ValueError("profile must be one of 'spec', 'request', 'offer' (SD-0108)")
    has_vendor = any(_token(b["variable"]) == VENDOR_VARIABLE for b in config.get("bindings", []))
    if profile == "offer" and not has_vendor:
        raise ValueError("profile 'offer' requires a variables/order/vendor binding (SD-0108); "
                         "an order cluster without a vendor is a 'request'")
    product = _token(config["product"])
    stmts = []
    seen = set()
    for b in config.get("bindings", []):
        var = _token(b["variable"])
        if profile == "spec" and var.startswith(COMMERCIAL_PREFIX):
            continue
        if profile == "request" and var == VENDOR_VARIABLE:
            continue
        surface = b.get("surface", "") or ""
        if surface:
            if not _SURFACE_RE.match(surface):
                raise ValueError(f"Invalid surface slug: {surface!r}")
            lhs = f"{var}@{surface}"
        else:
            lhs = var
        if lhs in seen:
            raise ValueError(f"Duplicate binding: {lhs}")
        seen.add(lhs)
        if "values" in b:
            vals = [_value_token(v) for v in b["values"]]
            ordered = b.get("ordered", var in KNOWN_ORDERED)
            rhs = ">".join(vals) if ordered else "+".join(sorted(vals))
        else:
            rhs = _value_token(b["value"])
        stmts.append((lhs, rhs))
    stmts.sort(key=lambda t: t[0])
    body = ";".join(f"{l}={r}" for l, r in stmts)
    return f"{ALGORITHM}:{profile};product={product};{body}"


def fingerprint(config: dict, profile: str = "spec") -> str:
    return hashlib.sha256(canonical_string(config, profile).encode("utf-8")).hexdigest()


def short(fp: str) -> str:
    return fp[:16]
