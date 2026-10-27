"""SD-0114 / TN-2 — production origin: sites[], operated on the equipment, derived status per offering (0.41.0)."""
import copy
import json
import pathlib

import pytest

from ptpge_mcp.production import derive, summary

ROOT = pathlib.Path(__file__).resolve().parents[2]
DECL = json.loads((ROOT / "trykkverk.no/.well-known/ptpge/declaration.json").read_text())
FSC = "https://ptpge.org/v1/printing/standards/certifications/environmental/fsc"
MATTE = "https://ptpge.org/v1/printing/features/surface-finish/lamination/matte"


def _mixed():
    d = copy.deepcopy(DECL)
    d["sites"] = [{"id": "oslo", "country": "NO", "city": "Oslo", "operated": "own", "certifications": [FSC]},
                  {"id": "partner-se", "country": "SE", "operated": "partner"}]
    for ln in d["capability"]["lines"]:
        ln["site"] = "oslo"
    # the A6 brochure's line laminates at a partner
    d["capability"]["lines"][3]["finishingMachines"].append(
        {"supplier": "https://ptpge.org/v1/suppliers/kolbus", "model": "Laminator", "serves": [MATTE], "operated": "partner"})
    # the large-format line is a partner's entirely
    d["capability"]["lines"][1]["operated"] = "partner"
    d["capability"]["lines"][1]["site"] = "partner-se"
    return d


def test_without_fields_everything_is_in_house():
    out = derive(DECL)
    assert out and all(r["production"] == "in-house" for r in out)
    assert all(r["countries"] == ["NO"] for r in out)   # falls back to the vendor's country


def test_mixed_declaration():
    by = {r["name"]: r for r in derive(_mixed())}
    assert by["Business Cards 85×55"]["production"] == "in-house"
    bro = by["Folded Brochure A6"]
    assert bro["production"] == "partly-outsourced"
    assert bro["outsourced"] == [MATTE] and bro["notDocumented"] == [MATTE]
    assert bro["certificationsCovering"] == [FSC] and bro["countries"] == ["NO"]
    panel = by["Panel Print (aluminium composite)"]
    assert panel["production"] == "outsourced" and panel["certificationsCovering"] == [] and panel["countries"] == []


def test_summary_counts():
    s = summary(_mixed())
    assert s["ownCountries"] == ["NO"] and s["partnerCountries"] == ["SE"]
    assert s["offerings"] == {"in-house": 3, "partly-outsourced": 1, "outsourced": 1}


def test_press_level_override_beats_line_default():
    d = copy.deepcopy(DECL)
    ln = d["capability"]["lines"][2]            # Digital Toner SRA3 → business cards
    ln["operated"] = "partner"
    ln["presses"][0]["operated"] = "own"         # the press is ours, the rest of the line is not
    by = {r["name"]: r for r in derive(d)}
    bc = by["Business Cards 85×55"]
    assert bc["steps"][0] == {"step": "printing", "operated": "own", "site": None}
    assert bc["production"] in ("in-house", "partly-outsourced")
