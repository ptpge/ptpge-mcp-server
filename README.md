# PTPGE MCP Server

A standalone Model Context Protocol (MCP) server that exposes the PTPGE Standard (Layer 1 — the open vocabulary for the printing industry) to AI agents.

This is the implementation referenced in `PTPGE-API-architecture.md` (Fase 2) and `STRATEGIC-DECISIONS.md` SD-0003 / SD-0007.

## What this is

A read-only HTTP/SSE MCP server written in Python that:

1. Fetches `terms.jsonld` and `search-index.json` from `https://api.ptpge.org/v1/` at startup.
2. Holds the data in memory (~50 MB for 464 terms — trivial).
3. Periodically reloads when `version.json` indicates a new dataset version.
4. Exposes a small set of MCP tools so AI agents can search, fetch, and classify against the PTPGE Standard vocabulary.

## Architecture

- **Stack:** Python 3.11+, `mcp` Python SDK over HTTP/SSE
- **Hosting:** A2 Hosting Managed cPanel 4GB VPS in Frankfurt at `mcp.ptpge.org` (operated by Tangerin AS as Tier 4 in the Infrastructure Services Catalog; shares the dedicated VPS with `api.ptpge.org`, `internal.ptpge.org`, `dashboard.ptpge.org`, and `editor.ptpge.org` since SD-0021 consolidation 2026-05-21)
- **Deploy:** Passenger via cPanel "Setup Python App" → entry point `passenger_wsgi.py`
- **Stealth Mode:** HTTP Basic Auth at the cPanel level until public launch

See `../PTPGE-API-architecture.md` for the full architectural context.

## Tools exposed (v1, per SD-0010)

The v1 tool surface was finalised on 2026-05-14 in [SD-0010](../STRATEGIC-DECISIONS.md#sd-0010--mcp-verktøyflate-v1-tre-verktøy-smal-og-fokusert). Three tools, smal and focused — the full spec is in [MCP-tool-surface-v1.md](../MCP-tool-surface-v1.md).

| Tool | Purpose |
|---|---|
| `ptpge_search_terms` | Free-text search over the vocabulary (uses `search-index.json`). Returns ranked hits with URI, notation, prefLabel, level, group, and score. |
| `ptpge_get_term` | Full context for one term: definition, relations (`broader` / `narrower` / `related`), mappings (`exactMatch` / `closeMatch`), `properties`, notation, level. Accepts full URI or relative path. |
| `ptpge_get_version` | Current dataset version, term counts per level and per group, license, scheme URL, server version. For version-pinning and diagnostics. |

**Deferred (v1.x or later):**

- `ptpge_classify_text` — requires ranking policy and likely embeddings; deferred until empirics from real `search_terms` usage are available.
- `ptpge_list_groups` — rejected as redundant; covered by `get_term` on the `printing` top-concept (returns `narrower` list).
- `ptpge_get_relations` — rejected as redundant; relations are already part of the `get_term` response.

Tool responses are plain JSON (not JSON-LD). Consumers don't need to handle `@context`.

## Project layout

```
mcp-server/
├── README.md                          # this file
├── pyproject.toml                     # Python project metadata + deps
├── requirements.txt                   # pinned deps for cPanel Passenger
├── passenger_wsgi.py                  # cPanel/Passenger entry point (a2wsgi-bridge)
├── .cpanel.yml                        # Git deploy configuration
├── .gitignore
├── ptpge_mcp/
│   ├── __init__.py
│   ├── server.py                      # MCP server — tools, handlers, HTTP/SSE
│   ├── data.py                        # fetch + cache + index + search
│   └── config.py                      # env-based runtime config
└── tests/
    ├── test_data.py                   # cache load + reload tests
    └── test_search_and_get_term.py    # search and lookup tests
```

## Local development

### First-time setup

```bash
cd mcp-server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running the server — two modes

**Mode A: Local Inspector / vocabulary-testing (most common)**

For verifying that the server loads vocabulary correctly, that MCP tools are exposed, and that search/lookup operations work via MCP Inspector. Skip MCP Basic Auth — it adds complexity that Inspector handles poorly with SSE transport.

In tab 1:

```bash
export PTPGE_API_BASE="https://internal.ptpge.org/v1"
python -m ptpge_mcp.server
```

Expected output:

```
INFO ptpge_mcp.data: Loading vocabulary data from https://internal.ptpge.org/v1
INFO httpx: HTTP Request: GET https://internal.ptpge.org/v1/version.json "HTTP/1.1 200 OK"
INFO httpx: HTTP Request: GET https://internal.ptpge.org/v1/terms.jsonld "HTTP/1.1 200 OK"
WARNING: Basic Auth NOT configured - server is open. (expected for local mode)
INFO: Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

In tab 2 (open with Cmd+T), launch Inspector:

```bash
npx @modelcontextprotocol/inspector
```

In the Inspector UI: keep URL as `http://localhost:8000/sse`, Transport=SSE, Connection Type=Via Proxy. Click **Connect** directly — do not click "Open Auth Settings" (that triggers OAuth, which this server does not support).

**Mode B: Auth-layer testing (rare — usually done with curl, not Inspector)**

For verifying that Basic Auth on the MCP server itself works. Inspector v0.21.2 has poor support for Basic Auth in SSE URLs, so use curl for this mode.

In tab 1:

```bash
export PTPGE_API_BASE="https://internal.ptpge.org/v1"
export PTPGE_MCP_AUTH_USER="frankenstein-mcp"
export PTPGE_MCP_AUTH_PASS="<actual password>"
python -m ptpge_mcp.server
```

In tab 2, test:

```bash
# Without auth: should return 401
curl -i http://localhost:8000/health

# With correct auth: should return 200 + JSON
curl -i -u "frankenstein-mcp:<actual password>" http://localhost:8000/health
```

### Critical: `PTPGE_API_BASE` must point to `internal.ptpge.org`

The default fallback in `config.py` points to `api.ptpge.org/v1`, but that domain is behind HTTP Basic Auth during Stealth Mode. If `PTPGE_API_BASE` is not explicitly set to `internal.ptpge.org/v1` (the unauthed mirror introduced in SD-0021), the server will crash at startup with a `401 Unauthorized` from `version.json`. **Always export `PTPGE_API_BASE` before starting the server.**

### Credential rotation notes

- **2026-05-24 (SD-0022):** Stealth Mode MCP user renamed from `frankenstein-stealth` → `frankenstein-mcp` and the password was rotated. Use the new name in all local examples.
- **2026-05-24 (SD-0022):** Per-recipient credentials introduced. Use `PTPGE_MCP_AUTH_USERS` (comma-separated `user:pass` pairs) or `PTPGE_MCP_<NAME>_AUTH_USER` / `_PASS` for multi-recipient setups. The legacy single-user `PTPGE_MCP_AUTH_USER` / `_PASS` still works (used in Mode B above).

## Deployment to A2 Managed VPS

Once the VPS is provisioned and `mcp.ptpge.org` is set up via cPanel "Setup Python App":

1. Push this repository to GitHub (private during Stealth Mode).
2. In cPanel → Git Version Control → Clone the repo into the app directory.
3. Edit `.cpanel.yml` if needed for the specific app paths.
4. Trigger first deploy: `git push` → cPanel `git pull` → `passenger_wsgi.py` is auto-detected.
5. Restart the Python app from cPanel.
6. Verify with:
   ```bash
   curl -u user:pass https://mcp.ptpge.org/health
   ```

## Configuration

Environment variables (set in cPanel Python App → Environment Variables):

| Variable | Default | Purpose |
|---|---|---|
| `PTPGE_API_BASE` | `https://api.ptpge.org/v1` | Where to fetch vocabulary data. **In practice always set to `https://internal.ptpge.org/v1`** to avoid auth-loop against api.ptpge.org which is behind Stealth Mode Basic Auth (per SD-0021). The default is a legacy value; consider it required to override. |
| `PTPGE_API_USER` | — | Basic Auth username for Stealth Mode API. Only needed if `PTPGE_API_BASE` points to an authed endpoint (rare — not the production setup). |
| `PTPGE_API_PASS` | — | Basic Auth password for Stealth Mode API. Same — rarely used in practice. |
| `PTPGE_MCP_AUTH_USERS` | — | Comma-separated `user:pass` pairs for multi-recipient Basic Auth on the MCP server itself. e.g. `frankenstein-mcp:p1,zipper:p2`. |
| `PTPGE_MCP_<NAME>_AUTH_USER` / `_PASS` | — | Per-recipient pair (cPanel-friendly). One pair per recipient; merges with legacy single-user variables. |
| `PTPGE_MCP_AUTH_USER` / `_PASS` | — | Legacy single-user Basic Auth on the MCP server. Still supported. Set both to enable Basic Auth. |
| `PTPGE_REFRESH_SECONDS` | `900` | How often to check for new dataset version (15 min default) |
| `PTPGE_LOG_LEVEL` | `INFO` | Standard Python logging level |

## License

Same license as the PTPGE Standard itself: CC BY 4.0 (data) + the server code under a permissive license to be confirmed at public launch.

Until public launch: all rights reserved by Tangerin AS / PTPGE AS (when incorporated).
