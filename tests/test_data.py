"""Smoke tests for ptpge_mcp.data — does not hit the network."""

from unittest.mock import MagicMock, patch

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


def test_load_populates_cache() -> None:
    """load() should fetch all three files and populate the cache atomically."""
    cache = VocabularyCache(_config())

    fake_responses = {
        "version.json": {"version": "2026-05-03", "term_count": 464},
        "terms.jsonld": {"@context": "...", "@graph": [{"id": "x"}]},
        "search-index.json": {"terms": []},
    }

    def fake_fetch(_self, _client, path):
        return fake_responses[path]

    with patch.object(VocabularyCache, "_fetch_json", fake_fetch), \
         patch.object(VocabularyCache, "_client", return_value=MagicMock()):
        cache.load()

    assert cache.version["version"] == "2026-05-03"
    assert cache.terms["@graph"][0]["id"] == "x"
    assert cache.search_index == {"terms": []}


def test_maybe_reload_returns_false_when_version_unchanged() -> None:
    cache = VocabularyCache(_config())

    same_version = {"version": "2026-05-03", "term_count": 464}
    fake_responses = {
        "version.json": same_version,
        "terms.jsonld": {"@graph": []},
        "search-index.json": {"terms": []},
    }

    def fake_fetch(_self, _client, path):
        return fake_responses[path]

    with patch.object(VocabularyCache, "_fetch_json", fake_fetch), \
         patch.object(VocabularyCache, "_client", return_value=MagicMock()):
        cache.load()
        assert cache.maybe_reload() is False


def test_inflected_forms_never_displace_an_exact_label():
    """SD-0072. The buyer's grammar is not a signal — but it is the weaker one.

    German Booklets is «Broschüren» and Brochures is «Broschüre». Tolerating
    number means each is now reachable by either form; ranking inflection below
    exact means the term that owns the word outright still wins it. Both
    properties matter, and only together: tolerance without the ordering would
    make the two products indistinguishable.
    """
    from ptpge_mcp.inflect import variants, index_for

    assert "broschüren" in variants("Broschüre")
    assert "broschüre" in variants("Broschüren")
    assert "visitenkarten" in variants("Visitenkarte")
    assert "stickers" in variants("Sticker") and "sticker" in variants("Stickers")

    # Truncation is the dangerous direction and is held back: a short stub that
    # is a real word with another meaning must never be generated.
    assert "post" not in variants("Poster")
    assert "bann" not in variants("Banner")
    assert "heft" not in variants("Hefter")

    # A form that some term already owns exactly is not also an inflection of
    # it — otherwise a label would compete with itself one tier down.
    labels, _ = index_for({"label": {"de": "Broschüre", "en": "Brochures"}})
    assert "brochures" not in labels

    # CJK has no number; generating suffixed forms there would be nonsense.
    labels, _ = index_for({"label": {"ja": "名刺", "zh-Hans": "名片"}})
    assert labels == frozenset()


def test_a_product_wins_a_tie_but_never_a_better_match():
    """SD-0073's ranking half: a tie-break, and strictly only that.

    If a product could outrank a better match, the name collisions the
    conformance check exists to expose would stop being visible in search —
    which is exactly how the singular/plural defect stayed hidden.
    """
    from ptpge_mcp.data import VocabularyCache

    def rank(pairs):
        results = list(pairs)
        results.sort(key=lambda r: (-r[0], 0 if "/ordering/products/" in (r[1].get("id") or "") else 1,
                                    r[1].get("id") or ""))
        return [r[1]["id"] for r in results]

    product = {"id": "https://ptpge.org/v1/ordering/products/rollups"}
    fmt = {"id": "https://ptpge.org/v1/printing/configurations/formats/rollups"}
    audience = {"id": "https://ptpge.org/v1/ordering/audiences/retail"}

    # Equal score: the orderable thing goes first.
    assert rank([(0.95, fmt), (0.95, product)])[0] == product["id"]
    # Better score elsewhere: the product does NOT jump the queue.
    assert rank([(0.95, fmt), (0.93, product)])[0] == fmt["id"]
    # And the ordering stays total, so results never depend on index order.
    assert rank([(0.9, audience), (0.9, fmt), (0.9, product)]) == [
        product["id"], audience["id"], fmt["id"]]


def test_er_is_a_plural_in_german_and_a_new_word_in_english():
    """Language-gated suffixes. «Bild → Bilder» is grammar; «mail → mailer» is
    a different word, and treating them alike reported a name collision that
    did not exist."""
    from ptpge_mcp.inflect import variants

    assert "bilder" in variants("Bild", "de")
    assert "mailer" not in variants("Mail", "en")
    assert "printer" not in variants("Print", "en")
    assert "korter" in variants("Kort", "nb")
    # English keeps the number rules it does have.
    assert variants("Mail", "en") == {"mails"}
    assert "sticker" in variants("Stickers", "en")
    # No language given: widest reading, for a caller checking one word alone.
    assert "mailer" in variants("Mail")
