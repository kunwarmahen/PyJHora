"""Check what the model *said* against what the chart *computes* (§68.1).

Four of the last five bugs in this file's history were one bug wearing different
clothes: the model asserted something about the chart that the chart itself
contradicts, the owner caught it in a finished reading, and the fix was a better
prompt (§63 read a drawing coordinate as a house, §64 reasoned over Sahams that
had been empty for months, §65 had two keys meaning different things, §67 said
"the 9th house is ruled by Jupiter" when the 9th here is Capricorn).

A prompt correction fixes the chart in front of you and no other. This module is
the mechanical version: extract the *checkable* assertions from the finished
text and test each one against the already-computed context. The vocabulary is
tiny and closed — 9 grahas plus the Lagna, 12 signs, 12 houses, 27 nakshatras,
a handful of conditions — so a regex pass over anchors is enough; no second LLM
call is involved in deciding whether the first one was wrong.

Design rules, in order of importance:

  • **A false alarm is worse than a miss.** A contradiction costs a regeneration
    and puts a warning under someone's reading, so every rule here refuses to
    guess. Sentences that change the frame of reference — a varga, a transit, an
    annual chart, "from the Moon", a hypothetical, a generic textbook statement —
    are skipped outright rather than checked against D1 facts they were never
    about. Coverage is deliberately traded for precision, and the skips are
    pinned in `tests/test_claim_check.py`.

  • **Facts come from the same context the model was given**, so a contradiction
    is genuinely internal: the model was told, in the prompt, the thing it then
    denied. Nothing here recomputes a chart, and nothing here needs a database.

  • **Silence when unknown.** `conditions` is a toggleable section; when it is
    absent no combust/retrograde claim is checked at all, rather than being
    checked against an empty set and "contradicted" for free.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from astrology import (EXALTATION_SIGN, NAKSHATRA_NAMES, OWN_SIGNS,
                       PLANET_NAMES, RASI_LORDS, ZODIAC_NAMES)

# ── Vocabulary ──────────────────────────────────────────────────────────────

PLANETS = [PLANET_NAMES[i] for i in range(9)]
LAGNA = "Lagna"

# Sanskrit synonyms the models reach for. Kept small and unambiguous: a word that
# also means something else in English prose is not worth the false positives.
_PLANET_ALIASES = {
    "surya": "Sun", "ravi": "Sun",
    "chandra": "Moon", "soma": "Moon",
    "mangal": "Mars", "mangala": "Mars", "kuja": "Mars", "angaraka": "Mars",
    "budha": "Mercury",
    "guru": "Jupiter", "brihaspati": "Jupiter", "brhaspati": "Jupiter",
    "shukra": "Venus", "sukra": "Venus",
    "shani": "Saturn", "sani": "Saturn", "shanaishchara": "Saturn",
    "ascendant": LAGNA, "lagna": LAGNA, "asc": LAGNA, "rising": LAGNA,
}
_SIGN_ALIASES = {
    "mesha": "Aries", "vrishabha": "Taurus", "vrishabh": "Taurus",
    "vrisabha": "Taurus", "mithuna": "Gemini", "karka": "Cancer",
    "karkata": "Cancer", "kataka": "Cancer", "simha": "Leo", "kanya": "Virgo",
    "tula": "Libra", "thula": "Libra", "vrischika": "Scorpio",
    "vrishchika": "Scorpio", "dhanu": "Sagittarius", "dhanus": "Sagittarius",
    "makara": "Capricorn", "makar": "Capricorn", "kumbha": "Aquarius",
    "meena": "Pisces", "mina": "Pisces",
}

_ORDINAL_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11,
    "twelfth": 12,
}
_ORDINAL_SUFFIX = {1: "st", 2: "nd", 3: "rd", 21: "st", 22: "nd", 23: "rd"}


def ordinal(n: int) -> str:
    return f"{n}{_ORDINAL_SUFFIX.get(n, 'th')}"


def _norm(word: str) -> str:
    """Lowercase, letters only — so `Mrigashira`, `mrigasira` and `Mrig-ashira`
    all collide before the alias table is consulted."""
    return re.sub(r"[^a-z]", "", word.lower())


# Nakshatra spellings vary more than any other name in the corpus, and a model
# will happily write "Moola" where the engine says "Mula". Rather than a table of
# every variant, the comparison runs over a normalized form with the handful of
# systematic transliteration swaps applied.
_NAK_SUBS = [("oo", "u"), ("aa", "a"), ("ee", "i"), ("sh", "s"), ("z", "s"),
             ("kri", "kr"), ("ri", "r"), ("v", "b"), ("th", "t"), ("w", "v")]


def _nak_key(name: str) -> str:
    key = _norm(name)
    for a, b in _NAK_SUBS:
        key = key.replace(a, b)
    return key


_NAK_BY_KEY = {_nak_key(n): n for n in NAKSHATRA_NAMES}


_VOWEL_FORMS = {"a": "a+", "e": "(?:e+|ee)", "i": "(?:i+|ee)",
                "o": "(?:o+|u)", "u": "(?:u+|oo)"}
# Consonants a transliteration may or may not aspirate: Dhanishta/Dhanishtha,
# Shatabhisha/Satabhisha, Jyeshtha/Jyestha.
_ASPIRABLE = set("stdkgbpjc")


def _nak_regex(name: str) -> str:
    """A pattern matching the spellings of one nakshatra that a model may write.

    `_nak_key` already collapses variants back to the canonical name — but only
    *after* something matched, and the anchors are found by literal pattern. So
    without this, "Moola" is not a word the extractor sees at all, and a wrong
    Moola claim goes unchecked rather than unflagged: a silent hole, which is the
    failure mode this whole module exists to close. Enumerating spellings was
    tried first and kept missing one (`Satabhisha`, `Dhanishtha`, `Poorva`);
    making each letter tolerant covers the family instead of its members.
    """
    out = []
    prev_consonant = False
    for ch in name.lower():
        if ch == " ":
            out.append(r"[\s-]+")
            prev_consonant = False
        elif ch == "h" and prev_consonant:
            prev_consonant = False       # already emitted as an optional h
        elif ch in _VOWEL_FORMS:
            out.append(_VOWEL_FORMS[ch])
            prev_consonant = False
        elif ch == "v":
            out.append("[vw]")
            prev_consonant = False
        else:
            out.append(re.escape(ch) + ("h?" if ch in _ASPIRABLE else ""))
            prev_consonant = ch in _ASPIRABLE
    return "".join(out)


# The longest alternatives come first so "Purva Phalguni" wins over a bare
# "Purva Ashadha" prefix.
_NAK_PATTERN = "|".join(
    _nak_regex(n) for n in sorted(NAKSHATRA_NAMES, key=len, reverse=True))

_MONTHS = ("january february march april may june july august september "
           "october november december").split()

# ── Frame-of-reference guards ───────────────────────────────────────────────
# A sentence matching any of these is not *about* the natal D1 chart, so its
# numbers are not comparable to D1 facts. Each entry is a real phrasing seen in
# this app's readings, and each is pinned by a test.
_SKIP = re.compile(r"""
    \b(?:navamsa|dasamsa|drekkana|dwadasamsa|chaturthamsa|saptamsa|shodasamsa
      |trimsamsa|varga|divisional|amsa|chalit|bhava\s+chalit)\b
  | \bd-?(?:[2-9]|[1-9]\d)\b                       # D9, D-10, D60
  | \b(?:transit|transits|transiting|gochara|ingress|ingresses|retrograding
      |stations?|conjoins?\s+the\s+transit)\b
  | \b(?:annual|varshaphal|varshphal|varsha|tajaka|tajika|muntha|solar\s+return
      |tithi\s+pravesha)\b
  | \b(?:prashna|horary|kp\s|sub-?lord|cuspal|significator)\b
  | \b(?:arudha|karakamsa|swamsa|upapada|\bal\b|\bul\b)\b
  | \bfrom\s+the\s+(?:moon|chandra|sun|surya|arudha|karakamsa|lagna|ascendant
      |7th|10th)\b
  | \bif\b | \bwere\s+(?:it|they|he|she|to|in)\b | \bwould\s+(?:be|have|place)\b
  | \b(?:suppose|hypothetical|imagine)\b
  | \b(?:people|natives?|anyone|those|someone|persons?)\s+with\b
  | \b(?:in\s+general|generally|typically|classically|traditionally|as\s+a\s+rule)\b
  | \b(?:bphs|parashara|phaladeepika|saravali|jataka|classical\s+texts?)\b
  | \b(?:enters?|entering|moves?\s+into|will\s+(?:be|enter|move|transit))\b
  | \b(?:partner|spouse'?s\s+chart|their\s+chart|the\s+other\s+chart)\b
  | \bperson\s+[2b]\b
""", re.I | re.X)

# What may sit between a subject and its placement. Two tests, not one:
#
#   • no *blocker* anywhere in the gap — a negation, an aspect, a comparison or
#     any verb that describes something other than being placed. "Jupiter gives
#     good results in the 5th house" is a textbook aside, not a claim that
#     Jupiter is in the 5th, and it is the shape a naive matcher gets wrong most.
#   • the last few words before the anchor must be pure connector, so free prose
#     is allowed to intervene ("Saturn, the karaka of longevity, is in the 3rd")
#     while a live verb immediately before the number is not.
_GAP_BLOCKERS = re.compile(r"""
    \b(?:not|never|isn'?t|aren'?t|wasn'?t|no|without|instead|rather|nor)\b
  | \b(?:aspect|aspects|aspected|aspecting|conjunct|conjoins?|conjoined|conjunction
      |opposite|opposition|than|unlike|whereas|but|though|although|however|while
      |versus|vs|except|unless|toward|towards|besides|beyond|unlike)\b
  | \b(?:gives?|giving|indicates?|signif\w+|shows?|brings?|denotes?|promises?
      |produces?|causes?|means?|suggests?|blesses?|protects?|afflicts?|damages?
      |strengthens?|weakens?|influences?|activates?|triggers?|governs?|controls?
      |represents?|relates?|points?|refers?|applies)\b
""", re.I | re.X)

# Words allowed in the immediate run-up to the anchor. Condition and dignity
# words are here too, so "Venus is combust in Taurus" still yields the sign.
_CONNECTORS = set("""
    is are was were sits sit sitting stands placed posited positioned located
    stationed occupies occupy occupying resides residing lies falls found
    in into within at the of and or a an this that its his her their both also
    house houses bhava sign rasi nakshatra star then itself native natives
    chart combust retrograde vakri exalted debilitated vargottama own
""".split())
_TAIL_WORDS = 3
_MAX_GAP = 90

# A comma before a conjunction starts a new clause, and a new clause is a new
# subject: ", and the 1st house is Aries" says nothing about the planet named
# before the comma. Without this, "The 1st lord is Mars, and the 1st house is
# Aries" reads as Mars being *in* the 1st.
_NEW_CLAUSE = re.compile(r"[,;]\s*(?:and|or|but|while|so|then|which|whose|where)\b", re.I)

# "the 9th house IS Capricorn" — a copula and nothing else. Any preposition and
# the sign belongs to whatever planet is being placed, not to the house.
_BARE_COPULA = re.compile(r"^[\s,;:=—–-]*(?:is|was|remains|stands\s+as)?[\s,;:=—–-]*$", re.I)

_LORD_GAP = re.compile(
    r"\b(?:lord|lords|lordship|ruler|rules|ruled|ruling|owns|owner|governs)\b", re.I)

# "the 2nd Lord (Mercury)" — the lord word comes AFTER the ordinal, which the gap
# between two anchors cannot see. Models write this constantly, and without it
# every such phrase reads as a placement: the first live run of this checker
# reported "Venus is in the 2nd house" from "the 1st Lord (Venus) and 2nd Lord
# (Mercury) are both placed in the 1st house". An ordinal followed by a lord word
# names a lordship and is never a place.
_ORD_TOKEN = rf"(?:\d{{1,2}}(?:st|nd|rd|th)|{'|'.join(_ORDINAL_WORDS)})"
_CONJ = r"(?:and|&|or|\+|,|/)"
_LORD_WORD = r"(?:lord|lords|lordship|ruler|rulers|ruling)"
# The lord word may sit behind a *list* of ordinals: "Mercury (2nd & 5th lord)",
# "Jupiter is the 8th and 11th lord". Both were live output, and both read as
# placements until the lookahead learned to cross the conjunction.
# A glossing aside may sit between the ordinals and the lord word too:
# "Saturn is the 9th (fortune) and 10th (career) lord" — live output, and it read
# as "Saturn is in the 9th house" until the lookahead learned to step over the
# parentheses.
_LORD_TAIL = re.compile(
    rf"^[\s,;:*_/]*(?:(?:\([^)]{{0,40}}\)|{_ORD_TOKEN}|{_CONJ})[\s,;:*_/]*){{0,5}}"
    rf"{_LORD_WORD}\b", re.I)
# What may join a planet to a lordship: nothing at all ("Jupiter (11th Lord)",
# "Venus, 2nd Lord"), or a bare copula ("the 4th lord is Jupiter", "Jupiter is
# the 8th and 11th lord"). Deliberately tight — ") and " must NOT qualify, or the
# second planet in a list inherits the first one's lordship, which is the other
# half of the same bug: "the 1st Lord (Venus) and 2nd Lord (Mercury)" would make
# Venus the 2nd lord.
# "the 8th and 11th", "(1st, 10th, 11th)" — one list, not separate assertions.
_LIST_SEP = re.compile(r"[\s,;()/]*(?:and|or|&|,|/)?[\s,;()/]*")

# "…the 9th house is Capricorn" — the house is the subject of its own clause, so
# it is not the destination of whatever planet was named before it. Checked by
# looking ahead, because the claim would otherwise be emitted at the house anchor
# before the sign is ever seen.
_SIGN_WORDS = "|".join(list(ZODIAC_NAMES) + list(_SIGN_ALIASES))
_SIGN_LEADS = re.compile(
    rf"^\W{{0,3}}({'|'.join(PLANETS)}|lagna|ascendant|rising)\b", re.I)

_HOUSE_IS_SIGN = re.compile(
    rf"^[\s,;:*_]*(?:is|was|remains|falls\s+in)\s+(?:the\s+)?(?:sign\s+of\s+)?"
    rf"(?:{_SIGN_WORDS})\b", re.I)

# NB: an *opening* paren may appear ("Jupiter (11th Lord)") but a closing one may
# not. A subject that has just been closed off is a finished list item, and
# "Your Lagna Lord (Venus), the 9th/10th Lord (Saturn)" made Venus the 9th lord
# by stepping over exactly that bracket.
_LORD_BRIDGE = re.compile(
    r"^[\s,;:=—–(\[*\-]*(?:is|was|are|remains|being)?\s*(?:the)?[\s,;:=—–(\[*\-]*$",
    re.I)

_CONDITIONS = {
    "retrograde": "retrograde", "vakri": "retrograde", "retrogression": "retrograde",
    "combust": "combust", "combustion": "combust", "asta": "combust",
    "vargottama": "vargottama",
}
# Which planets each condition is meaningful for. The engine flags retrogression
# only for the five tara-grahas (Rahu/Ketu are Mean nodes, so perpetually
# retrograde and deliberately unflagged) — checking a Rahu claim against that
# would manufacture a contradiction out of a convention.
_CONDITION_SCOPE = {
    "retrograde": {"Mars", "Mercury", "Jupiter", "Venus", "Saturn"},
    "combust": {"Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"},
    "vargottama": set(PLANETS),
}
_DIGNITIES = {"exalted": "exalted", "exaltation": "exalted", "uccha": "exalted",
              "debilitated": "debilitated", "debilitation": "debilitated",
              "neecha": "debilitated", "neecha bhanga": None, "fallen": "debilitated"}


# ── The truth table ─────────────────────────────────────────────────────────

@dataclass
class Facts:
    """Everything a claim can be checked against, taken from the same context the
    model was handed. Empty maps mean "not known here", never "false"."""
    planet_house: Dict[str, int] = field(default_factory=dict)
    planet_sign: Dict[str, str] = field(default_factory=dict)
    planet_nakshatra: Dict[str, str] = field(default_factory=dict)
    house_sign: Dict[int, str] = field(default_factory=dict)
    house_lord: Dict[int, str] = field(default_factory=dict)
    lords_of: Dict[str, List[int]] = field(default_factory=dict)
    # None (not {}) while the `conditions` section is absent, so "no flag" and
    # "no information" stay distinguishable.
    flags: Optional[Dict[str, Set[str]]] = None
    dignity: Dict[str, str] = field(default_factory=dict)

    def known(self) -> bool:
        return bool(self.planet_house or self.house_lord)


def _dignity_of(planet: str, sign_name: str) -> Optional[str]:
    """Exalted / debilitated / own, derived from the sign alone — no compute call
    and no extra section to switch off. Rahu and Ketu are left out: the classical
    sources disagree, and `EXALTATION_SIGN` deliberately omits them."""
    if sign_name not in ZODIAC_NAMES:
        return None
    sign0 = ZODIAC_NAMES.index(sign_name)
    ex = EXALTATION_SIGN.get(planet)
    if ex is not None:
        if sign0 == ex:
            return "exalted"
        if sign0 == (ex + 6) % 12:
            return "debilitated"
    if sign0 in OWN_SIGNS.get(planet, set()):
        return "own"
    return None


def build_facts(ctx: Dict[str, Any]) -> Facts:
    """Read a `chart_context.build_chart_context` result into a truth table.

    Tolerant by design: a partial context (a seeded tool-mode block, an older
    saved payload) yields partial facts and therefore fewer checks, which is the
    correct failure mode. Nothing here raises.
    """
    facts = Facts()
    if not isinstance(ctx, dict):
        return facts

    planets = ctx.get("planetary_positions") or {}
    for name, pos in planets.items():
        if name not in PLANETS or not isinstance(pos, dict):
            continue
        house = pos.get("house")
        if isinstance(house, int) and 1 <= house <= 12:
            facts.planet_house[name] = house
        sign = pos.get("sign_name")
        if sign in ZODIAC_NAMES:
            facts.planet_sign[name] = sign
            dig = _dignity_of(name, sign)
            if dig:
                facts.dignity[name] = dig
        nak = pos.get("nakshatra")
        if isinstance(nak, str) and _nak_key(nak) in _NAK_BY_KEY:
            facts.planet_nakshatra[name] = _NAK_BY_KEY[_nak_key(nak)]

    lagna = ctx.get("lagna") or {}
    if lagna.get("sign_name") in ZODIAC_NAMES:
        facts.planet_sign[LAGNA] = lagna["sign_name"]
        facts.planet_house[LAGNA] = 1

    for row in ctx.get("house_rulers") or []:
        house, sign, lord = row.get("house"), row.get("sign"), row.get("lord")
        if not (isinstance(house, int) and 1 <= house <= 12):
            continue
        if sign in ZODIAC_NAMES:
            facts.house_sign[house] = sign
        if lord in PLANETS:
            facts.house_lord[house] = lord
            facts.lords_of.setdefault(lord, []).append(house)
    for lord in facts.lords_of:
        facts.lords_of[lord].sort()

    # House rulers are seeded unconditionally upstream, but a saved context from
    # before §67 may predate them; the lagna alone is enough to rebuild the table.
    if not facts.house_lord and facts.planet_sign.get(LAGNA):
        asc = ZODIAC_NAMES.index(facts.planet_sign[LAGNA])
        for i in range(12):
            sign0 = (asc + i) % 12
            facts.house_sign[i + 1] = ZODIAC_NAMES[sign0]
            facts.house_lord[i + 1] = RASI_LORDS[sign0]
            facts.lords_of.setdefault(RASI_LORDS[sign0], []).append(i + 1)

    conditions = ctx.get("conditions")
    if isinstance(conditions, dict) and "flagged" in conditions:
        flags: Dict[str, Set[str]] = {p: set() for p in PLANETS}
        for row in conditions.get("flagged") or []:
            planet = row.get("planet")
            if planet not in flags:
                continue
            for flag in row.get("flags") or []:
                label = _norm(flag.get("label", "")) if isinstance(flag, dict) else ""
                if label.startswith("combust"):
                    flags[planet].add("combust")
                elif label.startswith("retrograde"):
                    flags[planet].add("retrograde")
                elif label.startswith("vargottama"):
                    flags[planet].add("vargottama")
        facts.flags = flags
    return facts


# ── Extraction ──────────────────────────────────────────────────────────────

@dataclass
class Claim:
    kind: str            # placement_house | placement_sign | lordship | ...
    subject: str         # a planet name, or the house number as a string
    value: Any
    quote: str           # the sentence it was read from, for the report

    def said(self) -> str:
        """How the claim reads back to a human, in the report and in the retry."""
        if self.kind == "placement_house":
            return f"{self.subject} is in the {ordinal(self.value)} house"
        if self.kind == "placement_sign":
            return f"{self.subject} is in {self.value}"
        if self.kind == "lordship":
            return f"the {ordinal(self.subject)} lord is {self.value}"
        if self.kind == "house_sign":
            return f"the {ordinal(self.subject)} house is {self.value}"
        if self.kind == "nakshatra":
            return f"{self.subject} is in {self.value}"
        if self.kind == "dignity":
            return f"{self.subject} is {self.value}"
        return f"{self.subject} is {self.value}"


_DIGNITY_PATTERN = "|".join(
    sorted((k.replace(" ", r"\s+") for k in _DIGNITIES), key=len, reverse=True))
_MONTH_PATTERN = "|".join(_MONTHS)

_ANCHOR = re.compile(rf"""
    (?P<planet>\b(?:{'|'.join(PLANETS)}|{'|'.join(_PLANET_ALIASES)})\b)
  | (?P<house>\b(?:(?:the\s+)?(?:\d{{1,2}}(?:st|nd|rd|th)|{'|'.join(_ORDINAL_WORDS)})
        (?:\s+(?:house|bhava))?
      | house\s+(?:no\.?\s*)?\d{{1,2}}
      | bhava\s+\d{{1,2}}
      | h\d{{1,2}})\b)
  | (?P<sign>\b(?:{'|'.join(ZODIAC_NAMES)}|{'|'.join(_SIGN_ALIASES)})\b)
  | (?P<nakshatra>\b(?:{_NAK_PATTERN})\b)
  | (?P<condition>\b(?:{'|'.join(_CONDITIONS)})\b)
  | (?P<dignity>\b(?:{_DIGNITY_PATTERN})\b)
""", re.I | re.X)

_HOUSE_NUM = re.compile(r"\d{1,2}")
# An ordinal with no "house" after it is only a house if the next word isn't
# measuring something else — "in the first half of 2027" is not a placement.
# "(6th/12th Axis)", "the 2nd/7th polarity" — naming a pair of houses, not
# placing anything in either of them.
_AXIS_TAIL = re.compile(
    rf"^[\s/,&]*(?:{_ORD_TOKEN}[\s/,&]*)*(?:axis|axes|polarity|pair|combination)\b",
    re.I)

_NOT_A_HOUSE = re.compile(
    rf"^\W*(?:half|halves|part|parts|portion|quarter|third|phase|stage|segment"
    rf"|round|time|week|month|year|day|decade|century|cycle|chapter|point|step"
    rf"|of\s+(?:{_MONTH_PATTERN})|\d{{4}})\b", re.I)


def _house_number(text: str, tail: str) -> Optional[int]:
    """The house an anchor names, or None when the ordinal is measuring something
    other than a bhava."""
    digits = _HOUSE_NUM.search(text)
    if digits:
        n = int(digits.group())
    else:
        word = _norm(text.replace("the", "", 1))
        n = _ORDINAL_WORDS.get(word)
        if n is None:
            for w, v in _ORDINAL_WORDS.items():
                if _norm(text).endswith(w):
                    n = v
                    break
    if n is None or not 1 <= n <= 12:
        return None
    if _AXIS_TAIL.match(tail):
        return None
    spelled_out = bool(re.search(r"\b(?:house|bhava|h\d)\b", text, re.I))
    if not spelled_out and _NOT_A_HOUSE.match(tail):
        return None
    return n


def _split_sentences(text: str) -> List[str]:
    """Sentences, with markdown structure treated as a boundary. A heading or a
    bullet is its own claim-bearing unit even without a full stop."""
    chunks: List[str] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        for part in re.split(r"(?<=[.!?;:])\s+", line):
            part = part.strip()
            if part:
                chunks.append(part)
    return chunks


def _clean(sentence: str) -> str:
    """Markdown emphasis out of the way so `**Saturn**` still reads as Saturn."""
    return re.sub(r"[*_`#>]+", " ", sentence)


def extract_claims(text: str) -> List[Claim]:
    """Every checkable assertion about the natal chart, in order of appearance."""
    claims: List[Claim] = []
    for sentence in _split_sentences(text):
        if _SKIP.search(sentence):
            continue
        claims.extend(_claims_in(_clean(sentence), sentence))
    return claims


def _claims_in(clean: str, original: str) -> List[Claim]:
    anchors = []
    for m in _ANCHOR.finditer(clean):
        kind = m.lastgroup
        raw = m.group()
        if kind == "planet":
            value = _PLANET_ALIASES.get(_norm(raw), raw.title())
            if value not in PLANETS and value != LAGNA:
                continue
        elif kind == "house":
            value = _house_number(raw, clean[m.end():m.end() + 24])
            if value is None:
                continue
        elif kind == "sign":
            value = _SIGN_ALIASES.get(_norm(raw), raw.title())
            if value not in ZODIAC_NAMES:
                continue
        elif kind == "nakshatra":
            value = _NAK_BY_KEY.get(_nak_key(raw))
            if value is None:
                continue
        elif kind == "condition":
            value = _CONDITIONS[_norm(raw)]
        else:
            value = _DIGNITIES.get(_norm(raw))
            if value is None:
                continue
        anchors.append({"kind": kind, "value": value,
                        "start": m.start(), "end": m.end()})

    out: List[Claim] = []
    subject: Optional[str] = None        # the planet a placement attaches to
    pending_house: Optional[int] = None  # the last house named
    house_role = "bare"                  # how that house was named: bare|placement|lordship
    # Houses that said "Lord" but have not named a planet yet. A list, because a
    # run of them shares one: "The 2nd/5th Lords (Mercury)" is two lordships, and
    # keeping only the first or the last silently halved that sentence.
    lord_houses: List[int] = []
    house_list = False                   # houses still running as one list, no planet since
    prev_end = 0                         # a relation binds to the NEAREST anchor

    for a in anchors:
        # A consumed lord word can put `prev_end` past this anchor entirely
        # ("the 8th and 11th lord" swallows the 11th); an empty gap is the right
        # reading there — the two ordinals share one lord.
        gap = clean[prev_end:a["start"]] if a["start"] >= prev_end else ""
        prev_end = max(prev_end, a["end"])

        if a["kind"] == "planet":
            # "the 9th house … is ruled by Jupiter" / "the 9th lord is Saturn" /
            # "the 1st Lord (Venus)" — in the last, the lord word sits in the gap
            # anyway; `lord_pending` covers the shapes where it does not.
            if lord_houses and _LORD_BRIDGE.match(gap):
                # "As the 4th lord (home/happiness) in the 1st, the Sun …" — the
                # Sun is the *4th* lord. Binding to `pending_house` instead made
                # it the 1st lord, because a later house had taken that slot.
                for h in lord_houses:
                    out.append(Claim("lordship", h, a["value"], original))
                house_role = "lordship"
                lord_houses = []
            elif pending_house is not None and _lord_ok(gap):
                out.append(Claim("lordship", pending_house, a["value"], original))
                house_role = "lordship"
                lord_house = None
            subject = a["value"]
            house_list = False   # a new subject ends the previous house list
            continue

        if a["kind"] == "house":
            trailing_lord = _LORD_TAIL.match(clean[a["end"]:a["end"] + 96])
            lord_follows = bool(trailing_lord)
            if trailing_lord:
                # Consume the lord word, or the NEXT planet sees it in its gap and
                # inherits a lordship that was already spoken for: "Jupiter (11th
                # Lord) and Ketu" made Ketu the 11th lord.
                prev_end = a["end"] + trailing_lord.end()
            if pending_house is not None and house_list \
                    and _LIST_SEP.fullmatch(gap or ""):
                # A list continues whatever the first item was. "lord of the 8th
                # and 11th" shares its lord; everything else shares *nothing* —
                # "…are in Kendra houses (1st, 10th, 11th)" was read as Venus
                # being in the 10th and the 11th because the later items in the
                # list bound to a subject the first item had already refused.
                # `lord_pending` means the lord is still coming ("2nd/5th Lords
                # (Mercury)"), so the list must not bind to whoever came before.
                if lord_houses:
                    lord_houses.append(a["value"])   # the run shares one lord
                elif house_role == "lordship" and subject:
                    out.append(Claim("lordship", a["value"], subject, original))
                pending_house = a["value"]
                continue
            elif subject and _lord_ok(gap):
                out.append(Claim("lordship", a["value"], subject, original))
                house_role = "lordship"
                pending_house = a["value"]
                lord_houses = []
                house_list = True
                continue
            elif lord_follows:
                # "…and 2nd Lord (Mercury)…" — a lordship, so never a placement.
                # It attaches to a preceding planet only when nothing but
                # punctuation separates them ("Jupiter (11th Lord)"); a planet
                # further back in a list is somebody else's lord.
                if subject and _LORD_BRIDGE.match(gap):
                    out.append(Claim("lordship", a["value"], subject, original))
                    lord_houses = []
                else:
                    lord_houses.append(a["value"])
                house_role = "lordship"
                pending_house = a["value"]
                house_list = True
                continue
            elif subject and not lord_houses and _placement_ok(gap) \
                    and not _HOUSE_IS_SIGN.match(clean[a["end"]:a["end"] + 40]):
                out.append(Claim("placement_house", subject, a["value"], original))
                house_role = "placement"
                lord_houses = []
                house_list = True
                pending_house = a["value"]
                continue
            else:
                house_role = "bare"
            pending_house = a["value"]
            house_list = True
            continue

        if a["kind"] == "sign":
            tail = clean[a["end"]:a["end"] + 20]
            leads = _SIGN_LEADS.match(tail)
            if leads:
                # "Taurus Lagna", "Taurus rising", "the Leo Moon" — the sign leads
                # its own subject, and that subject is not whatever planet was
                # named before it ("the Taurus Lagna, the Leo Moon" put the Lagna
                # in Leo).
                who = _PLANET_ALIASES.get(_norm(leads.group(1)), leads.group(1).title())
                out.append(Claim("placement_sign", who, a["value"], original))
            elif pending_house is not None and house_role != "placement" \
                    and _BARE_COPULA.match(gap):
                # "the 9th house is Capricorn" — a bare copula after the house
                # gives the house its sign. The preposition is what tells the two
                # apart: "…lord of the 9th, is IN Cancer" is a planet's placement,
                # and reading it as the 9th house's sign is a false alarm.
                out.append(Claim("house_sign", pending_house, a["value"], original))
            elif subject and _placement_ok(gap):
                out.append(Claim("placement_sign", subject, a["value"], original))
            continue

        if a["kind"] == "nakshatra" and subject and _placement_ok(gap):
            out.append(Claim("nakshatra", subject, a["value"], original))
            continue

        if a["kind"] in ("condition", "dignity"):
            if subject and _placement_ok(gap):
                out.append(Claim(a["kind"], subject, a["value"], original))
            else:
                # "…the Rahu Mahadasha and the Debilitated 7th Lord…" — the word
                # opens a new noun phrase, so the planet before it stops being the
                # subject. Without this the 7th lord came out as Rahu, purely
                # because an anchor sitting between them hid the distance.
                subject = None
    return out


def _placement_ok(gap: str) -> bool:
    """Whether `gap` — the text between an anchor and the one before it — reads as
    "…is placed…" rather than as any other relation."""
    if len(gap) > _MAX_GAP or _GAP_BLOCKERS.search(gap) or _LORD_GAP.search(gap):
        return False
    if _NEW_CLAUSE.search(gap):
        return False
    if ")" in gap:
        # The subject was parenthetical — "the 10th house (Saturn) and the 1st
        # house (Venus)" names two lords, and Saturn is not in the 1st. Crossing
        # a closing paren to place a planet costs a few true claims and removes a
        # whole family of false ones.
        return False
    return _tail_is_connector(gap)


def _lord_ok(gap: str) -> bool:
    """Same, for "…is the lord of…". The lord word itself is what makes it a
    lordship, so only the blockers apply."""
    return (len(gap) <= _MAX_GAP and bool(_LORD_GAP.search(gap))
            and not _GAP_BLOCKERS.search(gap))


def _tail_is_connector(gap: str) -> bool:
    """The last few words before the anchor must all be connectors. Prose may sit
    further back; a live verb immediately before the number may not."""
    words = re.findall(r"[a-z']+", gap.lower())
    return all(w in _CONNECTORS for w in words[-_TAIL_WORDS:])


# ── Checking ────────────────────────────────────────────────────────────────

@dataclass
class Contradiction:
    kind: str
    said: str
    truth: str
    quote: str

    def as_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "said": self.said, "truth": self.truth,
                "quote": self.quote}


def _check_claim(claim: Claim, facts: Facts) -> Optional[Contradiction]:
    """The truth for one claim, or None when it holds — or cannot be judged."""
    k, subject, value = claim.kind, claim.subject, claim.value

    if k == "placement_house":
        truth = facts.planet_house.get(subject)
        if truth and truth != value:
            sign = facts.planet_sign.get(subject)
            where = f" ({sign})" if sign else ""
            return Contradiction(k, claim.said(),
                                 f"{subject} is in the {ordinal(truth)} house{where}",
                                 claim.quote)
    elif k == "placement_sign":
        truth = facts.planet_sign.get(subject)
        if truth and truth != value:
            return Contradiction(k, claim.said(), f"{subject} is in {truth}", claim.quote)
    elif k == "lordship":
        # "Venus is the Lagna Lord (1st)" is correct English and not a claim that
        # the *Lagna* rules the 1st — the Lagna is not a graha and rules nothing.
        if value not in PLANETS:
            return None
        truth = facts.house_lord.get(subject)
        if truth and truth != value:
            sign = facts.house_sign.get(subject, "")
            because = f" — the {ordinal(subject)} is {sign}" if sign else ""
            rules = facts.lords_of.get(value)
            also = (f", and {value} rules the "
                    + " and ".join(ordinal(h) for h in rules)) if rules else \
                   (f", and {value} rules no house here" if value in PLANETS else "")
            return Contradiction(k, claim.said(),
                                 f"the {ordinal(subject)} lord is {truth}{because}{also}",
                                 claim.quote)
    elif k == "house_sign":
        truth = facts.house_sign.get(subject)
        if truth and truth != value:
            return Contradiction(k, claim.said(),
                                 f"the {ordinal(subject)} house is {truth}", claim.quote)
    elif k == "nakshatra":
        truth = facts.planet_nakshatra.get(subject)
        if truth and truth != value:
            return Contradiction(k, claim.said(),
                                 f"{subject} is in {truth}", claim.quote)
    elif k == "dignity":
        truth = facts.dignity.get(subject)
        if subject in facts.planet_sign and value in ("exalted", "debilitated") \
                and truth != value:
            sign = facts.planet_sign[subject]
            state = truth or "neither exalted nor debilitated"
            return Contradiction(k, claim.said(),
                                 f"{subject} is in {sign} — {state}", claim.quote)
    elif k == "condition":
        if facts.flags is None or subject not in _CONDITION_SCOPE.get(value, set()):
            return None
        if subject in facts.flags and value not in facts.flags[subject]:
            return Contradiction(k, claim.said(),
                                 f"{subject} is not {value}", claim.quote)
    return None


def check(text: str, facts: Facts) -> Dict[str, Any]:
    """Check a finished reading. Returns a report dict, always the same shape:

        {"checked": int, "contradictions": [ {kind, said, truth, quote} ], ...}

    `checked` is how many assertions were actually testable, which is the number
    that makes the contradiction *rate* in the admin console mean anything: a
    reading with no checkable claims is not a clean reading.
    """
    report = {"checked": 0, "claims": 0, "contradictions": []}
    if not text or not isinstance(facts, Facts) or not facts.known():
        return report
    seen = set()
    for claim in extract_claims(text):
        report["claims"] += 1
        verdict = _check_claim(claim, facts)
        judged = _judgeable(claim, facts)
        report["checked"] += 1 if judged else 0
        if verdict:
            key = (verdict.kind, verdict.said)
            if key in seen:            # the same slip repeated is one problem
                continue
            seen.add(key)
            report["contradictions"].append(verdict.as_dict())
    return report


def _judgeable(claim: Claim, facts: Facts) -> bool:
    """Whether the facts had anything to say about this claim at all."""
    k, s = claim.kind, claim.subject
    if k == "placement_house":
        return s in facts.planet_house
    if k == "placement_sign":
        return s in facts.planet_sign
    if k == "lordship":
        return s in facts.house_lord
    if k == "house_sign":
        return s in facts.house_sign
    if k == "nakshatra":
        return s in facts.planet_nakshatra
    if k == "dignity":
        return s in facts.planet_sign
    if k == "condition":
        return facts.flags is not None and s in _CONDITION_SCOPE.get(claim.value, set())
    return False


# ── What the reader and the model are told ──────────────────────────────────

CORRECTION_HEADER = "⚠ Checked against the computed chart"


def annotation(contradictions: List[Dict[str, Any]]) -> str:
    """The block appended under a reading that still contradicts the chart.

    The prose is left exactly as the model wrote it. Editing someone's sentences
    to say the opposite leaves paragraphs that no longer follow, and quietly
    deleting them leaves a hole; naming the error under the reading is the only
    version that stays honest about what happened.
    """
    if not contradictions:
        return ""
    n = len(contradictions)
    lines = [
        "\n\n---\n",
        f"**{CORRECTION_HEADER} — {n} statement{'s' if n > 1 else ''} "
        f"{'do' if n > 1 else 'does'} not match**\n",
    ]
    for c in contradictions:
        lines.append(f"- The reading says *“{c['said']}”* — in this chart, "
                     f"**{c['truth']}**.")
    lines.append("\nThese were flagged automatically by comparing the reading "
                 "with the computed chart. Where they disagree, the chart is "
                 "right.")
    return "\n".join(lines)


def retry_instruction(contradictions: List[Dict[str, Any]]) -> str:
    """Appended to the original prompt for the one regeneration attempt.

    It names the specific wrong sentence and the specific right fact, because a
    general "be careful about house lords" is the prompt fix that §67 already
    tried and that only ever helped one chart.
    """
    lines = ["\n\n=== YOUR PREVIOUS ANSWER CONTRADICTED THE CHART ===",
             "You have already answered this once. These statements in that "
             "answer are factually wrong for the chart given above:"]
    for c in contradictions:
        lines.append(f"- You wrote: “{c['said']}”. WRONG — {c['truth']}.")
    lines.append(
        "Write the answer again in full, keeping everything that was right and "
        "correcting these facts. Take every placement and every house lord from "
        "the chart data above, never from a planet's natural karaka-ship and "
        "never from memory. Do not mention this correction or that you are "
        "rewriting — produce the answer as it should have been the first time.")
    return "\n".join(lines)


# ── Orchestration: check, regenerate once, annotate what survives ───────────

MODES = ("off", "log", "annotate", "verify")


async def guard(text: str, facts: Facts, mode: str = "verify",
                regenerate=None) -> tuple:
    """Run the check over a finished reading and return `(text, report)`.

    `regenerate` is an awaitable taking the retry instruction and returning a
    fresh answer. Without one — the streaming path, where the reader has already
    watched the first answer arrive token by token — "verify" degrades to
    "annotate": there is nothing to re-do that the reader has not already seen.

    The retry is kept **only if it is strictly better**. A model told "you said
    the 9th lord is Jupiter, it is Saturn" usually fixes it, but a model having a
    bad day can answer worse the second time, and trading a known set of errors
    for a larger unknown one is not an improvement.
    """
    # `contradictions` is what SURVIVED — it drives the annotation and the admin
    # queue. `initial` is what the model said before being corrected, and it is
    # the honest answer to "how often does the model contradict its own chart":
    # counting only survivors would report a flawless 0% for a model that gets it
    # wrong every time and is rescued by the retry every time.
    report = {"mode": mode, "claims": 0, "checked": 0, "contradictions": [],
              "initial": [], "initial_contradictions": 0, "regenerated": False,
              "fixed_by_retry": 0}
    if mode not in MODES or mode == "off" or not facts.known():
        return text, report

    first = check(text, facts)
    report.update({k: first[k] for k in ("claims", "checked", "contradictions")})
    report["initial"] = list(first["contradictions"])
    report["initial_contradictions"] = len(first["contradictions"])
    if not first["contradictions"]:
        return text, report

    if mode == "verify" and regenerate is not None:
        try:
            retry_text = await regenerate(retry_instruction(first["contradictions"]))
        except Exception as e:
            # The retry is a best effort on top of an answer we already have.
            # Losing it costs the reader nothing but the correction note.
            print(f"[claim_check] regeneration failed: {e}")
            retry_text = None
        if retry_text and retry_text.strip():
            second = check(retry_text, facts)
            report["regenerated"] = True
            if len(second["contradictions"]) < len(first["contradictions"]):
                report["fixed_by_retry"] = (len(first["contradictions"])
                                            - len(second["contradictions"]))
                text = retry_text
                report.update({k: second[k]
                               for k in ("claims", "checked", "contradictions")})

    if report["contradictions"] and mode in ("annotate", "verify"):
        text = text + annotation(report["contradictions"])
    return text, report
