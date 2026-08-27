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

BUCKETS = ("misses", "weak", "colour", "ignored")

_lock = threading.RLock()
_state: dict = {b: {} for b in BUCKETS}
_path: str | None = None
_dirty = False

# Two apps (mcp. and open.) may point at ONE file. Each runs in its own process
# with its own copy in memory, so writing that copy out would silently discard
# whatever the other process recorded meanwhile. Instead each process keeps
# only what IT changed — counts as increments, edits as a replayable list — and
# every write re-reads the file and applies those on top. Nothing is lost, and
# no lock is held across a request.
_delta: dict = {b: {} for b in BUCKETS}     # bucket -> key -> times seen here
_meta: dict = {b: {} for b in BUCKETS}      # bucket -> key -> fields to merge
_ops: list = []                             # ("ignore"|"unignore"|"gloss", ...)


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
    # cPanel stores an env var verbatim, so "~/..." arrives with the tilde
    # intact. Expanding it here lets both apps be given the identical value.
    path = os.path.expanduser(path)
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
        _delta[bucket][key] = _delta[bucket].get(key, 0) + 1
        _meta[bucket].setdefault(key, {}).update(fields)
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
        _ops.append(("ignore", p, reason))
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
        _ops.append(("unignore", p))
        global _dirty
        _dirty = True
    flush()
    return gone


def _read_disk() -> dict:
    """Whatever is on disk right now — possibly written by the other process."""
    try:
        with open(_path, encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, dict):
            return {b: (loaded.get(b) if isinstance(loaded.get(b), dict) else {})
                    for b in BUCKETS}
    except FileNotFoundError:
        pass
    except Exception as exc:                                   # pragma: no cover
        logger.warning("Could not read learning file: %s", exc)
    return {b: {} for b in BUCKETS}


def _apply(doc: dict) -> dict:
    """Replay this process's own changes onto a freshly-read document."""
    for bucket, counts in _delta.items():
        for key, inc in counts.items():
            entry = doc[bucket].get(key)
            if entry is None:
                entry = {"n": 0, "first": _today()}
                doc[bucket][key] = entry
            entry["n"] = entry.get("n", 0) + inc
            entry["last"] = _today()
            for k, v in (_meta[bucket].get(key) or {}).items():
                # Never overwrite a known value with None: a later caller who
                # declared no language must not erase one who did.
                if v is not None or k not in entry:
                    entry[k] = v

    for op in _ops:
        if op[0] == "ignore":
            _, phrase, reason = op
            for bucket in ("misses", "weak"):
                doc[bucket].pop(phrase, None)
            entry = doc["ignored"].setdefault(phrase, {"n": 0, "first": _today()})
            entry["reason"] = reason
            entry["last"] = _today()
        elif op[0] == "unignore":
            doc["ignored"].pop(op[1], None)
        elif op[0] == "gloss":
            _, phrase, text, language = op
            for bucket in BUCKETS:
                entry = doc[bucket].get(phrase)
                if entry is not None:
                    entry["gloss"] = text
                    if language:
                        entry["lang"] = language

    for bucket in BUCKETS:
        entries = doc[bucket]
        if len(entries) > MAX_PHRASES:
            keep = sorted(entries.items(), key=lambda kv: -kv[1].get("n", 0))
            doc[bucket] = dict(keep[:MAX_PHRASES])
    return doc


def _sync(force: bool = False) -> None:
    """Merge this process's changes into the file and adopt the result.

    Called on every write and before every read, so a page opened on one host
    shows what the other host recorded. Cheap: one small JSON read and, only
    when something changed, one atomic replace.
    """
    global _dirty, _state
    if _path is None:
        return
    with _lock:
        if not _dirty and not force:
            return
        doc = _apply(_read_disk())
        payload = json.dumps(doc, ensure_ascii=False)
        _state = doc
        for bucket in BUCKETS:
            _delta[bucket] = {}
            _meta[bucket] = {}
        _ops.clear()
        had_changes, _dirty = _dirty, False
    if not had_changes:
        return
    try:
        d = os.path.dirname(_path) or "."
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".learning-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, _path)
    except Exception as exc:                                   # pragma: no cover
        logger.warning("Could not write learning file: %s", exc)


def flush() -> None:
    """Write pending changes. Cheap; safe to call often."""
    _sync()


def snapshot() -> dict:
    """Everything recorded, heaviest first — for the /learning page.

    Re-reads the file first, so when two apps share one record the page shows
    the whole of it and not just this process's share.
    """
    _sync(force=True)
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
    global _dirty
    with _lock:
        for k in BUCKETS:
            _state[k] = {}
            _delta[k] = {}
            _meta[k] = {}
        _ops.clear()
        _dirty = False
    if _path:
        try:
            os.remove(_path)
        except FileNotFoundError:
            pass
        except Exception as exc:                               # pragma: no cover
            logger.warning("Could not clear learning file: %s", exc)


def settled_language(search_index: dict):
    """A lookup that answers «which language is this word?» from the vocabulary.

    Once a phrase exists as a label or altLabel, the standard has already
    decided the question and no detector is needed. That is what lets a row on
    /learning heal itself: the day "Fahnen" is filed as a German altLabel on
    banners, the row that used to shrug starts saying `de`.

    Returns None when the word is unknown — a miss, by definition — and also
    when it is known in more than one language. "Banner" is English and German
    both, and picking one would be inventing a fact the vocabulary declines to
    state. Builds a plain dict, so the page costs one hash lookup per row.
    """
    index: dict[str, set[str]] = {}
    for entry in (search_index or {}).get("terms", []):
        for field in ("label", "altLabels"):
            for lang, value in (entry.get(field) or {}).items():
                for text in (value if isinstance(value, list) else [value]):
                    if isinstance(text, str) and text.strip():
                        index.setdefault(text.strip().lower(), set()).add(lang)

    def lookup(phrase: str) -> str | None:
        langs = index.get((phrase or "").strip().lower())
        return next(iter(langs)) if langs and len(langs) == 1 else None

    return lookup


def gloss(phrase: str, text: str, language: str | None = None) -> bool:
    """Store what a phrase means, so a row you cannot read stops being opaque.

    Written once, kept forever: the reading of チラシ does not change, and
    nobody should pay for the same lookup twice. If the gloss also settles the
    language, that is recorded as declared — a reading of the characters by a
    model that knows the trade beats a regex looking for umlauts.
    """
    p = _safe(phrase)
    if p is None or not (text or "").strip():
        return False
    with _lock:
        for bucket in ("misses", "weak", "ignored"):
            entry = _state.get(bucket, {}).get(p)
            if entry is not None:
                entry["gloss"] = text.strip()[:120]
                if language:
                    entry["lang"] = language
        _ops.append(("gloss", p, text.strip()[:120], language))
        global _dirty
        _dirty = True
    flush()
    return True
