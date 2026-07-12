# MCP Server — Changelog

The PTPGE MCP server exposes the open Layer 1 Standard to AI agents over the
Model Context Protocol. Endpoints: `mcp.ptpge.org` (and the open, unauthenticated
`open.mcp.ptpge.org`).

Versioning: **semver** (software). Dates reflect the project work log.
See SD-0044 for the versioning & changelog policy.

## 0.6.2 — 2026-07-13
- Playground assembly: product fallback — when no phrase resolves directly to ordering/products/*, the best product hit anywhere in the lookups (score >= 0.45) is used and reported ("product inferred: …"). "Folded leaflet" prompts now fingerprint. No-product message now notes the altLabel/steward feedback path.

## 0.6.1 — 2026-07-13
- Playground: free-text prompts can now go all the way — "Fingerprint this" button performs a heuristic assembly (URI-path -> variable map + quantity/page-count/gsm number rules) and calls ptpge_fingerprint with visuals, so custom prompts end in mark + QR + resolver link (which 0.6.0 self-registers). Unmapped terms are listed honestly; a real agent assembles via the envelope.

## 0.6.0 — 2026-07-13
- Self-registering fingerprints (SD-0058): every fingerprint computed by ptpge_fingerprint is POSTed (best-effort, daemon thread, stdlib urllib, 4 s timeout, process-lifetime dedupe) to the resolver's register endpoint, which writes the permanent page only when sha256(canonical) == hash. The resolverUrl in the payload becomes live within seconds of first computation. Disable with PTPGE_RESOLVER_REGISTER_URL="".
- fingerprint payload gains a "registration" note.

## 0.5.4 — 2026-07-12
- ptpge-mark/2 (SD-0056): turbo anatomy — rings 3–5, symmetry 2–7, fixed centre-dot fiducial (r=1.4, unscaled), print scaled .85, cross terminates at outermost ring. Add-on species grammar: brand (dot+rings) · spec (+cross, no frame) · offer (+circle r39) · job (+crop-mark corners). Square frame retired; legacy square/round/corners map to spec/offer/job. Supersedes ptpge-mark/1.

## 0.5.3 — 2026-07-12
- ptpge-mark/1.2: breathing room — contour group scaled .88 about centre, clip radius 37 → 34. Identity (byte→form) unchanged; presentation-only, in line with Amendment 1.1 framing rules.
- ptpge-mark/1.2: frame parity — round frame r 38 → 39, the exact inscribed circle of the 78×78 square; identical footprint, identical ring size in both frames.
- ptpge-mark/1.4: open print — crosshair segments terminate at the outermost ring (deterministic per-hash endpoints); the print is never crossed.
- ptpge-mark/1.3: job frame — four crop-mark corner brackets on the shared 78×78 footprint; profile→frame map spec→square, offer→round, job→corners.

## 0.5.2 — 2026-07-10

- Profile framing (`ptpge-mark/1.1`): the mark's registration frame now encodes
  the profile — **square = spec**, **round = offer**. Presentation only; the
  frozen byte→form contour algorithm is unchanged.

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
