"""The classical-text corpus and the importer that builds it (§68.8).

A wrong citation is worse than no citation: the whole point of §5.12 is that the
model quotes a source instead of asserting on its own authority, and a passage
filed under the wrong chapter turns that into a confident lie. So these tests
care about *references being right*, not about how much text was imported.
"""
import json
import os
import re
import sys

import pytest

CORPUS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "rag_corpus")
sys.path.insert(0, CORPUS_DIR)
import import_text  # noqa: E402


def _rows(filename):
    path = os.path.join(CORPUS_DIR, filename)
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh
                if line.strip() and not line.startswith("#")]


# ── The shipped corpus ─────────────────────────────────────────────────────
def test_every_corpus_line_is_a_citable_passage():
    import glob
    files = glob.glob(os.path.join(CORPUS_DIR, "*.jsonl"))
    assert files, "no corpus files — the citation feature would have nothing to cite"
    for path in files:
        for row in _rows(os.path.basename(path)):
            assert row.get("source"), f"{path}: passage with no source"
            assert row.get("reference"), f"{path}: passage with no reference"
            assert len(row.get("text", "").strip()) >= 40, f"{path}: stub passage"


def test_brihat_jataka_references_are_well_formed_and_unique():
    rows = _rows("brihat_jataka_1885.jsonl")
    assert len(rows) > 150
    seen = set()
    for row in rows:
        m = re.fullmatch(r"Ch\. (\d+) v\. (\d+)", row["reference"])
        assert m, f"unparseable reference {row['reference']!r}"
        chapter, verse = int(m.group(1)), int(m.group(2))
        assert 1 <= chapter <= import_text.BrihatJataka1885.chapters
        assert verse >= 1
        assert (chapter, verse) not in seen, f"duplicate {row['reference']}"
        seen.add((chapter, verse))


def test_brihat_jataka_carries_no_page_furniture():
    """A running head that survives into a verse gets quoted as scripture."""
    for row in _rows("brihat_jataka_1885.jsonl"):
        tokens = row["text"].split()
        assert not any(import_text._running_head_at(tokens, i)
                       for i in range(len(tokens))), \
            f"{row['reference']} contains the running page header"


@pytest.mark.parametrize("chapter, expected", [
    # From the book's own contents list, which it prints in its final chapter:
    # "7. On Ayurdaya…", "9. On Ashtakavargas", "27. On the Drekkanas".
    (7, r"years|life"),
    (9, r"ashtakavarga|benefic places"),
    (27, r"drekkana"),
])
def test_chapters_are_about_what_the_book_says_they_are_about(chapter, expected):
    texts = " ".join(r["text"] for r in _rows("brihat_jataka_1885.jsonl")
                     if r["reference"].startswith(f"Ch. {chapter} v."))
    assert texts, f"nothing imported for chapter {chapter}"
    assert re.search(expected, texts, re.I), \
        f"chapter {chapter} does not read like its subject — numbering has drifted"


def test_the_conclusion_chapter_is_not_shipped_as_doctrine():
    """Ch. 28 is the author listing his own chapters, not a teaching."""
    assert not [r for r in _rows("brihat_jataka_1885.jsonl")
                if r["reference"].startswith("Ch. 28 ")]


# ── The importer ───────────────────────────────────────────────────────────
SCAN = """
CHAPTER  I.
Definitions.

1.  The first verse of the first chapter, long enough to clear the minimum
length that the importer applies to every passage it keeps.

NOTES.
(a) Commentary that must never be imported as if it were a verse at all.

2.  The second verse of the first chapter, also long enough to be kept by
the length gate that every imported passage has to pass.

12  BRIHAT  JATAKA.  [cH.  I.

r  CHAPTER  IH.
1.  A verse of the third chapter, which the scan reached without ever
printing a heading for the second chapter anywhere on the page.

2.  A second verse of the third chapter, long enough to survive the length
gate that the importer applies to everything that it keeps.

CHAPTER  V.
1.  A verse of the fifth chapter, long enough to survive the length gate
that the importer applies to everything that it keeps.
"""


def _parse(text, **kw):
    kw.setdefault("min_quality", 0.0)
    kw.setdefault("min_chars", 40)
    kw.setdefault("words", set())
    return import_text.parse(text, import_text.BrihatJataka1885, **kw)


def test_headings_are_authoritative_even_when_the_ocr_mangles_them():
    passages, _ = _parse(SCAN)
    refs = {(p["chapter"], p["verse"]) for p in passages}
    # 'r CHAPTER IH.' is chapter three, not "the one after chapter one".
    assert (3, 1) in refs and (3, 2) in refs
    assert (1, 1) in refs and (1, 2) in refs
    assert (5, 1) in refs
    assert not any(c == 2 for c, _ in refs)


def test_notes_are_never_imported_as_verses():
    passages, _ = _parse(SCAN)
    assert not any("Commentary" in p["text"] for p in passages)


def test_page_furniture_never_reaches_a_passage():
    passages, _ = _parse(SCAN)
    assert not any("BRIHAT" in p["text"].upper() for p in passages)


def test_a_chapter_that_cannot_be_numbered_is_dropped_not_guessed():
    """A heading lost to the scan leaves verses no honest reference."""
    scan = SCAN.replace("CHAPTER  V.\n", "")   # ch.4 and ch.5 now run together
    passages, stats = _parse(scan)
    assert stats["unplaceable"] >= 1
    assert not any(p["chapter"] in (4, 5) for p in passages)


def test_the_quality_gate_drops_garbled_ocr():
    garbled = SCAN.replace(
        "The second verse of the first chapter, also long enough to be kept by\nthe length gate that every imported passage has to pass.",
        "Tfao Sna oocupios sigii Arios jupifcer eifcher tho 9fcli housc orr sigii\nCanccr aud thc malcfio planots occupj thc 3rd 6fch aud llfch housos.")
    words = import_text._load_dictionary()
    if not words:
        pytest.skip("no system wordlist on this machine")
    passages, stats = import_text.parse(
        garbled, import_text.BrihatJataka1885, min_quality=0.85, min_chars=40,
        words=words)
    assert stats["low_quality"] >= 1
    assert not any("oocupios" in p["text"] for p in passages)


def test_roman_numerals_survive_this_scans_confusions():
    assert import_text._roman("IH.") == 3          # 'H' is a run-together 'II'
    assert import_text._roman("IV*") == 4
    assert import_text._roman("Xlir.") == 13
    assert import_text._roman("XVIir.") == 18
    assert import_text._roman("XXL") == 21
    assert import_text._roman("XZIII.") == 23
    assert import_text._roman("XXVIir.") == 28
    assert import_text._roman("") is None
