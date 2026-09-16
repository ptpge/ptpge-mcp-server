"""Browser check for 0.27.1 rules convergence: serves PLAYGROUND_HTML through a
local proxy to open.mcp.ptpge.org (tools run LIVE) and asserts the rules path
gives the agent's fingerprint on the reference leaflet prompt, drops the fold
assumption on products whose envelope rejects it, and leaves flat products
unchanged. Not collected by pytest (needs Playwright + network):
    python tests/browser/playground_proxy.py &   (127.0.0.1:8790)
    python tests/browser/rules_fold_check.py
"""
import asyncio, json, re
from playwright.async_api import async_playwright
CASES=[("en","I want a folded leaflet on 170 gsm silk paper, matte lamination, full colour both sides, A4, 1000 copies","ac570760ad06a2e8"),
       ("de","Ich möchte einen gefalzten Flyer auf 170 g Seidenmattpapier, Matt-Laminierung, 4/4, A4, 1000 Exemplare","a64e252cb1b39196"),
       ("en","1000 tri-fold brochures A4, 170 gsm silk, full colour both sides","1c8492ec943dd0d3"),
       ("en","500 business cards, 350 gsm, 4/4, matte lamination","90157276ea9c9730")]
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(args=["--no-sandbox"]); pg=await b.new_page(); errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route("https://engine.gutenlex.com/**", lambda r: r.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin":"*"}, body='{"enabled":true,"model":"claude-sonnet-5","remaining_today":5}'))
        for lang,PROMPT,exp in CASES:
            await pg.goto("http://127.0.0.1:8790/playground"); await pg.wait_for_timeout(1000)
            await pg.evaluate("document.querySelectorAll('details').forEach(d=>d.open=true)")
            await pg.select_option('#q-lang', lang); await pg.fill('#prompt', PROMPT); await pg.evaluate("doResolve()")
            for _ in range(60):
                await pg.wait_for_timeout(400)
                if await pg.evaluate("!!LAST_RESOLVE && LAST_RESOLVE.raw==="+json.dumps(PROMPT)): break
            await pg.evaluate("assembleFingerprint()")
            for _ in range(80):
                await pg.wait_for_timeout(400)
                t=await pg.evaluate("document.getElementById('res-own').innerText")
                if 'sha256' in t or 'not valid' in t or 'stopped' in t or 'question' in t: break
            own=await pg.evaluate("document.getElementById('res-own').innerText")
            m=re.search(r'"short": "([0-9a-f]+)"', own); got=m.group(1) if m else None
            print(lang, PROMPT[:40], "→", got); assert got==exp, (got, exp, own[:300])
        assert not errs, errs; await b.close(); print("RULES FOLD CHECK OK")
asyncio.run(main())
