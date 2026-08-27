"""/learning — what real requests could not resolve, accumulated.

The miss report is something you drive: you type phrases and see how they do.
This is the opposite — it fills itself from whatever actually happens. A word
an agent looked for and did not find, a phrase that only just matched, a colour
count a template could not settle: they land here whether the request came from
us, from the playground, or from somebody's integration.

Nothing identifies a caller. Phrases, scores and counts only.
"""

from __future__ import annotations

import html as _html
import json

from .learning import language_hint


def esc(s) -> str:
    return _html.escape(str(s if s is not None else ""), quote=True)


CSS = """
:root{--paper:#faf9f6;--ink:#1a1a1a;--mut:#6a6a72;--line:#e2ddd1;--green:#046A38;
 --miss:#a12f2f;--missbg:#fbeaea;--weak:#8a5a00;--weakbg:#fdf3e0;--q:#4a4a94;--qbg:#ecebfa}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);line-height:1.5;
 font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:28px 24px 60px}
h1{font-size:24px;margin:0 0 4px}
.sub{color:var(--mut);font-size:14px;margin:0 0 22px}
.sub a{color:var(--green)}
h2{font-size:16px;margin:28px 0 8px}
h2 span{font-weight:400;color:var(--mut);font-size:13px}
table{width:100%;border-collapse:collapse;background:#fff;border:1.5px solid var(--line);
 border-radius:10px;overflow:hidden;font-size:13.5px}
th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#8a8578;
 padding:9px 12px;background:#fcfbf8}
td{padding:8px 12px;border-top:1px solid #f0ece3;vertical-align:top}
td.n{font-weight:800;width:64px}
code{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;color:#444}
.tag{border-radius:99px;padding:2px 9px;font-size:11px;font-weight:800;letter-spacing:.04em}
.tag.miss{color:var(--miss);background:var(--missbg)}
.tag.weak{color:var(--weak);background:var(--weakbg)}
.tag.q{color:var(--q);background:var(--qbg)}
.lang{display:inline-block;font-size:10.5px;font-weight:800;letter-spacing:.04em;
 border-radius:99px;padding:2px 8px;background:#eef0f3;color:#55606b;white-space:nowrap}
.lang.sure{background:#e7f4ec;color:#0b6b3a}
td.lg{width:86px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px}
.card{background:#fff;border:1.5px solid var(--line);border-radius:10px;padding:12px 16px;min-width:150px}
.card b{display:block;font-size:26px;line-height:1.1}
.card span{font-size:11.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}
.empty{color:var(--mut);font-size:13.5px;background:#fff;border:1.5px dashed var(--line);
 border-radius:10px;padding:16px 18px}
.note{color:var(--mut);font-size:13px;margin-top:26px;max-width:78ch}
.note b{color:var(--ink)}
.btn{border:1.5px solid var(--line);background:#fff;color:var(--mut);font-size:11.5px;
 font-weight:700;padding:3px 11px;border-radius:99px;cursor:pointer;white-space:nowrap}
.btn:hover{border-color:var(--miss);color:var(--miss)}
.btn.undo:hover{border-color:var(--green);color:var(--green)}
td.act{width:96px;text-align:right}
details.ign{margin-top:26px}
details.ign summary{cursor:pointer;font-size:13.5px;color:var(--mut)}
details.ign summary b{color:var(--ink)}
.gloss{color:#6a6a72;font-size:12.5px;font-style:italic;margin-top:2px;line-height:1.35}
.ask{border:0;background:none;color:#a9a396;font-size:11.5px;cursor:pointer;padding:2px 0 0;
 display:block;text-decoration:underline dotted}
.ask:hover{color:var(--green)}
.off{background:#fbeaea;border:1.5px solid #e7b9b9;border-radius:10px;padding:12px 16px;
 color:#7a2020;font-size:13.5px;margin-bottom:18px}
"""


def _language_of(row: dict, settled=None) -> tuple[str, bool]:
    """Which language a recorded phrase is in, and whether we actually know.

    Three sources, strongest first:

    1. The vocabulary. Once the word exists as a label or altLabel, the
       standard itself has settled the question — no detector needed. This is
       what makes a row heal: add "Fahnen" as a German altLabel, and the row
       that used to shrug stops guessing and says `de`.
    2. What the caller declared in `query_language`. They know what they typed.
    3. The characters, which only decide non-Latin scripts; for Latin ones it
       is marked a guess, because "fahnen" and "banner" give nothing away.

    Returns (tag, certain). An empty tag means we do not know, and the table
    says so rather than filling the column with plausible fiction.
    """
    phrase = row.get("key") or ""
    if settled:
        found = settled(phrase)
        if found:
            return found, True
    said = row.get("lang")
    if said:
        return said, True
    hint = row.get("hint") or language_hint(phrase)
    if hint:
        return hint.rstrip("?"), not hint.endswith("?")
    return "", False


def _rows(rows: list[dict], kind: str, curatable: bool = False, settled=None) -> str:
    if not rows:
        return ('<div class="empty">Nothing recorded yet — either everything asked for was '
                'found, or no one has asked since this was last cleared.</div>')
    out = []
    for r in rows[:120]:
        if kind == "colour":
            what = (f'<code>{esc(r.get("product"))}</code> · surface '
                    f'<b>{esc(r.get("surface"))}</b> · count <b>{esc(r.get("count"))}</b>')
            extra = f'{esc(r.get("candidates"))} readings open'
        else:
            what = esc(r.get("key"))
            if r.get("gloss"):
                # Read once, kept for good — the meaning of チラシ does not change.
                what += f'<div class="gloss">{esc(r["gloss"])}</div>'
            elif kind != "colour":
                what += (f'<button class="ask" onclick="gloss(this,\''
                         f'{esc(r.get("key"))}\')" title="What does this mean?">'
                         f'what is this?</button>')
            extra = (f'<code>{esc(r.get("got"))}</code> at {esc(r.get("score"))}'
                     if r.get("got") else "nothing found")
        act = ""
        if curatable and kind in ("miss", "weak"):
            act = (f'<td class="act"><button class="btn" '
                   f'onclick="curate(this,\'{esc(r.get("key"))}\')">Out of scope</button></td>')
        elif curatable and kind == "ignored":
            act = (f'<td class="act"><button class="btn undo" '
                   f'onclick="curate(this,\'{esc(r.get("key"))}\',1)">Restore</button></td>')
        elif curatable:
            act = "<td class=\"act\"></td>"
        if kind == "colour":
            lg = ""
        else:
            # Decided at render time, not read from store: the key IS the
            # phrase, so history gets a language too, and a row improves by
            # itself the moment the vocabulary learns the word.
            tag, sure = _language_of(r, settled)
            lg = (f'<span class="lang{" sure" if sure else ""}">'
                  f'{esc(tag if sure else tag + "?")}</span>'
                  if tag else '<span style="color:#c9c4b8">—</span>')
        lgcell = "" if kind == "colour" else f'<td class="lg">{lg}</td>'
        out.append(f'<tr><td class="n">{esc(r.get("n"))}×</td>{lgcell}<td>{what}</td>'
                   f'<td>{extra}</td><td><code>{esc(r.get("first"))} → {esc(r.get("last"))}</code></td>'
                   f'{act}</tr>')
    head = ('<th>Seen</th>'
            + ("" if kind == "colour" else "<th>Lang</th>")
            + '<th>What was asked</th><th>What came back</th><th>First → last</th>'
            + ("<th></th>" if curatable else ""))
    return f'<table><thead><tr>{head}</tr></thead><tbody>{"".join(out)}</tbody></table>' 


def page_html(snap: dict, curatable: bool = False, settled=None) -> str:
    t = snap.get("totals") or {}
    off = "" if snap.get("enabled") else (
        '<div class="off">The recorder is switched off on this server — nothing is being '
        'collected. Set <code>PTPGE_LEARNING_FILE</code> to a writable path to enable it.</div>')
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>PTPGE — What the vocabulary is learning</title>
<style>{CSS}</style></head><body>
<div class="wrap">
<h1>What the vocabulary is learning</h1>
<p class="sub">Lookups that failed, collected from real requests — ours, the playground's,
anybody's agent. No caller is identified: phrases, scores and counts only.
&nbsp;·&nbsp; <a href="/miss-report">Miss report</a> &nbsp;·&nbsp; <a href="/playground">Playground</a></p>
{off}
<div class="cards">
  <div class="card"><b>{t.get('misses', 0)}</b><span>found nothing</span></div>
  <div class="card"><b>{t.get('weak', 0)}</b><span>barely matched</span></div>
  <div class="card"><b>{t.get('colour', 0)}</b><span>colour questions</span></div>
</div>

<h2><span class="tag miss">FOUND NOTHING</span> &nbsp;<span>words the trade uses and the vocabulary does not</span></h2>
{_rows(snap.get('misses') or [], 'miss', curatable, settled)}

<h2><span class="tag weak">BARELY MATCHED</span> &nbsp;<span>an answer came back, but it would lose to the next competing term</span></h2>
{_rows(snap.get('weak') or [], 'weak', curatable, settled)}

<h2><span class="tag q">COLOUR QUESTIONS</span> &nbsp;<span>where a count like 4/1 could not be settled by the template (SD-0071)</span></h2>
{_rows(snap.get('colour') or [], 'colour', curatable)}

{_ignored_block(snap, curatable, settled)}

<p class="note"><b>How to use this.</b> A phrase at the top of the first table is the
vocabulary's most expensive blind spot: people keep asking and keep getting nothing. Add it as
a synonym on the term that should own it, then put it in <code>tools/search_corpus.txt</code>
so it can never come back unnoticed. The colour table says something different — it shows which
products force the shorthand to ask, which is a signal about the templates rather than the words.
<br><br><b>What is not here.</b> Successful lookups are never stored; there is nothing to learn
from them. Neither is anything about who asked — no user, no key, no address, no time of day.
Phrases that look like they carry personal data are discarded rather than counted.</p>
</div>
{_script(curatable)}
</body></html>
"""


def _ignored_block(snap: dict, curatable: bool, settled=None) -> str:
    """Out of scope on purpose — hidden, but still counted.

    Merchandise, apparel, 3D and POS sit outside the 54 product templates by
    decision. Their absence is not a gap, so they should not clutter the list —
    but the hits keep accumulating, so the size of the demand is measured if
    the scope is ever revisited.
    """
    rows = snap.get("ignored") or []
    if not rows:
        return ""
    hits = (snap.get("totals") or {}).get("ignored", 0)
    return (f'<details class="ign"><summary><b>{len(rows)} phrases set aside as out of scope</b>'
            f' — {hits} requests, still counted but not listed above</summary>'
            f'{_rows(rows, "ignored", curatable, settled)}</details>')


def _script(curatable: bool) -> str:
    if not curatable:
        return ""
    return """<script>
const KEY = "ptpge-learning-key";
function askKey() {
  let key = localStorage.getItem(KEY);
  if (!key) {
    key = prompt("Curation key (stored in this browser only):");
    if (key) localStorage.setItem(KEY, key);
  }
  return key;
}
async function gloss(btn, phrase) {
  const key = askKey();
  if (!key) return;
  btn.disabled = true; btn.textContent = "reading…";
  const r = await fetch("/learning/gloss", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Learning-Key": key },
    body: JSON.stringify({ phrase: phrase })
  });
  if (!r.ok) {
    if (r.status === 401) localStorage.removeItem(KEY);
    btn.disabled = false;
    btn.textContent = r.status === 401 ? "wrong key" : "could not read it";
    return;
  }
  const d = await r.json();
  const el = document.createElement("div");
  el.className = "gloss";
  el.textContent = d.gloss || "";
  btn.replaceWith(el);
}
async function curate(btn, phrase, undo) {
  const key = askKey();
  if (!key) return;
  btn.disabled = true; btn.textContent = "…";
  const r = await fetch("/learning/curate", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Learning-Key": key },
    body: JSON.stringify({ phrase: phrase, undo: undo ? 1 : 0 })
  });
  if (r.status === 401) {
    localStorage.removeItem(KEY);
    btn.disabled = false; btn.textContent = "Wrong key";
    return;
  }
  const row = btn.closest("tr");
  if (row) row.style.display = "none";
}
</script>"""


LOCKED = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>PTPGE</title>
<style>
body{margin:0;background:#faf9f6;color:#1a1a1a;min-height:100vh;display:grid;place-items:center;
 font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif}
.b{max-width:44ch;text-align:center;padding:0 24px}
h1{font-size:20px;margin:0 0 8px}
p{color:#6a6a72;font-size:14px;line-height:1.55;margin:0 0 18px}
input{width:100%;padding:10px 13px;border:1.5px solid #e2ddd1;border-radius:9px;font-size:14px}
button{margin-top:10px;border:1.5px solid #046A38;background:#046A38;color:#fff;font-weight:700;
 font-size:14px;padding:9px 20px;border-radius:99px;cursor:pointer}
</style></head><body><div class="b">
<h1>__TITLE__</h1>
<p>__BODY__</p>
__FORM__
</div></body></html>"""


def locked_html(unconfigured: bool = False) -> str:
    """Shown instead of the data when no valid key is presented.

    Nothing about the vocabulary's weaknesses is served here — the page is a
    door, not a preview.
    """
    if unconfigured:
        return (LOCKED.replace("__TITLE__", "Not available")
                      .replace("__BODY__", "This server does not keep a learning record.")
                      .replace("__FORM__", ""))
    form = ('<form method="get"><input name="key" type="password" autofocus '
            'placeholder="Key" autocomplete="off"><br><button>Open</button></form>')
    return (LOCKED.replace("__TITLE__", "Locked")
                  .replace("__BODY__", "What the vocabulary is learning is an internal record. "
                                       "Enter the key to open it.")
                  .replace("__FORM__", form))
