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
</style>
</head>
<body>
<header>
  <h1>PTPGE MCP — Playground <span class="badge">LIVE</span></h1>
  <div class="sub">Every button below sends a real MCP <code>tools/call</code> (JSON-RPC over
  Streamable HTTP) to <code>/mcp</code> on this server — exactly what an AI agent does.
  <span id="status">connecting…</span></div>
</header>
<main>

<div class="card">
  <h2>ptpge_search_terms — free-text search</h2>
  <div class="row">
    <input type="text" id="q" placeholder="e.g. brochure · accordion fold · ivory paper · full colour · copies" value="brochure">
    <select id="q-lang">
      <option value="en" selected>en</option><option value="nb">nb</option>
      <option value="de">de</option><option value="ja">ja</option>
      <option value="es">es</option><option value="zh-Hans">zh-Hans</option>
    </select>
    <button onclick="doSearch()">Search</button>
  </div>
  <div class="hint">Search is tokenized and language-agnostic — buyer phrases in any
  supported language hit the canonical terms. Try:
  <a onclick="preset('ivory paper')">ivory paper</a> ·
  <a onclick="preset('black only')">black only</a> ·
  <a onclick="preset('accordion fold')">accordion fold</a> ·
  <a onclick="preset('creasing')">creasing</a> ·
  <a onclick="preset('gold foil')">gold foil</a></div>
</div>

<div class="card">
  <h2>ptpge_get_term — full context for one term</h2>
  <div class="row">
    <input type="text" id="uri" placeholder="URI or path under /v1/"
           value="printing/completions/folding">
    <select id="t-lang">
      <option value="en" selected>en</option><option value="nb">nb</option>
      <option value="de">de</option><option value="ja">ja</option>
      <option value="es">es</option><option value="zh-Hans">zh-Hans</option>
    </select>
    <button onclick="doGet()">Get term</button>
  </div>
  <div class="hint">Tip: click a result <code>id</code> from a search, or try
  <a onclick="presetUri('ordering/products/brochures')">brochures</a> ·
  <a onclick="presetUri('printing/substrates/sheet-materials/paper/paper-weights/medium-paper')">medium-paper</a> ·
  <a onclick="presetUri('variables/order/quantity')">quantity</a></div>
</div>

<div class="card">
  <h2>ptpge_get_version — dataset &amp; server version</h2>
  <div class="row"><button onclick="doVersion()">Get version</button></div>
</div>

<div class="card">
  <h2>Test-prompt demo — the full chain, live</h2>
  <p style="font-size:13px;color:#555;margin:0 0 10px;font-style:italic">
  "I want a brochure, 6 pages, A5, folded as a Z-fold, on ivory-toned
  heavy paper, full colour on one side and black only on the other, 500 copies."</p>
  <div class="row">
    <button onclick="doEnvelope()">1 · Envelope</button>
    <button onclick="doValidate()">2 · Validate</button>
    <button onclick="doFingerprint()">3 · Fingerprint</button>
  </div>
  <div class="hint">The interpretation (words → bindings) is pre-scripted here — that is
  the AI agent's job. The lookups, envelope validation (incl. 250 gsm → weight band and
  the creasing advisory) and the ptpge-cfs/1 fingerprint run <em>live</em> against this
  server, exactly as an agent would call them.</div>
</div>

<div class="card">
  <h2>Your own prompt — see what resolves</h2>
  <textarea id="prompt" rows="3" style="width:100%;padding:10px 12px;border:1px solid #ccc;border-radius:7px;font-size:14px;font-family:inherit;resize:vertical" placeholder="Describe a print job in your own words, any language…">I want a folded leaflet on heavy recycled paper, matte lamination, full colour both sides, A4, 1000 copies</textarea>
  <div class="row" style="margin-top:10px"><button onclick="doResolve()">Resolve phrases</button></div>
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
        return r ? { i: c.i, n: c.n, phrase: c.phrase, hit: r } : null;
      } catch (e) { return null; }
    }));
    const ranked = hits.filter(Boolean).sort((a, b) => (b.hit.score - a.hit.score) || (b.n - a.n));
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

function doEnvelope()    { callTool("ptpge_get_product_envelope", { id_or_path: DEMO_PRODUCT }); }
function doValidate()    { callTool("ptpge_validate_config", { product: DEMO_PRODUCT, bindings: DEMO_BINDINGS }); }
function doFingerprint() { callTool("ptpge_fingerprint", { product: DEMO_PRODUCT, bindings: DEMO_BINDINGS, visuals: true }); }
function preset(v) { document.getElementById("q").value = v; doSearch(); }
function presetUri(v) { document.getElementById("uri").value = v; doGet(); }

document.getElementById("q").addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); });
document.getElementById("uri").addEventListener("keydown", e => { if (e.key === "Enter") doGet(); });

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
