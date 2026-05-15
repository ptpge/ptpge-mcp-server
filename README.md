# PTPGE MCP Server

A standalone Model Context Protocol (MCP) server that exposes the PTPGE vocabulary to AI agents.

This is the implementation referenced in `PTPGE-API-arkitektur.md` (Fase 2) and `STRATEGIC-DECISIONS.md` SD-0003 / SD-0007.

## What this is

A read-only HTTP/SSE MCP server written in Python that:

1. Fetches `terms.jsonld` and `search-index.json` from `https://api.ptpge.org/v1/` at startup.
2. Holds the data in memory (~50 MB for 464 terms — trivial).
3. Periodically reloads when `version.json` indicates a new dataset version.
4. Exposes a small set of MCP tools so AI agents can search, fetch, and classify against the PTPGE taxonomy.

## Architecture

- **Stack:** Python 3.11+, `mcp` Python SDK over HTTP/SSE
- **Hosting:** A2 Hosting Managed cPanel 4GB VPS at `mcp.ptpge.org` (operated by Tangerin AS as Tier 4 in the Infrastructure Services Catalog)
- **Deploy:** Passenger via cPanel "Setup Python App" → entry point `passenger_wsgi.py`
- **Stealth Mode:** HTTP Basic Auth at the cPanel level until public launch

See `../PTPGE-API-arkitektur.md` for the full architectural context.

## Tools exposed (v1, per SD-0010)

The v1 tool surface was finalised on 2026-05-14 in [SD-0010](../STRATEGIC-DECISIONS.md#sd-0010--mcp-verktøyflate-v1-tre-verktøy-smal-og-fokusert). Three tools, smal and focused — the full spec is in [MCP-tool-surface-v1.md](../MCP-tool-surface-v1.md).

| Tool | Purpose |
|---|---|
| `ptpge_search_terms` | Free-text search over the taxonomy (uses `search-index.json`). Returns ranked hits with URI, notation, prefLabel, level, group, and score. |
| `ptpge_get_term` | Full context for one term: definition, relations (`broader` / `narrower` / `related`), mappings (`exactMatch` / `closeMatch`), `properties`, notation, level. Accepts full URI or relative path. |
| `ptpge_get_version` | Current dataset version, term counts per level and per group, license, scheme URL, server version. For version-pinning and diagnostics. |

**Deferred (v1.x or later):**

- `ptpge_classify_text` — requires ranking policy and likely embeddings; deferred until empirics from real `search_terms` usage are available.
- `ptpge_list_groups` — rejected as redundant; covered by `get_term` on the manufacturing top-concept (returns `narrower` list).
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

```bash
cd mcp-server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m ptpge_mcp.server
```

The server listens on `http://localhost:8000` by default. Use the MCP Inspector (or any MCP-capable client) to test:

```bash
npx @modelcontextprotocol/inspector http://localhost:8000
```

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
| `PTPGE_API_BASE` | `https://api.ptpge.org/v1` | Where to fetch taxonomy data |
| `PTPGE_API_USER` | — | Basic Auth username for Stealth Mode API |
| `PTPGE_API_PASS` | — | Basic Auth password for Stealth Mode API |
| `PTPGE_REFRESH_SECONDS` | `900` | How often to check for new dataset version (15 min default) |
| `PTPGE_LOG_LEVEL` | `INFO` | Standard Python logging level |

## License

Same license as the PTPGE Standard itself: CC BY 4.0 (data) + the server code under a permissive license to be confirmed at public launch.

Until public launch: all rights reserved by Tangerin AS / PTPGE AS (when incorporated).
