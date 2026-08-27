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
.cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:8px}
.card{background:#fff;border:1.5px solid var(--line);border-radius:10px;padding:12px 16px;min-width:150px}
.card b{display:block;font-size:26px;line-height:1.1}
.card span{font-size:11.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}
.empty{color:var(--mut);font-size:13.5px;background:#fff;border:1.5px dashed var(--line);
 border-radius:10px;padding:16px 18px}
.note{color:var(--mut);font-size:13px;margin-top:26px;max-width:78ch}
.note b{color:var(--ink)}
.off{background:#fbeaea;border:1.5px solid #e7b9b9;border-radius:10px;padding:12px 16px;
 color:#7a2020;font-size:13.5px;margin-bottom:18px}
"""


def _rows(rows: list[dict], kind: str) -> str:
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
            extra = (f'<code>{esc(r.get("got"))}</code> at {esc(r.get("score"))}'
                     if r.get("got") else "nothing found")
        out.append(f'<tr><td class="n">{esc(r.get("n"))}×</td><td>{what}</td>'
                   f'<td>{extra}</td><td><code>{esc(r.get("first"))} → {esc(r.get("last"))}</code></td></tr>')
    return ('<table><thead><tr><th>Seen</th><th>What was asked</th><th>What came back</th>'
            f'<th>First → last</th></tr></thead><tbody>{"".join(out)}</tbody></table>')


def page_html(snap: dict) -> str:
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
{_rows(snap.get('misses') or [], 'miss')}

<h2><span class="tag weak">BARELY MATCHED</span> &nbsp;<span>an answer came back, but it would lose to the next competing term</span></h2>
{_rows(snap.get('weak') or [], 'weak')}

<h2><span class="tag q">COLOUR QUESTIONS</span> &nbsp;<span>where a count like 4/1 could not be settled by the template (SD-0071)</span></h2>
{_rows(snap.get('colour') or [], 'colour')}

<p class="note"><b>How to use this.</b> A phrase at the top of the first table is the
vocabulary's most expensive blind spot: people keep asking and keep getting nothing. Add it as
a synonym on the term that should own it, then put it in <code>tools/search_corpus.txt</code>
so it can never come back unnoticed. The colour table says something different — it shows which
products force the shorthand to ask, which is a signal about the templates rather than the words.
<br><br><b>What is not here.</b> Successful lookups are never stored; there is nothing to learn
from them. Neither is anything about who asked — no user, no key, no address, no time of day.
Phrases that look like they carry personal data are discarded rather than counted.</p>
</div>
</body></html>
"""
