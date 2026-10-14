"""PTPGE MCP server — exposes the PTPGE specification (the open vocabulary of print) via the Model Context Protocol.

v0.4.0 — four new tools (tool surface v2, additive):
    - ptpge_browse                — hierarchy navigation (children of a node;
      top concepts when called without arguments)
    - ptpge_get_product_envelope  — the complete Configuration Envelope of a
      product class in one call, with resolved labels (saves agents 10+
      get_term round-trips when composing)
    - ptpge_validate_config       — ENVELOPE validation: bindings vs
      supports*, numeric gsm -> weight band via minWeight/maxWeight
      properties, data-driven advisories (creasing thresholds from the
      scoring term). Deliberately not full legality — that is an implementation,
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
import hashlib
import json
import logging
import os
import re
import urllib.error
import urllib.request
import secrets
import time

import httpx

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool, ToolAnnotations
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Mount, Route

from . import __version__
from . import registerclient as _reg
from .config import Config
from . import fingermark as _fm
from . import colornotation, spotink
from . import learning
from . import agent as _agent
from .data import VocabularyCache
from .fingerprint import canonical_string as _cfs_canonical, fingerprint as _cfs_fingerprint, short as _cfs_short
from .cfs_resolution import resolve as _cfs_resolve, entailed_substrate_type as _cfs_entailed_type
from .htpasswd import HtpasswdVerifier
from .playground import PLAYGROUND_HTML
from . import completeness

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

    def __init__(self, app, credentials: list[tuple[str, str]] | None = None,
                 htpasswd_file: str | None = None) -> None:
        super().__init__(app)
        credentials = credentials or []
        self._expected_tokens: list[str] = []
        for username, password in credentials:
            if not username or not password:
                continue
            token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
            self._expected_tokens.append(f"Basic {token}")
        # v0.8.0: shared htpasswd file (register-provisioned per-user
        # credentials — same file as gutenlex.org/preview and api /v1).
        # Checked after the env pairs in dispatch().
        self._htpasswd = HtpasswdVerifier(htpasswd_file) if htpasswd_file else None
        # Auth is on if EITHER source is configured; if both collapse to
        # nothing, run open rather than locking the server out.
        self._enabled = bool(self._expected_tokens) or self._htpasswd is not None
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
        if not match and self._htpasswd is not None:
            match = self._try_htpasswd(provided)
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

    def _try_htpasswd(self, provided: str) -> bool:
        """Decode a `Basic <b64>` header and verify against the shared
        htpasswd file. Fail closed on any malformed input."""
        if not provided.startswith("Basic "):
            return False
        try:
            raw = base64.b64decode(provided[6:], validate=True).decode("utf-8")
            username, _, password = raw.partition(":")
        except (ValueError, UnicodeDecodeError):
            return False
        if not username or not password:
            return False
        return self._htpasswd.verify(username, password)


# ---------------------------------------------------------------------------
# Tool descriptors — kept module-level so they can be unit-tested without
# spinning up the full Starlette app.
# ---------------------------------------------------------------------------

TOOL_DESCRIPTORS: list[Tool] = [
    Tool(
        name="ptpge_search_terms",
        title="Search the vocabulary",
        annotations=ToolAnnotations(title="Search the vocabulary", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
        description=(
            "Free-text search over the PTPGE vocabulary and registers — the open specification of print. Returns a ranked list "
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
                "query_language": {
                    "type": "string",
                    "description": (
                        "ISO 639-1 code for the language the QUERY is written in — "
                        "not the language of the labels you want back (that is "
                        "`language`). Optional, and it never changes the results: "
                        "search always looks across every language. It is used only "
                        "so that a phrase we cannot resolve is recorded against the "
                        "right market, which is how missing synonyms get found and "
                        "added. Send it if you know it; omit it if you do not."
                    ),
                },
                "include_deprecated": {
                    "type": "boolean", "default": False,
                    "description": "Also return deprecated terms (they still resolve by URI but are no longer vocabulary). Default false: a brand name resolves to its register entry (kind=supplier) instead of the retired term."
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="ptpge_get_term",
        title="Read a term",
        annotations=ToolAnnotations(title="Read a term", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
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
        title="Dataset version",
        annotations=ToolAnnotations(title="Dataset version", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
        description=(
            "Return the current PTPGE dataset version, total term count, "
            "counts per level and per group, license, scheme URL, and server "
            "version. Useful for version-pinning, health checks, and diagnostics."
        ),
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="ptpge_browse",
        title="Browse the hierarchy",
        annotations=ToolAnnotations(title="Browse the hierarchy", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
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
        title="Product envelope",
        annotations=ToolAnnotations(title="Product envelope", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
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
        title="Validate a configuration",
        annotations=ToolAnnotations(title="Validate a configuration", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
        description=(
            "Envelope validation of a product configuration against the specification: checks "
            "every binding against the product's supports* envelopes. When a value is not in this "
            "template's envelope but another template takes every bound value, the result carries "
            "alsoOfferedBy (ranked) and switchHint — switch product and validate again rather than "
            "dropping what the buyer asked for (a poster on aluminium composite is a panel print). Maps "
            "numeric substrate-weight (gsm) to its weight band via the bands' "
            "minWeight/maxWeight properties, and returns data-driven "
            "advisories (e.g. creasing recommended above the scoring "
            "thresholds). NOTE: this validates the ENVELOPE only — "
            "cross-variable legality (e.g. valid panel counts per fold "
            "topology) and vendor capability matching are an implementation's "
            "concern (a configurator), not the specification's; commercial values (date, price) are "
            "not configuration and belong to the transaction layer. "
            "Elicitation contract (shared by every ptpge_* tool): whenever a "
            "result carries `needs_disambiguation`, each entry has a `field`, "
            "a `question` that MUST be put to the user verbatim, and "
            "`candidates` — never infer the answer, never fingerprint until "
            "it is resolved. SD-0083: the validator also checks completeness "
            "— a missing REQUIRED axis of the product (setup/fold, format, "
            "page count, binding, colour on the first face, shape where shape "
            "is the product) returns needs_disambiguation with the envelope's "
            "candidates; a required axis with exactly one allowed value is "
            "bound for you as envelope-implied; a surface name that is not a "
            "face of the bound setup (faces: flat-sheet front/back, "
            "folded-sheet outside/inside, multi-page front-cover…back-cover) "
            "is rejected with the allowed faces. `complete: true` means an "
            "identity can be issued. SD-0104 spot inks: a spot-color layer in "
            "color-mode is not identified until it is named — bind "
            "variables/features/spot-ink on the same face with the value "
            "<matching-system term>/<code>: Pantone 300 C → printing/standards/"
            "color-systems/color-matching-systems/pantone-matching-system/300-c, "
            "HKS 43 K → …/color-matching-systems/hks/43-k, RAL 5015 → …/ral/5015 "
            "(code lower-case, spaces as hyphens; checked for form only). One "
            "spot-ink per spot-color layer; two spots = color-mode values "
            "[cmyk, spot-color, spot-color] + two spot-ink values. Fewer inks than "
            "layers → needs_disambiguation; the specification sets no limit on "
            "the number of spot colours (the press does)."
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
                            "unit": {"type": "string", "enum": ["mm", "cm", "m", "in", "pt"], "description": "custom-width / custom-height only: the unit the value is stated in. Converted to mm before validation and identity (the identity is always mm)."},
                            "provenance": {
                                "type": "string",
                                "enum": ["confirmed", "inferred", "policy-default", "envelope-implied"],
                                "description": (
                                    "How this value came about (SD-0071): 'confirmed' — the "
                                    "buyer chose it; 'inferred' — you derived it without "
                                    "asking; 'policy-default' — a house rule supplied it. "
                                    "Never part of the fingerprint; identity is the product, "
                                    "not the conversation. Set it honestly: a vendor may "
                                    "refuse an order whose colour was never confirmed."
                                ),
                            },
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
        name="ptpge_resolve_color_notation",
        title="Resolve colour notation",
        annotations=ToolAnnotations(title="Resolve colour notation", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
        description=(
            "Resolve print colour pair notation (4/4, 4/1, 4+4) into per-surface "
            "colour bindings for a given product. The number is a COUNT OF "
            "SEPARATIONS, not a colour: it is resolved by searching the "
            "combinations this product's envelope actually supports whose "
            "colorChannelCount sums to that number. Returns one of three "
            "outcomes per surface — a deterministic binding, "
            "`needs_disambiguation` with the candidate combinations, or "
            "`invalid_for_template` when no combination is possible. "
            "IMPORTANT: when `needs_disambiguation` is returned you MUST put its "
            "`question` to the user and never infer the answer yourself. '1' is "
            "black on some products and a named spot colour on others; guessing "
            "gives two different products the same identity. Do not fingerprint "
            "an unresolved configuration."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "product": {"type": "string", "description": "Product URI or path."},
                "notation": {"type": "string", "description": "Pair notation, e.g. '4/4', '4 / 1', '4+4'."},
                "surfaces": {
                    "type": "array",
                    "description": ("Optional surface slugs in notation order. Without them the "
                                    "faces come from 'setup' (or the product's only setup): "
                                    "flat-sheet front/back, folded-sheet outside/inside, roll "
                                    "face/back (SD-0083)."),
                    "items": {"type": "string"},
                },
                "setup": {
                    "type": "string",
                    "description": ("Optional setup-model URI/path (e.g. 'printing/configurations/"
                                    "setup-models/folded-sheet/tri-fold') so the surfaces match "
                                    "the fold. Required for products with several setups."),
                },
                "language": {"type": "string", "default": "en"},
            },
            "required": ["product", "notation"],
        },
    ),
    Tool(
        name="ptpge_fingerprint",
        title="Fingerprint a configuration",
        annotations=ToolAnnotations(title="Fingerprint a configuration", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
        description=(
            "Compute the canonical ptpge-cfs/1 serialization and SHA-256 "
            "fingerprint of a resolved product configuration (SD-0040) — the "
            "vendor-neutral identity used as quote/order/cache key. Returns "
            "both profiles in strict containment spec ⊂ offer: 'spec' = the "
            "manufacturable artifact, commercial cluster excluded; 'offer' = "
            "spec plus the commercial cluster, which is exactly the four "
            "variables under variables/order/ — quantity, lead-time, "
            "delivery-method, incoterm (closed list, SD-0040). Transaction "
            "data (print-ready file, delivery date, price) is keyed BY the "
            "offer fingerprint and never hashed into it. SD-0083: the input "
            "is validated first and an identity is issued ONLY for a valid, "
            "complete configuration — every required axis of the product "
            "bound (or envelope-implied where the envelope offers one value; "
            "those are written into the identity) and every surface one of "
            "the bound setup's faces. Otherwise the result is "
            "error=not_fingerprintable with the validator's "
            "needs_disambiguation: put each question to the user verbatim, "
            "bind the answer, call again. Never guess a missing axis."
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
                            "unit": {"type": "string", "enum": ["mm", "cm", "m", "in", "pt"], "description": "custom-width / custom-height only — converted to mm before the identity."},
                            "ordered": {"type": "boolean"},
                        },
                        "required": ["variable"],
                    },
                },
                "visuals": {
                    "type": "boolean",
                    "default": False,
                    "description": "Also return markSvg (the ptpge-mark/1 "
                        "recognition mark) and qrSvg (QR encoding the resolver "
                        "permalink) per profile. Off by default to keep "
                        "payloads small.",
                },
            },
            "required": ["product", "bindings"],
        },
    ),
    Tool(
        name="ptpge_expand_fingerprint",
        title="Expand a fingerprint",
        annotations=ToolAnnotations(title="Expand a fingerprint", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
        description=(
            "Expand a spec or offer fingerprint (ptpge-cfs/1, full 64-hex or "
            "16-hex short form) back into its structured configuration — the "
            "read-back path for MIS/ERP: matched profile, product, every "
            "binding with resolved labels, the canonical string, and the "
            "dataset version. This is a LOOKUP in the public resolver "
            "(ptpge.org/f/), not an inversion of the hash: it resolves when "
            "the fingerprint has been registered (every fingerprint computed "
            "by ptpge_fingerprint is self-registered within seconds). An "
            "unregistered fingerprint is still a valid identity — it simply "
            "has no stored expansion yet; returns status 'unknown' then."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "fingerprint": {
                    "type": "string",
                    "description": "SHA-256 hex (64) or the 16-hex short form, with or without the resolver URL prefix.",
                },
                "language": {"type": "string", "default": "en"},
            },
            "required": ["fingerprint"],
        },
    ),
    Tool(
        name="ptpge_check_domain",
        title="Check a domain",
        annotations=ToolAnnotations(title="Check a domain", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True),
        description=(
            "Does an agent find PTPGE on this domain? Fetches exactly what a "
            "checkout agent fetches — https://<domain>/.well-known/ucp (the UCP "
            "manifest and its ptpge block), the vendor declaration at "
            "/.well-known/ptpge/declaration.json, the identity in the vendors "
            "register, and a supplier catalogue if the domain is a maker — and "
            "validates each against its published JSON Schema "
            "(ptpge.org/v1/schemas/) and the vocabulary. Returns a verdict "
            "(ready | partial | none), one line per step with errors and "
            "warnings, what the agent sees (name, identity, products, "
            "capability counts) and what is missing with where to fix it. "
            "Read-only; nothing is stored. Use it to answer 'is <printer> "
            "agent-ready?' or 'why does my declaration not validate?'."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "A hostname or URL, e.g. trykkverk.no or https://trykkverk.no/."},
                "document": {"type": "string", "description": "Optional: https URL of a declaration or catalogue hosted elsewhere than the known path (a register entry marked «hosted»)."},
            },
            "required": ["domain"],
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
# Variables not listed here either have no envelope in the specification (numeric
# page-count, commercial quantity) or are validated by other means.
VARIABLE_ENVELOPE = {
    "variables/configuration/setup-model":      ("supportsSetupModel", "product"),
    "variables/configuration/format":         ("supportsFormat", "product"),
    "variables/configuration/orientation":    ("supportsOrientation", "product"),
    "variables/finishing/edge":   ("supportsFoldDirection", "product"),
    "variables/finishing/binding":          ("supportsBinding", "product"),
    "variables/substrate/substrate-type":   ("supportsSubstrate", "product"),
    "variables/substrate/substrate-finish": ("supportsSubstrateFinish", "product"),
    "variables/substrate/substrate-color": ("supportsSubstrateColor", "product"),
    "variables/substrate/substrate-coating": ("supportsSubstrateCoating", "product"),
    "variables/substrate/substrate-fibre":   ("supportsSubstrateFibre", "product"),
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
    # SD-0076 (2026-09-03): substrate class (ISO 12647-2 PS1–PS5) and back orientation (XJDF LayoutIntent@Sides)
    "variables/substrate/substrate-class":      ("supportsSubstrateClass", "product"),
    "variables/configuration/back-orientation": ("supportsBackOrientation", "product"),
    "variables/configuration/winding-direction": ("supportsWindingDirection", "product"),
}

WEIGHT_VARIABLE = "variables/substrate/substrate-weight"
WEIGHT_ENVELOPE = "supportsSubstrateWeight"
# SD-0088 (2026-09-22): the null value of a per-face feature axis — «none» — is
# always permitted. A template envelope lists what may be APPLIED to a face;
# «nothing applied» is a statement every face can carry (it stands alone, SD-0084),
# and it is different from leaving the axis unspecified. The null value is
# appended to the envelope here (validation and the envelope payload) so the
# 56 templates need not list it and a vendor profile cannot narrow it away.
# SD-0098 (2026-10-07): surface finish has NO null value — «surface-finish/none» is
# deprecated without successor; a finish you do not ask for is not applied, and the
# axis is simply absent. colour-mode/none stays (spoken blankness: a face with no ink
# is a physical statement, SD-0068).
# 2026-10-11: the same for embellishment (SD-0098 extended) — «embellishments/none» is deprecated.
NULL_VALUES = {
    "variables/features/color-mode":     _BASE + "printing/features/colors/none",
}
NULL_BY_ENVELOPE = {
    "perSurfaceSupportsColorMode":      NULL_VALUES["variables/features/color-mode"],
}
# SD-0070: numeric thickness (canonical mm) with per-template {min,max} range
THICKNESS_VARIABLE = "variables/substrate/substrate-thickness"
THICKNESS_ENVELOPE = "supportsSubstrateThickness"
# SD-0076: spine thickness (mm) — same mechanics as SD-0070
SPINE_VARIABLE = "variables/configuration/spine-thickness"
SPINE_ENVELOPE = "supportsSpineThickness"
NUMERIC_RANGE_AXES = {THICKNESS_VARIABLE: THICKNESS_ENVELOPE, SPINE_VARIABLE: SPINE_ENVELOPE}
# SD-0076: substrate class vs coating consistency (PS1–PS4 coated, PS5 uncoated)
_PC = "printing/substrates/sheet-materials/paper/paper-classes/"
COATED_CLASSES = {_BASE + _PC + c for c in ("ps1-premium-coated", "ps2-improved-coated",
                                            "ps3-standard-glossy-coated", "ps4-standard-matte-coated")}
UNCOATED_CLASSES = {_BASE + _PC + c for c in ("ps5-wood-free-uncoated", "ps6-super-calendered",
                                              "ps7-improved-uncoated", "ps8-standard-uncoated")}   # PS6–PS8 added 2026-09-23
COATED_URI = _BASE + "printing/substrates/sheet-materials/paper/paper-coatings/coated"
UNCOATED_URI = _BASE + "printing/substrates/sheet-materials/paper/paper-coatings/uncoated"
CLASS_VARIABLE = "variables/substrate/substrate-class"
COATING_VARIABLE = "variables/substrate/substrate-coating"
SCORING_URI = _BASE + "printing/completions/structural-finishing/scoring"
# SD-0066: custom-mål
CUSTOM_WIDTH_VARIABLE = "variables/configuration/custom-width"
CUSTOM_HEIGHT_VARIABLE = "variables/configuration/custom-height"
FORMAT_VARIABLE = "variables/configuration/format"
CUSTOMIZED_FORMAT_URI = _BASE + "printing/configurations/formats/customized"


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
            vals = list(value)
            null = NULL_BY_ENVELOPE.get(key)     # SD-0088: the null value rides along
            if null and null not in vals and cache.get_term(null) is not None:
                vals.append(null)
            out["perSurface"][key] = [_ref(cache, u, language) for u in vals]
        elif key.startswith("supports") and isinstance(value, list):
            out["envelope"][key] = [_ref(cache, u, language) for u in value]
        elif key in ("typicalUse", "typicalAudience") and isinstance(value, list):
            out["typical"][key] = [_ref(cache, u, language) for u in value]
        elif key in ("typicalPageCount", "fulfilmentClass"):
            out["typical"][key] = value
    # SD-0083: what must be known before an identity is issued, what is
    # advisory, and which faces each setup has (surfaces follow the setup).
    out["required"] = [_ref(cache, u, language) for u in (term.get("requiredVariables") or [])]
    out["recommended"] = [_ref(cache, u, language) for u in (term.get("recommendedVariables") or [])]
    out["surfacesBySetup"] = {}
    for su in term.get("supportsSetupModel") or []:
        faces, panels = completeness.setup_faces(cache, su)
        if faces:
            out["surfacesBySetup"][su] = {"surfaces": faces, "panels": panels}
            parts = completeness.setup_parts(cache, su)
            if parts:
                out["surfacesBySetup"][su]["parts"] = parts
    out["identityRule"] = ("Required axes must be bound (or envelope-implied where the envelope "
                           "offers one value) before ptpge_fingerprint issues an identity; a "
                           "missing one returns needs_disambiguation. Surface names must be the "
                           "bound setup's faces. Where the setup has parts (multi-page: cover, inside), "
                           "substrate axes may be bound per part — surface: 'cover' / 'inside' — so a "
                           "300 g cover and a 130 g inside are two statements in one identity (SD-0102). "
                           "Recommended axes are advisory (SD-0083).")
    return out


def color_notation_payload(cache: "VocabularyCache", args: dict) -> object:
    """SD-0071: pair notation → per-surface bindings, or a question.

    The count is resolved against what this product's envelope supports, so the
    same "4/1" is deterministic on a product whose back surface only takes
    black and a question on one that also takes spot colour. We never guess.
    """
    language = args.get("language", "en")
    uri = _full_uri(args.get("product", ""))
    product = cache.get_term(uri)
    if product is None:
        return {"error": "not_found", "product": args.get("product")}
    if product.get("elementType") != "product":
        return {"error": "not_a_product", "id": product.get("id")}

    supported = product.get("perSurfaceSupportsColorMode") or []
    if not supported:
        return {"error": "no_per_surface_color",
                "product": _ref(cache, uri, language),
                "hint": ("This product declares no perSurfaceSupportsColorMode, so colour "
                         "is not a per-surface axis for it (SD-0068 closed semantics).")}

    channels = {u: n for u in supported
                if (n := colornotation.channel_count(cache.get_term(u))) is not None}
    surfaces = [s for s in (args.get("surfaces") or []) if isinstance(s, str)]
    # SD-0083: faces follow the setup. Without explicit surfaces, take them from
    # the given setup, or from the product's only setup; two-faced setups map
    # the pair notation directly (front/back, outside/inside, face/back).
    setup_note = None
    many_faces: list[str] = []
    if not surfaces:
        setup_uri = _full_uri(args["setup"]) if args.get("setup") else None
        if not setup_uri:
            sup = product.get("supportsSetupModel") or []
            setup_uri = sup[0] if len(sup) == 1 else None
        if setup_uri:
            faces, _panels = completeness.setup_faces(cache, setup_uri)
            if len(faces) == 2:
                surfaces = faces
                setup_note = f"faces from setup {setup_uri.rsplit('/', 1)[-1]}: {faces[0]}/{faces[1]}"
            elif faces:
                # SD-0102: multi-page. An equal pair is every face; an unequal pair asks per part.
                many_faces = faces
                setup_note = (f"setup {setup_uri.rsplit('/', 1)[-1]} has {len(faces)} faces "
                              f"({', '.join(faces)}); an equal pair (4/4) means every face, an unequal "
                              "pair must be stated per part (cover …, inside …)")
        else:
            setup_note = ("product has several setups and none was given — surfaces default to "
                          "front/back; pass 'setup' (or 'surfaces') so the faces match the fold")

    try:
        if many_faces:
            resolution = colornotation.resolve_many(args.get("notation", ""), supported, channels, many_faces)
        else:
            resolution = colornotation.resolve(
                args.get("notation", ""), supported, channels,
                surfaces or colornotation.SURFACES)
    except colornotation.NotationError:
        return {"error": "not_pair_notation",
                "notation": args.get("notation"),
                "hint": ("Expected two counts separated by '/' or '+', e.g. '4/4', '4/1', "
                         "'4 + 4'. A single colour (e.g. 'CMYK') is a term lookup — use "
                         "ptpge_search_terms instead.")}

    payload = resolution.to_dict()
    payload["product"] = _ref(cache, uri, language)
    if setup_note:
        payload["surfaces_note"] = setup_note
    # Label the URIs so the agent can put the question to a human unaided.
    for entry in payload.get("needs_disambiguation", []):
        if entry.get("reason") != "surface_count":
            continue
        entry["candidate_labels"] = [
            [_ref(cache, u, language) for u in combo] for combo in entry["candidates"]
        ]
    for surface in payload["surfaces"].values():
        if surface.get("binding"):
            surface["binding_labels"] = [_ref(cache, u, language) for u in surface["binding"]]
    if payload.get("needs_disambiguation"):
        payload["guidance"] = ("Put the question to the user. Do not infer the answer: the "
                               "same notation means different products on different presses.")
        # SD-0071 §9: count where the shorthand forced a question — template,
        # surface, number, how many readings stayed open. Structure only.
        for entry in payload["needs_disambiguation"]:
            if entry.get("reason") == "surface_count":
                learning.record_colour_question(
                    uri, entry.get("surface", "?"), entry.get("count", -1),
                    len(entry.get("candidates") or []))
    return payload


def _template_accepts(cache: "VocabularyCache", product: dict, var_tail: str, values: list) -> bool | None:
    """Does this product template's envelope accept these values for this variable?
    True / False, or None when the variable is not envelope-mapped (numeric, commercial) — then it does not count."""
    if var_tail == WEIGHT_VARIABLE and values and isinstance(values[0], (int, float)):
        env = product.get(WEIGHT_ENVELOPE)
        if env is None:
            return False
        band = _band_for_weight(cache, values[0])
        return bool(band) and band["id"] in env
    mapping = VARIABLE_ENVELOPE.get(var_tail)
    if mapping is None or not values or not isinstance(values[0], str):
        return None
    env = product.get(mapping[0])
    if env is None:
        return False
    env = list(env)
    if var_tail == "variables/features/surface-finish":
        env += list(product.get("perSurfaceSupportsEmbellishment") or [])
    if var_tail in NULL_VALUES:
        env.append(NULL_VALUES[var_tail])
    return all(_full_uri(v) in env for v in values)


def also_offered_by(cache: "VocabularyCache", current_uri: str, bindings: list, language: str, limit: int = 5) -> list:
    """Product templates whose envelopes accept EVERY bound value the current template rejects — and all the
    others too. Ranked by how many bindings they accept; the current template is excluded. Deterministic: data only.
    This is how «a poster on aluminium composite» finds Panel prints (12.10.2026)."""
    checks = []  # (var_tail, values)
    for b in bindings or []:
        var_tail = _full_uri(b.get("variable", ""))[len(_BASE):]
        values = b.get("values") if "values" in b else [b.get("value")]
        checks.append((var_tail, values))
    out = []
    all_terms = getattr(cache, "all_terms", None)
    if all_terms is None:
        return []
    for uri, t in all_terms().items():
        if t.get("elementType") != "product" or t.get("status") == "deprecated" or uri == current_uri:
            continue
        accepted = rejected = 0
        for var_tail, values in checks:
            r = _template_accepts(cache, t, var_tail, values)
            if r is True: accepted += 1
            elif r is False: rejected += 1
        if rejected == 0 and accepted > 0:
            out.append((accepted, _ref(cache, uri, language)))
    out.sort(key=lambda x: (-x[0], x[1].get("id", "")))
    return [dict(r, acceptsBindings=n) for n, r in out[:limit]]



# SD-0066 / 12.10.2026: the identity is in mm; the binding may say cm, m, in, pt. Converted here,
# before validation and before the fingerprint — never stored in any other unit.
_MM_PER = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "inch": 25.4, "\"": 25.4, "pt": 25.4 / 72.0}


def _normalize_units(bindings: list) -> list:
    """Custom-width/height bindings with a `unit` other than mm → value in mm (rounded to 0.1), the stated
    value/unit kept as statedValue/statedUnit. Other bindings pass through untouched."""
    out = []
    for b in bindings or []:
        if not isinstance(b, dict):
            out.append(b); continue
        tail = _full_uri(b.get("variable", ""))[len(_BASE):]
        unit = str(b.get("unit") or "").strip().lower()
        if tail in (CUSTOM_WIDTH_VARIABLE, CUSTOM_HEIGHT_VARIABLE) and unit and unit != "mm" \
                and isinstance(b.get("value"), (int, float)) and unit in _MM_PER:
            nb = dict(b)
            nb["statedValue"], nb["statedUnit"] = b["value"], unit
            mm = round(float(b["value"]) * _MM_PER[unit], 1)
            nb["value"] = int(mm) if mm == int(mm) else mm
            nb.pop("unit", None)
            out.append(nb)
        else:
            out.append(b)
    return out

def validate_payload(cache: "VocabularyCache", args: dict) -> object:
    language = args.get("language", "en")
    uri = _full_uri(args.get("product", ""))
    product = cache.get_term(uri)
    if product is None:
        return {"error": "not_found", "product": args.get("product")}
    if product.get("elementType") != "product":
        return {"error": "not_a_product", "id": product.get("id")}

    args = dict(args); args["bindings"] = _normalize_units(list(args.get("bindings", []) or []))
    results, advisories, rules = [], [], []
    all_ok = True
    bound_weight = None
    bound_class = None      # SD-0076
    bound_coating = None    # SD-0076
    # SD-0066: custom-mål — samle kryssvariabel-kontekst under løkka.
    bound_format = None
    custom_dims: dict[str, float] = {}
    for b in args.get("bindings", []) or []:
        var_uri = _full_uri(b.get("variable", ""))
        var_tail = var_uri[len(_BASE):]
        values = b.get("values") if "values" in b else [b.get("value")]
        # SD-0076: remember class / coating for the cross-axis rule after the loop
        if var_tail == CLASS_VARIABLE and isinstance(values[0], str):
            bound_class = _full_uri(values[0])
        if var_tail == COATING_VARIABLE and isinstance(values[0], str):
            bound_coating = _full_uri(values[0])
        entry = {
            "variable": var_tail,
            "surface": b.get("surface") or None,
            "value": b.get("values") if "values" in b else b.get("value"),
        }
        # SD-0071: provenance travels with the binding and is echoed back, but
        # never reaches the fingerprint — identity is the product, not the
        # conversation that produced it.
        if b.get("provenance"):
            entry["provenance"] = b["provenance"]
        # SD-0066: custom-width / custom-height — numerisk i mm; per-binding
        # sjekkes range (produktets customSizeRange foran variabelens 5–50000);
        # kryssvariabel-reglene (påkrevd-iff, normalisering) etter løkka.
        if var_tail in (CUSTOM_WIDTH_VARIABLE, CUSTOM_HEIGHT_VARIABLE) \
                and isinstance(values[0], (int, float)):
            dim = float(values[0])
            custom_dims[var_tail] = dim
            if b.get("statedUnit"):
                entry["stated"] = f"{b['statedValue']} {b['statedUnit']}"
                entry["note"] = f"Stated as {b['statedValue']} {b['statedUnit']}; the identity carries {values[0]} mm."
            axis = "Width" if var_tail == CUSTOM_WIDTH_VARIABLE else "Height"
            csr = product.get("customSizeRange") or {}
            # SD-0067: symmetrisk {min, max}; eldre minWidth/maxWidth-form
            # aksepteres som fallback.
            lo = csr.get("min", csr.get(f"min{axis}", 5))
            hi = csr.get("max", csr.get(f"max{axis}", 50000))
            if lo <= dim <= hi:
                entry.update(status="in_range", unit="mm")
            else:
                entry.update(status="out_of_range", unit="mm",
                             note=f"{dim} mm is outside "
                                  f"{'this product’s customSizeRange' if csr else 'the global sanity range'} "
                                  f"[{lo}, {hi}] mm.")
                all_ok = False
            results.append(entry)
            continue
        if var_tail == FORMAT_VARIABLE and values and isinstance(values[0], str):
            bound_format = _full_uri(values[0])
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
                                 note="Weight band is outside this product's envelope.",
                                 allowed=[_ref(cache, u, language) for u in env])
                    all_ok = False
            results.append(entry)
            continue
        # SD-0070 / SD-0076: numeric mm axes (substrate-thickness, spine-thickness)
        # against the template's {min,max} range.
        if var_tail in NUMERIC_RANGE_AXES and isinstance(values[0], (int, float)):
            mm = values[0]
            env_key = NUMERIC_RANGE_AXES[var_tail]
            rng = product.get(env_key)
            if rng is None:
                entry.update(status="not_supported",
                             note=f"Product declares no {env_key} (closed semantics).")
                all_ok = False
            else:
                lo, hi = rng.get("min"), rng.get("max")
                entry["range"] = {"min": lo, "max": hi, "unit": rng.get("unit", "mm")}
                if (lo is not None and mm < lo) or (hi is not None and mm > hi):
                    entry.update(status="out_of_range",
                                 note=f"{mm:g} mm is outside this product's thickness "
                                      f"range [{lo:g}, {hi:g}] mm. Canonical unit is mm "
                                      "(1 mil = 0.0254 mm; 14 pt = 0.356 mm; "
                                      "3/16 in = 4.76 mm).")
                    all_ok = False
                else:
                    entry["status"] = "in_range"
            results.append(entry)
            continue
        # SD-0104: a named spot ink — <matching-system term>/<code>; form only, never a list.
        if var_tail == spotink.SPOT_INK_VARIABLE:
            parsed = [spotink.parse_value(v, cache) for v in values]
            if all(parsed):
                entry.update(status="named_ink",
                             inks=[{"system": p["system"].rsplit("/", 1)[-1], "code": p["code"],
                                    "systemLabel": _ref(cache, _BASE + p["system"], language).get("label")} for p in parsed],
                             note="Checked for form under its matching system; the code itself is the system's own (SD-0104).")
            else:
                entry.update(status="invalid_ink_value",
                             note="A spot ink is <matching-system term>/<code> under printing/standards/color-systems/"
                                  "color-matching-systems — e.g. …/pantone-matching-system/300-c (SD-0104).")
                all_ok = False
            results.append(entry)
            continue
        # Envelope-mapped enum variables.
        mapping = VARIABLE_ENVELOPE.get(var_tail)
        if mapping is None:
            scope_note = ("numeric; topology legality is an implementation's rule, not the envelope's"
                          if var_tail == "variables/configuration/page-count"
                          else "commercial; no envelope in the specification"
                          if var_tail.startswith("variables/order/")
                          else "no envelope mapping for this variable")
            entry.update(status="not_checked", note=scope_note)
            results.append(entry)
            continue
        env_key, _scope = mapping
        env = product.get(env_key)
        # The ordered surface-finish STACK (SD-0040 §9: matte > spot-uv) may carry an
        # embellishment as its top layer — membership is checked against both
        # per-surface envelopes. Keeps the published worked example valid.
        if var_tail == "variables/features/surface-finish" and env is not None:
            env = list(env) + list(product.get("perSurfaceSupportsEmbellishment") or [])
        # SD-0088: «none» is always in a feature envelope
        if var_tail in NULL_VALUES and env is not None and NULL_VALUES[var_tail] not in env:
            env = list(env) + [NULL_VALUES[var_tail]]
        if env is None:
            entry.update(status="not_supported", envelope=env_key,
                         note=f"Product declares no {env_key} (closed semantics).")
            all_ok = False
            results.append(entry)
            continue
        bad = [v for v in values if _full_uri(v) not in env]
        entry["envelope"] = env_key
        if bad:
            # Selvkorrigering for agenter: si ikke bare hva som er ulovlig —
            # legg ved hele den lovlige menyen for akkurat denne variabelen.
            entry.update(status="not_in_envelope",
                         offending=[_full_uri(v) for v in bad],
                         allowed=[_ref(cache, u, language) for u in env])
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

    # SD-0066: kryssvariabel-regler for custom-mål (spesifikasjonen flagger; implementasjonen
    # håndhever). Én identitet per fysisk objekt: bredde ≤ høyde, rotasjon
    # via orientation.
    is_customized = bound_format == CUSTOMIZED_FORMAT_URI
    cw = custom_dims.get(CUSTOM_WIDTH_VARIABLE)
    ch = custom_dims.get(CUSTOM_HEIGHT_VARIABLE)
    if is_customized and (cw is None or ch is None):
        rules.append({
            "rule": "custom_size_required", "status": "violation",
            "note": "Format = Customized requires BOTH custom-width and "
                    "custom-height (mm). Without them the identity is "
                    "underspecified — two different sizes would share one "
                    "fingerprint (SD-0066)."})
        all_ok = False
    if custom_dims and not is_customized:
        rules.append({
            "rule": "custom_size_without_customized", "status": "violation",
            "note": "custom-width/custom-height may only be bound when "
                    "variables/configuration/format = "
                    "printing/configurations/formats/customized (SD-0066)."})
        all_ok = False
    if cw is not None and ch is not None and cw > ch:
        rules.append({
            "rule": "not_normalized", "status": "violation",
            "note": f"Canonical form is width ≤ height: bind "
                    f"custom-width={ch:g}, custom-height={cw:g} and express "
                    f"the rotation via variables/configuration/orientation="
                    f"landscape (SD-0066)."})
        all_ok = False

    # SD-0076: substrate class and coating must agree (PS1–PS4 coated, PS5 uncoated).
    if bound_class and bound_coating:
        clash = ((bound_class in COATED_CLASSES and bound_coating == UNCOATED_URI) or
                 (bound_class in UNCOATED_CLASSES and bound_coating == COATED_URI))
        if clash:
            rules.append({
                "rule": "substrate_class_coating_mismatch", "status": "violation",
                "note": "ISO 12647-2 classes PS1–PS4 are coated papers and PS5 is uncoated; "
                        "the bound substrate-coating contradicts the bound substrate-class (SD-0076)."})
            all_ok = False

    # SD-0083: surfaces follow the setup; required axes; envelope-implied values.
    comp = completeness.completeness(cache, product, list(args.get("bindings", []) or []),
                                     lambda u: _ref(cache, u, language), language)
    for e in comp["surface_errors"]:
        for r in results:
            if r["variable"] == e["variable"] and r.get("surface") == e["surface"]:
                r.update(status="surface_not_in_setup", allowed_surfaces=e["allowed"], note=e["note"])
        all_ok = False
    for b in args.get("bindings", []) or []:
        if b.get("_implied_surface"):
            tail = completeness._tail(_full_uri(b.get("variable", "")))
            for r in list(results):
                if r["variable"] == tail and r.get("surface") is None:
                    r["surface"] = b["_implied_surface"]; r["surface_provenance"] = "envelope-implied"
                    for extra in (b.get("_expand_to") or []):
                        r2 = dict(r); r2["surface"] = extra
                        r2["note"] = "Stated without a face → applies to every face of the setup (SD-0083 D5)."
                        results.append(r2)
                    if b.get("_expand_to"):
                        r["note"] = "Stated without a face → applies to every face of the setup (SD-0083 D5)."
            b.pop("_implied_surface", None); b.pop("_expand_to", None)
    for ib in comp["implied"]:
        results.append({"variable": ib["variable"], "surface": None, "value": ib["value"],
                        "provenance": "envelope-implied", "status": "envelope_implied",
                        "note": "The envelope offers exactly one value; it is written into the identity (SD-0083 D1)."})
    # SD-0083 R5: a value under a material entails the substrate type.
    _ent = {}
    _stated_type = None
    for b in args.get("bindings", []) or []:
        _v = completeness._tail(_full_uri(b.get("variable", "")))
        if _v == "variables/substrate/substrate-type":
            _stated_type = _full_uri(b.get("value", "")) if isinstance(b.get("value"), str) else _stated_type
            continue
        for val in ([b.get("value")] if "value" in b else list(b.get("values") or [])):
            m = _cfs_entailed_type(val)
            if m:
                _ent.setdefault(m, _v)
    if _ent:
        mats = sorted(_ent)
        if len(mats) > 1 or (_stated_type and _stated_type not in mats):
            results.append({"variable": "variables/substrate/substrate-type", "surface": None,
                            "value": _stated_type, "status": "substrate_type_conflict",
                            "entailed": [m[len(_BASE):] for m in mats],
                            "note": "The bound substrate values sit under a different material than the "
                                    "stated (or each other's) substrate type (SD-0083 R5)."})
            all_ok = False
        elif not _stated_type:
            results.append({"variable": "variables/substrate/substrate-type", "surface": None,
                            "value": mats[0][len(_BASE):], "provenance": "entailed", "status": "entailed",
                            "entailedBy": _ent[mats[0]],
                            "note": "Follows from the bound " + _ent[mats[0]].rsplit("/", 1)[-1] +
                                    " value; written into the identity (SD-0083 R5)."})
    # SD-0104: every spot-color layer carries a named ink; an ink without a layer is an error.
    _ink_errors, _ink_needs = spotink.check(list(args.get("bindings", []) or []),
                                            list((comp.get("setup") or {}).get("surfaces") or []), cache, language)
    for e in _ink_errors:
        if e["reason"] == "ink_without_spot_layer":
            results.append({"variable": e["variable"], "surface": e["surface"], "value": None,
                            "status": "ink_without_spot_layer", "note": e["note"]})
            all_ok = False
    comp["needs_disambiguation"].extend(_ink_needs)
    advisories.extend(comp["advisories"])
    # SD-0084 R6 — what may stand together: read from the same resolution module
    # as the fingerprint (exclusive groups, standalone, multi-instance).
    try:
        _r6 = _cfs_resolve(product, list(args.get("bindings", []) or []), cache.get_term)
        _r6_errors = [e for e in _r6["errors"] if e.get("rule") == "exclusive_group_conflict"]
    except Exception:  # pragma: no cover
        _r6_errors = []
    for e in _r6_errors:
        rules.append({"rule": "exclusive_group_conflict", "status": "violation",
                      "variable": str(e.get("variable", ""))[len(_BASE):], "surface": e.get("surface"),
                      "reason": e.get("reason"), "group": e.get("group"),
                      "values": [str(v)[len(_BASE):] for v in (e.get("values") or ([e["value"]] if e.get("value") else []))],
                      "note": ("These values cannot stand together on one face (specification data: "
                               "exclusiveGroups / standalone / multiInstance, SD-0084 R6). No identity is issued.")})
        all_ok = False
    complete = not comp["needs_disambiguation"] and not comp["surface_errors"] \
        and not any(r.get("status") == "substrate_type_conflict" for r in results) \
        and not _r6_errors

    resp = {
        "product": _ref(cache, uri, language),
        "validInEnvelope": all_ok,
        "complete": complete,
        "bindings": results,
        "advisories": advisories,
        "scope": "Envelope validation against the specification only. Cross-variable legality "
                 "(e.g. panel counts per topology) and vendor capability are "
                 "an implementation's services (a configurator), not the specification's.",
    }
    if rules:
        resp["rules"] = rules
    if not all_ok:
        # Another template may take exactly what this one rejects — say so, so an agent switches instead of giving up.
        alt = also_offered_by(cache, uri, args.get("bindings", []) or [], language)
        if alt:
            resp["alsoOfferedBy"] = alt
            resp["switchHint"] = ("Every bound value is in the envelope of " + alt[0].get("label", alt[0].get("id", "")) +
                                  " — validate again with that product instead of dropping the value.")
    if comp["setup"]:
        resp["setup"] = comp["setup"]
    resp["required"] = comp.get("required") or []
    if comp["needs_disambiguation"]:
        resp["needs_disambiguation"] = comp["needs_disambiguation"]
        resp["guidance"] = ("Put each question to the user verbatim and bind the answer. "
                            "ptpge_fingerprint refuses until the configuration is complete — "
                            "one specified product, one identity (SD-0083).")

    # SD-0071: surface what was never confirmed by the buyer. The envelope is
    # still valid — an inferred value can be perfectly legal — but a vendor or
    # marketplace may want confirmation before accepting the order, and a
    # dispute afterwards can be settled on data rather than recollection.
    unconfirmed = [
        {"variable": e["variable"], "surface": e.get("surface"),
         "provenance": e["provenance"]}
        for e in results
        if e.get("provenance") and e["provenance"] != "confirmed"
    ]
    stated = sum(1 for e in results if e.get("provenance"))
    if unconfirmed:
        resp["provenance"] = {
            "unconfirmed": unconfirmed,
            "note": ("These values were not confirmed by the buyer. They do not affect "
                     "the fingerprint — identity is the product, not the conversation — "
                     "but the order may be refused where confirmation is required."),
        }
    elif stated:
        resp["provenance"] = {"unconfirmed": [], "note": "All stated values were buyer-confirmed."}
    return resp


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


def fingerprint_payload(args: dict, cache: "VocabularyCache | None" = None) -> object:
    """SD-0083: an identity is issued only for a valid, complete configuration.
    Validation runs first; envelope-implied bindings are written into the
    canonical string; a missing required axis or a wrong surface returns the
    validator's questions instead of a hash."""
    implied: list[dict] = []
    validation = None
    args = dict(args); args["bindings"] = _normalize_units(list(args.get("bindings", []) or []))
    if cache is not None and args.get("product"):
        validation = validate_payload(cache, {"product": args.get("product"),
                                              "bindings": [dict(b) for b in (args.get("bindings", []) or [])],
                                              "language": args.get("language", "en")})
        if isinstance(validation, dict) and "error" not in validation:
            refusal = None
            if any(r.get("rule") == "exclusive_group_conflict" for r in (validation.get("rules") or [])):
                refusal = "exclusive_group_conflict"          # SD-0084 R6
            elif not validation.get("validInEnvelope", True):
                refusal = "not_valid_in_envelope"
            elif validation.get("needs_disambiguation"):
                refusal = "incomplete"
            if refusal:
                return {"error": "not_fingerprintable", "reason": refusal,
                        "needs_disambiguation": validation.get("needs_disambiguation", []),
                        "validation": validation,
                        "note": ("No identity is issued for an incomplete or invalid configuration "
                                 "(SD-0083). Answer the questions (or fix the surfaces) and call again.")}
    # Normalize to cfs/1 form (full URIs, numbers kept) before resolution.
    norm: list[dict] = []
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
        norm.append(nb)
    config = {"product": _full_uri(args.get("product", "")), "bindings": norm}
    if validation is not None and "error" not in validation:
        # The normative resolution step (cfs/1 § 11, SD-0083): the same module
        # runs in tools/, the configurator and the engine — one resolved
        # configuration from any implementation. The validator above decides
        # the refusal; resolution decides the bytes.
        res = _cfs_resolve(cache.get_term(config["product"]) or {}, norm, cache.get_term)
        if not res["ok"]:
            return {"error": "not_fingerprintable",
                    "reason": ("exclusive_group_conflict" if any(e.get("rule") == "exclusive_group_conflict" for e in res["errors"])
                               else "not_valid_in_envelope" if res["errors"] else "incomplete"),
                    "needs_disambiguation": validation.get("needs_disambiguation", []),
                    "resolution": {"errors": res["errors"], "incomplete": res["incomplete"]},
                    "validation": validation,
                    "note": ("No identity is issued for an incomplete or invalid configuration "
                             "(SD-0083). Answer the questions (or fix the surfaces) and call again.")}
        config["bindings"] = res["bindings"]
        implied = [{"variable": ib["variable"][len(_BASE):], "value": ib["value"]} for ib in res["implied"]]
    out = {"algorithm": "ptpge-cfs/1", "profiles": {}}
    visuals = bool(args.get("visuals"))
    for profile in ("spec", "offer"):
        s = _cfs_canonical(config, profile)
        h = _cfs_fingerprint(config, profile)
        entry = {"canonical": s, "sha256": h, "short": _cfs_short(h),
                 "resolverUrl": "https://ptpge.org/f/" + h}
        _reg.register_async(h, s)
        if visuals:
            try:
                # SD-0108: the cfs/1 "offer" profile carries an order cluster
                # but no vendor — by content it is a request, and its mark is
                # the request species (capped cross, no breath). The offer
                # species needs a vendor identity in the hash; that arrives
                # with the marketplace build (SD-0108, build later).
                entry["markSvg"] = _fm.mark_svg(h, species="spec" if profile == "spec" else "request")
            except ValueError as exc:
                # mark/3: the offer species carries a vendor's breath in the
                # rings — without a vendor identity there is nothing to draw.
                # Degrade gracefully instead of failing the whole call: the
                # hashes and resolver URLs above remain authoritative, and
                # the official mark lives on the register page.
                entry["markNote"] = str(exc) + " — mark omitted; see resolverUrl"
            qr = _fm.qr_svg(entry["resolverUrl"])
            if qr:
                entry["qrSvg"] = qr
            else:
                entry["qrNote"] = "qrcode package not installed on server — QR omitted"
        out["profiles"][profile] = entry
    if validation is not None and "error" not in validation:
        out["validated"] = True
        out["bindingsUsed"] = [{"variable": nb["variable"][len(_BASE):], "surface": nb.get("surface"),
                                "value": nb.get("values", nb.get("value"))} for nb in config["bindings"]]
        if implied:
            out["envelopeImplied"] = [{"variable": ib["variable"], "value": ib["value"]} for ib in implied]
        out["note"] = ("Validated and complete (SD-0083): required axes bound, surfaces on the "
                       "setup's faces; envelope-implied values written into the identity.")
        if validation.get("advisories"):
            out["advisories"] = validation["advisories"]
    else:
        out["note"] = ("Input was serialized as given — no vocabulary cache available for "
                       "validation in this context.")
    out["registration"] = ("Fingerprints are auto-registered with the public resolver "
                           "(best-effort, self-verifying) — the resolverUrl becomes a "
                           "permanent page within seconds.")
    return out


_HEX = re.compile(r"[0-9a-f]{16}(?:[0-9a-f]{48})?$")


def expand_payload(cache: "VocabularyCache", args: dict) -> object:
    """ptpge_expand_fingerprint — look a fingerprint up in the public resolver.

    The resolver page (ptpge.org/f/<hash>, content-negotiated JSON) is the
    permanent record written at registration (SD-0058); this tool re-labels
    its bindings in the requested language from the local vocabulary cache
    so MIS/ERP integrators get the same read-back over MCP as over HTTP.
    """
    raw = str(args.get("fingerprint", "")).strip().lower()
    raw = raw.rsplit("/", 1)[-1]
    if raw.endswith(".json"):
        raw = raw[:-5]
    if not _HEX.match(raw):
        raise ValueError("fingerprint must be a 64-hex SHA-256 or its 16-hex short form")
    language = args.get("language", "en") or "en"
    base = os.environ.get("PTPGE_RESOLVER_BASE", "https://ptpge.org/f/")
    url = base + raw
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                   "User-Agent": f"ptpge-mcp/{__version__}"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            body = resp.read().decode("utf-8")
            final = resp.geturl()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"status": "unknown", "fingerprint": raw, "resolverUrl": url,
                    "note": ("Not registered with the resolver. A fingerprint is a hash — it "
                             "cannot be inverted, only looked up. Compute it once through "
                             "ptpge_fingerprint and it registers itself.")}
        raise
    doc = json.loads(body)
    full = final.rsplit("/", 1)[-1]
    bindings = []
    for b in doc.get("bindings", []) or []:
        nb = dict(b)
        var = b.get("variable")
        if var:
            nb["variableLabel"] = _ref(cache, _full_uri(var), language).get("label")
        val = b.get("value")
        if isinstance(val, str) and val.startswith(("printing/", "ordering/", "variables/", "https://")):
            nb["label"] = _ref(cache, _full_uri(val), language).get("label") or b.get("label")
        bindings.append(nb)
    prod = doc.get("product") or {}
    if prod.get("uri"):
        prod = dict(prod, label=_ref(cache, prod["uri"], language).get("label") or prod.get("label"))
    return {
        "status": "resolved",
        "algorithm": doc.get("algorithm", "ptpge-cfs/1"),
        "profile": doc.get("matchedProfile"),
        "fingerprint": full if _HEX.match(full or "") else raw,
        "resolverUrl": base + (full if _HEX.match(full or "") else raw),
        "product": prod,
        "bindings": bindings,
        "canonical": doc.get("canonical"),
        "dataVersion": cache.version.get("version"),
        "note": ("Read-back for MIS/ERP. Bindings are the manufacturable configuration "
                 "(profile 'spec') or that plus the commercial cluster (profile 'offer'); "
                 "file, delivery date and price are transaction data keyed by the offer "
                 "fingerprint and are never part of it."),
    }


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
        hits = cache.search(query=query, limit=limit, groups=groups, language=language,
                            include_deprecated=bool(args.get("include_deprecated", False)))
        # SD-0071 §9: a lookup that failed is the only thing worth learning from.
        # Phrase and score only — never who asked. See ptpge_mcp/learning.py.
        # `query_language`, never `language`: the latter says which labels to
        # RETURN, so a Norwegian agent asking "visittkort" with language=en
        # would otherwise be filed as English and the Norwegian gap missed.
        learning.record_search(query, hits, args.get("query_language"))
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

    if name == "ptpge_resolve_color_notation":
        return color_notation_payload(cache, args)

    if name == "ptpge_fingerprint":
        return fingerprint_payload(args, cache)

    if name == "ptpge_expand_fingerprint":
        return expand_payload(cache, args)

    if name == "ptpge_check_domain":
        from .check import check_domain
        return check_domain(str(args.get("domain", "")), cache, args.get("document") or None)

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# Streamable HTTP transport (stateless JSON mode) — JSON-RPC plumbing
# ---------------------------------------------------------------------------

# Protocol revisions we know how to speak. We echo the client's requested
# version when we recognise it; otherwise we answer with our latest, per the
# MCP version-negotiation rules.
SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18", "2026-07-28")
LATEST_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[-1]
# 2026-07-28 (SEP-2575): protokollen er stateless, initialize-håndtrykket er
# borte i moderne æra, og server/discover er OBLIGATORISK. Vi er dual-era:
# initialize besvares fortsatt (legacy-klienter), server/discover + per-
# request-metadata dekker moderne klienter. Vi var stateless hele veien, så
# overgangen er additiv.

SERVER_INSTRUCTIONS = (
    "PTPGE vocabulary server — the open specification of print (printing & graphic industry). "
    "Use ptpge_search_terms to find terms, ptpge_get_term for full context "
    "on one term, ptpge_get_version for dataset version/statistics."
)


def negotiate_protocol_version(requested: object) -> str:
    if isinstance(requested, str) and requested in SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return LATEST_PROTOCOL_VERSION


_SERVER_INFO = {"name": "ptpge-mcp", "title": "PTPGE MCP — the open specification of print"}


def _rpc_result(msg_id: object, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _modern_result(msg_id: object, result: dict) -> dict:
    """2026-07-28-form: resultType er påkrevd i moderne resultater, og
    serveren identifiserer seg i hvert svars _meta (statelessness — ingen
    tilstand fra initialize). Legacy-klienter skal per spec behandle
    fraværende resultType som "complete", og ekstra felt er ufarlige, så
    formen er trygg for begge æraer."""
    result.setdefault("resultType", "complete")
    meta = result.setdefault("_meta", {})
    meta.setdefault("io.modelcontextprotocol/serverInfo",
                    dict(_SERVER_INFO, version=__version__))
    return _rpc_result(msg_id, result)


#: JSON-RPC methods whose result is a pure function of (dataset, request) and
#: may therefore be validated with an ETag. Everything else — notifications,
#: errors, anything with a side effect — is never tagged.
_CACHEABLE_METHODS = frozenset({
    "tools/list", "tools/call", "resources/list", "resources/templates/list",
    "prompts/list", "server/discover",
})


def _result_etag(cache: "VocabularyCache", method: str | None, reply: object) -> str | None:
    """A strong ETag over the JSON-RPC *result* plus the dataset it came from.

    Extends the ttlMs/cacheScope work of SEP-2549 toward the ETag validation
    named in the MCP roadmap (HTTP-Native Transport Unification): a client can
    revalidate cheaply instead of re-downloading a result it already holds.

    The JSON-RPC `id` is deliberately excluded — it identifies the *call*, not
    the *answer*. A 304 therefore means «the result you cached is still
    current; reuse it under your current request id». Our tools are pure reads
    over an immutable dataset snapshot, so the same request against the same
    (dataVersion, generated) always yields the same result.
    """
    if method not in _CACHEABLE_METHODS:
        return None
    if not isinstance(reply, dict) or "result" not in reply:
        return None          # errors and notifications are never validated
    try:
        version = cache.version or {}
    except Exception:
        return None
    seed = json.dumps(
        {"data": version.get("version"), "built": version.get("generated"),
         "server": __version__, "method": method, "result": reply["result"]},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return '"' + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32] + '"'


def _if_none_match(header: str | None, etag: str) -> bool:
    """RFC 9110 If-None-Match: a comma-separated list, or `*`."""
    if not header:
        return False
    candidates = [c.strip() for c in header.split(",")]
    return "*" in candidates or etag in candidates


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
                "title": "PTPGE MCP — the open specification of print",
                "version": __version__,
            },
            "instructions": SERVER_INSTRUCTIONS,
        })

    if method == "server/discover":
        # SEP-2575: OBLIGATORISK i 2026-07-28 — annonser versjoner,
        # kapabiliteter og identitet uten noen forutgående tilstand.
        return _modern_result(msg_id, {
            "supportedVersions": list(SUPPORTED_PROTOCOL_VERSIONS),
            "capabilities": {"tools": {"listChanged": False}},
            "instructions": SERVER_INSTRUCTIONS,
            "ttlMs": 3600000,
            "cacheScope": "public",
        })

    if method == "ping":
        # Fjernet i 2026-07-28, beholdt for legacy-klienter (dual-era).
        return _rpc_result(msg_id, {})

    if method == "tools/list":
        tools = [t.model_dump(by_alias=True, exclude_none=True) for t in TOOL_DESCRIPTORS]
        # SEP-2549: liste-resultater bærer cache-hint i 2026-07-28.
        # Rekkefølgen er deterministisk (fast deskriptorliste) per SHOULD-kravet.
        return _modern_result(msg_id, {"tools": tools,
                                       "ttlMs": 3600000, "cacheScope": "public"})

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
        return _modern_result(msg_id, {
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
                 protected_paths: tuple[str, ...] = ("/mcp",),
                 strict_paths: tuple[str, ...] = ("/vision",)) -> None:
        super().__init__(app)
        self._tokens_file = tokens_file
        self._static = [t for t in (static_tokens or []) if t]
        self._allow_anon = allow_anon
        self._protected = protected_paths
        # strict paths cost money per call (AI vision) — the migration
        # grace (allow_anon) never applies to them.
        self._strict = strict_paths
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
        strict = any(request.url.path.startswith(p) for p in self._strict)
        gated = strict or any(request.url.path.startswith(p) for p in self._protected)
        if not self._enabled or not gated:
            if request.method == "OPTIONS":  # CORS preflights carry no token
                return await call_next(request)
            return await call_next(request)
        if request.method == "OPTIONS":
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
        if self._allow_anon and not strict:
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


def make_vision_endpoint():
    """Factory for the /vision handler — module-level so tests can mount it
    without building the full app (which loads the vocabulary cache)."""

    async def vision(request: Request) -> Response:
        """AI-vision extraction for the mapping-to-specification v2 flow.

        Takes a screenshot of a print e-commerce product page (Vistaprint,
        Helloprint, Flyeralarm, Onlineprinters, Cloudprinter, ...) and returns
        a structured extraction that separates what is SELECTED (highlighted
        tile, filled radio, summary line) from what is merely OFFERED — the
        distinction OCR cannot see. The client then maps values to specification
        terms with the deterministic matcher, so the fingerprint stays
        verifiable; the model only reads the page.

        Cost control: this route is on the token middleware's STRICT list —
        a valid personal capability token is always required, so every call
        is attributable and revocable. Requires ANTHROPIC_API_KEY; model via
        PTPGE_VISION_MODEL (default claude-haiku-4-5).
        """
        cors = _chat_cors_headers()
        cors["Access-Control-Allow-Headers"] = "content-type, x-ptpge-token, x-ptpge-chat-token"
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=cors)

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return JSONResponse(
                {"error": "vision_unavailable",
                 "message": "ANTHROPIC_API_KEY is not set on this server."},
                status_code=503, headers=cors)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "bad_request"}, status_code=400, headers=cors)
        image_b64 = (body.get("image") or "").strip()
        media_type = (body.get("media_type") or "image/jpeg").strip()
        if media_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
            return JSONResponse({"error": "bad_media_type"}, status_code=400, headers=cors)
        if not image_b64 or len(image_b64) < 100:
            return JSONResponse({"error": "empty_image"}, status_code=400, headers=cors)
        if len(image_b64) > 8_000_000:  # ~6 MB decoded — plenty after client downscale
            return JSONResponse({"error": "image_too_large",
                                 "detail": "Downscale the screenshot before upload (max ~6 MB)."},
                                status_code=413, headers=cors)

        system = (
            "You extract print-product configurations from e-commerce screenshots "
            "(Vistaprint, Helloprint, Flyeralarm, Onlineprinters, Cloudprinter and similar). "
            "Respond with ONLY a JSON object, no prose, using exactly this shape:\n"
            '{"page_language":"<bcp47>","vendor":"<name or null>","product":"<page product name>",'
            '"selected":[{"label":"<attribute>","value":"<selected value>"}],'
            '"offered":[{"label":"<attribute>","values":["<option>","..."]}],'
            '"quantity":"<selected print run or null>","notes":"<ambiguities or empty>"}\n'
            "Rules: An option is SELECTED only if the UI shows it chosen — highlighted/bordered "
            "tile, filled radio, checked box, or a summary line like 'Material: 135 gsm gloss'. "
            "For folded products, a size written 'A4 folded to A5' means FINISHED size A5 — "
            "report the finished size as the value (keep the full tile text in notes). "
            "A 'RECOMMENDED' badge is NOT selection. Every visible alternative goes under "
            "'offered'. Keep values verbatim in the page language, including units (gsm, mm). "
            "Ignore prices, delivery dates and reviews."
        )
        payload = {
            "model": os.getenv("PTPGE_VISION_MODEL", "claude-haiku-4-5"),
            "max_tokens": 1500,
            "system": system,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                              "data": image_b64}},
                {"type": "text", "text": "Extract the configuration from this screenshot."},
            ]}],
        }
        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(
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
            text = "".join(b.get("text", "") for b in data.get("content", [])
                           if b.get("type") == "text").strip()
        except Exception as exc:
            return JSONResponse({"error": "upstream_exception", "detail": str(exc)[:300]},
                                status_code=502, headers=cors)
        ms = int((time.monotonic() - t0) * 1000)
        # Strip a ```json fence if the model added one, then parse.
        cleaned = text
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            extraction = json.loads(cleaned)
        except Exception:
            # Give the client the raw text so it can fall back to OCR-style parsing.
            return JSONResponse({"raw": text, "ms": ms}, headers=cors)
        return JSONResponse({"extraction": extraction, "ms": ms}, headers=cors)


    return vision


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

    # Learning loop (SD-0071 §9). Defaults into tmp/, which .cpanel.yml creates
    # and rsync excludes — so what the vocabulary has learned survives a deploy.
    # Set PTPGE_LEARNING_FILE="" to switch the recorder off entirely.
    _lf = os.environ.get("PTPGE_LEARNING_FILE")
    if _lf is None:
        _lf = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "tmp", "learning.json")
    learning.configure(_lf or None)

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

    def _mcp_cors_headers() -> dict:
        """CORS for /mcp (0.28.8): a browser page on another origin may call the
        open server directly — trykkverk.no/prompt/ runs the agent's tool calls
        from the buyer's browser. Default '*' (the server is open, cost is gated
        elsewhere); PTPGE_MCP_CORS_ORIGIN locks it to one origin, '0' turns it off."""
        o = os.getenv("PTPGE_MCP_CORS_ORIGIN", "*")
        if o == "0":
            return {}
        return {"Access-Control-Allow-Origin": o, "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "content-type, if-none-match, mcp-protocol-version",
                "Access-Control-Expose-Headers": "ETag", "Access-Control-Max-Age": "86400", "Vary": "Origin"}

    async def handle_mcp_http(request: Request) -> Response:
        """Streamable HTTP transport endpoint (stateless JSON mode).

        POST: one JSON-RPC message (or a batch array) in, one JSON response
        out. Notifications get 202 Accepted with no body. GET/DELETE return
        405 — this server opens no server-initiated streams and keeps no
        sessions, by design (see v0.3.0 note in the module docstring).
        OPTIONS answers the browser's CORS preflight (0.28.8).
        """
        cors = _mcp_cors_headers()
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=cors)
        resp = await _handle_mcp_post(request)
        for k, v in cors.items():
            resp.headers[k] = v
        return resp

    async def _handle_mcp_post(request: Request) -> Response:
        if request.method != "POST":
            return Response(status_code=405, headers={"Allow": "POST, OPTIONS"})
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

        method = body.get("method") if isinstance(body, dict) else None
        etag = _result_etag(cache, method, reply)
        if not etag:
            return JSONResponse(reply)
        learning.flush()          # cheap no-op unless something was recorded
        headers = {"ETag": etag, "Cache-Control": "public, max-age=3600"}
        if _if_none_match(request.headers.get("if-none-match"), etag):
            return Response(status_code=304, headers=headers)
        return JSONResponse(reply, headers=headers)

    async def check_page(request: Request) -> HTMLResponse:
        """Paste a domain → what an agent finds. With ?domain= the report is rendered server-side (SD-0105),
        so the text exists without scripts; the JS keeps it live. See ptpge_mcp/checkpage.py."""
        from .checkpage import CHECK_HTML, check_html_for
        domain = (request.query_params.get("domain") or "").strip()
        if not domain:
            return HTMLResponse(CHECK_HTML)
        from .check import check_domain
        import asyncio
        try:
            report = await asyncio.get_running_loop().run_in_executor(None, check_domain, domain, cache, None)
        except Exception:
            report = None
        return HTMLResponse(check_html_for(report), headers={"Cache-Control": "public, max-age=300"})

    async def artwork_read(request: Request) -> Response:
        """POST /artwork — the PDF as the request body (Content-Type application/pdf) → bindings with
        provenance «artwork», plus what must be asked (SD-0107). Read in memory, never stored. Hidden for now:
        not in tools/list; becomes ptpge_read_artwork when it has settled."""
        from .agent import cfg as _agent_cfg
        try:
            from . import artwork as _aw
            import pikepdf  # noqa: F401
        except Exception:
            return JSONResponse({"error": "unavailable", "note": "artwork reader not installed on this server (pikepdf)"}, status_code=503)
        origin = request.headers.get("origin", "")
        allowed = _agent_cfg()["origins"] + ["https://gutenlex.com", "https://www.gutenlex.com"]
        cors = {"Access-Control-Allow-Origin": origin if origin in allowed else allowed[0],
                "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type", "Vary": "Origin"}
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=cors)
        cl = int(request.headers.get("content-length") or 0)
        if cl > _aw.MAX_BYTES:
            return JSONResponse({"error": "too_large", "note": "25 MB at most"}, status_code=413, headers=cors)
        data = await request.body()
        if not data.startswith(b"%PDF"):
            return JSONResponse({"error": "not_a_pdf", "note": "Send the PDF file as the request body (Content-Type: application/pdf)."}, status_code=400, headers=cors)
        import asyncio
        lang = request.query_params.get("language", "en")
        try:
            rep = await asyncio.get_running_loop().run_in_executor(None, _aw.read_pdf, data, cache, lang)
        except Exception as e:  # never leak a traceback; never keep the bytes
            rep = {"error": "read_failed", "note": str(e)[:200]}
        del data
        return JSONResponse(rep, status_code=200 if "error" not in rep else 422, headers={**cors, "Cache-Control": "no-store"})

    def _json_cors(request: Request) -> dict:
        """CORS for the JSON wrappers below: the playground hosts, ptpge.org and gutenlex.com may call them from a page."""
        from .agent import cfg as _agent_cfg
        origin = request.headers.get("origin", "")
        allowed = _agent_cfg()["origins"] + ["https://gutenlex.com", "https://www.gutenlex.com"]
        return {"Access-Control-Allow-Origin": origin if origin in allowed else allowed[0],
                "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type",
                "Vary": "Origin", "Cache-Control": "no-store"}

    async def _tool_json(request: Request, fn) -> Response:
        """POST /validate and POST /fingerprint (0.39.0): the same payloads as the MCP tools
        ptpge_validate_config / ptpge_fingerprint, reachable from a web page without an MCP client —
        so ptpge.org/mapping asks the specification instead of reproducing it. Nothing is stored."""
        cors = _json_cors(request)
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=cors)
        try:
            args = await request.json()
        except Exception:
            return JSONResponse({"error": "bad_request", "note": "JSON body {product, bindings[], language?} required"}, status_code=400, headers=cors)
        if not isinstance(args, dict) or not args.get("product"):
            return JSONResponse({"error": "bad_request", "note": "product required, e.g. ordering/products/booklets"}, status_code=400, headers=cors)
        import asyncio
        payload = await asyncio.get_running_loop().run_in_executor(None, fn, args)
        return JSONResponse(payload, headers=cors)

    async def validate_json(request: Request) -> Response:
        return await _tool_json(request, lambda a: validate_payload(cache, a))

    async def fingerprint_json(request: Request) -> Response:
        return await _tool_json(request, lambda a: fingerprint_payload(a, cache))

    async def check_json(request: Request) -> Response:
        """GET /check.json?domain=… — the same report as JSON (curl-able, CORS open)."""
        from .check import check_domain
        domain = request.query_params.get("domain", "")
        if not domain.strip():
            return JSONResponse({"error": "domain query parameter required, e.g. /check.json?domain=trykkverk.no"}, status_code=400,
                                headers={"Access-Control-Allow-Origin": "*"})
        import asyncio
        document = request.query_params.get("document") or None
        report = await asyncio.get_running_loop().run_in_executor(None, check_domain, domain, cache, document)
        return JSONResponse(report, headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-store"})

    async def playground(_request: Request) -> HTMLResponse:
        """Browser test console (v0.3.3) — same-origin JS that POSTs real
        JSON-RPC to /mcp. See ptpge_mcp/playground.py."""
        return HTMLResponse(PLAYGROUND_HTML)

    async def miss_report(_request: Request) -> HTMLResponse:
        """Browser console for finding what the vocabulary CANNOT resolve.

        The CLI (tools/search_miss_report.py) guards deploys with a fixed
        corpus; this is for trying phrases the moment you think of them.
        Same origin as /mcp, so it calls the real search directly.
        """
        from .missreport import page_html
        return HTMLResponse(page_html())

    async def learning_page(request: Request) -> HTMLResponse:
        """What real requests could not resolve — SD-0071 §9, accumulated.

        Every lookup through /mcp is judged; the failures land here. No caller
        is identified: phrases and counts only.
        """
        from .learningpage import locked_html, page_html as _lp
        key = os.environ.get("PTPGE_LEARNING_KEY")
        if not key:
            # No key configured on this instance: the page does not exist here.
            return HTMLResponse(locked_html(unconfigured=True), status_code=404)
        # A list of what the vocabulary cannot do is an internal instrument, not
        # a demo — the open mirror is unauthenticated by design, so this page
        # carries its own lock. ?key= once, then a cookie for the session.
        supplied = (request.query_params.get("key")
                    or request.cookies.get("ptpge_learning") or "")
        # Two keys, two rights. The read-only one can be mailed to a colleague:
        # it shows everything and changes nothing, so it cannot quietly redefine
        # what is in scope and cannot spend a model call. Revoking it does not
        # disturb the curator's key.
        curatable = bool(supplied) and secrets.compare_digest(supplied, key)
        readonly = os.environ.get("PTPGE_LEARNING_KEY_READONLY") or ""
        if not curatable and not (readonly and supplied
                                  and secrets.compare_digest(supplied, readonly)):
            return HTMLResponse(locked_html(), status_code=401)
        # The vocabulary itself answers the language question wherever it can;
        # the detector is only the fallback. Rebuilt per request — the page is
        # opened by hand, and the index must not go stale behind a cache.
        try:
            settled = learning.settled_language(cache.search_index)
        except Exception:
            settled = None      # index not ready: fall back, never fail the page
        resp = HTMLResponse(_lp(learning.snapshot(), curatable=curatable,
                                settled=settled))
        if request.query_params.get("key"):
            resp.set_cookie("ptpge_learning", supplied, httponly=True,
                            samesite="strict", secure=True, max_age=60 * 60 * 12)
        return resp

    async def learning_curate(request: Request) -> Response:
        """Mark a phrase out of scope, or put it back.

        Key-gated: the open mirror is public, and nobody but us should be able
        to edit what the vocabulary has learned. The key lives in
        PTPGE_LEARNING_KEY; without it set, curation is simply unavailable.
        """
        key = os.environ.get("PTPGE_LEARNING_KEY")
        if not key:
            return JSONResponse({"error": "curation_disabled"}, status_code=404)
        if not secrets.compare_digest(request.headers.get("x-learning-key", ""), key):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "bad_request"}, status_code=400)
        phrase = (body.get("phrase") or "").strip()
        if not phrase:
            return JSONResponse({"error": "no_phrase"}, status_code=400)
        if body.get("undo"):
            ok = learning.unignore(phrase)
        else:
            ok = learning.ignore(phrase, body.get("reason") or "out of scope")
        return JSONResponse({"ok": ok, "phrase": phrase})

    async def learning_gloss(request: Request) -> Response:
        """Say what a recorded phrase means, in print-trade terms.

        A row you cannot read is a row you cannot curate: 不干胶 is a
        self-adhesive label, but a general translator will offer «not-dry
        glue», which is exactly the kind of confident wrong answer this
        vocabulary exists to prevent. So the question asked is a trade
        question, and the answer is written into the row and kept — a reading
        does not change, and nobody should pay for it twice.

        Key-gated like curation, and never automatic: one call per word you
        actually wondered about.
        """
        key = os.environ.get("PTPGE_LEARNING_KEY")
        if not key or not secrets.compare_digest(
                request.headers.get("x-learning-key", ""), key):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return JSONResponse({"error": "no_model",
                                 "detail": "ANTHROPIC_API_KEY is not set on this server."},
                                status_code=503)
        try:
            phrase = ((await request.json()).get("phrase") or "").strip()
        except Exception:
            phrase = ""
        if not phrase:
            return JSONResponse({"error": "no_phrase"}, status_code=400)

        prompt = (
            "You are helping curate a printing-industry vocabulary. A buyer or "
            "an AI agent searched for the phrase below and the vocabulary "
            "returned nothing useful.\n\n"
            f"Phrase: {phrase}\n\n"
            "Reply with ONE line of at most 14 words, in this shape:\n"
            "  <ISO 639-1 code> — <what it means as a printed product, "
            "material or process, in English>\n"
            "Use the trade sense, not the literal one. If you are not "
            "confident what it means in printing, say so plainly instead of "
            "guessing. No preamble, no quotes."
        )
        payload = {"model": os.getenv("PTPGE_VISION_MODEL", "claude-haiku-4-5"),
                   "max_tokens": 80,
                   "messages": [{"role": "user", "content": prompt}]}
        try:
            with httpx.Client(timeout=30.0) as client:
                r = client.post("https://api.anthropic.com/v1/messages",
                                headers={"x-api-key": api_key,
                                         "anthropic-version": "2023-06-01",
                                         "content-type": "application/json"},
                                json=payload)
            if r.status_code != 200:
                return JSONResponse({"error": "upstream", "status": r.status_code},
                                    status_code=502)
            text = "".join(b.get("text", "") for b in r.json().get("content", [])
                           if b.get("type") == "text").strip()
        except Exception as exc:
            return JSONResponse({"error": "upstream_exception", "detail": str(exc)[:200]},
                                status_code=502)
        if not text:
            return JSONResponse({"error": "empty"}, status_code=502)

        # "ja — flyers, a single-sheet advertising leaflet" → the code is a
        # reading of the characters by something that knows the trade, which
        # is a better source than a regex hunting for umlauts.
        lang = None
        head, sep, rest = text.partition("—")
        code = head.strip().lower()
        if sep and 2 <= len(code) <= 5 and code.replace("-", "").isalpha():
            lang, text = code, rest.strip() or text
        learning.gloss(phrase, text, lang)
        return JSONResponse({"ok": True, "phrase": phrase, "gloss": text, "lang": lang})

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
                "service": "PTPGE MCP — the open specification of print",
                "description": "Model Context Protocol server for PTPGE, the open specification of print: vocabulary, identity, formats. CC BY 4.0.",
                "server_version": __version__,
                "data_version": v,
                "endpoints": {
                    "mcp": "/mcp",
                    "playground": "/playground",
                    "check": "/check",
                    "agent": "/agent/status",
                    "check_json": "/check.json?domain=<domain>",
                    "validate": "POST /validate {product, bindings[]} — same as ptpge_validate_config",
                    "fingerprint": "POST /fingerprint {product, bindings[]} — same as ptpge_fingerprint",
                    "sse": "/sse" if config.sse_enabled else None,
                    "messages": "/mcp/messages/" if config.sse_enabled else None,
                    "health": "/healthz",
                },
                "transport": {
                    "recommended": "streamable-http (/mcp, stateless JSON)",
                    "legacy": "sse (/sse)" if config.sse_enabled else "sse disabled on this endpoint",
                },
                "documentation": "https://ptpge.org/developers/",
                "icon": "/icon-512.png",
                "status": "public-beta",
            }
        )

    _ASSET_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _asset(name: str, media_type: str):
        """Serve a static brand asset (favicon / icon) from the repo root."""
        path = os.path.join(_ASSET_DIR, name)

        async def endpoint(_request: Request) -> Response:
            if not os.path.isfile(path):
                return Response(status_code=404)
            return FileResponse(path, media_type=media_type,
                                headers={"Cache-Control": "public, max-age=86400"})
        return endpoint

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

    vision = make_vision_endpoint()

    middleware = [
        Middleware(NoIndexHeaderMiddleware),  # outermost: header on 401s too
        Middleware(
            BasicAuthMiddleware,
            credentials=config.credentials,
            htpasswd_file=config.htpasswd_file,
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
    elif not config.htpasswd_file:
        logger.warning("Basic Auth NOT configured - server is open. Set PTPGE_MCP_AUTH_USERS or PTPGE_MCP_AUTH_USER/_PASS to enable.")
    if config.htpasswd_file:
        logger.info("Basic Auth shared htpasswd ENABLED: %s (register-provisioned per-user credentials)",
                    config.htpasswd_file)

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
            Route("/agent/status", endpoint=_agent.agent_status, methods=["GET", "OPTIONS"]),
            Route("/agent/messages", endpoint=_agent.agent_messages, methods=["POST", "OPTIONS"]),
            Route("/check", endpoint=check_page, methods=["GET"]),
            Route("/check.json", endpoint=check_json, methods=["GET"]),
            Route("/artwork", endpoint=artwork_read, methods=["POST", "OPTIONS"]),
            Route("/validate", endpoint=validate_json, methods=["POST", "OPTIONS"]),
            Route("/fingerprint", endpoint=fingerprint_json, methods=["POST", "OPTIONS"]),
            Route("/playground/pdf", endpoint=lambda r: HTMLResponse(__import__("ptpge_mcp.artworkpage", fromlist=["PAGE"]).PAGE), methods=["GET"]),
            Route("/favicon.ico", endpoint=_asset("favicon.ico", "image/x-icon"), methods=["GET"]),
            Route("/icon-512.png", endpoint=_asset("icon-512.png", "image/png"), methods=["GET"]),
            Route("/miss-report", endpoint=miss_report, methods=["GET"]),
            Route("/learning", endpoint=learning_page, methods=["GET"]),
            Route("/learning/curate", endpoint=learning_curate, methods=["POST"]),
            Route("/learning/gloss", endpoint=learning_gloss, methods=["POST"]),
            Route("/chat", endpoint=chat, methods=["POST", "OPTIONS"]),
            Route("/vision", endpoint=vision, methods=["POST", "OPTIONS"]),
            Route("/health", endpoint=health, methods=["GET"]),
            Route("/healthz", endpoint=health, methods=["GET"]),  # standard alias (matches the commercial side)
            # Streamable HTTP (recommended). GET/DELETE answered with 405
            # inside the handler — stateless servers open no streams.
            Route("/mcp", endpoint=handle_mcp_http, methods=["POST", "GET", "DELETE", "OPTIONS"]),
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
