"""Browser check for playground agent mode: serves PLAYGROUND_HTML through a local
proxy to open.mcp.ptpge.org (tools run LIVE), mocks the model (sponsored proxy,
Anthropic own key, OpenAI own key) with a scripted policy, and asserts the
agent path ends in the same fingerprint as rules mode, renders the mark, and
logs every call. Not collected by pytest (needs Playwright + network):
    python tests/browser/agent_loop_check.py   (proxy on 127.0.0.1:8790)
"""
import asyncio, json, sys, re
from playwright.async_api import async_playwright
PROMPT="I want a folded leaflet on 170 gsm silk paper, matte lamination, full colour both sides, A4, 1000 copies"
STATE={"rules":None,"calls":[],"anthropic_headers":None}
def fake_model(body, sponsored):
    msgs=body["messages"]; n=sum(1 for m in msgs if m["role"]=="assistant")
    tools=[t["name"] for t in body["tools"]]; assert all(t.startswith("ptpge_") for t in tools), tools
    sysx=body["system"]; sys_text=sysx if isinstance(sysx,str) else " ".join(b["text"] for b in sysx)
    assert "PTPGE-PLAYGROUND-AGENT/1" in sys_text and 'language = "en"' in sys_text, sys_text[:300]
    r=STATE["rules"]; prod=r["product"]; binds=r["bindings"]
    plan=[("ptpge_search_terms",{"query":"leaflet","limit":5,"query_language":"en"}),
          ("ptpge_get_product_envelope",{"id_or_path":prod}),
          ("ptpge_validate_config",{"product":prod,"bindings":binds,"language":"en"}),
          ("ptpge_fingerprint",{"product":prod,"bindings":binds,"visuals":True})]
    if n<len(plan):
        name,args=plan[n]
        if n>0:
            last=msgs[-1]; assert last["role"]=="user" and last["content"][0]["type"]=="tool_result", last
            if n==3: assert "validInEnvelope" in last["content"][0]["content"]
        out={"id":"m%d"%n,"stop_reason":"tool_use","content":[{"type":"text","text":"step %d"%(n+1)},{"type":"tool_use","id":"tu%d"%n,"name":name,"input":args}],"usage":{"input_tokens":1000+n,"output_tokens":50}}
    else:
        last=msgs[-1]["content"][0]["content"]; assert '"short"' in last and "markSvg" not in last
        short=json.loads(last)["profiles"]["spec"]["short"]
        out={"id":"mf","stop_reason":"end_turn","content":[{"type":"text","text":"Brochure, A4, folded, 170 gsm silk, matte lamination, CMYK both sides, 1000 copies. Fingerprint "+short+"."}],"usage":{"input_tokens":2000,"output_tokens":60}}
    if sponsored: out["_sponsored"]={"model":"claude-sonnet-5","remaining_today":4,"round":n+1,"max_rounds":12}
    return out
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(args=["--no-sandbox"]); pg=await b.new_page()
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
        async def route_engine(route):
            req=route.request; url=req.url
            if url.endswith("/agent/status"):
                await route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin":"*"}, body=json.dumps({"enabled":True,"model":"claude-sonnet-5","remaining_today":5})); return
            if req.method=="OPTIONS":
                await route.fulfill(status=204, headers={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"Content-Type, X-Agent-Run","Access-Control-Allow-Methods":"POST, GET, OPTIONS"}); return
            body=json.loads(req.post_data); assert req.headers.get("x-agent-run","").startswith("run-")
            STATE["calls"].append("sponsored")
            await route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin":"*"}, body=json.dumps(fake_model(body,True)))
        async def route_anthropic(route):
            req=route.request
            if req.method=="OPTIONS":
                await route.fulfill(status=204, headers={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"*","Access-Control-Allow-Methods":"POST, OPTIONS"}); return
            STATE["anthropic_headers"]=dict(req.headers); body=json.loads(req.post_data); assert body["model"]=="claude-sonnet-5"
            STATE["calls"].append("own")
            await route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin":"*"}, body=json.dumps(fake_model(body,False)))
        async def route_openai(route):
            req=route.request
            if req.method=="OPTIONS":
                await route.fulfill(status=204, headers={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"*","Access-Control-Allow-Methods":"POST, OPTIONS"}); return
            assert req.headers.get("authorization")=="Bearer sk-oa-test"
            body=json.loads(req.post_data); assert body["model"]=="gpt-4.1-mini" and body["messages"][0]["role"]=="system"
            assert all(t["type"]=="function" and t["function"]["name"].startswith("ptpge_") for t in body["tools"])
            # rebuild anthropic-shaped view to reuse fake_model
            n=sum(1 for m in body["messages"] if m["role"]=="assistant")
            amsgs=[]
            for m in body["messages"]:
                if m["role"]=="assistant": amsgs.append({"role":"assistant","content":[]})
                elif m["role"]=="tool": amsgs.append({"role":"user","content":[{"type":"tool_result","tool_use_id":m["tool_call_id"],"content":m["content"]}]})
            if n>0: assert body["messages"][-1]["role"]=="tool" and body["messages"][-2]["role"]=="assistant" and body["messages"][-2]["tool_calls"]
            fm=fake_model({"messages":amsgs,"tools":[{"name":t["function"]["name"]} for t in body["tools"]],"system":body["messages"][0]["content"]}, False)
            msg={"role":"assistant","content":" ".join(b["text"] for b in fm["content"] if b["type"]=="text") or None}
            tcs=[{"id":b["id"],"type":"function","function":{"name":b["name"],"arguments":json.dumps(b["input"])}} for b in fm["content"] if b["type"]=="tool_use"]
            if tcs: msg["tool_calls"]=tcs
            STATE["calls"].append("openai")
            await route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin":"*"}, body=json.dumps({"choices":[{"message":msg,"finish_reason":"tool_calls" if tcs else "stop"}],"usage":{"prompt_tokens":900,"completion_tokens":40}}))
        await pg.route("https://api.openai.com/**", route_openai)
        await pg.route("https://engine.gutenlex.com/**", route_engine)
        await pg.route("https://api.anthropic.com/**", route_anthropic)
        await pg.goto("http://127.0.0.1:8790/playground"); await pg.wait_for_timeout(1500)
        await pg.evaluate("document.querySelectorAll('details').forEach(d=>d.open=true)")
        await pg.fill('#prompt', PROMPT); await pg.evaluate("doResolve()")
        for _ in range(60):
            await pg.wait_for_timeout(400)
            if await pg.evaluate("!!LAST_RESOLVE && LAST_RESOLVE.raw==="+json.dumps(PROMPT)): break
        await pg.evaluate("assembleFingerprint()")
        for _ in range(80):
            await pg.wait_for_timeout(400)
            t=await pg.evaluate("document.getElementById('res-own').innerText")
            if 'sha256' in t: break
        own=await pg.evaluate("document.getElementById('res-own').innerText")
        rules_short=re.search(r'"short": "([0-9a-f]+)"', own).group(1)
        asm=await pg.evaluate("Array.from(document.querySelectorAll('#tr-body .tr-entry')).filter(e=>e.innerText.includes('assembly:')).map(e=>e.innerText).pop()")
        i=asm.index('{'); STATE["rules"]=json.loads(asm[i:]) ; print("rules:", rules_short, len(STATE["rules"]["bindings"]), "bindings")
        st=await pg.evaluate("document.getElementById('ag-status').innerText"); print("status line:", st); assert "5 run(s) left" in st
        await pg.evaluate("agentRun()")
        for _ in range(80):
            await pg.wait_for_timeout(400)
            t=await pg.evaluate("document.getElementById('res-agent').innerText")
            if 'agent_answer' in t or 'agent failed' in t: break
        ag=await pg.evaluate("document.getElementById('res-agent').innerText"); meta=await pg.evaluate("document.querySelector('#res-agent .rmeta').innerText")
        print("META:", meta); assert "agent failed" not in ag, ag[:400]
        ag_short=re.search(r'"short": "([0-9a-f]+)"', ag).group(1); assert ag_short==rules_short, (ag_short, rules_short)
        assert "5 model call(s)" in meta and "4 tool call(s)" in meta, meta
        assert await pg.evaluate("!!document.querySelector('#res-agent .fpwrap svg')"), "mark not rendered"
        tr=await pg.evaluate("Array.from(document.querySelectorAll('#tr-body .tr-meta')).map(x=>x.innerText)")
        agent_entries=[x for x in tr if "by the agent" in x or "model →" in x]; print("transcript agent entries:", len(agent_entries)); assert len(agent_entries)==9, agent_entries
        await pg.select_option('#ag-mode','anthropic'); await pg.fill('#ag-key','sk-ant-test')
        assert await pg.evaluate("document.getElementById('ag-model').value")=="claude-sonnet-5"
        await pg.evaluate("agentRun()")
        for _ in range(80):
            await pg.wait_for_timeout(400)
            t=await pg.evaluate("document.querySelector('#res-agent .rmeta').innerText")
            if 'anthropic' in t: break
        meta2=await pg.evaluate("document.querySelector('#res-agent .rmeta').innerText"); print("META2:", meta2)
        h=STATE["anthropic_headers"]; assert h["x-api-key"]=="sk-ant-test" and h["anthropic-dangerous-direct-browser-access"]=="true" and h["anthropic-version"]=="2023-06-01", h
        assert await pg.evaluate("localStorage.getItem('ptpge-agent-key-anthropic')")=="sk-ant-test"
        await pg.select_option('#ag-mode','openai'); await pg.fill('#ag-key','sk-oa-test')
        assert await pg.evaluate("document.getElementById('ag-model').value")=="gpt-4.1-mini"
        await pg.evaluate("agentRun()")
        for _ in range(80):
            await pg.wait_for_timeout(400)
            t=await pg.evaluate("document.querySelector('#res-agent .rmeta').innerText")
            if 'openai' in t: break
        meta3=await pg.evaluate("document.querySelector('#res-agent .rmeta').innerText"); print("META3:", meta3)
        assert "fingerprint "+rules_short in meta3, meta3
        print("calls:", STATE["calls"].count("sponsored"), "sponsored,", STATE["calls"].count("own"), "own,", STATE["calls"].count("openai"), "openai")
        print("page errors:", errs); assert not errs
        await b.close(); print("AGENT LOOP CHECK OK")
asyncio.run(main())
