"""Tests for ptpge_search_terms and ptpge_get_term against fixture data.

No network — fixtures mimic the actual shapes verified against dist/v1/
on 2026-05-14, updated 2026-05-20 for Notation v2.0 (SD-0020):
  • Printing-only notation (Ordering Process gets none)
  • § separator between group and element (CF§A4)
  • Hierarchical dash form for structural (CF-FMT-ASER)
  • Top-concept and templates have no notation
"""

from unittest.mock import MagicMock, patch

import pytest

from ptpge_mcp.config import Config
from ptpge_mcp.data import VocabularyCache


def _config() -> Config:
    return Config(
        api_base="https://api.ptpge.org/v1",
        api_user=None,
        api_pass=None,
        refresh_seconds=900,
        log_level="INFO",
    )


_FAKE_VERSION = {
    "version": "2026-05-14",
    "generated": "2026-05-14T10:00:00+02:00",
    "terms": 3,
    "by_level": {"top-concept": 1, "group": 0, "category": 0, "sub-category": 1, "element": 1},
    "by_group": {"configurations": 2},
    "license": "https://creativecommons.org/licenses/by/4.0/",
    "scheme_url": "https://api.ptpge.org/v1/scheme",
}

_FAKE_TERMS = {
    "@context": "https://ptpge.org/v1/context.jsonld",
    "@graph": [
        {
            "id": "https://ptpge.org/v1/printing",
            "type": "skos:Concept",
            "level": "top-concept",
            "label": {"en": "Printing Process"},
            # Top-concept has no notation in v2.0
        },
        {
            "id": "https://ptpge.org/v1/printing/configurations/formats/a-series",
            "type": "skos:Concept",
            "level": "sub-category",
            "label": {"en": "A Series (ISO 216)", "nb": "A-serien (ISO 216)"},
            "notation": "CF-FMT-ASER",
            "group": "configurations",
            "broader": "https://ptpge.org/v1/printing/configurations/formats",
        },
        {
            "id": "https://ptpge.org/v1/printing/configurations/formats/a-series/a4",
            "type": "skos:Concept",
            "level": "element",
            "label": {"en": "A4", "nb": "A4"},
            "notation": "CF§A4",
            "group": "configurations",
            "broader": "https://ptpge.org/v1/printing/configurations/formats/a-series",
            "exactMatch": ["https://www.wikidata.org/wiki/Q254446"],
            "definition": {
                "en": "A4 paper size — 210 × 297 mm.",
                "nb": "A4 papirstørrelse — 210 × 297 mm.",
            },
            "properties": {
                "width": 210,
                "height": 297,
                "unit": "mm",
                "standard": "ISO 216",
            },
        },
    ],
}

_FAKE_SEARCH_INDEX = {
    "version": "2026-05-14",
    "count": 3,
    "terms": [
        {
            "id": "https://ptpge.org/v1/printing",
            "notation": "",   # top-concept has no notation in v2.0
            "level": "top-concept",
            "group": "",
            "label": {"en": "Printing Process"},
            "altLabels": {},
            "definition_en": "The supply-side view of the printing industry — how printed goods are produced.",
            "narrower": [],
        },
        {
            "id": "https://ptpge.org/v1/printing/configurations/formats/a-series",
            "notation": "CF-FMT-ASER",
            "level": "sub-category",
            "group": "configurations",
            "label": {"en": "A Series (ISO 216)", "nb": "A-serien (ISO 216)"},
            "altLabels": {"en": ["A-series", "ISO A"]},
            "definition_en": "ISO 216 A-series paper sizes, based on a 1:sqrt(2) aspect ratio.",
            "narrower": ["https://ptpge.org/v1/printing/configurations/formats/a-series/a4"],
        },
        {
            "id": "https://ptpge.org/v1/printing/configurations/formats/a-series/a4",
            "notation": "CF§A4",
            "level": "element",
            "group": "configurations",
            "label": {"en": "A4", "nb": "A4"},
            "altLabels": {},
            "definition_en": "A4 paper size — 210 by 297 mm.",
            "narrower": [],
        },
    ],
}


@pytest.fixture
def loaded_cache() -> VocabularyCache:
    """Build a cache with patched fetch returning the fake bundles."""
    cache = VocabularyCache(_config())
    fake = {
        "version.json": _FAKE_VERSION,
        "terms.jsonld": _FAKE_TERMS,
        "search-index.json": _FAKE_SEARCH_INDEX,
    }

    def fake_fetch(_self, _client, path):
        return fake[path]

    with patch.object(VocabularyCache, "_fetch_json", fake_fetch), \
         patch.object(VocabularyCache, "_client", return_value=MagicMock()):
        cache.load()
    return cache


# -------------------- get_term --------------------

def test_get_term_by_full_uri(loaded_cache):
    term = loaded_cache.get_term(
        "https://ptpge.org/v1/printing/configurations/formats/a-series/a4"
    )
    assert term is not None
    assert term["notation"] == "CF§A4"
    assert term["level"] == "element"
    assert term["properties"]["width"] == 210


def test_get_term_by_relative_path(loaded_cache):
    term = loaded_cache.get_term(
        "printing/configurations/formats/a-series/a4"
    )
    assert term is not None
    assert term["notation"] == "CF§A4"


def test_get_term_by_leading_slash_path(loaded_cache):
    term = loaded_cache.get_term(
        "/printing/configurations/formats/a-series/a4"
    )
    assert term is not None
    assert term["notation"] == "CF§A4"


def test_get_term_not_found(loaded_cache):
    assert loaded_cache.get_term("does/not/exist") is None
    assert loaded_cache.get_term("https://example.org/foo") is None


# -------------------- search --------------------

def test_search_exact_notation_match_wins(loaded_cache):
    results = loaded_cache.search("CF§A4")
    assert len(results) >= 1
    assert results[0]["notation"] == "CF§A4"
    assert results[0]["score"] == 1.0


def test_search_label_substring(loaded_cache):
    results = loaded_cache.search("Series")
    notations = [r["notation"] for r in results]
    assert "CF-FMT-ASER" in notations


def test_search_definition_substring(loaded_cache):
    results = loaded_cache.search("paper size")
    # Should hit A4 via definition match
    notations = [r["notation"] for r in results]
    assert "CF§A4" in notations


def test_search_groups_filter(loaded_cache):
    results = loaded_cache.search("A", groups=["configurations"])
    # Printing Process top-concept has no group, so it's filtered out
    levels = {r["level"] for r in results}
    assert "top-concept" not in levels


def test_search_respects_limit(loaded_cache):
    results = loaded_cache.search("a", limit=1)
    assert len(results) <= 1


def test_search_returns_empty_for_empty_query(loaded_cache):
    assert loaded_cache.search("") == []
    assert loaded_cache.search("   ") == []


def test_search_result_shape(loaded_cache):
    results = loaded_cache.search("A4")
    hit = results[0]
    assert set(hit.keys()) >= {"id", "notation", "prefLabel", "level", "group", "score"}
