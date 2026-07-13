#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""**Varsha Tithi Ashtottari** — the compressed annual dasha Jagannatha Hora pairs
with the Tithi Pravesha chart ("Tithi Ashtottari Dasa of Janma tithi in D-1").

PyJHora has no annual/compressed Tithi Ashtottari (`dhasa/annual/` ships only
Mudda and Patyayini), so it is written here. It is *not* the 108-year life dasha
in `dhasa/graha/tithi_ashtottari.py` scoped to a year — that is a different
construct with different lords and spans.

**Everything is Moon−Sun ELONGATION. Nothing is measured in days.** That is the
whole trick, and why every day-proportional model of this dasha fails: tithis run
0.79–1.06 days, so equal *angles* give unequal *days*, and the resulting ±1-day
"noise" is structural, not rounding.

Let `E(t)` be the sidereal Moon minus the sidereal Sun, mod 360 (it increases
monotonically at 10.8–14.4°/day, ~13.2° on average; a tithi is 12° of it).

  1. **Cycle.** `C = N × 360°`, N = the number of lunar months in the chart's year
     (ordinary 12 → 4320°; adhika-masa 13 → 4680°).
  2. **Lord + balance from the chart's own elongation** — the classic "dasha from
     the chart" rule, in elongation space instead of nakshatra space. At the chart
     instant `T` (for a TP chart, the pravesha moment):
       `tithi = floor(E(T)/12) + 1` → `lord`, and the elapsed fraction of that
       lord's period is `(E(T) mod 12) / 12` — *degrees* within the tithi, **not**
       time. The period therefore began at `advance(T, −elapsed × lord_span°)`.
  3. **Walk forward.** Each lord spans `allotment/108 × C` degrees.
  4. **Sub-levels subdivide the parent's DEGREE span**, recursively, six levels
     deep (Maha → Antara → Pratyantara → Sookshma → Prana → Deha):
     `child° = allotment/108 × parent°`, each child sequence starting on the lord
     *after* its parent.
  5. **Re-anchored per chart.** Each TP year's table is computed from that year's
     pravesha instant; it is not one continuous cycle running from birth.

Verified against two of the owner's Jagannatha Hora charts (1976-06-04 05:45:02,
Aligarh): TP-2026 (adhika, C = 4680°) and TP-2027 (ordinary, C = 4320°) reproduce
every maha boundary, and the sub-levels below them, to within ~90 seconds.

⚠️ Do **not** reach for the engine's Tithi Ashtottari functions to build this.
`tithi_ashtottari_immediate_children` subdivides proportionally in *days*, which
puts the first antara ~5 hours off; `_ashtottari_dasha_start_date` takes the
*time* fraction of the tithi, not the degree fraction. Only its **tables** are
used here (tithi → lord + allotment, and the lord order).
"""
from typing import Dict, List, Optional, Tuple
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from jhora import const, utils
from jhora.panchanga import drik
from jhora.horoscope.dhasa.graha import tithi_ashtottari as _ta

# {lord: allotment}, summing to 108. Sourced from the engine's own table so the
# tithi→lord mapping and the allotments can never drift apart.
ALLOTMENT: Dict[int, int] = {k: v[1] for k, v in _ta.ashtottari_adhipathi_dict.items()}

# Ashtottari lord order: Sun → Moon → Mars → Mercury → Saturn → Jupiter → Rahu → Venus.
ORDER: List[int] = list(_ta.ashtottari_adhipathi_list)

CYCLE = 108  # the "108" in Ashtottari

# Maha → Antara → Pratyantara → Sookshma → Prana → Deha.
LEVEL_NAMES = ["Maha", "Antara", "Pratyantara", "Sookshma", "Prana", "Deha"]
MAX_LEVEL = len(LEVEL_NAMES) - 1

# Elongation advances at 10.8–14.4°/day (Moon 11.8–15.4 minus Sun ~1.0), never
# backwards. The bounds make the unwrapping below exact; the mean seeds the solver.
_RATE_MIN = 10.8
_RATE_MAX = 14.4
_RATE_MEAN = 13.1764

# Below this, an advance is a no-op — 1e-6° is ~0.007 seconds of time.
_DEG_EPS = 1e-6


def elongation(jd: float, place) -> float:
    """Sidereal Moon − sidereal Sun, mod 360. Ayanamsa-independent (it cancels in
    the difference), so this is stable across ayanamsa settings. `jd` is a local
    Julian day, as everywhere else in this codebase — drik wants UT."""
    u = jd - place.timezone / 24.0
    return (drik.sidereal_longitude(u, const._MOON)
            - drik.sidereal_longitude(u, const._SUN)) % 360.0


def _travelled(jd: float, jd0: float, e0: float, sign: float, place) -> float:
    """Elongation travelled from `jd0` to `jd`, un-wrapped past 360° — a continuous,
    strictly increasing distance rather than an angle mod 360.

    `E` is only known mod 360, so the number of whole turns has to be recovered.
    Elapsed time `t` bounds the true distance to `[10.8t, 14.4t]`, a window 3.6t
    degrees wide; while that window stays under 360° (t < 100 days) only one
    candidate can fall inside it, so the turn count is unambiguous. Callers keep
    each leg under half a turn (~14 days), well inside that limit."""
    t = (jd - jd0) * sign
    if t <= 0:
        return 0.0
    r = ((elongation(jd, place) - e0) * sign) % 360.0
    turns = round((_RATE_MEAN * t - r) / 360.0)
    return r + 360.0 * max(0, turns)


def advance(jd0: float, deg: float, place) -> float:
    """The instant at which the elongation has advanced exactly `deg` degrees from
    `jd0` (negative runs it backwards). This is the primitive every boundary in the
    dasha is built from.

    Solved by Newton iteration on the un-wrapped distance, seeded with the mean
    rate. The rate only varies ±20% about the mean, so using the mean as a constant
    derivative still contracts the error by ~5× per step and converges in a handful
    of ephemeris calls — no stepping-and-bisecting needed."""
    if abs(deg) < _DEG_EPS:
        return jd0
    sign = 1.0 if deg > 0 else -1.0
    remaining = abs(deg)
    jd = jd0
    # Walk in legs of at most a half-turn, so _unwrapped's turn count stays exact.
    while remaining > _DEG_EPS:
        leg = min(remaining, 180.0)
        jd = _solve_leg(jd, leg, sign, place)
        remaining -= leg
    return jd


def _solve_leg(jd0: float, leg_deg: float, sign: float, place) -> float:
    e0 = elongation(jd0, place)
    jd = jd0 + sign * leg_deg / _RATE_MEAN
    for _ in range(40):
        f = _travelled(jd, jd0, e0, sign, place) - leg_deg
        if abs(f) < _DEG_EPS:
            break
        jd -= sign * f / _RATE_MEAN
    return jd


def refine_pravesha(seed_jd: float, target_elongation: float, place) -> Optional[float]:
    """The instant nearest `seed_jd` at which the elongation *equals* the birth
    elongation — i.e. the true tithi return, exact in degrees.

    The engine's `vratha.tithi_pravesha` locates the pravesha by interpolating
    **linearly in time** between the tithi's start and end (`t_time = s_end −
    t_frac × t_len`), which lands ~45–50 minutes early. That is invisible in a date
    but not in a dasha: the balance rule winds the elongation back by up to a full
    maha span (~910°), which magnifies the error ~50× into a **2.5-day** shift of
    every period. So the pravesha instant has to be solved in degrees, not minutes."""
    def f(jd: float) -> float:
        return ((elongation(jd, place) - target_elongation + 180.0) % 360.0) - 180.0

    lo, hi = seed_jd - 0.6, seed_jd + 0.6
    f_lo, f_hi = f(lo), f(hi)
    if f_lo * f_hi > 0:
        return None  # no crossing in ±14h of the engine's date — leave it alone
    for _ in range(60):
        mid = (lo + hi) / 2.0
        f_mid = f(mid)
        if f_lo * f_mid <= 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
        if hi - lo < 1e-8:  # ~1 millisecond
            break
    return (lo + hi) / 2.0


def next_lord(lord: int) -> int:
    return ORDER[(ORDER.index(lord) + 1) % len(ORDER)]


def cycle_degrees(start_jd: float, end_jd: float, place) -> float:
    """`C` — the elongation the pravesha window sweeps, which is the cycle the whole
    108-unit dasha is compressed into.

    Every rung of the lunar ladder is a clean fraction or multiple of a turn,
    because each is *defined* by an elongation boundary — so this is exact, not an
    estimate (measured, for the owner's chart):

        tithi     0.85 d  →    12°   (one tithi)
        paksha   14.41 d  →   180°   (half a turn)
        month    29.45 d  →   360°   (one turn)
        annual  384.03 d  →  4680°   (13 turns — an adhika-masa year)

    Deriving `C` this way rather than rounding days into lunar months (`round(span /
    29.53)`) matters twice: it makes the annual case exact instead of heuristic —
    settling how many months the year holds, 12 or 13, by counting turns rather than
    guessing — and it is the *only* form that works below a month. Rounding a
    fortnight's 14.4 days gives 1 lunar month → 360°, twice the true 180°, and the
    dasha would silently run at half speed.

    Stepped coarsely and summed mod 360: at 5 days a step the elongation advances at
    most ~72°, far short of a wrap, so no turn can be missed.

    Rounded to a micro-degree (~6 ms of time). The window's own endpoints come from
    the engine's boundary search, which carries a ~1e-8° residual — so a tithi
    measures 11.99999997° rather than a clean 12. Rounding keeps the reported cycle
    honest-looking and, more to the point, keeps it consistent with the period spans
    derived from it."""
    total = 0.0
    prev_jd, prev_e = start_jd, elongation(start_jd, place)
    while prev_jd < end_jd:
        jd = min(prev_jd + 5.0, end_jd)
        e = elongation(jd, place)
        total += (e - prev_e) % 360.0
        prev_jd, prev_e = jd, e
    return round(total, 6)


def lunar_months_in(cycle_deg: float) -> int:
    """How many lunar months the cycle spans — 12 or 13 for a pravesha year. Purely
    for display; the maths uses the degrees."""
    return int(round(cycle_deg / 360.0))


def seed_period(chart_jd: float, place, cycle_deg: float) -> Tuple[int, float, float]:
    """The running lord at the chart instant, when its period began, and its span
    — the "dasha from the chart" rule, in elongation space.

    Returns `(lord, start_jd, span_deg)`."""
    e = elongation(chart_jd, place)
    tithi_index = int(e // 12) + 1
    lord, _allot = _ta._ashtottari_adhipathi(tithi_index)
    span_deg = ALLOTMENT[lord] / CYCLE * cycle_deg
    elapsed = (e % 12) / 12.0            # degrees into the tithi, NOT time
    start_jd = advance(chart_jd, -elapsed * span_deg, place)
    return lord, start_jd, span_deg


def periods(start_jd: float, start_lord: int, parent_deg: float, place,
            count: int = 8) -> List[Dict]:
    """One level of the dasha: `count` consecutive periods from `start_jd`,
    subdividing `parent_deg` degrees among the eight lords by allotment.

    At the top level `parent_deg` is the whole cycle `C` and `start_lord` is the
    chart's running lord. Below it, `parent_deg` is the parent period's degree span
    and `start_lord` is the lord *after* the parent (Ashtottari's antardasa rule)."""
    out = []
    jd, lord = start_jd, start_lord
    for _ in range(count):
        span_deg = ALLOTMENT[lord] / CYCLE * parent_deg
        end_jd = advance(jd, span_deg, place)
        out.append({
            "lord": lord,
            "start_jd": jd,
            "end_jd": end_jd,
            "span_deg": span_deg,
            "span_days": end_jd - jd,
        })
        jd, lord = end_jd, next_lord(lord)
    return out


def maha_periods(chart_jd: float, place, cycle_deg: float) -> List[Dict]:
    """The maha dasas of a pravesha chart: the lord already running when the window
    opens, then a full cycle of eight.

    Nine rows, not eight — the first is the *balance* of a period that began before
    the pravesha instant (JHora shows it too), so a full cycle still fits after it."""
    lord, start_jd, _span = seed_period(chart_jd, place, cycle_deg)
    return periods(start_jd, lord, cycle_deg, place, count=9)


def children(parent_start_jd: float, parent_lord: int, parent_deg: float,
             place) -> List[Dict]:
    """The eight sub-periods of one period — the lazy drill-down. Six levels deep is
    8⁶ ≈ 262k rows, so a level is only ever computed when it is opened."""
    return periods(parent_start_jd, next_lord(parent_lord), parent_deg, place, count=8)
