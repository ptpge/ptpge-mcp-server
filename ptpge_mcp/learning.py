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

# Script and orthography hints. A single trade word cannot be language-typed
# reliably — "banner" is English and German both — so these are marked as
# guesses in the UI. The CJK ones are certain; the Latin ones lean on
# characters that only some languages use.
_SCRIPTS = [
    ("ja", re.compile(r"[\u3040-\u30ff]")),          # kana — certain
    ("zh", re.compile(r"[\u4e00-\u9fff]")),          # Han (also ja kanji; kana wins above)
    ("ko", re.compile(r"[\uac00-\ud7af]")),
    ("el", re.compile(r"[\u0370-\u03ff]")),
    ("ru", re.compile(r"[\u0400-\u04ff]")),
]
_ORTHO = [
    ("nb/da", re.compile(r"[øæåØÆÅ]")),
    ("de", re.compile(r"[äöüßÄÖÜ]")),
    ("es", re.compile(r"[ñáéíóúü¿¡]")),
    ("fr", re.compile(r"[çèêëàâîïôùû]")),
]

_EMAILISH = re.compile(r"[^\s@]+@[^\s@]+")
_LONGDIGITS = re.compile(r"\d{5,}")

_lock = threading.RLock()
_state: dict = {"misses": {}, "weak": {}, "colour": {}, "ignored": {}}
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


def language_hint(phrase: str) -> str:
    """A short tag for which language the phrase is probably in.

    Certain for non-Latin scripts, a guess for Latin ones — «nb/da?» rather
    than a claim. Shown so the table says WHICH language's synonyms are thin,
    which is the whole reason to look at it.
    """
    for tag, rx in _SCRIPTS:
        if rx.search(phrase):
            return tag
    for tag, rx in _ORTHO:
        if rx.search(phrase):
            return tag + "?"
    return ""


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
                for k in ("misses", "weak", "colour", "ignored"):
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


def record_search(query: str, hits: list[dict], language: str | None = None) -> None:
    """Judge one search. Only failures are kept."""
    if _path is None:
        return
    phrase = _safe(query)
    if phrase is None:
        return
    try:
        with _lock:
            known = phrase in _state.get("ignored", {})
        if known:
            # Out of scope by decision, not by oversight — keep counting so the
            # size of the demand stays visible if the scope ever changes.
            _bump("ignored", phrase)
            return
        # `lang` is what the caller declared (often nothing); `hint` is what the
        # characters suggest. Kept apart so a guess is never read as a fact.
        meta = {"hint": language_hint(query), "lang": language or None}
        if not hits:
            _bump("misses", phrase, got=None, score=None, **meta)
        else:
            top = hits[0]
            score = top.get("score")
            if score is not None and score < WEAK_BELOW:
                _bump("weak", phrase,
                      got=(top.get("id") or "").replace("https://ptpge.org/v1/", ""),
                      score=score, **meta)
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


def ignore(phrase: str, reason: str = "out of scope") -> bool:
    """Take a phrase off the list for good.

    Used for words that are missing on purpose — merchandise, apparel, 3D and
    POS are outside the 54 product templates by decision, so their absence is
    not a gap to fix. The phrase stops appearing, but its hits keep being
    counted under `ignored`, so if the scope ever widens the demand is already
    measured.
    """
    p = _safe(phrase)
    if p is None:
        return False
    with _lock:
        for bucket in ("misses", "weak"):
            _state[bucket].pop(p, None)
        entry = _state.setdefault("ignored", {}).setdefault(
            p, {"n": 0, "first": _today(), "reason": reason})
        entry["reason"] = reason
        entry["last"] = _today()
        global _dirty
        _dirty = True
    flush()
    return True


def unignore(phrase: str) -> bool:
    p = _safe(phrase)
    if p is None:
        return False
    with _lock:
        gone = _state.get("ignored", {}).pop(p, None) is not None
        global _dirty
        _dirty = True
    flush()
    return gone


def flush() -> None:
    """Write the file if anything changed. Cheap; safe to call often."""
    global _dirty
    if _path is None or not _dirty:
        return
    try:
        with _lock:
            for bucket in ("misses", "weak", "colour", "ignored"):
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
                "colour": rows("colour"), "ignored": rows("ignored"),
                "totals": {k: sum(e.get("n", 0) for e in _state[k].values())
                           for k in ("misses", "weak", "colour", "ignored")}}


def reset() -> None:
    with _lock:
        for k in ("misses", "weak", "colour", "ignored"):
            _state[k] = {}
        global _dirty
        _dirty = True
    flush()
