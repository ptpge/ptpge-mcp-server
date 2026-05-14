"""PTPGE MCP server — exposes the PTPGE taxonomy via the Model Context Protocol.

v0.2.0 — implements the full v1 tool surface per SD-0010 and
MCP-tool-surface-v1.md:

    - ptpge_search_terms — free-text search over the taxonomy
    - ptpge_get_term     — full context for a single term
    - ptpge_get_version  — current dataset version and statistics

Run locally:
    python -m ptpge_mcp.server

Deploy on cPanel Passenger:
    The Passenger entry point at the project root (`passenger_wsgi.py`) imports
    the ASGI app from this module and bridges it via a2wsgi.
"""

import json
import logging

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from . import __version__
from .config import Config
from .data import TaxonomyCache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool descriptors — kept module-level so they can be unit-tested without
# spinning up the full Starlette app.
# ---------------------------------------------------------------------------

TOOL_DESCRIPTORS: list[Tool] = [
    Tool(
        name="ptpge_search_terms",
        description=(
            "Free-text search over the PTPGE taxonomy. Returns a ranked list "
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
                        "E.g. 'manufacturing/configurations/formats/a-series/a4'."
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

    cache = TaxonomyCache(config)
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

    return Starlette(
        debug=False,
        routes=[
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
