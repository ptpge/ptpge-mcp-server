# MCP Server — Changelog

The PTPGE MCP server exposes the PTPGE specification — the open vocabulary of print — to AI agents over the
Model Context Protocol. Endpoint: `mcp.ptpge.org`.

Versioning: **semver** (software). Dates reflect the project work log.
See SD-0044 for the versioning & changelog policy.

## 0.38.4 — 2026-10-13

- **/artwork: TrimBox on some pages only** is reported as such (trim where set, MediaBox elsewhere) instead of
  «no TrimBox» next to a bleed figure.

## 0.38.3 — 2026-10-13

- **/artwork: colour pages + black pages = CMYK, asked per part.** A file with some pages in CMYK and some in black
  only no longer binds two process layers (the validator rightly refused `cmyk + black`); it binds CMYK and asks
  «cover 4/4, inside 1/1?». The pages show rule violations in the «not valid» line.

## 0.38.2 — 2026-10-13

- **/playground/pdf: no guessing the product, faces follow the setup.** Without a product word the page asks instead
  of taking the first search hit; when the file's front/back are not faces of the chosen setup (a booklet), the
  colour bindings lose their face and apply to every face (SD-0083 D5), then validate again. Drop zone is a block.

## 0.38.0 — 2026-10-13

- **Artwork as a source (SD-0107) — hidden.** `POST /artwork` reads a print PDF (body = the file) and returns
  bindings with provenance `artwork`: format from the TrimBox (named format ±1 mm or customized + mm), bleed,
  page count, colour per face from the pages' colour spaces (CMYK / black / spot layers), named inks → `spot-ink`
  (Pantone/HKS/RAL), print standard from a PDF/X output intent, and the file's sha256 for request/1 — plus `toAsk`:
  fold, binding, paper, finish, quantity, which a PDF never states and are never guessed. Read in memory, never
  stored (`Cache-Control: no-store`). Hidden page `/playground/pdf` (noindex, unlinked). Not in tools/list yet;
  becomes `ptpge_read_artwork` when it has settled. Needs `pikepdf` on the server (requirements.txt).

## 0.37.3 — 2026-10-12

- **/check reads the declaration out loud (SD-0105).** `ptpge_check_domain` and `/check.json` now carry
  `agentSees.lines` and `agentSees.offerings` — the declaration's production lines and offerings in vocabulary
  labels. `/check?domain=…` renders the whole report server-side, with a card «What the declaration says»
  (provenance: read-at time, URL, document date; «the file is the source — nothing is stored»), so the text exists
  without scripts; the page is indexable only when the domain is agent-ready. The register page on ptpge.org
  points here and holds no reading of its own.

## 0.37.2 — 2026-10-12

- **Any unit in, mm out.** A custom-width / custom-height binding may carry `unit` (mm, cm, m, in, pt); the value
  is converted to mm before range check and identity, and the result echoes what was stated («12 cm») next to what
  was bound (120 mm). 12 × 18 cm and 120 × 180 mm are one identity — for every product with a custom size range,
  not only booklets. Rule mode reads «12x18 cm», «8.5 x 11 in», «3.5" x 2"»; the agent prompt says the same.

## 0.37.1 — 2026-10-12

- **Rule mode reads a size.** «85x55», «148 × 210 mm», «210x297» is matched against the product's named formats
  (either way round) — Business Card EU (85 x 55 mm) — and otherwise, where the product takes custom sizes, bound as
  format = customized + custom-width/height (normalized w ≤ h, SD-0066). The numbers are claimed before the quantity
  fallback can take one of them.

## 0.37.0 — 2026-10-12

- **Named spot inks (SD-0104).** New variable `variables/features/spot-ink`: the ink behind a spot-color layer, as
  `<matching-system term>/<code>` — Pantone 300 C → `…/color-matching-systems/pantone-matching-system/300-c`, HKS 43 K
  → `…/hks/43-k`, RAL 5015 → `…/ral/5015`. No list of codes: the code is checked for form, the libraries are the
  systems' own. `ptpge_validate_config`: on every face the number of spot-ink values must equal the number of
  spot-color layers — fewer asks («Which spot ink?»), more is an error, a malformed code is an error. The identity
  carries the ink (`spot-ink@front=…/300-c`). The resolver's search bound for spot layers goes from 4 to 8; the
  specification sets no limit — the press does (`inkStations` in vendor-declaration/1). Agent prompt and rule mode
  read «Pantone 300 C», «PMS 485», «HKS 43 K», «RAL 5015» as a spot layer plus a named ink on the face named.

## 0.36.8 — 2026-10-12

- **Something is happening.** While the agent runs, a moving bar sits under the rail with a line that follows the
  work — «model call 3 of 12 · 7 tool calls so far · the model is thinking …», «model call 3 · ptpge_validate_config …».
  It disappears when the run ends.

## 0.36.7 — 2026-10-12

- **Mark and QR the same size.** In the fingerprint result the mark tile and the QR tile are now both 160 px with
  the same padding, captions aligned beneath.

## 0.36.6 — 2026-10-12

- **Rule mode: «cover» is a place, not a thing.** A lone face or part word (cover, inside, outside, front, back and
  their translations) is no longer looked up on its own — «cover» found case binding and the booklet failed on a
  binding nobody asked for. Also: the envelope-implied setup model was listed among the «not in envelope» values in
  the message; it is not.

## 0.36.5 — 2026-10-12

- **Rule mode: a face word scopes only face axes.** «saddle stitched, 300 gsm matte cover» gave the binding and the
  setup model a surface («outside») because «cover» stood near them — and the validator rightly refused. Now only
  colour, surface finish and embellishment take a face word; on a multi-page product «cover» places the finish on
  the front and back cover and «inside» on the inside pages (never outside/inside, which are folded-sheet faces).

## 0.36.4 — 2026-10-12

- **4/4 on a booklet means every page.** `ptpge_resolve_color_notation` on a setup with more than two faces
  (multi-page) now reads an equal pair — 4/4, 1/1 — as every face; before, it mapped to front/back, which are not
  faces of a booklet, and the validator then asked «Which colour set on the front-cover?». An unequal pair (4/1)
  cannot be placed on five faces without a guess: one question, «state it per part, e.g. cover 4/4, inside 1/1».
  Rule mode relays that question.

## 0.36.3 — 2026-10-12

- **Rule mode knows parts.** «300 gsm matte cover, 130 gsm inside» (and omslag/innmat, Umschlag/Innenteil, …) now
  gives two `substrate-weight` bindings scoped `@cover` / `@inside` in «Resolve by rule»; before, the first gsm
  was taken for the whole product and the second dropped. A gsm with no part word binds the whole product as before.

## 0.36.2 — 2026-10-12

- **Fix: Playground stuck on «connecting…».** 0.36.0 put an unescaped quote in the agent prompt text, which broke
  the page's script. A test now parses every Playground script with node.

## 0.36.1 — 2026-10-12

- **Parts in the declaration.** `ptpge_check_domain` accepts `offerings[].supports` keys with a part scope
  (`substrate-weight@cover`, `@inside`) per vendor-declaration/1 as updated today: the variable must be a substrate
  variable and the part one that a setup model of the product declares; otherwise an error names the parts that exist.

## 0.36.0 — 2026-10-12

- **Parts (SD-0102).** A booklet can carry one paper on the cover and another inside. `multi-page` declares parts
  (`cover`, `inside`); the substrate variables can be bound per part — `substrate-weight@cover=300`, `@inside=130`.
  The ptpge-cfs/1 scope slug now means surface *or* part; grammar unchanged, existing fingerprints unchanged.
  `ptpge_validate_config`: a part scope that is not in the chosen setup → `surface_not_in_setup`; weight bound for one
  part only → `needs_disambiguation` («Which paper weight for the inside?»). `ptpge_get_product_envelope` returns
  `surfacesBySetup[setup].parts`. The Playground agent knows `@cover`/`@inside` and asks rather than assumes.

## 0.35.0 — 2026-10-12

- **The right template, not a dead end.** When a bound value is not in the chosen template's envelope but another
  template takes every bound value, `ptpge_validate_config` now returns `alsoOfferedBy` (ranked, with
  `acceptsBindings`) and a `switchHint`: a poster on aluminium composite is a panel print. The Playground's rule mode
  switches once and validates again; the agent prompt tells the model to switch rather than drop what the buyer asked
  for; «What the agent did» says «Posters does not take aluminium composite — but Panel Prints does». Data only, no model.

## 0.34.1 — 2026-10-12

- **Answer the agent.** When a run ends without a fingerprint — the specification asked which fold, which format, how
  many pages — a reply box appears: type the answer, the same conversation continues (same run, so it counts as rounds,
  not a new sponsored run), the rail and the story carry on. The buyer's answer is a line in «What the agent did».
- Model turns get `max_tokens` 4000 (was 1500 — a long tool_use turn could end empty); when a run still ends without text
  the stop reason is shown instead of «the question is in the last line».

## 0.34.0 — 2026-10-12

- **Sponsored Playground runs are PTPGE's own.** The model proxy moved from an implementer's service to this server:
  `GET /agent/status`, `POST /agent/messages` — PTPGE pays, 5 runs per address per day (`PTPGE_AGENT_PER_IP`), 300 a day
  in all, 12 model calls per run; the key (`ANTHROPIC_API_KEY`) never leaves the server, prompts are not logged, only
  counts. Own-key runs (Anthropic, OpenAI) are unchanged. The page now says what it is for: watching the loop — for
  everyday use, switch on the connector in Claude or ChatGPT.
- **The rail and the story.** While the agent runs, five steps light up as its tool calls land — Product · The words ·
  Colour · Check · Identity (amber when the specification asks a question back). Afterwards, «What the agent did»: one
  plain sentence per tool call, written from the call and its result, no model — the raw transcript stays below.

## 0.33.5 — 2026-10-12

- **The mark is black, on white.** `markSvg` from `ptpge_fingerprint` now renders in black ink (was the brand green); the
  Playground shows every mark and QR on a white tile, so they read the same in light and dark mode. Same change on
  the register (ptpge.org/f) and the scan page.

## 0.33.4 — 2026-10-12

- Theme and language follow you from ptpge.org: both are now also kept in a cookie for `*.ptpge.org`, so dark mode
  and the chosen language set on the site apply on mcp.ptpge.org (Playground, /check) and the register — localStorage
  alone is per host. The Playground reads the shared `ptpge-lang` as well as its own key.

## 0.33.3 — 2026-10-11

- Playground: the twelve language buttons in the convergence demo carry their flag, like the site's language picker.

## 0.33.2 — 2026-10-11

- **Check is bounded on a silent domain.** A host that does not answer (connection hang) timed out once per
  document — 30–40 s and a gateway timeout from the page. Now: connect timeout 5 s, and a host that times out once is
  not asked again in the same check; the report comes back in ≈10 s with «No answer from the domain».

## 0.33.1 — 2026-10-11

- **Check: makers and hosted documents.** A domain with a valid supplier catalogue and a suppliers-register entry,
  but no shop manifest or declaration, is now `maker` (maker-ready) instead of partial — a mill is not a shop.
  The identity step checks whichever identities the documents carry (vendors and/or suppliers). Optional `document`
  parameter (tool, `/check.json?document=`): an https URL of a declaration or catalogue hosted elsewhere than the
  known path (register entries marked «hosted»); the step then warns rather than fails on the path. `agentSees`
  gains `logo`, `catalogueIdentity`, `catalogueName`, `catalogueLogo`.
- ptpge.org's adopt flow (apply.php, weekly recheck.php) now validates through `/check.json` — one truth — with the
  old mechanical HTTP/JSON/identity check only as fallback when this server does not answer.

## 0.33.0 — 2026-10-11

- **Tenth tool — `ptpge_check_domain`: does an agent find you?** Fetches exactly what a checkout agent fetches on a
  domain — `/.well-known/ucp` (the UCP manifest and its `ptpge` block), the vendor declaration at
  `/.well-known/ptpge/declaration.json`, the identity in the vendors register, and a supplier catalogue if present —
  and validates each against its published JSON Schema (fetched from `ptpge.org/v1/schemas/`, never copied) and the
  vocabulary (unknown term = error, deprecated = warning). Returns a verdict (`ready` · `partial` · `none`), one line
  per step, what the agent sees (name, identity, products, capability counts) and what is missing with where to fix it.
  Read-only; nothing is stored.
- **Two more doors to the same check:** `GET /check` — a page in the ptpge.org frame (paste a domain; `?domain=` deep
  link), and `GET /check.json?domain=…` — the raw report, CORS open, for curl and other tools. `ptpge.org/check/`
  redirects here.
- New dependencies: `jsonschema`, `referencing`.

## 0.32.2 — 2026-10-11

- **Playground demo order is complete again.** Orientation became a required axis (SD-0083/SD-0101) after the
  demo was written: the fixed example now says «A5 portrait», binds orientation, and binds the ivory substrate colour
  it always asked for; the ten-language convergence demo binds orientation too. Three clicks end in a fingerprint.

## 0.32.1 — 2026-10-11

- **Playground, rule mode:** a named fold that resolves as a completion (`completions/folding/roll-fold`) is bound
  as the sheet's setup model (`setup-models/folded-sheet/roll-fold`) when no setup is bound yet — «A4 roll fold
  leaflet» no longer ends in «which fold?». The validator still confirms the setup is in the product's envelope.

## 0.32.0 — 2026-10-11

- **SD-0098 applied to surface finish.** `ptpge_validate_config` and `ptpge_get_product_envelope` no longer append
  `surface-finish/none` to envelopes — that term is deprecated without successor; a finish you do not ask for is not
  applied. The same for `embellishments/none` (SD-0098 extended 2026-10-11). `colors/none` (a face with no ink) is unchanged.
- **No layer wording.** Tool descriptions and results say «the specification» and «an implementation's concern (a
  configurator)» instead of Layer 1/2/3.
- **Playground:** when the agent ends without text and without a fingerprint, the panel shows the specification's last
  answer — open questions (`needs_disambiguation`), values not in the envelope, rule violations — instead of «(no answer)».

## 0.31.1 — 2026-10-10

- `/favicon.ico` and `/icon-512.png` served by the app (the PTPGE mark) so directory listings and MCP clients
  that read the favicon from the server URL show the right icon. Root banner: `status` is now `public-beta`,
  `documentation` points to ptpge.org/developers/, `icon` added.

## 0.31.0 — 2026-10-10

- **Tool annotations.** Every tool carries `title` and `annotations` (`readOnlyHint: true`, `destructiveHint: false`,
  `idempotentHint: true`, `openWorldHint: false`) — required by the Claude Connectors Directory; useful to every
  client. No tool behaviour changed. Requires `mcp>=1.12.0`.
- Listed in the official MCP Registry as `org.ptpge/mcp-server` (`server.json`).

## 0.30.1 — 2026-10-10

- Repository prepared for public release: Apache-2.0 `LICENSE`, `pyproject.toml` (licence, version 0.30.1,
  author PTPGE), README rewritten for readers outside the project (tools, endpoints, run it yourself,
  configuration — no hosting internals), last «Standard» strings in code → «specification» (SD-0095).
  No functional change.

## 0.30.0 — 2026-10-07

- **SD-0098 — absence means «none».** `ptpge_validate_config` no longer lists finishing axes (`variables/finishing/*`,
  `features/surface-finish`, `features/embellishment`) as `unspecified_axes`: a configuration without them is an
  unfinished product, complete whenever the required variables are bound. Substrate, production and compliance axes stay
  advisories. The advisory note says so.
- Playground agent instructions: step 4b — never ask about, suggest or bind an optional axis the buyer did not mention;
  ask back only about required variables.
- Playground frame links to ptpge.org (go-live 7 Oct). Playground in the PTPGE dress: ink instead of green,
  4 px corners, Spectral title, dark mode on cards/buttons/transcript.

## 0.29.0 — 2026-10-06

- SD-0097: `ptpge_search_terms` skips deprecated terms by default (new `include_deprecated`
  flag); every hit carries `kind` — term | supplier | vendor | schema — so an agent asking for
  «Heidelberg» lands on the register entry `/v1/suppliers/heidelberg`, not the retired node.
  Deprecated hits (when asked for) carry `status` and `replacedBy`. Search index now includes
  `status`, `type`, `replacedBy` (built by build_api.py). Embeddings rebuilt from the 2026-10-06
  data (deprecated excluded, registers and schemas included).

## 0.28.10 — 2026-10-06

- Playground wears the ptpge.org frame: mark + PTPGE + nav + group stripe + footer,
  Fraunces/Inter via `ptpge.org/assets/fonts`, contour background. «← GutenLex» →
  «← Developers» (ptpge.org/developers/). Frame is generated into `ptpge_mcp/_frame.py`
  by `tools/export_frame.py` (do not edit by hand).

## 0.28.9 — 2026-10-05

- Wording (SD-0095): "PTPGE Standard" / "GutenLex Standard" / "the Standard" →
  "PTPGE specification" everywhere the server speaks: `_SERVER_INFO` title,
  root JSON (`service`, `description`), tool descriptions, module docstring,
  Playground UI strings and the `e_own` explainer in all 14 UI languages.
- Playground: the example prompt is now complete (A4 portrait, roll fold …)
  so «Run agent → fingerprint» ends in a fingerprint; a hint under the button
  says the agent asks (SD-0083) when fold or orientation is left out.

## 0.28.8 — 2026-10-03

- `/mcp` answers CORS: `OPTIONS` → 204, and every response carries
  `Access-Control-Allow-Origin` (default `*`; `PTPGE_MCP_CORS_ORIGIN` locks it
  to one origin, `0` switches it off). A browser page on another origin can now
  call the open server directly — first user: trykkverk.no/prompt/, where the
  buyer's typed or spoken order is turned into a configuration by an agent whose
  tool calls run from the buyer's browser. Nothing changes for same-origin
  clients (playground) or for MCP clients.

## 0.28.7 — 2026-09-23

**Twelve languages (SD-0089).** The playground speaks Portuguese and Hindi:
language menu, the full UI string set for both, and the four convergence
products (brochure, business cards, booklet, panel print) phrased in `pt` and
`hi`; «ten languages» reads «twelve» in every UI language. The `get_term` /
`search` language selectors list `pt` and `hi`. `term_embeddings.npz` rebuilt
from the 843 terms with the new labels and altLabels (523 value/product/
reference vectors; same model). Lexical search already matched the new labels
the moment the data refreshed (2026-09-23). The language button is the same
flag pill as the editor, the configurator and the storefront (flag + code;
flag + native name in the list) — Patrik.

## 0.28.6 — 2026-09-22

**SD-0088 — the null value is always in a feature envelope.** For colour mode,
embellishment and surface finish, `…/none` is a member of every template's
per-face envelope without being listed: `ptpge_get_product_envelope` appends it
to `perSurfaceSupports*` (only when the term exists in the vocabulary) and
`ptpge_validate_config` accepts it as `in_envelope`. New Layer 1 values
`surface-finish/none` and `embellishments/none` (standalone). Two tests.

## 0.28.5 — 2026-09-20

**R6 — what may stand together (SD-0084).** `cfs_resolution.py` (byte-identical
with tools/, the configurator and the Engine) now reads three data fields from
the Standard: `exclusiveGroups` on a variable (rule `at-most-one`), `standalone`
and `multiInstance` on a value. A binding carrying two values of one group
(CMYK + CMYKOGV, black + CMYK), a standalone value with company (none + spot) or
a repeated value that is not multi-instance is refused with
`exclusive_group_conflict`; three named spot inks remain legal and serialize as
three instances. `ptpge_validate_config` reports the violation under `rules`
and sets `complete: false`; `ptpge_fingerprint` refuses with
`reason: exclusive_group_conflict`. No valid identity changes. Tests 134.

## 0.28.4 — 2026-09-19

**Term vectors rebuilt after the sv/da/nl altLabel pass** (Standard dataVersion
2026-09-19: 802 buyer words on the 56 product templates; Dutch «folder» moved
from Flyers to Brochures). 521 of 521 eligible terms. No code change.

## 0.28.3 — 2026-09-19

**Term vectors rebuilt.** `term_embeddings.npz` was from 2026-09-08 and missed the
altLabel edits of 13.09 and the June duplicate clean-up (two retired URIs still
carried vectors). Now 521 of 521 eligible terms, built 19.09. No code change;
search weights unchanged. The dashboard's Search Relevance Tuning panel now
reports coverage and staleness of this file, so the drift is visible next time.

## 0.28.2 — 2026-09-18

**cfs/1 § 11 R5 — entailment: "170 gsm silk" *is* paper.** Patrik ran the same
tri-fold prompt through two agents and got two identities. Half the drift was an
agent adding `substrate-type = paper` that the other left out; the other half was
an agent scoping "matte lamination" to `@outside` alone. Two fixes:

- `cfs_resolution.py` R5: a bound value under
  `printing/substrates/<class>/<material>/` (a paper surface, weight class,
  coating, shade, supplier) entails `substrate-type = <material>`; unbound →
  bound (*entailed*), bound to another material → `substrate_type_conflict`
  (refuse). Byte-identical in the four homes; conformance vectors
  `trifold-silk-untyped` == `trifold-silk-typed`, conflict refused.
- `ptpge_validate_config` reports the entailed type (`status: entailed`,
  `entailedBy`) so an agent sees it before hashing; a conflict fails
  `validInEnvelope` and `complete`.
- Playground agent prompt (marker `PTPGE-PLAYGROUND-AGENT/1` unchanged — the Engine proxy checks it), new rule 2b: bind exactly
  what the buyer stated — a face attribute without a face is bound without a
  surface (the validator spreads it, D5); never add an axis the buyer did not
  state. Same text in `present/live` and `dl/live`.

Nothing else is entailed. Agent-introduced choices remain visible as different
identities — the Standard promises *same configuration → same identity*, not
*same words → same identity* beyond what follows from the words.

## 0.28.1 — 2026-09-16

**cfs/1 § 11 — resolution is one module, four homes.** The SD-0083 steps that
decide the *bytes* of an identity (setup envelope-implied, D5 face expansion,
required-axes check) moved out of `server.py` into `ptpge_mcp/cfs_resolution.py`,
a byte-identical copy of the Standard's reference `tools/cfs_resolution.py`
(also in the configurator and the engine; `tests/test_cfs_conformance.py` in the
main repo refuses drift and checks four-way equality on the SD-0083 vectors).
`ptpge_fingerprint` behaviour is unchanged (same hashes, same refusals); the
`not_fingerprintable` payload additionally carries `resolution: {errors,
incomplete}`. Spec: `docs/CONFIGURATION-FINGERPRINT.md` § 11 (v0.2). 132 tests.

## 0.28.0 — 2026-09-16

**SD-0083 — one specified product, one identity.** Two runs of the same model on
the same prompt had produced two identities (15/16 Sept): the Standard let two
spellings of a folded sheet's faces through, and let an *assumed* fold become
an identity. Fixed at the source, in the tools, not in the model:

- **Surfaces follow the setup model.** Every setup term already declares its
  faces (`surfaces`: flat-sheet front/back, folded-sheet outside/inside,
  multi-page front-cover … back-cover, roll face/back, display-system graphic,
  structural outside/inside, multi-part parts). `ptpge_validate_config` now
  rejects a surface that is not a face (or panel) of the bound setup — status
  `surface_not_in_setup` with the allowed faces — never a silent rename, so
  `ptpge-cfs/1` stays byte-defined. `ptpge_get_product_envelope` returns
  `surfacesBySetup`. `ptpge_resolve_color_notation` takes the faces from the
  new `setup` argument (or the product's only setup): "4/1" on a tri-fold
  lands on outside/inside.
- **No identity without the required axes.** Product templates carry
  `requiredVariables` / `recommendedVariables` (dataVersion 2026-09-16; the
  56-row table in `docs/sd-0083/`). Missing required axis → `needs_disambiguation`
  with the question and the envelope's candidates (which fold, which format,
  how many pages, which binding, which colour on the first face, which shape
  where shape is the product); missing recommended axis → advisory
  `unspecified_axes`. New result field `complete`.
- **`ptpge_fingerprint` validates first and refuses** (`error:
  not_fingerprintable`, reason `not_valid_in_envelope` | `incomplete`, with the
  validator's questions) — no hash for an incomplete or invalid configuration.
  A complete result carries `validated: true`, `bindingsUsed`, `envelopeImplied`.
- **D1 — envelope-implied values are written into the identity.** A required
  axis with exactly one allowed value (flat-sheet for a flyer) is bound with
  provenance `envelope-implied` and appears in the canonical string, so an
  agent that states it and one that omits it get the same hash.
- **D5 — a face attribute stated without a face applies to every face.**
  "full colour", "matte lamination" on a two-faced setup expand to one binding
  per face (`surface_provenance: envelope-implied`); "4/0", "one-sided",
  "outside only" say otherwise. "1000 Flyer A5, 170 g, 4/4" and "1000 flyers
  A5, 170 gsm, full colour" now share `445aa8c9df3fa52e`.
- **The Standard never assumes.** The 0.27.1 rule that bound single-fold for
  "folded" is withdrawn; the rules path shows the validator's question instead
  ("no identity yet — the Standard asks"). Playground agent instructions
  updated: relay the question, never assume a fold, size or colour; pass
  `setup` to the colour resolver. Provenance enum gains `envelope-implied`.
- Known limit: pair notation ("4/4") on multi-page setups still maps to
  front/back and the validator then asks for the front-cover colour — the
  six-faced case needs its own notation rule.
- Registered fingerprints are untouched (never retired); configurations that
  previously omitted an implied setup reproduce with it from now on.
- Playground: **Agent mode is the primary path** (rules buttons outlined, "Resolve
  by rule"); the four presets get **Verify with a real model →** — the same
  phrase, the same tools, and the answer "✓ same identity" or the model's
  reason; the rules path shows the Standard's questions instead of a hash.
  `agentRun(opts)` returns `{fp, answer}` for callers.
- The ordered surface-finish stack may carry an embellishment as its top layer
  (matte > spot-uv, the published worked example): membership is checked
  against both per-surface envelopes. The reference brochure (`f2e377cb…`)
  validates and is complete under the new rules.
- Tests: 132 (seven new SD-0083 tests incl. stated-vs-implied and D5 equality).

## 0.27.1 — 2026-09-16

- **Rules mode learns what the agent did on the leaflet prompt.** On 15 Sept the
  agent and the rules path disagreed on the reference prompt ("folded leaflet …
  full colour both sides"): the agent bound `folded-sheet/single-fold` and put
  the colour on *outside/inside*; the rules bound no setup and used
  *front/back*. Rules now do the same, explicitly: when the prompt says "folded"
  (ten languages: folded, falset/falsede, gefalzt, gevouwen, plié, plegado,
  składany, 折り …) and names no fold, the Single-Fold Setup is bound and the
  transcript says *"folded, fold not named → single-fold (one fold — name the
  fold to change it)"*. With any folded-sheet setup bound, a two-sided colour
  goes to outside + inside instead of front + back, and the colour resolver's
  front/back are read as outside/inside (logged). Both paths now give
  `ac570760ad06a2e8` on the reference prompt.
- The fold is an assumption, not the buyer's word — so if the product's
  envelope rejects it (flyers, business cards), the binding is dropped, the
  derived surfaces revert to front/back, and validation runs again; the
  transcript shows the drop. Fingerprints for products without folded setups
  are unchanged.
- Trap fixed on the way: a `\b` written inside the Python source string
  reached the browser as a backspace character; regex word boundaries in
  `playground.py` must be written `\\b`. Test added.

## 0.27.0 — 2026-09-15

- **Playground agent mode — a real model runs the loop.** Under "Your own
  prompt", next to the rules-based path, the page can now hand the tools from
  `tools/list` to an LLM and let it run the loop itself: search terms, read the
  envelope, resolve colour notation, validate, fingerprint. The TOOL calls are
  still made by the page against `/mcp`, so the transcript shows the complete
  conversation an agent has with the Standard — model turns (with token
  counts) and every `tools/call`. The result renders like the rules path:
  mark, QR, editable canonical form, the agent's answer on top.
- Three ways to bring a model. *Sponsored run* (default): model calls go
  through `engine.gutenlex.com/agent/messages` (Engine 0.5.0), which holds the
  key and caps runs (5 per address per day, 300 per day, 12 model calls per
  run); interpreting free text is Layer-3 work, so this Layer-1 server never
  carries a model. *Your own Anthropic key* / *Your own OpenAI key*: kept only
  in the browser's localStorage and sent straight to the provider; the model
  name is editable (defaults `claude-sonnet-5` / `gpt-5.4-mini`; OpenAI calls use `max_completion_tokens`, required by the GPT-5 series).
- System prompt (`PTPGE-PLAYGROUND-AGENT/1`) encodes the same rules as
  assembly v2 — element-level terms only, variable by tree position, numbers
  by unit word, colour counts through the resolver and STOP on
  `needs_disambiguation`, validate before fingerprint, never invent URIs.
- Tests: `tests/test_playground_agent.py` (static wiring);
  `tests/browser/agent_loop_check.py` (Playwright, model mocked with a scripted
  policy, tools live) — sponsored, Anthropic and OpenAI paths all end in the
  same fingerprint as rules mode on the leaflet prompt (`213fcf22d7218aad`),
  headers and localStorage verified, no page errors.

## 0.26.0 — 2026-09-14

- **Playground own-prompt: assembly v2 — the prompt is solved, not sketched.**
  "Fingerprint this" now follows the steps an agent takes, as rules: only
  value-level terms bind (a group such as "Paper Weights" or the root never
  does); each term goes to the variable its place in the tree implies (binding,
  substrate-finish/-coating/-color/-class, surface-finish, embellishment,
  format, setup-model, orientation, certification, print-standard,
  technology …); numbers bind by the unit word beside them in the ten
  languages (24 sider → page-count, 110 g → substrate-weight, 500 stk →
  quantity); "4 farver 2-sidet", "4/4", "4+1", "enkelsidigt" go through
  `ptpge_resolve_color_notation` and a `needs_disambiguation` stops the run
  with the question shown verbatim; the configuration is validated with
  `ptpge_validate_config` before it is fingerprinted, and a value outside the
  product's envelope stops it with a plain reason. The transcript shows every
  call. The Danish booklet prompt that used to yield two bindings now yields
  the same seven bindings — and the same fingerprint — as a Claude agent using
  the connector.
- Default example prompt changed to one inside the Brochures envelope
  ("170 gsm silk paper"); "heavy recycled paper" was never a brochure
  substrate finish and now says so instead of fingerprinting half a product.

## 0.25.2 — 2026-09-14

- **Playground own-prompt: Unicode-aware word splitting.** The n-gram stand-in
  cut words at æ ø å ä ö ü ł ñ (and every non-Latin script): "hæfter" became
  "h" + "fter" and matched Postpress Proofing, "på" became "p" and matched the
  root. Letters in every script now survive, so "hæfter" resolves to Booklets
  (0.95) as the search itself always did. Stop-word list extended with the
  small connector words of nb/da/sv, de, nl, pl and es so they stop producing
  candidate phrases.

## 0.25.1 — 2026-09-14

- **Playground: every fingerprint result is now editable.** The canonical form
  under a `ptpge_fingerprint` result (own prompt, chain demo, transcript) is a
  live field: change one byte and the SHA-256 recomputes in the browser and
  turns red — "different bytes, different identity" — with the mark and QR
  dimmed; `reset` brings the published hash back, green. Same mechanism as the
  convergence demo, now wherever a fingerprint is shown, so a free-text prompt
  can be taken all the way to identity and back on one page.
- Fix: the "could not reach /mcp" hint referenced a variable out of scope.

## 0.25.0 — 2026-09-11

- **`ptpge_expand_fingerprint` (new, 9 tools).** Read-back over MCP: a spec or
  offer fingerprint (64-hex or 16-hex short form, URL prefix tolerated) →
  profile, product, every binding with labels in the requested language,
  canonical string, dataVersion. A lookup in the public resolver (ptpge.org/f/),
  never an inversion — unregistered fingerprints return `status: "unknown"`
  with an explanation. Closes the MIS/ERP rung Torben flagged 11.9 (Dataline /
  MultiPress connector).
- **`ptpge_fingerprint` description: no more «etc.».** The commercial cluster is
  named as the closed list it is — quantity, lead-time, delivery-method,
  incoterm (`variables/order/`, SD-0040); transaction data (file, delivery
  date, price) is keyed by the offer fingerprint and never hashed into it.
- **Elicitation contract stated once for all tools** (`ptpge_validate_config`
  description): `needs_disambiguation` entries carry `field`, `question`
  (verbatim to the user) and `candidates`; never infer, never fingerprint
  before resolution. Same shape `ptpge_resolve_color_notation` has used since
  SD-0071.
- Tests: 121 (3 new for expansion — non-hex rejected, 404 → unknown, resolve +
  relabel).

## 0.24.0 — 2026-09-08

- **Polish (pl) is the tenth content language (SD-0077).** `label.pl`, `definition.pl`
  and `altLabels.pl` on all 840 terms; `get_term(language="pl")` and search over
  Polish buyer phrases now resolve. Embeddings rebuilt with Polish labels and
  altLabels (523 vectors). Playground: Polish added to the convergence demo
  (four products), «nine languages» → «ten languages» in all UI languages.
  `llm-draft` in `ptpge:translationStatus`; professional review pending.

## 0.23.0 — 2026-09-05

- **Winding direction is bindable.** `validate` knows `variables/configuration/winding-direction`
  (FINAT positions 1–8, adopted from XJDF `Component/@WindingResult`) against the
  `supportsWindingDirection` envelope on roll-supplied products (labels, stickers).
  A beta tester's kiss-cut sticker ticket on a roll asked for it. One new test; 118 pass.

## 0.22.0 — 2026-09-03

- **Print condition and paper class are bindable (SD-0076).** `validate` now
  knows two more axes with product envelopes: `variables/substrate/substrate-class`
  (ISO 12647-2 PS1–PS5 → `supportsSubstrateClass`) and
  `variables/configuration/back-orientation` (head-to-head / head-to-foot →
  `supportsBackOrientation`). `supportsPrintStandard` is populated on the paper
  templates, so a bound Fogra/GRACoL/CRPC condition is checked, not passed
  through.
- **Numeric range axes.** A small table (`NUMERIC_RANGE_AXES`) maps numeric
  axes to their `{min, max, unit}` envelope: substrate thickness (SD-0070) and
  the new `spine-thickness` (mm; books, photo books, notebooks). Out-of-range
  values are reported with the template's range.
- **Cross-axis rule `substrate_class_coating_mismatch`.** PS1–PS4 are coated,
  PS5 is uncoated; a bound coating that contradicts the bound class is a
  violation. Three new tests; 117 pass.
- **Language-gated inflection.** «-er» / «-e» endings mark a plural in German,
  Dutch and the Scandinavian languages, not in English — «mail → mailer» is a
  different word. `variants()` takes the label's language tag; the false
  «Mailer»/«Postal Mail» collision on Postcards is gone.

## 0.21.0 — 2026-08-27

- **Products win ties, and only ties (SD-0073).** Where a phrase matches a
  product and a non-product equally well, the orderable thing goes first. It is
  what alphabetical URI order already did by accident; now it is stated, and
  tested to be a tie-break only. A product that could outrank a better match
  would hide the name collisions SD-0073 exists to expose.

## 0.20.0 — 2026-08-27

- **Number-tolerant matching (SD-0072).** «Broschüre» and «Broschüren» are one
  request; so are «sticker» and «stickers», «visittkort» and «visittkortet».
  Each label grows inflected forms, matched one tier below exact — so nothing
  that resolves correctly today is displaced, and the forms a buyer happens to
  choose stop being the difference between an answer and silence.

  Generated from our own labels rather than by stemming the query: we know what
  our labels are, and we do not know what the buyer typed. Stemming an unknown
  word is how «Poster» becomes «post». Truncation is held to a longer minimum
  than suffixing for the same reason.

  Five failures in the 342-phrase product-variant corpus resolved, none broken.
  CJK excluded — no grammatical number.

## 0.19.0 — 2026-08-27

- **A view-only key for /learning**, `PTPGE_LEARNING_KEY_READONLY`. It shows the
  whole record and grants no authority: no setting a word out of scope, no
  asking for a gloss. That makes it a key you can put in an email to a
  colleague — revoking it later does not disturb the curator's own key, and
  scope stays a decision made in one place rather than by two people
  separately. The page says which key you arrived with.
- Fix: the session cookie stored the curator's key regardless of which key was
  presented. It now stores the one actually used.

## 0.18.0 — 2026-08-27

- **One learning record across both apps.** `mcp.` and `open.` can now be
  pointed at the same file via `PTPGE_LEARNING_FILE` and keep one shared
  account of what the vocabulary cannot resolve — so a phrase set out of scope
  on one host is out of scope on the other.

  Sharing a file between two processes is where this normally goes wrong: each
  app holds its own copy in memory, and writing that copy out discards whatever
  the other recorded meanwhile. So a process no longer writes what it *has* —
  it writes what it *changed*. Counts are kept as increments and edits as a
  replayable list; every write re-reads the file and applies them on top, and
  every read of the page re-reads first. No lock is held across a request.
- `~` in `PTPGE_LEARNING_FILE` is expanded, so both apps can be given the
  identical value — cPanel stores env vars verbatim, tilde and all.
- `reset()` removes the file rather than writing an empty one, so a cleared
  record cannot resurrect from a stale in-memory copy.

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
