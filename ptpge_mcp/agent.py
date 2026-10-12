"""Sponsored Playground runs — the model proxy, on the PTPGE server (0.34.0).

Until 0.33 the Playground's «Sponsored run» went through engine.gutenlex.com.
PTPGE is the specification and must not depend on an implementer's service,
so the proxy now lives here. The key never leaves this server; prompts are not
logged, only counts.

    GET  /agent/status    → {enabled, model, remaining_today, per_ip, global, max_rounds, day}
    POST /agent/messages  {system, messages[], tools[], max_tokens?}  → Anthropic Messages response
                           + _sponsored {model, remaining_today, round, max_rounds}

Env:  ANTHROPIC_API_KEY     the key for sponsored runs (absent → 503, the page says «use your own key»)
      PTPGE_AGENT_MODEL     default claude-sonnet-5
      PTPGE_AGENT_ENABLED   "1"/"0" kill switch (default 1)
      PTPGE_AGENT_PER_IP    runs per IP per UTC day (default 5)
      PTPGE_AGENT_GLOBAL    runs per UTC day, all IPs (default 300)
      PTPGE_AGENT_MAX_ROUNDS model calls that count as ONE run (default 12)
      PTPGE_AGENT_STORE     counters file (default ~/data/ptpge-agent-usage.json)
      PTPGE_AGENT_ORIGINS   extra allowed Origins, comma list (the playground hosts are always allowed)

The proxy only serves the Playground agent: the system prompt must carry the
marker, the tools must be ptpge_* tools from tools/list. One run = one
X-Agent-Run id made up by the browser; the per-IP and global caps count runs,
the round cap counts model calls per run.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

AGENT_MARKER = "PTPGE-PLAYGROUND-AGENT/1"
_DEFAULT_ORIGINS = ["https://mcp.ptpge.org", "https://open.mcp.ptpge.org", "https://ptpge.org",
                    "https://trykkverk.no", "http://localhost:8765", "http://127.0.0.1:8765"]
_lock = threading.Lock()


def cfg() -> dict:
    extra = [o.strip() for o in os.environ.get("PTPGE_AGENT_ORIGINS", "").split(",") if o.strip()]
    return {
        "key": os.environ.get("ANTHROPIC_API_KEY", "").strip(),
        "model": os.environ.get("PTPGE_AGENT_MODEL", "claude-sonnet-5").strip(),
        "enabled": os.environ.get("PTPGE_AGENT_ENABLED", "1").strip() != "0",
        "per_ip": int(os.environ.get("PTPGE_AGENT_PER_IP", "5") or 5),
        "global": int(os.environ.get("PTPGE_AGENT_GLOBAL", "300") or 300),
        "max_rounds": int(os.environ.get("PTPGE_AGENT_MAX_ROUNDS", "12") or 12),
        "origins": list(dict.fromkeys(_DEFAULT_ORIGINS + extra)),
    }


def _store() -> Path:
    p = os.environ.get("PTPGE_AGENT_STORE", "").strip()
    return Path(p) if p else Path.home() / "data" / "ptpge-agent-usage.json"


def _load() -> dict:
    try:
        d = json.loads(_store().read_text())
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return {}


def _save(d: dict) -> None:
    p = _store()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d))
    tmp.replace(p)


def _day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _ip_key(request: Request) -> str:
    ip = request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")
    ip = ip.split(",")[0].strip()
    return hashlib.sha256(("ptpge-agent-ip:" + ip).encode()).hexdigest()[:16]


def _usage(request: Request) -> tuple[dict, dict]:
    """Today's counters: (store, ip_record). Old days are dropped."""
    d = _load()
    day = _day()
    rec = d.get(day) or {"runs": 0, "calls": 0, "in": 0, "out": 0, "ips": {}}
    d = {day: rec}
    ipk = _ip_key(request)
    ipr = rec["ips"].get(ipk) or {"runs": 0, "calls": 0, "run_id": "", "run_calls": 0}
    rec["ips"][ipk] = ipr
    return d, ipr


def _cors(request: Request) -> dict:
    origin = request.headers.get("origin", "")
    c = cfg()
    allow = origin if origin in c["origins"] else c["origins"][0]
    return {"Access-Control-Allow-Origin": allow, "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-Agent-Run", "Vary": "Origin"}


def _resp(request: Request, code: int, obj: dict) -> Response:
    return JSONResponse(obj, status_code=code, headers=_cors(request))


def status_payload(request: Request) -> dict:
    c = cfg()
    d, ipr = _usage(request)
    day = d[_day()]
    remaining = max(0, min(c["per_ip"] - ipr["runs"], c["global"] - day["runs"]))
    return {"enabled": bool(c["enabled"] and c["key"]), "model": c["model"], "remaining_today": remaining,
            "per_ip": c["per_ip"], "global": c["global"], "max_rounds": c["max_rounds"], "day": _day(),
            "paid_by": "PTPGE",
            "note": "Sponsored Playground runs, paid by PTPGE. The key never leaves this server; prompts are not logged, only counts."}


async def agent_status(request: Request) -> Response:
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=_cors(request))
    return _resp(request, 200, status_payload(request))


async def agent_messages(request: Request) -> Response:
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=_cors(request))
    c = cfg()
    if not c["enabled"] or not c["key"]:
        return _resp(request, 503, {"error": "sponsored runs are switched off — use your own key"})
    origin = request.headers.get("origin", "")
    if origin and origin not in c["origins"]:
        return _resp(request, 403, {"error": "origin not allowed for sponsored runs"})
    try:
        raw = await request.body()
        if len(raw) > 200 * 1024:
            return _resp(request, 400, {"error": "body too large"})
        body = json.loads(raw.decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("body must be an object")
    except Exception as e:
        return _resp(request, 400, {"error": str(e)})
    system = body.get("system")
    system_text = " ".join(str(b.get("text", "")) for b in system if isinstance(b, dict)) if isinstance(system, list) else str(system or "")
    if AGENT_MARKER not in system_text:
        return _resp(request, 400, {"error": "this proxy only serves the PTPGE Playground agent"})
    tools = body.get("tools") or []
    if not isinstance(tools, list) or not tools or any(not str(t.get("name", "")).startswith("ptpge_") for t in tools if isinstance(t, dict)):
        return _resp(request, 400, {"error": "tools must be the ptpge_* tools from tools/list"})
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages or len(messages) > 60:
        return _resp(request, 400, {"error": "messages: 1–60 entries"})
    max_tokens = min(int(body.get("max_tokens") or 1500), 4000)
    run_id = (request.headers.get("x-agent-run") or "").strip()[:40]
    with _lock:
        d, ipr = _usage(request)
        day = d[_day()]
        new_run = bool(run_id) and run_id != ipr.get("run_id")
        if new_run or not run_id:
            if ipr["runs"] >= c["per_ip"]:
                _save(d)
                return _resp(request, 429, {"error": f"{c['per_ip']} sponsored runs per day reached for this address — use your own key, or come back tomorrow", "remaining_today": 0})
            if day["runs"] >= c["global"]:
                _save(d)
                return _resp(request, 429, {"error": "today's sponsored runs are used up — use your own key", "remaining_today": 0})
            ipr["runs"] += 1; day["runs"] += 1
            ipr["run_id"] = run_id; ipr["run_calls"] = 0
        ipr["run_calls"] = int(ipr.get("run_calls") or 0) + 1
        if ipr["run_calls"] > c["max_rounds"]:
            _save(d)
            return _resp(request, 429, {"error": f"a run is limited to {c['max_rounds']} model calls"})
        ipr["calls"] += 1; day["calls"] += 1
        _save(d)
    payload = {"model": c["model"], "max_tokens": max_tokens,
               "system": [{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
               "tools": tools, "messages": messages}
    if isinstance(body.get("tool_choice"), dict):
        payload["tool_choice"] = body["tool_choice"]
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "x-api-key": c["key"], "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            out = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode())
        except Exception:
            detail = {"message": str(e)}
        return _resp(request, 502, {"error": "model call failed", "status": e.code, "detail": detail})
    except Exception as e:
        return _resp(request, 502, {"error": "model call failed", "detail": str(e)})
    usage = out.get("usage") or {}
    with _lock:
        d, ipr = _usage(request)
        day = d[_day()]
        day["in"] += int(usage.get("input_tokens") or 0)
        day["out"] += int(usage.get("output_tokens") or 0)
        _save(d)
    remaining = max(0, min(c["per_ip"] - ipr["runs"], c["global"] - day["runs"]))
    out["_sponsored"] = {"model": c["model"], "remaining_today": remaining, "round": ipr.get("run_calls"), "max_rounds": c["max_rounds"], "paid_by": "PTPGE"}
    return _resp(request, 200, out)
