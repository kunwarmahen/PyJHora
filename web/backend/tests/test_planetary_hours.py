"""The running-hora rule (`running_hora_index`).

The day's 24 horas run sunrise -> next sunrise, so the night block's clock times
cross midnight and stop increasing. The rule used to refuse the whole night
block over that, which meant no running hora from sunset onwards — half of every
day, and no hora on the Dashboard's chart of the moment every evening.

The caller reads "now" off the real clock, so these drive the extracted pure
function rather than the compute.
"""
import pytest

from astrology.compute_panchanga import running_hora_index

# A real day: Chicago, 2026-09-09. Sunrise 06:29, sunset ~18:02, next sunrise
# 06:30 — so hora 12 starts the night block and one of them straddles midnight.
def _spans():
    day = [(389 + 63 * i, 389 + 63 * (i + 1)) for i in range(12)]     # 06:29 -> 18:05
    night = []
    t = 1082                                                          # 18:02
    for _ in range(12):
        night.append((t % 1440, (t + 57) % 1440))
        t += 57
    return day + night


def test_finds_the_running_daytime_hora():
    spans = _spans()
    i = running_hora_index(spans, 389 + 70)      # just inside hora 2
    assert i == 1
    assert spans[i][0] <= 389 + 70 < spans[i][1]


def test_finds_a_running_evening_hora():
    """The regression: 19:10 is in the night block, and used to report nothing."""
    spans = _spans()
    i = running_hora_index(spans, 19 * 60 + 10)
    assert i is not None and i >= 12, "an evening hora must be found in the night block"


def test_the_straddling_hora_runs_to_midnight():
    spans = _spans()
    straddler = next(k for k, (s, e) in enumerate(spans) if e < s)
    start = spans[straddler][0]
    assert running_hora_index(spans, start) == straddler
    assert running_hora_index(spans, 1439) == straddler     # 23:59


def test_claims_nothing_in_the_small_hours():
    """After midnight the remaining horas fall on the NEXT calendar day. A caller
    asking at 01:30 is inside the PREVIOUS date's night block, which this list
    doesn't hold — so the answer is None, not a hora from the wrong night flagged
    a day early. That misfire is what a naive end<start fix would introduce."""
    spans = _spans()
    for minute in (0, 30, 90, 5 * 60):
        assert running_hora_index(spans, minute) is None, f"claimed a hora at {minute}min"


def test_at_most_one_hora_is_ever_current():
    spans = _spans()
    for minute in range(1440):
        i = running_hora_index(spans, minute)
        if i is not None:
            s, e = spans[i]
            assert (s <= minute < e) if e > s else (minute >= s), \
                f"minute {minute} flagged hora {i} = {spans[i]}"


def test_no_clock_means_no_claim():
    assert running_hora_index(_spans(), None) is None


def test_survives_unparseable_spans():
    assert running_hora_index([(None, None), (600, 660)], 620) == 1
