"""SD-0083 — one specified product, one identity.

Three rules, applied by ptpge_validate_config and enforced by ptpge_fingerprint:

1. Surfaces follow the setup model. Every setup-model term declares its faces
   (flat-sheet: front/back; folded-sheet/*: outside/inside; multi-page:
   front-cover … back-cover; roll: face/back; display-system: graphic;
   structural: outside/inside; multi-part: parts). A surface-scoped binding
   whose surface is not one of the bound setup's faces (or their panels) is
   rejected — never silently renamed, so ptpge-cfs/1 stays byte-defined.
2. No identity without the required axes. A product template lists its
   ``requiredVariables`` (what the artefact *is*) and ``recommendedVariables``
   (what it is made of / how it is finished). A missing required axis becomes
   a ``needs_disambiguation`` entry with the envelope's candidates; a missing
   recommended axis is an advisory. Where the envelope offers exactly one value
   for a required axis, it is bound as ``envelope-implied`` and written into
   the canonical string, so an agent that states it and one that omits it get
   the same fingerprint (decision D1, 16 Sept 2026).
3. Defaults come only from those entitled to them — the vendor's profile
   (``policy-default``, SD-0071). The Standard never defaults on the buyer's
   behalf; the question is the residual mechanism.

Colour (D2): required on the setup's *first* surface; other surfaces without a
statement are simply unspecified (an advisory), never defaulted.
"""
from __future__ import annotations

_BASE = "https://ptpge.org/v1/"
SETUP_VARIABLE = "variables/configuration/setup-model"
FORMAT_VARIABLE = "variables/configuration/format"
PAGE_COUNT_VARIABLE = "variables/configuration/page-count"
COLOR_VARIABLE = "variables/features/color-mode"
CUSTOM_WIDTH_VARIABLE = "variables/configuration/custom-width"
CUSTOM_HEIGHT_VARIABLE = "variables/configuration/custom-height"
CUSTOMIZED_FORMAT_URI = _BASE + "printing/configurations/formats/customized"
MULTI_SETUPS = ("setup-models/multi-page", "setup-models/multi-part")

# Variable tail -> envelope predicate holding the candidate values for a question.
CANDIDATE_ENVELOPE = {
    SETUP_VARIABLE: "supportsSetupModel",
    FORMAT_VARIABLE: "supportsFormat",
    "variables/finishing/binding": "supportsBinding",
    "variables/configuration/shape": "supportsShape",
    COLOR_VARIABLE: "perSurfaceSupportsColorMode",
    "variables/configuration/orientation": "supportsOrientation",
}

# Human question per axis (English; the agent puts it to the buyer in the
# buyer's language). Kept short and free of assumptions.
QUESTION = {
    SETUP_VARIABLE: "Which setup — for a folded product, which fold?",
    FORMAT_VARIABLE: "Which format (a named size, or custom width × height in mm)?",
    PAGE_COUNT_VARIABLE: "How many pages?",
    "variables/finishing/binding": "Which binding?",
    "variables/configuration/shape": "Which shape?",
    COLOR_VARIABLE: "Which colour set on the {surface}?",
}

SURFACE_SCOPED = {
    COLOR_VARIABLE,
    "variables/features/embellishment",
    "variables/features/surface-finish",
}


def _tail(uri: str) -> str:
    return uri[len(_BASE):] if uri.startswith(_BASE) else uri.lstrip("/")


def _full(uri_or_tail: str) -> str:
    s = str(uri_or_tail or "").strip()
    return s if s.startswith("http") else _BASE + s.lstrip("/")


def setup_faces(cache, setup_uri: str) -> tuple[list[str], list[str]]:
    """(surface ids, panel ids) declared on a setup-model term. Empty if unknown."""
    term = cache.get_term(setup_uri) or {}
    surfaces, panels = [], []
    for s in term.get("surfaces") or []:
        if not isinstance(s, dict) or not s.get("id"):
            continue
        surfaces.append(s["id"])
        for p in s.get("panels") or []:
            if isinstance(p, dict) and p.get("id"):
                panels.append(p["id"])
    return surfaces, panels


def resolve_setup(cache, product: dict, bindings: list[dict]) -> dict:
    """Which setup model is in play.

    Returns {"uri": str|None, "implied": bool, "candidates": [uri, ...]}.
    ``implied`` is True when the envelope offers exactly one setup and the
    caller did not bind it (D1)."""
    supported = [str(u) for u in (product.get("supportsSetupModel") or [])]
    for b in bindings:
        if _tail(_full(b.get("variable", ""))) == SETUP_VARIABLE:
            v = b.get("value")
            if isinstance(v, str):
                return {"uri": _full(v), "implied": False, "candidates": supported}
    if len(supported) == 1:
        return {"uri": supported[0], "implied": True, "candidates": supported}
    return {"uri": None, "implied": False, "candidates": supported}


def completeness(cache, product: dict, bindings: list[dict], ref, language: str) -> dict:
    """Apply SD-0083 to a binding list.

    ``ref(uri)`` resolves a URI to a compact labelled reference (server._ref).
    Returns a dict:
      implied           bindings to add (variable, value, provenance="envelope-implied")
      surface_errors    [{variable, surface, allowed}] — surface not on the setup
      needs_disambiguation  [{field, reason, question, candidates, ...}]
      advisories        [{type, ...}] for unspecified recommended axes
      setup             {"uri", "implied", "surfaces", "panels"}
    """
    out = {"implied": [], "surface_errors": [], "needs_disambiguation": [],
           "advisories": [], "setup": None}
    bound: dict[str, list[dict]] = {}
    for b in bindings:
        bound.setdefault(_tail(_full(b.get("variable", ""))), []).append(b)

    # 1. Setup model
    setup = resolve_setup(cache, product, bindings)
    surfaces, panels = ([], [])
    if setup["uri"]:
        surfaces, panels = setup_faces(cache, setup["uri"])
        if setup["implied"]:
            out["implied"].append({"variable": SETUP_VARIABLE, "value": setup["uri"],
                                   "provenance": "envelope-implied"})
    elif setup["candidates"]:
        out["needs_disambiguation"].append({
            "field": SETUP_VARIABLE, "reason": "required_axis_missing",
            "question": QUESTION[SETUP_VARIABLE],
            "candidates": [ref(u) for u in setup["candidates"]],
        })
    out["setup"] = {"uri": setup["uri"], "implied": setup["implied"],
                    "surfaces": surfaces, "panels": panels}
    is_multi = bool(setup["uri"]) and any(m in setup["uri"] for m in MULTI_SETUPS)

    # 2. Surfaces on surface-scoped bindings
    allowed = set(surfaces) | set(panels)
    for var, bs in bound.items():
        if var not in SURFACE_SCOPED:
            continue
        for b in bs:
            sf = b.get("surface")
            if sf:
                if allowed and sf not in allowed:
                    out["surface_errors"].append({
                        "variable": var, "surface": sf, "allowed": surfaces,
                        "note": (f"'{sf}' is not a face of this setup; the faces are "
                                 f"{', '.join(surfaces)}. Faces follow the setup model "
                                 "(SD-0083) — rename the surface, do not guess.")})
            else:
                # D5 (SD-0083 rule 1b): a face attribute stated without a face applies
                # to EVERY face of the setup — "full colour", "matte lamination" on a
                # flyer mean both sides. Expanded into one binding per face
                # (surface_provenance envelope-implied) so the two ways of saying the
                # same thing give one string. The buyer who means one side says so
                # ("4/0", "one-sided", "outside only").
                if len(surfaces) == 1:
                    b["_implied_surface"] = surfaces[0]
                elif surfaces:
                    b["_implied_surface"] = surfaces[0]
                    b["_expand_to"] = list(surfaces[1:])

    # 3. Required axes
    required = [_tail(str(u)) for u in (product.get("requiredVariables") or [])]
    if is_multi and PAGE_COUNT_VARIABLE not in required:
        required.append(PAGE_COUNT_VARIABLE)
    if not is_multi and PAGE_COUNT_VARIABLE in required and setup["uri"]:
        required.remove(PAGE_COUNT_VARIABLE)   # calendars: flat variant
    for var in required:
        if var == SETUP_VARIABLE:
            continue
        if var == COLOR_VARIABLE:
            first = surfaces[0] if surfaces else None
            have = [b for b in bound.get(var, [])
                    if not first or (b.get("surface") or b.get("_implied_surface")) == first]
            if have or not setup["uri"]:
                continue   # no setup yet → that question comes first
            env = product.get(CANDIDATE_ENVELOPE[var]) or product.get("supportsColorMode") or []
            out["needs_disambiguation"].append({
                "field": var, "surface": first, "reason": "required_axis_missing",
                "question": QUESTION[var].format(surface=first or "printed side"),
                "candidates": [ref(u) for u in env]})
            continue
        if bound.get(var):
            if var == FORMAT_VARIABLE:
                v = bound[var][0].get("value")
                if isinstance(v, str) and _full(v) == CUSTOMIZED_FORMAT_URI \
                        and not (bound.get(CUSTOM_WIDTH_VARIABLE) and bound.get(CUSTOM_HEIGHT_VARIABLE)):
                    out["needs_disambiguation"].append({
                        "field": FORMAT_VARIABLE, "reason": "required_axis_missing",
                        "question": "Custom size — width and height in mm?",
                        "candidates": []})
            continue
        env_key = CANDIDATE_ENVELOPE.get(var)
        env = [str(u) for u in (product.get(env_key) or [])] if env_key else []
        if len(env) == 1:
            out["implied"].append({"variable": var, "value": env[0], "provenance": "envelope-implied"})
            if var == FORMAT_VARIABLE and env[0] == CUSTOMIZED_FORMAT_URI \
                    and not (bound.get(CUSTOM_WIDTH_VARIABLE) and bound.get(CUSTOM_HEIGHT_VARIABLE)):
                out["needs_disambiguation"].append({
                    "field": FORMAT_VARIABLE, "reason": "required_axis_missing",
                    "question": "Custom size — width and height in mm?",
                    "candidates": []})
            continue
        entry = {"field": var, "reason": "required_axis_missing",
                 "question": QUESTION.get(var, f"Which value for {var.rsplit('/', 1)[-1]}?"),
                 "candidates": [ref(u) for u in env]}
        if var == PAGE_COUNT_VARIABLE:
            entry["datatype"] = "integer"
            if product.get("typicalPageCount"):
                entry["typical"] = product["typicalPageCount"]
        out["needs_disambiguation"].append(entry)

    # 4. Recommended axes → one advisory
    recommended = [_tail(str(u)) for u in (product.get("recommendedVariables") or [])]
    missing = [v for v in recommended if v not in bound and v != PAGE_COUNT_VARIABLE]
    if surfaces and len(surfaces) > 1 and bound.get(COLOR_VARIABLE):
        stated = set()
        for b in bound[COLOR_VARIABLE]:
            stated.add(b.get("surface") or b.get("_implied_surface"))
            stated.update(b.get("_expand_to") or [])
        unstated = [s for s in surfaces if s not in stated]
        if unstated:
            out["advisories"].append({
                "type": "surface_unspecified", "variable": COLOR_VARIABLE, "surfaces": unstated,
                "note": ("No colour stated for " + ", ".join(unstated) +
                         " — unspecified, not 'none'. A vendor's offer may fill it "
                         "(policy-default); the Standard never defaults.")})
    if missing:
        out["advisories"].append({
            "type": "unspecified_axes", "variables": missing,
            "note": ("Not stated; the spec fingerprint is computed from what was said. "
                     "A vendor's offer may complete these under policy-default (SD-0071).")})
    return out
