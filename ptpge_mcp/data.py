"""Fetches and caches PTPGE vocabulary data from api.ptpge.org.

Strategy:
- At startup, fetch terms.jsonld, search-index.json, and version.json.
- Cache them in-memory.
- Build lookup indices for O(1) get_term and fast search.
- Periodically check version.json; reload everything if the version changed.
- Never block on a refresh failure — keep serving the cached data.

Data shapes (verified against dist/v1/ on 2026-05-14):
- version.json: {"version", "generated", "terms", "by_level", "by_group", "license", "scheme_url"}
- search-index.json: {"version", "count", "terms": [{"id", "notation", "level", "group", "label", "altLabels", "definition_en", "narrower"}, ...]}
- terms.jsonld: {"@context", "@graph": [...full term objects...]}
"""

import logging
import re
import threading
import time
from typing import Any

import httpx

from . import inflect, semantic
from .config import Config

# Hybrid search weights (used only when semantic embeddings are available).
_LEX_WEIGHT = 0.35
_SEM_WEIGHT = 0.65
# Inflected forms of each label, built once per term and memoised on the term
# itself: the work is pure and the index is rebuilt on every reload, so there
# is nothing to invalidate.
_INFLECT_KEY = "_inflected_forms"


def _inflected(entry: dict) -> tuple[frozenset, frozenset]:
    forms = entry.get(_INFLECT_KEY)
    if forms is None:
        forms = inflect.index_for(entry)
        entry[_INFLECT_KEY] = forms
    return forms


_SEM_THRESHOLD = 0.35  # minimum blended score to surface a semantic-only hit

logger = logging.getLogger(__name__)


class VocabularyCache:
    """In-memory cache of PTPGE vocabulary data.

    Thread-safe for read operations once load() has completed at least once.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._lock = threading.RLock()
        self._version: dict[str, Any] | None = None
        self._terms: dict[str, Any] | None = None
        self._search_index: dict[str, Any] | None = None
        self._term_index: dict[str, dict[str, Any]] = {}
        self._search_index_by_id: dict[str, dict[str, Any]] = {}
        self._loaded_at: float = 0.0

    @property
    def version(self) -> dict[str, Any]:
        with self._lock:
            if self._version is None:
                raise RuntimeError("VocabularyCache.load() has not been called yet")
            return self._version

    @property
    def terms(self) -> dict[str, Any]:
        with self._lock:
            if self._terms is None:
                raise RuntimeError("VocabularyCache.load() has not been called yet")
            return self._terms

    @property
    def search_index(self) -> dict[str, Any]:
        with self._lock:
            if self._search_index is None:
                raise RuntimeError("VocabularyCache.load() has not been called yet")
            return self._search_index

    def _client(self) -> httpx.Client:
        auth = None
        if self._config.api_user and self._config.api_pass:
            auth = (self._config.api_user, self._config.api_pass)
        return httpx.Client(auth=auth, timeout=30.0, follow_redirects=True)

    def _fetch_json(self, client: httpx.Client, path: str) -> dict[str, Any]:
        url = f"{self._config.api_base}/{path.lstrip('/')}"
        response = client.get(url)
        response.raise_for_status()
        return response.json()

    def _build_indices(self) -> None:
        """Build O(1) lookup tables from the loaded bundles. Caller holds lock."""
        term_index: dict[str, dict[str, Any]] = {}
        for term in (self._terms or {}).get("@graph", []):
            tid = term.get("id") or term.get("@id")
            if tid:
                term_index[tid] = term
        search_by_id: dict[str, dict[str, Any]] = {}
        for entry in (self._search_index or {}).get("terms", []):
            tid = entry.get("id")
            if tid:
                search_by_id[tid] = entry
        self._term_index = term_index
        self._search_index_by_id = search_by_id

    def load(self) -> None:
        """Fetch all data from the API and replace the cache atomically."""
        logger.info("Loading vocabulary data from %s", self._config.api_base)
        with self._client() as client:
            version = self._fetch_json(client, "version.json")
            terms = self._fetch_json(client, "terms.jsonld")
            search_index = self._fetch_json(client, "search-index.json")

        with self._lock:
            self._version = version
            self._terms = terms
            self._search_index = search_index
            self._loaded_at = time.time()
            self._build_indices()

        logger.info(
            "Loaded vocabulary version %s (%s terms, %s indexed)",
            version.get("version"),
            version.get("terms"),
            len(self._term_index),
        )

    # ------------------------------------------------------------------
    # Lookup helpers used by MCP tool implementations
    # ------------------------------------------------------------------

    def all_terms(self) -> dict[str, dict[str, Any]]:
        """{uri: term} for every indexed term (a snapshot of the index)."""
        with self._lock:
            return dict(self._term_index)

    def get_term(self, id_or_path: str) -> dict[str, Any] | None:
        """Look up a term by full URI or by relative path under /v1/.

        Examples of accepted inputs:
            https://ptpge.org/v1/printing/configurations/formats/a-series/a4
            printing/configurations/formats/a-series/a4
            /printing/configurations/formats/a-series/a4
        """
        with self._lock:
            if id_or_path in self._term_index:
                return self._term_index[id_or_path]
            # Try as relative path under the canonical base
            rel = id_or_path.lstrip("/")
            candidate = f"https://ptpge.org/v1/{rel}"
            return self._term_index.get(candidate)

    def search(
        self,
        query: str,
        limit: int = 10,
        groups: list[str] | None = None,
        language: str = "en",
        include_deprecated: bool = False,
    ) -> list[dict[str, Any]]:
        """Tokenized, language-agnostic search over the search index (v0.3.2).

        SD-0097 (0.29.0): deprecated terms are skipped unless include_deprecated — a deprecated
        term still resolves by URI, but a search for «Heidelberg» should land on the register
        entry (/v1/suppliers/…), not on the retired vocabulary node. Register entries and schemas
        carry `kind` (supplier | vendor | schema) in the result so agents can tell them from terms.

        The query is split into tokens on whitespace and common separators
        (comma, semicolon, slash, pipe), with surrounding punctuation stripped
        (internal hyphens kept). An entry matches when
        EVERY token matches somewhere (AND semantics). Matching looks across
        ALL language variants of label/altLabels — not just the requested
        language — so a Norwegian agent searching "trekkspill" finds
        Accordion Fold without setting language=nb. The `language` parameter
        controls which prefLabel is RETURNED, not which languages are
        searched. (Pre-0.3.2 the whole query was matched as one substring
        against one language's label, so multi-word and cross-language
        queries silently returned nothing — the v1 test-prompt killer.)

        Scoring (higher = more relevant):
            1.00 — whole query exactly equals `notation`
            0.95 — whole query exactly equals a label (any language)
            0.90 — whole query exactly equals an altLabel (any language)
            0.85 — a label (any language) starts with the whole query
            0.80 — an altLabel (any language) starts with the whole query
            otherwise, min over tokens of the best per-token score:
                0.70 — token substring in a label (any language)
                0.60 — token substring in an altLabel (any language)
                0.50 — token substring in the notation
                0.40 — token substring in a definition
            (min = weakest-link: every token must earn its place)
        """
        q = (query or "").strip().lower()
        if not q:
            return []
        # Split on whitespace AND common separators (comma, semicolon, slash,
        # pipe) so natural prompt phrasing — "A4, CMYK, saddle-stitch" — tokenizes
        # cleanly; strip surrounding punctuation per token but keep internal
        # hyphens (saddle-stitch, fold-binding-edge).
        tokens = [t.strip(".,;:!?()[]\"'") for t in re.split(r"[\s,;/|]+", q)]
        tokens = [t for t in tokens if t]
        groups_filter = set(groups) if groups else None

        # gsm-vakt: «250 gsm» er en VEKT, aldri et format. Uten vakten lot
        # talltoleransen (SD-0072) 250 treffe «B4 (250 x 353 mm)» — funnet i
        # Helloprint-dekningsmålingen 2026-08-30. I vektkontekst (gsm/g-m²
        # i spørringen) hopper vi over format-termer helt, og ruter tallet
        # til paper-weights-KLASSEN hvis definisjonsområde inneholder det
        # (240–309 → Heavy Paper). Klassene bærer områdene i definisjonene
        # sine, så vakten holder seg synkron med vokabularet av seg selv.
        weight_ctx = bool(re.search(r"\b(gsm|g/m2|g/m²|gram)\b", q))
        weight_n = None
        if weight_ctx:
            mnum = re.search(r"\b(\d{2,4})\b", q)
            weight_n = int(mnum.group(1)) if mnum else None

        def _gsm_range(entry: dict) -> tuple[int, int] | None:
            d = entry.get("definition_en") or ""
            m = re.search(r"(\d+)\s*[–—-]\s*(\d+)\s*gsm", d)
            if m:
                return int(m.group(1)), int(m.group(2))
            m = re.search(r"above\s+(\d+)\s*gsm", d, re.I)
            if m:
                return int(m.group(1)), 10**6
            return None

        results: list[tuple[float, dict[str, Any]]] = []
        # Dense (embedding) similarities, keyed by full term URI; None if the
        # semantic layer is unavailable (then we fall back to pure lexical).
        sems = semantic.query_sims(q)
        with self._lock:
            entries = (self._search_index or {}).get("terms", [])

        for entry in entries:
            if groups_filter and entry.get("group") not in groups_filter:
                continue
            if entry.get("status") == "deprecated" and not include_deprecated:
                continue
            eid = entry.get("id") or ""
            if weight_ctx and "/configurations/formats/" in eid:
                continue  # gsm-vakten: et vekttall skal aldri bli et ark-format
            notation = (entry.get("notation") or "").lower()
            labels = [
                str(v).lower()
                for v in (entry.get("label") or {}).values()
                if v
            ]
            alt_values = [
                (a or "").lower()
                for alts in (entry.get("altLabels") or {}).values()
                for a in (alts or [])
            ]
            definitions = [
                d.lower()
                for d in (
                    entry.get(f"definition_{language}"),
                    entry.get("definition_en"),
                )
                if d
            ]

            # Whole-query exact/prefix matches rank above token matches.
            # An exact synonym hit must outrank a partial one: searching
            # «パントン» should reach the system that IS called that, not the
            # library merely containing it in «パントン ソリッド». Without the
            # exact-altLabel tier both scored 0.60 and the winner depended on
            # index order.
            if notation and notation == q:
                score = 1.0
            elif any(lbl == q for lbl in labels):
                score = 0.95
            elif q in _inflected(entry)[0]:
                # SD-0072: the buyer's grammar is not a signal. «Broschüre» and
                # «Broschüren» are one request. Below exact by design, so a term
                # that owns the word outright is never displaced by one that
                # merely inflects to it.
                score = 0.93
            elif any(a == q for a in alt_values):
                score = 0.90
            elif q in _inflected(entry)[1]:
                score = 0.88
            elif any(lbl.startswith(q) for lbl in labels):
                score = 0.85
            elif any(a.startswith(q) for a in alt_values):
                score = 0.80
            else:
                per_token: list[float] = []
                for t in tokens:
                    # Plural-aware: also try the singular (strip one trailing 's')
                    # so "brochures"->"brochure", "stickers"->"sticker", "cards"->"card".
                    variants = [t]
                    if len(t) >= 4 and t.endswith("s") and not t.endswith("ss"):
                        variants.append(t[:-1])
                    if any(v in lbl for lbl in labels for v in variants):
                        per_token.append(0.70)
                    elif any(v in a for a in alt_values for v in variants):
                        per_token.append(0.60)
                    elif notation and any(v in notation for v in variants):
                        per_token.append(0.50)
                    elif any(v in d for d in definitions for v in variants):
                        per_token.append(0.40)
                    else:
                        per_token = []
                        break  # AND semantics: one unmatched token kills the entry
                score = min(per_token) if per_token else 0.0

            # gsm-vakten, rutedelen: tallet lander i klassen som eier området.
            if (weight_n is not None and "/paper-weights/" in eid):
                rng = _gsm_range(entry)
                if rng and rng[0] <= weight_n <= rng[1]:
                    score = max(score, 0.92)

            if sems is not None:
                # Hybrid: the embedding cosine should ADD recall for meaning-based
                # matches ("round sticker" -> Circle) with little/no lexical overlap,
                # but must never DRAG DOWN a solid lexical hit. A label/altLabel/
                # notation match (score >= 0.50) is trustworthy on its own and keeps
                # its score; weaker definition-only hits (0.40) still need semantic
                # support to surface.
                sem = sems.get(entry.get("id"), 0.0)
                blended = _LEX_WEIGHT * score + _SEM_WEIGHT * sem
                floor = score if score >= 0.50 else 0.0
                final = max(floor, blended)
                if final >= _SEM_THRESHOLD:
                    results.append((final, entry))
            elif score > 0:
                results.append((score, entry))

        # Deterministic: equal scores break on the URI, never on index order.
        # SD-0073 makes one part of that ordering explicit rather than
        # accidental: when a phrase matches a product and a non-product equally
        # well, the product wins, because a product is the thing that can
        # actually be ordered. It happens to be what alphabetical URI order
        # already did — «ordering/» sorts before «printing/» — but relying on
        # the alphabet for a rule we depend on is how a rule silently changes.
        # This is a TIE-break only; it must never lift a product over a better
        # match, or it would hide the name collisions SD-0073 exists to expose.
        # A standard that promises lookups rather than interpretations cannot
        # answer the same query differently between two calls.
        def _rank(r: tuple[float, dict]) -> tuple:
            uri = r[1].get("id") or ""
            is_product = 0 if "/ordering/products/" in uri else 1
            return (-r[0], is_product, uri)

        results.sort(key=_rank)
        return [
            {
                "id": entry["id"],
                "notation": entry.get("notation") or None,
                "prefLabel": (entry.get("label") or {}).get(language)
                or (entry.get("label") or {}).get("en"),
                "level": entry.get("level"),
                "group": entry.get("group") or None,
                "score": round(score, 3),
                "kind": {"ptpge:Supplier": "supplier", "ptpge:Vendor": "vendor", "ptpge:Schema": "schema"}.get(entry.get("type") or "", "term"),
                **({"status": entry.get("status")} if entry.get("status") == "deprecated" else {}),
                **({"replacedBy": entry.get("replacedBy")} if entry.get("replacedBy") else {}),
            }
            for score, entry in results[:limit]
        ]

    def maybe_reload(self) -> bool:
        """Check the remote version and reload only if it has changed.

        Returns True if a reload happened, False otherwise.
        Never raises; logs and returns False on failure so the caller can
        keep serving stale data.
        """
        try:
            with self._client() as client:
                remote_version = self._fetch_json(client, "version.json")
        except Exception as exc:
            logger.warning("Version check failed (will retry): %s", exc)
            return False

        # Freshness is (version, generated), not version alone. dataVersion is
        # a date, so two deploys on the same day carry the same string and a
        # version-only check silently keeps serving the older dataset until
        # someone happens to restart the app. `generated` is a full timestamp
        # written by tools/build_api.py on every build, so it moves whenever
        # anything is rebuilt — including a same-day correction.
        def _key(v: dict | None) -> tuple:
            return ((v or {}).get("version"), (v or {}).get("generated"))

        with self._lock:
            current = _key(self._version)
        remote = _key(remote_version)

        if remote == current:
            return False

        logger.info("New dataset detected: %s -> %s", current, remote)
        try:
            self.load()
            return True
        except Exception as exc:
            logger.error("Reload failed (will retry next cycle): %s", exc)
            return False

    def start_background_refresh(self) -> threading.Thread:
        """Start a daemon thread that calls maybe_reload() on a schedule."""
        interval = self._config.refresh_seconds

        def _loop() -> None:
            while True:
                time.sleep(interval)
                self.maybe_reload()

        thread = threading.Thread(target=_loop, daemon=True, name="ptpge-refresh")
        thread.start()
        return thread
