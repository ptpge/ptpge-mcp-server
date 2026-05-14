"""Smoke tests for ptpge_mcp.data — does not hit the network."""

from unittest.mock import MagicMock, patch

from ptpge_mcp.config import Config
from ptpge_mcp.data import TaxonomyCache


def _config() -> Config:
    return Config(
        api_base="https://api.ptpge.org/v1",
        api_user=None,
        api_pass=None,
        refresh_seconds=900,
        log_level="INFO",
    )


def test_load_populates_cache() -> None:
    """load() should fetch all three files and populate the cache atomically."""
    cache = TaxonomyCache(_config())

    fake_responses = {
        "version.json": {"version": "2026-05-03", "term_count": 464},
        "terms.jsonld": {"@context": "...", "@graph": [{"id": "x"}]},
        "search-index.json": {"terms": []},
    }

    def fake_fetch(_self, _client, path):
        return fake_responses[path]

    with patch.object(TaxonomyCache, "_fetch_json", fake_fetch), \
         patch.object(TaxonomyCache, "_client", return_value=MagicMock()):
        cache.load()

    assert cache.version["version"] == "2026-05-03"
    assert cache.terms["@graph"][0]["id"] == "x"
    assert cache.search_index == {"terms": []}


def test_maybe_reload_returns_false_when_version_unchanged() -> None:
    cache = TaxonomyCache(_config())

    same_version = {"version": "2026-05-03", "term_count": 464}
    fake_responses = {
        "version.json": same_version,
        "terms.jsonld": {"@graph": []},
        "search-index.json": {"terms": []},
    }

    def fake_fetch(_self, _client, path):
        return fake_responses[path]

    with patch.object(TaxonomyCache, "_fetch_json", fake_fetch), \
         patch.object(TaxonomyCache, "_client", return_value=MagicMock()):
        cache.load()
        assert cache.maybe_reload() is False
