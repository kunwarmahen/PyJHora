"""Mangal cancellations travel as codes the UI translates (todo.md §85.2).

The English `cancellations` stay for the AI and API readers; `cancellation_codes`
must say the same thing one-for-one, and the Hindi built from them must never
fall back to English."""
import re

from astrology.compute_match import _mangal_dosha
from astrology.compute_strength import _MANGLIK_CANCEL_HI, _manglik_description

LATIN = re.compile(r"[A-Za-z]")


def _pp(lagna, mars, jupiter=None, moon=0, venus=0):
    """Synthetic rasi_chart output: [['L', (sign, long)], [pid, (sign, long)], ...]."""
    rows = [["L", (lagna, 1.0)], [1, (moon, 1.0)], [2, (mars, 1.0)], [5, (venus, 1.0)]]
    rows.append([4, (jupiter if jupiter is not None else (mars + 3) % 12, 1.0)])
    return rows


CASES = {
    "own_sign": _pp(lagna=0, mars=0),        # Mars in Aries, 1st from an Aries Lagna
    "exalted": _pp(lagna=3, mars=9),         # Mars in Capricorn, 7th from Cancer
    "jupiter": _pp(lagna=4, mars=5, jupiter=5),  # Mars+Jupiter in Virgo, 2nd from Leo
}


def test_every_code_fires_and_matches_the_english_one_for_one():
    seen = set()
    for pp in CASES.values():
        m = _mangal_dosha(pp)
        assert len(m["cancellation_codes"]) == len(m["cancellations"])
        seen |= {c["code"] for c in m["cancellation_codes"]}
        if m["cancellations"]:
            assert m["status"] == "cancelled" and not m["manglik"]
    # Exception: Mars in Taurus is the listed exception for the 12th from the Lagna.
    m = _mangal_dosha(_pp(lagna=2, mars=1))
    assert [c["code"] for c in m["cancellation_codes"]] == ["exception"]
    assert m["cancellation_codes"][0]["house"] == 12
    seen.add("exception")
    assert seen == set(_MANGLIK_CANCEL_HI)


def test_no_placement_means_no_codes():
    m = _mangal_dosha(_pp(lagna=0, mars=2))  # 3rd from the Lagna
    assert m["status"] == "none" and m["cancellation_codes"] == []


def test_hindi_description_has_the_reasons_and_no_english():
    for pp in list(CASES.values()) + [_pp(lagna=2, mars=1)]:
        m = _mangal_dosha(pp)
        hi = _manglik_description(m, "hi")
        assert not LATIN.search(hi), hi
        if m["cancellation_codes"]:
            assert "निरस्त" in hi
