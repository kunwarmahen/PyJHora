#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# Copyright (C) Open Astro Technologies, USA.
# Modified by Sundar Sundaresan, USA. carnaticmusicguru2015@comcast.net
# Downloaded from https://github.com/naturalstupid/PyJHora

# This file is part of the "PyJHora" Python library
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
Drig Dhasa (Parāśari) — JHora v8.0 parity-first (DRIG-local overrides only)

Supports:
  - PVR_PAPER
  - PVR_BOOK (2 cycles: cycle2 = 12 - cycle1)

JHora Drig UI settings supported (DRIG only):
  1) Force Scorpio/Aquarius dasha owners (default JHora):
       Scorpio -> Ketu
       Aquarius -> Saturn

  2) Force "stronger of opposite pairs" (6 pairs), with exceptions:
       Ar-Li -> Li         (No exception)
       Ta-Sc -> Sc         (No exception)
       Ge-Sg -> Sg         (No exception)
       Cn-Cp -> Cn         (No exception)
       Le-Aq -> Le         (No exception)
       Vi-Pi -> Pi         (Ketu Exception)

"Ketu Exception" meaning (from PVR Narayana Dasa chapter):
  If Ketu occupies the DASA SEED, reverse the basic direction of progression.

NOTE:
  - const.HOUSE_7 must be 6 (0-based sign indexing).
"""

from typing import List, Tuple, Sequence, Optional, Union, Dict

from jhora import const, utils
from jhora.horoscope.chart import house, charts
from jhora.horoscope.dhasa.raasi import narayana
from jhora.panchanga import drik

_DHASA_OWNER_OVERRIDES = {
  "owners": {
     const.SCORPIO: const.KETU_ID,
     const.AQUARIUS: const.SATURN_ID
  },
  "stronger_pairs": {
     (const.ARIES, const.LIBRA): {"stronger": const.LIBRA, "exception": "NONE"},
     (const.TAURUS, const.SCORPIO): {"stronger": const.SCORPIO, "exception": "NONE"},
     (const.GEMINI, const.SAGITTARIUS): {"stronger": const.SAGITTARIUS, "exception": "NONE"},
     (const.CANCER, const.CAPRICORN): {"stronger": const.CANCER, "exception": "NONE"},
     (const.LEO, const.AQUARIUS): {"stronger": const.LEO, "exception": "NONE"},   # <-- your Aq/Le choice
     (const.VIRGO, const.PISCES): {"stronger": const.PISCES, "exception": "KETU"}, # only if you want
  }
}

_DAYS_IN_YEAR = float(const.sidereal_year)
_ROUND_NDIGITS = int(getattr(const, "DHASA_DURATION_ROUNDING_TO", 2))


# ---------------- small helpers ----------------
def _mod12(x: int) -> int:
    return x % 12

def _pp_upto_ketu(jd: float, place, dcf: int, chart_method: int = 1, **kwargs):
    pp = charts.divisional_chart(jd, place, divisional_chart_factor=dcf, chart_method=chart_method, **kwargs)
    return pp[:const._pp_count_upto_ketu]

def _p_to_h(pp):
    return utils.get_planet_house_dictionary_from_planet_positions(pp)

def _lagna_sign(pp) -> int:
    pth = _p_to_h(pp)
    if 'L' in pth:
        return int(pth['L']) % 12
    asc_sym = getattr(const, "_ascendant_symbol", "L")
    if asc_sym in pth:
        return int(pth[asc_sym]) % 12
    raise ValueError("Lagna not found (expected key 'L').")

def _jd_to_tuple(jd_val: float):
    return utils.jd_to_gregorian(jd_val)

def _tuple_to_jd(t):
    y, m, d, fh = t
    return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

def _append_row(rows, lords, start_jd, dur_years, round_duration: bool):
    start_t = _jd_to_tuple(start_jd)
    d = round(float(dur_years), _ROUND_NDIGITS) if round_duration else float(dur_years)
    rows.append((tuple(int(x) % 12 for x in lords), start_t, float(d)))

def _dist_forward(a: int, b: int) -> int:
    d = (b - a) % 12
    return 12 if d == 0 else d

def _dist_backward(a: int, b: int) -> int:
    d = (a - b) % 12
    return 12 if d == 0 else d

def _is_odd_sign(s: int) -> bool:
    return s in const.odd_signs
def _is_movable(s: int) -> bool:
    return s in const.movable_signs
def _is_fixed(s: int) -> bool:
    return s in const.fixed_signs
def _is_dual(s: int) -> bool:
    return s in const.dual_signs


# ---------------- global override helpers ----------------
def _get_pair_rule(a: int, b: int):
    rules = utils.get_dhasa_stronger_pair_rules()
    key = (min(a % 12, b % 12), max(a % 12, b % 12))
    return rules.get(key)

def _stronger_for_dhasa(pp, a: int, b: int) -> int:
    """
    Returns stronger sign for dhasa decisions using global overrides if present.
    If no override exists for the pair, fall back to house.stronger_rasi_from_planet_positions.
    """
    a, b = int(a) % 12, int(b) % 12
    rule = _get_pair_rule(a, b)
    if rule and "stronger" in rule:
        return int(rule["stronger"]) % 12
    return int(house.stronger_rasi_from_planet_positions(pp, a, b)) % 12

def _apply_pair_exception_direction(pp, a: int, b: int, seed: int, direction: int) -> int:
    """
    Apply per-pair exception flags to direction, using global rules.
    Supported exceptions: NONE, KETU, SATURN, SATURN_KETU.
    Semantics:
      - SATURN: if Saturn is in seed => force forward (+1)
      - KETU:   if Ketu is in seed   => reverse direction
    """
    a, b = int(a) % 12, int(b) % 12
    seed = int(seed) % 12
    rule = _get_pair_rule(a, b)
    if not rule:
        return direction
    ex = str(rule.get("exception", "NONE")).upper()

    pth = _p_to_h(pp)
    sat = pth.get(const.SATURN_ID, -999)
    ket = pth.get(const.KETU_ID, -999)

    if ex in ("SATURN", "SATURN_KETU"):
        if int(sat) == seed:
            direction = 1
    if ex in ("KETU", "SATURN_KETU"):
        if int(ket) == seed:
            direction *= -1
    return direction


# ---------------- MD sequence ----------------
def _md_sequence(lagna: int, method: int, chart, pp):
    seq = []
    for offset in (const.HOUSE_9, const.HOUSE_10, const.HOUSE_11):
        anchor = _mod12(lagna + offset)
        seq.append(anchor)

        if method == const.DRIG_TYPE.PVR_BOOK:
            even_footed = anchor in const.even_footed_signs
            aspects = list(house.aspected_kendras_of_raasi(anchor, even_footed) or [])
            uniq = []
            for x in aspects:
                x = int(x) % 12
                if x not in uniq:
                    uniq.append(x)
            if len(uniq) != 3:
                raise ValueError(f"BOOK: expected 3 aspected kendras for anchor={anchor}, got {uniq}")
            seq.extend(uniq)
        else:
            cand = list(house.raasi_drishti_of_the_raasi(chart, anchor) or [])
            uniq = []
            for x in cand:
                x = int(x) % 12
                if x not in uniq:
                    uniq.append(x)
            if len(uniq) != 3:
                raise ValueError(f"PAPER: expected 3 rasi-drishti signs for anchor={anchor}, got {uniq}")

            zodiacal = (_is_fixed(anchor) or (_is_dual(anchor) and _is_odd_sign(anchor)))
            dist = (lambda t: _dist_forward(anchor, t)) if zodiacal else (lambda t: _dist_backward(anchor, t))
            uniq.sort(key=lambda t: dist(t))

            # tie-break: same lord as anchor
            anchor_lord = house.house_owner_from_planet_positions(pp, anchor, check_during_dhasa=True)
            out = []
            i = 0
            while i < len(uniq):
                d0 = dist(uniq[i])
                group = [uniq[i]]
                j = i + 1
                while j < len(uniq) and dist(uniq[j]) == d0:
                    group.append(uniq[j])
                    j += 1
                if len(group) == 1:
                    out.extend(group)
                else:
                    pref = None
                    for g in group:
                        if house.house_owner_from_planet_positions(pp, g, check_during_dhasa=True) == anchor_lord:
                            pref = g
                            break
                    if pref is None:
                        out.extend(group)
                    else:
                        out.append(pref)
                        out.extend([g for g in group if g != pref])
                i = j

            seq.extend(out)

    if len(seq) != 12:
        raise ValueError(f"Invalid MD sequence length {len(seq)}: {seq}")
    return seq


# ---------------- durations ----------------
def _md_years_paper(sign: int) -> float:
    if _is_movable(sign): return 7.0
    if _is_fixed(sign):   return 8.0
    return 9.0

def _md_years_book_cycle1(pp, sign: int) -> float:
    return float(narayana._dhasa_duration(pp, sign))

def _book_cycle_years(cycle_idx: int, cycle1: float) -> float:
    if cycle_idx == 1:
        return float(cycle1)
    y2 = 12.0 - float(cycle1)
    return 0.0 if y2 <= 0 else float(y2)


# ---------------- child order (Antardasa and deeper) ----------------
def _paper_children_order(parent_sign: int, pp) -> List[int]:
    opp = _mod12(parent_sign + const.HOUSE_7)  # HOUSE_7 should be 6
    seed = _stronger_for_dhasa(pp, parent_sign, opp)

    direction = 1 if _is_odd_sign(parent_sign) else -1
    direction = _apply_pair_exception_direction(pp, parent_sign, opp, seed, direction)

    if _is_movable(parent_sign):
        return [_mod12(seed + direction * i) for i in range(12)]

    if _is_fixed(parent_sign):
        step = 5 * direction
        return [_mod12(seed + step * i) for i in range(12)]

    # dual
    step3 = 3 * direction
    if direction == 1:
        bases = [seed, _mod12(seed + const.HOUSE_5), _mod12(seed + const.HOUSE_9)]
    else:
        bases = [seed, _mod12(seed + const.HOUSE_9), _mod12(seed + const.HOUSE_5)]

    seq = []
    for base in bases:
        for i in range(4):
            seq.append(_mod12(base + step3 * i))
    return seq


def _book_children_order(parent_sign: int, pp) -> List[int]:
    """
    DRIG-local Narayana antardasa logic so that global stronger-pair overrides affect it.
    Uses the same shape as narayana._narayana_antardhasa but seed comparison uses _stronger_for_dhasa.
    """
    dhasa_rasi = int(parent_sign) % 12

    # lord of maha sign
    lord_of_dhasa = house.house_owner_from_planet_positions(pp, dhasa_rasi, check_during_dhasa=True)
    house_of_lord = pp[int(lord_of_dhasa) + 1][1][0]

    # lord of 7th from maha sign
    lord_of_7th = house.house_owner_from_planet_positions(pp, (dhasa_rasi + const.HOUSE_7) % 12, check_during_dhasa=True)
    house_of_7th_lord = pp[int(lord_of_7th) + 1][1][0]

    a = int(house_of_lord) % 12
    b = int(house_of_7th_lord) % 12

    seed = _stronger_for_dhasa(pp, a, b)

    pth = _p_to_h(pp)
    direction = 1 if seed in const.odd_signs else -1

    # Saturn in seed -> force forward
    if int(pth.get(const.SATURN_ID, -999)) == seed:
        direction = 1

    # apply pair exception (if configured for that opposite pair)
    direction = _apply_pair_exception_direction(pp, a, b, seed, direction)

    # Ketu in maha sign flips antardasa direction (Narayana rule)
    if int(pth.get(const.KETU_ID, -999)) == dhasa_rasi:
        direction *= -1

    return [(seed + direction * i) % 12 for i in range(12)]


def _children_order(parent_sign: int, pp, method: int) -> List[int]:
    if method == const.DRIG_TYPE.PVR_BOOK:
        return _book_children_order(parent_sign, pp)
    return _paper_children_order(parent_sign, pp)


# ---------------- recursion ----------------
def _expand_equal_12(rows, target_depth, current_depth, lords_prefix, parent_sign, start_jd, dur_years,
                     pp, method, round_duration):
    if current_depth == target_depth:
        _append_row(rows, lords_prefix, start_jd, dur_years, round_duration)
        return

    order = _children_order(parent_sign, pp, method)
    child_years = float(dur_years) / 12.0
    jd_ptr = float(start_jd)

    for child_sign in order:
        child_sign = int(child_sign) % 12
        _expand_equal_12(rows, target_depth, current_depth + 1,
                         lords_prefix + [child_sign],
                         child_sign, jd_ptr, child_years,
                         pp, method, round_duration)
        jd_ptr += child_years * _DAYS_IN_YEAR


# ============================================================
# PUBLIC 1: get_dhasa_antardhasa
# ============================================================
def get_dhasa_antardhasa(jd: float,
                         place,
                         dhasa_method=const.DRIG_TYPE.PVR_PAPER,
                         divisional_chart_factor: int = 1,
                         chart_method: int = 1,
                         **kwargs) -> List[Tuple]:
    dhasa_level_index = int(kwargs.pop("dhasa_level_index", int(const.MAHA_DHASA_DEPTH.ANTARA)))
    round_duration = bool(kwargs.pop("round_duration", True))
    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6")

    pp = _pp_upto_ketu(jd, place, divisional_chart_factor, chart_method=chart_method, **kwargs)
    chart = utils.get_house_planet_list_from_planet_positions(pp)
    lagna = _lagna_sign(pp)
    md_seq = _md_sequence(lagna, dhasa_method, chart, pp)

    rows: List[Tuple] = []
    jd_ptr = float(jd)

    if dhasa_method == const.DRIG_TYPE.PVR_BOOK:
        for cycle in (1, 2):
            for md_sign in md_seq:
                c1 = _md_years_book_cycle1(pp, md_sign)
                md_years = _book_cycle_years(cycle, c1)
                if md_years <= 0:
                    continue

                if dhasa_level_index == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
                    _append_row(rows, [md_sign], jd_ptr, md_years, round_duration)
                else:
                    _expand_equal_12(rows, dhasa_level_index, 1, [md_sign], md_sign, jd_ptr, md_years,
                                     pp, dhasa_method, round_duration)

                jd_ptr += md_years * _DAYS_IN_YEAR
    else:
        for md_sign in md_seq:
            md_years = _md_years_paper(md_sign)

            if dhasa_level_index == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
                _append_row(rows, [md_sign], jd_ptr, md_years, round_duration)
            else:
                _expand_equal_12(rows, dhasa_level_index, 1, [md_sign], md_sign, jd_ptr, md_years,
                                 pp, dhasa_method, round_duration)

            jd_ptr += md_years * _DAYS_IN_YEAR

    return rows


# ============================================================
# PUBLIC 2: drig_immediate_children
# ============================================================
def drig_immediate_children(
    parent_lords: Union[int, Sequence[int]],
    parent_start: Tuple[int, int, int, float],
    parent_duration: Optional[float] = None,
    parent_end: Optional[Tuple[int, int, int, float]] = None,
    *,
    jd_at_dob: float,
    place,
    dhasa_method=const.DRIG_TYPE.PVR_PAPER,
    divisional_chart_factor: int = 1,
    chart_method: int = 1,
    **kwargs
):
    if isinstance(parent_lords, int):
        path = (int(parent_lords) % 12,)
    else:
        path = tuple(int(x) % 12 for x in parent_lords)

    parent_sign = int(path[-1]) % 12

    start_jd = _tuple_to_jd(parent_start)
    if (parent_duration is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration or parent_end.")
    if parent_end is None:
        end_jd = start_jd + float(parent_duration) * _DAYS_IN_YEAR
    else:
        end_jd = _tuple_to_jd(parent_end)

    if end_jd <= start_jd:
        return []

    pp_birth = _pp_upto_ketu(jd_at_dob, place, divisional_chart_factor, chart_method=chart_method, **kwargs)
    order = _children_order(parent_sign, pp_birth, dhasa_method)

    parent_years = (end_jd - start_jd) / _DAYS_IN_YEAR
    child_years = parent_years / 12.0

    out = []
    cursor = start_jd
    for i, child_sign in enumerate(order):
        child_end = end_jd if i == 11 else cursor + child_years * _DAYS_IN_YEAR
        out.append([path + (int(child_sign) % 12,), _jd_to_tuple(cursor), _jd_to_tuple(child_end)])
        cursor = child_end
        if cursor >= end_jd:
            break

    if out:
        out[-1][2] = _jd_to_tuple(end_jd)
    return out


# ============================================================
# PUBLIC 3: get_running_dhasa_for_given_date
# ============================================================
def get_running_dhasa_for_given_date(
    current_jd: float,
    jd_at_dob: float,
    place,
    dhasa_method=const.DRIG_TYPE.PVR_PAPER,
    dhasa_level_index: int = const.MAHA_DHASA_DEPTH.DEHA,
    *,
    divisional_chart_factor: int = 1,
    chart_method: int = 1,
    **kwargs
):
    target_depth = max(1, min(6, int(dhasa_level_index)))

    # MD-only schedule
    md_rows = get_dhasa_antardhasa(
        jd=jd_at_dob,
        place=place,
        dhasa_method=dhasa_method,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        dhasa_level_index=int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY),
        round_duration=False,
        **kwargs
    )
    if not md_rows:
        return []

    spans = []
    for lords, start_t, dur in md_rows:
        sjd = _tuple_to_jd(start_t)
        ejd = sjd + float(dur) * _DAYS_IN_YEAR
        spans.append((sjd, ejd, tuple(lords)))
    spans.sort(key=lambda x: x[0])

    cur = float(current_jd)
    running = None
    for sjd, ejd, lords in spans:
        if sjd <= cur < ejd:
            running = [lords, _jd_to_tuple(sjd), _jd_to_tuple(ejd)]
            break
    if running is None:
        sjd, ejd, lords = spans[-1]
        running = [lords, _jd_to_tuple(sjd), _jd_to_tuple(ejd)]

    ladder = [running]
    if target_depth == 1:
        return ladder

    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running
        children = drig_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            dhasa_method=dhasa_method,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
            **kwargs
        )
        if not children:
            break

        found = None
        for lords, st, en in children:
            sjd = _tuple_to_jd(st)
            ejd = _tuple_to_jd(en)
            if sjd <= cur < ejd:
                found = (tuple(lords), st, en)
                break
        if found is None:
            lords, st, en = children[-1]
            found = (tuple(lords), st, en)

        running = [found[0], found[1], found[2]]
        ladder.append(running)

    return ladder

if __name__ == "__main__":
    """
    dob = drik.Date(1996,12,7)
    tob = (10,34,0)
    place = drik.Place('Chennai,IN', 13.0389, 80.2619, +5.5)
    jd = utils.julian_day_number(dob, tob)
    
    pp1 = charts.divisional_chart(jd, place, divisional_chart_factor=1, chart_method=1)[:const._pp_count_upto_ketu]
    pp9 = charts.divisional_chart(jd, place, divisional_chart_factor=9, chart_method=1)[:const._pp_count_upto_ketu]
    
    VI = const.VIRGO   # should be 5
    PI = const.PISCES  # should be 11
    
    print("D1 stronger(Vi,Pi) =", house.stronger_rasi_from_planet_positions(pp1, VI, PI))
    print("D9 stronger(Vi,Pi) =", house.stronger_rasi_from_planet_positions(pp9, VI, PI))
    
    print("D9 stronger(Aq,Le) =", house.stronger_rasi_from_planet_positions(pp9, const.AQUARIUS, const.LEO))
    print("D9 stronger(Sc,Ta) =", house.stronger_rasi_from_planet_positions(pp9, const.SCORPIO, const.TAURUS))
    chart9 = utils.get_house_planet_list_from_planet_positions(pp9)
    
    print("D9 Leo occupants:", chart9[const.LEO])
    print("D9 Aquarius occupants:", chart9[const.AQUARIUS])    
    exit()
    """
    utils.set_language('en')
    utils.set_owner_overrides_for_dhasa(_DHASA_OWNER_OVERRIDES)
    dob = drik.Date(1996,12,7)
    tob = (10,34,0)
    place = drik.Place('Chennai,IN', 13.0389, 80.2619, +5.5)
    jd = utils.julian_day_number(dob, tob)
    def print_md_ad(dcf, method, chart_method=1):
        rows = get_dhasa_antardhasa(
            jd=jd, place=place,
            dhasa_method=method,
            divisional_chart_factor=dcf,
            chart_method=chart_method,
            dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,  # MD+AD
            round_duration=False
        )
    
        # group by MD
        cur_md = None
        md_years = None
        ad_list = []
        for lords, start_t, dur in rows:
            md = lords[0]
            ad = lords[1]
            if cur_md is None:
                cur_md = md
                ad_list = [ad]
                md_years = dur * 12.0  # because rows are equal 1/12 for PAPER and also for BOOK expansion
            elif md == cur_md:
                ad_list.append(ad)
            else:
                print(utils.RAASI_SHORT_LIST[cur_md], f"({md_years:.0f})", ",".join(utils.RAASI_SHORT_LIST[x] for x in ad_list))
                cur_md = md
                ad_list = [ad]
                md_years = dur * 12.0
    
        if cur_md is not None:
            print(utils.RAASI_SHORT_LIST[cur_md], f"({md_years:.0f})", ",".join(utils.RAASI_SHORT_LIST[x] for x in ad_list))
    
    print("PVR_PAPER D1")
    print_md_ad(1, const.DRIG_TYPE.PVR_PAPER, chart_method=1)
    
    print("PVR_PAPER D9")
    print_md_ad(9, const.DRIG_TYPE.PVR_PAPER, chart_method=1)
    
    print("PVR_BOOK D1")
    print_md_ad(1, const.DRIG_TYPE.PVR_BOOK, chart_method=1)
    
    print("PVR_BOOK D9")
    print_md_ad(9, const.DRIG_TYPE.PVR_BOOK, chart_method=1)
    exit()    
    utils.set_language('en')
    dob = drik.Date(1996,12,7); tob = (10,34,0)
    place = drik.Place('Chennai,IN', 13.0389, 80.2619, +5.5)    
    jd_at_dob  = utils.julian_day_number(dob, tob)
    from datetime import datetime
    current_date_str,current_time_str = datetime.now().strftime('%Y,%m,%d;%H:%M:%S').split(';')
    y,m,d = map(int,current_date_str.split(','))
    hh,mm,ss = map(int,current_time_str.split(':')); fh = hh+mm/60+ss/3600
    print(utils.date_time_tuple_to_date_time_string(y, m, d, fh))
    current_jd = utils.julian_day_number(drik.Date(y,m,d),(hh,mm,ss))
    import time
    _dhasa_method=const.DRIG_TYPE.PVR_BOOK; dcf = 9; chart_method = 1
    sc_owner = const.KETU_ID; aq_owner = const.SATURN_ID
    print("Drig Dhasa Method","PVR_BOOK" if _dhasa_method==const.DRIG_TYPE.PVR_BOOK else "PVR_PAPER","div=",dcf,"cm=",chart_method)
    start_time = time.time()
    DLI = const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY
    rd1 = get_running_dhasa_for_given_date(current_jd, jd_at_dob, place,
                                                            dhasa_level_index=DLI,
                                                            dhasa_method=_dhasa_method,
                                                            divisional_chart_factor=dcf,
                                                            chart_method=chart_method,
                                                            scorpio_owner_for_dhasa_calculations=sc_owner,
                                                            aquarius_owner_for_dhasa_calculations=aq_owner)
    for row in rd1:
        lords,ds,de = row
        print([utils.RAASI_LIST[lord] for lord in lords],ds,de)
    print('new method elapsed time',time.time()-start_time)
    start_time = time.time()
    _dhasa_cycles = 1 if _dhasa_method==1 else 2
    ad = get_dhasa_antardhasa(jd_at_dob, place, dhasa_level_index=DLI,dhasa_method=_dhasa_method,
                                                            divisional_chart_factor=dcf,
                                                            chart_method=chart_method,
                                                            scorpio_owner_for_dhasa_calculations=sc_owner,
                                                            aquarius_owner_for_dhasa_calculations=aq_owner)
    #"""
    if DLI <= const.MAHA_DHASA_DEPTH.ANTARA:
        for row in ad:
            lords,ds,dur = row
            print([utils.RAASI_LIST[lord] for lord in lords],ds,dur)
        exit()
    #"""
    rd2 = utils.get_running_dhasa_at_all_levels_for_given_date(current_jd, ad,DLI,
                                                               extract_running_period_for_all_levels=True,
                                                               dhasa_cycle_count=_dhasa_cycles)
    for row in rd2:
        lords,ds,de = row
        print([utils.RAASI_LIST[lord] for lord in lords],ds,de)
    print('old method elapsed time',time.time()-start_time)
    exit()
    from jhora.tests import pvr_tests
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.chapter_21_tests()
