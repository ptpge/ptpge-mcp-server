"""PTPGE MCP server — exposes the PTPGE Standard (Layer 1 vocabulary) via the Model Context Protocol.

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

    Activated when both PTPGE_MCP_AUTH_USER and PTPGE_MCP_AUTH_PASS are set.
    Passes through transparently if either is unset, so local development and
    post-launch open access remain frictionless.

    Uses `secrets.compare_digest` for constant-time comparison to avoid
    leaking auth timing.
    """

    # HTTP header values must be latin-1 encodable. We pin this to a strict
    # ASCII subset and verify at construction time so any drift back to
    # smart-punctuation gets caught at import, not at the first 401.
    _REALM = "PTPGE MCP Stealth Mode"

    def __init__(self, app, username: str = "", password: str = "") -> None:
        super().__init__(app)
        self._enabled = bool(username and password)
        if self._enabled:
            token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
            self._expected = f"Basic {token}"
        else:
            self._expected = ""
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
        if not secrets.compare_digest(provided, self._expected):
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
        args = arguments or {}

        if name == "ptpge_get_version":
            v = cache.version
            payload = {
                "dataVersion": v.get("version"),
                "schemaVersion": "v1",
                "generated": v.get("generated"),
                "termsTotal": v.get("terms"),
                "termsByLevel": v.get("by_level"),
                "termsByGroup": v.get("by_group"),
                "license": v.get("license"),
                "schemeUrl": v.get("scheme_url"),
                "serverVersion": __version__,
            }
            return _json_text(payload)

        if name == "ptpge_search_terms":
            query = args.get("query", "")
            limit = int(args.get("limit", 10))
            groups = args.get("groups")
            language = args.get("language", "en")
            hits = cache.search(
                query=query, limit=limit, groups=groups, language=language
            )
            return _json_text({"query": query, "count": len(hits), "results": hits})

        if name == "ptpge_get_term":
            id_or_path = args.get("id_or_path", "")
            language = args.get("language", "en")
            term = cache.get_term(id_or_path)
            if term is None:
                return _json_text(
                    {"error": "not_found", "id_or_path": id_or_path}
                )
            return _json_text(_term_for_response(term, language))

        raise ValueError(f"Unknown tool: {name}")

    sse = SseServerTransport("/mcp/messages/")

    async def handle_sse(request: Request) -> Response:
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await mcp_server.run(streams[0], streams[1], mcp_server.create_initialization_options())
        return Response()

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
                    "sse": "/sse",
                    "messages": "/mcp/messages/",
                    "health": "/health",
                },
                "documentation": "https://ptpge.org",
                "status": "stealth-mode",
            }
        )

    middleware = [
        Middleware(
            BasicAuthMiddleware,
            username=config.auth_user,
            password=config.auth_pass,
        ),
    ]

    if config.auth_user and config.auth_pass:
        logger.info("Basic Auth ENABLED for all routes (Stealth Mode)")
    else:
        logger.warning("Basic Auth NOT configured — server is open. Set PTPGE_MCP_AUTH_USER / _PASS to enable.")

    return Starlette(
        debug=False,
        middleware=middleware,
        routes=[
            Route("/", endpoint=root, methods=["GET"]),
            Route("/health", endpoint=health, methods=["GET"]),
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Mount("/mcp/messages/", app=sse.handle_post_message),
        ],
    )


# ASGI app — imported by passenger_wsgi.py and by uvicorn for local dev
app = build_app()


def main() -> None:
    """Local development entry point. In production, Passenger drives this."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
