# MCP Server — Changelog

The PTPGE MCP server exposes the open Layer 1 Standard to AI agents over the
Model Context Protocol. Endpoints: `mcp.ptpge.org` (and the open, unauthenticated
`open.mcp.ptpge.org`).

Versioning: **semver** (software). Dates reflect the project work log.
See SD-0044 for the versioning & changelog policy.

## 0.17.0 — 2026-08-27

- **«what is this?» on any row you cannot read.** A row in a script you do not
  read is a row you cannot curate. One click asks the model already configured
  for /vision a *trade* question — 不干胶 is a self-adhesive label, where a
  general translator offers «not-dry glue», which is precisely the confident
  wrong answer this vocabulary exists to prevent. The reading is written into
  the row and kept: a meaning does not change, so nobody pays for it twice.
  Key-gated like curation, and never automatic — one call per word you actually
  wondered about.
- When the reading names the language, that becomes the row's language. A model
  that knows the trade reading the characters beats a regex hunting umlauts.

## 0.16.0 — 2026-08-27

Language on the learning page, from three sources instead of one guess.

- **`query_language` on `ptpge_search_terms`.** New optional argument, distinct
  from `language`: it says what tongue the QUERY is written in, where
  `language` says which labels to hand back. Conflating them would have filed a
  Norwegian agent asking «visittkort» with `language=en` as an English gap and
  hidden the Norwegian one. It never changes results — search has always looked
  across every language — and the recorder now reads it and nothing else.
- **The vocabulary answers first.** `learning.settled_language()` indexes every
  label and altLabel, so a phrase the standard already knows needs no detector.
  A row heals itself: file "Fahnen" as a German altLabel and the row that used
  to shrug starts saying `de`. Where a word belongs to two languages at once —
  "banner" is English and German both — it stays silent rather than pick one.
- **The corpus carries its market.** `lang=xx` per line, or `# lang: xx` over a
  block, in `tools/search_corpus.txt`; the harness sends it as `query_language`.
  We wrote those phrases, so we know what they are; that beats a detector
  staring at a lone word.
- The playground's own-prompt demo sends `query_language` too — the prompt was
  typed in the language selected on screen.
- The page never fails over this: if the index is not loaded, the column falls
  back to the detector rather than taking the page down with it.

## 0.15.3 — 2026-08-27

- **Language derived when the row is drawn, not when it was written.** The key
  *is* the phrase, so everything recorded before the column existed gets a
  language too — no backfill, and no rows left blank for the wrong reason.

## 0.15.2 — 2026-08-27

- **Fix: /learning returned 500 once a key was configured.** The endpoint took
  `_request` but its body read `request`, so the gate raised `NameError` on the
  only path that reaches it — the path that exists after someone sets the key.
  A test now walks all three doors (no key → 404, wrong key → 401, right key →
  the table), so the gate can never again be shipped untried.

## 0.15.1 — 2026-08-27

- **Language on every row.** Without it the table cannot answer the question it
  exists for — *which* language's synonyms are thin. Three levels, kept apart so
  a guess is never read as a fact: certain for non-Latin scripts (`ja`, `zh`),
  a guess from distinctive characters for Latin ones (`de?` from ä/ö/ü, `nb/da?`
  from ø/æ/å), and the caller's own `language` argument when they supplied one.
  Where nothing is known it says so rather than assuming English.

## 0.15.0 — 2026-08-27

- **`/learning` is behind a key.** A list of what the vocabulary cannot do is an
  internal instrument, not a demo, and the open mirror is unauthenticated by
  design — so the page carries its own lock: `?key=` once, then a session
  cookie. Without `PTPGE_LEARNING_KEY` set the page does not exist on that
  instance at all. Nothing about the vocabulary's weaknesses is served before
  the key is presented.
- **Out of scope, not missing.** Each row can be set aside with one click.
  Merchandise, apparel, 3D and POS sit outside the 54 product templates by
  decision, so their absence is not a gap and should not clutter the list — but
  the hits keep accumulating under `ignored`, so the size of that demand is
  already measured if the scope is ever revisited. Reversible.
- Curation is key-gated too (`POST /learning/curate`), so no passer-by can edit
  what the vocabulary has learned.

## 0.14.0 — 2026-08-27

- **The learning loop, live** (SD-0071 §9). Every lookup through `/mcp` is now
  judged, and the ones that went badly are counted: a phrase that found
  nothing, a phrase that only just matched, a colour count a template could
  not settle. It fills itself from whatever actually happens — our testing,
  the playground, somebody's agent — instead of waiting to be driven.
- New page **`/learning`** shows the accumulated picture, heaviest first: the
  words the trade uses and the vocabulary does not, the answers that would
  lose to the next competing term, and which products force `4/1` to ask.
- **What is not recorded is the point.** No user, no key, no IP, no session, no
  time of day — phrases, scores and counts only, so the open mirror's promise
  of anonymity per the partner onboarding still holds. Successful lookups are
  never stored; there is nothing to learn from them. Phrases that look like
  they carry personal data (an address, a long digit run, a whole prompt) are
  discarded rather than counted.
- Data lives in `tmp/learning.json`, which `.cpanel.yml` creates and rsync
  excludes, so what has been learned survives a deploy. Set
  `PTPGE_LEARNING_FILE=""` to switch the recorder off; an unwritable path
  disables it silently, because bookkeeping must never break a lookup.

## 0.13.0 — 2026-08-27

- New page **`/miss-report`** beside `/playground`: type or paste buyer phrases
  and see what the vocabulary cannot resolve, colour-coded as MISS (nothing
  found), WRONG (a different term won than the one pinned with `expect=`),
  WEAK (right term, but it will lose to the next competitor) or OK. Same origin
  as `/mcp`, so it calls the real search; the phrase list persists in the
  browser and grows into a personal corpus.
- Counterpart to `tools/search_miss_report.py`, which stays the regression
  guard: fixed corpus in the repo, exit code, run before a deploy. Between them
  the vocabulary's blind spots surface from our own testing rather than from a
  customer's failed order — the live counter of SD-0071 §9 without waiting for
  third-party traffic.

## 0.12.1 — 2026-08-27

- **Search: an exact synonym now outranks a partial one.** Two new tiers —
  0.90 when the query exactly equals an altLabel, 0.80 when an altLabel starts
  with it — sit between the existing exact-label (0.95) and label-prefix (0.85)
  tiers. Found by searching «パントン»: the system that IS called that and the
  library merely containing it in «パントン ソリッド» both scored 0.60, because
  exact and substring synonym hits were indistinguishable.
- **Ties are deterministic.** Equal scores now break on the term URI rather
  than on index order, so the same query cannot return a different first result
  between two calls. A standard whose pitch is «a lookup, never an
  interpretation» must not answer twice.

## 0.12.0 — 2026-08-27

- **ETag validation on cacheable results.** Read methods (`tools/list`,
  `tools/call`, the `*/list` family, `server/discover`) now return a strong
  `ETag` plus `Cache-Control`, and honour `If-None-Match` with `304 Not
  Modified`. Extends the `ttlMs`/`cacheScope` work of SEP-2549 toward the ETag
  validation named in the MCP roadmap's HTTP-Native Transport Unification area.
- The tag covers the dataset (`dataVersion` + `generated`), the server version,
  the method and the *result* — but deliberately not the JSON-RPC `id`, which
  identifies the call rather than the answer. A 304 therefore means "the result
  you cached is still current; reuse it under your current request id". Our
  tools are pure reads over an immutable dataset snapshot, so the same request
  against the same snapshot always yields the same result.
- Errors, notifications and non-read methods are never tagged.
- **Cache freshness fixed** in `data.py`: `maybe_reload()` now compares
  `(version, generated)` rather than `version` alone. `dataVersion` is a date,
  so two deploys on the same day carried the same string and a version-only
  check kept serving the older dataset until someone happened to restart the
  app — exactly the class of staleness that is invisible until you test it.

## 0.11.0 — 2026-08-27

- **`provenance` on bindings** (SD-0071 §7): `confirmed` | `inferred` |
  `policy-default` — how a value came about. Accepted by
  `ptpge_validate_config`, echoed back per binding, and summarised under
  `provenance.unconfirmed` so a vendor or marketplace can require confirmation
  before accepting an order, and a dispute can be settled on data.
- It is **never part of the fingerprint**. Two buyers who arrive at the same
  configuration hold the same product however they got there; if provenance
  touched the hash, physically identical print would carry two identities and
  comparison would break. Provenance references the identity the way price and
  vendor do, rather than constituting it.
- The exclusion already held by construction — canonicalization reads only
  variable/surface/value(s)/ordered — and is now stated in `fingerprint.py` and
  pinned by `tests/test_cfs_conformance.py::test_provenance_never_reaches_the_hash`,
  which proves it across all four implementations (tools, mcp-server, engine,
  configurator).
- New `tools/color_ambiguity_sweep.py`: runs the resolver over every template ×
  count and reports where ambiguity lives. The static counterpart to the live
  counter — it tells us something today instead of waiting for traffic.

## 0.10.0 — 2026-08-27

- New tool **`ptpge_resolve_color_notation`** (tool surface 7 → 8), implementing
  SD-0071. Print colour pair notation (`4/4`, `4/1`, `4+4`) resolves to
  per-surface bindings — the notation buyers actually write, and the one XJDF
  carries as `ColorIntent`/SurfaceColor.
- The count is treated as a **constraint, not a value**. Hand-written candidate
  lists collapse (7 = CMYKOGV, or CMYKOG+white, or CMYK+3 spots, or CMYK+2
  spots+white, …), so the resolver instead searches the combinations *this
  product's envelope supports* whose `colorChannelCount` sums to N. Three
  outcomes: a deterministic binding, `needs_disambiguation` with the candidates
  and a ready-made question, or `invalid_for_template`.
- Consequence worth stating: the same `4/1` is **deterministic** on a product
  whose back surface only supports black, and a **question** on one that also
  supports spot colour. Two declared conventions: `4` is CMYK, `0` is None.
  Black is never added to CMYK (K is already there); `+` between *different*
  numbers asks first, since parts of the trade read `4+1` as five inks on one
  surface.
- The tool description instructs agents never to infer an ambiguous count. We
  cannot force a third-party agent to ask, but the ambiguity is now a
  machine-readable fact rather than something it cannot see.
- New module `ptpge_mcp/colornotation.py`, deliberately free of MCP/HTTP
  concerns so the API and Engine can import it unchanged. 32 new tests (85 total).

## 0.9.0 — 2026-08-24

- MCP revision **2026-07-28** (SEP-2575/2549): the server is now dual-era.
  `server/discover` implemented (mandatory in the new revision) — advertises
  supported versions, capabilities and identity with `ttlMs`/`cacheScope`
  cache hints. All modern results carry `resultType: "complete"` and
  `io.modelcontextprotocol/serverInfo` in `_meta`; `tools/list` carries the
  new cache hints and remains deterministically ordered. Legacy
  `initialize`/`ping` still answered for older clients. We were stateless
  from day one, so the stateless-protocol change is purely additive.

## 0.8.3 (surface updates) — 2026-08-23

- Playground: fourth product in the convergence demo — **Panel print**
  (70 × 100 cm custom size, portrait, CMYK front, 5 mm foam board, 3 pcs)
  in all nine content languages; shows SD-0066 custom dimensions and
  SD-0070 thickness live. UI strings updated in 13 languages.

## 0.8.3 — 2026-08-22

- SD-0070: `validate_config` validates the new numeric
  `variables/substrate/substrate-thickness` axis (canonical mm) against the
  template's `supportsSubstrateThickness` `{min,max}` range — closed semantics
  when the predicate is absent; error notes carry the mil/pt/inch conversions.

## 0.8.2 — 2026-08-22

- SD-0069: `validate_config` maps the new `variables/substrate/substrate-coating`
  axis (coated/uncoated — buyer-optional refinement; unbound = unspecified).
- Bug fix: `substrate-color` was mapped to UK-spelled `supportsSubstrateColour`
  (against SD-0047), making shade validation silently dead — corrected to
  `supportsSubstrateColor`. Paper shade bindings now validate against each
  template's declared shades, with `allowed` lists on rejection.

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
