"""Number-tolerant matching: the buyer's grammar is not a signal (SD-0072).

A buyer types «visittkort» or «visittkortet», «Broschüre» or «Broschüren»,
«sticker» or «stickers». Those are the same request. The vocabulary must not
require anyone to guess which form we happened to write in the label — and an
AI agent relaying a buyer's sentence will not normalise it either.

WHY VARIANTS OF THE LABEL, NOT A STEMMER ON THE QUERY

    Stemming an unknown query is how "Poster" becomes "post" and "Banner"
    becomes "bann". We do not know what the buyer typed, so we cannot safely
    take it apart. But we DO know our own labels: they are curated, and there
    are only a few thousand of them. So the direction is reversed — each label
    grows a small set of plausible inflected forms, and a query that hits one
    of those matches at a tier just BELOW exact.

    That ordering is the whole safety argument. Nothing that resolves correctly
    today can be displaced: an exact label still beats every inflected form. A
    generated form that no one ever types simply sits unused; the cost of a
    wrong guess is an unused string, not a wrong answer.

    German Booklets («Broschüren») and Brochures («Broschüre») differ only by
    number, so folding them makes them collide — which is a defect in the
    naming, not something matching should paper over. This module makes the
    collision visible at 0.93 instead of hiding it behind whichever form the
    buyer happened to choose.

Chinese and Japanese nouns are not inflected for number, so they are left
alone: generating suffixed forms there would be nonsense.
"""

from __future__ import annotations

#: Languages whose labels get inflected forms. CJK is deliberately absent.
INFLECTED = ("en", "de", "nb", "nn", "sv", "da", "nl", "es", "it", "fr", "pt")

_MIN = 4        # below this, a suffix rule is more likely noise than grammar

#: Cutting letters OFF a word is the dangerous direction: «Poster» would yield
#: «post» and «Banner» would yield «bann» — short stubs that are real words
#: meaning something else, and a buyer typing one would be answered confidently
#: and wrongly. Adding letters cannot do that: the result is either the real
#: other form or a string nobody types. So the two directions get different
#: floors, and truncation must leave a word long enough not to be an accident.
_MIN_TRUNCATED = 6


def _add(out: set, word: str) -> None:
    if len(word) >= _MIN:
        out.add(word)


def variants(label: str) -> set[str]:
    """Plausible other number-forms of one label, lowercased.

    Deliberately generous in shape and conservative in effect: every form here
    can only ever match at a tier below exact, so an extra candidate costs
    nothing while a missing one costs a failed lookup. Rules are shared across
    the Germanic and Romance labels rather than split by language, because a
    label carries no reliable marker of which language it is written in and a
    wrong-language suffix simply produces a string nobody types.
    """
    w = (label or "").strip().lower()
    if len(w) < _MIN:
        return set()
    out: set[str] = set()

    # --- towards the plural -------------------------------------------------
    if not w.endswith("s"):
        _add(out, w + "s")                       # cards, stickers, flyers
    if w.endswith(("s", "x", "z", "ch", "sh")):
        _add(out, w + "es")                      # boxes, matches
    if w.endswith("y") and w[-2:-1] not in "aeiou":
        _add(out, w[:-1] + "ies")                # category -> categories
    if w.endswith("e"):
        _add(out, w + "n")                       # Karte -> Karten, Broschüre -> Broschüren
    if not w.endswith(("e", "n", "s")):
        _add(out, w + "e")                       # Schild -> Schilde
        _add(out, w + "en")                      # Etikett -> Etiketten
        _add(out, w + "er")                      # Bild -> Bilder, kort -> korter
    if w.endswith("er"):
        _add(out, w + "e")                       # hefter -> heftere (nb/da)
    if not w.endswith("r"):
        _add(out, w + "r")                       # brosjyre -> brosjyrer, kalender -> …
    if not w.endswith(("ar", "er", "or")):
        _add(out, w + "ar")                      # sv: pärm -> pärmar

    # --- towards the singular ----------------------------------------------
    if w.endswith("ies") and len(w) > 5:
        _add(out, w[:-3] + "y")
    if w.endswith("es") and not w.endswith(("ses", "zes")):
        _add(out, w[:-2])                        # boxes -> box
    if w.endswith("s") and not w.endswith("ss"):
        _add(out, w[:-1])                        # stickers -> sticker
    for suffix in ("en", "er", "ar", "or", "n", "e"):
        if w.endswith(suffix) and len(w) - len(suffix) >= _MIN_TRUNCATED:
            _add(out, w[: -len(suffix)])         # Broschüren -> Broschüre
    # Scandinavian definite plurals: kortene, blokkene, flaggene
    for suffix in ("ene", "erne", "arna", "orna", "na", "et", "en"):
        if w.endswith(suffix) and len(w) - len(suffix) >= _MIN_TRUNCATED:
            _add(out, w[: -len(suffix)])

    out.discard(w)
    return out


def index_for(entry: dict) -> tuple[frozenset, frozenset]:
    """(label forms, altLabel forms) for one term — computed once at load.

    Returned frozen so the index can be shared between threads without
    copying, and so nothing downstream can mutate a cached term's forms.
    """
    labels: set[str] = set()
    alts: set[str] = set()
    for lang, value in (entry.get("label") or {}).items():
        if lang.split("-")[0] in INFLECTED and value:
            labels |= variants(str(value))
    for lang, values in (entry.get("altLabels") or {}).items():
        if lang.split("-")[0] in INFLECTED:
            for value in (values or []):
                if value:
                    alts |= variants(str(value))
    # A form that is already an exact label must not also count as inflected.
    exact = {str(v).lower() for v in (entry.get("label") or {}).values() if v}
    exact |= {str(a).lower()
              for alts_ in (entry.get("altLabels") or {}).values()
              for a in (alts_ or []) if a}
    return frozenset(labels - exact), frozenset(alts - exact - labels)
