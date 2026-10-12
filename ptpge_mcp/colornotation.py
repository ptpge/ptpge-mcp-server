"""Color pair notation (4/4, 4/1, 4+4) → per-surface color bindings.

Implements SD-0071. Two rules carry the whole design:

1. **The number is a constraint, not a value.** "4" does not name a color; it
   says the surface carries four separations. Hand-written candidate lists
   collapse immediately (7 can be CMYKOGV, CMYKOG + white, CMYK + 3 spots,
   CMYK + 2 spots + white, black + 6 spots, 7 spots …), so we never write one.
   Instead each color term carries `properties.colorChannelCount`, and we search
   the combinations the *product template* actually supports that sum to N.

2. **Never guess.** One combination → deterministic binding. Several → a
   `needs_disambiguation` result carrying the candidates and a ready-made
   question for the agent to relay. None → the count is invalid for that
   template, which is a third useful answer.

Two declared conventions, stated here so they are visible as choices rather
than derivations: `4` is CMYK (mathematically it could be four spot inks; in
the trade it never is) and `0` is None (SD-0068 spoken blankness).

The module is deliberately free of MCP/HTTP concerns so the API and the Engine
can import it unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import combinations
from typing import Iterable, Sequence

BASE = "https://ptpge.org/v1/"
CMYK = BASE + "printing/features/colors/cmyk"
BLACK = BASE + "printing/features/colors/black"
NONE = BASE + "printing/features/colors/none"
SPOT = BASE + "printing/features/colors/spot-color"

#: Upper bound on how many spot inks a single surface may be assumed to carry
#: when resolving a count. Keeps the combination search finite; a buyer who
#: wants more can bind the layers explicitly instead of using the shorthand.
MAX_SPOT = 4

SURFACES = ("front", "back")

#: Pair notation: two counts separated by "/" or "+", spaces optional.
_PAIR = re.compile(r"^\s*(\d{1,2})\s*([/+])\s*(\d{1,2})\s*$")

#: Worded pair notation. Buyers say "double-sided" and "single-sided" far more
#: often than they write 4/4 — Helloprint's own flyer configurator offers
#: exactly those two words (coverage run 2026-08-30). They are NOT vocabulary
#: terms and never will be: per the None-decision (SD-0068 spoken blankness),
#: "single-sided" is x/0 — back bound to None deterministically, front count
#: unknown — and "double-sided" is x/y with both counts unknown. Unknown counts
#: are carried as None and produce needs_disambiguation, never a guess.
_WORDED_SINGLE = re.compile(
    r"^\s*(?:(?:single|one|1)[-\s]?sided(?:\s+print(?:ing)?)?|simplex)\s*$", re.I)
_WORDED_DOUBLE = re.compile(
    r"^\s*(?:(?:double|two|2)[-\s]?sided(?:\s+print(?:ing)?)?|duplex|both\s+sides(?:\s+printed)?)\s*$",
    re.I)


class NotationError(ValueError):
    """The string is not a color pair notation at all."""


@dataclass(frozen=True)
class Pair:
    """A parsed pair notation.

    Counts are `None` when the notation names the *shape* of the pair without
    the numbers — "double-sided" says both surfaces carry ink but not how much.
    """

    front: int | None
    back: int | None
    separator: str
    raw: str

    @property
    def is_plus(self) -> bool:
        return self.separator == "+"


@dataclass
class SurfaceResult:
    """Resolution outcome for one surface."""

    surface: str
    count: int | None
    #: Every combination the template supports that sums to `count`. Each
    #: candidate is a tuple of color URIs, in print order.
    candidates: list[tuple[str, ...]] = field(default_factory=list)
    #: Set when exactly one candidate remains.
    binding: tuple[str, ...] | None = None
    #: Set when no combination is possible on this template.
    invalid: bool = False
    question: str | None = None

    @property
    def resolved(self) -> bool:
        return self.binding is not None


def parse_pair(text: str) -> Pair:
    """Parse "4/4", "4 / 4", "4+4", "4 + 4" into a :class:`Pair`.

    Raises :class:`NotationError` if the text is not pair notation. Order is
    front then back (SD-0071); no market is known to write it the other way.
    """
    m = _PAIR.match(text or "")
    if m:
        return Pair(front=int(m.group(1)), back=int(m.group(3)),
                    separator=m.group(2), raw=text.strip())
    if _WORDED_SINGLE.match(text or ""):
        # x/0: the reverse is unprinted — a positive, deterministic statement
        # (SD-0068). The front count stays open.
        return Pair(front=None, back=0, separator="worded", raw=text.strip())
    if _WORDED_DOUBLE.match(text or ""):
        return Pair(front=None, back=None, separator="worded", raw=text.strip())
    raise NotationError(f"not a color pair notation: {text!r}")


def plus_is_ambiguous(pair: Pair) -> bool:
    """True when "+" cannot be read as a surface pair.

    In parts of the trade "4+1" means CMYK *plus one spot on the same surface*
    (five plates, one surface), not front/back. When the two numbers are equal
    both readings land on the same configuration, so "4+4" is safe; when they
    differ the notation genuinely forks and we must ask.
    """
    return pair.is_plus and pair.front != pair.back


def channel_count(term: dict | None) -> int | None:
    """Read `properties.colorChannelCount` off a color term."""
    if not term:
        return None
    value = (term.get("properties") or {}).get("colorChannelCount")
    return value if isinstance(value, int) else None


def _combinations_for(count: int, supported: Sequence[str],
                      channels: dict[str, int]) -> list[tuple[str, ...]]:
    """All supported layer combinations whose channel counts sum to `count`.

    Spot colors are multi-instance (a surface may carry several named inks), so
    they are expanded to 1..MAX_SPOT copies. Every other layer appears at most
    once — a surface cannot carry CMYK twice.
    """
    if count == 0:
        return [(NONE,)] if NONE in supported else []

    # CMYK already contains K, so black is never an addition to it. Excluding
    # the pair here keeps "5" from resolving to the nonsense CMYK + black.
    def valid(combo: tuple[str, ...]) -> bool:
        return not (CMYK in combo and BLACK in combo)

    pool: list[str] = []
    for uri in supported:
        if uri == NONE:
            continue
        n = channels.get(uri)
        if not n:
            continue
        pool.extend([uri] * (MAX_SPOT if uri == SPOT else 1))

    found: set[tuple[str, ...]] = set()
    for size in range(1, len(pool) + 1):
        for combo in combinations(pool, size):
            if sum(channels[u] for u in combo) != count:
                continue
            if not valid(combo):
                continue
            # Canonical order: process colors first, then spot/white extras —
            # this is print order, and it keeps the tuple stable for equality.
            found.add(tuple(sorted(combo, key=lambda u: (-channels[u], u))))
    return sorted(found)


def _phrase(combo: tuple[str, ...]) -> str:
    """Human phrasing for one combination, with repeats collapsed.

    "CMYK + 3 named spot colors", not "CMYK + a named spot color + a named
    spot color + a named spot color".
    """
    counts: dict[str, int] = {}
    for uri in combo:
        counts[uri] = counts.get(uri, 0) + 1
    parts = []
    for uri, n in counts.items():
        leaf = uri.rsplit("/", 1)[-1]
        if uri == SPOT:
            parts.append("a named spot color" if n == 1 else f"{n} named spot colors")
        else:
            name = leaf.upper() if leaf in {"cmyk", "cmykog", "cmykogv"} else leaf.replace("-", " ")
            parts.append(name if n == 1 else f"{n}× {name}")
    return " + ".join(parts)


def _question_for(surface: str, candidates: Iterable[tuple[str, ...]]) -> str:
    """A ready-made question the agent can put to the buyer.

    Spot is the asymmetric candidate: "black" is a complete binding on its own,
    while a spot color is not until it is named. So the question asks for the
    name in the same breath, the way a human would.
    """
    combos = list(candidates)
    wants_spot_name = any(SPOT in c for c in combos)
    joined = ", or ".join(_phrase(c) for c in combos)
    if len(combos) == 1 and wants_spot_name:
        # Only one combination, but it needs the ink named before it is a
        # binding — so the question is "which", not "which of these".
        return f"For the {surface}: {joined} — which spot color?"
    tail = " — and which spot color?" if wants_spot_name else "?"
    return f"For the {surface}: {joined}{tail}"


def resolve_surface(count: int, supported: Sequence[str], channels: dict[str, int],
                    surface: str = "front") -> SurfaceResult:
    """Resolve one surface's count against what the template supports."""
    result = SurfaceResult(surface=surface, count=count)

    # Declared conventions (SD-0071 §3). 4 is CMYK by trade convention, not by
    # arithmetic; 0 is spoken blankness.
    if count == 4 and CMYK in supported:
        result.binding = (CMYK,)
        result.candidates = [(CMYK,)]
        return result
    if count == 0:
        if NONE in supported:
            result.binding = (NONE,)
            result.candidates = [(NONE,)]
        else:
            result.invalid = True
        return result

    result.candidates = _combinations_for(count, supported, channels)
    if not result.candidates:
        result.invalid = True
    elif len(result.candidates) == 1 and SPOT not in result.candidates[0]:
        result.binding = result.candidates[0]
    else:
        # A combination containing spot is never a complete binding: a spot ink
        # is not identified until it is named. So even a single such candidate
        # keeps the surface open — otherwise "9/9" on a card that happens to
        # support white and spots would silently bind, and fingerprint, a
        # configuration nobody chose.
        result.question = _question_for(surface, result.candidates)
    return result


@dataclass
class PairResolution:
    """The outcome of resolving a full pair notation against a template."""

    pair: Pair
    surfaces: dict[str, SurfaceResult]
    ambiguous_separator: bool = False
    separator_question: str | None = None

    @property
    def resolved(self) -> bool:
        return (not self.ambiguous_separator
                and all(s.resolved for s in self.surfaces.values()))

    @property
    def invalid(self) -> bool:
        return any(s.invalid for s in self.surfaces.values())

    def to_dict(self) -> dict:
        """Wire form. `needs_disambiguation` is the field an agent acts on."""
        out: dict = {
            "notation": self.pair.raw,
            "surfaces": {
                name: {
                    "count": s.count,
                    "binding": list(s.binding) if s.binding else None,
                    "candidates": [list(c) for c in s.candidates],
                    "invalid": s.invalid,
                }
                for name, s in self.surfaces.items()
            },
            "resolved": self.resolved,
        }
        needs: list[dict] = []
        if self.ambiguous_separator:
            needs.append({
                "reason": "separator",
                "question": self.separator_question,
                "note": ("'+' between different numbers is read as a surface pair in "
                         "some markets and as extra inks on one surface in others."),
            })
        for name, s in self.surfaces.items():
            if s.invalid:
                continue
            if not s.resolved:
                needs.append({
                    "reason": "surface_count",
                    "surface": name,
                    "count": s.count,
                    "candidates": [list(c) for c in s.candidates],
                    "question": s.question,
                })
        if needs:
            out["needs_disambiguation"] = needs
        invalid = {n: s.count for n, s in self.surfaces.items() if s.invalid}
        if invalid:
            out["invalid_for_template"] = invalid
        return out


def resolve(text: str, supported: Sequence[str], channels: dict[str, int],
            surfaces: Sequence[str] = SURFACES) -> PairResolution:
    """Resolve a pair notation against one template's supported color layers.

    `supported` is the template's `perSurfaceSupportsColorMode` list and
    `channels` maps color URI → `colorChannelCount`. Surface slugs are free
    text in the vocabulary (front/back on a flat sheet, outside/inside on a
    folded one), so the caller may name them; the pair is always read in the
    given order, first number first.
    """
    pair = parse_pair(text)
    first, second = (list(surfaces) + list(SURFACES))[:2]

    def one(count: int | None, surface: str) -> SurfaceResult:
        if count is not None:
            return resolve_surface(count, supported, channels, surface)
        # Worded shorthand left this count open. Never guess (SD-0071 §2):
        # ask for the pair itself, with the notation as the example so the
        # agent can relay a question the trade already answers daily.
        r = SurfaceResult(surface=surface, count=None)
        r.question = (
            f"“{pair.raw}” does not say which colors the {surface} carries — "
            "answer with a pair such as 4/4 (full color both sides), "
            "4/1 (color front, black reverse) or 4/0 (front only).")
        return r

    surfaces = {
        first: one(pair.front, first),
        second: one(pair.back, second),
    }
    res = PairResolution(pair=pair, surfaces=surfaces)
    if plus_is_ambiguous(pair):
        res.ambiguous_separator = True
        res.separator_question = (
            f"Does “{pair.raw}” mean {pair.front} colors on the front and "
            f"{pair.back} on the back, or {pair.front + pair.back} inks on a single surface?"
        )
    return res


def channels_from_terms(terms: Iterable[dict]) -> dict[str, int]:
    """Build the URI → channel-count map from loaded color terms."""
    out: dict[str, int] = {}
    for term in terms:
        n = channel_count(term)
        uri = term.get("id") or term.get("@id")
        if n is not None and uri:
            out[uri] = n
    return out


def resolve_many(text: str, supported: Sequence[str], channels: dict[str, int],
                 faces: Sequence[str]) -> PairResolution:
    """Pair notation on a setup with more than two faces (multi-page, SD-0102).

    An equal pair — 4/4, 1/1 — is the trade's way of saying «every page, both
    sides»: every face carries that count. An unequal pair (4/1) cannot be
    placed on five faces without a guess, so every face is left open with one
    question that names the parts: say it per part («cover 4/4, inside 1/1»).
    """
    pair = parse_pair(text)
    if pair.front is not None and pair.front == pair.back:
        surfaces = {f: resolve_surface(pair.front, supported, channels, f) for f in faces}
        return PairResolution(pair=pair, surfaces=surfaces)
    surfaces = {}
    for f in faces:
        r = SurfaceResult(surface=f, count=None)
        r.question = (f"“{pair.raw}” on a multi-page product does not say which pages carry which colours — "
                      "state it per part, e.g. “cover 4/4, inside 1/1”.")
        surfaces[f] = r
    return PairResolution(pair=pair, surfaces=surfaces)

