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


# -------------------- v0.3.2: tokenized, language-agnostic search --------------------

def test_search_norwegian_label_found_without_language_param(loaded_cache):
    """Cross-language: nb label must hit even with default language=en."""
    results = loaded_cache.search("a-serien")
    notations = [r["notation"] for r in results]
    assert "CF-FMT-ASER" in notations
    # prefLabel still follows the requested language (en)
    hit = next(r for r in results if r["notation"] == "CF-FMT-ASER")
    assert hit["prefLabel"] == "A Series (ISO 216)"


def test_search_multi_token_and_semantics(loaded_cache):
    """All tokens must match somewhere — across fields."""
    results = loaded_cache.search("series iso")
    notations = [r["notation"] for r in results]
    assert "CF-FMT-ASER" in notations


def test_search_multi_token_one_garbage_token_kills_entry(loaded_cache):
    results = loaded_cache.search("series xyzzy")
    assert results == []


def test_search_token_in_alt_label(loaded_cache):
    results = loaded_cache.search("ISO A")
    notations = [r["notation"] for r in results]
    assert "CF-FMT-ASER" in notations


# --------------------------------------------------------------------------
# Exact-synonym ranking and deterministic ties
# --------------------------------------------------------------------------

class _AltCache:
    """Two terms where one's altLabel is a prefix of the other's."""

    version = {"version": "x", "generated": "y"}

    _entries = [
        {"id": "https://ptpge.org/v1/b-library", "notation": "P:X§LIB",
         "label": {"en": "Pantone Solid"},
         "altLabels": {"ja": ["パントン ソリッド"], "en": ["Pantone Solid Coated"]}},
        {"id": "https://ptpge.org/v1/a-system", "notation": "P:X§SYS",
         "label": {"en": "Pantone"},
         "altLabels": {"ja": ["パントン"], "en": ["PMS"]}},
    ]

    def __init__(self):
        from ptpge_mcp.data import VocabularyCache
        from ptpge_mcp.config import Config
        self._c = VocabularyCache.__new__(VocabularyCache)
        import threading
        self._c._lock = threading.RLock()
        self._c._search_index = {"terms": self._entries}
        self._c._config = None

    def search(self, **kw):
        from ptpge_mcp.data import VocabularyCache
        return VocabularyCache.search(self._c, **kw)


def test_exact_altlabel_outranks_partial(monkeypatch):
    from ptpge_mcp import semantic
    monkeypatch.setattr(semantic, "query_sims", lambda q: None)
    hits = _AltCache().search(query="パントン", limit=5)
    assert hits, "expected both terms to match"
    assert hits[0]["id"].endswith("/a-system"), \
        "an exact synonym must beat a synonym that merely contains the query"
    assert hits[0]["score"] > hits[1]["score"], "scores must not tie here"


def test_altlabel_prefix_tier(monkeypatch):
    from ptpge_mcp import semantic
    monkeypatch.setattr(semantic, "query_sims", lambda q: None)
    hits = _AltCache().search(query="pms", limit=5)
    assert hits[0]["id"].endswith("/a-system")
    assert hits[0]["score"] == 0.9          # exact altLabel


def test_ties_are_deterministic(monkeypatch):
    """Equal scores break on the URI, so repeated calls never reshuffle."""
    from ptpge_mcp import semantic
    monkeypatch.setattr(semantic, "query_sims", lambda q: None)
    c = _AltCache()
    runs = [[h["id"] for h in c.search(query="pantone", limit=5)] for _ in range(5)]
    assert all(r == runs[0] for r in runs), "search order must be stable"
    assert runs[0] == sorted(runs[0]) or len(set(runs[0])) == len(runs[0])


# --------------------------------------------------------------------------
# Learning recorder (SD-0071 §9)
# --------------------------------------------------------------------------

def test_learning_records_only_failures(tmp_path):
    from ptpge_mcp import learning
    learning.reset(); learning.configure(str(tmp_path / "l.json"))
    learning.record_search("gazebo", [])                                   # miss
    learning.record_search("business cards", [{"id": "x", "score": 0.95}])  # fine
    learning.record_search("poster frame", [{"id": "y", "score": 0.41}])    # weak
    snap = learning.snapshot()
    assert [r["key"] for r in snap["misses"]] == ["gazebo"]
    assert [r["key"] for r in snap["weak"]] == ["poster frame"]
    assert snap["totals"]["misses"] == 1


def test_learning_counts_repeats(tmp_path):
    from ptpge_mcp import learning
    learning.reset(); learning.configure(str(tmp_path / "l.json"))
    for _ in range(3):
        learning.record_search("correx", [])
    assert learning.snapshot()["misses"][0]["n"] == 3


def test_learning_drops_anything_personal(tmp_path):
    from ptpge_mcp import learning
    learning.reset(); learning.configure(str(tmp_path / "l.json"))
    learning.record_search("anna@example.com", [])            # address
    learning.record_search("order 998877665544", [])          # long digit run
    learning.record_search("x" * 200, [])                     # a prompt, not a term
    assert learning.snapshot()["totals"]["misses"] == 0


def test_learning_records_colour_questions(tmp_path):
    from ptpge_mcp import learning
    learning.reset(); learning.configure(str(tmp_path / "l.json"))
    learning.record_colour_question(
        "https://ptpge.org/v1/ordering/products/business-cards", "back", 1, 3)
    row = learning.snapshot()["colour"][0]
    assert row["surface"] == "back" and row["count"] == 1 and row["candidates"] == 3


def test_learning_survives_a_restart(tmp_path):
    from ptpge_mcp import learning
    path = str(tmp_path / "l.json")
    learning.reset(); learning.configure(path)
    learning.record_search("wiro", [])
    learning.flush()
    # A fresh process starts with empty memory but the file still on disk —
    # reset() would also wipe the file, which is not what a restart does.
    learning._state.update({"misses": {}, "weak": {}, "colour": {}})
    learning._path = None
    learning.configure(path)
    assert any(r["key"] == "wiro" for r in learning.snapshot()["misses"])


def test_learning_disabled_is_silent():
    from ptpge_mcp import learning
    learning.reset(); learning.configure(None)
    learning.record_search("anything", [])          # must not raise
    assert learning.snapshot()["enabled"] is False


def test_ignored_phrases_leave_the_list_but_keep_counting(tmp_path):
    """Out of scope by decision is not a gap — hide it, but keep the demand."""
    from ptpge_mcp import learning
    learning.reset(); learning.configure(str(tmp_path / "l.json"))
    learning.record_search("ballpoint pens", [])
    assert learning.snapshot()["totals"]["misses"] == 1

    assert learning.ignore("ballpoint pens", "merch — outside the 54 templates")
    snap = learning.snapshot()
    assert snap["misses"] == []                       # off the list
    assert snap["ignored"][0]["key"] == "ballpoint pens"

    for _ in range(5):
        learning.record_search("ballpoint pens", [])  # asked again, still hidden
    snap = learning.snapshot()
    assert snap["misses"] == []
    assert snap["totals"]["ignored"] == 5             # but the demand is measured


def test_ignore_can_be_undone(tmp_path):
    from ptpge_mcp import learning
    learning.reset(); learning.configure(str(tmp_path / "l.json"))
    learning.ignore("mugs")
    assert learning.unignore("mugs")
    learning.record_search("mugs", [])
    assert learning.snapshot()["misses"][0]["key"] == "mugs"


def test_learning_page_route_survives_a_configured_key(tmp_path, monkeypatch):
    """The gate must run, not crash.

    A key set on the server is the only path that reaches the lock; a typo in
    the endpoint's own parameter name therefore stays invisible until the
    moment it matters. This walks all three doors: no key, wrong key, right key.
    """
    from starlette.testclient import TestClient
    from ptpge_mcp import learning, server as server_mod

    learning.reset()
    learning.configure(str(tmp_path / "l.json"))
    learning.record_search("チラシ", [])

    # The app is built for its routes only; the vocabulary is fetched over the
    # network at startup and is irrelevant to a gate that runs before any data.
    monkeypatch.setattr(server_mod.VocabularyCache, "load", lambda self: None)
    monkeypatch.setattr(server_mod.VocabularyCache, "maybe_reload", lambda self: None)

    monkeypatch.delenv("PTPGE_LEARNING_KEY", raising=False)
    client = TestClient(server_mod.build_app(), raise_server_exceptions=False)
    assert client.get("/learning").status_code == 404       # not configured here

    monkeypatch.setenv("PTPGE_LEARNING_KEY", "sesame")
    assert client.get("/learning").status_code == 401       # configured, unlocked
    assert client.get("/learning?key=nope").status_code == 401

    ok = client.get("/learning?key=sesame")
    assert ok.status_code == 200
    assert "チラシ" in ok.text and "Out of scope" in ok.text
    assert "ja" in ok.text                                  # the language column


def test_settled_language_prefers_the_vocabulary_over_a_guess():
    """The standard answers before the detector does — and stays quiet when
    the word belongs to two languages at once."""
    from ptpge_mcp.learning import settled_language
    from ptpge_mcp.learningpage import _language_of

    settled = settled_language({"terms": [
        {"label": {"en": "Business cards", "nb": "Visittkort"},
         "altLabels": {"de": ["Visitenkarten"], "en": ["Banner"]}},
        {"label": {"de": "Banner"}, "altLabels": {}},
    ]})

    # Known in exactly one language: settled, and certain.
    assert _language_of({"key": "visittkort"}, settled) == ("nb", True)
    assert _language_of({"key": "Visitenkarten"}, settled) == ("de", True)
    # Known in two: the vocabulary declines to choose, so we do not invent one.
    assert _language_of({"key": "banner"}, settled) == ("", False)
    # Unknown to the vocabulary — that is what a miss IS — so fall down the
    # ladder: what the caller declared, then the characters, then nothing.
    assert _language_of({"key": "dekaler", "lang": "sv"}, settled) == ("sv", True)
    assert _language_of({"key": "チラシ"}, settled) == ("ja", True)
    assert _language_of({"key": "faltblätter"}, settled) == ("de", False)
    assert _language_of({"key": "fahnen"}, settled) == ("", False)
