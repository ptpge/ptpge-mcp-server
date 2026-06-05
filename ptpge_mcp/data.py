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
import threading
import time
from typing import Any

import httpx

from .config import Config

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
    ) -> list[dict[str, Any]]:
        """Tokenized, language-agnostic search over the search index (v0.3.2).

        The query is split into whitespace tokens and an entry matches when
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
            0.85 — a label (any language) starts with the whole query
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
        tokens = q.split()
        groups_filter = set(groups) if groups else None

        results: list[tuple[float, dict[str, Any]]] = []
        with self._lock:
            entries = (self._search_index or {}).get("terms", [])

        for entry in entries:
            if groups_filter and entry.get("group") not in groups_filter:
                continue
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
            if notation and notation == q:
                score = 1.0
            elif any(lbl == q for lbl in labels):
                score = 0.95
            elif any(lbl.startswith(q) for lbl in labels):
                score = 0.85
            else:
                per_token: list[float] = []
                for t in tokens:
                    if any(t in lbl for lbl in labels):
                        per_token.append(0.70)
                    elif any(t in a for a in alt_values):
                        per_token.append(0.60)
                    elif notation and t in notation:
                        per_token.append(0.50)
                    elif any(t in d for d in definitions):
                        per_token.append(0.40)
                    else:
                        per_token = []
                        break  # AND semantics: one unmatched token kills the entry
                score = min(per_token) if per_token else 0.0

            if score > 0:
                results.append((score, entry))

        results.sort(key=lambda r: -r[0])
        return [
            {
                "id": entry["id"],
                "notation": entry.get("notation") or None,
                "prefLabel": (entry.get("label") or {}).get(language)
                or (entry.get("label") or {}).get("en"),
                "level": entry.get("level"),
                "group": entry.get("group") or None,
                "score": round(score, 3),
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

        with self._lock:
            current = self._version.get("version") if self._version else None
            remote = remote_version.get("version")

        if remote == current:
            return False

        logger.info("New dataset version detected: %s -> %s", current, remote)
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
