# MCP Server — Changelog

The PTPGE MCP server exposes the open Layer 1 Standard to AI agents over the
Model Context Protocol. Endpoints: `mcp.ptpge.org` (and the open, unauthenticated
`open.mcp.ptpge.org`).

Versioning: **semver** (software). Dates reflect the project work log.
See SD-0044 for the versioning & changelog policy.

## 0.5.1 — 2026-07-10

- Playground: the Fingerprint button now requests `visuals: true` and renders
  the mark + QR above the JSON (SVG fields collapsed in the JSON view).

## 0.5.0 — 2026-07-10

- **`ptpge_fingerprint` returns the full identity set.** Every profile now
  carries `resolverUrl` (the permanent `ptpge.org/f/{hash}` permalink,
  SD-0052). With the new `visuals: true` flag the tool also returns
  `markSvg` — the canonical `ptpge-mark/1` recognition mark (SD-0053) in
  brand green — and `qrSvg`, a scannable QR encoding the resolver permalink
  (white tile, quiet zone). Off by default to keep agent payloads small.
- New optional dependency `qrcode` (tool degrades gracefully without it).

## 0.4.0 — 2026-06-06

- **Streamable HTTP transport** at `/mcp` (stateless JSON), the current MCP
  transport. Legacy SSE remains available behind a toggle (`PTPGE_MCP_SSE=0`
  to disable).
- `X-Robots-Tag: noindex` on the open endpoint (`open.mcp.ptpge.org`).
- **Four new tools** (7 total): `ptpge_browse`, `ptpge_get_product_envelope`,
  `ptpge_validate_config`, `ptpge_fingerprint` (emits `ptpge-cfs/1`, SD-0040) —
  joining `ptpge_search_terms`, `ptpge_get_term`, `ptpge_get_version`.
- Tokenized search improvements.

## 0.3.3 — 2026-06-06

- `/playground` — an in-browser console for trying the tools (envelope →
  validate → fingerprint chained live).

## 0.2.2 — 2026-05-15

- Stability and tool-surface refinements.

## 0.2.x — 2026-05-14

- Initial MCP tool surface (`ptpge_search_terms`, `ptpge_get_term`,
  `ptpge_get_version`), per SD-0010.

---

*Tools are byte-compatible with the Layer 1 reference implementations; the
`ptpge_fingerprint` output matches the SD-0040 reference. Dataset content is
tracked separately in the API changelog (`api.ptpge.org/changelog.html`).*
