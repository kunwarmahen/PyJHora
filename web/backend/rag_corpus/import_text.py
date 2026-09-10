"""Turn a scanned public-domain classical text into RAG corpus `.jsonl`.

The RAG feature (§5.12) can only cite what is in `rag_corpus/*.jsonl`. This
script fills that folder from the raw OCR text of a **public-domain** edition —
the kind Archive.org publishes as `<id>_djvu.txt` — so the citations carry real
chapter/verse references instead of the honest-but-vague "General principle".

    python rag_corpus/import_text.py brihat-jataka-1885 \
        --input bj_raw.txt --output rag_corpus/brihat_jataka.jsonl

Why a profile per book: every scan is laid out differently, and 19th-century OCR
mangles exactly the parts a parser leans on. In this book the chapter headings
alone read `CHAPTER IV*`, `r CHAPTER IH.`, `CHPTER X.`, `OEfAPTER VI.` and
`CHAPTER XXVIir.` — so headings are matched by *edit distance* to the word
CHAPTER, numerals are read through an OCR confusion map, and both chapter and
stanza numbers are then forced to run 1,2,3… A number that does not continue the
sequence is a page number or a footnote marker, not a verse.

**OCR quality gate.** A garbled passage is worse than a missing one: the model
would quote nonsense under a real verse number. Every candidate stanza is scored
by the fraction of its words that a dictionary (or the bundled Jyotish glossary)
recognises, and anything below `--min-quality` is dropped. The run prints how
many stanzas it kept, so the loss is visible rather than silent.

Nothing here invents text. Each output line is a verse as the translator wrote
it, with the chapter/verse number it was printed under.
"""
import argparse
import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))

# ── OCR repair ─────────────────────────────────────────────────────────────
# Roman numerals in headings, as this scan actually renders them. Applied to the
# numeral only — never to body text.
_NUMERAL_FIXES = str.maketrans({
    "l": "I", "1": "I", "i": "I", "|": "I", "!": "I", "r": "I", "t": "I",
    "L": "I", "J": "I", "H": "I",  # 'H' is a run-together 'II'; see _roman()
    "Y": "V", "v": "V", "y": "V", "U": "V",
    "Z": "X", "z": "X", "x": "X", "K": "X",
})

_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

# Words a dictionary will not know but this text is full of. Kept lowercase.
JYOTISH_WORDS = {
    "rasi", "rasis", "graha", "grahas", "bhava", "bhavas", "lagna", "lagnas",
    "navamsa", "navamsas", "amsa", "amsas", "drekkana", "drekkanas", "hora",
    "horas", "dwadasamsa", "trimsamsa", "saptamamsa", "dasamsa", "shodasamsa",
    "shashtyamsa", "shadvarga", "dasavarga", "varga", "vargas", "dasa", "dasas",
    "bhukti", "antara", "ayana", "ayanamsa", "kendra", "kendras", "kona",
    "trikona", "panapara", "apoklima", "upachaya", "arudha", "argala",
    "mesha", "vrishabha", "mithuna", "kataka", "simha", "kanya", "tula",
    "vrischika", "dhanus", "makara", "kumbha", "meena", "vrisbabha",
    "aswani", "ashwini", "bharani", "krittika", "rohini", "mrigasira", "ardra",
    "punarvasu", "pushya", "aslesha", "magha", "purvaphalguni", "uttaraphalguni",
    "hasta", "chitra", "swati", "visakha", "anuradha", "jyeshta", "mula",
    "purvashadha", "uttarashadha", "sravana", "dhanishta", "satabhisha",
    "purvabhadra", "uttarabhadra", "revati", "abhijit",
    "surya", "chandra", "kuja", "mangala", "budha", "guru", "brihaspati",
    "sukra", "shukra", "sani", "shani", "rahu", "ketu", "mandi", "gulika",
    "yoga", "yogas", "rajayoga", "rajayogas", "karaka", "karakas", "karana",
    "tithi", "tithis", "nakshatra", "nakshatras", "asterism", "asterisms",
    "malefic", "malefics", "benefic", "benefics", "combust", "retrograde",
    "exaltation", "debilitation", "exalted", "debilitated", "aspect", "aspects",
    "zodiac", "zodiacal", "ecliptic", "horoscopy", "horoscope", "astrology",
    "varaha", "mihira", "parasara", "satyacharya", "jataka", "brihat", "samhita",
    "kalapurusha", "kalapurnsha", "purusha", "atma", "deva", "devas", "veda",
    "vedas", "karma", "muni", "brahmin", "brahmins", "kshatriya", "vaisya",
    "sudra", "prasna", "prashna", "muhurta", "sandhyakala", "moksha",
    "sthira", "chara", "dwiswabhava", "ubhaya", "vargottama", "neecha",
    "uchcha", "moolatrikona", "mulatrikona", "sputa", "sphuta", "rasyadi",
    "commentator", "stanza", "stanzas", "aforesaid", "th", "st", "nd", "rd",
}


def _load_dictionary() -> set:
    """System wordlist if there is one; the run still works without it."""
    for path in ("/usr/share/dict/words", "/usr/share/dict/american-english",
                 "/usr/dict/words"):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                return {w.strip().lower() for w in fh if w.strip()}
        except OSError:
            continue
    return set()


def _roman(raw: str) -> Optional[int]:
    """Read an OCR-mangled roman numeral, or None if it is not one."""
    s = raw.strip().strip(".,*:;'\"()[]- ")
    if not s:
        return None
    # 'H' is a run-together 'II' in this scan ("CHAPTER IH." is III).
    s = s.replace("H", "II").replace("h", "II")
    s = s.translate(_NUMERAL_FIXES)
    s = re.sub(r"[^IVXLCDM]", "", s.upper())
    if not s:
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        val = _ROMAN_VALUES[ch]
        total += -val if val < prev else val
        prev = max(prev, val)
    return total or None


def _edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _dehyphenate(text: str) -> str:
    """`begin-\\ning` → `beginning`. The scan breaks words at every line end."""
    return re.sub(r"([A-Za-z])-\s*\n\s*([a-z])", r"\1\2", text)


# Running page furniture, e.g. "8 BRIHAT JATAKA. [cH. I." and its mirror
# "tH. I.] IBRIHIT JATAKA. 8" — and, in the same book, "234 UUIUAT JAT&KA.
# [O0« 27." Matched fuzzily for the same reason the headings are: the OCR
# spells the running head a dozen ways, and one that slips through lands
# verbatim in the middle of a quoted verse.
_BRACKET_HEADER = re.compile(r"^\W*\[?\s*[ctCTG][hHnN0][.,].{0,12}$")


def _head_word(token: str, target: str, slack: int) -> bool:
    word = re.sub(r"[^A-Za-z&]", "", token).upper().replace("&", "A")
    return bool(word) and _edit_distance(word, target) <= slack


def _running_head_at(tokens: List[str], i: int) -> bool:
    """True when tokens[i:i+2] are the work and title of the running head.

    Generous slack (the scan renders `BRIHAT JATAKA` as `isRlHAT JATAKA`,
    `BBIIIAT JATAKA`, `UUVAT JAT&KA`, `DainAT JATAKA`, `BRIHAt JkTkKkl`), which
    is safe only because *both* words must land side by side.
    """
    if i + 1 >= len(tokens):
        return False
    return _head_word(tokens[i], "BRIHAT", 3) and _head_word(tokens[i + 1], "JATAKA", 4)


def _looks_like_running_head(line: str) -> bool:
    tokens = line.split()
    return any(_running_head_at(tokens, i) for i in range(len(tokens)))


# Page furniture that rides *along* the running head: a page number before it,
# a bracketed chapter marker after it, and whatever fragment of a word the
# header split in half ("ka)," from "Kataka"). Every alternative requires a
# digit or a punctuation mark, so an ordinary short word next to the header
# ("of", "the", "a") is never mistaken for furniture and eaten.
_PUNCT = r"[\[\](){}<>.,;:*«»'\"|_—-]"
_FURNITURE_TOKEN = re.compile(
    rf"^(?:{_PUNCT}+"                       # pure punctuation
    rf"|{_PUNCT}*\d{{1,3}}{_PUNCT}*"        # a page number
    rf"|{_PUNCT}*[A-Za-z]{{1,3}}{_PUNCT}+"   # 'OH.', 'ka),' — a split fragment
    rf"|{_PUNCT}+[A-Za-z]{{1,3}}{_PUNCT}*)$")


def _scrub_running_heads(text: str) -> str:
    """Excise a running head that the scan ran into the middle of a verse.

    `_strip_furniture` only drops whole lines; the OCR often joins the header to
    the text around it ("…Cancer (Eata*. OH. I.] isRlHAT JATAKA. 5 ka), of the
    shape of a crab…"). Left unscrubbed that lands verbatim inside a quoted
    verse, under a real verse number.
    """
    tokens = text.split()
    i = 0
    out: List[str] = []
    while i < len(tokens):
        if _running_head_at(tokens, i):
            # Walk back over the page number / bracket noise already emitted…
            back = 0
            while back < 3 and out and _FURNITURE_TOKEN.match(out[-1]):
                out.pop()
                back += 1
            # …and forward over the same on the far side.
            i += 2
            fwd = 0
            while fwd < 4 and i < len(tokens) and _FURNITURE_TOKEN.match(tokens[i]):
                i += 1
                fwd += 1
            continue
        out.append(tokens[i])
        i += 1
    return " ".join(out)


def _strip_furniture(lines: Iterable[str]) -> List[str]:
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            out.append("")
            continue
        if _looks_like_running_head(s) or _BRACKET_HEADER.match(s):
            continue
        # A bare page number on its own line.
        if re.fullmatch(r"\W*\d{1,3}\W*", s):
            continue
        out.append(ln)
    return out


def _clean(text: str) -> str:
    text = _dehyphenate(text)
    text = re.sub(r"\s+", " ", text).strip()
    text = _scrub_running_heads(text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


def _quality(text: str, words: set) -> float:
    """Fraction of a passage's words that are real words. 1.0 when unknowable."""
    tokens = [t.lower() for t in re.findall(r"[A-Za-z]{3,}", text)]
    if not tokens:
        return 0.0
    if not words and not JYOTISH_WORDS:
        return 1.0
    known = sum(1 for t in tokens if t in words or t in JYOTISH_WORDS
                or t.rstrip("s") in words or t.rstrip("s") in JYOTISH_WORDS)
    return known / len(tokens)


# ── Profiles ───────────────────────────────────────────────────────────────
class Profile:
    """How one edition is laid out on the page."""
    slug: str
    source: str
    work: str
    chapters: int          # expected chapter count, as a sanity check
    body_starts: str       # regex marking the end of the front matter
    skip_chapters: Tuple[int, ...] = ()   # front/back matter numbered as chapters


class BrihatJataka1885(Profile):
    slug = "brihat-jataka-1885"
    source = "Brihat Jataka (Varaha Mihira)"
    work = ("The Brihat Jataka of Varaha Mihira, translated by "
            "N. Chidambaram Iyer, Foster Press, Madras, 1885 (public domain)")
    chapters = 28
    body_starts = r"^\s*CHAPTER\s+I\s*[.,*]"
    # Ch. 28 is headed "Conclusion": its three stanzas are the author listing
    # his own chapters, not doctrine. (That list is also the best check on this
    # parser — "7. On Ayurdaya", "9. On Ashtakavargas" agree with what the
    # importer puts under Ch. 7 and Ch. 9.)
    skip_chapters = (28,)


PROFILES: Dict[str, Profile] = {p.slug: p for p in (BrihatJataka1885,)}


def _is_heading(line: str) -> Optional[int]:
    """Chapter number if this line is a chapter heading, else None.

    Matched by edit distance because the scan spells the word CHAPTER at least
    four different ways.
    """
    s = line.strip()
    if not s or len(s) > 48 or re.search(r"[a-z]{4}", s):
        return None
    tokens = s.replace(".", " ").replace(",", " ").split()
    for idx, tok in enumerate(tokens):
        word = re.sub(r"[^A-Za-z]", "", tok).upper()
        if not (5 <= len(word) <= 9):
            continue
        if _edit_distance(word, "CHAPTER") > 2:
            continue
        rest = " ".join(tokens[idx + 1:])
        return _roman(rest) or -1     # -1: heading found, numeral unreadable
    return None


_NOTES = re.compile(r"^\s*N\W?[Oo0]\W?[Tt]\W?[Ee]\W?[Ss]?\W{0,3}$")
_STANZA = re.compile(r"^\s*(\d{1,3})\s*[.,]\s+(\S.*)$")


def parse(raw: str, profile: Profile, min_quality: float, min_chars: int,
          words: set) -> Tuple[List[Dict[str, str]], Dict[str, int]]:
    """Split the scan into {chapter, verse, text} passages.

    Two passes, because a wrong chapter number is worse than a missing verse.

    1. Cut the text into *segments* — runs of stanzas numbered 1, 2, 3… A
       segment opens either at a chapter heading or at a bare restart to verse 1
       (five of this book's 28 headings did not survive the scan at all).
    2. Number the segments. **Headings are authoritative**: a heading that reads
       `CHAPTER XII` makes its segment chapter 12, full stop. A heading-less
       segment is only numbered when the arithmetic is unambiguous — the gap
       between the headings on either side has exactly as many restarts in it as
       there are missing chapters. Where it doesn't add up, those segments are
       **dropped**, because there is no way to cite them honestly.
    """
    lines = raw.splitlines()

    start = 0
    for i, ln in enumerate(lines):
        if re.match(profile.body_starts, ln):
            start = i
            break
    lines = _strip_furniture(lines[start:])

    stats = {"stanzas": 0, "kept": 0, "too_short": 0, "low_quality": 0,
             "chapters": 0, "numeral_guessed": 0, "verses_skipped": 0,
             "unplaceable": 0}

    # ── Pass 1: segments ───────────────────────────────────────────────────
    # Each: {"heading": int|None, "verses": [(verse_no, [line, …]), …]}
    segments: List[Dict[str, Any]] = []
    seg: Optional[Dict[str, Any]] = None
    verse = 0
    buf: Optional[List[str]] = None
    in_notes = False

    def close_verse() -> None:
        nonlocal buf
        if seg is not None and buf and verse:
            seg["verses"].append((verse, buf))
        buf = None

    def open_segment(heading: Optional[int]) -> None:
        nonlocal seg, verse, in_notes
        close_verse()
        seg = {"heading": heading, "verses": []}
        segments.append(seg)
        verse, in_notes = 0, False

    for ln in lines:
        head = _is_heading(ln)
        if head is not None:
            open_segment(head if head > 0 else None)
            continue

        if seg is None:
            continue

        m = _STANZA.match(ln)
        if m:
            num = int(m.group(1))
            # Verse 1 again means a chapter heading did not survive the scan.
            if num == 1 and verse >= 2:
                open_segment(None)
            # A small forward gap is a stanza number the scan mangled; a big
            # jump is a page number or a footnote marker, so ignore it.
            if verse < num <= verse + 3 or num == 1:
                close_verse()
                if num > verse + 1:
                    stats["verses_skipped"] += num - verse - 1
                verse, in_notes, buf = num, False, [m.group(2)]
                continue

        if _NOTES.match(ln):
            close_verse()
            in_notes = True
            continue

        if not in_notes and buf is not None:
            buf.append(ln)

    close_verse()

    # ── Pass 2: chapter numbers ────────────────────────────────────────────
    numbers: List[Optional[int]] = [None] * len(segments)
    heading_at = [i for i, s in enumerate(segments) if s["heading"] is not None]

    previous = 0
    for i in heading_at:
        n = segments[i]["heading"]
        if n <= previous:            # unreadable or out of order — best guess
            n = previous + 1
            stats["numeral_guessed"] += 1
        numbers[i] = n
        previous = n
    stats["chapters"] = previous

    # Heading-less runs: number them only when the count matches the gap.
    bounds = [(-1, 0)] + [(i, numbers[i]) for i in heading_at] + \
             [(len(segments), None)]
    for (lo, lo_n), (hi, hi_n) in zip(bounds, bounds[1:]):
        run = list(range(lo + 1, hi))
        if not run:
            continue
        missing = (hi_n - lo_n - 1) if (lo_n and hi_n) else -1
        if missing == len(run):
            for offset, idx in enumerate(run, 1):
                numbers[idx] = lo_n + offset
        else:
            stats["unplaceable"] += sum(len(segments[i]["verses"]) for i in run)

    # ── Emit ───────────────────────────────────────────────────────────────
    passages: List[Dict[str, Any]] = []
    for chapter, segment in zip(numbers, segments):
        for verse_no, raw_lines in segment["verses"]:
            if chapter is None or chapter in profile.skip_chapters:
                continue
            stats["stanzas"] += 1
            text = _clean("\n".join(raw_lines))
            if len(text) < min_chars:
                stats["too_short"] += 1
                continue
            if _quality(text, words) < min_quality:
                stats["low_quality"] += 1
                continue
            stats["kept"] += 1
            passages.append({"chapter": chapter, "verse": verse_no, "text": text})

    return passages, stats


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("profile", choices=sorted(PROFILES), help="edition layout")
    ap.add_argument("--input", required=True, help="raw OCR text file")
    ap.add_argument("--output", required=True, help=".jsonl to write")
    ap.add_argument("--min-quality", type=float, default=0.85,
                    help="drop stanzas below this fraction of real words (0.85)")
    ap.add_argument("--min-chars", type=int, default=80,
                    help="drop stanzas shorter than this (80)")
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = ap.parse_args(argv)

    profile = PROFILES[args.profile]
    with open(args.input, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()

    words = _load_dictionary()
    if not words:
        print("warning: no system wordlist found — quality gate is weaker",
              file=sys.stderr)

    passages, stats = parse(raw, profile, args.min_quality, args.min_chars, words)

    print(f"{profile.slug}: {stats['chapters']} chapters "
          f"(expected {profile.chapters}), {stats['stanzas']} stanzas found, "
          f"{stats['kept']} kept, {stats['too_short']} too short, "
          f"{stats['low_quality']} below quality {args.min_quality}, "
          f"{stats['numeral_guessed']} chapter numerals inferred from sequence, "
          f"{stats['verses_skipped']} verse numbers the scan lost, "
          f"{stats['unplaceable']} stanzas dropped as unciteable")
    if stats["chapters"] != profile.chapters:
        print(f"warning: chapter count {stats['chapters']} != "
              f"{profile.chapters}; the scan may be laid out differently",
              file=sys.stderr)
    if not passages:
        print("nothing to write", file=sys.stderr)
        return 1

    if args.dry_run:
        for p in passages[:5]:
            print(f"  Ch.{p['chapter']} v.{p['verse']}: {p['text'][:110]}…")
        return 0

    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(f"# {profile.work}\n")
        fh.write(f"# Generated by rag_corpus/import_text.py ({profile.slug}); "
                 f"{stats['kept']} of {stats['stanzas']} stanzas passed the "
                 f"OCR quality gate at --min-quality {args.min_quality}.\n")
        for p in passages:
            fh.write(json.dumps({
                "source": profile.source,
                "reference": f"Ch. {p['chapter']} v. {p['verse']}",
                "text": p["text"],
            }, ensure_ascii=False) + "\n")
    print(f"wrote {len(passages)} passages to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
