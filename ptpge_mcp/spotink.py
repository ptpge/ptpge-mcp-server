"""Named spot inks — SD-0104 (12.10.2026).

A spot-colour layer is not identified until it is named (SD-0071). The name is a code under a
colour matching system the vocabulary already lists (printing/standards/color-systems/
color-matching-systems/…): Pantone 300 C, HKS 43 K, RAL 5015. No list of codes is kept — the
libraries are the systems' own — so a code is checked for form, never for existence, exactly as a
grammage is a number and not a term.

    variables/features/spot-ink = <matching-system term>/<code>
    …/color-matching-systems/pantone-matching-system/300-c
    …/color-matching-systems/hks/43-k

Rule: on every face, the number of spot-ink values equals the number of spot-color layers bound in
color-mode there. Fewer → the specification asks («Which spot ink?»); more → an error (an ink
without a layer). The specification sets no upper limit on spot colours — the press does
(vendor-declaration/1 inkStations).
"""
from __future__ import annotations

import re

BASE = "https://ptpge.org/v1/"
SPOT_INK_VARIABLE = "variables/features/spot-ink"
COLOR_VARIABLE = "variables/features/color-mode"
SPOT_LAYER = "printing/features/colors/spot-color"
SYSTEMS_PREFIX = "printing/standards/color-systems/color-matching-systems/"
CODE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def tail(uri: str) -> str:
    u = str(uri or "")
    return u[len(BASE):] if u.startswith(BASE) else u.strip("/")


def normalize_code(code: str) -> str:
    """'300 C' → '300-c'; 'Pantone 300C' is the caller's job to strip to the code."""
    c = re.sub(r"[\s_]+", "-", str(code or "").strip().lower())
    c = re.sub(r"-+", "-", c).strip("-")
    return c


def make_value(system_uri: str, code: str) -> str:
    """The cfs/1 value for a named ink: system term + '/' + normalized code (relative form)."""
    return tail(system_uri).rstrip("/") + "/" + normalize_code(code)


def parse_value(value, cache=None) -> dict | None:
    """Split a spot-ink value into {system, code, systemTerm}. None if not of the form <system>/<code>
    under color-matching-systems, or the code fails the pattern. When a cache is given, the system term must exist."""
    if not isinstance(value, str):
        return None
    t = tail(value)
    if not t.startswith(SYSTEMS_PREFIX) or "/" not in t[len(SYSTEMS_PREFIX):]:
        return None
    system, _, code = t.rpartition("/")
    if not CODE_RE.match(code):
        return None
    term = cache.get_term(BASE + system) if cache is not None else None
    if cache is not None and term is None:
        return None
    return {"system": system, "code": code, "systemTerm": term}


def _values(b: dict) -> list:
    return list(b.get("values") or []) if "values" in b else [b.get("value")]


def check(bindings: list[dict], faces: list[str], cache=None, language: str = "en") -> tuple[list[dict], list[dict]]:
    """→ (errors, needs_disambiguation).

    errors: [{variable, surface, value, reason}] — invalid ink value, or an ink without a spot layer.
    needs:  [{field, surface, reason: 'spot_ink_missing', missing, question}] — spot layers without a name.
    Unscoped bindings apply to every face (SD-0083 D5); with no faces known they are compared as a whole.
    """
    spot: dict[str, int] = {}
    ink: dict[str, int] = {}
    errors: list[dict] = []
    keys = set(faces or [])
    for b in bindings:
        v = tail(b.get("variable", ""))
        sf = b.get("surface") or "*"
        if v == COLOR_VARIABLE:
            n = sum(1 for x in _values(b) if tail(x) == SPOT_LAYER)
            if n:
                spot[sf] = spot.get(sf, 0) + n
                if sf != "*":
                    keys.add(sf)
        elif v == SPOT_INK_VARIABLE:
            for x in _values(b):
                if parse_value(x, cache) is None:
                    errors.append({"variable": SPOT_INK_VARIABLE, "surface": b.get("surface") or None, "value": x,
                                   "reason": "invalid_ink_value",
                                   "note": "A spot ink is <matching-system term>/<code>, the code lower-case with hyphens — "
                                           "…/color-matching-systems/pantone-matching-system/300-c (SD-0104)."})
                    continue
                ink[sf] = ink.get(sf, 0) + 1
                if sf != "*":
                    keys.add(sf)
    needs: list[dict] = []
    if not spot and not ink:
        return errors, needs
    compare = sorted(keys) if keys else ["*"]
    for k in compare:
        n_spot = spot.get(k, 0) + (spot.get("*", 0) if k != "*" else 0)
        n_ink = ink.get(k, 0) + (ink.get("*", 0) if k != "*" else 0)
        if n_spot > n_ink:
            where = "" if k == "*" else f" on the {k}"
            needs.append({"field": SPOT_INK_VARIABLE, "surface": None if k == "*" else k, "reason": "spot_ink_missing",
                          "missing": n_spot - n_ink,
                          "question": (f"Which spot ink{'s' if n_spot - n_ink > 1 else ''}{where}? "
                                       f"{n_spot - n_ink} named ink{'s' if n_spot - n_ink > 1 else ''} needed — e.g. Pantone 300 C, HKS 43 K."),
                          "note": "A spot-color layer is not identified until it is named (SD-0071, SD-0104)."})
        elif n_ink > n_spot:
            errors.append({"variable": SPOT_INK_VARIABLE, "surface": None if k == "*" else k, "value": None,
                           "reason": "ink_without_spot_layer",
                           "note": f"{n_ink} spot ink(s) named but only {n_spot} spot-color layer(s) bound in color-mode"
                                   f"{'' if k == '*' else ' on the ' + k} — add a spot-color layer per ink (SD-0104)."})
    return errors, needs
