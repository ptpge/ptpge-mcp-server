"""Browser playground for the PTPGE MCP server (v0.3.3).

A single self-contained HTML page served at GET /playground. It exercises
the real Streamable HTTP transport from the browser: every button builds a
JSON-RPC message and POSTs it to /mcp on the SAME origin (no CORS needed),
then renders the tool result. Zero dependencies, zero install — the demo
URL anyone can open: https://open.mcp.ptpge.org/playground

On the stealth server the page sits behind the same Basic Auth as
everything else, so it works there too once the browser has credentials.
"""

_PLAYGROUND_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%231f4a35'/%3E%3C/svg%3E">
<title>Playground — PTPGE</title>
<style>__FRAME_CSS__</style>
<style>
* { box-sizing: border-box; }
body { font: 15px/1.55 var(--pf-sans), -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
       color: #1a1a1a; background: #f7f7f5; margin: 0; padding: 0; }
header:not(.pf) { background: #fff; border-bottom: 1px solid #e0e0dd; padding: 18px 28px; }
header, main { position: relative; z-index: 1; }
body { background: transparent; }
header:not(.pf) h1 { font-size: 18px; margin: 0; }
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
.dark { background: #1e1e1e; color: #d4d4d4; border-radius: 10px; padding: 16px 20px;
        font: 12.5px/1.5 ui-monospace, "SF Mono", Menlo, monospace;
        white-space: pre-wrap; word-break: break-word; overflow: auto; }
.dark .k { color: #9cdcfe; } .dark .s { color: #ce9178; } .dark .n { color: #b5cea8; }
/* — v3: accordion cards + inline results + session transcript — */
details.card summary, #transcript summary { cursor: pointer; list-style: none; position: relative; padding-right: 30px; }
details.card summary::-webkit-details-marker, #transcript summary::-webkit-details-marker { display: none; }
details.card summary::after, #transcript summary::after { content: "▾"; position: absolute; right: 2px; top: -2px;
        color: #444; font-size: 18px; line-height: 1.3; transition: transform .2s, color .15s; transform: rotate(-90deg); }
details.card[open] summary::after, #transcript[open] summary::after { transform: rotate(0); }
details.card summary:hover::after, #transcript summary:hover::after { color: #1f4a35; }
details.card summary h2 { margin: 0; }
.expl { display: block; font-size: 12.5px; color: #888; margin: 3px 0 0; }
details.card[open] summary { margin-bottom: 12px; }
.res { display: none; margin-top: 14px; }
.res .rjson { max-height: 420px; min-height: 0; }
.rmeta { font-size: 12px; color: #888; margin: 0 2px 6px; }
#transcript { margin-top: 26px; }
#transcript summary { display: flex; justify-content: space-between; align-items: baseline;
        font-size: 12px; color: #777; text-transform: uppercase; letter-spacing: .5px; }
#transcript summary b { color: #1f4a35; margin-left: 4px; }
#transcript summary a { color: #2a6045; cursor: pointer; text-decoration: underline;
        text-transform: none; letter-spacing: 0; margin-left: 14px; }
#transcript[open] summary { margin-bottom: 6px; }
#tr-body { min-height: 90px; max-height: 460px; }
.tr-empty { color: #777; font-style: italic; }
.tr-entry { border-top: 1px solid #333; padding-top: 10px; margin-top: 10px; }
.tr-entry:first-child { border-top: none; margin-top: 0; padding-top: 0; }
.tr-meta { font-size: 12px; color: #7fae97; margin: 0 0 6px; }
#status { font-size: 13px; color: #777; }
#status b { color: #1f4a35; }
footer { text-align: center; color: #999; font-size: 12px; padding: 18px; }
footer a { color: #2a6045; }
/* — v2: convergence demo + language switcher — */
.hdr-row { display: flex; align-items: center; justify-content: space-between;
           gap: 14px; flex-wrap: wrap; }
.hdr-left { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.hdr-row h1 { margin: 0; }
.pill { border: 1px solid #e0e0dd; background: #fff; border-radius: 999px;
        padding: 9px 18px; font-size: 14px; font-weight: 600; color: #1a1a1a;
        text-decoration: none; display: inline-flex; align-items: center;
        gap: 7px; cursor: pointer; white-space: nowrap; }
.pill:hover { border-color: #1f4a35; }
#langbtn { position: relative; border-radius: 8px; padding: 7px 11px; font-size: 12.5px; background: transparent; margin-left: 8px; color: #5b5b54; border-color: #e4e2dc;
           letter-spacing: .05em; color: #555; }
#langbtn .fl, #langlist .fl { font-size: 16px; line-height: 1; }
#langlist .fl { margin-right: 9px; }
#langbtn .car { font-size: 10px; color: #777; }
#langlist { position: absolute; top: 36px; right: 0; background: #fff;
            border: 1px solid #e0e0dd; border-radius: 12px; padding: 6px;
            display: none; min-width: 170px; max-height: calc(100vh - 70px); overflow: auto;
            box-shadow: 0 6px 24px rgba(0,0,0,.08); z-index: 5; }
#langlist a { display: flex; align-items: center; padding: 6px 10px; border-radius: 8px;
              color: #1a1a1a; text-decoration: none; font-size: 13px; letter-spacing: 0;
              font-weight: 400; cursor: pointer; }
#langlist a:hover { background: #f0f4f1; }
#langlist a.on { color: #1f4a35; font-weight: 700; }
.conv .langrow button { background: #fff; color: #1f4a35; border: 1.5px solid #1f4a35; }
button.secondary { background: #fff; color: #1f4a35; border: 1.5px solid #1f4a35; }
.conv .langrow button:hover { background: #eef4f0; }
.conv .langrow button.on { background: #1f4a35; color: #fff; }
.conv .prodrow button { border-radius: 999px; background: #eef4f0; color: #1f4a35;
  border: 1.5px solid transparent; padding: 8px 20px; }
.conv .prodrow button:hover { border-color: #1f4a35; background: #eef4f0; }
.conv .prodrow button.on { background: #1f4a35; color: #fff; }
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
.hashok { color: #1f7a3d; font-weight: 600; }
.hashbad { color: #b03434; font-weight: 600; }
.stale { opacity: .35; }
.canedit { border: 1px dashed transparent; border-radius: 6px; padding: 2px 4px; }
.canedit:hover { border-color: #cfcabb; }
.canedit:focus { border-color: #1f4a35; background: #fffdf6; outline: none; }
</style>
<style>
/* ── PTPGE dress (7 Oct 2026): ink instead of green, 4 px corners, Spectral for the title, dark mode ── */
:root{--ink:#20261f;--mute:#6a6a66;--line:#e4e2dc;--soft:#f6f5f1;--bg:#fff}
html.dark{--ink:#f2f3ef;--mute:#9a9a92;--line:rgba(255,255,255,.13);--soft:#1e201c;--bg:#262823}
body{color:var(--ink)}
header:not(.pf){background:transparent;border-bottom:1px solid var(--line);padding:28px 28px 18px}
header:not(.pf) h1{font:italic 600 clamp(28px,3.6vw,38px)/1.1 'Spectral',Georgia,serif;color:var(--ink);letter-spacing:0}
header:not(.pf) .sub{color:var(--mute);font-size:12.5px;margin-top:8px}header:not(.pf) .sub code{background:var(--soft);border:1px solid var(--line);border-radius:3px}
.badge{background:var(--ink);color:var(--soft);border-radius:3px;letter-spacing:.08em}
.card,.dark,.pill,button,input,select,#langlist,#langlist a,.stage .lng,.canedit{border-radius:4px}
.card{background:var(--bg);border-color:var(--line)}
.card h2{color:var(--ink);font-weight:600;letter-spacing:.14em;font-size:11.5px}
.expl,.hint,.rmeta,#status,.stage .slbl,.stage td.ph,.tr-empty,#transcript summary{color:var(--mute)}
button{background:var(--ink);color:var(--soft);border:1px solid var(--ink);font-family:inherit;font-weight:600}
button:hover{background:#000;border-color:#000}
html.dark button{background:#e6e8e2;color:#1e201c;border-color:#e6e8e2}
button:disabled{background:var(--line);color:var(--mute);border-color:var(--line)}
button.secondary,.conv .langrow button{background:var(--bg);color:var(--ink);border:1px solid var(--line)}
button.secondary:hover,.conv .langrow button:hover{border-color:var(--ink);background:var(--soft)}
.conv .langrow button.on{background:var(--ink);color:var(--soft);border-color:var(--ink)}
.conv .prodrow button{border-radius:4px;background:var(--soft);color:var(--ink);border:1px solid var(--line);padding:8px 16px}
.conv .prodrow button:hover{border-color:var(--ink);background:var(--soft)}
.conv .prodrow button.on{background:var(--ink);color:var(--soft);border-color:var(--ink)}
html.dark .conv .langrow button.on,html.dark .conv .prodrow button.on{background:#e6e8e2;color:#1e201c;border-color:#e6e8e2}
input,select{background:var(--bg);color:var(--ink);border-color:var(--line);font-family:inherit}
input:focus,select:focus{outline:2px solid var(--ink);outline-offset:1px;border-color:var(--ink)}
.hint a,footer a,#transcript summary a,#status b,#transcript summary b,.stage .slbl .num,#langlist a.on{color:var(--ink)}
details.card summary::after{color:var(--mute)}details.card summary:hover::after,#transcript summary:hover::after{color:var(--ink)}
.stage{border-left-color:var(--line)}.stage .lng{background:var(--soft);color:var(--ink);border:1px solid var(--line)}
.stage .tag{background:var(--soft);color:var(--mute);border:1px solid var(--line);border-radius:3px}
#conv-hist .same,.hashok{color:#2f6b3a}.hashbad{color:#a63a2a}
.tr-meta{color:#9aa39b}
.dark{background:#1b1d19;color:#e6e8e2}
#langlist{background:var(--bg);border-color:var(--line)}#langlist a{color:var(--ink)}#langlist a:hover{background:var(--soft)}
#langbtn{border-radius:4px}
.pill{background:var(--bg);color:var(--ink);border-color:var(--line);border-radius:4px}.pill:hover{border-color:var(--ink)}
.canedit:focus{border-color:var(--ink);background:var(--soft)}
footer{color:var(--mute)}
#conv-hist td{border-top-color:var(--line)}
</style>
</head>
<body>
__FRAME_HEADER__
<header>
  <div class="hdr-row">
    <div class="hdr-left">
      <h1>Playground</h1>
    </div>
  </div>
  <div class="sub" style="margin-top:8px"><span id="status">connecting…</span></div>
</header>
<template id="langtpl"><span class="pill" id="langbtn" onclick="langMenu(event)">
        <span class="fl" id="langflag">🇬🇧</span> <b id="langcode">EN</b> <span class="car">▾</span>
        <span id="langlist"></span>
      </span></template>
<script>(function(){var t=document.getElementById('langtpl'),b=document.getElementById('themebtn');if(t&&b){b.parentNode.insertBefore(t.content.cloneNode(true),b);}})();</script>
<main>

<details class="card conv" open>
  <summary><h2 data-i="t_conv">Same product · any language · one fingerprint</h2>
  <span class="expl" data-i="e_conv">Four real products in twelve languages — watch the same identity emerge, live.</span></summary>
  <p style="font-size:13px;color:#555;margin:0 0 10px" data-i="i_conv">Four real products,
  four different setup models — a brochure (folded sheet), business cards (flat sheet) and
  a booklet (multi-page) and a panel print (custom size on a rigid board) — each phrased in twelve languages. Pick a product, then a language,
  and watch the same identity emerge.</p>
  <div class="row prodrow" id="prod-btns" style="margin-bottom:12px"></div>
  <div class="row langrow" style="align-items:center">
    <span id="conv-btns" style="display:contents"></span>
    <span id="conv-tgl" style="display:none;margin-left:auto"><a
      style="cursor:pointer;color:#2a6045;font-size:12px;text-decoration:underline"
      onclick="convToggle()"></a></span>
  </div>
  <div id="conv-out"></div>
  <div class="hint" data-i="h_conv">The interpretation (words → bindings) is pre-scripted per
  language — that is the AI agent's job in production. The term labels, envelope validation
  and the ptpge-cfs/1 fingerprint run <em>live</em> against this server. The hash is a
  deterministic function, not a model output.</div>
  <div id="conv-hist" style="display:none;margin-top:14px">
    <div class="stage"><span class="slbl" data-i="hist">Run history — same product, different languages</span>
    <table id="conv-hist-t"></table></div>
  </div>
</details>

<details class="card">
  <summary><h2 data-i="t_search">ptpge_search_terms — free-text search</h2>
  <span class="expl" data-i="e_search">Type a buyer phrase in any of twelve languages — get the canonical term and its permanent URI.</span></summary>
  <div class="row">
    <input type="text" id="q" placeholder="e.g. brochure · accordion fold · ivory paper · full colour · copies" value="brochure">
    <select id="q-lang">
      <option value="en" selected>en</option><option value="nb">nb</option>
      <option value="de">de</option><option value="ja">ja</option>
      <option value="es">es</option><option value="zh-Hans">zh-Hans</option>
      <option value="pt">pt</option><option value="hi">hi</option>
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
  <div class="res" id="res-search"></div>
</details>

<details class="card">
  <summary><h2 data-i="t_get">ptpge_get_term — full context for one term</h2>
  <span class="expl" data-i="e_get">One URI in — full context out: labels in all languages, definition, place in the tree.</span></summary>
  <div class="row">
    <input type="text" id="uri" placeholder="URI or path under /v1/"
           value="printing/completions/folding">
    <select id="t-lang">
      <option value="en" selected>en</option><option value="nb">nb</option>
      <option value="de">de</option><option value="ja">ja</option>
      <option value="es">es</option><option value="zh-Hans">zh-Hans</option>
      <option value="pt">pt</option><option value="hi">hi</option>
    </select>
    <button onclick="doGet()" data-i="b_get">Get term</button>
  </div>
  <div class="hint"><span data-i="h_get">Tip: click a result <code>id</code> from a search, or try</span>
  <a onclick="presetUri('ordering/products/brochures')">brochures</a> ·
  <a onclick="presetUri('printing/substrates/sheet-materials/paper/paper-weights/medium-paper')">medium-paper</a> ·
  <a onclick="presetUri('variables/order/quantity')">quantity</a></div>
  <div class="res" id="res-get"></div>
</details>

<details class="card">
  <summary><h2 data-i="t_ver">ptpge_get_version — dataset &amp; server version</h2>
  <span class="expl" data-i="e_ver">Which dataset and server version this playground is talking to.</span></summary>
  <div class="row"><button onclick="doVersion()" data-i="b_ver">Get version</button></div>
  <div class="res" id="res-ver"></div>
</details>

<details class="card">
  <summary><h2 data-i="t_color">ptpge_resolve_color_notation — the shorthand buyers actually write</h2>
  <span class="expl" data-i="e_color">"4/1" is a count of separations, not a colour. Watch the same notation resolve differently on different products — and ask when it must.</span></summary>
  <p style="font-size:13px;color:#555;margin:0 0 10px;font-style:italic">
  A buyer writes "CMYK on the front, black on the back" — or just 4/1. But "1" is
  black on one press and a named spot colour on another, so the number alone cannot
  identify the product. The resolver searches the combinations <em>this product's
  envelope supports</em> whose channel counts sum to that number.</p>
  <div class="row">
    <button onclick="doColor('ordering/products/business-cards','4/4')">4/4 · business cards</button>
    <button onclick="doColor('ordering/products/books','4/1')">4/1 · books</button>
    <button onclick="doColor('ordering/products/business-cards','4/1')">4/1 · business cards</button>
    <button onclick="doColor('ordering/products/business-cards','4+1')">4+1 · business cards</button>
  </div>
  <div class="hint" data-i="h_color">Three outcomes, all correct: <b>4/4</b> resolves (4 is CMYK by trade
  convention). <b>4/1 on books</b> resolves to black — that template supports no other
  single-channel ink, so there is nothing to ask about. <b>4/1 on business cards</b> returns
  <code>needs_disambiguation</code> with a ready-made question, because black, white and spot
  are all possible. <b>4+1</b> asks about the separator first: in parts of the trade it means
  five inks on one surface, not front/back. The server never guesses — a guessed default would
  give two different products the same fingerprint. (SD-0071)</div>
  <div class="res" id="res-color"></div>
</details>

<details class="card">
  <summary><h2 data-i="t_chain">Test-prompt demo — the full chain, live</h2>
  <span class="expl" data-i="e_chain">Envelope → validation → fingerprint on a fixed example order — the whole journey in three clicks.</span></summary>
  <p style="font-size:13px;color:#555;margin:0 0 10px;font-style:italic">
  "I want a brochure, 6 pages, A5 portrait, folded as a Z-fold, on ivory-toned
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
  <div class="res" id="res-chain"></div>
</details>

<details class="card">
  <summary><h2 data-i="t_own">Your own prompt — see what resolves</h2>
  <span class="expl" data-i="e_own">Describe a print job in your own words and see which pieces map to the specification.</span></summary>
  <textarea id="prompt" rows="3" style="width:100%;padding:10px 12px;border:1px solid #ccc;border-radius:7px;font-size:14px;font-family:inherit;resize:vertical" placeholder="Describe a print job in your own words, any language…">I want a folded leaflet, A4 portrait, roll fold, 170 gsm silk paper, matte lamination, full colour both sides, 1000 copies</textarea>
  <div class="row" style="margin-top:10px"><button class="secondary" onclick="doResolve()" data-i="b_resolve">Resolve by rule</button><button id="fpassemble" class="secondary" style="display:none" onclick="assembleFingerprint()" data-i="b_fp">Fingerprint this &rarr; mark + QR</button></div>
  <div class="hint">Two ways to solve the same prompt. <b>Agent mode</b> (the green box — the primary path): a real model is handed the tools and runs the loop itself, from the outside, like any AI agent. <b>Rules</b> (the outlined buttons): the page searches 1–3 word n-grams and assembles them by rule — no model, deterministic, an approximation of what an agent does. Both end in the same place — a validated, <i>complete</i> configuration and one ptpge-cfs/1 fingerprint — or in the specification's question (SD-0083: no identity until the required axes are known). Both log every call to the transcript.</div>
  <div class="res" id="res-own"></div>
  <div id="agent-box" style="margin-top:14px;padding:12px 14px;border:1px solid #cfe0d6;border-radius:8px;background:#f4f9f6">
    <div class="row" style="align-items:center;gap:10px;flex-wrap:wrap;margin:0">
      <b data-i="ag_t" style="margin-right:4px">Agent mode — a real model runs the loop</b>
      <select id="ag-mode" onchange="agModeChange()" style="padding:6px 8px;border:1px solid #ccc;border-radius:6px;font-size:13px">
        <option value="sponsored" data-i="ag_o1">Sponsored run — we pay, 5 a day</option>
        <option value="anthropic" data-i="ag_o2">Your own Anthropic key</option>
        <option value="openai" data-i="ag_o3">Your own OpenAI key</option>
      </select>
      <input id="ag-key" type="password" autocomplete="off" placeholder="API key — stays in this browser" style="display:none;padding:6px 8px;border:1px solid #ccc;border-radius:6px;font-size:13px;width:260px">
      <input id="ag-model" autocomplete="off" placeholder="model" style="display:none;padding:6px 8px;border:1px solid #ccc;border-radius:6px;font-size:13px;width:170px">
      <button onclick="agentRun()" data-i="b_agent">Run agent &rarr; fingerprint</button><span class="hint" style="margin:0" data-i="h_agent">Complete prompt → one fingerprint. Leave out the fold or the orientation and the agent asks instead of guessing.</span>
      <span id="ag-status" style="font-size:12px;color:#5b7a69"></span>
    </div>
    <div class="hint" data-i="ag_hint" style="margin-top:8px">The model is handed the same tools an AI agent gets from <code>tools/list</code> and runs the loop itself: search terms, read the envelope, resolve colour counts, validate, fingerprint — every model turn and every <code>tools/call</code> lands in the transcript. Sponsored runs go through <code>engine.gutenlex.com</code> (a GutenLex service), which holds the key; the open MCP server never carries a model. Your own key is kept only in this browser's localStorage and sent straight to the provider.</div>
    <div class="res" id="res-agent"></div>
  </div>
</details>

<details id="transcript">
  <summary><span><span data-i="tr_t">Session transcript — every MCP call this page has made</span> <b id="tr-count" style="display:none"></b></span>
  <a onclick="event.preventDefault();event.stopPropagation();trClear()" data-i="tr_clear">clear</a></summary>
  <div id="tr-body" class="dark"><div class="tr-empty" data-i="tr_e">No calls yet. Every button logs its request and response here, chronologically — the conversation an AI agent would have with this server.</div></div>
</details>

</main>
<p class="sub" style="max-width:960px;margin:40px auto 56px;padding:0 24px;position:relative;z-index:1;font-size:12.5px;color:#8a8a82;text-align:center"><span data-i="sub">Every button above sends a real MCP <code>tools/call</code> (JSON-RPC over Streamable HTTP) to <code>/mcp</code> on this server — exactly what an AI agent does.</span></p>
__FRAME_FOOTER__

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

async function callTool(name, args, target) {
  const buttons = document.querySelectorAll("button");
  buttons.forEach(b => b.disabled = true);
  showBusy(target, "tools/call " + name + " — calling…");
  try {
    const { json, ms, status } = await rpc("tools/call", { name: name, arguments: args });
    let payload = json;
    if (json.result && json.result.content && json.result.content[0]) {
      try { payload = JSON.parse(json.result.content[0].text); } catch (e) { payload = json.result; }
    } else if (json.error) {
      payload = json;
    }
    showInline(target, `tools/call ${name} · HTTP ${status} · ${ms} ms · request id ${json.id}`, payload);
  } catch (e) {
    showInline(target, "request failed", { error: String(e) });
  } finally {
    buttons.forEach(b => b.disabled = false);
  }
}

// Hybrid output (v3): the response renders INLINE in the card you clicked,
// and every call is appended to the session transcript at the bottom —
// the chronological conversation an agent would have with this server.
function showBusy(target, text) {
  const res = target ? document.getElementById("res-" + target) : null;
  if (res) { res.style.display = "block";
    res.innerHTML = '<div class="rmeta">' + text + '</div>'; }
}
function showInline(target, metaText, obj) {
  const html = fmtJson(obj);
  const res = target ? document.getElementById("res-" + target) : null;
  if (res) { res.style.display = "block";
    res.innerHTML = '<div class="rmeta">' + metaText + '</div>' +
                    '<div class="rjson dark">' + html + '</div>'; }
  trAdd(metaText, html);
}
let TR_N = 0;
function trAdd(metaText, html) {
  const b = document.getElementById("tr-body");
  if (!b) return;
  const e0 = b.querySelector(".tr-empty"); if (e0) e0.remove();
  TR_N++;
  const c = document.getElementById("tr-count");
  if (c) { c.style.display = ""; c.textContent = "(" + TR_N + ")"; }
  const hh = new Date().toTimeString().slice(0, 8);
  const d = document.createElement("div"); d.className = "tr-entry";
  d.innerHTML = '<div class="tr-meta">#' + TR_N + ' · ' + hh + ' · ' + metaText +
                '</div><div>' + html + '</div>';
  b.appendChild(d);
  b.scrollTop = b.scrollHeight;
}
const TR_EMPTY_HTML = document.getElementById("tr-body").innerHTML;
function trClear() {
  TR_N = 0;
  const c = document.getElementById("tr-count");
  if (c) { c.style.display = "none"; c.textContent = ""; }
  document.getElementById("tr-body").innerHTML = TR_EMPTY_HTML;
  setLang(CUR_LANG);
}

function fmtJson(obj) {
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
      // Editable canonical form + live SHA-256 (same trick as the convergence
      // demo): edit a byte, the identity goes red; reset, it comes home green.
      const sp = obj.profiles.spec;
      const tt = key => (typeof UI !== "undefined" && ((UI[CUR_LANG] && UI[CUR_LANG][key]) || UI.en[key])) || key;
      const escA = v => String(v).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
      strip = '<div class="fpwrap" data-orig="' + escA(sp.canonical) + '" data-hash="' + escA(sp.sha256) + '">' +
        '<div class="fpe-vis">' + strip + '</div>' +
        '<div style="font-size:11px;color:#7fae97;margin:2px 0 4px">canonical · ptpge-cfs/1 ' +
        '<span class="fpe-reset" style="cursor:pointer;color:#37d98a;margin-left:8px">reset</span></div>' +
        '<div class="fpe-canon" contenteditable="true" spellcheck="false" style="white-space:pre-wrap;word-break:break-all;border:1px dashed #3a5a48;border-radius:6px;padding:6px 8px;color:#d8d8d8;outline:none">' + escA(sp.canonical) + '</div>' +
        '<div class="fpe-hash" style="margin-top:6px;font-weight:700;color:#37d98a;word-break:break-all">' + escA(sp.sha256) + '</div>' +
        '<div class="fpe-note" style="font-size:12px;color:#7fae97;margin-bottom:12px">\u2713 ' + tt("same") + ' \u00b7 ' + escA(sp.resolverUrl || "") + '</div>' +
        '<div style="font-size:11px;color:#7fae97;margin-bottom:14px">' + tt("ed_hint") + '</div></div>';
    }
  } catch (e) { strip = ""; }
  const text = JSON.stringify(obj, null, 2);
  const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const colored = esc
    .replace(/("(?:[^"\\\\]|\\\\.)*")(\\s*:)/g, '<span class="k">$1</span>$2')
    .replace(/: ("(?:[^"\\\\]|\\\\.)*")/g, ': <span class="s">$1</span>')
    .replace(/: (-?\\d+(?:\\.\\d+)?)/g, ': <span class="n">$1</span>');
  return strip + colored;
}
// Live re-hash for every editable canonical form on the page (delegated, so it
// works for results rendered later — own prompt, chain demo, transcript).
(function () {
  const tt = key => (typeof UI !== "undefined" && ((UI[CUR_LANG] && UI[CUR_LANG][key]) || UI.en[key])) || key;
  async function reHash(wrap) {
    const canon = wrap.querySelector(".fpe-canon"), hash = wrap.querySelector(".fpe-hash"),
          note = wrap.querySelector(".fpe-note"), vis = wrap.querySelector(".fpe-vis");
    const txt = canon.textContent, orig = wrap.getAttribute("data-orig");
    if (txt === orig) {
      hash.textContent = wrap.getAttribute("data-hash"); hash.style.color = "#37d98a";
      note.innerHTML = "\u2713 " + tt("same"); if (vis) vis.style.opacity = "";
      return;
    }
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(txt));
    hash.textContent = Array.from(new Uint8Array(buf)).map(x => x.toString(16).padStart(2, "0")).join("");
    hash.style.color = "#ff6b6b";
    note.innerHTML = "\u2717 " + tt("ed_diff"); if (vis) vis.style.opacity = "0.25";
  }
  document.addEventListener("input", e => {
    const w = e.target.closest && e.target.closest(".fpwrap"); if (w && e.target.classList.contains("fpe-canon")) reHash(w);
  });
  document.addEventListener("click", e => {
    if (!e.target.classList || !e.target.classList.contains("fpe-reset")) return;
    const w = e.target.closest(".fpwrap"); if (!w) return;
    w.querySelector(".fpe-canon").textContent = w.getAttribute("data-orig"); reHash(w);
  });
})();

function doSearch() {
  callTool("ptpge_search_terms", {
    query: document.getElementById("q").value,
    limit: 10,
    language: document.getElementById("q-lang").value,
  }, "search");
}
function doGet() {
  callTool("ptpge_get_term", {
    id_or_path: document.getElementById("uri").value,
    language: document.getElementById("t-lang").value,
  }, "get");
}
function doVersion() { callTool("ptpge_get_version", {}, "ver"); }

// SD-0071 — colour pair notation. The count is resolved against what the
// product's envelope supports, so the same string is deterministic on one
// template and a question on another.
function doColor(product, notation) {
  callTool("ptpge_resolve_color_notation", { product: product, notation: notation }, "color");
}

// — Test-prompt demo: the canonical brochure configuration —
const DEMO_PRODUCT = "ordering/products/brochures";
const DEMO_BINDINGS = [
  { variable: "variables/configuration/setup-model",
    value: "printing/configurations/setup-models/folded-sheet/z-fold" },
  { variable: "variables/configuration/page-count", value: 6 },
  { variable: "variables/configuration/format",
    value: "printing/configurations/formats/a-series/a5" },
  { variable: "variables/configuration/orientation",
    value: "printing/configurations/orientation/portrait" },   // required axis (SD-0083) — the prompt says «A5 portrait»
  { variable: "variables/substrate/substrate-type",
    value: "printing/substrates/sheet-materials/paper" },
  { variable: "variables/substrate/substrate-color",
    value: "printing/substrates/sheet-materials/paper/paper-color-shades/ivory-paper" },
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
  const STOP = new Set(("i want a an the on of with and or in to for it is be both sides side please order printed print copies copy gsm " +
    "jeg vil ha en et pa på med og eller som begge sider af av til det den ett " +          // nb / da / sv
    "ich möchte ein eine mit auf und oder von für in zu das der die " +                       // de
    "ik wil een met op en of van voor het " +                                                 // nl
    "chcę z na i lub w do o " +                                                               // pl
    "quiero un una con en y o de la el por para sobre").split(" ").filter(Boolean));         // es
  // Unicode-aware: keep letters in every script (æ ø å ä ö ü ł ñ 日本語 …) — an ASCII class
  // used to split "hæfter" into "h" + "fter" and "på" into "p".
  const cleaned = raw.toLowerCase().replace(/[^\\p{L}\\p{N}\\s-]/gu, " ");
  const rawWords = cleaned.split(/\\s+/).filter(Boolean);
  const numbers = rawWords.filter(w => /^[0-9]/.test(w));
  const words = rawWords.filter(w => !STOP.has(w) && !/^[0-9]/.test(w));
  if (!words.length) { showInline("own", "resolve", { note: "No searchable words found." }); return; }
  const cands = [];
  for (let i = 0; i < words.length; i++)
    for (let n = 1; n <= 3 && i + n <= words.length; n++)
      cands.push({ i, n, phrase: words.slice(i, i + n).join(" ") });
  const buttons = document.querySelectorAll("button");
  buttons.forEach(b => b.disabled = true);
  showBusy("own", 'resolving "' + raw + '" — ' + cands.length + " candidate phrases via ptpge_search_terms…");
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
          // query_language as well as language: the prompt was typed in the
          // language selected here, so a phrase that fails is recorded
          // against the right market instead of defaulting to English.
          name: "ptpge_search_terms",
          arguments: { query: c.phrase, limit: 5, language: lang, query_language: lang },
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
      i: c.i, n: c.n,   // ordposisjon — flate-deteksjonen i assembleFingerprint trenger naboene
      level: c.hit.level || null, notation: c.hit.notation || null, score: c.hit.score }));
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
    LAST_RESOLVE = { resolved: resolved, numbers: numbers, raw: raw, words: words, productFallback: productFallback };
    document.getElementById("fpassemble").style.display = resolved.length ? "" : "none";
    showInline("own",
      resolved.length + " attribute(s) resolved · " + cands.length + " lookups · ptpge_search_terms", {
      prompt: raw,
      resolved_attributes: resolved,
      numeric_or_layer2: numbers.length ? numbers : undefined,
      redundant_words: redundant.length ? redundant : undefined,
      unresolved_words: unresolved.length ? unresolved : undefined,
      note: "Greedy non-overlapping n-gram resolution (the demo's stand-in for an LLM). 'redundant_words' already map to a term captured via another word (e.g. 'leaflet' -> the same Folded Sheet Setup as 'folded'). Press 'Fingerprint this' to assemble: value-level terms bind by their place in the tree, numbers bind by the unit word beside them, colour counts go through the resolver, and the configuration is validated before it is fingerprinted — the steps an agent takes, as rules.",
    });
  } finally {
    buttons.forEach(b => b.disabled = false);
  }
}

let LAST_RESOLVE = null;
// Assembly v2 (2026-09-14): rules, not a model — but the rules a careful agent
// would follow. (1) only VALUE-level terms bind (a group like "Paper Weights"
// never does); (2) each term goes to the variable its place in the tree
// implies; (3) numbers bind by the unit word beside them, in the ten
// languages of the specification; (4) "4 colours", "4/4", "4+1", "double-sided"
// go through ptpge_resolve_color_notation — a count is not a colour;
// (5) validate against the envelope, put any disambiguation question to the
// user verbatim and STOP; (6) only then fingerprint. Same tools an agent calls.
const VAR_MAP = [
  ["/configurations/formats/",      "variables/configuration/format"],
  ["/configurations/setup-models/", "variables/configuration/setup-model"],
  ["/features/colors/",             "variables/features/color-mode"],
  ["/features/surface-finish/",     "variables/features/surface-finish"],
  ["/features/embellishments/",     "variables/features/embellishment"],
  ["/completions/binding/",         "variables/finishing/binding"],
  ["/completions/structural-finishing/", "variables/finishing/structural-finishing"],
  ["/completions/edge",             "variables/finishing/edge"],
  ["/configurations/orientation/",  "variables/configuration/orientation"],
  ["/configurations/back-orientation/", "variables/configuration/back-orientation"],
  ["/configurations/shape",         "variables/configuration/shape"],
  ["/standards/certifications/",    "variables/compliance/certification"],
  ["/standards/print-standards/",   "variables/compliance/print-standard"],
  ["/technologies/printing-technologies/", "variables/production/technology"],
  ["/paper-surfaces/",              "variables/substrate/substrate-finish"],
  ["/paper-coatings/",              "variables/substrate/substrate-coating"],
  ["/paper-fibre/",                 "variables/substrate/substrate-fibre"],
  ["/paper-color-shades/",          "variables/substrate/substrate-color"],
  ["/paper-classes/",               "variables/substrate/substrate-class"],
  ["/paper-weights/",               "variables/substrate/substrate-weight"],
  ["/substrates/",                  "variables/substrate/substrate-type"],
];
// Unit words that give a bare number its axis — en de nb sv da nl pl es ja zh.
const U_PAGES = "pages?|pp|sider|sidor|seiten|pagina'?s?|paginas?|stron|strony?|p[aá]ginas?|ページ|页|頁";
const U_GSM   = "gsm|g\\\\/m[²2]|gram|gramos?|gramm|gr|g";
const U_QTY   = "copies|pcs|pieces|units|stk|stk\\\\.|st|eks|eks\\\\.|ex|exemplare|exemplaren|st[üu]ck|szt|sztuk|ejemplares|unidades|部|份|件";
const U_COL   = "colou?rs?|farver|farger|f[äa]rger|farben|kleuren|kolor[óo]w|kolory|colores|色|色数";
const SIDES2  = /(\\b(2|to|two|double|both|dobbelt|dubbel)[- ]?(sided|sidet|sidig|seitig|zijdig|sides|sider|sidor)|tosidig|tosidet|beidseitig|zweiseitig|dubbelzijdig|dwustronn|a doble cara|両面|双面)/;
// 0.27.1: "folded" in the ten languages (a named fold — tri-fold, z-fold — resolves on its own)
const FOLDW   = /(\\bfolded\\b|\\bfold\\b|\\bfals(et|ede|ad|ade)\\b|\\bfoldet\\b|\\bgefalzt\\w*|\\bgefaltet\\w*|\\bfalz\\b|\\bgevouwen\\b|\\bvouw\\b|\\bpli[ée]e?s?\\b|\\bplegad[oa]s?\\b|\\bdoblad[oa]s?\\b|\\bskładan[yae]\\w*|\\bzłożon[yae]\\w*|折り|折页|对折)/;
const SIDES1  = /(\\b(1|one|single|enkelt?|een)[- ]?(sided|sidet|sidig|seitig|zijdig|side)|ensidig|ensidet|enkelsidig|einseitig|enkelzijdig|jednostronn|a una cara|片面|单面)/;
function numWithUnit(raw, units) {
  const m = new RegExp("(\\\\d+)\\\\s*(?:" + units + ")(?![\\\\p{L}])", "iu").exec(raw);
  return m ? parseInt(m[1], 10) : null;
}
async function assembleFingerprint() {
  if (!LAST_RESOLVE) return;
  const rel = u => u.replace("https://ptpge.org/v1/", "");
  const raw = (LAST_RESOLVE.raw || "").toLowerCase();
  const lang = document.getElementById("q-lang").value;
  const WORDS = LAST_RESOLVE.words || [];
  const OUT = /^(outside|cover|outer|exterior|utside|udvendig|außen|aussen|buitenkant)$/, IN = /^(inside|inner|interior|innside|indvendig|innen|binnenkant)$/;
  const surfaceFor = r => {
    if (r.i == null) return "";
    const test = w => OUT.test(w) ? "outside" : (IN.test(w) ? "inside" : "");
    for (let k = r.i; k < Math.min(WORDS.length, r.i + r.n + 4); k++) { const s = test((WORDS[k] || "").toLowerCase()); if (s) return s; }
    for (let k = Math.max(0, r.i - 2); k < r.i; k++) { const s = test((WORDS[k] || "").toLowerCase()); if (s) return s; }
    return "";
  };
  let product = null; const bindings = []; const skipped = []; const steps = [];
  let foldedGroup = false;   // 0.27.1: "folded" resolved to the Folded Sheet group, no fold named
  for (const r of LAST_RESOLVE.resolved) {
    const u = rel(r.uri);
    if (u.indexOf("ordering/products/") === 0) { if (!product) product = u; continue; }
    if (r.level && r.level !== "element") {
      if (u === "printing/configurations/setup-models/folded-sheet") foldedGroup = true;
      skipped.push(r.resolved + " — a group, not a value"); continue;
    }
    if (u === "printing" || u.indexOf("ordering/knowledge/") === 0) { skipped.push(r.resolved + " — not a configuration value"); continue; }
    let mapped = null;
    for (const [frag, v] of VAR_MAP) if (u.indexOf(frag) !== -1) { mapped = v; break; }
    // 0.32.0: a named fold found as a completion (completions/folding/roll-fold) is, on a
    // folded product, the setup model of the same name — bind it there; the validator
    // confirms it is in the product's envelope.
    if (!mapped && u.indexOf("printing/completions/folding/") === 0) {
      const slug = u.slice("printing/completions/folding/".length);
      if (slug && slug.indexOf("/") === -1) {
        const setupU = "printing/configurations/setup-models/folded-sheet/" + slug;
        if (!bindings.some(b => b.variable === "variables/configuration/setup-model")) {
          bindings.push({ variable: "variables/configuration/setup-model", value: setupU });
          steps.push(r.resolved + " → setup model " + slug + " (a named fold is the sheet's setup)");
          continue;
        }
      }
    }
    if (mapped) {
      if (mapped === "variables/substrate/substrate-weight" && numWithUnit(raw, U_GSM) != null) { skipped.push(r.resolved + " — the stated gsm wins over the band word"); continue; }
      const b = { variable: mapped, value: u };
      const s = surfaceFor(r); if (s) b.surface = s;
      bindings.push(b);
    } else skipped.push(r.resolved + " (" + u + ")");
  }
  // Merge same axis+surface into a values list (matte + spot-UV); never send a duplicate.
  const byLhs = {};
  for (const b of bindings) {
    const lhs = b.variable + "@" + (b.surface || ""); const prev = byLhs[lhs];
    if (!prev) { byLhs[lhs] = b; continue; }
    if (typeof b.value === "string" && (prev.values || typeof prev.value === "string")) { prev.values = (prev.values || [prev.value]).concat([b.value]); delete prev.value; }
    else skipped.push("duplicate on " + lhs + " → kept first");
  }
  bindings.length = 0; Array.prototype.push.apply(bindings, Object.values(byLhs));
  const hasVar = v => bindings.some(b => b.variable === v);
  // 0.27.1 — a folded product with no fold named: bind the Single-Fold Setup (one
  // fold, the least assumption) and say so. Name the fold ("tri-fold", "z-fold")
  // to change it. Same choice the agent made on this prompt (2026-09-15).
  // SD-0083 (0.28.0): "folded" with no fold named is NOT assumed any more — the
  // validator asks "which fold?" and no identity is issued until it is answered.
  // (0.27.1 bound single-fold here; withdrawn: the specification never assumes.)
  if ((foldedGroup || FOLDW.test(raw)) && !hasVar("variables/configuration/setup-model"))
    steps.push("folded, fold not named → the validator will ask which fold (SD-0083)");
  // A folded sheet's two faces are outside/inside; a flat sheet's are front/back.
  const folded = bindings.some(b => b.variable === "variables/configuration/setup-model" && String(b.value).indexOf("setup-models/folded-sheet/") !== -1);
  const boundSetup = (bindings.find(b => b.variable === "variables/configuration/setup-model") || {}).value || null;
  const F1 = folded ? "outside" : "front", F2 = folded ? "inside" : "back";
  const derivedSurface = new Set();   // bindings whose outside/inside came from the fold, not the buyer
  // "full colour both sides" — a colour term with no surface word: two-sided prompts
  // put it on both surfaces, one-sided prompts on the first surface only.
  for (const b of bindings.slice()) {
    if (b.variable !== "variables/features/color-mode" || b.surface) continue;
    if (SIDES2.test(raw)) { b.surface = F1; const b2 = { variable: b.variable, surface: F2, value: b.value }; bindings.push(b2); derivedSurface.add(b); derivedSurface.add(b2); steps.push("colour → " + F1 + " + " + F2 + " (two-sided)"); }
    else if (SIDES1.test(raw)) { b.surface = F1; derivedSurface.add(b); steps.push("colour → " + F1 + " (one-sided)"); }
  }
  // Numbers by unit word. A number claimed by one rule is not offered to the next.
  const claimed = new Set();
  const pc = numWithUnit(raw, U_PAGES);
  if (pc != null && !hasVar("variables/configuration/page-count")) { bindings.push({ variable: "variables/configuration/page-count", value: pc }); claimed.add(pc); steps.push(pc + " → page-count"); }
  const gsm = numWithUnit(raw, U_GSM);
  if (gsm != null && !hasVar("variables/substrate/substrate-weight")) { bindings.push({ variable: "variables/substrate/substrate-weight", value: gsm }); claimed.add(gsm); steps.push(gsm + " → substrate-weight (gsm)"); }
  let qty = numWithUnit(raw, U_QTY);
  if (qty == null) {   // no unit word: the largest number ≥ 25 that nothing else claimed
    const nums = (LAST_RESOLVE.numbers || []).map(x => parseInt(x, 10)).filter(n => !isNaN(n) && !claimed.has(n));
    qty = nums.filter(n => n >= 25).sort((a, b) => b - a)[0] || null;
  }
  if (qty != null && !hasVar("variables/order/quantity")) { bindings.push({ variable: "variables/order/quantity", value: qty }); claimed.add(qty); steps.push(qty + " → quantity"); }
  // Colours: "4/4", "4+1", "4 colours double-sided", "4 farver 2-sidet" → resolver, never a guess.
  let notation = null;
  const pair = /(\\d)\\s*[\\/+]\\s*(\\d)/.exec(raw);
  if (pair) notation = pair[1] + "/" + pair[2];
  else {
    const nc = numWithUnit(raw, U_COL);
    if (nc != null) notation = SIDES1.test(raw) ? nc + "/0" : (nc + "/" + nc);
  }
  if (!product && LAST_RESOLVE.productFallback) product = rel(LAST_RESOLVE.productFallback.id);
  if (!product) { showInline("own", "assembly", { note: "No product recognised in the prompt — include a product word (labels, poster, brochure, business card …)." }); return; }
  if (notation && !hasVar("variables/features/color-mode")) {
    showBusy("own", "assembly · " + notation + " → ptpge_resolve_color_notation …");
    try {
      const cnArgs = { product: product, notation: notation, language: lang }; if (boundSetup) cnArgs.setup = boundSetup;
      const { json } = await rpc("tools/call", { name: "ptpge_resolve_color_notation", arguments: cnArgs });
      const cr = JSON.parse(json.result.content[0].text);
      trAdd("ptpge_resolve_color_notation · " + notation + " on " + product, fmtJson(cr));
      const qs = [];
      for (const [sf, r] of Object.entries(cr.surfaces || {})) {
        if (r.needs_disambiguation || (r.candidates && r.candidates.length > 1 && !r.binding)) qs.push({ surface: sf, question: r.question || (r.needs_disambiguation && r.needs_disambiguation.question) || "Which colour set is meant?", candidates: r.candidates });
        else if (r.binding && r.binding.length && !r.invalid) { const cb = { variable: "variables/features/color-mode", surface: folded ? (sf === "front" ? "outside" : (sf === "back" ? "inside" : sf)) : sf, value: rel(r.binding[0]) }; bindings.push(cb); if (folded) derivedSurface.add(cb); }
        else if (r.count === 0) { /* 4/0: nothing on that surface */ }
        else if (r.invalid) skipped.push("colour " + notation + " on " + sf + ": invalid for this product");
      }
      steps.push(notation + " → color-mode per surface (resolver" + (folded ? ", front/back read as outside/inside on a folded sheet" : "") + ")");
      if (qs.length) {
        showInline("own", "assembly stopped — the resolver needs an answer (elicitation contract: never guess a colour)", { product: product, bindings: bindings, needs_disambiguation: qs, note: "An agent puts this question to the buyer verbatim and only then fingerprints. Rephrase the prompt with the answer (e.g. 'black on the back') and run again." });
        return;
      }
    } catch (e) { skipped.push("colour notation " + notation + ": " + e); }
  }
  trAdd("assembly: " + product + " + " + bindings.length + " binding(s) · " + steps.join(" · ") + (skipped.length ? " · left out: " + skipped.join(", ") : ""), fmtJson({ product: product, bindings: bindings }));
  // Validate first — an agent never fingerprints an unvalidated configuration.
  showBusy("own", "assembly · ptpge_validate_config …");
  try {
    let { json } = await rpc("tools/call", { name: "ptpge_validate_config", arguments: { product: product, bindings: bindings, language: lang } });
    let vr = JSON.parse(json.result.content[0].text);
    let bad = (vr.bindings || []).filter(b => b.status && b.status !== "in_envelope" && b.status !== "not_checked");
    void derivedSurface;
    trAdd("ptpge_validate_config · " + (vr.validInEnvelope ? "valid in envelope" : "NOT valid") + (bad.length ? " · " + bad.map(b => b.variable + ": " + b.status).join(", ") : "") + ((vr.advisories || []).length ? " · advisories: " + vr.advisories.length : ""), fmtJson(vr));
    if (vr.needs_disambiguation && vr.needs_disambiguation.length) {
      const qs = vr.needs_disambiguation.map(q => "• " + q.question + (q.candidates && q.candidates.length ? "  (" + q.candidates.map(c => (c.label || c.id || c)).slice(0, 8).join(", ") + (q.candidates.length > 8 ? ", …" : "") + ")" : "")).join("\\n");
      showInline("own", "no identity yet — the specification asks (SD-0083): answer in the prompt and run again", Object.assign({ questions: qs.split("\\n") }, vr));
      trAdd("ptpge_validate_config · complete: false · " + vr.needs_disambiguation.length + " question(s) — no fingerprint until answered", fmtJson(vr));
      return;
    }
    if (vr.validInEnvelope === false) {
      const why = bad.map(b => (b.value || "").toString().split("/").pop() + " is not in the " + product.split("/").pop() + " envelope for " + b.variable.split("/").pop()).join("; ");
      showInline("own", "not valid in this product's envelope — " + why + " · an agent would ask the buyer here; the fingerprint is not computed", vr); return;
    }
  } catch (e) { trAdd("ptpge_validate_config failed: " + e, ""); }
  callTool("ptpge_fingerprint", { product: product, bindings: bindings, visuals: true }, "own");
}
// ————— Agent mode (0.27.0): a real model runs the tool loop in the browser —————
// Sponsored runs: the model calls go through engine.gutenlex.com/agent/messages
// (the GutenLex engine holds the key; this server never carries a model). Own-key
// runs go straight from the browser to the provider. In both cases the TOOL
// calls are made by this page against /mcp, so the transcript shows the whole
// conversation an agent has with the specification — nothing is pre-scripted.
const AGENT_PROXY = "https://engine.gutenlex.com";
const AGENT_ROUNDS = 12;
const AGENT_DEFAULT_MODEL = { anthropic: "claude-sonnet-5", openai: "gpt-5.4-mini" };
const AGENT_SYSTEM = [
  "PTPGE-PLAYGROUND-AGENT/1",
  "You are a print-buying agent talking to the PTPGE MCP server — the open vocabulary of print. Turn the buyer's free-text order into ONE validated, fingerprinted configuration, using only the tools. Never invent term URIs: use only URIs the tools return.",
  "Method:",
  "1. Product first: ptpge_search_terms on the product word (limit 5) and take the ordering/products/... hit; then ptpge_get_product_envelope for it — the envelope says which variables and values this product allows.",
  "2. For every attribute in the prompt, ptpge_search_terms (query_language = the prompt's language; language = \\"LANGCODE\\"). Bind only element-level terms, never a group. Each term goes to the variable its tree position implies: configurations/formats → variables/configuration/format; setup-models → variables/configuration/setup-model; features/colors → variables/features/color-mode; surface-finish → variables/features/surface-finish; embellishments → variables/features/embellishment; completions/binding → variables/finishing/binding; paper-surfaces → variables/substrate/substrate-finish; paper-coatings → variables/substrate/substrate-coating; paper-color-shades → variables/substrate/substrate-color; substrates → variables/substrate/substrate-type. Numbers: pages → variables/configuration/page-count; gsm → variables/substrate/substrate-weight (a stated gsm wins over a weight-band word); copies → variables/order/quantity. Add surface: front/back/outside/inside when the prompt says so.",
  "2b. Bind exactly what the buyer stated — no more. Never add a surface the buyer did not name: a face attribute stated without a face (\\"matte lamination\\", \\"full colour\\") is bound WITHOUT surface, and the validator applies it to every face of the setup. Never add an axis the buyer did not state — no substrate-type for \\"silk\\" or \\"170 gsm\\", no default weight, no orientation, no coating: resolution adds what follows from the statement (silk IS paper) by itself. The identity must be a function of the buyer's words, not of your choices; two agents given the same words must reach the same fingerprint.",
  "3. Colour counts and notation (\\"4/4\\", \\"4+1\\", \\"4 colours double-sided\\", \\"black on the back\\") go through ptpge_resolve_color_notation on this product — never guess a colour set. If a surface comes back needs_disambiguation, STOP and return its question verbatim.",
  "4. ptpge_validate_config with product and bindings. If validInEnvelope is false, fix what it names (a surface must be one of the bound setup's faces: flat-sheet front/back, folded-sheet outside/inside, multi-page front-cover…back-cover). If it returns needs_disambiguation (a REQUIRED axis is missing — which fold, which format, how many pages, which binding, which colour on the first face), STOP and return the question(s) verbatim with the candidates — never assume a fold, a size or a colour. When one is missing from the prompt you cannot fingerprint. Pass setup to ptpge_resolve_color_notation so the faces match the fold.",
  "4b. What the buyer does not ask for is not applied (SD-0098): never ask about, suggest or bind a finish, embellishment or other optional axis the buyer did not mention — a configuration without them is complete whenever the envelope's required variables are bound. Ask back only about required variables.",
  "5. Only when complete is true: ptpge_fingerprint with visuals: true. The tool refuses incomplete configurations (error not_fingerprintable) — that refusal is the answer, relay its questions.",
  "Aim for at most 10 tool calls. Final answer: two to four plain sentences in the buyer's language — the product, the bindings, and the spec fingerprint's short id — or the open question.",
].join("\\n");

function agEl(id) { return document.getElementById(id); }
function agModeChange() {
  const m = agEl("ag-mode").value, own = m !== "sponsored";
  agEl("ag-key").style.display = own ? "" : "none";
  agEl("ag-model").style.display = own ? "" : "none";
  if (own) {
    try { agEl("ag-key").value = localStorage.getItem("ptpge-agent-key-" + m) || ""; } catch (e) {}
    let mdl = ""; try { mdl = localStorage.getItem("ptpge-agent-model-" + m) || ""; } catch (e) {}
    agEl("ag-model").value = mdl || AGENT_DEFAULT_MODEL[m];
    agEl("ag-status").textContent = "";
  } else agentStatus();
}
async function agentStatus() {
  const s = agEl("ag-status"); if (!s) return;
  try {
    const r = await fetch(AGENT_PROXY + "/agent/status");
    const j = await r.json();
    s.textContent = j.enabled ? ("sponsored · " + j.model + " · " + j.remaining_today + " run(s) left today")
                              : "sponsored runs are off right now — use your own key";
  } catch (e) { s.textContent = "sponsored runs unreachable — use your own key"; }
}
function agToolsAnthropic(tools) {
  return tools.map(t => ({ name: t.name, description: t.description || "", input_schema: t.inputSchema || { type: "object" } }));
}
function agToolsOpenAI(tools) {
  return tools.map(t => ({ type: "function", function: { name: t.name, description: t.description || "", parameters: t.inputSchema || { type: "object" } } }));
}
async function agCallAnthropic(mode, key, model, system, messages, tools, runId) {
  const sponsored = mode === "sponsored";
  const url = sponsored ? AGENT_PROXY + "/agent/messages" : "https://api.anthropic.com/v1/messages";
  const headers = { "Content-Type": "application/json" };
  if (sponsored) headers["X-Agent-Run"] = runId;
  else { headers["x-api-key"] = key; headers["anthropic-version"] = "2023-06-01"; headers["anthropic-dangerous-direct-browser-access"] = "true"; }
  const body = { max_tokens: 1500, system: system, messages: messages, tools: agToolsAnthropic(tools) };
  if (!sponsored) body.model = model;
  const r = await fetch(url, { method: "POST", headers: headers, body: JSON.stringify(body) });
  const j = await r.json();
  if (!r.ok) throw new Error((j.error && (j.error.message || j.error)) || ("HTTP " + r.status));
  return j;
}
async function agCallOpenAI(key, model, system, messages, tools) {
  const msgs = [{ role: "system", content: system }];
  for (const m of messages) {
    if (m.role === "user") {
      if (typeof m.content === "string") { msgs.push({ role: "user", content: m.content }); continue; }
      for (const b of m.content) {
        if (b.type === "tool_result") msgs.push({ role: "tool", tool_call_id: b.tool_use_id, content: typeof b.content === "string" ? b.content : JSON.stringify(b.content) });
        else if (b.type === "text") msgs.push({ role: "user", content: b.text });
      }
    } else {
      const txt = m.content.filter(b => b.type === "text").map(b => b.text).join("\\n");
      const tcs = m.content.filter(b => b.type === "tool_use").map(b => ({ id: b.id, type: "function", function: { name: b.name, arguments: JSON.stringify(b.input || {}) } }));
      const am = { role: "assistant", content: txt || null }; if (tcs.length) am.tool_calls = tcs; msgs.push(am);
    }
  }
  const r = await fetch("https://api.openai.com/v1/chat/completions", { method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + key },
    body: JSON.stringify({ model: model, messages: msgs, tools: agToolsOpenAI(tools), max_completion_tokens: 1500 }) });
  const j = await r.json();
  if (!r.ok) throw new Error((j.error && j.error.message) || ("HTTP " + r.status));
  const c = j.choices[0].message; const content = [];
  if (c.content) content.push({ type: "text", text: c.content });
  for (const tc of (c.tool_calls || [])) { let inp = {}; try { inp = JSON.parse(tc.function.arguments || "{}"); } catch (e) {} content.push({ type: "tool_use", id: tc.id, name: tc.function.name, input: inp }); }
  return { content: content, stop_reason: (c.tool_calls && c.tool_calls.length) ? "tool_use" : "end_turn",
           usage: j.usage ? { input_tokens: j.usage.prompt_tokens, output_tokens: j.usage.completion_tokens } : undefined };
}
async function agentRun(opts) {
  opts = opts || {};
  const mode = agEl("ag-mode").value, key = (agEl("ag-key").value || "").trim(), model = (agEl("ag-model").value || "").trim();
  const prompt = (opts.prompt || agEl("prompt").value || "").trim(); const lang = opts.lang || agEl("q-lang").value;
  if (!prompt) return null;
  if (mode !== "sponsored" && !key) { agEl("ag-status").textContent = "enter your API key first"; return; }
  if (mode !== "sponsored") { try { localStorage.setItem("ptpge-agent-key-" + mode, key); localStorage.setItem("ptpge-agent-model-" + mode, model); } catch (e) {} }
  const runId = "run-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
  const buttons = document.querySelectorAll("button"); buttons.forEach(b => b.disabled = true);
  showBusy("agent", "agent · tools/list …");
  let rounds = 0, calls = 0, fp = null, finalText = "", stopped = "", lastTool = null;
  try {
    const tl = await rpc("tools/list");
    const tools = (tl.json.result && tl.json.result.tools) || [];
    if (!tools.length) throw new Error("tools/list returned no tools");
    trAdd("tools/list · " + tools.length + " tools handed to the model (" + mode + ")", fmtJson(tools.map(t => t.name)));
    const system = AGENT_SYSTEM.replace("LANGCODE", lang);
    const messages = [{ role: "user", content: prompt }];
    for (; rounds < AGENT_ROUNDS; rounds++) {
      showBusy("agent", "agent · model call " + (rounds + 1) + " …");
      const resp = mode === "openai" ? await agCallOpenAI(key, model, system, messages, tools)
                                     : await agCallAnthropic(mode, key, model, system, messages, tools, runId);
      const blocks = resp.content || [];
      const texts = blocks.filter(b => b.type === "text").map(b => b.text).join("\\n");
      const uses = blocks.filter(b => b.type === "tool_use");
      const u = resp.usage || {};
      trAdd("model → " + (uses.length ? uses.map(x => x.name).join(", ") : "final answer") +
            (u.input_tokens != null ? " · " + u.input_tokens + " in / " + u.output_tokens + " out" : "") +
            (resp._sponsored ? " · sponsored " + resp._sponsored.model : ""),
            fmtJson({ text: texts || undefined, tool_use: uses.length ? uses.map(x => ({ name: x.name, input: x.input })) : undefined }));
      messages.push({ role: "assistant", content: blocks });
      if (resp.stop_reason !== "tool_use" || !uses.length) { finalText = texts; break; }
      const results = [];
      for (const use of uses) {
        showBusy("agent", "agent · tools/call " + use.name + " …");
        const { json, ms, status } = await rpc("tools/call", { name: use.name, arguments: use.input || {} }); calls++;
        let payload = json;
        if (json.result && json.result.content && json.result.content[0]) { try { payload = JSON.parse(json.result.content[0].text); } catch (e) { payload = json.result; } }
        else if (json.error) payload = json;
        let forModel = payload;
        if (use.name === "ptpge_fingerprint" && payload && payload.profiles) {
          fp = payload;
          forModel = JSON.parse(JSON.stringify(payload));
          for (const pr of Object.values(forModel.profiles || {})) { delete pr.markSvg; delete pr.qrSvg; }
        }
        trAdd("tools/call " + use.name + " · HTTP " + status + " · " + ms + " ms · by the agent", fmtJson(payload));
        lastTool = { name: use.name, payload: payload };
        results.push({ type: "tool_result", tool_use_id: use.id, content: JSON.stringify(forModel).slice(0, 24000) });
      }
      messages.push({ role: "user", content: results });
    }
    if (rounds >= AGENT_ROUNDS) stopped = "stopped at the round limit (" + AGENT_ROUNDS + ")";
    const meta = "agent (" + mode + (mode !== "sponsored" && model ? " · " + model : "") + ") · " + Math.min(rounds + 1, AGENT_ROUNDS) +
                 " model call(s) · " + calls + " tool call(s) · " + (fp ? "fingerprint " + fp.profiles.spec.short : "no fingerprint");
    if (fp) showInline("agent", meta, Object.assign({ agent_answer: finalText || undefined }, fp));
    else {
      // No fingerprint. If the model ended without text, the reason is in the last tool
      // result: surface the specification's questions and refusals instead of «(no answer)».
      const why = {};
      if (!finalText && lastTool && lastTool.payload && typeof lastTool.payload === "object") {
        const pl = lastTool.payload;
        why.last_tool = lastTool.name;
        if (Array.isArray(pl.needs_disambiguation) && pl.needs_disambiguation.length)
          why.open_questions = pl.needs_disambiguation.map(q => ({ field: q.field, question: q.question,
            candidates: (q.candidates || []).slice(0, 8).map(c => c.label || c.id) }));
        const bad = (pl.bindings || []).filter(b => b.status === "not_in_envelope");
        if (bad.length) why.not_in_envelope = bad.map(b => ({ variable: b.variable, surface: b.surface || undefined, value: b.value,
            allowed: (b.allowed || []).map(a => a.label || a.id) }));
        const viol = (pl.rules || []).filter(r => r.status === "violation");
        if (viol.length) why.rule_violations = viol.map(r => r.note || r.rule);
        if (pl.error) why.error = pl.error;
      }
      showInline("agent", meta, Object.assign({ agent_answer: finalText || "(the model ended without text)",
        note: stopped || (Object.keys(why).length > 1 ? "the agent stopped before fingerprinting — the specification's last answer is below"
                                                     : "the agent stopped before fingerprinting — its reason is in the answer and the transcript") }, why));
    }
    return { fp: fp, answer: finalText, meta: meta };
  } catch (e) {
    showInline("agent", "agent failed", { error: String(e),
      hint: mode === "sponsored" ? "Sponsored runs may be used up or switched off — choose your own key."
                                 : "Check the key and model. The browser calls the provider directly; a network error here is usually CORS or a wrong key." });
  } finally {
    buttons.forEach(b => b.disabled = false);
    if (mode === "sponsored") agentStatus();
  }
}
agModeChange();

function doEnvelope()    { callTool("ptpge_get_product_envelope", { id_or_path: DEMO_PRODUCT }, "chain"); }
function doValidate()    { callTool("ptpge_validate_config", { product: DEMO_PRODUCT, bindings: DEMO_BINDINGS }, "chain"); }
function doFingerprint() { callTool("ptpge_fingerprint", { product: DEMO_PRODUCT, bindings: DEMO_BINDINGS, visuals: true }, "chain"); }
function preset(v) { document.getElementById("q").value = v; doSearch(); }
function presetUri(v) { document.getElementById("uri").value = v; doGet(); }

document.getElementById("q").addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); });
document.getElementById("uri").addEventListener("keydown", e => { if (e.key === "Enter") doGet(); });

// ————— v2: convergence demo — four products, ten languages —————
const REF_PRODUCT = "ordering/products/brochures";
const REF_ROWS = [
  ["variables/configuration/format",        null,      "printing/configurations/formats/a-series/a5"],
  ["variables/configuration/orientation",   null,      "printing/configurations/orientation/portrait"],
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
function refBindings(rows) {
  return (rows || REF_ROWS).map(r => {
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
  { code: "sv", label: "Svenska",
    phrase: "broschyr, A5, dragspelsfals, 8 sidor, 170 g papper, fyrfärg utvändigt, endast svart invändigt, matt laminat med partiell UV-lack utvändigt, 500 exemplar",
    m: ["A5", "8 sidor", "dragspelsfals", "fyrfärg utvändigt", "endast svart invändigt",
        "matt laminat med partiell UV-lack", "papper", "170 g", "500 exemplar"] },
  { code: "da", label: "Dansk",
    phrase: "brochure, A5, leporellofals, 8 sider, 170 g papir, firfarve udvendigt, kun sort indvendigt, mat laminering med partiel UV-lak udvendigt, 500 eksemplarer",
    m: ["A5", "8 sider", "leporellofals", "firfarve udvendigt", "kun sort indvendigt",
        "mat laminering med partiel UV-lak", "papir", "170 g", "500 eksemplarer"] },
  { code: "nl", label: "Nederlands",
    phrase: "brochure, A5, zigzagvouw, 8 pagina's, 170 grams papier, buitenzijde full colour, binnenzijde alleen zwart, mat laminaat met spot-UV op de buitenzijde, 500 exemplaren",
    m: ["A5", "8 pagina's", "zigzagvouw", "buitenzijde full colour", "binnenzijde alleen zwart",
        "mat laminaat met spot-UV", "papier", "170 grams", "500 exemplaren"] },
  { code: "pl", label: "Polski",
    phrase: "broszura, A5, złam harmonijkowy, 8 stron, papier 170 g, pełny kolor na zewnątrz, wewnątrz tylko czerń, laminowanie matowe z lakierem UV wybiórczym na zewnątrz, 500 egzemplarzy",
    m: ["A5", "8 stron", "złam harmonijkowy", "pełny kolor na zewnątrz", "wewnątrz tylko czerń",
        "laminowanie matowe z lakierem UV wybiórczym", "papier", "170 g", "500 egzemplarzy"] },
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
  { code: "pt", label: "Português",
    phrase: "folheto, A5, dobra sanfona, 8 páginas, papel 170 g, 4 cores por fora, só preto por dentro, laminação fosca com verniz UV localizado por fora, 500 exemplares",
    m: ["A5", "8 páginas", "dobra sanfona", "4 cores por fora", "só preto por dentro",
        "laminação fosca com verniz UV localizado", "papel", "170 g", "500 exemplares"] },
  { code: "hi", label: "हिन्दी",
    phrase: "ब्रोशर, A5, अकॉर्डियन फ़ोल्ड, 8 पृष्ठ, 170 gsm काग़ज़, बाहर फ़ुल कलर, अंदर केवल काला, बाहर मैट लैमिनेशन और स्पॉट UV, 500 प्रतियाँ",
    m: ["A5", "8 पृष्ठ", "अकॉर्डियन फ़ोल्ड", "बाहर फ़ुल कलर", "अंदर केवल काला",
        "मैट लैमिनेशन और स्पॉट UV", "काग़ज़", "170 gsm", "500 प्रतियाँ"] },
];
let CONV_HISTORY = [];

// Business cards — flat-sheet setup (front/back surfaces)
const BC_ROWS = [
  ["variables/configuration/format",       null,    "printing/configurations/formats/business-cards/business-card-eu"],
  ["variables/configuration/setup-model",  null,    "printing/configurations/setup-models/flat-sheet"],
  ["variables/features/color-mode",        "front", "printing/features/colors/cmyk"],
  ["variables/features/color-mode",        "back",  "printing/features/colors/black"],
  ["variables/substrate/substrate-type",   null,    "printing/substrates/sheet-materials/paper"],
  ["variables/substrate/substrate-weight", null,    350],
  ["variables/order/quantity",             null,    100],
];
const BC_LANGS = [
  { code:"en", label:"English",
    phrase:"business cards, EU size, flat sheet, full colour front, black on the back, card stock 350 gsm, 100 pcs",
    m:["EU size","flat sheet","full colour front","black on the back","card stock","350 gsm","100 pcs"] },
  { code:"nb", label:"Norsk",
    phrase:"visittkort, EU-format, flatt ark, full farge foran, sort bak, kartong 350 g, 100 stk",
    m:["EU-format","flatt ark","full farge foran","sort bak","kartong","350 g","100 stk"] },
  { code:"sv", label:"Svenska",
    phrase:"visitkort, EU-format, plant ark, fyrfärg framsida, svart baksida, kartong 350 g, 100 st",
    m:["EU-format","plant ark","fyrfärg framsida","svart baksida","kartong","350 g","100 st"] },
  { code:"da", label:"Dansk",
    phrase:"visitkort, EU-format, fladt ark, firfarve forside, sort bagside, karton 350 g, 100 stk.",
    m:["EU-format","fladt ark","firfarve forside","sort bagside","karton","350 g","100 stk."] },
  { code:"nl", label:"Nederlands",
    phrase:"visitekaartjes, EU-formaat, vlak vel, voorzijde full colour, achterzijde zwart, karton 350 grams, 100 stuks",
    m:["EU-formaat","vlak vel","voorzijde full colour","achterzijde zwart","karton","350 grams","100 stuks"] },
  { code:"pl", label:"Polski",
    phrase:"wizytówki, format EU, arkusz płaski, awers w pełnym kolorze, rewers czarny, karton 350 g, 100 szt.",
    m:["format EU","arkusz płaski","awers w pełnym kolorze","rewers czarny","karton","350 g","100 szt."] },
  { code:"de", label:"Deutsch",
    phrase:"Visitenkarten, EU-Format, Planobogen, vorne 4-farbig, hinten schwarz, Karton 350 g, 100 Stück",
    m:["EU-Format","Planobogen","vorne 4-farbig","hinten schwarz","Karton","350 g","100 Stück"] },
  { code:"es", label:"Español",
    phrase:"tarjetas de visita, formato UE, hoja plana, color por delante, negro por detrás, cartulina 350 g, 100 uds",
    m:["formato UE","hoja plana","color por delante","negro por detrás","cartulina","350 g","100 uds"] },
  { code:"ja", label:"日本語",
    phrase:"名刺、EUサイズ、平判、表フルカラー、裏モノクロ、カード紙350gsm、100枚",
    m:["EUサイズ","平判","表フルカラー","裏モノクロ","カード紙","350gsm","100枚"] },
  { code:"zh-Hans", label:"中文",
    phrase:"名片，EU尺寸，平张，正面四色，背面单黑，卡纸350克，100张",
    m:["EU尺寸","平张","正面四色","背面单黑","卡纸","350克","100张"] },
  { code:"pt", label:"Português",
    phrase:"cartões de visita, formato EU, folha plana, 4 cores na frente, preto no verso, cartão 350 g, 100 un.",
    m:["formato EU","folha plana","4 cores na frente","preto no verso","cartão","350 g","100 un."] },
  { code:"hi", label:"हिन्दी",
    phrase:"विज़िटिंग कार्ड, EU साइज़, फ़्लैट शीट, सामने फ़ुल कलर, पीछे काला, कार्ड स्टॉक 350 gsm, 100 पीस",
    m:["EU साइज़","फ़्लैट शीट","सामने फ़ुल कलर","पीछे काला","कार्ड स्टॉक","350 gsm","100 पीस"] },
];
// Booklet — multi-page setup (cover + inside surfaces, saddle-stitched).
// NB: separate cover stock (250 g gloss) is a per-PART binding — reserved
// for compound products (SD-0037); v1 has a single implicit part, so the
// cover paper stays out of the fingerprint until cfs supports @part.surface.
const BK_ROWS = [
  ["variables/configuration/format",       null, "printing/configurations/formats/a-series/a5"],
  ["variables/configuration/page-count",   null, 16],
  ["variables/configuration/setup-model",  null, "printing/configurations/setup-models/multi-page"],
  ["variables/features/color-mode",        "inside-pages",      "printing/features/colors/black"],
  ["variables/features/color-mode",        "front-cover",       "printing/features/colors/cmyk"],
  ["variables/features/color-mode",        "back-cover",        "printing/features/colors/cmyk"],
  ["variables/features/color-mode",        "inside-front-cover","printing/features/colors/black"],
  ["variables/features/color-mode",        "inside-back-cover", "printing/features/colors/black"],
  ["variables/substrate/substrate-type",   null, "printing/substrates/sheet-materials/paper"],
  ["variables/substrate/substrate-finish", null, "printing/substrates/sheet-materials/paper/paper-surfaces/matte-paper"],
  ["variables/substrate/substrate-weight", null, 130],
  ["variables/finishing/binding",          null, "printing/completions/binding/saddle-stitching"],
  ["variables/order/quantity",             null, 250],
];
const BK_LANGS = [
  { code:"en", label:"English",
    phrase:"booklet, A5, 16 pages, black only on both sides inside, matte paper 130 gsm, cover full colour outside and black inside, folded and saddle-stitched, 250 copies",
    m:["A5","16 pages","booklet","black on both sides inside","cover full colour outside","cover full colour outside","cover black inside","cover black inside","paper","matte","130 gsm","folded and saddle-stitched","250 copies"] },
  { code:"nb", label:"Norsk",
    phrase:"hefte, A5, 16 sider, sort på begge sider innvendig, matt papir 130 g, omslag med fullfarge utvendig og sort innvendig, falset og stiftet, 250 eksemplarer",
    m:["A5","16 sider","hefte","sort på begge sider innvendig","omslag fullfarge utvendig","omslag fullfarge utvendig","omslag sort innvendig","omslag sort innvendig","papir","matt","130 g","falset og stiftet","250 eksemplarer"] },
  { code:"sv", label:"Svenska",
    phrase:"häfte, A5, 16 sidor, svart på båda sidor invändigt, matt papper 130 g, omslag i fyrfärg utvändigt och svart invändigt, falsat och klammerhäftat, 250 exemplar",
    m:["A5","16 sidor","häfte","svart på båda sidor invändigt","omslag fyrfärg utvändigt","omslag fyrfärg utvändigt","omslag svart invändigt","omslag svart invändigt","papper","matt","130 g","falsat och klammerhäftat","250 exemplar"] },
  { code:"da", label:"Dansk",
    phrase:"hæfte, A5, 16 sider, sort på begge sider indvendigt, mat papir 130 g, omslag i firfarve udvendigt og sort indvendigt, falset og klammerhæftet, 250 eksemplarer",
    m:["A5","16 sider","hæfte","sort på begge sider indvendigt","omslag firfarve udvendigt","omslag firfarve udvendigt","omslag sort indvendigt","omslag sort indvendigt","papir","mat","130 g","falset og klammerhæftet","250 eksemplarer"] },
  { code:"nl", label:"Nederlands",
    phrase:"boekje, A5, 16 pagina's, binnenwerk beide zijden zwart, mat papier 130 grams, omslag buitenzijde full colour en binnenzijde zwart, gevouwen en geniet, 250 exemplaren",
    m:["A5","16 pagina's","boekje","binnenwerk beide zijden zwart","omslag buitenzijde full colour","omslag buitenzijde full colour","omslag binnenzijde zwart","omslag binnenzijde zwart","papier","mat","130 grams","gevouwen en geniet","250 exemplaren"] },
  { code:"pl", label:"Polski",
    phrase:"książeczka, A5, 16 stron, wnętrze czarne po obu stronach, papier matowy 130 g, okładka w pełnym kolorze na zewnątrz i czarna wewnątrz, złożona i zszywana zeszytowo, 250 egzemplarzy",
    m:["A5","16 stron","książeczka","wnętrze czarne po obu stronach","okładka w pełnym kolorze na zewnątrz","okładka w pełnym kolorze na zewnątrz","okładka czarna wewnątrz","okładka czarna wewnątrz","papier","matowy","130 g","złożona i zszywana zeszytowo","250 egzemplarzy"] },
  { code:"de", label:"Deutsch",
    phrase:"Heft, A5, 16 Seiten, innen beidseitig schwarz, mattes Papier 130 g, Umschlag außen 4-farbig und innen schwarz, gefalzt und drahtgeheftet, 250 Exemplare",
    m:["A5","16 Seiten","Heft","innen beidseitig schwarz","Umschlag außen 4-farbig","Umschlag außen 4-farbig","Umschlag innen schwarz","Umschlag innen schwarz","Papier","matt","130 g","gefalzt und drahtgeheftet","250 Exemplare"] },
  { code:"es", label:"Español",
    phrase:"cuadernillo, A5, 16 páginas, interior en negro a dos caras, papel mate de 130 g, cubierta a todo color por fuera y negro por dentro, plegado y grapado a caballete, 250 ejemplares",
    m:["A5","16 páginas","cuadernillo","interior en negro a dos caras","cubierta a todo color por fuera","cubierta a todo color por fuera","cubierta negro por dentro","cubierta negro por dentro","papel","mate","130 g","plegado y grapado a caballete","250 ejemplares"] },
  { code:"ja", label:"日本語",
    phrase:"冊子、A5、16ページ、本文両面モノクロ、マット紙130gsm、表紙は外側フルカラー・内側モノクロ、折り加工と中綴じ、250部",
    m:["A5","16ページ","冊子","本文両面モノクロ","表紙外側フルカラー","表紙外側フルカラー","表紙内側モノクロ","表紙内側モノクロ","用紙","マット","130gsm","折り加工と中綴じ","250部"] },
  { code:"zh-Hans", label:"中文",
    phrase:"小册子，A5，16页，内页双面单黑，哑光纸130克，封面外侧四色、内侧单黑，折页并骑马钉，250份",
    m:["A5","16页","小册子","内页双面单黑","封面外侧四色","封面外侧四色","封面内侧单黑","封面内侧单黑","纸张","哑光","130克","折页并骑马钉","250份"] },
  { code:"pt", label:"Português",
    phrase:"brochura, A5, 16 páginas, só preto nos dois lados no miolo, papel fosco 130 g, capa 4 cores por fora e preto por dentro, dobrada e grampeada, 250 exemplares",
    m:["A5","16 páginas","brochura","só preto nos dois lados no miolo","capa 4 cores por fora","capa 4 cores por fora","capa preto por dentro","capa preto por dentro","papel","fosco","130 g","dobrada e grampeada","250 exemplares"] },
  { code:"hi", label:"हिन्दी",
    phrase:"बुकलेट, A5, 16 पृष्ठ, अंदर दोनों ओर केवल काला, मैट काग़ज़ 130 gsm, कवर बाहर फ़ुल कलर और अंदर काला, मोड़कर सैडल-स्टिच, 250 प्रतियाँ",
    m:["A5","16 पृष्ठ","बुकलेट","अंदर दोनों ओर केवल काला","कवर बाहर फ़ुल कलर","कवर बाहर फ़ुल कलर","कवर अंदर काला","कवर अंदर काला","काग़ज़","मैट","130 gsm","मोड़कर सैडल-स्टिच","250 प्रतियाँ"] },
];
// Panel print — rigid board, custom size (SD-0066) + thickness (SD-0070)
const PP_ROWS = [
  ["variables/configuration/format",        null,    "printing/configurations/formats/customized"],
  ["variables/configuration/custom-width",  null,    700],
  ["variables/configuration/custom-height", null,    1000],
  ["variables/configuration/orientation",   null,    "printing/configurations/orientation/portrait"],
  ["variables/configuration/setup-model",   null,    "printing/configurations/setup-models/flat-sheet"],
  ["variables/features/color-mode",         "front", "printing/features/colors/cmyk"],
  ["variables/substrate/substrate-type",    null,    "printing/substrates/board-materials/foam"],
  ["variables/substrate/substrate-thickness", null,  5],
  ["variables/order/quantity",              null,    3],
];
const PP_LANGS = [
  { code:"en", label:"English",
    phrase:"panel prints, custom size 70 \u00d7 100 cm, portrait, flat panel, full colour on the front, 5 mm foam board, 3 pcs",
    m:["custom size","70","100","portrait","flat panel","full colour on the front","foam board","5 mm","3 pcs"] },
  { code:"nb", label:"Norsk",
    phrase:"panelbilder, spesialm\u00e5l 70 \u00d7 100 cm, st\u00e5ende, flat plate, full farge p\u00e5 forsiden, 5 mm skumplate, 3 stk",
    m:["spesialm\u00e5l","70","100","st\u00e5ende","flat plate","full farge p\u00e5 forsiden","skumplate","5 mm","3 stk"] },
  { code:"sv", label:"Svenska",
    phrase:"paneltryck, specialm\u00e5tt 70 \u00d7 100 cm, st\u00e5ende, plan skiva, fyrf\u00e4rg p\u00e5 framsidan, 5 mm skumskiva, 3 st",
    m:["specialm\u00e5tt","70","100","st\u00e5ende","plan skiva","fyrf\u00e4rg p\u00e5 framsidan","skumskiva","5 mm","3 st"] },
  { code:"da", label:"Dansk",
    phrase:"paneltryk, specialm\u00e5l 70 \u00d7 100 cm, st\u00e5ende, flad plade, firfarve p\u00e5 forsiden, 5 mm skumplade, 3 stk.",
    m:["specialm\u00e5l","70","100","st\u00e5ende","flad plade","firfarve p\u00e5 forsiden","skumplade","5 mm","3 stk."] },
  { code:"nl", label:"Nederlands",
    phrase:"paneelprints, aangepast formaat 70 \u00d7 100 cm, staand, vlak paneel, full colour op de voorzijde, 5 mm schuimplaat, 3 stuks",
    m:["aangepast formaat","70","100","staand","vlak paneel","full colour op de voorzijde","schuimplaat","5 mm","3 stuks"] },
  { code:"pl", label:"Polski",
    phrase:"wydruki na panelach, format niestandardowy 70 \u00d7 100 cm, pionowo, płaski panel, pełny kolor na awersie, płyta piankowa 5 mm, 3 szt.",
    m:["format niestandardowy","70","100","pionowo","płaski panel","pełny kolor na awersie","płyta piankowa","5 mm","3 szt."] },
  { code:"de", label:"Deutsch",
    phrase:"Paneldrucke, Sonderma\u00df 70 \u00d7 100 cm, Hochformat, plane Platte, vorne 4-farbig, 5 mm Schaumplatte, 3 St\u00fcck",
    m:["Sonderma\u00df","70","100","Hochformat","plane Platte","vorne 4-farbig","Schaumplatte","5 mm","3 St\u00fcck"] },
  { code:"es", label:"Espa\u00f1ol",
    phrase:"impresiones en panel, medida personalizada 70 \u00d7 100 cm, vertical, panel plano, todo color por delante, cart\u00f3n pluma de 5 mm, 3 uds",
    m:["medida personalizada","70","100","vertical","panel plano","todo color por delante","cart\u00f3n pluma","5 mm","3 uds"] },
  { code:"ja", label:"\u65e5\u672c\u8a9e",
    phrase:"\u30d1\u30cd\u30eb\u30d7\u30ea\u30f3\u30c8\u3001\u30ab\u30b9\u30bf\u30e0\u30b5\u30a4\u30ba70\u00d7100cm\u3001\u7e26\u5411\u304d\u3001\u5e73\u677f\u3001\u8868\u9762\u30d5\u30eb\u30ab\u30e9\u30fc\u30015mm\u30d5\u30a9\u30fc\u30e0\u30dc\u30fc\u30c9\u30013\u679a",
    m:["\u30ab\u30b9\u30bf\u30e0\u30b5\u30a4\u30ba","70","100","\u7e26\u5411\u304d","\u5e73\u677f","\u8868\u9762\u30d5\u30eb\u30ab\u30e9\u30fc","\u30d5\u30a9\u30fc\u30e0\u30dc\u30fc\u30c9","5mm","3\u679a"] },
  { code:"zh-Hans", label:"\u4e2d\u6587",
    phrase:"\u9762\u677f\u6253\u5370\uff0c\u81ea\u5b9a\u4e49\u5c3a\u5bf870\u00d7100\u5398\u7c73\uff0c\u7ad6\u5411\uff0c\u5e73\u677f\uff0c\u6b63\u9762\u56db\u8272\uff0c5\u6beb\u7c73\u6ce1\u6cab\u677f\uff0c3\u5757",
    m:["\u81ea\u5b9a\u4e49\u5c3a\u5bf8","70","100","\u7ad6\u5411","\u5e73\u677f","\u6b63\u9762\u56db\u8272","\u6ce1\u6cab\u677f","5\u6beb\u7c73","3\u5757"] },
  { code:"pt", label:"Português",
    phrase:"painéis impressos, formato personalizado 70 \u00d7 100 cm, retrato, painel plano, 4 cores na frente, foam board 5 mm, 3 un.",
    m:["formato personalizado","70","100","retrato","painel plano","4 cores na frente","foam board","5 mm","3 un."] },
  { code:"hi", label:"हिन्दी",
    phrase:"पैनल प्रिंट, कस्टम साइज़ 70 \u00d7 100 cm, पोर्ट्रेट, फ़्लैट पैनल, सामने फ़ुल कलर, 5 mm फ़ोम बोर्ड, 3 पीस",
    m:["कस्टम साइज़","70","100","पोर्ट्रेट","फ़्लैट पैनल","सामने फ़ुल कलर","फ़ोम बोर्ड","5 mm","3 पीस"] },
];
const PRODUCTS = [
  { product: REF_PRODUCT,                        rows: REF_ROWS, langs: null },  // langs settes under (CONV)
  { product: "ordering/products/business-cards", rows: BC_ROWS,  langs: BC_LANGS },
  { product: "ordering/products/booklets",       rows: BK_ROWS,  langs: BK_LANGS },
  { product: "ordering/products/panel-prints",   rows: PP_ROWS,  langs: PP_LANGS },
];
let CUR_PROD = 0;
function prodSelect(i) {
  CUR_PROD = i;
  CONV_HISTORY = [];
  document.getElementById("conv-hist").style.display = "none";
  document.getElementById("conv-hist-t").innerHTML = "";
  document.getElementById("conv-out").innerHTML = "";
  document.getElementById("conv-tgl").style.display = "none";
  document.querySelectorAll("#prod-btns button").forEach((b, k) =>
    b.classList.toggle("on", k === i));
  document.querySelectorAll("#conv-btns button").forEach(b => b.classList.remove("on"));
}
function renderProdBtns() {
  const el = document.getElementById("prod-btns");
  if (!el) return;
  el.innerHTML = [convTT("p1"), convTT("p2"), convTT("p3"), convTT("p4")].map((n, i) =>
    '<button data-p="' + i + '">' + n + '</button>').join("");
  document.querySelectorAll("#prod-btns button").forEach((b, k) => {
    b.addEventListener("click", () => prodSelect(k));
    b.classList.toggle("on", k === CUR_PROD);
  });
}

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
  const P = PRODUCTS[CUR_PROD];
  const L = P.langs[idx];
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
  P.rows.forEach(r => {
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
  P.rows.forEach((r, i) => {
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
  const fp = await toolQ("ptpge_fingerprint", { product: P.product, bindings: refBindings(P.rows), visuals: true });
  const spec = fp.profiles.spec, offer = fp.profiles.offer;
  document.getElementById("cv3").innerHTML =
    '<div class="stage"><span class="slbl"><span class="num">03</span>' + t("s03") +
    '<span class="tag">ptpge-cfs/1</span>' +
    '<span class="tag" id="cv3-reset" style="background:#eef4f0;color:#1f4a35;cursor:pointer">reset</span></span>' +
    '<div class="mono canedit" id="cv3-canon" contenteditable="true" spellcheck="false" style="color:#555"></div>' +
    '<div class="hint">' + t("ed_hint") + '</div></div>';
  document.getElementById("cv3-canon").textContent = spec.canonical;
  document.getElementById("cv4").innerHTML =
    '<div class="stage"><span class="slbl"><span class="num">04</span>SHA-256' +
    '<span class="tag">' + t("tag04") + '</span></span>' +
    '<div class="mono hashok" id="cv4-hash">' + spec.sha256 + '</div>' +
    '<div class="hint" id="cv4-note"></div></div>';
  // Live re-hash while editing: same deterministic function, in the browser.
  (function wireEdit(orig, origHash) {
    const canonEl = document.getElementById("cv3-canon");
    const hashEl = document.getElementById("cv4-hash");
    const noteEl = document.getElementById("cv4-note");
    async function reHash() {
      const txt = canonEl.textContent;
      if (txt === orig) {
        hashEl.textContent = origHash;
        hashEl.className = "mono hashok";
        noteEl.textContent = "\\u2713 " + t("same");
        document.getElementById("cv5").classList.remove("stale");
        return;
      }
      const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(txt));
      hashEl.textContent = Array.from(new Uint8Array(buf))
        .map(x => x.toString(16).padStart(2, "0")).join("");
      hashEl.className = "mono hashbad";
      noteEl.textContent = "\\u2717 " + t("ed_diff");
      document.getElementById("cv5").classList.add("stale");
    }
    canonEl.addEventListener("input", reHash);
    document.getElementById("cv3-reset").addEventListener("click", () => {
      canonEl.textContent = orig;
      reHash();
    });
  })(spec.canonical, spec.sha256);
  document.getElementById("cv5").innerHTML =
    '<div class="stage"><span class="slbl"><span class="num">05</span>' + t("s05") + '</span>' +
    '<div style="display:flex;gap:22px;align-items:center;flex-wrap:wrap;margin-top:8px">' +
    (spec.markSvg ? '<div class="vis" style="width:88px">' + spec.markSvg + '</div>' : '') +
    (spec.qrSvg ? '<div class="vis" style="width:88px">' + spec.qrSvg + '</div>' : '') +
    '<div><div class="mono" style="font-size:17px;font-weight:700">' + spec.short + '</div>' +
    '<a href="' + spec.resolverUrl + '" target="_blank" rel="noopener">' + t("resolver") + '</a>' +
    '<div class="hint">offer (+ quantity): <span class="mono">' + offer.short +
    '</span> · <a href="' + offer.resolverUrl + '" target="_blank" rel="noopener">/f/…</a></div>' +
    '<div style="margin-top:8px"><button class="secondary" onclick="convVerify(' + idx + ', &quot;' + spec.short + '&quot;)" id="cv-verify">' + t("verify") + '</button> <span id="cv-verify-out" style="font-size:12px;color:#5b7a69"></span></div>' +
    '</div></div></div>';
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
// SD-0083: the preset is assembled by rule; a real model gets the same phrase and the
// same tools and must land on the same identity — or say why not.
async function convVerify(idx, presetShort) {
  const P = PRODUCTS[CUR_PROD]; const L = P.langs[idx];
  const out = document.getElementById("cv-verify-out"); const btn = document.getElementById("cv-verify");
  const t = key => (UI[CUR_LANG] && UI[CUR_LANG][key]) || UI.en[key];
  if (btn) btn.disabled = true; if (out) out.textContent = t("verifying");
  try {
    const r = await agentRun({ prompt: L.phrase, lang: L.code });
    if (!r) { if (out) out.textContent = ""; return; }
    if (r.fp && r.fp.profiles.spec.short === presetShort) out.innerHTML = '<span class="same">✓ ' + t("verify_same") + ' · ' + escH(r.fp.profiles.spec.short) + '</span>';
    else if (r.fp) out.innerHTML = '<span style="color:#b3261e">✗ ' + t("verify_diff") + ' ' + escH(r.fp.profiles.spec.short) + '</span> — ' + t("verify_see");
    else out.innerHTML = '<span style="color:#b3261e">' + t("verify_asked") + '</span> — ' + escH((r.answer || "").slice(0, 160));
  } catch (e) { if (out) out.textContent = String(e); }
  finally { if (btn) btn.disabled = false; }
}
PRODUCTS[0].langs = CONV;
document.getElementById("conv-btns").innerHTML = CONV.map((L, i) =>
  '<button onclick="convRun(' + i + ')">' + L.label + '</button>').join("");

// ————— v2: 13-language UI (same set as gutenlex.org) —————
const LANG_NAMES = [["en","English","🇬🇧"],["de","Deutsch","🇩🇪"],["nb","Norsk","🇳🇴"],["nl","Nederlands","🇳🇱"],
  ["sv","Svenska","🇸🇪"],["da","Dansk","🇩🇰"],["fi","Suomi","🇫🇮"],["is","Íslenska","🇮🇸"],["fr","Français","🇫🇷"],
  ["pl","Polski","🇵🇱"],["es","Español","🇪🇸"],["ja","日本語","🇯🇵"],["zh","中文","🇨🇳"],["pt","Português","🇵🇹"],["hi","हिन्दी","🇮🇳"]];
let CUR_LANG = "en";
const UI = {
en: { s01:"Raw specification", s02:"Matched against the vocabulary",
  tag02:"pre-scripted — the agent's job", s03:"Canonical form", tag04:"deterministic function, not the model",
  s05:"Identity", live:"checked live", resolver:"resolves on the public register ↗",
  same:"same identity", "try":"Try:",
  verify:"Verify with a real model →", verifying:"a real model is running the same phrase with the same tools…", verify_same:"same identity — rule and model agree", verify_diff:"the model landed on", verify_see:"see Agent mode below for its reasoning", verify_asked:"the model asked a question instead of assuming — see Agent mode below", b_col:"collapse", b_exp:"expand", p1:"Brochure", p2:"Business cards", p3:"Booklet", p4:"Panel print", ed_hint:"Try editing a character in the canonical form — the SHA-256 recomputes live in your browser. Restore it and the identity comes back.", ed_diff:"different bytes — different identity" },
de: { sub:"Jeder Button sendet einen echten MCP-<code>tools/call</code> (JSON-RPC über Streamable HTTP) an <code>/mcp</code> — genau wie ein KI-Agent.",
  t_conv:"Gleiches Produkt · jede Sprache · ein Fingerprint",
  i_conv:"Vier echte Produkte, vier Aufbau-Modelle — Broschüre (Falzbogen), Visitenkarten (Planobogen), Heft (mehrseitig) und Paneldruck (Sondermaß auf Platte) — je in zwölf Sprachen formuliert. Wählen Sie Produkt und Sprache und sehen Sie dieselbe Identität entstehen.",
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
  b_search:"Suchen", b_get:"Begriff abrufen", b_resolve:"Phrasen auflösen", b_fp:"Fingerprint → Marke + QR", b_col:"einklappen", b_exp:"ausklappen", p1:"Broschüre", p2:"Visitenkarten", p3:"Heft", p4:"Paneldruck", ed_hint:"Ändern Sie ein Zeichen der kanonischen Form — SHA-256 wird live im Browser neu berechnet. Stellen Sie es wieder her, und die Identität kehrt zurück.", ed_diff:"andere Bytes — andere Identität",
  e_search:"Eine Käuferphrase in einer von zwölf Sprachen eingeben — zurück kommt der kanonische Begriff mit permanenter URI.", e_get:"Eine URI hinein — voller Kontext heraus: Labels in allen Sprachen, Definition, Platz im Baum.", e_ver:"Mit welcher Daten- und Serverversion dieses Playground spricht.", e_chain:"Envelope → Validierung → Fingerprint an einem festen Beispielauftrag — die ganze Reise in drei Klicks.", e_own:"Beschreiben Sie einen Druckauftrag in eigenen Worten — und sehen Sie, was auf die Spezifikation abbildet.", tr_t:"Sitzungsprotokoll — jeder MCP-Aufruf dieser Seite", tr_clear:"leeren", tr_e:"Noch keine Aufrufe. Jeder Button protokolliert Request und Antwort hier, chronologisch — das Gespräch, das ein KI-Agent mit diesem Server führen würde.", e_conv:"Vier echte Produkte in zwölf Sprachen — sehen Sie dieselbe Identität live entstehen." },
nb: { sub:"Hver knapp sender et ekte MCP-<code>tools/call</code> (JSON-RPC over Streamable HTTP) til <code>/mcp</code> — akkurat som en KI-agent.",
  t_conv:"Samme produkt · alle språk · ett fingerprint",
  i_conv:"Fire ekte produkter, fire setup-modeller — brosjyre (falset ark), visittkort (flatt ark), hefte (flersidig) og panelbilde (spesialmål på plate) — hver formulert på tolv språk. Velg produkt og språk, og se samme identitet vokse frem.",
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
  b_search:"Søk", b_get:"Hent term", b_resolve:"Løs opp fraser", b_fp:"Fingerprint → merke + QR", b_col:"skjul", b_exp:"vis", p1:"Brosjyre", p2:"Visittkort", p3:"Hefte", p4:"Panelbilde", ed_hint:"Prøv å endre et tegn i den kanoniske formen — SHA-256 beregnes på nytt i nettleseren. Gjenopprett, og identiteten kommer tilbake.", ed_diff:"andre bytes — annen identitet",
  e_search:"Skriv en kjøperfrase på ett av tolv språk — få den kanoniske termen med permanent URI.", e_get:"Én URI inn — full kontekst ut: etiketter på alle språk, definisjon, plass i treet.", e_ver:"Hvilken data- og serverversjon denne playgrounden snakker med.", e_chain:"Envelope → validering → fingerprint på et fast eksempel — hele reisen i tre klikk.", e_own:"Beskriv en trykksak med egne ord — og se hva som treffer spesifikasjonen.", tr_t:"Sesjonstranskript — alle MCP-kall denne siden har gjort", tr_clear:"tøm", tr_e:"Ingen kall ennå. Hver knapp logger forespørsel og svar her, kronologisk — samtalen en KI-agent ville hatt med denne serveren.", e_conv:"Fire ekte produkter på tolv språk — se samme identitet vokse frem, live." },
nl: { sub:"Elke knop stuurt een echte MCP-<code>tools/call</code> (JSON-RPC over Streamable HTTP) naar <code>/mcp</code> — precies wat een AI-agent doet.",
  t_conv:"Zelfde product · elke taal · één fingerprint",
  i_conv:"Vier echte producten, vier opzetmodellen — brochure (gevouwen vel), visitekaartjes (vlak vel), boekje (meerpagina) en paneelprint (aangepast formaat op plaat) — elk in twaalf talen. Kies product en taal en zie dezelfde identiteit ontstaan.",
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
  b_search:"Zoeken", b_get:"Term ophalen", b_resolve:"Zinnen oplossen", b_fp:"Fingerprint → merk + QR", b_col:"inklappen", b_exp:"uitklappen", p1:"Brochure", p2:"Visitekaartjes", p3:"Boekje", p4:"Paneelprint", ed_hint:"Wijzig een teken in de canonieke vorm — de SHA-256 wordt live in uw browser herberekend. Herstel het en de identiteit keert terug.", ed_diff:"andere bytes — andere identiteit",
  e_search:"Typ een inkoopfrase in een van twaalf talen — krijg de canonieke term met permanente URI.", e_get:"Eén URI erin — volledige context eruit: labels in alle talen, definitie, plek in de boom.", e_ver:"Met welke data- en serverversie dit playground praat.", e_chain:"Envelope → validatie → fingerprint op een vast voorbeeld — de hele reis in drie klikken.", e_own:"Beschrijf een drukwerkopdracht in eigen woorden — en zie wat op de specificatie afbeeldt.", tr_t:"Sessietranscript — elke MCP-aanroep van deze pagina", tr_clear:"wissen", tr_e:"Nog geen aanroepen. Elke knop logt verzoek en antwoord hier, chronologisch — het gesprek dat een AI-agent met deze server zou voeren.", e_conv:"Vier echte producten in twaalf talen — zie dezelfde identiteit live ontstaan." },
sv: { sub:"Varje knapp skickar ett äkta MCP-<code>tools/call</code> (JSON-RPC över Streamable HTTP) till <code>/mcp</code> — precis som en AI-agent.",
  t_conv:"Samma produkt · alla språk · ett fingerprint",
  i_conv:"Fyra riktiga produkter, fyra uppläggsmodeller — broschyr (falsat ark), visitkort (plant ark), häfte (flersidigt) och paneltryck (specialmått på skiva) — var och en på tolv språk. Välj produkt och språk och se samma identitet växa fram.",
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
  b_search:"Sök", b_get:"Hämta term", b_resolve:"Lös upp fraser", b_fp:"Fingerprint → märke + QR", b_col:"fäll ihop", b_exp:"fäll ut", p1:"Broschyr", p2:"Visitkort", p3:"Häfte", p4:"Paneltryck", ed_hint:"Ändra ett tecken i den kanoniska formen — SHA-256 räknas om live i webbläsaren. Återställ, och identiteten kommer tillbaka.", ed_diff:"andra bytes — annan identitet",
  e_search:"Skriv en köparfras på ett av tolv språk — få den kanoniska termen med permanent URI.", e_get:"En URI in — full kontext ut: etiketter på alla språk, definition, plats i trädet.", e_ver:"Vilken data- och serverversion denna playground pratar med.", e_chain:"Envelope → validering → fingerprint på ett fast exempel — hela resan i tre klick.", e_own:"Beskriv ett tryckjobb med egna ord — och se vad som träffar specifikationen.", tr_t:"Sessionsutskrift — alla MCP-anrop denna sida gjort", tr_clear:"rensa", tr_e:"Inga anrop ännu. Varje knapp loggar förfrågan och svar här, kronologiskt — samtalet en AI-agent skulle föra med denna server.", e_conv:"Fyra riktiga produkter på tolv språk — se samma identitet växa fram, live." },
da: { sub:"Hver knap sender et ægte MCP-<code>tools/call</code> (JSON-RPC over Streamable HTTP) til <code>/mcp</code> — præcis som en AI-agent.",
  t_conv:"Samme produkt · alle sprog · ét fingerprint",
  i_conv:"Fire rigtige produkter, fire opsætningsmodeller — brochure (falset ark), visitkort (fladt ark), hæfte (flersidet) og paneltryk (specialmål på plade) — hver på tolv sprog. Vælg produkt og sprog, og se den samme identitet opstå.",
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
  b_search:"Søg", b_get:"Hent term", b_resolve:"Opløs fraser", b_fp:"Fingerprint → mærke + QR", b_col:"fold sammen", b_exp:"fold ud", p1:"Brochure", p2:"Visitkort", p3:"Hæfte", p4:"Paneltryk", ed_hint:"Ændr et tegn i den kanoniske form — SHA-256 genberegnes live i browseren. Gendan, og identiteten vender tilbage.", ed_diff:"andre bytes — anden identitet",
  e_search:"Skriv en køberfrase på et af tolv sprog — få den kanoniske term med permanent URI.", e_get:"Én URI ind — fuld kontekst ud: etiketter på alle sprog, definition, plads i træet.", e_ver:"Hvilken data- og serverversion denne playground taler med.", e_chain:"Envelope → validering → fingerprint på et fast eksempel — hele rejsen i tre klik.", e_own:"Beskriv en tryksag med egne ord — og se hvad der rammer specifikationen.", tr_t:"Sessionsudskrift — alle MCP-kald denne side har lavet", tr_clear:"ryd", tr_e:"Ingen kald endnu. Hver knap logger forespørgsel og svar her, kronologisk — samtalen en AI-agent ville føre med denne server.", e_conv:"Fire ægte produkter på tolv sprog — se samme identitet opstå, live." },
fi: { sub:"Jokainen painike lähettää aidon MCP-<code>tools/call</code>-kutsun (JSON-RPC, Streamable HTTP) osoitteeseen <code>/mcp</code> — täsmälleen kuten tekoälyagentti.",
  t_conv:"Sama tuote · kaikki kielet · yksi sormenjälki",
  i_conv:"Neljä oikeaa tuotetta, neljä rakennemallia — esite (taitettu arkki), käyntikortit (tasainen arkki), vihko (monisivuinen) ja paneelituloste (erikoismitta levylle) — kukin kahdellatoista kielellä. Valitse tuote ja kieli ja katso saman identiteetin syntyvän.",
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
  b_search:"Hae", b_get:"Hae termi", b_resolve:"Ratkaise fraasit", b_fp:"Sormenjälki → merkki + QR", b_col:"pienennä", b_exp:"laajenna", p1:"Esite", p2:"Käyntikortit", p3:"Vihko", p4:"Paneelituloste", ed_hint:"Muokkaa merkkiä kanonisessa muodossa — SHA-256 lasketaan uudelleen selaimessa. Palauta, ja identiteetti palaa.", ed_diff:"eri tavut — eri identiteetti",
  e_search:"Kirjoita ostajan fraasi jollakin kahdestatoista kielestä — saat kanonisen termin pysyvine URI:neen.", e_get:"Yksi URI sisään — koko konteksti ulos: nimikkeet kaikilla kielillä, määritelmä, paikka puussa.", e_ver:"Minkä data- ja palvelinversion kanssa tämä playground keskustelee.", e_chain:"Envelope → validointi → sormenjälki kiinteällä esimerkillä — koko matka kolmella klikkauksella.", e_own:"Kuvaile painotyö omin sanoin — ja katso mikä osuu spesifikaatioon.", tr_t:"Istunnon loki — jokainen tämän sivun MCP-kutsu", tr_clear:"tyhjennä", tr_e:"Ei kutsuja vielä. Jokainen painike kirjaa pyynnön ja vastauksen tänne aikajärjestyksessä — keskustelu, jonka tekoälyagentti kävisi tämän palvelimen kanssa.", e_conv:"Neljä oikeaa tuotetta kahdellatoista kielellä — katso saman identiteetin syntyvän, livenä." },
is: { sub:"Hver hnappur sendir ekta MCP-<code>tools/call</code> (JSON-RPC yfir Streamable HTTP) á <code>/mcp</code> — nákvæmlega eins og gervigreindarfulltrúi.",
  t_conv:"Sama vara · öll tungumál · eitt fingrafar",
  i_conv:"Fjórar raunverulegar vörur, fjögur uppsetningarlíkön — bæklingur (brotin örk), nafnspjöld (flöt örk), hefti (fjölsíðna) og plötuprent (sérmál á plötu) — hver á tólf tungumálum. Veldu vöru og tungumál og sjáðu sömu auðkenni verða til.",
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
  b_search:"Leita", b_get:"Sækja hugtak", b_resolve:"Leysa orðalag", b_fp:"Fingrafar → merki + QR", b_col:"fella saman", b_exp:"opna", p1:"Bæklingur", p2:"Nafnspjöld", p3:"Hefti", p4:"Plötuprent", ed_hint:"Breyttu staf í kanóníska forminu — SHA-256 er endurreiknað í vafranum. Endurheimtu, og auðkennið kemur aftur.", ed_diff:"aðrir bætar — annað auðkenni",
  e_search:"Sláðu inn kaupandafrasa á einu af tólf tungumálum — fáðu kanóníska hugtakið með varanlegri URI.", e_get:"Ein URI inn — fullt samhengi út: heiti á öllum tungumálum, skilgreining, staður í trénu.", e_ver:"Hvaða gagna- og þjónsútgáfu þessi playground talar við.", e_chain:"Envelope → staðfesting → fingrafar á föstu dæmi — öll leiðin í þremur smellum.", e_own:"Lýstu prentverki með eigin orðum — og sjáðu hvað fellur að forskriftinni.", tr_t:"Lotuskrá — hvert MCP-kall þessarar síðu", tr_clear:"hreinsa", tr_e:"Engin köll enn. Hver hnappur skráir beiðni og svar hér, í tímaröð — samtalið sem gervigreindarfulltrúi ætti við þennan þjón.", e_conv:"Fjórar alvöru vörur á tólf tungumálum — sjáðu sama auðkennið verða til, í beinni." },
fr: { sub:"Chaque bouton envoie un vrai <code>tools/call</code> MCP (JSON-RPC sur Streamable HTTP) vers <code>/mcp</code> — exactement comme un agent IA.",
  t_conv:"Même produit · toutes les langues · une empreinte",
  i_conv:"Quatre produits réels, quatre modèles de montage — brochure (feuille pliée), cartes de visite (feuille plate), livret (multipage) et impression sur panneau (format sur mesure sur plaque) — chacun en douze langues. Choisissez un produit et une langue, et regardez la même identité émerger.",
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
  b_search:"Rechercher", b_get:"Obtenir le terme", b_resolve:"Résoudre les phrases", b_fp:"Empreinte → marque + QR", b_col:"replier", b_exp:"déplier", p1:"Brochure", p2:"Cartes de visite", p3:"Livret", p4:"Impression sur panneau", ed_hint:"Modifiez un caractère de la forme canonique — le SHA-256 est recalculé dans votre navigateur. Restaurez-le et l'identité revient.", ed_diff:"octets différents — identité différente",
  e_search:"Saisissez une phrase d'acheteur dans l'une des douze langues — obtenez le terme canonique et son URI permanente.", e_get:"Une URI en entrée — tout le contexte en sortie : libellés dans toutes les langues, définition, place dans l'arbre.", e_ver:"Avec quelle version des données et du serveur ce playground dialogue.", e_chain:"Envelope → validation → empreinte sur un exemple fixe — tout le parcours en trois clics.", e_own:"Décrivez un travail d'impression avec vos mots — et voyez ce qui correspond à la spécification.", tr_t:"Transcription de session — chaque appel MCP de cette page", tr_clear:"effacer", tr_e:"Aucun appel pour l'instant. Chaque bouton journalise requête et réponse ici, chronologiquement — la conversation qu'un agent IA aurait avec ce serveur.", e_conv:"Quatre produits réels en douze langues — voyez la même identité émerger, en direct." },
pl: { sub:"Każdy przycisk wysyła prawdziwe MCP-<code>tools/call</code> (JSON-RPC przez Streamable HTTP) do <code>/mcp</code> — dokładnie jak agent AI.",
  t_conv:"Ten sam produkt · każdy język · jeden odcisk",
  i_conv:"Cztery prawdziwe produkty, cztery modele konstrukcji — broszura (arkusz falcowany), wizytówki (arkusz płaski), książeczka (wielostronicowa) i druk panelowy (wymiar niestandardowy na płycie) — każdy w dwunastu językach. Wybierz produkt i język i zobacz, jak wyłania się ta sama tożsamość.",
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
  b_search:"Szukaj", b_get:"Pobierz termin", b_resolve:"Rozwiąż frazy", b_fp:"Odcisk → znak + QR", b_col:"zwiń", b_exp:"rozwiń", p1:"Broszura", p2:"Wizytówki", p3:"Książeczka", p4:"Druk panelowy", ed_hint:"Zmień znak w formie kanonicznej — SHA-256 zostanie przeliczony w przeglądarce. Przywróć, a tożsamość wróci.", ed_diff:"inne bajty — inna tożsamość",
  e_search:"Wpisz frazę kupującego w jednym z dwunastu języków — otrzymasz termin kanoniczny z trwałym URI.", e_get:"Jedno URI na wejściu — pełny kontekst na wyjściu: etykiety we wszystkich językach, definicja, miejsce w drzewie.", e_ver:"Z jaką wersją danych i serwera rozmawia ten playground.", e_chain:"Envelope → walidacja → odcisk na stałym przykładzie — cała podróż w trzech kliknięciach.", e_own:"Opisz zlecenie druku własnymi słowami — i zobacz, co trafia w specyfikację.", tr_t:"Zapis sesji — każde wywołanie MCP tej strony", tr_clear:"wyczyść", tr_e:"Brak wywołań. Każdy przycisk zapisuje tu żądanie i odpowiedź, chronologicznie — rozmowa, jaką agent AI prowadziłby z tym serwerem.", e_conv:"Cztery prawdziwe produkty w dwunastu językach — zobacz, jak ta sama tożsamość powstaje na żywo." },
es: { sub:"Cada botón envía un <code>tools/call</code> MCP real (JSON-RPC sobre Streamable HTTP) a <code>/mcp</code> — exactamente lo que hace un agente de IA.",
  t_conv:"Mismo producto · cualquier idioma · una huella",
  i_conv:"Cuatro productos reales, cuatro modelos de montaje — folleto (hoja plegada), tarjetas de visita (hoja plana), cuadernillo (multipágina) e impresión en panel (medida personalizada sobre placa) — cada uno en doce idiomas. Elija producto e idioma y vea emerger la misma identidad.",
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
  b_search:"Buscar", b_get:"Obtener término", b_resolve:"Resolver frases", b_fp:"Huella → marca + QR", b_col:"contraer", b_exp:"expandir", p1:"Folleto", p2:"Tarjetas de visita", p3:"Cuadernillo", p4:"Impresión en panel", ed_hint:"Edite un carácter de la forma canónica — el SHA-256 se recalcula en su navegador. Restáurelo y la identidad vuelve.", ed_diff:"bytes distintos — identidad distinta",
  e_search:"Escriba una frase de comprador en uno de doce idiomas — obtenga el término canónico con su URI permanente.", e_get:"Una URI de entrada — contexto completo de salida: etiquetas en todos los idiomas, definición, lugar en el árbol.", e_ver:"Con qué versión de datos y servidor habla este playground.", e_chain:"Envelope → validación → huella sobre un ejemplo fijo — todo el recorrido en tres clics.", e_own:"Describa un trabajo de impresión con sus palabras — y vea qué encaja en la especificación.", tr_t:"Transcripción de sesión — cada llamada MCP de esta página", tr_clear:"limpiar", tr_e:"Aún no hay llamadas. Cada botón registra aquí petición y respuesta, cronológicamente — la conversación que un agente de IA tendría con este servidor.", e_conv:"Cuatro productos reales en doce idiomas — vea emerger la misma identidad, en vivo." },
ja: { sub:"各ボタンは本物のMCP <code>tools/call</code>（Streamable HTTP上のJSON-RPC）を<code>/mcp</code>に送信します — AIエージェントの動作そのものです。",
  t_conv:"同じ製品 · どの言語でも · ひとつのフィンガープリント",
  i_conv:"4つの実在製品、4つのセットアップモデル — パンフレット（折り）、名刺（平判）、冊子（多ページ）、パネルプリント（カスタムサイズの板材）— それぞれ12言語で表現。製品と言語を選び、同じアイデンティティが現れるのをご覧ください。",
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
  b_search:"検索", b_get:"用語取得", b_resolve:"フレーズを解決", b_fp:"フィンガープリント → マーク + QR", b_col:"折りたたむ", b_exp:"展開", p1:"パンフレット", p2:"名刺", p3:"冊子", p4:"パネルプリント", ed_hint:"正規形の一文字を変えてみてください — SHA-256はブラウザで再計算されます。元に戻せばアイデンティティも戻ります。", ed_diff:"バイト列が異なる — アイデンティティが異なる",
  e_search:"12言語いずれかで購買フレーズを入力 — 恒久URI付きの正規用語が返ります。", e_get:"URIを1つ入力 — 全言語のラベル、定義、ツリー上の位置まで完全なコンテキストを返します。", e_ver:"このプレイグラウンドが接続するデータ／サーバーのバージョン。", e_chain:"固定サンプルで Envelope → 検証 → フィンガープリント — 全行程を3クリックで。", e_own:"印刷物を自分の言葉で記述 — 何が仕様にマッピングされるかを確認。", tr_t:"セッション記録 — このページが行った全MCP呼び出し", tr_clear:"クリア", tr_e:"まだ呼び出しはありません。各ボタンのリクエストと応答が時系列でここに記録されます — AIエージェントがこのサーバーと交わす会話です。", e_conv:"12言語×4つの実在製品 — 同じアイデンティティがライブで現れるのをご覧ください。" },
zh: { sub:"每个按钮都会向 <code>/mcp</code> 发送真实的 MCP <code>tools/call</code>（基于 Streamable HTTP 的 JSON-RPC）— 与 AI 智能体的行为完全一致。",
  t_conv:"同一产品 · 任何语言 · 一个指纹",
  i_conv:"四个真实产品、四种装帧模型 — 宣传册（折页）、名片（平张）、小册子（多页）、面板打印（板材自定义尺寸）— 各用十二种语言表述。选择产品和语言，看同一身份如何呈现。",
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
  b_search:"搜索", b_get:"获取术语", b_resolve:"解析短语", b_fp:"指纹 → 标记 + QR", b_col:"收起", b_exp:"展开", p1:"宣传册", p2:"名片", p3:"小册子", p4:"面板打印", ed_hint:"试着修改规范形式中的一个字符 — SHA-256 会在浏览器中重新计算。恢复后，身份也随之恢复。", ed_diff:"字节不同 — 身份不同",
  e_search:"用十二种语言之一输入买家用语 — 返回带永久 URI 的规范术语。", e_get:"输入一个 URI — 输出完整上下文：所有语言的标签、定义、在树中的位置。", e_ver:"此演练场连接的数据与服务器版本。", e_chain:"固定示例上的 Envelope → 验证 → 指纹 — 三次点击走完全程。", e_own:"用自己的话描述印刷品 — 看哪些内容映射到规范。", tr_t:"会话记录 — 本页发出的每个 MCP 调用", tr_clear:"清空", tr_e:"尚无调用。每个按钮的请求与响应都会按时间记录在此 — 这就是 AI 智能体与此服务器的对话。", e_conv:"十二种语言、四个真实产品 — 实时看同一身份浮现。" },
pt: { sub:"Cada botão envia um <code>tools/call</code> MCP real (JSON-RPC sobre Streamable HTTP) para <code>/mcp</code> — exatamente como um agente de IA.",
  t_conv:"Mesmo produto · qualquer língua · uma impressão digital",
  i_conv:"Quatro produtos reais, quatro modelos de montagem — folheto (folha dobrada), cartões de visita (folha plana), brochura (multipágina) e painel impresso (formato personalizado em placa) — cada um formulado em doze línguas. Escolha o produto e a língua e veja a mesma identidade surgir.",
  h_conv:"A interpretação (palavras → vínculos) está preparada aqui por língua — em produção é a tarefa do agente de IA. Termos, validação do envelope e a impressão digital ptpge-cfs/1 correm <em>ao vivo</em> contra este servidor. O hash é uma função determinística, não a saída de um modelo.",
  hist:"Histórico — mesmo produto, línguas diferentes",
  s01:"Especificação em bruto", s02:"Resolvida contra o vocabulário", tag02:"preparado — a tarefa do agente",
  s03:"Forma canónica", tag04:"função determinística, não o modelo", s05:"Identidade",
  live:"verificado ao vivo", resolver:"resolve no registo público ↗", same:"mesma identidade",
  t_search:"ptpge_search_terms — pesquisa de texto livre",
  h_search:"A pesquisa é tokenizada e independente da língua — frases do comprador em qualquer língua suportada acertam nos termos canónicos.", "try":"Experimente:",
  t_get:"ptpge_get_term — contexto completo de um termo", h_get:"Dica: clique num <code>id</code> de uma pesquisa, ou experimente:",
  t_ver:"ptpge_get_version — versão dos dados e do servidor", b_ver:"Obter versão",
  t_chain:"Prompt de teste — a cadeia completa, ao vivo",
  h_chain:"A interpretação (palavras → vínculos) está preparada aqui — essa é a tarefa do agente de IA. Consultas, validação do envelope e a impressão digital ptpge-cfs/1 correm <em>ao vivo</em> contra este servidor.",
  t_own:"O seu próprio prompt — o que se resolve?",
  h_own:"Um agente real decompõe o prompt com um LLM; a demo aproxima isso com pesquisas de n-gramas — cada fragmento é consultado <em>ao vivo</em>.",
  b_search:"Pesquisar", b_get:"Obter termo", b_resolve:"Resolver frases", b_fp:"Impressão digital → marca + QR", b_col:"recolher", b_exp:"expandir", p1:"Folheto", p2:"Cartões de visita", p3:"Brochura", p4:"Painel impresso", ed_hint:"Altere um carácter da forma canónica — o SHA-256 é recalculado ao vivo no seu navegador. Restaure-o e a identidade volta.", ed_diff:"bytes diferentes — identidade diferente",
  e_search:"Escreva uma frase de comprador numa de doze línguas — receba o termo canónico e o seu URI permanente.", e_get:"Um URI entra — contexto completo sai: rótulos em todas as línguas, definição, lugar na árvore.", e_ver:"Com que versão de dados e servidor este playground fala.", e_chain:"Envelope → validação → impressão digital num pedido de exemplo fixo — toda a viagem em três cliques.", e_own:"Descreva um trabalho de impressão nas suas palavras — e veja o que mapeia para a especificação.", tr_t:"Registo da sessão — cada chamada MCP desta página", tr_clear:"limpar", tr_e:"Ainda sem chamadas. Cada botão regista aqui o pedido e a resposta, por ordem — a conversa que um agente de IA teria com este servidor.", e_conv:"Quatro produtos reais em doze línguas — veja a mesma identidade surgir ao vivo." },
hi: { sub:"हर बटन <code>/mcp</code> को एक असली MCP <code>tools/call</code> (Streamable HTTP पर JSON-RPC) भेजता है — बिल्कुल AI एजेंट की तरह।",
  t_conv:"वही उत्पाद · कोई भी भाषा · एक फ़िंगरप्रिंट",
  i_conv:"चार असली उत्पाद, चार सेटअप मॉडल — ब्रोशर (मुड़ी शीट), विज़िटिंग कार्ड (फ़्लैट शीट), बुकलेट (बहु-पृष्ठ) और पैनल प्रिंट (कठोर बोर्ड पर कस्टम साइज़) — हर एक बारह भाषाओं में। उत्पाद और भाषा चुनें और वही पहचान उभरते देखें।",
  h_conv:"व्याख्या (शब्द → बाइंडिंग) यहाँ प्रति भाषा पहले से लिखी है — उत्पादन में यह AI एजेंट का काम है। पद, एनवलप सत्यापन और ptpge-cfs/1 फ़िंगरप्रिंट इस सर्वर पर <em>लाइव</em> चलते हैं। हैश एक निर्धारक फ़ंक्शन है, मॉडल का आउटपुट नहीं।",
  hist:"इतिहास — वही उत्पाद, अलग भाषाएँ",
  s01:"कच्चा विनिर्देश", s02:"शब्दावली से मिलान", tag02:"पहले से लिखा — एजेंट का काम",
  s03:"कैनोनिकल रूप", tag04:"निर्धारक फ़ंक्शन, मॉडल नहीं", s05:"पहचान",
  live:"लाइव जाँचा", resolver:"सार्वजनिक रजिस्टर में हल होता है ↗", same:"वही पहचान",
  t_search:"ptpge_search_terms — मुक्त-पाठ खोज",
  h_search:"खोज टोकनीकृत और भाषा-निरपेक्ष है — किसी भी समर्थित भाषा में ख़रीदार के वाक्यांश कैनोनिकल पदों से मिलते हैं।", "try":"आज़माएँ:",
  t_get:"ptpge_get_term — एक पद का पूरा संदर्भ", h_get:"सुझाव: खोज से कोई <code>id</code> क्लिक करें, या आज़माएँ:",
  t_ver:"ptpge_get_version — डेटा और सर्वर संस्करण", b_ver:"संस्करण लें",
  t_chain:"टेस्ट प्रॉम्प्ट — पूरी शृंखला, लाइव",
  h_chain:"व्याख्या (शब्द → बाइंडिंग) यहाँ पहले से लिखी है — वह AI एजेंट का काम है। लुकअप, एनवलप सत्यापन और ptpge-cfs/1 फ़िंगरप्रिंट इस सर्वर पर <em>लाइव</em> चलते हैं।",
  t_own:"आपका अपना प्रॉम्प्ट — क्या हल होता है?",
  h_own:"असली एजेंट प्रॉम्प्ट को LLM से तोड़ता है; डेमो इसे n-ग्राम खोजों से अनुमानित करता है — हर टुकड़ा <em>लाइव</em> देखा जाता है।",
  b_search:"खोजें", b_get:"पद लें", b_resolve:"वाक्यांश हल करें", b_fp:"फ़िंगरप्रिंट → मार्क + QR", b_col:"समेटें", b_exp:"फैलाएँ", p1:"ब्रोशर", p2:"विज़िटिंग कार्ड", p3:"बुकलेट", p4:"पैनल प्रिंट", ed_hint:"कैनोनिकल रूप में एक अक्षर बदलें — SHA-256 आपके ब्राउज़र में लाइव फिर से बनता है। वापस करें और पहचान लौट आती है।", ed_diff:"अलग बाइट — अलग पहचान",
  e_search:"बारह भाषाओं में से किसी में ख़रीदार का वाक्यांश लिखें — कैनोनिकल पद और उसका स्थायी URI पाएँ।", e_get:"एक URI अंदर — पूरा संदर्भ बाहर: सभी भाषाओं में लेबल, परिभाषा, पेड़ में स्थान।", e_ver:"यह प्लेग्राउंड किस डेटा और सर्वर संस्करण से बात करता है।", e_chain:"एनवलप → सत्यापन → फ़िंगरप्रिंट एक निश्चित उदाहरण ऑर्डर पर — पूरी यात्रा तीन क्लिक में।", e_own:"अपने शब्दों में कोई प्रिंट जॉब बताएँ — और देखें विशिष्टता में क्या मैप होता है।", tr_t:"सत्र लॉग — इस पेज की हर MCP कॉल", tr_clear:"साफ़ करें", tr_e:"अभी कोई कॉल नहीं। हर बटन यहाँ अनुरोध और उत्तर क्रम से दर्ज करता है — वह बातचीत जो AI एजेंट इस सर्वर से करता।", e_conv:"बारह भाषाओं में चार असली उत्पाद — वही पहचान लाइव उभरते देखें।" },
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
  if (typeof renderProdBtns === "function") renderProdBtns();
  try { localStorage.setItem("ptpge-playground-lang", l); } catch (e) {}
  document.getElementById("langcode").textContent = l.toUpperCase();
  const _lf = LANG_NAMES.find(p => p[0] === l); if (_lf) document.getElementById("langflag").textContent = _lf[2];
  document.querySelectorAll("#langlist a").forEach(a =>
    a.classList.toggle("on", a.getAttribute("data-l") === l));
}
function langMenu(e) {
  if (e) e.stopPropagation();
  const m = document.getElementById("langlist");
  m.style.display = (m.style.display === "block") ? "none" : "block";
}
document.addEventListener("click", () => {
  const m = document.getElementById("langlist");
  if (m) m.style.display = "none";
});
(function initLang() {
  document.getElementById("langlist").innerHTML = LANG_NAMES.map(p =>
    '<a data-l="' + p[0] + '"><span class="fl">' + p[2] + '</span>' + p[1] + '</a>').join("");
  document.querySelectorAll("#langlist a").forEach(a =>
    a.addEventListener("click", () => setLang(a.getAttribute("data-l"))));
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
      (new URLSearchParams(location.search).get("t") ? "" : " (tip: if tokens are required, open /playground?t=YOUR_TOKEN from your welcome email)");
  }
})();
</script>
</body>
</html>
"""

try:
    from ._frame import FRAME_CSS, FRAME_HEADER, FRAME_FOOTER
except Exception:  # pragma: no cover — frame module missing: render without it
    FRAME_CSS, FRAME_HEADER, FRAME_FOOTER = "", "", ""
PLAYGROUND_HTML = (_PLAYGROUND_TEMPLATE.replace("__FRAME_CSS__", FRAME_CSS)
                   .replace("__FRAME_HEADER__", FRAME_HEADER).replace("__FRAME_FOOTER__", FRAME_FOOTER))
