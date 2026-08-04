"""Browser playground for the PTPGE MCP server (v0.3.3).

A single self-contained HTML page served at GET /playground. It exercises
the real Streamable HTTP transport from the browser: every button builds a
JSON-RPC message and POSTs it to /mcp on the SAME origin (no CORS needed),
then renders the tool result. Zero dependencies, zero install — the demo
URL anyone can open: https://open.mcp.ptpge.org/playground

On the stealth server the page sits behind the same Basic Auth as
everything else, so it works there too once the browser has credentials.
"""

PLAYGROUND_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%231f4a35'/%3E%3C/svg%3E">
<title>PTPGE MCP — Playground</title>
<style>
* { box-sizing: border-box; }
body { font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
       color: #1a1a1a; background: #f7f7f5; margin: 0; padding: 0; }
header { background: #fff; border-bottom: 1px solid #e0e0dd; padding: 18px 28px; }
header h1 { font-size: 18px; margin: 0; }
header .sub { color: #777; font-size: 13px; margin-top: 4px; }
header .sub code { background: #f0f0ee; padding: 1px 6px; border-radius: 4px; }
.badge { display: inline-block; background: #1f4a35; color: #fff; font-size: 11px;
         font-weight: 600; letter-spacing: .5px; padding: 2px 9px; border-radius: 100px;
         margin-left: 8px; vertical-align: 2px; }
main { max-width: 880px; margin: 0 auto; padding: 22px 28px 60px; }
.card { background: #fff; border: 1px solid #e0e0dd; border-radius: 10px;
        padding: 18px 22px; margin-bottom: 18px; }
.card h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .6px;
           color: #555; margin: 0 0 12px; }
.row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
input, select { padding: 8px 12px; border: 1px solid #ccc; border-radius: 7px;
                font-size: 14px; font-family: inherit; }
input[type=text] { flex: 1; min-width: 220px; }
button { padding: 8px 18px; border: none; border-radius: 7px; background: #1f4a35;
         color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; }
button:hover { background: #2a6045; }
button:disabled { background: #aaa; cursor: wait; }
.hint { font-size: 12px; color: #888; margin-top: 8px; }
.hint a { color: #2a6045; cursor: pointer; text-decoration: underline; }
#out { background: #1e1e1e; color: #d4d4d4; border-radius: 10px; padding: 16px 20px;
       font: 12.5px/1.5 ui-monospace, "SF Mono", Menlo, monospace;
       white-space: pre-wrap; word-break: break-word; min-height: 120px;
       max-height: 540px; overflow: auto; }
#out .k { color: #9cdcfe; } #out .s { color: #ce9178; } #out .n { color: #b5cea8; }
#meta { font-size: 12px; color: #888; margin: 8px 2px; }
#status { font-size: 13px; color: #777; }
#status b { color: #1f4a35; }
footer { text-align: center; color: #999; font-size: 12px; padding: 18px; }
footer a { color: #2a6045; }
/* — v2: convergence demo + language switcher — */
#ui-lang { float: right; margin-top: -34px; }
.conv .langrow button { background: #fff; color: #1f4a35; border: 1.5px solid #1f4a35; }
.conv .langrow button:hover { background: #eef4f0; }
.conv .langrow button.on { background: #1f4a35; color: #fff; }
.stage { border-left: 3px solid #e0e0dd; margin: 14px 0 0; padding: 2px 0 2px 14px; }
.stage .slbl { font-size: 11px; letter-spacing: .6px; text-transform: uppercase;
               color: #777; font-weight: 700; }
.stage .slbl .num { color: #1f4a35; margin-right: 6px; }
.stage .tag { display: inline-block; font-size: 10px; background: #f0ede2; color: #8a6d00;
              border-radius: 100px; padding: 1px 8px; margin-left: 8px; vertical-align: 1px; }
.stage .mono { font: 12.5px/1.5 ui-monospace, "SF Mono", Menlo, monospace;
               word-break: break-all; }
.stage table { border-collapse: collapse; width: 100%; font-size: 12.5px; margin-top: 4px; }
.stage td { padding: 3px 10px 3px 0; vertical-align: top; }
.stage td.ph { color: #555; font-style: italic; }
.stage .lng { display: inline-block; font-size: 10px; background: #e8f2ed; color: #1f4a35;
              border-radius: 4px; padding: 0 5px; margin-left: 6px; font-style: normal; }
#conv-hist table { border-collapse: collapse; width: 100%; font-size: 12.5px; }
#conv-hist td { padding: 4px 10px 4px 0; border-top: 1px solid #eee; }
#conv-hist .fp { font-family: ui-monospace, Menlo, monospace; }
#conv-hist .same { color: #1f7a3d; font-weight: 700; }
.stage .vis svg { width: 100%; height: auto; display: block; }
</style>
</head>
<body>
<header>
  <select id="ui-lang" onchange="setLang(this.value)"></select>
  <h1>PTPGE MCP — Playground <span class="badge">LIVE</span></h1>
  <div class="sub"><span data-i="sub">Every button below sends a real MCP <code>tools/call</code> (JSON-RPC over
  Streamable HTTP) to <code>/mcp</code> on this server — exactly what an AI agent does.</span>
  <span id="status">connecting…</span></div>
</header>
<main>

<div class="card conv">
  <h2 data-i="t_conv">Same product · any language · one fingerprint</h2>
  <p style="font-size:13px;color:#555;margin:0 0 10px" data-i="i_conv">The reference brochure
  — A5, accordion fold, 8 pages, 170 gsm, colour outside / black inside, matte lamination
  with spot UV — phrased in six languages. Pick one and watch the same identity emerge.</p>
  <div class="row langrow" id="conv-btns"></div>
  <div id="conv-tgl" style="display:none;text-align:right;margin-top:8px"><a
    style="cursor:pointer;color:#2a6045;font-size:12px;text-decoration:underline"
    onclick="convToggle()"></a></div>
  <div id="conv-out"></div>
  <div class="hint" data-i="h_conv">The interpretation (words → bindings) is pre-scripted per
  language — that is the AI agent's job in production. The term labels, envelope validation
  and the ptpge-cfs/1 fingerprint run <em>live</em> against this server. The hash is a
  deterministic function, not a model output.</div>
  <div id="conv-hist" style="display:none;margin-top:14px">
    <div class="stage"><span class="slbl" data-i="hist">Run history — same product, different languages</span>
    <table id="conv-hist-t"></table></div>
  </div>
</div>

<div class="card">
  <h2 data-i="t_search">ptpge_search_terms — free-text search</h2>
  <div class="row">
    <input type="text" id="q" placeholder="e.g. brochure · accordion fold · ivory paper · full colour · copies" value="brochure">
    <select id="q-lang">
      <option value="en" selected>en</option><option value="nb">nb</option>
      <option value="de">de</option><option value="ja">ja</option>
      <option value="es">es</option><option value="zh-Hans">zh-Hans</option>
    </select>
    <button onclick="doSearch()" data-i="b_search">Search</button>
  </div>
  <div class="hint"><span data-i="h_search">Search is tokenized and language-agnostic — buyer phrases in any
  supported language hit the canonical terms.</span> <span data-i="try">Try:</span>
  <a onclick="preset('ivory paper')">ivory paper</a> ·
  <a onclick="preset('black only')">black only</a> ·
  <a onclick="preset('accordion fold')">accordion fold</a> ·
  <a onclick="preset('creasing')">creasing</a> ·
  <a onclick="preset('gold foil')">gold foil</a></div>
</div>

<div class="card">
  <h2 data-i="t_get">ptpge_get_term — full context for one term</h2>
  <div class="row">
    <input type="text" id="uri" placeholder="URI or path under /v1/"
           value="printing/completions/folding">
    <select id="t-lang">
      <option value="en" selected>en</option><option value="nb">nb</option>
      <option value="de">de</option><option value="ja">ja</option>
      <option value="es">es</option><option value="zh-Hans">zh-Hans</option>
    </select>
    <button onclick="doGet()" data-i="b_get">Get term</button>
  </div>
  <div class="hint"><span data-i="h_get">Tip: click a result <code>id</code> from a search, or try</span>
  <a onclick="presetUri('ordering/products/brochures')">brochures</a> ·
  <a onclick="presetUri('printing/substrates/sheet-materials/paper/paper-weights/medium-paper')">medium-paper</a> ·
  <a onclick="presetUri('variables/order/quantity')">quantity</a></div>
</div>

<div class="card">
  <h2 data-i="t_ver">ptpge_get_version — dataset &amp; server version</h2>
  <div class="row"><button onclick="doVersion()" data-i="b_ver">Get version</button></div>
</div>

<div class="card">
  <h2 data-i="t_chain">Test-prompt demo — the full chain, live</h2>
  <p style="font-size:13px;color:#555;margin:0 0 10px;font-style:italic">
  "I want a brochure, 6 pages, A5, folded as a Z-fold, on ivory-toned
  heavy paper, full colour on one side and black only on the other, 500 copies."</p>
  <div class="row">
    <button onclick="doEnvelope()">1 · Envelope</button>
    <button onclick="doValidate()">2 · Validate</button>
    <button onclick="doFingerprint()">3 · Fingerprint</button>
  </div>
  <div class="hint" data-i="h_chain">The interpretation (words → bindings) is pre-scripted here — that is
  the AI agent's job. The lookups, envelope validation (incl. 250 gsm → weight band and
  the creasing advisory) and the ptpge-cfs/1 fingerprint run <em>live</em> against this
  server, exactly as an agent would call them.</div>
</div>

<div class="card">
  <h2 data-i="t_own">Your own prompt — see what resolves</h2>
  <textarea id="prompt" rows="3" style="width:100%;padding:10px 12px;border:1px solid #ccc;border-radius:7px;font-size:14px;font-family:inherit;resize:vertical" placeholder="Describe a print job in your own words, any language…">I want a folded leaflet on heavy recycled paper, matte lamination, full colour both sides, A4, 1000 copies</textarea>
  <div class="row" style="margin-top:10px"><button onclick="doResolve()" data-i="b_resolve">Resolve phrases</button><button id="fpassemble" style="display:none" onclick="assembleFingerprint()" data-i="b_fp">Fingerprint this &rarr; mark + QR</button></div>
  <div class="hint">A real agent uses an LLM to decompose a prompt. This demo approximates that by searching 1–3 word n-grams and greedily keeping the best non-overlapping matches —
  commas and connectors as a rough stand-in, then look each fragment up <em>live</em> — so you
  see which pieces map to canonical PTPGE terms and which don't. Assembling the hits into a
  validated, fingerprinted configuration is the agent's job (the demo above shows that step).</div>
</div>

<div id="meta"></div>
<div id="out">Results appear here.</div>

</main>
<footer>
  PTPGE Standard · Layer 1 vocabulary · CC BY 4.0 ·
  <a href="/">server info</a> · <a href="https://ptpge.org">ptpge.org</a>
</footer>

<script>
let rpcId = 0;

async function rpc(method, params) {
  const body = { jsonrpc: "2.0", id: ++rpcId, method: method };
  if (params) body.params = params;
  const t0 = performance.now();
  // Personal capability token: /playground?t=glxt_... forwards to /mcp, so
  // the playground keeps working after the anonymous door closes.
  const _tok = new URLSearchParams(location.search).get("t");
  const res = await fetch("/mcp" + (_tok ? "?t=" + encodeURIComponent(_tok) : ""), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const ms = Math.round(performance.now() - t0);
  const json = await res.json();
  return { json, ms, status: res.status };
}

async function callTool(name, args) {
  const buttons = document.querySelectorAll("button");
  buttons.forEach(b => b.disabled = true);
  try {
    const { json, ms, status } = await rpc("tools/call", { name: name, arguments: args });
    let payload = json;
    if (json.result && json.result.content && json.result.content[0]) {
      try { payload = JSON.parse(json.result.content[0].text); } catch (e) { payload = json.result; }
    } else if (json.error) {
      payload = json;
    }
    document.getElementById("meta").textContent =
      `tools/call ${name} · HTTP ${status} · ${ms} ms · request id ${json.id}`;
    render(payload);
  } catch (e) {
    document.getElementById("meta").textContent = "request failed";
    document.getElementById("out").textContent = String(e);
  } finally {
    buttons.forEach(b => b.disabled = false);
  }
}

function render(obj) {
  let strip = "";
  try {
    if (obj && obj.profiles && obj.profiles.spec && obj.profiles.spec.markSvg) {
      obj = JSON.parse(JSON.stringify(obj));
      strip = '<div style="display:flex;gap:26px;flex-wrap:wrap;align-items:flex-start;margin:0 0 14px">';
      for (const prof of ["spec", "offer"]) {
        const pr = obj.profiles[prof]; if (!pr || !pr.markSvg) continue;
        strip += '<div style="text-align:center;font-size:11px;color:#7fae97">' + pr.markSvg +
                 '<br>' + prof + ' · ' + pr.short + '</div>';
        if (pr.qrSvg) {
          strip += '<div style="text-align:center;font-size:11px;color:#7fae97">' + pr.qrSvg +
                   '<br><a href="' + pr.resolverUrl + '" target="_blank" rel="noopener" style="color:#37d98a">resolver ↗</a></div>';
        }
        pr.markSvg = "(rendered above)";
        if (pr.qrSvg) { pr.qrSvg = "(rendered above)"; }
      }
      strip += "</div>";
    }
  } catch (e) { strip = ""; }
  const text = JSON.stringify(obj, null, 2);
  const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const colored = esc
    .replace(/("(?:[^"\\\\]|\\\\.)*")(\\s*:)/g, '<span class="k">$1</span>$2')
    .replace(/: ("(?:[^"\\\\]|\\\\.)*")/g, ': <span class="s">$1</span>')
    .replace(/: (-?\\d+(?:\\.\\d+)?)/g, ': <span class="n">$1</span>');
  document.getElementById("out").innerHTML = strip + colored;
}

function doSearch() {
  callTool("ptpge_search_terms", {
    query: document.getElementById("q").value,
    limit: 10,
    language: document.getElementById("q-lang").value,
  });
}
function doGet() {
  callTool("ptpge_get_term", {
    id_or_path: document.getElementById("uri").value,
    language: document.getElementById("t-lang").value,
  });
}
function doVersion() { callTool("ptpge_get_version", {}); }

// — Test-prompt demo: the canonical brochure configuration —
const DEMO_PRODUCT = "ordering/products/brochures";
const DEMO_BINDINGS = [
  { variable: "variables/configuration/setup-model",
    value: "printing/configurations/setup-models/folded-sheet/z-fold" },
  { variable: "variables/configuration/page-count", value: 6 },
  { variable: "variables/configuration/format",
    value: "printing/configurations/formats/a-series/a5" },
  { variable: "variables/substrate/substrate-type",
    value: "printing/substrates/sheet-materials/paper" },
  { variable: "variables/substrate/substrate-weight", value: 250 },
  { variable: "variables/features/color-mode", surface: "outside",
    value: "printing/features/colors/cmyk" },
  { variable: "variables/features/color-mode", surface: "inside",
    value: "printing/features/colors/black" },
  { variable: "variables/order/quantity", value: 500 },
];
// — Free-text prompt: greedy non-overlapping n-gram resolution (LLM-free stand-in) —
async function doResolve() {
  const raw = document.getElementById("prompt").value || "";
  const lang = document.getElementById("q-lang").value;
  const STOP = new Set(("i want a an the on of with and or in to for it is be both sides side please order printed print copies copy gsm jeg vil ha en et pa med og eller som begge sider").split(" "));
  const cleaned = raw.toLowerCase().replace(/[^a-z0-9\\s-]/g, " ");
  const rawWords = cleaned.split(/\\s+/).filter(Boolean);
  const numbers = rawWords.filter(w => /^[0-9]/.test(w));
  const words = rawWords.filter(w => !STOP.has(w) && !/^[0-9]/.test(w));
  if (!words.length) { render({ note: "No searchable words found." }); return; }
  const cands = [];
  for (let i = 0; i < words.length; i++)
    for (let n = 1; n <= 3 && i + n <= words.length; n++)
      cands.push({ i, n, phrase: words.slice(i, i + n).join(" ") });
  const buttons = document.querySelectorAll("button");
  buttons.forEach(b => b.disabled = true);
  document.getElementById("meta").textContent =
    'resolving "' + raw + '" — ' + cands.length + " candidate phrases via ptpge_search_terms…";
  try {
    const THRESH = 0.6;
    // Skip non-configuration groups (educational guides, audiences, geography)
    // so a buyer phrase resolves to the configurable VALUE, not a knowledge guide
    // (e.g. "colour" -> CMYK, not the "Colours & ICC Profiles" guide).
    const EXCLUDE = new Set(["knowledge", "use-cases", "audiences", "geography"]);
    const pick = results => {
      for (const r of (results || []))
        if (r && r.score >= THRESH && !EXCLUDE.has(r.group)) return r;
      return null;
    };
    const hits = await Promise.all(cands.map(async c => {
      try {
        const { json } = await rpc("tools/call", {
          name: "ptpge_search_terms", arguments: { query: c.phrase, limit: 5, language: lang },
        });
        const pp = JSON.parse(json.result.content[0].text);
        const r = pick(pp.results);
        let prod = null;
        for (const x of (pp.results || []))
          if (x && x.id && x.id.indexOf("ordering/products/") !== -1 && x.score >= 0.45) { prod = x; break; }
        return (r || prod) ? { i: c.i, n: c.n, phrase: c.phrase, hit: r || null, prod: prod } : null;
      } catch (e) { return null; }
    }));
    let productFallback = null;
    for (const h of hits) if (h && h.prod && (!productFallback || h.prod.score > productFallback.score)) productFallback = h.prod;
    const ranked = hits.filter(h => h && h.hit).sort((a, b) => (b.hit.score - a.hit.score) || (b.n - a.n));
    const used = new Array(words.length).fill(false);
    const seenUri = new Set();
    const chosen = [];
    for (const c of ranked) {
      let overlap = false;
      for (let k = c.i; k < c.i + c.n; k++) if (used[k]) overlap = true;
      if (overlap || seenUri.has(c.hit.id)) continue;
      for (let k = c.i; k < c.i + c.n; k++) used[k] = true;
      seenUri.add(c.hit.id); chosen.push(c);
    }
    chosen.sort((a, b) => a.i - b.i);
    const resolved = chosen.map(c => ({
      phrase: c.phrase, resolved: c.hit.prefLabel, uri: c.hit.id,
      notation: c.hit.notation || null, score: c.hit.score }));
    // Tell "redundant" (its meaning was already captured by another word mapping
    // to the SAME term, e.g. "leaflet" -> the same Folded Sheet Setup as "folded")
    // apart from words with no match at all ("unresolved").
    const wordHit = new Array(words.length).fill(null);
    for (const h of hits) if (h && h.n === 1) wordHit[h.i] = h.hit;
    const redundant = [], unresolved = [];
    words.forEach((w, k) => {
      if (used[k]) return;
      if (wordHit[k] && seenUri.has(wordHit[k].id)) redundant.push(w);
      else unresolved.push(w);
    });
    document.getElementById("meta").textContent =
      resolved.length + " attribute(s) resolved · " + cands.length + " lookups · ptpge_search_terms";
    LAST_RESOLVE = { resolved: resolved, numbers: numbers, raw: raw, productFallback: productFallback };
    document.getElementById("fpassemble").style.display = resolved.length ? "" : "none";
    render({
      prompt: raw,
      resolved_attributes: resolved,
      numeric_or_layer2: numbers.length ? numbers : undefined,
      redundant_words: redundant.length ? redundant : undefined,
      unresolved_words: unresolved.length ? unresolved : undefined,
      note: "Greedy non-overlapping n-gram resolution (the demo's stand-in for an LLM). 'redundant_words' already map to a term captured via another word (e.g. 'leaflet' -> the same Folded Sheet Setup as 'folded'). A real agent assembles these URIs into a validated, fingerprinted configuration; numbers like quantity/weight are Layer 2 / numeric axes.",
    });
  } finally {
    buttons.forEach(b => b.disabled = false);
  }
}

let LAST_RESOLVE = null;
// Heuristic assembly (v1): URI-path -> variable. A real agent does this with
// the envelope; this is the demo's stand-in so free text reaches the mark+QR.
const VAR_MAP = [
  ["/configurations/formats/",      "variables/configuration/format"],
  ["/configurations/setup-models/", "variables/configuration/setup-model"],
  ["/features/colors/",             "variables/features/color-mode"],
  ["/paper-surfaces/",              "variables/substrate/substrate-finish"],
  ["/paper-weights/",               "variables/substrate/substrate-weight"],
  ["/laminations/",                 "variables/features/lamination"],
  ["/substrates/",                  "variables/substrate/substrate-type"],
];
function assembleFingerprint() {
  if (!LAST_RESOLVE) return;
  const rel = u => u.replace("https://ptpge.org/v1/", "");
  let product = null; const bindings = []; const skipped = [];
  for (const r of LAST_RESOLVE.resolved) {
    const u = rel(r.uri);
    if (u.indexOf("ordering/products/") === 0) { if (!product) product = u; continue; }
    let mapped = null;
    for (const [frag, v] of VAR_MAP) if (u.indexOf(frag) !== -1) { mapped = v; break; }
    if (mapped) bindings.push({ variable: mapped, value: u });
    else skipped.push(r.resolved + " (" + u + ")");
  }
  const raw = (LAST_RESOLVE.raw || "").toLowerCase();
  const nums = (LAST_RESOLVE.numbers || []).map(x => parseInt(x, 10)).filter(n => !isNaN(n));
  const qty = nums.filter(n => n >= 25).sort((a, b) => b - a)[0];
  if (qty) bindings.push({ variable: "variables/order/quantity", value: qty });
  if (/\b(page|pages|pp|sider)\b/.test(raw)) {
    const pc = nums.filter(n => n >= 2 && n <= 96 && n !== qty)[0];
    if (pc) bindings.push({ variable: "variables/configuration/page-count", value: pc });
  }
  if (/gsm/.test(raw)) {
    const w = nums.filter(n => n >= 40 && n <= 600 && n !== qty)[0];
    if (w) bindings.push({ variable: "variables/substrate/substrate-weight", value: w });
  }
  let prodNote = "";
  if (!product && LAST_RESOLVE.productFallback) {
    product = rel(LAST_RESOLVE.productFallback.id);
    prodNote = " · product inferred: " + LAST_RESOLVE.productFallback.prefLabel +
               " (score " + LAST_RESOLVE.productFallback.score + ")";
  }
  if (!product) {
    render({ note: "No product recognised in the prompt — include a product word (labels, poster, brochure, business card …). Heuristic assembly needs one. (Steward note: if a common word like this SHOULD name a product, that is an altLabel proposal for the Standard.)" });
    return;
  }
  document.getElementById("meta").textContent =
    "heuristic assembly: " + product + " + " + bindings.length + " binding(s)" + prodNote +
    (skipped.length ? " · not mapped: " + skipped.join(", ") : "") +
    " · an agent would assemble via the envelope — then ptpge_fingerprint(visuals)";
  callTool("ptpge_fingerprint", { product: product, bindings: bindings, visuals: true });
}
function doEnvelope()    { callTool("ptpge_get_product_envelope", { id_or_path: DEMO_PRODUCT }); }
function doValidate()    { callTool("ptpge_validate_config", { product: DEMO_PRODUCT, bindings: DEMO_BINDINGS }); }
function doFingerprint() { callTool("ptpge_fingerprint", { product: DEMO_PRODUCT, bindings: DEMO_BINDINGS, visuals: true }); }
function preset(v) { document.getElementById("q").value = v; doSearch(); }
function presetUri(v) { document.getElementById("uri").value = v; doGet(); }

document.getElementById("q").addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); });
document.getElementById("uri").addEventListener("keydown", e => { if (e.key === "Enter") doGet(); });

// ————— v2: convergence demo — the reference brochure in six languages —————
const REF_PRODUCT = "ordering/products/brochures";
const REF_ROWS = [
  ["variables/configuration/format",        null,      "printing/configurations/formats/a-series/a5"],
  ["variables/configuration/page-count",    null,      8],
  ["variables/configuration/setup-model",   null,      "printing/configurations/setup-models/folded-sheet/accordion-fold"],
  ["variables/features/color-mode",         "outside", "printing/features/colors/cmyk"],
  ["variables/features/color-mode",         "inside",  "printing/features/colors/black"],
  ["variables/features/surface-finish",     "outside", ["printing/features/surface-finish/lamination/matte",
                                                        "printing/features/embellishments/spot-uv-varnish"]],
  ["variables/substrate/substrate-type",    null,      "printing/substrates/sheet-materials/paper"],
  ["variables/substrate/substrate-weight",  null,      170],
  ["variables/order/quantity",              null,      500],
];
function refBindings() {
  return REF_ROWS.map(r => {
    const b = { variable: r[0] };
    if (r[1]) b.surface = r[1];
    if (Array.isArray(r[2])) { b.values = r[2]; b.ordered = true; } else { b.value = r[2]; }
    return b;
  });
}
const CONV = [
  { code: "en", label: "English",
    phrase: "brochure, A5, accordion fold, 8 pages, 170 gsm paper, full colour outside, black only inside, matte lamination with spot UV outside, 500 copies",
    m: ["A5", "8 pages", "accordion fold", "full colour outside", "black only inside",
        "matte lamination with spot UV", "paper", "170 gsm", "500 copies"] },
  { code: "nb", label: "Norsk",
    phrase: "brosjyre, A5, trekkspillfals, 8 sider, 170 g papir, full farge utvendig, kun sort innvendig, matt laminat med spot-UV utvendig, 500 eksemplarer",
    m: ["A5", "8 sider", "trekkspillfals", "full farge utvendig", "kun sort innvendig",
        "matt laminat med spot-UV", "papir", "170 g", "500 eksemplarer"] },
  { code: "de", label: "Deutsch",
    phrase: "Broschüre, A5, Leporellofalz, 8 Seiten, 170 g Papier, außen 4-farbig, innen nur schwarz, außen Mattlaminat mit partiellem UV-Lack, 500 Exemplare",
    m: ["A5", "8 Seiten", "Leporellofalz", "außen 4-farbig", "innen nur schwarz",
        "Mattlaminat mit partiellem UV-Lack", "Papier", "170 g", "500 Exemplare"] },
  { code: "es", label: "Español",
    phrase: "folleto, A5, plegado en acordeón, 8 páginas, papel de 170 g, exterior a todo color, interior solo negro, laminado mate con barniz UV selectivo, 500 ejemplares",
    m: ["A5", "8 páginas", "plegado en acordeón", "exterior a todo color", "interior solo negro",
        "laminado mate con barniz UV selectivo", "papel", "170 g", "500 ejemplares"] },
  { code: "ja", label: "日本語",
    phrase: "パンフレット、A5、蛇腹折り、8ページ、170gsm用紙、表面フルカラー、内側モノクロ、表面マットPP+スポットUV、500部",
    m: ["A5", "8ページ", "蛇腹折り", "表面フルカラー", "内側モノクロ",
        "マットPP+スポットUV", "用紙", "170gsm", "500部"] },
  { code: "zh-Hans", label: "中文",
    phrase: "宣传册，A5，风琴折，8页，170克纸张，外面四色，里面单黑，外面哑膜加局部UV，500份",
    m: ["A5", "8页", "风琴折", "外面四色", "里面单黑", "哑膜加局部UV", "纸张", "170克", "500份"] },
];
let CONV_HISTORY = [];

async function toolQ(name, args) {
  const { json } = await rpc("tools/call", { name: name, arguments: args });
  if (json.error) { throw new Error(json.error.message || "RPC error"); }
  return JSON.parse(json.result.content[0].text);
}
function escH(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;"); }

function convTT(key) {
  return (UI[CUR_LANG] && UI[CUR_LANG][key]) || UI.en[key] || key;
}
function convTglLabel() {
  const a = document.querySelector("#conv-tgl a");
  if (!a) return;
  const hidden = document.getElementById("conv-out").style.display === "none";
  a.textContent = hidden ? ("▼ " + convTT("b_exp")) : ("▲ " + convTT("b_col"));
}
function convToggle() {
  const o = document.getElementById("conv-out");
  o.style.display = (o.style.display === "none") ? "" : "none";
  convTglLabel();
}
async function convRun(idx) {
  const L = CONV[idx];
  document.querySelectorAll("#conv-btns button").forEach((b, i) =>
    b.classList.toggle("on", i === idx));
  document.getElementById("conv-out").style.display = "";
  document.getElementById("conv-tgl").style.display = "";
  convTglLabel();
  const out = document.getElementById("conv-out");
  const t = key => (UI[CUR_LANG] && UI[CUR_LANG][key]) || UI.en[key];
  out.innerHTML =
    '<div class="stage"><span class="slbl"><span class="num">01</span>' + t("s01") +
    ' <span class="lng">' + L.code + '</span></span>' +
    '<div class="mono">&quot;' + escH(L.phrase) + '&quot;</div></div>' +
    '<div id="cv2"></div><div id="cv3"></div><div id="cv4"></div><div id="cv5"></div>';
  // 02 — matched terms, labels fetched LIVE in the chosen language
  const uris = [];
  REF_ROWS.forEach(r => {
    if (Array.isArray(r[2])) { r[2].forEach(u => uris.push(u)); }
    else if (typeof r[2] === "string") { uris.push(r[2]); }
  });
  const labels = {};
  await Promise.all(uris.map(async u => {
    try {
      const p = await toolQ("ptpge_get_term", { id_or_path: u, language: L.code });
      labels[u] = p.label || p.prefLabel || u.split("/").pop();
    } catch (e) { labels[u] = u.split("/").pop(); }
  }));
  let rows = "";
  REF_ROWS.forEach((r, i) => {
    const axis = r[0].split("/").pop() + (r[1] ? "@" + r[1] : "");
    let canon;
    if (Array.isArray(r[2])) {
      canon = r[2].map(u => escH(labels[u])).join(" &gt; ");
    } else if (typeof r[2] === "string") {
      canon = escH(labels[r[2]]);
    } else { canon = String(r[2]); }
    rows += '<tr><td class="mono">' + axis + '</td><td class="ph">&quot;' + escH(L.m[i]) +
            '&quot;<span class="lng">' + L.code + '</span></td><td>&rarr; ' + canon + '</td></tr>';
  });
  document.getElementById("cv2").innerHTML =
    '<div class="stage"><span class="slbl"><span class="num">02</span>' + t("s02") +
    '<span class="tag">' + t("tag02") + '</span></span><table>' + rows + '</table></div>';
  // Fingerprint — LIVE, with visuals: the spec mark + QR complete the
  // trinity (hash for systems, QR for the camera, mark for the eye).
  // The offer MARK is deliberately absent — it belongs to a vendor
  // identity (mark/3), and the tool now omits it gracefully.
  const fp = await toolQ("ptpge_fingerprint", { product: REF_PRODUCT, bindings: refBindings(), visuals: true });
  const spec = fp.profiles.spec, offer = fp.profiles.offer;
  document.getElementById("cv3").innerHTML =
    '<div class="stage"><span class="slbl"><span class="num">03</span>' + t("s03") +
    '<span class="tag">ptpge-cfs/1</span></span><div class="mono" style="color:#555">' +
    escH(spec.canonical) + '</div></div>';
  document.getElementById("cv4").innerHTML =
    '<div class="stage"><span class="slbl"><span class="num">04</span>SHA-256' +
    '<span class="tag">' + t("tag04") + '</span></span><div class="mono">' + spec.sha256 + '</div></div>';
  document.getElementById("cv5").innerHTML =
    '<div class="stage"><span class="slbl"><span class="num">05</span>' + t("s05") + '</span>' +
    '<div style="display:flex;gap:22px;align-items:center;flex-wrap:wrap;margin-top:8px">' +
    (spec.markSvg ? '<div class="vis" style="width:88px">' + spec.markSvg + '</div>' : '') +
    (spec.qrSvg ? '<div class="vis" style="width:88px">' + spec.qrSvg + '</div>' : '') +
    '<div><div class="mono" style="font-size:17px;font-weight:700">' + spec.short + '</div>' +
    '<a href="' + spec.resolverUrl + '" target="_blank" rel="noopener">' + t("resolver") + '</a>' +
    '<div class="hint">offer (+ quantity): <span class="mono">' + offer.short +
    '</span> · <a href="' + offer.resolverUrl + '" target="_blank" rel="noopener">/f/…</a></div></div></div></div>';
  // history — convergence proof
  CONV_HISTORY.push({ label: L.label, code: L.code, spec: spec.short });
  const first = CONV_HISTORY[0].spec;
  document.getElementById("conv-hist").style.display = "";
  document.getElementById("conv-hist-t").innerHTML = CONV_HISTORY.map(h =>
    '<tr><td>' + h.label + ' <span class="lng">' + h.code + '</span></td>' +
    '<td class="fp">' + h.spec + '</td>' +
    '<td>' + (h.spec === first && CONV_HISTORY.length > 1 ? '<span class="same">= ' + t("same") + '</span>' : '') +
    '</td></tr>').join("");
}
document.getElementById("conv-btns").innerHTML = CONV.map((L, i) =>
  '<button onclick="convRun(' + i + ')">' + L.label + '</button>').join("");

// ————— v2: 13-language UI (same set as gutenlex.org) —————
const LANG_NAMES = [["en","English"],["de","Deutsch"],["nb","Norsk"],["nl","Nederlands"],
  ["sv","Svenska"],["da","Dansk"],["fi","Suomi"],["is","Íslenska"],["fr","Français"],
  ["pl","Polski"],["es","Español"],["ja","日本語"],["zh","中文"]];
let CUR_LANG = "en";
const UI = {
en: { s01:"Raw specification", s02:"Matched against the vocabulary",
  tag02:"pre-scripted — the agent's job", s03:"Canonical form", tag04:"deterministic function, not the model",
  s05:"Identity", live:"checked live", resolver:"resolves on the public register ↗",
  same:"same identity", "try":"Try:", b_col:"collapse", b_exp:"expand" },
de: { sub:"Jeder Button sendet einen echten MCP-<code>tools/call</code> (JSON-RPC über Streamable HTTP) an <code>/mcp</code> — genau wie ein KI-Agent.",
  t_conv:"Gleiches Produkt · jede Sprache · ein Fingerprint",
  i_conv:"Die Referenzbroschüre — A5, Leporellofalz, 8 Seiten, 170 g, außen farbig / innen schwarz, Mattlaminat mit partiellem UV-Lack — in sechs Sprachen formuliert. Wählen Sie eine und sehen Sie dieselbe Identität entstehen.",
  h_conv:"Die Interpretation (Worte → Bindings) ist hier pro Sprache vorbereitet — in Produktion die Aufgabe des KI-Agenten. Begriffe, Envelope-Validierung und der ptpge-cfs/1-Fingerprint laufen <em>live</em> gegen diesen Server. Der Hash ist eine deterministische Funktion, kein Modell-Output.",
  hist:"Verlauf — gleiches Produkt, verschiedene Sprachen",
  s01:"Rohe Spezifikation", s02:"Gegen das Vokabular aufgelöst", tag02:"vorbereitet — Aufgabe des Agenten",
  s03:"Kanonische Form", tag04:"deterministische Funktion, kein Modell", s05:"Identität",
  live:"live geprüft", resolver:"löst im öffentlichen Register auf ↗", same:"gleiche Identität",
  t_search:"ptpge_search_terms — Freitextsuche",
  h_search:"Die Suche ist tokenisiert und sprachunabhängig — Käuferphrasen in jeder unterstützten Sprache treffen die kanonischen Begriffe.", "try":"Beispiele:",
  t_get:"ptpge_get_term — voller Kontext eines Begriffs", h_get:"Tipp: eine <code>id</code> aus einer Suche anklicken, oder:",
  t_ver:"ptpge_get_version — Daten- &amp; Serverversion", b_ver:"Version abrufen",
  t_chain:"Test-Prompt — die volle Kette, live",
  h_chain:"Die Interpretation (Worte → Bindings) ist hier vorbereitet — das ist die Aufgabe des KI-Agenten. Lookups, Envelope-Validierung und der ptpge-cfs/1-Fingerprint laufen <em>live</em> gegen diesen Server.",
  t_own:"Ihr eigener Prompt — was löst sich auf?",
  h_own:"Ein echter Agent zerlegt den Prompt mit einem LLM; die Demo nähert das mit N-Gramm-Suchen an — jedes Fragment wird <em>live</em> nachgeschlagen.",
  b_search:"Suchen", b_get:"Begriff abrufen", b_resolve:"Phrasen auflösen", b_fp:"Fingerprint → Marke + QR", b_col:"einklappen", b_exp:"ausklappen" },
nb: { sub:"Hver knapp sender et ekte MCP-<code>tools/call</code> (JSON-RPC over Streamable HTTP) til <code>/mcp</code> — akkurat som en KI-agent.",
  t_conv:"Samme produkt · alle språk · ett fingerprint",
  i_conv:"Referansebrosjyren — A5, trekkspillfals, 8 sider, 170 g, farger utvendig / sort innvendig, matt laminat med spot-UV — formulert på seks språk. Velg ett og se samme identitet vokse frem.",
  h_conv:"Tolkningen (ord → bindings) er forhåndsskrevet per språk — det er KI-agentens jobb i produksjon. Termoppslag, envelope-validering og ptpge-cfs/1-fingerprintet kjører <em>live</em> mot denne serveren. Hashen er en deterministisk funksjon, ikke modell-output.",
  hist:"Kjørehistorikk — samme produkt, ulike språk",
  s01:"Rå spesifikasjon", s02:"Matchet mot vokabularet", tag02:"forhåndsskrevet — agentens jobb",
  s03:"Kanonisk form", tag04:"deterministisk funksjon, ikke modellen", s05:"Identitet",
  live:"sjekket live", resolver:"slår opp i det offentlige registeret ↗", same:"samme identitet",
  t_search:"ptpge_search_terms — fritekstsøk",
  h_search:"Søket er tokenisert og språkuavhengig — kjøperfraser på alle støttede språk treffer de kanoniske termene.", "try":"Prøv:",
  t_get:"ptpge_get_term — full kontekst for én term", h_get:"Tips: klikk en <code>id</code> fra et søk, eller prøv:",
  t_ver:"ptpge_get_version — data- og serverversjon", b_ver:"Hent versjon",
  t_chain:"Test-prompt — hele kjeden, live",
  h_chain:"Tolkningen (ord → bindings) er forhåndsskrevet her — det er KI-agentens jobb. Oppslag, envelope-validering og ptpge-cfs/1-fingerprintet kjører <em>live</em> mot denne serveren.",
  t_own:"Din egen prompt — se hva som løses",
  h_own:"En ekte agent dekomponerer prompten med en LLM; demoen tilnærmer det med n-gram-søk — hvert fragment slås opp <em>live</em>.",
  b_search:"Søk", b_get:"Hent term", b_resolve:"Løs opp fraser", b_fp:"Fingerprint → merke + QR", b_col:"skjul", b_exp:"vis" },
nl: { sub:"Elke knop stuurt een echte MCP-<code>tools/call</code> (JSON-RPC over Streamable HTTP) naar <code>/mcp</code> — precies wat een AI-agent doet.",
  t_conv:"Zelfde product · elke taal · één fingerprint",
  i_conv:"De referentiebrochure — A5, leporellovouw, 8 pagina's, 170 g, kleur buiten / zwart binnen, matlaminaat met spot-UV — in zes talen. Kies er één en zie dezelfde identiteit ontstaan.",
  h_conv:"De interpretatie (woorden → bindings) is per taal voorbereid — in productie het werk van de AI-agent. Termen, envelope-validatie en de ptpge-cfs/1-fingerprint draaien <em>live</em> tegen deze server. De hash is een deterministische functie, geen modeloutput.",
  hist:"Geschiedenis — zelfde product, verschillende talen",
  s01:"Ruwe specificatie", s02:"Gematcht met het vocabulaire", tag02:"voorbereid — het werk van de agent",
  s03:"Canonieke vorm", tag04:"deterministische functie, niet het model", s05:"Identiteit",
  live:"live gecontroleerd", resolver:"lost op in het openbare register ↗", same:"zelfde identiteit",
  t_search:"ptpge_search_terms — vrije-tekst zoeken",
  h_search:"Zoeken is getokeniseerd en taalonafhankelijk — koperszinnen in elke ondersteunde taal raken de canonieke termen.", "try":"Probeer:",
  t_get:"ptpge_get_term — volledige context van één term", h_get:"Tip: klik een <code>id</code> uit een zoekopdracht, of probeer:",
  t_ver:"ptpge_get_version — data- &amp; serverversie", b_ver:"Versie ophalen",
  t_chain:"Test-prompt — de volledige keten, live",
  h_chain:"De interpretatie (woorden → bindings) is hier voorbereid — dat is het werk van de AI-agent. Lookups, envelope-validatie en de ptpge-cfs/1-fingerprint draaien <em>live</em> tegen deze server.",
  t_own:"Uw eigen prompt — zie wat er oplost",
  h_own:"Een echte agent ontleedt de prompt met een LLM; de demo benadert dat met n-gram-zoekopdrachten — elk fragment wordt <em>live</em> opgezocht.",
  b_search:"Zoeken", b_get:"Term ophalen", b_resolve:"Zinnen oplossen", b_fp:"Fingerprint → merk + QR", b_col:"inklappen", b_exp:"uitklappen" },
sv: { sub:"Varje knapp skickar ett äkta MCP-<code>tools/call</code> (JSON-RPC över Streamable HTTP) till <code>/mcp</code> — precis som en AI-agent.",
  t_conv:"Samma produkt · alla språk · ett fingerprint",
  i_conv:"Referensbroschyren — A5, leporellofals, 8 sidor, 170 g, färg utsida / svart insida, mattlaminat med spot-UV — formulerad på sex språk. Välj ett och se samma identitet växa fram.",
  h_conv:"Tolkningen (ord → bindings) är förskriven per språk — i produktion agentens jobb. Termuppslag, envelope-validering och ptpge-cfs/1-fingerprintet körs <em>live</em> mot denna server. Hashen är en deterministisk funktion, inte modelloutput.",
  hist:"Körhistorik — samma produkt, olika språk",
  s01:"Rå specifikation", s02:"Matchad mot vokabulären", tag02:"förskriven — agentens jobb",
  s03:"Kanonisk form", tag04:"deterministisk funktion, inte modellen", s05:"Identitet",
  live:"kontrollerad live", resolver:"slås upp i det offentliga registret ↗", same:"samma identitet",
  t_search:"ptpge_search_terms — fritextsökning",
  h_search:"Sökningen är tokeniserad och språkoberoende — köparfraser på alla stödda språk träffar de kanoniska termerna.", "try":"Prova:",
  t_get:"ptpge_get_term — full kontext för en term", h_get:"Tips: klicka en <code>id</code> från en sökning, eller prova:",
  t_ver:"ptpge_get_version — data- och serverversion", b_ver:"Hämta version",
  t_chain:"Test-prompt — hela kedjan, live",
  h_chain:"Tolkningen (ord → bindings) är förskriven här — det är AI-agentens jobb. Uppslag, envelope-validering och ptpge-cfs/1-fingerprintet körs <em>live</em> mot denna server.",
  t_own:"Din egen prompt — se vad som löses upp",
  h_own:"En riktig agent bryter ner prompten med en LLM; demon approximerar det med n-gram-sökningar — varje fragment slås upp <em>live</em>.",
  b_search:"Sök", b_get:"Hämta term", b_resolve:"Lös upp fraser", b_fp:"Fingerprint → märke + QR", b_col:"fäll ihop", b_exp:"fäll ut" },
da: { sub:"Hver knap sender et ægte MCP-<code>tools/call</code> (JSON-RPC over Streamable HTTP) til <code>/mcp</code> — præcis som en AI-agent.",
  t_conv:"Samme produkt · alle sprog · ét fingerprint",
  i_conv:"Referencebrochuren — A5, leporellofals, 8 sider, 170 g, farve udvendig / sort indvendig, matlaminat med spot-UV — formuleret på seks sprog. Vælg ét og se den samme identitet opstå.",
  h_conv:"Fortolkningen (ord → bindings) er forberedt pr. sprog — i produktion agentens job. Termopslag, envelope-validering og ptpge-cfs/1-fingerprintet kører <em>live</em> mod denne server. Hashen er en deterministisk funktion, ikke modeloutput.",
  hist:"Kørselshistorik — samme produkt, forskellige sprog",
  s01:"Rå specifikation", s02:"Matchet mod vokabularet", tag02:"forberedt — agentens job",
  s03:"Kanonisk form", tag04:"deterministisk funktion, ikke modellen", s05:"Identitet",
  live:"tjekket live", resolver:"slår op i det offentlige register ↗", same:"samme identitet",
  t_search:"ptpge_search_terms — fritekstsøgning",
  h_search:"Søgningen er tokeniseret og sproguafhængig — køberfraser på alle understøttede sprog rammer de kanoniske termer.", "try":"Prøv:",
  t_get:"ptpge_get_term — fuld kontekst for én term", h_get:"Tip: klik et <code>id</code> fra en søgning, eller prøv:",
  t_ver:"ptpge_get_version — data- og serverversion", b_ver:"Hent version",
  t_chain:"Test-prompt — hele kæden, live",
  h_chain:"Fortolkningen (ord → bindings) er forberedt her — det er AI-agentens job. Opslag, envelope-validering og ptpge-cfs/1-fingerprintet kører <em>live</em> mod denne server.",
  t_own:"Din egen prompt — se hvad der løses",
  h_own:"En rigtig agent nedbryder prompten med en LLM; demoen tilnærmer det med n-gram-søgninger — hvert fragment slås op <em>live</em>.",
  b_search:"Søg", b_get:"Hent term", b_resolve:"Opløs fraser", b_fp:"Fingerprint → mærke + QR", b_col:"fold sammen", b_exp:"fold ud" },
fi: { sub:"Jokainen painike lähettää aidon MCP-<code>tools/call</code>-kutsun (JSON-RPC, Streamable HTTP) osoitteeseen <code>/mcp</code> — täsmälleen kuten tekoälyagentti.",
  t_conv:"Sama tuote · kaikki kielet · yksi sormenjälki",
  i_conv:"Referenssiesite — A5, haitaritaitto, 8 sivua, 170 g, värit ulkopuolella / musta sisällä, mattalaminointi ja kohde-UV — kuudella kielellä. Valitse yksi ja katso saman identiteetin syntyvän.",
  h_conv:"Tulkinta (sanat → sidonnat) on ennalta kirjoitettu kielittäin — tuotannossa se on agentin työ. Termihaut, envelope-validointi ja ptpge-cfs/1-sormenjälki ajetaan <em>live</em> tätä palvelinta vasten. Hash on deterministinen funktio, ei mallin tuotos.",
  hist:"Ajohistoria — sama tuote, eri kielet",
  s01:"Raaka spesifikaatio", s02:"Sovitettu sanastoon", tag02:"ennalta kirjoitettu — agentin työ",
  s03:"Kanoninen muoto", tag04:"deterministinen funktio, ei malli", s05:"Identiteetti",
  live:"tarkistettu live", resolver:"ratkeaa julkisessa rekisterissä ↗", same:"sama identiteetti",
  t_search:"ptpge_search_terms — vapaatekstihaku",
  h_search:"Haku on tokenisoitu ja kieliriippumaton — ostajan fraasit kaikilla tuetuilla kielillä osuvat kanonisiin termeihin.", "try":"Kokeile:",
  t_get:"ptpge_get_term — yhden termin koko konteksti", h_get:"Vinkki: napsauta <code>id</code> hakutuloksesta, tai kokeile:",
  t_ver:"ptpge_get_version — data- ja palvelinversio", b_ver:"Hae versio",
  t_chain:"Testikehote — koko ketju, live",
  h_chain:"Tulkinta (sanat → sidonnat) on ennalta kirjoitettu — se on agentin työ. Haut, envelope-validointi ja ptpge-cfs/1-sormenjälki ajetaan <em>live</em> tätä palvelinta vasten.",
  t_own:"Oma kehotteesi — katso mikä ratkeaa",
  h_own:"Oikea agentti purkaa kehotteen LLM:llä; demo approksimoi sen n-grammihauilla — jokainen fragmentti haetaan <em>live</em>.",
  b_search:"Hae", b_get:"Hae termi", b_resolve:"Ratkaise fraasit", b_fp:"Sormenjälki → merkki + QR", b_col:"pienennä", b_exp:"laajenna" },
is: { sub:"Hver hnappur sendir ekta MCP-<code>tools/call</code> (JSON-RPC yfir Streamable HTTP) á <code>/mcp</code> — nákvæmlega eins og gervigreindarfulltrúi.",
  t_conv:"Sama vara · öll tungumál · eitt fingrafar",
  i_conv:"Viðmiðunarbæklingurinn — A5, harmonikubrot, 8 síður, 170 g, litur að utan / svart að innan, matt lagskipting með stað-UV — orðaður á sex tungumálum. Veldu eitt og sjáðu sömu auðkenni verða til.",
  h_conv:"Túlkunin (orð → bindingar) er fyrirfram skrifuð fyrir hvert tungumál — í framleiðslu er það verk fulltrúans. Hugtakauppflettingar, envelope-staðfesting og ptpge-cfs/1-fingrafarið keyra <em>live</em> gegn þessum þjóni. Hashið er deterministískt fall, ekki líkansútkoma.",
  hist:"Keyrslusaga — sama vara, ólík tungumál",
  s01:"Hrá forskrift", s02:"Parað við orðaforðann", tag02:"fyrirfram skrifað — verk fulltrúans",
  s03:"Kanónískt form", tag04:"deterministískt fall, ekki líkanið", s05:"Auðkenni",
  live:"staðfest live", resolver:"flettist upp í opinberu skránni ↗", same:"sama auðkenni",
  t_search:"ptpge_search_terms — frjáls textaleit",
  h_search:"Leitin er tókuð og tungumálaóháð — orðalag kaupanda á öllum studdum tungumálum hittir kanónísku hugtökin.", "try":"Prófaðu:",
  t_get:"ptpge_get_term — allt samhengi eins hugtaks", h_get:"Ábending: smelltu á <code>id</code> úr leit, eða prófaðu:",
  t_ver:"ptpge_get_version — gagna- og þjónsútgáfa", b_ver:"Sækja útgáfu",
  t_chain:"Prufuskipun — öll keðjan, live",
  h_chain:"Túlkunin (orð → bindingar) er fyrirfram skrifuð hér — það er verk fulltrúans. Uppflettingar, envelope-staðfesting og ptpge-cfs/1-fingrafarið keyra <em>live</em> gegn þessum þjóni.",
  t_own:"Þín eigin skipun — sjáðu hvað leysist",
  h_own:"Alvöru fulltrúi brýtur skipunina niður með LLM; sýnidæmið nálgast það með n-gramma leit — hvert brot er flett upp <em>live</em>.",
  b_search:"Leita", b_get:"Sækja hugtak", b_resolve:"Leysa orðalag", b_fp:"Fingrafar → merki + QR", b_col:"fella saman", b_exp:"opna" },
fr: { sub:"Chaque bouton envoie un vrai <code>tools/call</code> MCP (JSON-RPC sur Streamable HTTP) vers <code>/mcp</code> — exactement comme un agent IA.",
  t_conv:"Même produit · toutes les langues · une empreinte",
  i_conv:"La brochure de référence — A5, pli accordéon, 8 pages, 170 g, couleur à l'extérieur / noir à l'intérieur, pelliculage mat avec vernis UV sélectif — formulée en six langues. Choisissez-en une et regardez la même identité émerger.",
  h_conv:"L'interprétation (mots → liaisons) est pré-écrite par langue — en production, c'est le travail de l'agent IA. Les termes, la validation d'enveloppe et l'empreinte ptpge-cfs/1 s'exécutent <em>en direct</em> sur ce serveur. Le hash est une fonction déterministe, pas une sortie de modèle.",
  hist:"Historique — même produit, langues différentes",
  s01:"Spécification brute", s02:"Résolue contre le vocabulaire", tag02:"pré-écrit — le travail de l'agent",
  s03:"Forme canonique", tag04:"fonction déterministe, pas le modèle", s05:"Identité",
  live:"vérifié en direct", resolver:"se résout dans le registre public ↗", same:"même identité",
  t_search:"ptpge_search_terms — recherche en texte libre",
  h_search:"La recherche est tokenisée et indépendante de la langue — les phrases d'acheteur dans toute langue prise en charge atteignent les termes canoniques.", "try":"Essayez :",
  t_get:"ptpge_get_term — contexte complet d'un terme", h_get:"Astuce : cliquez un <code>id</code> d'une recherche, ou essayez :",
  t_ver:"ptpge_get_version — version des données &amp; du serveur", b_ver:"Obtenir la version",
  t_chain:"Prompt de test — la chaîne complète, en direct",
  h_chain:"L'interprétation (mots → liaisons) est pré-écrite ici — c'est le travail de l'agent IA. Les recherches, la validation d'enveloppe et l'empreinte ptpge-cfs/1 s'exécutent <em>en direct</em> sur ce serveur.",
  t_own:"Votre propre prompt — voyez ce qui se résout",
  h_own:"Un vrai agent décompose le prompt avec un LLM ; la démo l'approxime par recherches n-grammes — chaque fragment est résolu <em>en direct</em>.",
  b_search:"Rechercher", b_get:"Obtenir le terme", b_resolve:"Résoudre les phrases", b_fp:"Empreinte → marque + QR", b_col:"replier", b_exp:"déplier" },
pl: { sub:"Każdy przycisk wysyła prawdziwe MCP-<code>tools/call</code> (JSON-RPC przez Streamable HTTP) do <code>/mcp</code> — dokładnie jak agent AI.",
  t_conv:"Ten sam produkt · każdy język · jeden odcisk",
  i_conv:"Broszura referencyjna — A5, składanie harmonijkowe, 8 stron, 170 g, kolor na zewnątrz / czerń wewnątrz, laminat matowy z lakierem UV wybiórczym — sformułowana w sześciu językach. Wybierz jeden i zobacz, jak wyłania się ta sama tożsamość.",
  h_conv:"Interpretacja (słowa → powiązania) jest przygotowana per język — w produkcji to zadanie agenta AI. Terminy, walidacja envelope i odcisk ptpge-cfs/1 działają <em>na żywo</em> na tym serwerze. Hash to funkcja deterministyczna, nie wynik modelu.",
  hist:"Historia — ten sam produkt, różne języki",
  s01:"Surowa specyfikacja", s02:"Dopasowana do słownika", tag02:"przygotowane — zadanie agenta",
  s03:"Forma kanoniczna", tag04:"funkcja deterministyczna, nie model", s05:"Tożsamość",
  live:"sprawdzone na żywo", resolver:"rozwiązuje się w publicznym rejestrze ↗", same:"ta sama tożsamość",
  t_search:"ptpge_search_terms — wyszukiwanie pełnotekstowe",
  h_search:"Wyszukiwanie jest tokenizowane i niezależne od języka — frazy kupującego w każdym obsługiwanym języku trafiają w terminy kanoniczne.", "try":"Wypróbuj:",
  t_get:"ptpge_get_term — pełny kontekst jednego terminu", h_get:"Wskazówka: kliknij <code>id</code> z wyników, albo wypróbuj:",
  t_ver:"ptpge_get_version — wersja danych i serwera", b_ver:"Pobierz wersję",
  t_chain:"Prompt testowy — pełny łańcuch, na żywo",
  h_chain:"Interpretacja (słowa → powiązania) jest tu przygotowana — to zadanie agenta AI. Wyszukiwania, walidacja envelope i odcisk ptpge-cfs/1 działają <em>na żywo</em> na tym serwerze.",
  t_own:"Twój własny prompt — zobacz, co się rozwiązuje",
  h_own:"Prawdziwy agent rozkłada prompt przy użyciu LLM; demo przybliża to wyszukiwaniami n-gramów — każdy fragment jest sprawdzany <em>na żywo</em>.",
  b_search:"Szukaj", b_get:"Pobierz termin", b_resolve:"Rozwiąż frazy", b_fp:"Odcisk → znak + QR", b_col:"zwiń", b_exp:"rozwiń" },
es: { sub:"Cada botón envía un <code>tools/call</code> MCP real (JSON-RPC sobre Streamable HTTP) a <code>/mcp</code> — exactamente lo que hace un agente de IA.",
  t_conv:"Mismo producto · cualquier idioma · una huella",
  i_conv:"El folleto de referencia — A5, plegado en acordeón, 8 páginas, 170 g, color por fuera / negro por dentro, laminado mate con barniz UV selectivo — formulado en seis idiomas. Elija uno y vea emerger la misma identidad.",
  h_conv:"La interpretación (palabras → vínculos) está preescrita por idioma — en producción es trabajo del agente de IA. Los términos, la validación de envelope y la huella ptpge-cfs/1 se ejecutan <em>en vivo</em> contra este servidor. El hash es una función determinista, no salida de un modelo.",
  hist:"Historial — mismo producto, idiomas distintos",
  s01:"Especificación en bruto", s02:"Resuelta contra el vocabulario", tag02:"preescrito — trabajo del agente",
  s03:"Forma canónica", tag04:"función determinista, no el modelo", s05:"Identidad",
  live:"verificado en vivo", resolver:"se resuelve en el registro público ↗", same:"misma identidad",
  t_search:"ptpge_search_terms — búsqueda de texto libre",
  h_search:"La búsqueda está tokenizada y es independiente del idioma — las frases del comprador en cualquier idioma soportado alcanzan los términos canónicos.", "try":"Pruebe:",
  t_get:"ptpge_get_term — contexto completo de un término", h_get:"Consejo: haga clic en un <code>id</code> de una búsqueda, o pruebe:",
  t_ver:"ptpge_get_version — versión de datos y servidor", b_ver:"Obtener versión",
  t_chain:"Prompt de prueba — la cadena completa, en vivo",
  h_chain:"La interpretación (palabras → vínculos) está preescrita aquí — es trabajo del agente de IA. Las búsquedas, la validación de envelope y la huella ptpge-cfs/1 se ejecutan <em>en vivo</em> contra este servidor.",
  t_own:"Su propio prompt — vea qué se resuelve",
  h_own:"Un agente real descompone el prompt con un LLM; la demo lo aproxima con búsquedas de n-gramas — cada fragmento se consulta <em>en vivo</em>.",
  b_search:"Buscar", b_get:"Obtener término", b_resolve:"Resolver frases", b_fp:"Huella → marca + QR", b_col:"contraer", b_exp:"expandir" },
ja: { sub:"各ボタンは本物のMCP <code>tools/call</code>（Streamable HTTP上のJSON-RPC）を<code>/mcp</code>に送信します — AIエージェントの動作そのものです。",
  t_conv:"同じ製品 · どの言語でも · ひとつのフィンガープリント",
  i_conv:"リファレンスパンフレット — A5、蛇腹折り、8ページ、170g、表面カラー／内側モノクロ、マットPP+スポットUV — を6言語で表現。ひとつ選んで、同じアイデンティティが現れるのをご覧ください。",
  h_conv:"解釈（言葉 → バインディング）は言語ごとに事前定義 — 本番ではAIエージェントの仕事です。用語参照、envelope検証、ptpge-cfs/1フィンガープリントはこのサーバーで<em>ライブ</em>実行。ハッシュは決定的関数であり、モデルの出力ではありません。",
  hist:"実行履歴 — 同じ製品、異なる言語",
  s01:"元の仕様", s02:"語彙とのマッチング", tag02:"事前定義 — エージェントの仕事",
  s03:"正規形", tag04:"決定的関数（モデルではない）", s05:"アイデンティティ",
  live:"ライブ検証済み", resolver:"公開レジストリで解決 ↗", same:"同一アイデンティティ",
  t_search:"ptpge_search_terms — フリーテキスト検索",
  h_search:"検索はトークン化され言語非依存 — 対応言語の購買者フレーズが正規の用語にヒットします。", "try":"例：",
  t_get:"ptpge_get_term — 用語の完全なコンテキスト", h_get:"ヒント：検索結果の<code>id</code>をクリック、または：",
  t_ver:"ptpge_get_version — データ＆サーバーバージョン", b_ver:"バージョン取得",
  t_chain:"テストプロンプト — 全チェーン、ライブ",
  h_chain:"解釈（言葉 → バインディング）はここでは事前定義 — それがAIエージェントの仕事です。参照、envelope検証、ptpge-cfs/1フィンガープリントはこのサーバーで<em>ライブ</em>実行されます。",
  t_own:"自分のプロンプト — 何が解決されるか",
  h_own:"実際のエージェントはLLMでプロンプトを分解します。デモはn-gram検索で近似 — 各フラグメントを<em>ライブ</em>で照会します。",
  b_search:"検索", b_get:"用語取得", b_resolve:"フレーズを解決", b_fp:"フィンガープリント → マーク + QR", b_col:"折りたたむ", b_exp:"展開" },
zh: { sub:"每个按钮都会向 <code>/mcp</code> 发送真实的 MCP <code>tools/call</code>（基于 Streamable HTTP 的 JSON-RPC）— 与 AI 智能体的行为完全一致。",
  t_conv:"同一产品 · 任何语言 · 一个指纹",
  i_conv:"参考宣传册 — A5、风琴折、8页、170克、外面彩色／里面单黑、哑膜加局部UV — 用六种语言表述。选择一种，看同一身份如何呈现。",
  h_conv:"解释（词语 → 绑定）按语言预先编写 — 在生产中这是 AI 智能体的工作。术语查询、envelope 验证和 ptpge-cfs/1 指纹在此服务器上<em>实时</em>运行。哈希是确定性函数，不是模型输出。",
  hist:"运行历史 — 同一产品，不同语言",
  s01:"原始规格", s02:"与词汇表匹配", tag02:"预先编写 — 智能体的工作",
  s03:"规范形式", tag04:"确定性函数，非模型", s05:"身份",
  live:"实时验证", resolver:"在公共注册表中解析 ↗", same:"同一身份",
  t_search:"ptpge_search_terms — 自由文本搜索",
  h_search:"搜索经过分词且与语言无关 — 任何受支持语言的买家用语都能命中规范术语。", "try":"试试：",
  t_get:"ptpge_get_term — 单个术语的完整上下文", h_get:"提示：点击搜索结果中的 <code>id</code>，或试试：",
  t_ver:"ptpge_get_version — 数据与服务器版本", b_ver:"获取版本",
  t_chain:"测试提示 — 完整链路，实时",
  h_chain:"解释（词语 → 绑定）在此预先编写 — 那是 AI 智能体的工作。查询、envelope 验证和 ptpge-cfs/1 指纹在此服务器上<em>实时</em>运行。",
  t_own:"你自己的提示 — 看看能解析出什么",
  h_own:"真正的智能体用 LLM 分解提示；演示用 n-gram 搜索近似 — 每个片段都<em>实时</em>查询。",
  b_search:"搜索", b_get:"获取术语", b_resolve:"解析短语", b_fp:"指纹 → 标记 + QR", b_col:"收起", b_exp:"展开" },
};
const _EN_DEFAULTS = {};
function setLang(l) {
  CUR_LANG = l;
  document.querySelectorAll("[data-i]").forEach(el => {
    const k = el.getAttribute("data-i");
    if (!(k in _EN_DEFAULTS)) _EN_DEFAULTS[k] = el.innerHTML;
    const d = UI[l] || {};
    el.innerHTML = (l !== "en" && d[k]) ? d[k] : _EN_DEFAULTS[k];
  });
  document.documentElement.lang = l;
  if (typeof convTglLabel === "function") convTglLabel();
  try { localStorage.setItem("ptpge-playground-lang", l); } catch (e) {}
  const sel = document.getElementById("ui-lang");
  if (sel && sel.value !== l) sel.value = l;
}
(function initLang() {
  const sel = document.getElementById("ui-lang");
  sel.innerHTML = LANG_NAMES.map(p => '<option value="' + p[0] + '">' + p[1] + '</option>').join("");
  let l = new URLSearchParams(location.search).get("lang");
  if (!l) { try { l = localStorage.getItem("ptpge-playground-lang"); } catch (e) {} }
  if (l && (l === "en" || UI[l])) setLang(l); else setLang("en");
})();

// On load: real MCP handshake (initialize) + version — shows liveness in the header.
(async () => {
  try {
    const init = await rpc("initialize", {
      protocolVersion: "2025-06-18", capabilities: {},
      clientInfo: { name: "ptpge-playground", version: "1.0" },
    });
    const v = await rpc("tools/call", { name: "ptpge_get_version", arguments: {} });
    const payload = JSON.parse(v.json.result.content[0].text);
    document.getElementById("status").innerHTML =
      `connected · server <b>${init.json.result.serverInfo.version}</b> · data <b>${payload.dataVersion}</b> · ${payload.termsTotal} terms`;
  } catch (e) {
    document.getElementById("status").textContent = "could not reach /mcp — " + e +
      (_tok ? "" : " (tip: if tokens are required, open /playground?t=YOUR_TOKEN from your welcome email)");
  }
})();
</script>
</body>
</html>
"""
