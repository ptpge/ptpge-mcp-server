"""PTPGE MCP server — exposes the PTPGE Standard (Layer 1 vocabulary) via the Model Context Protocol.

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
import secrets

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from . import __version__
from .config import Config
from .data import VocabularyCache

logger = logging.getLogger(__name__)


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
                "title": "PTPGE Standard",
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
                "service": "PTPGE MCP Server",
                "description": "Model Context Protocol server for the PTPGE Standard vocabulary.",
                "server_version": __version__,
                "data_version": v,
                "endpoints": {
                    "mcp": "/mcp",
                    "sse": "/sse" if config.sse_enabled else None,
                    "messages": "/mcp/messages/" if config.sse_enabled else None,
                    "health": "/health",
                },
                "transport": {
                    "recommended": "streamable-http (/mcp, stateless JSON)",
                    "legacy": "sse (/sse)" if config.sse_enabled else "sse disabled on this endpoint",
                },
                "documentation": "https://ptpge.org",
                "status": "stealth-mode",
            }
        )

    middleware = [
        Middleware(NoIndexHeaderMiddleware),  # outermost: header on 401s too
        Middleware(
            BasicAuthMiddleware,
            credentials=config.credentials,
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

    return Starlette(
        debug=False,
        middleware=middleware,
        routes=[
            Route("/", endpoint=root, methods=["GET"]),
            Route("/health", endpoint=health, methods=["GET"]),
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
