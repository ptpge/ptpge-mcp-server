"""PTPGE MCP server — exposes the PTPGE Standard (Layer 1 vocabulary) via the Model Context Protocol.

v0.4.0 — four new tools (tool surface v2, additive):
    - ptpge_browse                — hierarchy navigation (children of a node;
      top concepts when called without arguments)
    - ptpge_get_product_envelope  — the complete Configuration Envelope of a
      product class in one call, with resolved labels (saves agents 10+
      get_term round-trips when composing)
    - ptpge_validate_config       — Layer 1 ENVELOPE validation: bindings vs
      supports*, numeric gsm -> weight band via minWeight/maxWeight
      properties, data-driven advisories (creasing thresholds from the
      scoring term). Deliberately not full legality — that is Layer 2,
      licensed; this free tool is its demonstration.
    - ptpge_fingerprint           — canonical ptpge-cfs/1 serialization +
      SHA-256 in both profiles (spec/offer), per SD-0040. Server-side port
      in ptpge_mcp/fingerprint.py, verified byte-identical against the
      reference implementation's worked example.
    Original three tools unchanged. Playground gains a "test-prompt demo"
    card that chains envelope -> validate -> fingerprint live.

v0.3.3 — browser playground at /playground:
    A self-contained HTML test console (ptpge_mcp/playground.py) served
    same-origin, whose buttons POST real JSON-RPC tools/call messages to
    /mcp — letting anyone exercise search/get_term/get_version from a
    browser with zero install. Demo URL for partners:
    https://open.mcp.ptpge.org/playground (behind Basic Auth on the
    stealth server, like every other route).

v0.3.2 — tokenized, language-agnostic search:
    ptpge_search_terms previously matched the whole query string as one
    substring against a single language's label, so multi-word queries
    ("trekkspill accordion fold") and cross-language queries (Norwegian
    "trekkspill" with default language=en) silently returned nothing.
    Search now splits the query into tokens (AND semantics) and matches
    across ALL language variants of label/altLabels; the language
    parameter only controls which prefLabel is returned. Essential for
    the Norwegian v1 test-prompt and for non-English agents generally.

v0.3.1 — SSE transport toggle (PTPGE_MCP_SSE=0):
    On a PUBLIC endpoint, any client that opens /sse occupies a Passenger
    worker forever — one stray curl can wedge the whole app (observed
    2026-06-05: claude.ai connector retries against /sse kept re-wedging
    fresh workers seconds after every pkill). With PTPGE_MCP_SSE=0 the
    /sse route answers 410 Gone with a pointer to /mcp instead of opening
    a stream. Set it on the open mirror; leave unset on the stealth server
    where Basic Auth limits who can connect.

v0.3.0 — Streamable HTTP transport at /mcp (stateless JSON mode):
    The SSE transport keeps one HTTP connection open per client for the
    lifetime of the session. Behind cPanel/Passenger on shared hosting the
    app gets very few worker processes, so a single long-lived SSE client
    occupies a worker permanently and every other request queues behind it
    (observed 2026-06-05: claude.ai connector probes left hanging SSE
    streams and ALL requests took 60+ seconds).

    /mcp implements the MCP Streamable HTTP transport in *stateless JSON*
    mode: every JSON-RPC message is one short-lived POST with a plain
    application/json response. No sessions, no server-initiated streams,
    no persistent connections — a perfect impedance match for Passenger,
    and the transport claude.ai custom connectors prefer.

    Implemented directly on Starlette (not via the SDK's
    StreamableHTTPSessionManager) because the a2wsgi bridge Passenger
    requires does not run ASGI lifespan events, which the SDK session
    manager depends on. The protocol surface we need is small: initialize,
    ping, tools/list, tools/call, plus empty resources/prompts lists and
    202 for notifications.

    /sse remains mounted for backwards compatibility (MCP Inspector,
    mcp-remote bridges). New integrations should use /mcp.

    Also new: X-Robots-Tag "noindex, nofollow" on every response (parity
    with api/internal subdomains; Stealth Mode hygiene).

v0.2.6 — cPanel-friendly per-recipient env var pattern:
    Config loader now auto-detects PTPGE_<NAME>_AUTH_USER +
    PTPGE_<NAME>_AUTH_PASS pairs and treats each pair as one Basic Auth
    credential. Easier to add, revoke, and rotate individual recipients
    via the cPanel environment-variables UI than the v0.2.5 comma-
    separated PTPGE_MCP_AUTH_USERS approach (which also still works,
    taking precedence when explicitly set). The legacy PTPGE_MCP_AUTH_USER +
    PTPGE_MCP_AUTH_PASS pair is captured automatically by the pattern
    (NAME="MCP"), so deployments configured with only the legacy
    variables continue to work without changes.

v0.2.5 — multi-user Basic Auth for tracked Stealth Mode access:
    BasicAuthMiddleware now accepts a list of (username, password) pairs
    and treats a request as authenticated if it matches any of them. The
    Config object reads PTPGE_MCP_AUTH_USERS (comma-separated
    `user:pass,user:pass,...`) when set, falling back to legacy
    PTPGE_MCP_AUTH_USER/_PASS otherwise. This enables per-recipient
    credentials for selective revocation and access tracking, documented
    in external-references/access-log.md and the credentials-sharing
    policy section of SD-0014.

v0.2.4 — two production fixes:
    1. Critical: removed em-dash from the WWW-Authenticate realm string.
       HTTP header values are encoded as latin-1, so any non-ASCII
       character (em-dash, en-dash, smart quotes) triggers
       UnicodeEncodeError when the response is serialised, causing
       every unauthenticated request to return 500 instead of 401.
    2. Added GET / root banner so the base URL returns a friendly JSON
       descriptor (200 OK) instead of a bare 404 to clients that probe
       the domain.

v1 tool surface unchanged (per SD-0010 and MCP-tool-surface-v1.md):

    - ptpge_search_terms — free-text search over the vocabulary
    - ptpge_get_term     — full context for a single term
    - ptpge_get_version  — current dataset version and statistics

Stealth Mode HTTP Basic Auth is enforced at the application layer (Starlette
middleware) because cPanel/Passenger bypasses Apache .htaccess auth for
Python apps. Credentials come from PTPGE_MCP_AUTH_USER / PTPGE_MCP_AUTH_PASS
environment variables; if unset, the server runs unauthenticated.

Run locally:
    python -m ptpge_mcp.server

Deploy on cPanel Passenger:
    The Passenger entry point at the project root (`passenger_wsgi.py`) imports
    the ASGI app from this module and bridges it via a2wsgi. Passenger spawns
    the app on a dynamic port — there is no fixed port 8000 in this mode.
"""

import base64
import json
import logging
import os
import secrets

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Mount, Route

from . import __version__
from .config import Config
from .data import VocabularyCache
from .fingerprint import canonical_string as _cfs_canonical, fingerprint as _cfs_fingerprint, short as _cfs_short
from .playground import PLAYGROUND_HTML

logger = logging.getLogger(__name__)


def _chat_cors_headers() -> dict:
    """CORS headers for the /chat AI-panel endpoint. Origin defaults to '*'
    (the shared token gates cost); set PTPGE_CHAT_ORIGIN to the dashboard
    origin to lock it down."""
    return {
        "Access-Control-Allow-Origin": os.getenv("PTPGE_CHAT_ORIGIN", "*"),
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "content-type, x-ptpge-chat-token",
        "Access-Control-Max-Age": "86400",
        "Vary": "Origin",
    }


# ---------------------------------------------------------------------------
# Basic Auth middleware — Stealth Mode gatekeeper
# ---------------------------------------------------------------------------

class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests without valid HTTP Basic Auth credentials.

    v0.2.5+: supports multiple credential pairs simultaneously. A request
    is accepted if its `Authorization` header matches **any** configured
    credential. This enables per-recipient credentials for tracked
    Stealth Mode access (see external-references/access-log.md).

    Activated when at least one credential pair is configured via either:

      - PTPGE_MCP_AUTH_USERS (multi-user: comma-separated `user:pass` pairs)
      - PTPGE_MCP_AUTH_USER + PTPGE_MCP_AUTH_PASS (legacy single-user)

    Passes through transparently if no credentials are configured, so local
    development and post-launch open access remain frictionless.

    Uses `secrets.compare_digest` for constant-time comparison against
    every configured credential, to avoid leaking auth timing for any
    individual credential.
    """

    # HTTP header values must be latin-1 encodable. We pin this to a strict
    # ASCII subset and verify at construction time so any drift back to
    # smart-punctuation gets caught at import, not at the first 401.
    _REALM = "PTPGE MCP Stealth Mode"

    def __init__(self, app, credentials: list[tuple[str, str]] | None = None) -> None:
        super().__init__(app)
        credentials = credentials or []
        self._enabled = bool(credentials)
        self._expected_tokens: list[str] = []
        for username, password in credentials:
            if not username or not password:
                continue
            token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
            self._expected_tokens.append(f"Basic {token}")
        # If credentials were provided but all dropped during validation,
        # disable auth rather than locking the server with an empty list.
        if not self._expected_tokens:
            self._enabled = False
        # Fail loudly if anyone later edits the realm with non-ASCII text.
        try:
            self._REALM.encode("ascii")
        except UnicodeEncodeError as e:  # pragma: no cover
            raise RuntimeError(
                "BasicAuthMiddleware._REALM contains non-ASCII characters and "
                "cannot be sent as an HTTP header value. Use plain hyphens "
                "and straight quotes."
            ) from e

    async def dispatch(self, request: Request, call_next):
        if not self._enabled:
            return await call_next(request)

        provided = request.headers.get("authorization", "")
        # Constant-time compare against every configured credential.
        # We always run the full loop to avoid timing leaks about which
        # credential (if any) matched.
        match = False
        for token in self._expected_tokens:
            if secrets.compare_digest(provided, token):
                match = True
        if not match:
            return Response(
                content="Unauthorized\n",
                status_code=401,
                # NOTE: HTTP header values are encoded as latin-1, so the realm
                # string must be ASCII-only. The class-level _REALM constant is
                # asserted ASCII at construction time, so any drift back to
                # smart-punctuation is caught immediately at app import.
                headers={"WWW-Authenticate": f'Basic realm="{self._REALM}"'},
            )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Tool descriptors — kept module-level so they can be unit-tested without
# spinning up the full Starlette app.
# ---------------------------------------------------------------------------

TOOL_DESCRIPTORS: list[Tool] = [
    Tool(
        name="ptpge_search_terms",
        description=(
            "Free-text search over the PTPGE Standard vocabulary. Returns a ranked list "
            "of matching terms with their URI, notation, preferred label, "
            "level (top-concept / group / category / sub-category / element), "
            "group, and a relevance score (0.0–1.0)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Free-text query. Matched against notation, label, altLabels, and definition.",
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Maximum number of results to return.",
                },
                "groups": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional filter by group code(s), e.g. "
                        "[\"substrates\", \"configurations\"]. Omit for all groups."
                    ),
                },
                "language": {
                    "type": "string",
                    "default": "en",
                    "description": "ISO 639-1 language code for label and definition matching.",
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="ptpge_get_term",
        description=(
            "Fetch full context for a single PTPGE term: definition, broader/"
            "narrower relations, exactMatch / closeMatch mappings, properties, "
            "notation, level, and metadata. Accepts either a full URI "
            "(https://ptpge.org/v1/...) or a relative path under /v1/."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "id_or_path": {
                    "type": "string",
                    "description": (
                        "Full URI or relative path under /v1/. "
                        "E.g. 'printing/configurations/formats/a-series/a4'."
                    ),
                },
                "language": {
                    "type": "string",
                    "default": "en",
                    "description": "ISO 639-1 language code for which label and definition variants to return flat.",
                },
            },
            "required": ["id_or_path"],
        },
    ),
    Tool(
        name="ptpge_get_version",
        description=(
            "Return the current PTPGE dataset version, total term count, "
            "counts per level and per group, license, scheme URL, and server "
            "version. Useful for version-pinning, health checks, and diagnostics."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="ptpge_browse",
        description=(
            "Navigate the PTPGE hierarchy. Returns a node and its children "
            "(id, notation, label, level, elementType, hasChildren). Omit "
            "id_or_path to get the three top concepts (printing, ordering, "
            "variables). Use this for systematic exploration instead of "
            "guessing search keywords."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "id_or_path": {
                    "type": "string",
                    "description": "Full URI or path under /v1/. Omit for the top concepts.",
                },
                "language": {"type": "string", "default": "en"},
            },
            "required": [],
        },
    ),
    Tool(
        name="ptpge_get_product_envelope",
        description=(
            "Return the complete Configuration Envelope of a product class in "
            "one call: supportsSetupModel, every supports* and "
            "perSurfaceSupports* predicate with resolved labels, plus "
            "typical* descriptors. This is the full menu of what can be "
            "configured for the product — use it before composing a "
            "configuration, instead of many individual ptpge_get_term calls. "
            "Absent predicates mean NOT supported (closed semantics)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "id_or_path": {
                    "type": "string",
                    "description": "Product URI or path, e.g. 'ordering/products/brochures'.",
                },
                "language": {"type": "string", "default": "en"},
            },
            "required": ["id_or_path"],
        },
    ),
    Tool(
        name="ptpge_validate_config",
        description=(
            "Layer 1 envelope validation of a product configuration: checks "
            "every binding against the product's supports* envelopes, maps "
            "numeric substrate-weight (gsm) to its weight band via the bands' "
            "minWeight/maxWeight properties, and returns data-driven "
            "advisories (e.g. creasing recommended above the scoring "
            "thresholds). NOTE: this validates the ENVELOPE only — "
            "cross-variable legality (e.g. valid panel counts per fold "
            "topology) and vendor capability matching are Layer 2 "
            "(Configurator) services."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "product": {"type": "string", "description": "Product URI or path."},
                "bindings": {
                    "type": "array",
                    "description": "Variable bindings to validate.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "variable": {"type": "string", "description": "Variable URI or path, e.g. 'variables/configuration/format'."},
                            "value": {"description": "URI/path (enum) or number (numeric variables)."},
                            "values": {"type": "array", "description": "For cardinality-multiple variables."},
                            "surface": {"type": "string", "description": "Surface slug for surface-scoped bindings (e.g. 'outside')."},
                        },
                        "required": ["variable"],
                    },
                },
                "language": {"type": "string", "default": "en"},
            },
            "required": ["product", "bindings"],
        },
    ),
    Tool(
        name="ptpge_fingerprint",
        description=(
            "Compute the canonical ptpge-cfs/1 serialization and SHA-256 "
            "fingerprint of a resolved product configuration (SD-0040) — the "
            "vendor-neutral identity used as quote/order/cache key. Returns "
            "both profiles: 'spec' (the manufacturable artifact, commercial "
            "cluster excluded) and 'offer' (incl. quantity etc.). Input is "
            "NOT validated against envelopes — call ptpge_validate_config "
            "first if needed."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "product": {"type": "string", "description": "Product URI or path."},
                "bindings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "variable": {"type": "string"},
                            "value": {"description": "URI/path or number."},
                            "values": {"type": "array"},
                            "surface": {"type": "string"},
                            "ordered": {"type": "boolean"},
                        },
                        "required": ["variable"],
                    },
                },
            },
            "required": ["product", "bindings"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Tool handler implementations
# ---------------------------------------------------------------------------

def _json_text(payload: object) -> list[TextContent]:
    """MCP convention: return JSON-encoded text for structured payloads."""
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


def _localize(value: object, language: str) -> object:
    """Return a flattened value for a language map, or pass through otherwise.

    {"en": "A4", "nb": "A4"} + "nb" -> "A4"
    "raw string" + _ -> "raw string"
    """
    if isinstance(value, dict) and value:
        # Heuristic: language map if keys look like ISO 639-1
        if all(isinstance(k, str) and 2 <= len(k) <= 7 for k in value.keys()):
            if language in value:
                return value[language]
            if "en" in value:
                return value["en"]
            # Fallback: first available
            return next(iter(value.values()))
    return value


def _term_for_response(term: dict, language: str) -> dict:
    """Flatten language maps in a term for a specific language.

    The MCP response is plain JSON (not JSON-LD), so we strip @context and
    surface the chosen language's prefLabel / definition / scopeNote as flat
    strings while keeping the original maps available under *_all.
    """
    out: dict = {}
    for key, value in term.items():
        if key in ("@context",):
            continue
        if key in ("label", "definition", "scopeNote", "example"):
            out[key] = _localize(value, language)
            out[f"{key}_all"] = value
        else:
            out[key] = value
    return out


# ---------------------------------------------------------------------------
# v0.4.0 tool helpers — envelope, validation, browse
# ---------------------------------------------------------------------------

_BASE = "https://ptpge.org/v1/"

# Variable URI tail -> the product envelope predicate it is constrained by.
# Variables not listed here either have no Layer 1 envelope (numeric
# page-count, commercial quantity) or are validated by other means.
VARIABLE_ENVELOPE = {
    "variables/configuration/setup-model":      ("supportsSetupModel", "product"),
    "variables/configuration/format":         ("supportsFormat", "product"),
    "variables/configuration/orientation":    ("supportsOrientation", "product"),
    "variables/finishing/edge":   ("supportsFoldDirection", "product"),
    "variables/finishing/binding":          ("supportsBinding", "product"),
    "variables/substrate/substrate-type":   ("supportsSubstrate", "product"),
    "variables/substrate/substrate-finish": ("supportsSubstrateFinish", "product"),
    "variables/substrate/substrate-color": ("supportsSubstrateColour", "product"),
    "variables/production/technology":      ("supportsTechnology", "product"),
    "variables/production/press-type":      ("supportsPressType", "product"),
    "variables/compliance/certification":   ("supportsCertification", "product"),
    "variables/compliance/print-standard":  ("supportsPrintStandard", "product"),
    "variables/compliance/color-profile":        ("supportsColorProfile", "product"),
    "variables/features/color-mode":           ("perSurfaceSupportsColorMode", "surface"),
    "variables/features/embellishment": ("perSurfaceSupportsEmbellishment", "surface"),
    "variables/features/surface-finish": ("perSurfaceSupportsSurfaceFinish", "surface"),
    "variables/finishing/structural-finishing": ("supportsStructuralFinishing", "product"),
    "variables/configuration/shape":            ("supportsShape", "product"),
}

WEIGHT_VARIABLE = "variables/substrate/substrate-weight"
WEIGHT_ENVELOPE = "supportsSubstrateWeight"
SCORING_URI = _BASE + "printing/completions/structural-finishing/scoring"


def _full_uri(id_or_path: str) -> str:
    s = str(id_or_path or "").strip()
    return s if s.startswith("http") else _BASE + s.lstrip("/")


def _localized(value, language: str):
    return _localize(value, language)


def _ref(cache: "VocabularyCache", uri: str, language: str) -> dict:
    """Resolve a URI to a compact reference {id, notation, label, level}."""
    term = cache.get_term(uri)
    if term is None:
        return {"id": uri, "label": uri.rsplit("/", 1)[-1], "resolved": False}
    return {
        "id": term.get("id", uri),
        "notation": term.get("notation") or None,
        "label": _localized(term.get("label"), language),
        "level": term.get("level"),
        "elementType": term.get("elementType") or None,
    }


def _weight_bands(cache: "VocabularyCache") -> list[dict]:
    """All weight band terms with their numeric range, via the substrate-weight
    Variable's valueDomain -> narrower walk. Data-driven; nothing hardcoded."""
    var = cache.get_term(_BASE + WEIGHT_VARIABLE) or {}
    domain = var.get("valueDomain") or _BASE + "printing/substrates/sheet-materials/paper/paper-weights"
    parent = cache.get_term(domain) or {}
    bands = []
    for u in parent.get("narrower", []) or []:
        t = cache.get_term(u) or {}
        p = t.get("properties") or {}
        if "minWeight" in p:
            bands.append({
                "id": t.get("id", u), "notation": t.get("notation"),
                "minWeight": p.get("minWeight"), "maxWeight": p.get("maxWeight"),
            })
    bands.sort(key=lambda b: b["minWeight"])
    return bands


def _band_for_weight(cache: "VocabularyCache", gsm) -> dict | None:
    for b in _weight_bands(cache):
        if gsm >= b["minWeight"] and (b.get("maxWeight") is None or gsm <= b["maxWeight"]):
            return b
    return None


def envelope_payload(cache: "VocabularyCache", id_or_path: str, language: str) -> object:
    uri = _full_uri(id_or_path)
    term = cache.get_term(uri)
    if term is None:
        return {"error": "not_found", "id_or_path": id_or_path}
    if term.get("elementType") != "product":
        return {"error": "not_a_product", "id": term.get("id"),
                "elementType": term.get("elementType"),
                "hint": "ptpge_get_product_envelope only applies to elementType=product terms."}
    out = {
        "product": _ref(cache, uri, language),
        "envelope": {},
        "perSurface": {},
        "typical": {},
        "closedSemantics": "Predicates absent from this envelope are NOT supported for this product.",
    }
    for key, value in term.items():
        if key.startswith("perSurfaceSupports") and isinstance(value, list):
            out["perSurface"][key] = [_ref(cache, u, language) for u in value]
        elif key.startswith("supports") and isinstance(value, list):
            out["envelope"][key] = [_ref(cache, u, language) for u in value]
        elif key in ("typicalUse", "typicalAudience") and isinstance(value, list):
            out["typical"][key] = [_ref(cache, u, language) for u in value]
        elif key in ("typicalPageCount", "fulfilmentClass"):
            out["typical"][key] = value
    return out


def validate_payload(cache: "VocabularyCache", args: dict) -> object:
    language = args.get("language", "en")
    uri = _full_uri(args.get("product", ""))
    product = cache.get_term(uri)
    if product is None:
        return {"error": "not_found", "product": args.get("product")}
    if product.get("elementType") != "product":
        return {"error": "not_a_product", "id": product.get("id")}

    results, advisories = [], []
    all_ok = True
    bound_weight = None
    for b in args.get("bindings", []) or []:
        var_uri = _full_uri(b.get("variable", ""))
        var_tail = var_uri[len(_BASE):]
        values = b.get("values") if "values" in b else [b.get("value")]
        entry = {
            "variable": var_tail,
            "surface": b.get("surface") or None,
            "value": b.get("values") if "values" in b else b.get("value"),
        }
        # Numeric substrate-weight: map to band, check band against envelope.
        if var_tail == WEIGHT_VARIABLE and isinstance(values[0], (int, float)):
            gsm = values[0]
            bound_weight = gsm
            band = _band_for_weight(cache, gsm)
            if band is None:
                entry.update(status="no_matching_band",
                             note=f"{gsm} gsm matches no weight band (bands cover 50+).")
                all_ok = False
            else:
                env = product.get(WEIGHT_ENVELOPE)
                entry["band"] = {"id": band["id"], "notation": band["notation"],
                                 "range": [band["minWeight"], band.get("maxWeight")]}
                if env is None:
                    entry.update(status="not_supported",
                                 note="Product declares no supportsSubstrateWeight (closed semantics).")
                    all_ok = False
                elif band["id"] in env:
                    entry["status"] = "in_envelope"
                else:
                    entry.update(status="not_in_envelope",
                                 note="Weight band is outside this product's envelope.")
                    all_ok = False
            results.append(entry)
            continue
        # Envelope-mapped enum variables.
        mapping = VARIABLE_ENVELOPE.get(var_tail)
        if mapping is None:
            scope_note = ("numeric; topology legality is Layer 2"
                          if var_tail == "variables/configuration/page-count"
                          else "commercial; no Layer 1 envelope"
                          if var_tail.startswith("variables/order/")
                          else "no Layer 1 envelope mapping for this variable")
            entry.update(status="not_checked", note=scope_note)
            results.append(entry)
            continue
        env_key, _scope = mapping
        env = product.get(env_key)
        if env is None:
            entry.update(status="not_supported", envelope=env_key,
                         note=f"Product declares no {env_key} (closed semantics).")
            all_ok = False
            results.append(entry)
            continue
        bad = [v for v in values if _full_uri(v) not in env]
        entry["envelope"] = env_key
        if bad:
            entry.update(status="not_in_envelope",
                         offending=[_full_uri(v) for v in bad])
            all_ok = False
        else:
            entry["status"] = "in_envelope"
        results.append(entry)

    # Data-driven advisory: creasing thresholds from the scoring term (SD: rilling).
    scoring = cache.get_term(SCORING_URI) or {}
    sp = scoring.get("properties") or {}
    if bound_weight is not None and sp.get("recommendedFromWeight") is not None:
        if bound_weight >= sp.get("standardFromWeight", 10 ** 9):
            advisories.append({
                "type": "creasing_standard",
                "term": SCORING_URI,
                "note": f"At {bound_weight} gsm, creasing (rilling) is standard practice "
                        f"(from {sp['standardFromWeight']} gsm) when the product is folded.",
            })
        elif bound_weight >= sp["recommendedFromWeight"]:
            advisories.append({
                "type": "creasing_recommended",
                "term": SCORING_URI,
                "note": f"At {bound_weight} gsm, creasing (rilling) is recommended "
                        f"(from {sp['recommendedFromWeight']} gsm) when the product is folded.",
            })

    return {
        "product": _ref(cache, uri, language),
        "validInEnvelope": all_ok,
        "bindings": results,
        "advisories": advisories,
        "scope": "Layer 1 envelope validation only. Cross-variable legality "
                 "(e.g. panel counts per topology) and vendor capability are "
                 "Layer 2 (Configurator) services.",
    }


def browse_payload(cache: "VocabularyCache", id_or_path: str | None, language: str) -> object:
    if not id_or_path:
        roots = [_BASE + "printing", _BASE + "ordering", _BASE + "variables"]
        return {"node": None, "children": [
            dict(_ref(cache, u, language),
                 hasChildren=bool((cache.get_term(u) or {}).get("narrower")))
            for u in roots
        ]}
    uri = _full_uri(id_or_path)
    term = cache.get_term(uri)
    if term is None:
        return {"error": "not_found", "id_or_path": id_or_path}
    children = []
    for u in term.get("narrower", []) or []:
        child = cache.get_term(u) or {}
        children.append(dict(_ref(cache, u, language),
                             hasChildren=bool(child.get("narrower"))))
    return {"node": _ref(cache, uri, language),
            "broader": term.get("broader") or None,
            "children": children}


def fingerprint_payload(args: dict) -> object:
    config = {"product": _full_uri(args.get("product", "")),
              "bindings": []}
    for b in args.get("bindings", []) or []:
        nb = {"variable": _full_uri(b.get("variable", ""))}
        if "values" in b:
            nb["values"] = [
                v if isinstance(v, (int, float)) else _full_uri(v)
                for v in b["values"]
            ]
            if "ordered" in b:
                nb["ordered"] = bool(b["ordered"])
        else:
            v = b.get("value")
            nb["value"] = v if isinstance(v, (int, float)) else _full_uri(v)
        if b.get("surface"):
            nb["surface"] = b["surface"]
        config["bindings"].append(nb)
    out = {"algorithm": "ptpge-cfs/1", "profiles": {}}
    for profile in ("spec", "offer"):
        s = _cfs_canonical(config, profile)
        h = _cfs_fingerprint(config, profile)
        out["profiles"][profile] = {"canonical": s, "sha256": h, "short": _cfs_short(h)}
    out["note"] = ("Input was serialized as given — not validated against the "
                   "product envelope. Use ptpge_validate_config for that.")
    return out


# ---------------------------------------------------------------------------
# Shared tool dispatch — used by BOTH transports (SSE and Streamable HTTP).
# Pure function of (cache, name, args) so it is unit-testable without an app.
# ---------------------------------------------------------------------------

def tool_payload(cache: "VocabularyCache", name: str, args: dict) -> object:
    """Execute a tool and return its JSON-serialisable payload.

    Raises ValueError for unknown tool names (protocol-level error);
    any other exception is a tool-execution error (isError=true in MCP).
    """
    if name == "ptpge_get_version":
        v = cache.version
        # Two complementary version dimensions per the PTPGE Stability
        # Guarantee (see PTPGE-API-architecture.md § 8): calendar dataVersion
        # for the term snapshot, semantic apiVersion for the contract.
        return {
            "dataVersion": v.get("version"),
            "apiVersion": v.get("apiVersion"),
            "changeType": v.get("changeType"),
            "previousDataVersion": v.get("previousVersion"),
            "previousApiVersion": v.get("previousApiVersion"),
            "changelogUrl": v.get("changelogUrl"),
            "schemaVersion": "v1",
            "generated": v.get("generated"),
            "termsTotal": v.get("terms"),
            "termsByLevel": v.get("by_level"),
            "termsByGroup": v.get("by_group"),
            "license": v.get("license"),
            "schemeUrl": v.get("scheme_url"),
            "serverVersion": __version__,
        }

    if name == "ptpge_search_terms":
        query = args.get("query", "")
        limit = int(args.get("limit", 10))
        groups = args.get("groups")
        language = args.get("language", "en")
        hits = cache.search(query=query, limit=limit, groups=groups, language=language)
        return {"query": query, "count": len(hits), "results": hits}

    if name == "ptpge_get_term":
        id_or_path = args.get("id_or_path", "")
        language = args.get("language", "en")
        term = cache.get_term(id_or_path)
        if term is None:
            return {"error": "not_found", "id_or_path": id_or_path}
        return _term_for_response(term, language)

    if name == "ptpge_browse":
        return browse_payload(cache, args.get("id_or_path"), args.get("language", "en"))

    if name == "ptpge_get_product_envelope":
        return envelope_payload(cache, args.get("id_or_path", ""), args.get("language", "en"))

    if name == "ptpge_validate_config":
        return validate_payload(cache, args)

    if name == "ptpge_fingerprint":
        return fingerprint_payload(args)

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Streamable HTTP transport (stateless JSON mode) — JSON-RPC plumbing
# ---------------------------------------------------------------------------

# Protocol revisions we know how to speak. We echo the client's requested
# version when we recognise it; otherwise we answer with our latest, per the
# MCP version-negotiation rules.
SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18")
LATEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[-1]

SERVER_INSTRUCTIONS = (
    "PTPGE Standard vocabulary server (printing & graphic industry). "
    "Use ptpge_search_terms to find terms, ptpge_get_term for full context "
    "on one term, ptpge_get_version for dataset version/statistics."
)


def negotiate_protocol_version(requested: object) -> str:
    if isinstance(requested, str) and requested in SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return LATEST_PROTOCOL_VERSION


def _rpc_result(msg_id: object, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _rpc_error(msg_id: object, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def handle_jsonrpc_message(cache: "VocabularyCache", msg: object) -> dict | None:
    """Process one JSON-RPC message; return the response dict, or None for
    messages that get no response body (notifications, client responses)."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        msg_id = msg.get("id") if isinstance(msg, dict) else None
        return _rpc_error(msg_id, -32600, "Invalid Request")

    method = msg.get("method")
    msg_id = msg.get("id")

    if method is None:
        return None  # a response from the client (e.g. to a ping) — nothing to do
    if msg_id is None:
        return None  # notification (notifications/initialized, .../cancelled, ...)

    if method == "initialize":
        params = msg.get("params") or {}
        return _rpc_result(msg_id, {
            "protocolVersion": negotiate_protocol_version(params.get("protocolVersion")),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": "ptpge-mcp",
                "title": "PTPGE Standard MCP",
                "version": __version__,
            },
            "instructions": SERVER_INSTRUCTIONS,
        })

    if method == "ping":
        return _rpc_result(msg_id, {})

    if method == "tools/list":
        tools = [t.model_dump(by_alias=True, exclude_none=True) for t in TOOL_DESCRIPTORS]
        return _rpc_result(msg_id, {"tools": tools})

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name", "")
        args = params.get("arguments") or {}
        try:
            payload = tool_payload(cache, name, args)
        except ValueError as exc:
            return _rpc_error(msg_id, -32602, str(exc))
        except Exception as exc:  # tool execution error → isError result, not protocol error
            logger.exception("Tool %s failed", name)
            return _rpc_result(msg_id, {
                "content": [{"type": "text", "text": f"Tool execution failed: {exc}"}],
                "isError": True,
            })
        return _rpc_result(msg_id, {
            "content": [{
                "type": "text",
                "text": json.dumps(payload, ensure_ascii=False, indent=2),
            }],
            "isError": False,
        })

    # We advertise only tools, but answer the other list methods gracefully
    # for clients that probe them anyway.
    if method == "resources/list":
        return _rpc_result(msg_id, {"resources": []})
    if method == "resources/templates/list":
        return _rpc_result(msg_id, {"resourceTemplates": []})
    if method == "prompts/list":
        return _rpc_result(msg_id, {"prompts": []})

    return _rpc_error(msg_id, -32601, f"Method not found: {method}")


# ---------------------------------------------------------------------------
# noindex middleware — Stealth Mode hygiene, parity with api/internal
# ---------------------------------------------------------------------------

class CapabilityTokenMiddleware(BaseHTTPMiddleware):
    """Per-tester capability tokens for the OPEN mirror's /mcp endpoint.

    Web connectors (claude.ai, ChatGPT) cannot send Basic Auth, so the open
    mirror runs without transport auth — this middleware adds a revocable,
    attributable capability instead: the connector URL carries a personal
    token (`?t=glxt_...`, or header `X-PTPGE-Token`).

    Tokens come from two sources, merged:
      - a JSON users file (the register server's beta-users.json): every
        record with status == "active" and a non-empty "mcp_token" counts.
        The file is re-read when its mtime changes, so approving or
        suspending a tester in the register admin panel takes effect
        immediately — no restart.
      - PTPGE_MCP_TOKENS (comma-separated static tokens, internal use).

    Only the configured paths are gated (default: /mcp) — /playground,
    /healthz and the landing page stay open. While `allow_anon` is True
    (migration grace) tokenless requests pass through; invalid (wrong)
    tokens are always rejected, so a revoked tester cannot keep using a
    stale URL even during the grace period.
    """

    def __init__(self, app, tokens_file: str | None = None,
                 static_tokens: list[str] | None = None,
                 allow_anon: bool = True,
                 protected_paths: tuple[str, ...] = ("/mcp",)) -> None:
        super().__init__(app)
        self._tokens_file = tokens_file
        self._static = [t for t in (static_tokens or []) if t]
        self._allow_anon = allow_anon
        self._protected = protected_paths
        self._file_tokens: list[str] = []
        self._mtime: float | None = None
        self._enabled = bool(tokens_file or self._static)

    def _load_file_tokens(self) -> None:
        if not self._tokens_file:
            return
        try:
            mtime = os.path.getmtime(self._tokens_file)
        except OSError:
            self._file_tokens = []
            self._mtime = None
            return
        if mtime == self._mtime:
            return
        try:
            with open(self._tokens_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            users = data.get("users", data) if isinstance(data, dict) else data
            tokens = []
            for u in users if isinstance(users, list) else []:
                if isinstance(u, dict) and u.get("status") == "active" and u.get("mcp_token"):
                    tokens.append(str(u["mcp_token"]))
            self._file_tokens = tokens
            self._mtime = mtime
        except Exception as exc:  # malformed file must not lock the server
            logger.warning("token file unreadable (%s): %s", self._tokens_file, exc)

    def _valid(self, presented: str) -> bool:
        ok = False
        for t in self._file_tokens + self._static:
            # constant-time compare against every token — no early exit
            if secrets.compare_digest(presented, t):
                ok = True
        return ok

    async def dispatch(self, request, call_next):
        if not self._enabled or not any(request.url.path.startswith(p) for p in self._protected):
            return await call_next(request)
        self._load_file_tokens()
        presented = request.query_params.get("t") or request.headers.get("x-ptpge-token") or ""
        if presented:
            if self._valid(presented):
                return await call_next(request)
            return JSONResponse(
                {"error": "invalid_token",
                 "detail": "This PTPGE connector token is not valid (it may have been revoked). "
                           "Apply at https://register.ptpge.org/ for access."},
                status_code=401)
        if self._allow_anon:
            return await call_next(request)
        return JSONResponse(
            {"error": "token_required",
             "detail": "This endpoint uses personal connector URLs. Use the URL from your "
                       "welcome email (https://open.mcp.ptpge.org/mcp?t=...), or apply at "
                       "https://register.ptpge.org/."},
            status_code=401)


class NoIndexHeaderMiddleware(BaseHTTPMiddleware):
    """Add X-Robots-Tag: noindex to every response (including 401s)."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
        return response


def build_app() -> Starlette:
    """Construct the Starlette ASGI app, MCP server, and tool handlers.

    Loading happens at import-time so any startup failure surfaces immediately
    in cPanel Passenger logs rather than silently in the first request.
    """
    config = Config.from_env()
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cache = VocabularyCache(config)
    cache.load()
    cache.start_background_refresh()

    mcp_server: Server = Server("ptpge-mcp")

    @mcp_server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOL_DESCRIPTORS

    @mcp_server.call_tool()
    async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        # Shared dispatch with the Streamable HTTP transport (see tool_payload).
        return _json_text(tool_payload(cache, name, arguments or {}))

    sse = SseServerTransport("/mcp/messages/")

    async def handle_sse(request: Request) -> Response:
        if not config.sse_enabled:
            # SSE disabled (PTPGE_MCP_SSE=0): each SSE client permanently
            # occupies a Passenger worker, so the public mirror refuses the
            # transport entirely instead of letting any client wedge the app.
            return JSONResponse(
                {
                    "error": "sse_disabled",
                    "message": "The SSE transport is disabled on this endpoint. "
                               "Use the Streamable HTTP transport at /mcp instead.",
                    "mcp_endpoint": "/mcp",
                },
                status_code=410,
            )
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await mcp_server.run(streams[0], streams[1], mcp_server.create_initialization_options())
        return Response()

    async def handle_mcp_http(request: Request) -> Response:
        """Streamable HTTP transport endpoint (stateless JSON mode).

        POST: one JSON-RPC message (or a batch array) in, one JSON response
        out. Notifications get 202 Accepted with no body. GET/DELETE return
        405 — this server opens no server-initiated streams and keeps no
        sessions, by design (see v0.3.0 note in the module docstring).
        """
        if request.method != "POST":
            return Response(status_code=405, headers={"Allow": "POST"})
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(_rpc_error(None, -32700, "Parse error"), status_code=400)

        if isinstance(body, list):  # batch (protocol <= 2025-03-26)
            if not body:
                return JSONResponse(_rpc_error(None, -32600, "Invalid Request"), status_code=400)
            replies = [r for m in body if (r := handle_jsonrpc_message(cache, m)) is not None]
            if not replies:
                return Response(status_code=202)
            return JSONResponse(replies)

        reply = handle_jsonrpc_message(cache, body)
        if reply is None:
            return Response(status_code=202)
        return JSONResponse(reply)

    async def playground(_request: Request) -> HTMLResponse:
        """Browser test console (v0.3.3) — same-origin JS that POSTs real
        JSON-RPC to /mcp. See ptpge_mcp/playground.py."""
        return HTMLResponse(PLAYGROUND_HTML)

    async def health(_request: Request) -> JSONResponse:
        try:
            v = cache.version.get("version")
            return JSONResponse({"status": "ok", "data_version": v, "server_version": __version__})
        except Exception as exc:
            return JSONResponse({"status": "error", "error": str(exc)}, status_code=503)

    async def root(_request: Request) -> JSONResponse:
        """Service banner for the base URL.

        Returns 200 OK with a small JSON descriptor instead of letting
        Starlette 404 / proxy clients 500 on the bare domain. Useful as a
        smoke-test endpoint and as a friendly response for anyone who
        navigates to https://mcp.ptpge.org/ in a browser.
        """
        v = cache.version.get("version") if cache.version else None
        return JSONResponse(
            {
                "service": "PTPGE Standard MCP",
                "description": "Model Context Protocol server for the PTPGE Standard vocabulary.",
                "server_version": __version__,
                "data_version": v,
                "endpoints": {
                    "mcp": "/mcp",
                    "playground": "/playground",
                    "sse": "/sse" if config.sse_enabled else None,
                    "messages": "/mcp/messages/" if config.sse_enabled else None,
                    "health": "/healthz",
                },
                "transport": {
                    "recommended": "streamable-http (/mcp, stateless JSON)",
                    "legacy": "sse (/sse)" if config.sse_enabled else "sse disabled on this endpoint",
                },
                "documentation": "https://ptpge.org",
                "status": "stealth-mode",
            }
        )

    async def chat(request: Request) -> Response:
        """LLM 'Ask the standard' proxy for the dashboard's AI panel.

        Retrieval-grounded: searches the vocabulary for the question, feeds the
        matching terms to the model as context, and returns a natural-language
        answer plus the source terms. Anthropic is called directly over HTTPS
        (no extra SDK dependency).

        Cost/abuse controls: requires the shared header token PTPGE_CHAT_TOKEN
        when set, and returns 503 when ANTHROPIC_API_KEY is unset (so the panel
        gracefully falls back to local search). CORS is opened to the dashboard
        origin (PTPGE_CHAT_ORIGIN) so the cross-origin fetch from
        dashboard.ptpge.org works on the open mirror.
        """
        cors = _chat_cors_headers()
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=cors)

        token = os.getenv("PTPGE_CHAT_TOKEN")
        if token and request.headers.get("x-ptpge-chat-token") != token:
            return JSONResponse({"error": "unauthorized"}, status_code=401, headers=cors)

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return JSONResponse(
                {"error": "chat_unconfigured",
                 "message": "ANTHROPIC_API_KEY is not set on this server."},
                status_code=503, headers=cors)

        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "bad_request"}, status_code=400, headers=cors)
        question = (body.get("question") or "").strip()
        if not question:
            return JSONResponse({"error": "empty_question"}, status_code=400, headers=cors)

        # Retrieval grounding: top vocabulary hits + their definitions.
        ctx_lines, sources = [], []
        for h in cache.search(question, limit=8):
            term = cache.get_term(h["id"]) or {}
            defn = term.get("definition") or {}
            d = (defn.get("en") or defn.get("nb") or "").strip()
            ctx_lines.append(f"- {h.get('notation') or ''} {h.get('prefLabel') or ''}: {d}".strip())
            sources.append({"notation": h.get("notation"), "label": h.get("prefLabel"), "url": h["id"]})
        context = "\n".join(ctx_lines) or "(no matching PTPGE terms found)"

        system = (
            "You are the PTPGE assistant for the open print-industry vocabulary "
            "(Periodic Table of Print & Graphic Elements). Answer the user's "
            "question using ONLY the PTPGE terms in the provided context. Be "
            "concise and practical. Cite term notations (e.g. P:CP§SCORING) "
            "where relevant. If the context does not contain the answer, say so "
            "plainly and point to the closest related terms. Reply in the user's "
            "language (Norwegian Bokmål or English)."
        )
        payload = {
            "model": os.getenv("PTPGE_CHAT_MODEL", "claude-opus-4-20250514"),
            "max_tokens": 800,
            "system": system,
            "messages": [{"role": "user",
                          "content": f"Context (PTPGE terms):\n{context}\n\nQuestion: {question}"}],
        }
        try:
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": api_key,
                             "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                    json=payload,
                )
            if r.status_code != 200:
                return JSONResponse({"error": "upstream", "status": r.status_code,
                                     "detail": r.text[:300]}, status_code=502, headers=cors)
            data = r.json()
            answer = "".join(b.get("text", "") for b in data.get("content", [])
                             if b.get("type") == "text").strip()
        except Exception as exc:  # network / parse
            return JSONResponse({"error": "upstream_exception", "detail": str(exc)[:300]},
                                status_code=502, headers=cors)

        return JSONResponse({"answer": answer, "sources": sources}, headers=cors)

    middleware = [
        Middleware(NoIndexHeaderMiddleware),  # outermost: header on 401s too
        Middleware(
            BasicAuthMiddleware,
            credentials=config.credentials,
        ),
        Middleware(
            CapabilityTokenMiddleware,
            tokens_file=config.tokens_file,
            static_tokens=config.tokens_static,
            allow_anon=config.token_allow_anon,
        ),
    ]

    if config.credentials:
        n = len(config.credentials)
        if n == 1:
            logger.info("Basic Auth ENABLED for all routes (Stealth Mode, 1 credential pair)")
        else:
            logger.info("Basic Auth ENABLED for all routes (Stealth Mode, %d credential pairs)", n)
    else:
        logger.warning("Basic Auth NOT configured - server is open. Set PTPGE_MCP_AUTH_USERS or PTPGE_MCP_AUTH_USER/_PASS to enable.")

    if config.tokens_file or config.tokens_static:
        mode = "grace (anon allowed)" if config.token_allow_anon else "required"
        logger.info("Capability tokens ENABLED on /mcp — mode: %s, file: %s, static: %d",
                    mode, config.tokens_file or "-", len(config.tokens_static))

    return Starlette(
        debug=False,
        middleware=middleware,
        routes=[
            Route("/", endpoint=root, methods=["GET"]),
            Route("/playground", endpoint=playground, methods=["GET"]),
            Route("/chat", endpoint=chat, methods=["POST", "OPTIONS"]),
            Route("/health", endpoint=health, methods=["GET"]),
            Route("/healthz", endpoint=health, methods=["GET"]),  # standard alias (matches the commercial side)
            # Streamable HTTP (recommended). GET/DELETE answered with 405
            # inside the handler — stateless servers open no streams.
            Route("/mcp", endpoint=handle_mcp_http, methods=["POST", "GET", "DELETE"]),
            # Legacy SSE transport (MCP Inspector, mcp-remote bridges).
            # NOTE: /mcp/messages/ must stay mounted AFTER /mcp so the more
            # specific Route above wins for exact /mcp requests.
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/mcp/messages/", app=sse.handle_post_message),
        ],
    )


# ASGI app — imported by passenger_wsgi.py and by uvicorn for local dev.
# Built lazily (PEP 562) so that importing this module for unit tests does
# not require network access to the PTPGE API. Passenger still fails loudly
# at boot: passenger_wsgi.py does `from ptpge_mcp.server import app`, which
# triggers the build immediately.
_app: Starlette | None = None


def __getattr__(name: str):
    if name == "app":
        global _app
        if _app is None:
            _app = build_app()
        return _app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main() -> None:
    """Local development entry point. In production, Passenger drives this."""
    import uvicorn

    uvicorn.run(build_app(), host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
