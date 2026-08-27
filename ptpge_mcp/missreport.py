"""/miss-report — what the vocabulary fails to find, in a browser.

The CLI (tools/search_miss_report.py) is the regression guard: a fixed corpus,
an exit code, run before a deploy. This is the other half — a page for trying
phrases the moment you think of them, without a terminal.

Same origin as /mcp, so the browser can call the real search directly. Your
phrase list lives in localStorage, so it survives a reload and grows into your
own working corpus; the canonical regression corpus stays in the repo.
"""

DEFAULT_CORPUS = """\
# One phrase per line. Add `expect=<path fragment>` where it matters WHICH
# term wins. Lines starting with # are ignored.

business cards      expect=ordering/products/business-cards
flyers              expect=ordering/products/flyers
leaflets            expect=ordering/products/flyers
brochures           expect=ordering/products/brochures
roll-up banner      expect=ordering/products/rollups
pavement sign       expect=ordering/products/pavement-signs
correx              expect=board-materials/plastic
canvas print        expect=ordering/products/canvas-prints
perfect bound       expect=binding/perfect-binding
wiro                expect=binding/wire-o-binding
spot UV             expect=embellishments/spot-uv-varnish
Pantone             expect=color-matching-systems/pantone-matching-system
NCS                 expect=color-matching-systems/ncs
spot colour         expect=features/colors/spot-color
visittkort          expect=ordering/products/business-cards
kanalplast          expect=board-materials/plastic
Vierfarbdruck       expect=features/colors/cmyk
名刺
スミ                 expect=features/colors/black
"""

PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>PTPGE — Search miss report</title>
<style>
:root{--paper:#faf9f6;--ink:#1a1a1a;--mut:#6a6a72;--line:#e2ddd1;--green:#046A38;
 --ok:#0b6b3a;--okbg:#e7f4ec;--weak:#8a5a00;--weakbg:#fdf3e0;
 --wrong:#a15c00;--wrongbg:#fbeee0;--miss:#a12f2f;--missbg:#fbeaea}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);line-height:1.5;
 font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 24px 60px}
h1{font-size:24px;margin:0 0 4px}
.sub{color:var(--mut);font-size:14px;margin:0 0 20px}
.sub a{color:var(--green)}
textarea{width:100%;min-height:190px;padding:12px 14px;border:1.5px solid var(--line);
 border-radius:10px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:13px;
 line-height:1.55;background:#fff;resize:vertical}
.bar{display:flex;gap:10px;align-items:center;margin:12px 0 20px;flex-wrap:wrap}
button{border:1.5px solid var(--green);background:var(--green);color:#fff;font-weight:700;
 font-size:14px;padding:9px 18px;border-radius:99px;cursor:pointer}
button.ghost{background:#fff;color:var(--green)}
button:disabled{opacity:.5;cursor:default}
.count{font-size:13px;color:var(--mut)}
.sum{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 14px}
.pill{border-radius:99px;padding:6px 14px;font-size:13px;font-weight:700}
.pill.ok{color:var(--ok);background:var(--okbg)}
.pill.weak{color:var(--weak);background:var(--weakbg)}
.pill.wrong{color:var(--wrong);background:var(--wrongbg)}
.pill.miss{color:var(--miss);background:var(--missbg)}
table{width:100%;border-collapse:collapse;background:#fff;border:1.5px solid var(--line);
 border-radius:10px;overflow:hidden;font-size:13.5px}
th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#8a8578;
 padding:9px 12px;background:#fcfbf8}
td{padding:8px 12px;border-top:1px solid #f0ece3;vertical-align:top}
tr.f td{background:#fffdfa}
.v{font-weight:800;font-size:11px;letter-spacing:.04em;border-radius:99px;padding:2px 9px;
 white-space:nowrap}
.v.OK{color:var(--ok);background:var(--okbg)}
.v.WEAK{color:var(--weak);background:var(--weakbg)}
.v.WRONG{color:var(--wrong);background:var(--wrongbg)}
.v.MISS{color:var(--miss);background:var(--missbg)}
code{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;color:#444}
.exp{color:var(--mut);font-size:12px}
.note{color:var(--mut);font-size:13px;margin-top:16px;max-width:76ch}
.note b{color:var(--ink)}
</style></head><body>
<div class="wrap">
<h1>Search miss report</h1>
<p class="sub">What the vocabulary fails to find — type or paste buyer phrases and run them
against the live search. Your list is kept in this browser.
&nbsp;·&nbsp; <a href="/playground">Playground</a></p>

<textarea id="corpus" spellcheck="false"></textarea>
<div class="bar">
  <button id="run">Run</button>
  <button class="ghost" id="reset">Reset to default list</button>
  <button class="ghost" id="copy" disabled>Copy failures</button>
  <span class="count" id="status"></span>
</div>

<div class="sum" id="sum"></div>
<div id="out"></div>

<p class="note"><b>MISS</b> — nothing came back: the word exists in the trade and not in the
vocabulary. <b>WRONG</b> — something came back, but not the term you pinned with
<code>expect=</code>: usually two terms competing for one word. <b>WEAK</b> — the right term,
but barely; it will lose the moment a competitor appears. Add what you find as synonyms on the
right term, and add the phrase to <code>tools/search_corpus.txt</code> so it stays fixed.</p>
</div>

<script>
const KEY = "ptpge-miss-corpus";
const DEFAULT = __DEFAULT__;
const ta = document.getElementById("corpus");
ta.value = localStorage.getItem(KEY) || DEFAULT;
ta.addEventListener("input", () => { try { localStorage.setItem(KEY, ta.value); } catch (e) {} });
document.getElementById("reset").onclick = () => {
  ta.value = DEFAULT; try { localStorage.setItem(KEY, DEFAULT); } catch (e) {}
};

function parse(text) {
  return text.split("\\n").map(l => l.trim())
    .filter(l => l && !l.startsWith("#"))
    .map(l => {
      let expect = null, q = l;
      const i = l.indexOf("expect=");
      if (i > -1) { expect = l.slice(i + 7).trim(); q = l.slice(0, i).trim(); }
      return { q, expect };
    }).filter(r => r.q);
}

async function search(query) {
  const r = await fetch("/mcp", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call",
      params: { name: "ptpge_search_terms", arguments: { query, limit: 3 } } })
  });
  const j = await r.json();
  const txt = j?.result?.content?.[0]?.text;
  if (!txt) return [];
  const d = JSON.parse(txt);
  return d.results || d.terms || [];
}

let failures = [];

document.getElementById("run").onclick = async () => {
  const rows = parse(ta.value);
  const btn = document.getElementById("run"), st = document.getElementById("status");
  btn.disabled = true; failures = [];
  const counts = { OK: 0, WEAK: 0, WRONG: 0, MISS: 0 };
  const body = [];
  for (let i = 0; i < rows.length; i++) {
    st.textContent = `${i + 1} / ${rows.length}…`;
    let hits = [];
    try { hits = await search(rows[i].q); } catch (e) {}
    const top = hits[0];
    const got = top ? (top.id || "").replace("https://ptpge.org/v1/", "") : "";
    const score = top ? top.score : null;
    let v = "OK";
    if (!top) v = "MISS";
    else if (rows[i].expect && !got.includes(rows[i].expect)) v = "WRONG";
    else if (score !== null && score < 0.55) v = "WEAK";
    counts[v]++;
    if (v !== "OK") failures.push(`${rows[i].q}  →  ${got || "nothing"}${
      rows[i].expect ? "  (expected " + rows[i].expect + ")" : ""}`);
    body.push(`<tr class="${v === "OK" ? "" : "f"}">
      <td><span class="v ${v}">${v}</span></td>
      <td>${rows[i].q.replace(/</g, "&lt;")}</td>
      <td><code>${score === null ? "—" : score}</code></td>
      <td><code>${got || "nothing found"}</code>${
        v === "WRONG" ? `<div class="exp">expected ${rows[i].expect}</div>` : ""}</td>
    </tr>`);
  }
  document.getElementById("sum").innerHTML =
    `<span class="pill ok">${counts.OK} ok</span>` +
    (counts.WEAK ? `<span class="pill weak">${counts.WEAK} weak</span>` : "") +
    (counts.WRONG ? `<span class="pill wrong">${counts.WRONG} wrong</span>` : "") +
    (counts.MISS ? `<span class="pill miss">${counts.MISS} missing</span>` : "");
  document.getElementById("out").innerHTML =
    `<table><thead><tr><th></th><th>Phrase</th><th>Score</th><th>Top result</th></tr></thead>
     <tbody>${body.join("")}</tbody></table>`;
  st.textContent = `${rows.length} phrases`;
  btn.disabled = false;
  document.getElementById("copy").disabled = failures.length === 0;
};

document.getElementById("copy").onclick = () => {
  navigator.clipboard.writeText(failures.join("\\n"));
  document.getElementById("copy").textContent = "Copied";
  setTimeout(() => document.getElementById("copy").textContent = "Copy failures", 1400);
};
</script>
</body></html>
"""


def page_html() -> str:
    import json as _json
    return PAGE.replace("__DEFAULT__", _json.dumps(DEFAULT_CORPUS))
