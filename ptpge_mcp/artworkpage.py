"""GET /playground/pdf — hidden page (SD-0107): drop a print PDF, see what it says and what the specification
must ask, then validate and fingerprint. Not linked from anywhere; noindex. Same frame as the Playground."""
from .checkpage import FRAME_CSS, FRAME_HEADER, FRAME_FOOTER

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<link rel="icon" href="/favicon.ico">
<title>Drop your PDF — PTPGE</title>
<style>__FRAME_CSS__</style>
<style>
*{box-sizing:border-box}
:root{--ink:#20261f;--mute:#6a6a66;--line:#e4e2dc;--soft:#f6f5f1;--bg:#fff;--ok:#2f6b3a;--warn:#9a6b12;--fail:#a63a2a}
html.dark{--ink:#f2f3ef;--mute:#9a9a92;--line:rgba(255,255,255,.13);--soft:#1e201c;--bg:#262823;--ok:#6fbf7a;--warn:#d9a441;--fail:#e07a6a}
body{font:15px/1.55 var(--pf-sans),-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;color:var(--ink);background:transparent;margin:0}
header:not(.pf){background:transparent;border-bottom:1px solid var(--line);padding:28px 0 18px}
header:not(.pf)>*{max-width:880px;margin-left:auto;margin-right:auto;padding:0 28px}
header:not(.pf) h1{font:italic 600 clamp(28px,3.6vw,38px)/1.1 'Spectral',Georgia,serif;margin:0}
header:not(.pf) .sub{color:var(--mute);font-size:12.5px;margin-top:8px;max-width:760px}
header,main{position:relative;z-index:1}
main{max-width:880px;margin:0 auto;padding:22px 28px 60px}
.card{background:var(--bg);border:1px solid var(--line);border-radius:4px;padding:18px 22px;margin-bottom:18px}
.card h2{font-size:11.5px;text-transform:uppercase;letter-spacing:.14em;font-weight:600;margin:0 0 12px}
.drop{display:block;border:2px dashed var(--line);border-radius:6px;padding:38px 20px;text-align:center;color:var(--mute);cursor:pointer;font-size:14px;line-height:1.6;transition:border-color .15s,background .15s}
.drop b{display:block;font-size:17px;margin-bottom:4px}
.drop.over{border-color:var(--ink);background:var(--soft)}
.drop b{color:var(--ink)}
.drop input{display:none}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:700px){.two{grid-template-columns:1fr}}
ul.l{margin:0;padding-left:18px;font-size:13.5px}ul.l li{margin:4px 0;line-height:1.5}
ul.l li.q{color:var(--mute)}ul.l li.q b{color:var(--ink)}
.pill{display:inline-block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;border:1px solid var(--line);border-radius:999px;padding:2px 9px;color:var(--mute);margin-left:6px}
.warn{color:var(--warn);font-size:13px}
button{font:inherit;font-size:13.5px;padding:9px 16px;border-radius:4px;border:1px solid var(--ink);background:var(--ink);color:var(--bg);cursor:pointer}
button.gho{background:transparent;color:var(--ink)}
button:disabled{opacity:.5;cursor:default}
pre{font:12px/1.5 var(--pf-mono),ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word;background:#1b1d1a;color:#dfe3dc;padding:14px 16px;border-radius:4px;max-height:420px;overflow:auto}
.meta{font-size:12px;color:var(--mute)}
.hint{font-size:12.5px;color:var(--mute)}
.ans{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.ans input{flex:1;min-width:220px;padding:8px 10px;border:1px solid var(--line);border-radius:4px;font:inherit;font-size:14px;background:var(--bg);color:var(--ink)}
.mktile{display:inline-block;background:#fff;border-radius:6px;padding:10px;line-height:0;width:150px;height:150px}
.mktile svg{width:100%;height:100%}
.fp{display:flex;gap:22px;align-items:flex-start;flex-wrap:wrap}
.fp .cap{font:12px var(--pf-mono),ui-monospace,monospace;color:var(--mute);margin-top:6px;text-align:center}
</style>
</head>
<body>
__FRAME_HEADER__
<header>
  <h1>Drop your PDF</h1>
  <div class="sub">A print PDF knows some things about the product it is the pages of — the trim, the page count, the colour spaces, named inks, the output intent. The specification binds those and asks the rest. Nothing is stored; only the file's hash travels. <span class="pill">hidden · SD-0107</span></div>
</header>
<main>
<div class="card">
  <label class="drop" id="drop"><input type="file" id="file" accept="application/pdf"><b>Drop a PDF here</b>or click to choose · up to 25 MB · read in memory, never kept</label>
  <div class="meta" id="status" style="margin-top:10px"></div>
</div>
<div id="out"></div>
</main>
__FRAME_FOOTER__
<script>
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
var drop=document.getElementById('drop'), inp=document.getElementById('file'), out=document.getElementById('out'), st=document.getElementById('status');
var LAST=null, ANSWERS={};
['dragenter','dragover'].forEach(function(e){drop.addEventListener(e,function(ev){ev.preventDefault();drop.classList.add('over')})});
['dragleave','drop'].forEach(function(e){drop.addEventListener(e,function(ev){ev.preventDefault();drop.classList.remove('over')})});
drop.addEventListener('drop',function(ev){var f=ev.dataTransfer.files&&ev.dataTransfer.files[0];if(f)read(f)});
inp.addEventListener('change',function(){if(inp.files[0])read(inp.files[0])});
async function rpc(method,params){var r=await fetch('/mcp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:Date.now(),method:method,params:params})});return r.json()}
function short(u){return String(u).replace('https://ptpge.org/v1/','')}
function lab(u){return short(u).split('/').pop().replace(/-/g,' ')}
async function read(f){
  if(f.type!=='application/pdf'&&!/\.pdf$/i.test(f.name)){st.textContent='Only PDF in this version.';return}
  st.textContent='Reading '+f.name+' ('+Math.round(f.size/1024)+' KB) — the file is sent once, read, and dropped …';
  out.innerHTML='';
  try{
    var r=await fetch('/artwork',{method:'POST',headers:{'Content-Type':'application/pdf'},body:f});
    var j=await r.json();
    if(j.error){st.textContent='Could not read the file: '+(j.note||j.error);return}
    LAST=j; ANSWERS={}; st.textContent=f.name+' · sha256 '+j.artwork.sha256.slice(0,16)+'… · '+j.artwork.pages+' page(s)';
    render(j);
  }catch(e){st.textContent='Failed: '+e}
}
function render(j){
  var ff=(j.fromFile||[]).map(function(x){return '<li>'+esc(x)+'</li>'}).join('');
  var ta=(j.toAsk||[]).map(function(q,i){return '<li class="q"><b>'+esc(lab(q.variable))+(q.surface?' @'+esc(q.surface):'')+'</b> — '+esc(q.hint)+'</li>'}).join('');
  var w=(j.warnings||[]).map(function(x){return '<div class="warn">⚠ '+esc(x)+'</div>'}).join('');
  out.innerHTML='<div class="two"><div class="card"><h2>What the file said</h2><ul class="l">'+ff+'</ul>'+w+'</div>'
    +'<div class="card"><h2>What the specification must ask</h2><ul class="l">'+ta+'</ul>'
    +'<p class="hint">Answer in words — product and anything open («A5 booklet, saddle stitched, 170 gsm silk, matte lamination, 500 copies»). The file\'s bindings stay; your words add the rest; the identity is computed from both.</p>'
    +'<div class="ans"><input id="ans" placeholder="booklet, saddle stitched, 130 gsm inside, 300 gsm cover, 500 copies"><button id="go">Validate → identity</button></div></div></div>'
    +'<div class="card"><details><summary class="meta">Raw reading (JSON)</summary><pre>'+esc(JSON.stringify(j,null,2))+'</pre></details></div>';
  document.getElementById('go').onclick=finish;
}
var PRODUCT_WORDS=[['booklet','ordering/products/booklets'],['hefte','ordering/products/booklets'],['brochure','ordering/products/brochures'],['brosjyre','ordering/products/brochures'],['flyer','ordering/products/flyers'],['business card','ordering/products/business-cards'],['visittkort','ordering/products/business-cards'],['poster','ordering/products/posters'],['plakat','ordering/products/posters'],['magazine','ordering/products/magazines'],['magasin','ordering/products/magazines'],['catalogue','ordering/products/catalogues'],['catalog','ordering/products/catalogues'],['katalog','ordering/products/catalogues'],['book','ordering/products/books'],['bok','ordering/products/books'],['postcard','ordering/products/postcards'],['postkort','ordering/products/postcards'],['letterhead','ordering/products/letterheads'],['brevark','ordering/products/letterheads']];
async function finish(){
  var text=(document.getElementById('ans').value||'').toLowerCase(); var btn=document.getElementById('go'); btn.disabled=true;
  var product=null; for(var i=0;i<PRODUCT_WORDS.length;i++){if(text.indexOf(PRODUCT_WORDS[i][0])!==-1){product=PRODUCT_WORDS[i][1];break}}
  if(!product){ // fall back to search
    try{var sr=await rpc('tools/call',{name:'ptpge_search_terms',arguments:{query:text.split(',')[0]||'product',limit:5}});var hits=JSON.parse(sr.result.content[0].text).results||[];var h=hits.filter(function(x){return x.id.indexOf('/ordering/products/')!==-1&&(x.score||0)>=0.9})[0];if(h)product=short(h.id)}catch(e){}
  }
  if(!product){st.textContent='Name the product (booklet, brochure, business cards, poster …) — the file cannot say which it is.';btn.disabled=false;return}
  var b=LAST.bindings.map(function(x){var o={variable:x.variable};if(x.surface)o.surface=x.surface;if(x.values)o.values=x.values;else o.value=x.value;return o});
  // words → a few more bindings, by rule (the same rules the Playground uses are not loaded here; keep it minimal)
  var m;
  if((m=/(\d{2,4})\s*(?:gsm|g\b|gr\b)[^,]*(cover|omslag)/.exec(text))){b.push({variable:'variables/substrate/substrate-weight',value:+m[1],surface:'cover'})}
  if((m=/(\d{2,4})\s*(?:gsm|g\b|gr\b)[^,]*(inside|innmat)/.exec(text))){b.push({variable:'variables/substrate/substrate-weight',value:+m[1],surface:'inside'})}
  if(!b.some(function(x){return x.variable==='variables/substrate/substrate-weight'})&&(m=/(\d{2,4})\s*(?:gsm|g\b|gr\b)/.exec(text))){b.push({variable:'variables/substrate/substrate-weight',value:+m[1]})}
  if(/saddle|stitch|stiftet|ryggstift/.test(text))b.push({variable:'variables/finishing/binding',value:'printing/completions/binding/saddle-stitching'});
  else if(/perfect|limfrest|limbind/.test(text))b.push({variable:'variables/finishing/binding',value:'printing/completions/binding/perfect-binding'});
  else if(/wire-?o/.test(text))b.push({variable:'variables/finishing/binding',value:'printing/completions/binding/wire-o-binding'});
  if(/matte? lam|matt lam/.test(text))b.push({variable:'variables/features/surface-finish',value:'printing/features/surface-finish/lamination/matte'});
  else if(/gloss lam|blank lam/.test(text))b.push({variable:'variables/features/surface-finish',value:'printing/features/surface-finish/lamination/gloss'});
  if(/portrait|stående/.test(text))b.push({variable:'variables/configuration/orientation',value:'printing/configurations/orientation/portrait'});
  else if(/landscape|liggende/.test(text))b.push({variable:'variables/configuration/orientation',value:'printing/configurations/orientation/landscape'});
  if(/flat sheet|flat\b|flatt/.test(text))b.push({variable:'variables/configuration/setup-model',value:'printing/configurations/setup-models/flat-sheet'});
  if((m=/(\d{2,6})\s*(?:copies|pcs|stk|eks|ex)\b/.exec(text))){b.push({variable:'variables/order/quantity',value:+m[1]})}
  // the file's "back" question: a one-page PDF with «4/0» or «one-sided» in the answer
  if(/4\/0|one-?sided|ensidig/.test(text)&&LAST.artwork.pages===1)b.push({variable:'variables/features/color-mode',value:'printing/features/colors/none',surface:'back'});
  try{
    var vr=JSON.parse((await rpc('tools/call',{name:'ptpge_validate_config',arguments:{product:product,bindings:b}})).result.content[0].text);
    if((vr.bindings||[]).some(function(x){return x.status==='surface_not_in_setup'})){ // the file's front/back are not this setup's faces → apply to every face (SD-0083 D5)
      var drop={}; (vr.bindings||[]).forEach(function(x){if(x.status==='surface_not_in_setup')drop[x.variable+'@'+x.surface]=1});
      b=b.filter(function(x){return !(x.surface&&drop[x.variable+'@'+x.surface]&&x.variable!=='variables/features/color-mode'&&x.variable!=='variables/features/spot-ink')}).map(function(x){if(x.surface&&drop[x.variable+'@'+x.surface]){var y={};for(var k in x)if(k!=='surface')y[k]=x[k];return y}return x});
      vr=JSON.parse((await rpc('tools/call',{name:'ptpge_validate_config',arguments:{product:product,bindings:b}})).result.content[0].text);
    }
    var qs=(vr.needs_disambiguation||[]).map(function(q){return '<li class="q">'+esc(q.question||q.reason)+'</li>'}).join('');
    var bad=(vr.bindings||[]).filter(function(x){return x.status&&['in_envelope','not_checked','envelope_implied','entailed','in_range','named_ink'].indexOf(x.status)===-1});
    var html='<div class="card"><h2>Validation · '+esc(lab(product))+'</h2>'+(vr.validInEnvelope?'<div class="meta">valid in the envelope</div>':'<div class="warn">not valid: '+esc(bad.map(function(x){return lab(x.variable)+' '+x.status}).join('; '))+'</div>')
      +(qs?'<p class="hint">The specification still asks:</p><ul class="l">'+qs+'</ul><p class="hint">Add the answer to your words and validate again.</p>':'')+'</div>';
    if(vr.complete&&vr.validInEnvelope){
      var fr=JSON.parse((await rpc('tools/call',{name:'ptpge_fingerprint',arguments:{product:product,bindings:b}})).result.content[0].text);
      if(fr.profiles&&fr.profiles.spec){var sp=fr.profiles.spec;
        html+='<div class="card"><h2>Identity</h2><div class="fp">'+(sp.markSvg?'<div><span class="mktile">'+sp.markSvg+'</span><div class="cap">spec · '+esc(sp.short)+'</div></div>':'')+(sp.qrSvg?'<div><span class="mktile">'+sp.qrSvg+'</span><div class="cap"><a href="'+esc(sp.resolverUrl)+'" target="_blank" rel="noopener">resolver ↗</a></div></div>':'')+'</div>'
          +'<p class="meta" style="margin-top:12px">artwork sha256 '+esc(LAST.artwork.sha256)+' — goes into request/1 as the file\'s identity, next to the product\'s.</p><pre>'+esc(sp.canonical)+'</pre></div>';
      } else html+='<div class="card"><pre>'+esc(JSON.stringify(fr,null,2))+'</pre></div>';
    }
    var prev=document.getElementById('res'); if(prev)prev.remove();
    var d=document.createElement('div'); d.id='res'; d.innerHTML=html; out.appendChild(d);
  }catch(e){st.textContent='Validation failed: '+e}
  btn.disabled=false;
}
</script>
</body>
</html>
"""

PAGE = (_TEMPLATE.replace("__FRAME_CSS__", FRAME_CSS).replace("__FRAME_HEADER__", FRAME_HEADER)
        .replace("__FRAME_FOOTER__", FRAME_FOOTER))
