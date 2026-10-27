"""PTPGE TN-2 — production origin: derive, per offering, where and by whom a product is made.

Input: a vendor-declaration/1 document (dict). Output: one record per offering —

    {"offering": i, "name": …, "production": "in-house" | "partly-outsourced" | "outsourced",
     "steps": [{"step": "printing" | <completion URI> | <feature URI>, "operated": "own"|"partner", "site": <id>|None}, …],
     "outsourced": [<step> …],                  # the partner-operated steps, for an agent to name («lamination»)
     "sites": [<site id> …],                    # where the own-operated steps stand
     "countries": [<ISO> …],                    # countries of the own-operated steps' sites
     "certificationsCovering": [<term URI> …],  # certifications that hold where every own step is made
     "notDocumented": [<step> …]}               # partner steps: nothing is known about the partner's certifications

Rule (SD-0114): `operated` is stated on the equipment (presses, finishing machines) with the line as default and
`own` as the default of defaults. The offering uses the line's press(es) plus the completions and embellishments the
offering supports that the line performs. Nothing is stored on the product — this is computed, so the equipment and
the product can never disagree. Byte-identical copy lives in mcp-server/ptpge_mcp/production.py (SD-0083 pattern).
"""
from __future__ import annotations

TERM_PREFIX = "https://ptpge.org/v1/"
COMPLETION = TERM_PREFIX + "printing/completions/"
FEATURE = TERM_PREFIX + "printing/features/"


def _op(obj: dict | None, default: str) -> str:
    v = (obj or {}).get("operated")
    return v if v in ("own", "partner") else default


def derive(doc: dict) -> list[dict]:
    cap = doc.get("capability") or {}
    lines = cap.get("lines") or []
    sites = {s.get("id"): s for s in (doc.get("sites") or []) if isinstance(s, dict)}
    vendor_certs = list(cap.get("certifications") or [])
    out: list[dict] = []
    for i, off in enumerate(doc.get("offerings") or []):
        li = off.get("line")
        line = lines[li] if isinstance(li, int) and 0 <= li < len(lines) else {}
        line_op = _op(line, "own")
        site_id = line.get("site")
        steps: list[dict] = []
        # 1. printing — the line's presses
        presses = line.get("presses") or []
        if presses:
            ops = {_op(p, line_op) for p in presses}
            steps.append({"step": "printing", "operated": "own" if "own" in ops else "partner", "site": site_id})
        else:
            steps.append({"step": "printing", "operated": line_op, "site": site_id})
        # 2. the completions / embellishments the offering supports, limited to what the line performs
        wanted: list[str] = []
        for key, vals in (off.get("supports") or {}).items():
            for v in vals if isinstance(vals, list) else []:
                if isinstance(v, str) and (v.startswith(COMPLETION) or v.startswith(FEATURE)) and v not in wanted:
                    wanted.append(v)
        line_fin = set(line.get("finishing") or [])
        line_emb = set(line.get("embellishment") or [])
        machines = line.get("finishingMachines") or []
        for uri in wanted:
            if uri in line_fin:
                served = [m for m in machines if uri in (m.get("serves") or [])]
                if served:
                    ops = {_op(m, line_op) for m in served}
                    steps.append({"step": uri, "operated": "own" if "own" in ops else "partner", "site": site_id})
                else:
                    steps.append({"step": uri, "operated": line_op, "site": site_id})
            elif uri in line_emb:
                served = [m for m in machines if uri in (m.get("serves") or [])]
                if served:
                    ops = {_op(m, line_op) for m in served}
                    steps.append({"step": uri, "operated": "own" if "own" in ops else "partner", "site": site_id})
                else:
                    steps.append({"step": uri, "operated": line_op, "site": site_id})
            # a value the line does not perform is a vocabulary/offering question, not a production-status one
        ops_all = {s["operated"] for s in steps}
        production = "in-house" if ops_all == {"own"} else ("outsourced" if ops_all == {"partner"} else "partly-outsourced")
        own_sites = sorted({s["site"] for s in steps if s["operated"] == "own" and s["site"]})
        countries = sorted({sites[s].get("country") for s in own_sites if s in sites and sites[s].get("country")})
        if not own_sites and production == "in-house":
            countries = [doc.get("country")] if doc.get("country") else []
        # certifications covering: must hold at every site an own step stands on (vendor-level counts for own sites)
        covering: list[str] = []
        if production != "outsourced":
            cert_sets = []
            for sid in own_sites:
                st = sites.get(sid) or {}
                if st.get("operated", "own") == "own":
                    cert_sets.append(set(vendor_certs) | set(st.get("certifications") or []))
                else:
                    cert_sets.append(set(st.get("certifications") or []))
            if not own_sites:
                cert_sets.append(set(vendor_certs))
            covering = sorted(set.intersection(*cert_sets)) if cert_sets else []
        out.append({
            "offering": i, "name": off.get("name"), "product": off.get("product"),
            "production": production, "steps": steps,
            "outsourced": [s["step"] for s in steps if s["operated"] == "partner"],
            "sites": own_sites, "countries": countries,
            "certificationsCovering": covering,
            "notDocumented": [s["step"] for s in steps if s["operated"] == "partner"],
        })
    return out


def summary(doc: dict) -> dict:
    """Vendor-level view for a directory card: where it produces (own / partner countries) and the offerings' statuses."""
    sites = [s for s in (doc.get("sites") or []) if isinstance(s, dict)]
    own = sorted({s.get("country") for s in sites if s.get("operated") == "own" and s.get("country")})
    partner = sorted({s.get("country") for s in sites if s.get("operated") == "partner" and s.get("country")})
    per = derive(doc)
    counts = {k: sum(1 for r in per if r["production"] == k) for k in ("in-house", "partly-outsourced", "outsourced")}
    return {"ownCountries": own, "partnerCountries": partner, "offerings": counts}
