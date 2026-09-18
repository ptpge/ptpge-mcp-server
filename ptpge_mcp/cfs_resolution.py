"""ptpge-cfs/1 — resolution of a configuration before canonicalization (SD-0083).

Reference implementation. Byte-identical copies live in
  mcp-server/ptpge_mcp/cfs_resolution.py
  ptpge-configurator/src/ptpge_configurator/cfs_resolution.py
  engine-backend/cfs_resolution.py
and tests/test_cfs_conformance.py refuses drift between them.

`ptpge-cfs/1` hashes a *resolved* configuration. Canonicalization is a pure
function of its input; resolution is the step that turns what a buyer or an
agent said into that input, and it is data-dependent: it reads the product
template (its envelope, its required axes) and the setup-model terms (their
faces). Two implementations given the same statement and the same Standard
data MUST produce the same resolved configuration — otherwise "one specified
product, one identity" would hold only inside one program.

Rules (spec: docs/CONFIGURATION-FINGERPRINT.md § 11):

  R1  Surfaces follow the setup. The setup model is the bound one, or the
      only one the template supports (then it is bound, envelope-implied).
      A surface-scoped binding whose surface is not a face (or panel) of that
      setup is an error — no identity.
  R2  A surface-scoped variable stated without a surface applies to every
      face of the setup: it is expanded to one binding per face (D5).
  R3  Every required axis of the template must be bound. Where the envelope
      offers exactly one value, that value is bound (envelope-implied, D1).
      Otherwise the configuration is incomplete — no identity, a question.
      Colour is required on the setup's first face. A customized format
      requires custom-width and custom-height. Page count is required for
      multi-page / multi-part setups and never for the others.
  R4  Resolution is idempotent: resolving a resolved configuration changes
      nothing.
  R5  Entailment. A value under printing/substrates/<class>/<material>/
      (a paper surface, weight class, coating, colour shade …) entails
      substrate-type = printing/substrates/<class>/<material>. If the
      substrate type is unbound it is bound (entailed); if it is bound to a
      different material the configuration is in error — no identity.
      Nothing else is entailed: resolution adds what follows from the
      statement, never what the buyer did not say.

Bindings use the cfs/1 form: {"variable", "surface"?, "value"|"values", "ordered"?}.
Any other key (provenance, notes) is carried through untouched.
"""
from __future__ import annotations

from typing import Callable

BASE = "https://ptpge.org/v1/"
SETUP = "variables/configuration/setup-model"
FORMAT = "variables/configuration/format"
PAGE_COUNT = "variables/configuration/page-count"
COLOR = "variables/features/color-mode"
CUSTOM_WIDTH = "variables/configuration/custom-width"
CUSTOM_HEIGHT = "variables/configuration/custom-height"
CUSTOMIZED_FORMAT = BASE + "printing/configurations/formats/customized"
MULTI_SETUPS = ("setup-models/multi-page", "setup-models/multi-part")
SUBSTRATE_TYPE = "variables/substrate/substrate-type"
SUBSTRATES = "printing/substrates/"

# Variables whose vocabulary term carries scope = "surface".
SURFACE_SCOPED = frozenset({
    COLOR,
    "variables/features/embellishment",
    "variables/features/surface-finish",
})

# Required axis → template predicate holding its candidate values.
ENVELOPE_OF = {
    SETUP: "supportsSetupModel",
    FORMAT: "supportsFormat",
    "variables/finishing/binding": "supportsBinding",
    "variables/configuration/shape": "supportsShape",
    "variables/configuration/orientation": "supportsOrientation",
    COLOR: "supportsColorMode",
}


def tail(uri: str) -> str:
    s = str(uri or "").strip()
    return s[len(BASE):] if s.startswith(BASE) else s.strip("/")


def full(uri_or_tail: str) -> str:
    s = str(uri_or_tail or "").strip()
    return s if s.startswith("http") else BASE + s.lstrip("/")


def faces_of(setup_term: dict | None) -> tuple[list[str], list[str]]:
    """(surface ids, panel ids) declared on a setup-model term."""
    surfaces, panels = [], []
    for s in (setup_term or {}).get("surfaces") or []:
        if not isinstance(s, dict) or not s.get("id"):
            continue
        surfaces.append(s["id"])
        for p in s.get("panels") or []:
            if isinstance(p, dict) and p.get("id"):
                panels.append(p["id"])
    return surfaces, panels


def entailed_substrate_type(value) -> str | None:
    """R5: the material a substrate value sits under, or None.

    printing/substrates/sheet-materials/paper/paper-surfaces/silk-paper
      -> https://ptpge.org/v1/printing/substrates/sheet-materials/paper
    A value that *is* a class or material (four segments or fewer) entails
    nothing; literals (weights, thicknesses) entail nothing.
    """
    if not isinstance(value, str):
        return None
    t = tail(value)
    if not t.startswith(SUBSTRATES):
        return None
    seg = t.split("/")
    if len(seg) < 5:
        return None
    return full("/".join(seg[:4]))


def resolve(product: dict, bindings: list[dict],
            setup_term: Callable[[str], dict | None]) -> dict:
    """Resolve `bindings` for `product` (the raw template term).

    `setup_term(uri)` returns the setup-model term (dict) or None.

    Returns
      ok          True when the configuration may be fingerprinted
      bindings    the resolved binding list (input order, surfaces filled and
                  expanded, envelope-implied bindings appended)
      implied     [{variable, value}] bound by R1/R3 (full URIs)
      expanded    [{variable, surfaces}] bindings expanded by R2
      errors      [{rule, variable, ...}] — R1 (surface_not_in_setup) and
                  R5 (substrate_type_conflict) violations
      incomplete  [{variable, surface?, candidates}] — R3 questions
      setup       the setup URI in force, or None
    """
    out = {"ok": False, "bindings": [], "implied": [], "expanded": [],
           "errors": [], "incomplete": [], "setup": None}
    bindings = [dict(b) for b in bindings or []]
    bound: dict[str, list[dict]] = {}
    for b in bindings:
        bound.setdefault(tail(b.get("variable", "")), []).append(b)

    # R1 — setup model
    supported = [str(u) for u in (product.get("supportsSetupModel") or [])]
    setup = None
    for b in bound.get(SETUP, []):
        if isinstance(b.get("value"), str):
            setup = full(b["value"])
            break
    if setup is None and len(supported) == 1:
        setup = supported[0]
        out["implied"].append({"variable": full(SETUP), "value": setup})
    if setup is None and supported:
        out["incomplete"].append({"variable": full(SETUP), "candidates": supported})
    out["setup"] = setup
    surfaces, panels = faces_of(setup_term(setup)) if setup else ([], [])
    allowed = set(surfaces) | set(panels)
    is_multi = bool(setup) and any(m in setup for m in MULTI_SETUPS)

    # R1 (faces) + R2 (expansion)
    resolved: list[dict] = []
    for b in bindings:
        var = tail(b.get("variable", ""))
        sf = b.get("surface") or None
        if var in SURFACE_SCOPED:
            if sf:
                if allowed and sf not in allowed:
                    out["errors"].append({"rule": "surface_not_in_setup", "variable": full(var),
                                          "surface": sf, "allowed": list(surfaces)})
                resolved.append(b)
            elif surfaces:
                for i, face in enumerate(surfaces):
                    nb = dict(b)
                    nb["surface"] = face
                    resolved.append(nb)
                if len(surfaces) > 1:
                    out["expanded"].append({"variable": full(var), "surfaces": list(surfaces)})
            else:
                resolved.append(b)          # setup unknown: cannot place it (incomplete anyway)
        else:
            resolved.append(b)

    # R3 — required axes
    required = [tail(str(u)) for u in (product.get("requiredVariables") or [])]
    if is_multi and PAGE_COUNT not in required:
        required.append(PAGE_COUNT)
    if setup and not is_multi and PAGE_COUNT in required:
        required.remove(PAGE_COUNT)
    first = surfaces[0] if surfaces else None
    for var in required:
        if var == SETUP:
            continue                          # handled above
        if var == COLOR:
            if not setup:
                continue                      # the setup question comes first
            have = [b for b in resolved if tail(b.get("variable", "")) == COLOR
                    and (not first or b.get("surface") == first)]
            if not have:
                env = [str(u) for u in (product.get("perSurfaceSupportsColorMode")
                                        or product.get("supportsColorMode") or [])]
                out["incomplete"].append({"variable": full(COLOR), "surface": first,
                                          "candidates": env})
            continue
        if bound.get(var):
            if var == FORMAT:
                v = bound[FORMAT][0].get("value")
                if isinstance(v, str) and full(v) == CUSTOMIZED_FORMAT \
                        and not (bound.get(CUSTOM_WIDTH) and bound.get(CUSTOM_HEIGHT)):
                    out["incomplete"].append({"variable": full(FORMAT), "candidates": [],
                                              "needs": [full(CUSTOM_WIDTH), full(CUSTOM_HEIGHT)]})
            continue
        key = ENVELOPE_OF.get(var)
        env = [str(u) for u in (product.get(key) or [])] if key else []
        if len(env) == 1:
            out["implied"].append({"variable": full(var), "value": env[0]})
            if var == FORMAT and env[0] == CUSTOMIZED_FORMAT \
                    and not (bound.get(CUSTOM_WIDTH) and bound.get(CUSTOM_HEIGHT)):
                out["incomplete"].append({"variable": full(FORMAT), "candidates": [],
                                          "needs": [full(CUSTOM_WIDTH), full(CUSTOM_HEIGHT)]})
            continue
        out["incomplete"].append({"variable": full(var), "candidates": env})

    # R5 — entailment: a value under a material entails the substrate type
    entailed: dict[str, str] = {}
    for b in bindings:
        var = tail(b.get("variable", ""))
        if var == SUBSTRATE_TYPE:
            continue
        vals = [b.get("value")] if "value" in b else list(b.get("values") or [])
        for v in vals:
            m = entailed_substrate_type(v)
            if m:
                entailed.setdefault(m, full(var))
    if entailed:
        stated = [full(b["value"]) for b in bound.get(SUBSTRATE_TYPE, [])
                  if isinstance(b.get("value"), str)]
        materials = sorted(entailed)
        if len(materials) > 1 or (stated and stated[0] not in materials):
            out["errors"].append({"rule": "substrate_type_conflict", "variable": full(SUBSTRATE_TYPE),
                                  "stated": stated, "entailed": materials,
                                  "from": [entailed[m] for m in materials]})
        elif not stated:
            out["implied"].append({"variable": full(SUBSTRATE_TYPE), "value": materials[0],
                                   "entailedBy": entailed[materials[0]]})

    for ib in out["implied"]:
        resolved.append({"variable": ib["variable"], "value": ib["value"]})
    out["bindings"] = resolved
    out["ok"] = not out["errors"] and not out["incomplete"]
    return out


def local_setup_term_loader(terms_root):
    """`setup_term` callable over a terms/ or dist/v1 directory (tools, tests)."""
    import json
    from pathlib import Path
    root = Path(terms_root)

    def load(uri: str):
        rel = tail(uri)
        for cand in (root / f"{rel}.jsonld", root / rel / "_index.jsonld"):
            if cand.exists():
                try:
                    return json.loads(cand.read_text(encoding="utf-8"))
                except Exception:
                    return None
        return None
    return load
