"""What real requests could not resolve — the learning loop of SD-0071 §9.

Every lookup that comes through /mcp is judged, and the ones that went badly
are counted here: a phrase that found nothing, a phrase that barely found
something, a colour count the template could not settle. Whether the request
came from us testing, from the playground, or from somebody's agent makes no
difference — the vocabulary learns from use rather than from guesswork.

WHAT IS RECORDED, AND WHAT IS NOT
    Recorded: the phrase that failed, the score, the term it reached (if any),
    a count, and the day it was first and last seen.
    Never recorded: who asked. No user, no key, no IP, no session, no
    timestamp finer than a date. The open mirror promises callers anonymity
    per the partner onboarding, and an aggregate of *phrases* keeps that
    promise — nothing here can be traced back to a caller.

    Successful lookups are not recorded at all. There is nothing to learn from
    a query that worked, and not storing them keeps the file small and the
    exposure minimal.

    Anything that looks like it carries personal data — an address, a long
    free-text order, a digit run — is dropped rather than stored (see _safe).

Storage is a small JSON file, capped, written atomically. If the path is not
writable the recorder disables itself silently: telemetry must never be able
to break a lookup.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import tempfile
import threading

logger = logging.getLogger(__name__)

#: Below this a lookup counts as weak — the right answer may have been reached,
#: but by so little that the next competing term would displace it.
WEAK_BELOW = 0.55

MAX_PHRASES = 4000          # hard cap; least-seen entries are dropped first
MAX_PHRASE_LEN = 60         # longer than this is a prompt, not a term

_EMAILISH = re.compile(r"[^\s@]+@[^\s@]+")
_LONGDIGITS = re.compile(r"\d{5,}")

_lock = threading.RLock()
_state: dict = {"misses": {}, "weak": {}, "colour": {}}
_path: str | None = None
_dirty = False


def _safe(phrase: str) -> str | None:
    """Keep short trade phrases; drop anything that could carry personal data."""
    p = (phrase or "").strip()
    if not p or len(p) > MAX_PHRASE_LEN:
        return None
    if _EMAILISH.search(p) or _LONGDIGITS.search(p):
        return None
    return p.lower()


def configure(path: str | None) -> None:
    """Point the recorder at a file. None (or an unwritable path) disables it."""
    global _path
    if not path:
        _path = None
        return
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                for k in ("misses", "weak", "colour"):
                    if isinstance(loaded.get(k), dict):
                        _state[k] = loaded[k]
        _path = path
        logger.info("Learning recorder active: %s", path)
    except Exception as exc:                                   # pragma: no cover
        _path = None
        logger.warning("Learning recorder disabled (%s): %s", path, exc)


def _today() -> str:
    return datetime.date.today().isoformat()


def _bump(bucket: str, key: str, **fields) -> None:
    with _lock:
        entry = _state.setdefault(bucket, {}).get(key)
        if entry is None:
            entry = {"n": 0, "first": _today(), **fields}
            _state[bucket][key] = entry
        entry["n"] += 1
        entry["last"] = _today()
        entry.update(fields)
        global _dirty
        _dirty = True


def record_search(query: str, hits: list[dict]) -> None:
    """Judge one search. Only failures are kept."""
    if _path is None:
        return
    phrase = _safe(query)
    if phrase is None:
        return
    try:
        if not hits:
            _bump("misses", phrase, got=None, score=None)
        else:
            top = hits[0]
            score = top.get("score")
            if score is not None and score < WEAK_BELOW:
                _bump("weak", phrase,
                      got=(top.get("id") or "").replace("https://ptpge.org/v1/", ""),
                      score=score)
    except Exception:                                          # pragma: no cover
        pass                    # never let bookkeeping break a lookup


def record_colour_question(product: str, surface: str, count: int,
                           candidates: int) -> None:
    """A colour count the template could not settle (SD-0071 §9).

    Purely structural: which template, which surface, which number, how many
    readings stayed open. No buyer text is involved at all.
    """
    if _path is None:
        return
    try:
        key = f"{product.replace('https://ptpge.org/v1/', '')}|{surface}|{count}"
        _bump("colour", key, product=product.replace("https://ptpge.org/v1/", ""),
              surface=surface, count=count, candidates=candidates)
    except Exception:                                          # pragma: no cover
        pass


def flush() -> None:
    """Write the file if anything changed. Cheap; safe to call often."""
    global _dirty
    if _path is None or not _dirty:
        return
    try:
        with _lock:
            for bucket in ("misses", "weak", "colour"):
                entries = _state[bucket]
                if len(entries) > MAX_PHRASES:
                    keep = sorted(entries.items(), key=lambda kv: -kv[1].get("n", 0))
                    _state[bucket] = dict(keep[:MAX_PHRASES])
            payload = json.dumps(_state, ensure_ascii=False)
            _dirty = False
        d = os.path.dirname(_path) or "."
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".learning-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, _path)
    except Exception as exc:                                   # pragma: no cover
        logger.warning("Could not write learning file: %s", exc)


def snapshot() -> dict:
    """Everything recorded, newest-heaviest first — for the /learning page."""
    with _lock:
        def rows(bucket: str) -> list[dict]:
            return sorted(
                ({"key": k, **v} for k, v in _state[bucket].items()),
                key=lambda r: (-r.get("n", 0), r["key"]))
        return {"enabled": _path is not None,
                "misses": rows("misses"), "weak": rows("weak"),
                "colour": rows("colour"),
                "totals": {k: sum(e.get("n", 0) for e in _state[k].values())
                           for k in ("misses", "weak", "colour")}}


def reset() -> None:
    with _lock:
        for k in ("misses", "weak", "colour"):
            _state[k] = {}
        global _dirty
        _dirty = True
    flush()
