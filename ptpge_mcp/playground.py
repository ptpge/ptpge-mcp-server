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
    <input type="text" id="q" placeholder="e.g. trekkspill · gultonet · accordion fold · fullfarge · opplag" value="trekkspill">
    <select id="q-lang">
      <option value="en" selected>en</option><option value="nb">nb</option>
      <option value="de">de</option><option value="ja">ja</option>
      <option value="es">es</option><option value="zh-Hans">zh-Hans</option>
    </select>
    <button onclick="doSearch()">Search</button>
  </div>
  <div class="hint">Search is tokenized and language-agnostic — Norwegian buyer phrases hit
  English terms and vice versa. Try:
  <a onclick="preset('gultonet papir')">gultonet papir</a> ·
  <a onclick="preset('kun sort')">kun sort</a> ·
  <a onclick="preset('litt tykt papir')">litt tykt papir</a> ·
  <a onclick="preset('rilling')">rilling</a> ·
  <a onclick="preset('brosjyre')">brosjyre</a></div>
</div>

<div class="card">
  <h2>ptpge_get_term — full context for one term</h2>
  <div class="row">
    <input type="text" id="uri" placeholder="URI or path under /v1/"
           value="printing/completions/finishing/scoring">
    <select id="t-lang">
      <option value="en" selected>en</option><option value="nb">nb</option>
      <option value="de">de</option><option value="ja">ja</option>
      <option value="es">es</option><option value="zh-Hans">zh-Hans</option>
    </select>
    <button onclick="doGet()">Get term</button>
  </div>
  <div class="hint">Tip: click a result <code>id</code> from a search, or try
  <a onclick="presetUri('ordering/products/buy-online/sheets/brochures')">brochures</a> ·
  <a onclick="presetUri('printing/substrates/sheet-materials/paper/paper-weights/medium-paper')">medium-paper</a> ·
  <a onclick="presetUri('variables/commercial/quantity')">quantity</a></div>
</div>

<div class="card">
  <h2>ptpge_get_version — dataset &amp; server version</h2>
  <div class="row"><button onclick="doVersion()">Get version</button></div>
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
  const res = await fetch("/mcp", {
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
  const text = JSON.stringify(obj, null, 2);
  const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const colored = esc
    .replace(/("(?:[^"\\\\]|\\\\.)*")(\\s*:)/g, '<span class="k">$1</span>$2')
    .replace(/: ("(?:[^"\\\\]|\\\\.)*")/g, ': <span class="s">$1</span>')
    .replace(/: (-?\\d+(?:\\.\\d+)?)/g, ': <span class="n">$1</span>');
  document.getElementById("out").innerHTML = colored;
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
    document.getElementById("status").textContent = "could not reach /mcp — " + e;
  }
})();
</script>
</body>
</html>
"""
