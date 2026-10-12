"""GET /check — paste a domain, see what an agent finds (the browser door to check.py).

Same-origin JS fetches /check.json?domain=… and renders the report. Same
frame as the Playground (header/footer/CSS exported from ptpge.org).
"""

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="__ROBOTS__">
<link rel="icon" href="/favicon.ico">
<title>Check a domain — PTPGE</title>
<style>__FRAME_CSS__</style>
<style>
*{box-sizing:border-box}
:root{--ink:#20261f;--mute:#6a6a66;--line:#e4e2dc;--soft:#f6f5f1;--bg:#fff;--ok:#2f6b3a;--warn:#9a6b12;--fail:#a63a2a}
html.dark{--ink:#f2f3ef;--mute:#9a9a92;--line:rgba(255,255,255,.13);--soft:#1e201c;--bg:#262823;--ok:#6fbf7a;--warn:#d9a441;--fail:#e07a6a}
body{font:15px/1.55 var(--pf-sans),-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;color:var(--ink);background:transparent;margin:0}
header:not(.pf){background:transparent;border-bottom:1px solid var(--line);padding:28px 28px 18px}
header:not(.pf) h1{font:italic 600 clamp(28px,3.6vw,38px)/1.1 'Spectral',Georgia,serif;margin:0;letter-spacing:0}
header:not(.pf) .sub{color:var(--mute);font-size:12.5px;margin-top:8px}
header,main{position:relative;z-index:1}
main{max-width:880px;margin:0 auto;padding:22px 28px 60px}
.card{background:var(--bg);border:1px solid var(--line);border-radius:4px;padding:18px 22px;margin-bottom:18px}
.card h2{font-size:11.5px;text-transform:uppercase;letter-spacing:.14em;color:var(--ink);font-weight:600;margin:0 0 12px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
input[type=text]{flex:1;min-width:220px;padding:9px 12px;border:1px solid var(--line);border-radius:4px;font:inherit;font-size:15px;background:var(--bg);color:var(--ink)}
input:focus{outline:2px solid var(--ink);outline-offset:1px;border-color:var(--ink)}
button{padding:9px 18px;border:1px solid var(--ink);border-radius:4px;background:var(--ink);color:var(--soft);font:inherit;font-weight:600;cursor:pointer}
button:hover{background:#000;border-color:#000}html.dark button{background:#e6e8e2;color:#1e201c;border-color:#e6e8e2}
button:disabled{background:var(--line);color:var(--mute);border-color:var(--line);cursor:wait}
.hint{font-size:12.5px;color:var(--mute);margin-top:8px}.hint a{color:var(--ink)}
.verdict{font:italic 600 22px/1.25 'Spectral',Georgia,serif;margin:0 0 6px}
.verdict.ready,.verdict.maker{color:var(--ok)}.verdict.partial{color:var(--warn)}.verdict.none{color:var(--fail)}
.summary{color:var(--mute);margin:0 0 4px}
ol.steps{list-style:none;margin:0;padding:0}
ol.steps li{display:grid;grid-template-columns:26px 1fr;gap:10px;padding:12px 0;border-top:1px solid var(--line)}
ol.steps li:first-child{border-top:0}
.dot{width:16px;height:16px;border-radius:50%;margin-top:4px;background:var(--line)}
.dot.ok{background:var(--ok)}.dot.warn{background:var(--warn)}.dot.fail{background:var(--fail)}.dot.skip{background:transparent;border:2px solid var(--line)}
.st b{font-weight:600}.st .u{display:block;font:12px/1.4 ui-monospace,Menlo,monospace;color:var(--mute);word-break:break-all;margin-top:2px}
.st .u a{color:var(--mute)}
.st .d{margin-top:3px}
ul.msgs{margin:6px 0 0;padding-left:18px;font-size:13px}ul.msgs li{padding:1px 0}
ul.msgs.err{color:var(--fail)}ul.msgs.wrn{color:var(--warn)}
.prov{font-size:12.5px;color:var(--mute);border:1px solid var(--line);border-radius:4px;padding:8px 10px;margin:0 0 10px}
.card h3{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--mute);margin:12px 0 6px;font-weight:600}
ul.rd{margin:0;padding-left:18px;font-size:13.5px}ul.rd li{margin:3px 0;line-height:1.55}
table.sees{border-collapse:collapse;width:100%;font-size:14px}
table.sees th{text-align:left;font-weight:600;padding:5px 12px 5px 0;vertical-align:top;white-space:nowrap;color:var(--mute);font-size:12px;text-transform:uppercase;letter-spacing:.08em}
table.sees td{padding:5px 0;border-top:1px solid var(--line)}table.sees tr:first-child td,table.sees tr:first-child th{border-top:0}
table.sees a{color:var(--ink)}
.miss{border-left:3px solid var(--warn);padding:6px 12px;margin:8px 0}
.miss b{display:block}.miss .why{color:var(--mute);font-size:13.5px}.miss a{color:var(--ink);font-size:13px}
pre.raw{background:#1b1d19;color:#e6e8e2;border-radius:4px;padding:14px 18px;font:12.5px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word;max-height:420px;overflow:auto}
details.raw summary{cursor:pointer;color:var(--mute);font-size:13px}
.meta{font-size:12px;color:var(--mute);margin-top:10px}
#out:empty{display:none}
</style>
</head>
<body>
__FRAME_HEADER__
<header>
  <h1>Does an agent find you?</h1>
  <div class="sub">Paste a domain. This fetches what a checkout agent fetches — <code>/.well-known/ucp</code>, the declaration, the identity — and validates each against its published schema. Read-only; nothing is stored.</div>
</header>
<main>
<div class="card">
  <form class="row" id="f" onsubmit="return go()">
    <input type="text" id="dom" placeholder="trykkverk.no" autocomplete="off" spellcheck="false" autofocus>
    <button type="submit" id="btn">Check</button>
  </form>
  <div class="hint">Try <a href="#" onclick="return pick('trykkverk.no')">trykkverk.no</a> (the pilot printer). Same check as JSON: <code>/check.json?domain=…</code> · as an MCP tool: <code>ptpge_check_domain</code> · how to publish: <a href="https://ptpge.org/adopt/">ptpge.org/adopt</a></div>
</div>
<div id="out"__SSR_ATTR__>__SSR__</div>
</main>
__FRAME_FOOTER__
<script>
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function pick(d){document.getElementById('dom').value=d;go();return false}
function li(s){
  var u=s.url?'<span class="u"><a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.url)+'</a></span>':'';
  var e=(s.errors||[]).length?'<ul class="msgs err">'+s.errors.map(function(x){return '<li>'+esc(x)+'</li>'}).join('')+'</ul>':'';
  var w=(s.warnings||[]).length?'<ul class="msgs wrn">'+s.warnings.map(function(x){return '<li>'+esc(x)+'</li>'}).join('')+'</ul>':'';
  return '<li><span class="dot '+esc(s.status)+'"></span><div class="st"><b>'+esc(s.title)+'</b>'+u+'<div class="d">'+esc(s.detail)+'</div>'+e+w+'</div></li>';
}
function render(r){
  var h='<div class="card"><p class="verdict '+esc(r.verdict)+'">'+esc(r.domain)+' — '+({ready:'agent-ready',maker:'maker-ready',partial:'partly there',none:'nothing found'}[r.verdict]||r.verdict)+'</p><p class="summary">'+esc(r.summary)+'</p></div>';
  h+='<div class="card"><h2>What the agent does</h2><ol class="steps">'+r.steps.map(li).join('')+'</ol></div>';
  var a=r.agentSees||{};
  if(a.name||a.identity||a.catalogueIdentity){
    var prods=(a.products||[]).map(function(p){return '<a href="'+esc(p.uri)+'" target="_blank" rel="noopener">'+esc(p.template)+'</a>'}).join(' · ');
    h+='<div class="card"><h2>What the agent sees</h2><table class="sees">'
      +(a.name?'<tr><th>Name</th><td>'+esc(a.name)+(a.country?' ('+esc(a.country)+')':'')+'</td></tr>':'')
      +(a.identity?'<tr><th>Identity</th><td><a href="'+esc(a.identity)+'" target="_blank" rel="noopener">'+esc(a.identity)+'</a></td></tr>':'')
      +(a.vendorTypes?'<tr><th>Type</th><td>'+esc((a.vendorTypes||[]).join(', '))+'</td></tr>':'')
      +(a.identity?'<tr><th>Products</th><td>'+(prods||'—')+'</td></tr>'
      +'<tr><th>Capability</th><td>'+esc(a.lineCount||0)+' production line(s) · '+esc(a.pressCount||0)+' press(es) · '+esc(a.substrateCount||0)+' substrate(s)</td></tr>':'')
      +(a.catalogueItems!=null?'<tr><th>Catalogue</th><td>'+esc(a.catalogueName||'')+' — '+esc(a.catalogueItems)+' items · <a href="'+esc(a.catalogueIdentity)+'" target="_blank" rel="noopener">'+esc(a.catalogueIdentity)+'</a></td></tr>':'')
      +(a.modified?'<tr><th>Modified</th><td>'+esc(a.modified)+'</td></tr>':'')
      +'</table></div>';
  }
  if((a.lines||[]).length||(a.offerings||[]).length){
    var ls=(a.lines||[]).map(function(l){ var b=[esc(l.technology)]; if((l.presses||[]).length)b.push(esc(l.presses.join(', '))); if(l.maxFormatMm)b.push('max '+esc(l.maxFormatMm)+' mm'); if(l.weightGsm)b.push(esc(l.weightGsm)+' g/m²'); if((l.colourModes||[]).length)b.push('colour '+esc(l.colourModes.join(', '))); if((l.substrates||[]).length)b.push('stock: '+esc(l.substrates.join('; '))); return '<li><b>'+esc(l.name)+'</b> — '+b.join(' · ')+'</li>'; }).join('');
    var os=(a.offerings||[]).map(function(o){ var b=(o.supports||[]).map(function(x){return esc(x.variable)+': '+esc((x.values||[]).join(', '))}); if((o.colour||[]).length)b.push('colour '+esc(o.colour.join(', '))); if((o.pages||[]).length)b.push('pages '+esc(o.pages.join('/'))); if(o.minimumQuantity)b.push('min '+esc(o.minimumQuantity)); if(o.leadTimeWorkingDays!=null)b.push('lead '+esc(o.leadTimeWorkingDays)+' working days'); return '<li><b>'+esc(o.name)+'</b> (<a href="'+esc(o.productUri)+'" target="_blank" rel="noopener">'+esc(o.product)+'</a>)'+(o.line?' on «'+esc(o.line)+'»':'')+' — '+b.join('; ')+'</li>'; }).join('');
    var ds=(r.steps||[]).filter(function(s){return s.id==='declaration'})[0]||{};
    h+='<div class="card"><h2>What the declaration says</h2><p class="prov">Read just now from <a href="'+esc(ds.url||'')+'" target="_blank" rel="noopener">'+esc(ds.url||'the declaration')+'</a>'+(a.modified?' · document modified '+esc(String(a.modified).slice(0,10)):'')+'. <b>The file is the source</b> — this is a reading of it in the vocabulary\'s labels; nothing is stored. No prices: a price is a quote.</p>'
      +(ls?'<h3>Production lines (capability)</h3><ul class="rd">'+ls+'</ul>':'')+(os?'<h3>Offerings — in the specification\'s terms</h3><ul class="rd">'+os+'</ul>':'')+'</div>';
  }
  if((r.missing||[]).length){
    h+='<div class="card"><h2>What is missing</h2>'+r.missing.map(function(m){return '<div class="miss"><b>'+esc(m.what)+'</b><div class="why">'+esc(m.why)+'</div><a href="'+esc(m.where)+'" target="_blank" rel="noopener">'+esc(m.where)+'</a></div>'}).join('')+'</div>';
  }
  h+='<div class="card"><details class="raw"><summary>Raw report (JSON)</summary><pre class="raw">'+esc(JSON.stringify(r,null,2))+'</pre></details><div class="meta">Checked '+esc(r.checkedAt)+' · '+esc(r.durationMs)+' ms · <a href="/check.json?domain='+encodeURIComponent(r.domain)+'" style="color:inherit">this report as JSON</a></div></div>';
  document.getElementById('out').innerHTML=h;
}
function go(){
  var d=document.getElementById('dom').value.trim(); if(!d) return false;
  var b=document.getElementById('btn'); b.disabled=true; b.textContent='Checking…';
  document.getElementById('out').innerHTML='<div class="card"><p class="summary">Fetching '+esc(d)+' …</p></div>';
  try{history.replaceState(null,'','?domain='+encodeURIComponent(d))}catch(e){}
  fetch('/check.json?domain='+encodeURIComponent(d),{headers:{'Accept':'application/json'}})
    .then(function(r){return r.json()}).then(render)
    .catch(function(e){document.getElementById('out').innerHTML='<div class="card"><p class="verdict none">Check failed</p><p class="summary">'+esc(e)+'</p></div>'})
    .finally(function(){b.disabled=false;b.textContent='Check'});
  return false;
}
(function(){var q=new URLSearchParams(location.search).get('domain');if(q){document.getElementById('dom').value=q;if(!document.getElementById('out').getAttribute('data-ssr'))go()}})();
</script>
</body>
</html>
"""

try:
    from ._frame import FRAME_CSS, FRAME_HEADER, FRAME_FOOTER
except Exception:  # pragma: no cover
    FRAME_CSS, FRAME_HEADER, FRAME_FOOTER = "", "", ""
_BASE_HTML = (_TEMPLATE.replace("__FRAME_CSS__", FRAME_CSS)
              .replace("__FRAME_HEADER__", FRAME_HEADER).replace("__FRAME_FOOTER__", FRAME_FOOTER))
CHECK_HTML = _BASE_HTML.replace("__SSR_ATTR__", "").replace("__SSR__", "").replace("__ROBOTS__", "noindex,nofollow")


def _e(s) -> str:
    import html
    return html.escape("" if s is None else str(s), quote=True)


def render_report_html(r: dict) -> str:
    """Server-side rendering of a check report (SD-0105): the same cards the JS draws, as static HTML so a
    crawler or a browsing model gets the text without running scripts. The JS keeps the page live for people."""
    names = {"ready": "agent-ready", "maker": "maker-ready", "partial": "partly there", "none": "nothing found"}
    h = f'<div class="card"><p class="verdict {_e(r.get("verdict"))}">{_e(r.get("domain"))} — {_e(names.get(r.get("verdict"), r.get("verdict")))}</p><p class="summary">{_e(r.get("summary", ""))}</p></div>'
    steps = ""
    for st in r.get("steps") or []:
        u = f'<span class="u"><a href="{_e(st.get("url"))}" rel="noopener">{_e(st.get("url"))}</a></span>' if st.get("url") else ""
        er = "".join(f"<li>{_e(x)}</li>" for x in st.get("errors") or [])
        wr = "".join(f"<li>{_e(x)}</li>" for x in st.get("warnings") or [])
        steps += (f'<li><span class="dot {_e(st.get("status"))}"></span><div class="st"><b>{_e(st.get("title"))}</b>{u}<div class="d">{_e(st.get("detail"))}</div>'
                  + (f'<ul class="msgs err">{er}</ul>' if er else "") + (f'<ul class="msgs wrn">{wr}</ul>' if wr else "") + "</div></li>")
    h += f'<div class="card"><h2>What the agent does</h2><ol class="steps">{steps}</ol></div>'
    a = r.get("agentSees") or {}
    if a.get("name") or a.get("identity"):
        prods = " · ".join(f'<a href="{_e(p.get("uri"))}" rel="noopener">{_e(p.get("template"))}</a>' for p in a.get("products") or [])
        rows = ""
        if a.get("name"):
            rows += f'<tr><th>Name</th><td>{_e(a["name"])}{(" (" + _e(a["country"]) + ")") if a.get("country") else ""}</td></tr>'
        if a.get("identity"):
            rows += f'<tr><th>Identity</th><td><a href="{_e(a["identity"])}" rel="noopener">{_e(a["identity"])}</a></td></tr>'
            rows += f'<tr><th>Products</th><td>{prods or "—"}</td></tr>'
            rows += f'<tr><th>Capability</th><td>{_e(a.get("lineCount", 0))} production line(s) · {_e(a.get("pressCount", 0))} press(es) · {_e(a.get("substrateCount", 0))} substrate(s)</td></tr>'
        if a.get("modified"):
            rows += f'<tr><th>Modified</th><td>{_e(a["modified"])}</td></tr>'
        h += f'<div class="card"><h2>What the agent sees</h2><table class="sees">{rows}</table></div>'
    if a.get("lines") or a.get("offerings"):
        ls = ""
        for l in a.get("lines") or []:
            b = [_e(l.get("technology"))]
            if l.get("presses"): b.append(_e(", ".join(l["presses"])))
            if l.get("maxFormatMm"): b.append(f'max {_e(l["maxFormatMm"])} mm')
            if l.get("weightGsm"): b.append(f'{_e(l["weightGsm"])} g/m²')
            if l.get("colourModes"): b.append("colour " + _e(", ".join(l["colourModes"])))
            if l.get("substrates"): b.append("stock: " + _e("; ".join(l["substrates"])))
            ls += f'<li><b>{_e(l.get("name"))}</b> — {" · ".join(b)}</li>'
        os_ = ""
        for o in a.get("offerings") or []:
            b = [f'{_e(x.get("variable"))}: {_e(", ".join(x.get("values") or []))}' for x in o.get("supports") or []]
            if o.get("colour"): b.append("colour " + _e(", ".join(str(c) for c in o["colour"])))
            if o.get("pages"): b.append("pages " + _e("/".join(str(x) for x in o["pages"])))
            if o.get("minimumQuantity"): b.append(f'min {_e(o["minimumQuantity"])}')
            if o.get("leadTimeWorkingDays") is not None: b.append(f'lead {_e(o["leadTimeWorkingDays"])} working days')
            os_ += (f'<li><b>{_e(o.get("name"))}</b> (<a href="{_e(o.get("productUri"))}" rel="noopener">{_e(o.get("product"))}</a>)'
                    + (f' on «{_e(o["line"])}»' if o.get("line") else "") + " — " + "; ".join(b) + "</li>")
        ds = next((st for st in r.get("steps") or [] if st.get("id") == "declaration"), {})
        h += (f'<div class="card"><h2>What the declaration says</h2><p class="prov">Read at {_e(r.get("checkedAt"))} from '
              f'<a href="{_e(ds.get("url"))}" rel="noopener">{_e(ds.get("url"))}</a>'
              + (f' · document modified {_e(str(a["modified"])[:10])}' if a.get("modified") else "")
              + '. <b>The file is the source</b> — this is a reading of it in the vocabulary\'s labels; nothing is stored. No prices: a price is a quote.</p>'
              + (f'<h3>Production lines (capability)</h3><ul class="rd">{ls}</ul>' if ls else "")
              + (f'<h3>Offerings — in the specification\'s terms</h3><ul class="rd">{os_}</ul>' if os_ else "") + "</div>")
    if r.get("missing"):
        h += '<div class="card"><h2>What is missing</h2>' + "".join(
            f'<div class="miss"><b>{_e(m.get("what"))}</b><div class="why">{_e(m.get("why"))}</div><a href="{_e(m.get("where"))}" rel="noopener">{_e(m.get("where"))}</a></div>'
            for m in r["missing"]) + "</div>"
    h += f'<div class="card"><div class="meta">Checked {_e(r.get("checkedAt"))} · read live from the domain; nothing is stored (SD-0101, SD-0105).</div></div>'
    return h


def check_html_for(report: dict | None) -> str:
    """The page with a server-rendered report (when a domain was given). Indexable only for a ready/maker domain."""
    if not report:
        return CHECK_HTML
    indexable = report.get("verdict") in ("ready", "maker")
    return (_BASE_HTML.replace("__SSR_ATTR__", ' data-ssr="1"').replace("__SSR__", render_report_html(report))
            .replace("__ROBOTS__", "index,follow" if indexable else "noindex,nofollow"))
