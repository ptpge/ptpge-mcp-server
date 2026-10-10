# PTPGE MCP Server

A read-only [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the
[PTPGE specification](https://ptpge.org) — the open vocabulary of print — to AI agents.

The vocabulary (terms with permanent URIs, product templates, variables, schemas and registers) is
published under CC BY 4.0 at `https://api.ptpge.org/v1/`. This server loads it, keeps it in memory,
reloads when the dataset version changes, and offers it to agents as a small set of MCP tools:
search a term, read a term, read a product envelope, validate a configuration, resolve a colour
notation, compute and expand a configuration fingerprint (`ptpge-cfs/1`).

Live, open, no key: `https://mcp.ptpge.org/mcp` (Streamable HTTP). `open.mcp.ptpge.org` is an alias.

## Add it to your assistant

- **Claude** (web or desktop): Settings → Connectors → Add custom connector → `https://mcp.ptpge.org/mcp`
- **ChatGPT**: Settings → Connectors → Add (developer mode) → same URL
- **Claude Code**: `claude mcp add ptpge --transport http https://mcp.ptpge.org/mcp`

Then ask, in any language: «What is a roll fold?» or «Fingerprint an A4 tri-fold brochure, 170 g silk, 4/4».

## Tools

| Tool | What it does |
|---|---|
| `ptpge_search_terms` | Free-text search over the vocabulary, tokenised and language-independent. Hits carry URI, label, level, group, `kind` (term · supplier · vendor · schema) and score. Deprecated terms are skipped unless asked for. |
| `ptpge_get_term` | One term in full: definition, relations (`broader` / `narrower` / `related`), mappings, properties, notation. Accepts a full URI or a relative path. |
| `ptpge_get_version` | Dataset version, term counts, licence, scheme URL, server version. |
| `ptpge_browse` | Walk the hierarchy from a node. |
| `ptpge_get_product_envelope` | For a product template: which variables apply, which are required for an identity, which values are allowed. |
| `ptpge_validate_config` | Check a configuration (bindings on vocabulary URIs) against its envelope: membership, cardinality, scope, numeric bands, cross-variable rules. |
| `ptpge_resolve_color_notation` | `4/4`, `4/1`, `1/0` … → ink counts per face in vocabulary terms. |
| `ptpge_fingerprint` | Canonicalise a validated configuration and compute its `ptpge-cfs/1` fingerprint (spec and offer). |
| `ptpge_expand_fingerprint` | A fingerprint back to its configuration, from the register at `ptpge.org/f/`. |

Responses are plain JSON. The `/playground` page lets you watch an agent run the loop from a free-text
order to a fingerprint, every tool call in the transcript.

## Endpoints

| Path | Purpose |
|---|---|
| `POST /mcp` | MCP over Streamable HTTP (also GET for the event stream, DELETE to end a session) |
| `GET /health`, `/healthz` | Liveness + dataset version |
| `GET /playground` | The Playground |
| `GET /sse` | Retired — answers 410 with a pointer to `/mcp` |

## Run it yourself

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m ptpge_mcp.server          # http://0.0.0.0:8000/mcp
```

Test with the MCP Inspector: `npx @modelcontextprotocol/inspector`, transport Streamable HTTP, URL
`http://localhost:8000/mcp`.

```bash
pytest -q
```

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PTPGE_API_BASE` | `https://api.ptpge.org/v1` | Where the vocabulary is fetched from |
| `PTPGE_REFRESH_SECONDS` | `900` | How often to check `version.json` for a new dataset |
| `PTPGE_LOG_LEVEL` | `INFO` | Python logging level |
| `PTPGE_MCP_AUTH_USERS` | — | Optional Basic Auth on the server, comma-separated `user:pass` pairs. Leave unset for an open server. |
| `PTPGE_MCP_HTPASSWD` | — | Optional path to an Apache htpasswd file used instead of the variable above |
| `PTPGE_MCP_TOKENS` / `_TOKENS_FILE` | — | Optional per-recipient tokens (`?t=`), same purpose |

The public server at `mcp.ptpge.org` runs with none of the auth variables set.

## Layout

```
ptpge_mcp/
├── server.py           # tools, handlers, Streamable HTTP, Playground route
├── data.py             # fetch, cache, index, search
├── config.py           # environment-based runtime config
├── cfs_resolution.py   # canonicalisation + ptpge-cfs/1
├── fingerprint.py, fingermark.py   # hash and mark
├── completeness.py     # required variables / unspecified axes
├── colornotation.py    # 4/4-style notation → terms
├── semantic.py         # embedding search (term_embeddings.npz)
├── registerclient.py   # ptpge.org/f/ register client
├── playground.py, learningpage.py, missreport.py
└── _frame.py           # ptpge.org site frame (generated; do not edit)
tests/
passenger_wsgi.py       # cPanel/Passenger entry point for the hosted instance
.cpanel.yml             # deploy script for the hosted instance
CHANGELOG.md            # semver; one entry per release
```

## Versioning

Semver for the server; the dataset has its own date version (`ptpge_get_version`). The fingerprint
algorithm is a separate contract, `ptpge-cfs/1`, and does not change with server releases.

## Licence

Code: [Apache License 2.0](LICENSE). Vocabulary and data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
held by PTPGE, a non-profit association (being formed). See [ptpge.org/governance](https://ptpge.org/governance/).

## Registry

Listed in the official MCP Registry as `org.ptpge/mcp-server` (`server.json` in this repository; published with
`mcp-publisher`, namespace verified by a DNS record on ptpge.org).
