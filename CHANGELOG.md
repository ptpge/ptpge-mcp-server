# MCP Server — Changelog

The PTPGE MCP server exposes the open Layer 1 Standard to AI agents over the
Model Context Protocol. Endpoints: `mcp.ptpge.org` (and the open, unauthenticated
`open.mcp.ptpge.org`).

Versioning: **semver** (software). Dates reflect the project work log.
See SD-0044 for the versioning & changelog policy.

## 0.8.1 — 2026-08-21

- SD-0067: `ptpge_validate_config` reads the adopted symmetric
  `customSizeRange {min, max, unit}` (all 49 Customized templates now carry
  industry-vetted ranges); the older `minWidth/maxWidth` form remains as
  fallback. Format lists in the dataset are now build-derived from
  `supportsFormatFamilies` within each template's range.

## 0.8.0 — 2026-08-21

- SD-0066 custom dimensions: `ptpge_validate_config` understands the new
  `variables/configuration/custom-width` / `custom-height` variables (mm) —
  per-binding range checks (template `customSizeRange` when present, global
  5–50000 mm otherwise) and cross-variable rules in a new `rules` array:
  `custom_size_required` (Customized without both dimensions),
  `custom_size_without_customized`, and `not_normalized` (width > height;
  the note tells the agent the exact normalized binding + orientation).

## 0.7.1 — 2026-08-21

- Agent self-correction: `ptpge_validate_config` now includes the `allowed`
  list (the product's envelope values, with labels) directly in every
  `not_in_envelope` binding — both enum variables and numeric
  substrate-weight. Agents no longer need a second envelope call to
  recover from a rejected value. Found in the first agent smoke test
  against the live server.

## 0.7.0 (surface updates) — 2026-08-16 (ii)

- Dutch (nl) joins as the vocabulary's ninth language — 139 pre-existing
  Dutch labels from the VIGC field-mapping collaboration preserved, the
  rest completed. Embeddings rebuilt with Dutch labels and altLabels;
  tokenized search matches Dutch buyer phrases («zigzagvouw»,
  «visitekaartjes», «garenloos binden») with no server code change.
  Playground: **Nederlands** added to the convergence demo (all three
  products), and «eight languages» → «nine languages» corrected across
  all 13 UI locales.

## 0.7.0 (surface updates) — 2026-08-16

- Danish (da) joins as the vocabulary's eighth language. Embeddings rebuilt
  with Danish labels and altLabels (507 vectors); tokenized search matches
  Danish buyer phrases («klammerhæftning», «leporellofals», «løbesedler»)
  with no server code change. Playground: **Dansk** added to the convergence
  demo (all three products), and «seven languages» → «eight languages»
  corrected across all 13 UI locales.

## 0.7.0 (surface updates) — 2026-08-15

- Swedish (sv) joins as the vocabulary's seventh language. Semantic-search
  embeddings rebuilt with Swedish labels and altLabels in the text base
  (507 vectors — the server's tokenized search needs no code change: it
  already matches across ALL label/altLabel language variants, so Swedish
  buyer phrases like «klammerhäftning» and «dragspelsfals» resolve as soon
  as the API data carries them). Playground: **Svenska** added to the
  convergence demo with pre-scripted Swedish phrasings for all three
  products (brochure / business cards / booklet), and «six languages» →
  «seven languages» corrected across all 13 UI locales.

## 0.7.0 (surface updates) — 2026-08-11

- Playground v3/v3.1 (deployed 2026-08-11, within server 0.7.0): every tool
  card is a `<details>` accordion with a plain-language explainer in the
  header; responses render inline in the card you clicked; the bottom
  console is now a collapsed **session transcript** with a live call
  counter — entries numbered with timestamps. 9 new i18n keys × 12
  languages. No server/tool changes (commits 320337f, 15a28c3).

## 0.7.0 (surface updates) — 2026-08-04

- Playground v2 — the convergence demo: three real products (brochure /
  business cards / booklet), each phrased in six languages, stepping
  through raw phrase → live labels → canonical cfs/1 → SHA-256 → same
  identity, with run history. 13-language UI switcher; editable canonical
  form recomputing SHA-256 live in the browser (commits d889580 … 322fdf6).
- Fingerprint visuals degrade gracefully without a vendor hash: spec mark +
  QR still delivered, offer mark omitted with a note — the mark/3 rule
  stands (4018730).

## 0.7.0 — 2026-07-15

- `ptpge-mark/3` per SD-0060: 2×2 species grammar, vendor minutiae,
  equal-dot scan frame, origin dot 2.94, unscaled rings — version bump to
  0.7.0 (966d859).
- Basic Auth path 4 (2026-08-03, 35b638c): shared htpasswd via
  `PTPGE_MCP_HTPASSWD` — register-provisioned beta credentials now work on
  the gated MCP («one login, three doors»).

## 0.6.3 — 2026-07-14

- Fingermark scanFrame option (register dots, BL anchor — spec amendment
  2.1); cross stroke 1.47u (0b3c26c).

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
