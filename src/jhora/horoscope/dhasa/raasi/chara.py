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
from jhora import const, utils
from jhora.horoscope.chart import charts, house
from jhora.panchanga import drik

"""
    1=> KN Rao method
    2=> Parasara/PVN Rao Method - from https://vedicastrologer.org/articles/pp_chara_dasa.pdf
    3=> Raghava Bhatta method from https://sutramritam.blogspot.com/2009/08/chara-dasa-raghava-bhatta-nrisimha-suri.html
"""
_dhasa_cycles = 2
one_year_days = const.sidereal_year

# ─────────────────────────────────────────────────────────────────────────────
# NEW: Iranganti / RB–NS sets & helpers (used by Method=3,4) and MindSutra (5)
# Sources: Iranganti's booklet (Phalita Daśās → Chara Daśā); RB–NS note (Shanmukha)
# ─────────────────────────────────────────────────────────────────────────────

OJAPADA_SIGNS = {
    const.ARIES, const.TAURUS, const.GEMINI, const.LIBRA, const.SCORPIO, const.SAGITTARIUS
}
SAMAPADA_SIGNS = {
    const.CANCER, const.LEO, const.VIRGO, const.CAPRICORN, const.AQUARIUS, const.PISCES
}

""" This _antardhasa() is added to ONLY  support yogardha dhasa but not used here """
def _antardhasa(dhasas, method=const.CHARA_TYPE.PVN_RAO):
    _antardhasas = dhasas[1:] + [dhasas[0]] if method == 1 else dhasas
    return _antardhasas

def _lord_of(sign, planet_positions):
    # Classical sign lords in these Chara rules (Sc=Mars, Aq=Saturn; nodes not used)
    if sign == const.SCORPIO:
        return const.MARS_ID
    if sign == const.AQUARIUS:
        return const.SATURN_ID
    return const.house_owners[sign]


def _dhasa_progression_iranganti_m1_male(planet_positions):
    asc = planet_positions[0][1][0]
    ninth = (asc + const.HOUSE_9) % 12
    is_forward = ninth in OJAPADA_SIGNS
    return [(asc + (i if is_forward else -i)) % 12 for i in range(12)]


def _dhasa_duration_iranganti_m1_male(planet_positions, sign):
    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    lord = _lord_of(sign, planet_positions)
    lord_house = p_to_h[lord]
    if lord_house == sign:
        return 12
    if sign in OJAPADA_SIGNS:
        count = ((lord_house - sign) % 12) + 1
    else:
        count = ((sign - lord_house) % 12) + 1
    years = count - 1
    st = const.house_strengths_of_planets[lord][lord_house]
    if st == const._EXALTED_UCCHAM:
        years += 1
    elif st == const._DEBILITATED_NEECHAM:
        years -= 1
    if years <= 0:
        years = 12
    return years


def _dual_block(start, forward=True):
    """
    Dual trinal blocks:
      forward : [a, a+4, a-4] and anchor a := a+1  (odd parent)
      reverse : [a, a-4, a+4] and anchor a := a-1  (even parent)
    """
    out = []
    a = start % 12
    if forward:
        for _ in range(4):
            out.extend([a, (a + 4) % 12, (a - 4) % 12])
            a = (a + 1) % 12
    else:
        for _ in range(4):
            out.extend([a, (a - 4) % 12, (a + 4) % 12])
            a = (a - 1) % 12
    return out


def _padakrama_list_from_parent(parent_sign):
    """
    Rangacharya / RB–NS Antardaśā padakrama with direction set by the PARENT SIGN's parity.
      - Movable: contiguous ±1
      - Fixed  : every‑6th ±5 (0‑based)
      - Dual   : trinal blocks (forward/reverse)
    """
    P = parent_sign % 12
    odd = P in const.odd_signs

    if P in const.movable_signs:
        step = 1 if odd else -1
        return [(P + step * i) % 12 for i in range(12)]

    if P in const.fixed_signs:
        step = 5 if odd else -5
        return [(P + step * i) % 12 for i in range(12)]

    return _dual_block(P, forward=odd)


def _dhasa_progression_iranganti_m2_male(planet_positions):
    asc = planet_positions[0][1][0]
    odd = asc in const.odd_signs
    if asc in const.movable_signs:
        step = 1 if odd else -1
        return [(asc + step * i) % 12 for i in range(12)]
    if asc in const.fixed_signs:
        step = 5 if odd else -5
        return [(asc + step * i) % 12 for i in range(12)]
    return _dual_block(asc, forward=odd)


def _dhasa_duration_iranganti_m2_male(planet_positions, sign):
    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    lord = _lord_of(sign, planet_positions)
    lord_house = p_to_h[lord]
    if lord_house == sign:
        return 12
    forward = lord_house in const.odd_signs
    count = ((sign - lord_house) % 12) + 1 if forward else ((lord_house - sign) % 12) + 1
    years = count - 1
    if years <= 0:
        years = 12
    return years


def _dhasa_progression_iranganti_female(planet_positions):
    asc = planet_positions[0][1][0]
    odd = asc in const.odd_signs
    start = (asc + 3) % 12 if odd else (asc - 3) % 12
    if asc in const.movable_signs:
        step = 1 if odd else -1
        return [(start + step * i) % 12 for i in range(12)]
    if asc in const.fixed_signs:
        step = 5 if odd else -5
        return [(start + step * i) % 12 for i in range(12)]
    return _dual_block(start, forward=odd)


def _dhasa_duration_iranganti_female(planet_positions, sign):
    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    lord = _lord_of(sign, planet_positions)
    lord_house = p_to_h[lord]
    if lord_house == sign:
        return 12
    if lord_house == (sign + const.HOUSE_7) % 12:
        return 10
    forward = sign in const.odd_signs
    count = ((sign - lord_house) % 12) + 1 if forward else ((lord_house - sign) % 12) + 1
    years = count - 1
    if years <= 0:
        years = 12
    return years


# Antardaśā (Iranganti/RB–NS): parent-sign padakrama; 12 parts; equal split
def _antardhasa_iranganti(parent_sign):
    return _padakrama_list_from_parent(parent_sign)

def _antardhasa_order_knrao(parent_sign):
    """
    KN Rao Method: Generates sub-periods ending at the parent sign.
    
    Forward (+1) starting at (parent + 1) for: Ar, Le, Li, Aq, Vi, Pi
    Backward (-1) starting at (parent - 1) for: Ta, Ge, Cn, Sc, Sg, Cp
    
    Assumes 0-indexed integers: 0=Aries, 1=Taurus, ..., 11=Pisces.
    """
    # Exact signs that progress forward in KN Rao's Antardasha system
    # Aries(0), Leo(4), Virgo(5), Libra(6), Aquarius(10), Pisces(11)
    forward_signs = {0, 4, 5, 6, 10, 11}
    
    if parent_sign in forward_signs:
        # Move forward from the next sign, landing on the parent sign last
        return [(parent_sign + 1 + h) % 12 for h in range(12)]
    else:
        # Move backward from the previous sign, landing on the parent sign last
        return [(parent_sign - 1 - h) % 12 for h in range(12)]
        
def _dhasa_progression_mindsutra(planet_positions, gender):
    asc = planet_positions[0][1][0]
    odd = asc in const.odd_signs
    start = asc if gender == 0 else ((asc + 3) % 12 if odd else (asc - 3) % 12)

    seq = [start]
    seen = {start}
    trinal_master = [0, 4, 8, 1, 5, 9, 2, 6, 10, 3, 7, 11]

    def _next_dual(cur):
        k = trinal_master.index(cur)
        return trinal_master[(k + 1) % 12]

    while len(seq) < 12:
        cur = seq[-1]
        if cur in const.movable_signs:
            nxt = (cur + 1) % 12
        elif cur in const.fixed_signs:
            nxt = (cur + 5) % 12
        else:
            nxt = _next_dual(cur)
        if nxt in seen:
            i = 0
            while nxt in seen and i < 12:
                nxt = (nxt + 1) % 12
                i += 1
        seq.append(nxt)
        seen.add(nxt)

    if not odd:
        tail = seq[1:]
        tail.reverse()
        seq = [start] + tail
    return seq


def _dhasa_duration_mindsutra(planet_positions, sign):
    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    lord = _lord_of(sign, planet_positions)
    lord_house = p_to_h[lord]
    
    # Rule 4: If Lord is in the dasa sign itself -> 12 years
    if lord_house == sign:
        return 12
        
    # Rule 3: If Lord is 7th from dasa sign -> 10 years
    if lord_house == (sign + 6) % 12: # Standardized 0-indexed 7th house step
        return 10
        
    # Rule 1 & 2: Odd/Even Sign direction tracking
    forward = lord_house in const.odd_signs
    
    # Count from Lord (Paka) to Dasha sign inclusive
    count = utils.count_rasis(lord_house, sign, direction=1 if forward else -1)
    
    years = count - 1
    return years


def _antardhasa_order_mindsutra(parent_sign, planet_positions, dhasa_years):
    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    lord = _lord_of(parent_sign, planet_positions)
    paka = p_to_h[lord]
    
    forward = paka in const.odd_signs
    
    # MindSutra Modification: The number of Antardashas MUST equal dhasa_years
    order = []
    for i in range(dhasa_years):
        if forward:
            next_sign = (paka + i) % 12
        else:
            next_sign = (paka - i) % 12
        order.append(next_sign)
        
    return order

def _antardhasa_rangacharya(parent_sign):
    """
    Parent-specific padakrama (matches JHora "Rangacharya").
    """
    P = parent_sign % 12
    if P in const.movable_signs:
        return [(P + i) % 12 for i in range(12)]
    if P in const.fixed_signs:
        return [(P + 5 * i) % 12 for i in range(12)]
    out = []
    for g in range(4):
        a = (P - g) % 12
        out.extend([a, (a - 4) % 12, (a + 4) % 12])
    return out


def _dhasa_duration_knrao_method(planet_positions, sign):
    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    lord_of_sign = house.house_owner_from_planet_positions(planet_positions, sign)
    house_of_lord = p_to_h[lord_of_sign]
    dhasa_period = utils.count_rasis(house_of_lord, sign) if sign in const.even_footed_signs else utils.count_rasis(sign, house_of_lord)
    dhasa_period -= 1
    if dhasa_period <= 0:
        dhasa_period = 12
    if const.house_strengths_of_planets[lord_of_sign][house_of_lord] == const._EXALTED_UCCHAM:
        dhasa_period += 1
    elif const.house_strengths_of_planets[lord_of_sign][house_of_lord] == const._DEBILITATED_NEECHAM:
        dhasa_period -= 1
    return dhasa_period

def _lord_of_pvn(sign, planet_positions):
    """Get the stronger lord for a sign using built-in house methods."""
    if sign not in (const.SCORPIO, const.AQUARIUS):
        return const.house_owners[sign]
        
    if sign == const.SCORPIO:
        l1, l2 = const.MARS_ID, const.KETU_ID
    else:
        l1, l2 = const.SATURN_ID, const.RAHU_ID
        
    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    s1 = p_to_h.get(l1, -1)
    s2 = p_to_h.get(l2, -1)
    
    if s1 == sign and s2 != sign: return l2
    if s2 == sign and s1 != sign: return l1
    if s1 == sign and s2 == sign: return l1
    
    # Use the library's built-in stronger planet comparison
    stronger = house.stronger_planet_from_planet_positions(planet_positions, l1, l2)
    return l1 if stronger == l1 else l2


def _antardhasa_order_pvnrao(parent_sign, planet_positions):
    seventh_sign = (parent_sign + const.HOUSE_7) % 12
    
    # Use the library's built-in stronger rasi comparison
    stronger_rasi = house.stronger_rasi_from_planet_positions(planet_positions, parent_sign, seventh_sign)
    start_sign = parent_sign if stronger_rasi == parent_sign else seventh_sign
    
    ODD_SIGNS = {const.ARIES, const.GEMINI, const.LEO, const.LIBRA, const.SAGITTARIUS, const.AQUARIUS}
    forward = start_sign in ODD_SIGNS
    
    if start_sign in const.movable_signs:
        step = 1 if forward else -1
        return [(start_sign + step * i) % 12 for i in range(12)]
    elif start_sign in const.fixed_signs:
        step = 5 if forward else -5
        return [(start_sign + step * i) % 12 for i in range(12)]
    else:
        out = []
        step_kendra = 3 if forward else -3
        step_block = 4 if forward else -4
        for g in range(3):
            anchor = (start_sign + step_block * g) % 12
            out.extend([(anchor + step_kendra * i) % 12 for i in range(4)])
        return out
def _dhasa_duration_pvnrao_method(planet_positions, sign):
    """Not fully implemented yet."""
    p_to_h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    h_to_p = utils.get_house_to_planet_dict_from_planet_to_house_dict(p_to_h)

    if sign == const.SCORPIO:
        if p_to_h[const.MARS_ID] == sign and p_to_h[const.KETU_ID] == sign:
            dhasa_period = 12
            return dhasa_period
        elif p_to_h[const.MARS_ID] == sign and p_to_h[const.KETU_ID] != sign:
            house_of_lord = p_to_h[const.KETU_ID]
        elif p_to_h[const.KETU_ID] == sign and p_to_h[const.MARS_ID] != sign:
            house_of_lord = p_to_h[const.MARS_ID]
        else:
            lord_of_sign = house.house_owner_from_planet_positions(planet_positions, sign)
            house_of_lord = p_to_h[lord_of_sign]
    elif sign == const.AQUARIUS:
        if p_to_h[const.SATURN_ID] == sign and p_to_h[const.RAHU_ID] == sign:
            dhasa_period = 12
            return dhasa_period
        elif p_to_h[const.SATURN_ID] == sign and p_to_h[const.RAHU_ID] != sign:
            house_of_lord = p_to_h[const.RAHU_ID]
        elif p_to_h[const.RAHU_ID] == sign and p_to_h[const.SATURN_ID] != sign:
            house_of_lord = p_to_h[const.SATURN_ID]
        else:
            lord_of_sign = house.house_owner_from_planet_positions(planet_positions, sign)
            house_of_lord = p_to_h[lord_of_sign]
    else:
        lord_of_sign = const.house_owners[sign]
        house_of_lord = p_to_h[lord_of_sign]

    dhasa_period = 0
    if sign in const.even_footed_signs:
        if house_of_lord < sign:
            dhasa_period = sign + 1 - house_of_lord
        else:
            dhasa_period = sign + 13 - house_of_lord
    else:
        if house_of_lord < sign:
            dhasa_period = house_of_lord + 13 - sign
        else:
            dhasa_period = house_of_lord + 1 - sign
    dhasa_period -= 1
    if dhasa_period <= 0:
        dhasa_period = 12
    return dhasa_period
def _dhasa_progression_pvnrao_method(planet_positions):
    """
    Parasara PVR Method Mahadasa Order:
    Starts from Lagna (Ascendant) with direction determined by the 9th house.
    Only with this assumption dhasa progression matches with JHora V8.0 software
    Instead if we use PVR's paper: https://vedicastrologer.org/articles/pp_chara_dasa.pdf
    stronger lord calculation does not match with JHora V8.0 software. 
    Hence we are using Lagna as the starting point.
    """
    asc_house = planet_positions[0][1][0]  # Lagna sign index (Capricorn for this chart)
    seed_house = asc_house
    
    ninth_house = (seed_house + const.HOUSE_9) % 12
    _dhasa_progression = [(h + seed_house) % 12 for h in range(12)]
    
    # If 9th house from seed is even-footed, reverse the progression
    if ninth_house in const.even_footed_signs:
        _dhasa_progression = [(seed_house + 12 - h) % 12 for h in range(12)]
        
    return _dhasa_progression

def _dhasa_duration(planet_positions, sign):
    return _dhasa_duration_knrao_method(planet_positions, sign)

def _dhasa_progression_knrao_method(planet_positions):
    asc_house = planet_positions[0][1][0]
    seed_house = asc_house
    ninth_house = (seed_house + const.HOUSE_9) % 12
    _dhasa_progression = [(h + seed_house) % 12 for h in range(12)]
    if ninth_house in const.even_footed_signs:
        _dhasa_progression = [(seed_house + 12 - h) % 12 for h in range(12)]
    return _dhasa_progression

def get_dhasa_antardhasa(
    dob,
    tob,
    place,
    divisional_chart_factor=1,
    years=1,
    months=1,
    sixty_hours=1,
    chara_method=None,
    gender=0,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
    round_duration=True,
    dhasa_duration_type=None,
    savana_year_method=None,
    **kwargs,
):
    """
    Chara Daśā (sign-based), depth-enabled.
    """
    if chara_method is None: chara_method = const.CHARA_TYPE_DEFAULT
    global one_year_days
    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6 (1=Maha .. 6=Deha).")

    jd_at_dob = utils.julian_day_number(dob, tob)

    one_year_days = drik.dhasa_year_duration(
        jd=jd_at_dob,
        place=place,
        dhasa_duration_type=dhasa_duration_type,
        savana_year_method=savana_year_method,
    )

    planet_positions = charts.divisional_chart(
        jd_at_dob,
        place,
        divisional_chart_factor=divisional_chart_factor,
        **kwargs,
    )[:const._pp_count_upto_ketu]

    if chara_method == const.CHARA_TYPE.PVN_RAO:
        dhasa_progression = _dhasa_progression_pvnrao_method(planet_positions)
        duration_func = _dhasa_duration_pvnrao_method
        cycles = 2
        antardhasa_function = lambda sign, years=None: _antardhasa_order_pvnrao(sign, planet_positions)
        
    elif chara_method == const.CHARA_TYPE.KN_RAO:
        dhasa_progression = _dhasa_progression_knrao_method(planet_positions)
        duration_func = _dhasa_duration_knrao_method
        cycles = 1
        antardhasa_function = lambda sign, years=None: _antardhasa_order_knrao(sign)
        
    elif chara_method == const.CHARA_TYPE.IRANGATTI_MALE1:
        dhasa_progression = _dhasa_progression_iranganti_m1_male(planet_positions) if gender == 0 else _dhasa_progression_iranganti_female(planet_positions)
        duration_func = _dhasa_duration_iranganti_m1_male if gender == 0 else _dhasa_duration_iranganti_female
        cycles = 1
        antardhasa_function = lambda sign, years=None: _antardhasa_iranganti(sign)
        
    elif chara_method == const.CHARA_TYPE.IRANGATTI_MALE2:
        dhasa_progression = _dhasa_progression_iranganti_m2_male(planet_positions) if gender == 0 else _dhasa_progression_iranganti_female(planet_positions)
        duration_func = _dhasa_duration_iranganti_m2_male if gender == 0 else _dhasa_duration_iranganti_female
        cycles = 1
        antardhasa_function = lambda sign, years=None: _antardhasa_iranganti(sign)
        
    elif chara_method == const.CHARA_TYPE.MIND_SUTRA:
        dhasa_progression = _dhasa_progression_mindsutra(planet_positions, gender)
        duration_func = _dhasa_duration_mindsutra
        cycles = 1
        antardhasa_function = lambda sign, years=12: _antardhasa_order_mindsutra(sign, planet_positions, years)
        
    else:
        raise ValueError("Unsupported chara_method.")

    # You can completely safely delete the legacy bhukthis_global variable execution line here!

    def _append(out, tpl):
        out.append(tpl)

    def _child_order(parent_sign, parent_depth, parent_years=None):
        if antardhasa_function is not None:
            # For MindSutra, pass parent_years down. If it is None, default to 12.
            years_int = int(round(parent_years)) if parent_years is not None else 12
            return antardhasa_function(parent_sign, years=years_int)
        return []

    def _recurse(level, parent_sign, parent_start_jd, parent_years, prefix, out_rows):
        # Forward the parent years down into the child calculation layer
        child_order = _child_order(parent_sign, len(prefix), parent_years=parent_years)
        
        # Calculate sub-unit chunks cleanly
        if chara_method == const.CHARA_TYPE.MIND_SUTRA:
            # MindSutra fixes Antardasha block length to 1.0 year 
            # and Pratyantaradasha steps to 1/12th of a year (1 month).
            child_unrounded = 1.0 if len(prefix) == 1 else (1.0 / 12.0)
        else:
            child_unrounded = parent_years / 12.0
            
        jd_cursor = parent_start_jd

        if level < dhasa_level_index:
            for child_sign in child_order:
                # For levels below Antara, child_unrounded represents the new parent_years 
                _recurse(level + 1, child_sign, jd_cursor, child_unrounded, prefix + (child_sign,), out_rows)
                jd_cursor += child_unrounded * one_year_days
        else:
            for child_sign in child_order:
                start_str = utils.jd_to_gregorian(jd_cursor)
                dur_ret = round(child_unrounded, dhasa_level_index + 1) if round_duration else child_unrounded
                _append(out_rows, (prefix + (child_sign,), start_str, dur_ret))
                jd_cursor += child_unrounded * one_year_days


    rows = []
    jd_cur = jd_at_dob

    for cycle_ix in range(cycles):
        for lord in dhasa_progression:
            dd = float(duration_func(planet_positions, lord))
            if chara_method == const.CHARA_TYPE.PVN_RAO and cycle_ix == 1:
                dd = 12.0 - dd

            if dhasa_level_index == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
                start_str = utils.jd_to_gregorian(jd_cur)
                dur_ret = round(dd, dhasa_level_index + 1) if round_duration else dd
                _append(rows, ((lord,), start_str, dur_ret))
                jd_cur += dd * one_year_days
                continue

            # Pass dd down into child_order setup
            child_order = _child_order(lord, 1, parent_years=dd)

            if dhasa_level_index == const.MAHA_DHASA_DEPTH.ANTARA:
                # MindSutra uses 1 year per AD. Other methods split Mahadasha by 12.
                if chara_method == const.CHARA_TYPE.MIND_SUTRA:
                    ddb = 1.0  # Exactly 1 year duration per Antardasha block
                else:
                    ddb = dd / 12.0
                
                jd_b_ini = jd_cur
                for bhukthi in child_order:
                    start_str = utils.jd_to_gregorian(jd_b_ini)
                    dur_ret = round(ddb, dhasa_level_index + 1) if round_duration else ddb
                    _append(rows, ((lord, bhukthi), start_str, dur_ret))
                    jd_b_ini += ddb * one_year_days
                jd_cur += dd * one_year_days
                continue

            # Higher Depths (Pratyantara/Deha Deep-Dive)
            _recurse(
                level=const.MAHA_DHASA_DEPTH.ANTARA,
                parent_sign=lord,
                parent_start_jd=jd_cur,
                parent_years=dd,
                prefix=(lord,),
                out_rows=rows,
            )
            jd_cur += dd * one_year_days

    return rows



def chara_immediate_children(
    parent_lords,
    parent_start,
    parent_duration=None,
    parent_end=None,
    *,
    jd_at_dob,
    place,
    chara_method = None,
    gender: int = 0,
    divisional_chart_factor: int = 1,
    years: int = 1,
    months: int = 1,
    sixty_hours: int = 1,
    round_duration: bool = False,
    dhasa_duration_type=None,
    savana_year_method=None,
    **kwargs,
):
    """
    Chara — return ONLY the immediate (p -> p+1) children inside the given parent span.
    """
    if chara_method is None: chara_method = const.CHARA_TYPE_DEFAULT
    global one_year_days

    one_year_days = drik.dhasa_year_duration(
        jd=jd_at_dob,
        place=place,
        dhasa_duration_type=dhasa_duration_type,
        savana_year_method=savana_year_method,
    )

    if isinstance(parent_lords, int):
        path = (parent_lords,)
    elif isinstance(parent_lords, (list, tuple)) and parent_lords:
        path = tuple(parent_lords)
    else:
        raise ValueError("parent_lords must be int or non-empty tuple/list of ints")
    parent_sign = path[-1]
    parent_depth = len(path)

    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _jd_to_tuple(jd_val):
        return utils.jd_to_gregorian(jd_val)

    start_jd = _tuple_to_jd(parent_start)
    if (parent_duration is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration (years) or parent_end (tuple).")

    if parent_end is None:
        parent_years = float(parent_duration)
        end_jd = start_jd + parent_years * one_year_days
    else:
        end_jd = _tuple_to_jd(parent_end)
        parent_years = (end_jd - start_jd) / one_year_days

    if end_jd <= start_jd:
        return []

    planet_positions = charts.divisional_chart(
        jd_at_dob,
        place,
        divisional_chart_factor=divisional_chart_factor,
        **kwargs,
    )[:const._pp_count_upto_ketu]

    if chara_method == const.CHARA_TYPE.PVN_RAO:
        dhasa_progression = _dhasa_progression_pvnrao_method(planet_positions)
        antardhasa_function = lambda sign, years=None: _antardhasa_order_pvnrao(sign, planet_positions)
        
    elif chara_method == const.CHARA_TYPE.KN_RAO:
        dhasa_progression = _dhasa_progression_knrao_method(planet_positions)
        antardhasa_function = lambda sign, years=None: _antardhasa_order_knrao(sign)
        
    elif chara_method == const.CHARA_TYPE.IRANGATTI_MALE1:
        dhasa_progression = _dhasa_progression_iranganti_m1_male(planet_positions) if gender == 0 else _dhasa_progression_iranganti_female(planet_positions)
        antardhasa_function = lambda sign, years=None: _antardhasa_iranganti(sign)
        
    elif chara_method == const.CHARA_TYPE.IRANGATTI_MALE2:
        dhasa_progression = _dhasa_progression_iranganti_m2_male(planet_positions) if gender == 0 else _dhasa_progression_iranganti_female(planet_positions)
        antardhasa_function = lambda sign, years=None: _antardhasa_iranganti(sign)
        
    elif chara_method == const.CHARA_TYPE.MIND_SUTRA:
        dhasa_progression = _dhasa_progression_mindsutra(planet_positions, gender)
        antardhasa_function = lambda sign, years=12: _antardhasa_order_mindsutra(sign, planet_positions, years)
        
    else:
        raise ValueError("Unsupported chara_method.")

    # Clean up child list extraction logic cleanly depending on depth layers:
    if parent_depth == 1:
        # We are pulling Antardashas from a Mahadasha parent sign
        years_int = int(round(parent_years)) if parent_years is not None else 12
        bhukthis_order = antardhasa_function(parent_sign, years=years_int)
    else:
        # Deep Sub-periods (Pratyantardasha, etc.) under MindSutra default to 12
        bhukthis_order = antardhasa_function(parent_sign, years=12)

    # MindSutra Adjustment: Define step sizes depending on depth level
    if chara_method == const.CHARA_TYPE.MIND_SUTRA:
        if parent_depth == 1:
            child_years = 1.0  # MindSutra Antardasha is always precisely 1 year long
        else:
            child_years = parent_years / 12.0  # Sub-divisions of an active Antardasha are 12 steps
    else:
        child_years = parent_years / 12.0

    children = []
    cursor = start_jd
    total_elements = len(bhukthis_order)
    
    for idx, child_sign in enumerate(bhukthis_order):
        if idx == total_elements - 1:
            child_end = end_jd
        else:
            child_end = cursor + child_years * one_year_days
            
        children.append([
            path + (child_sign,),
            _jd_to_tuple(cursor),
            _jd_to_tuple(child_end),
        ])
        cursor = child_end
        if cursor >= end_jd:
            break

    if children:
        children[-1][2] = _jd_to_tuple(end_jd)
    return children

def get_running_dhasa_for_given_date(
    current_jd,
    jd_at_dob,
    place,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
    *,
    chara_method = None,
    gender: int = 0,
    divisional_chart_factor: int = 1,
    years: int = 1,
    months: int = 1,
    sixty_hours: int = 1,
    round_duration: bool = False,
    dhasa_duration_type=None,
    savana_year_method=None,
    **kwargs,
):
    """
    Chara — narrow Mahā -> … -> target depth and return the full running ladder.
    """
    if chara_method == const.CHARA_TYPE.MIND_SUTRA:
        raise ValueError("MindSutra method is not supported in get_running_dhasa_for_given_date. Use get_dhasa_antardhasa instead.")
    global one_year_days
    if chara_method is None: chara_method = const.CHARA_TYPE_DEFAULT
    one_year_days = drik.dhasa_year_duration(
        jd=jd_at_dob,
        place=place,
        dhasa_duration_type=dhasa_duration_type,
        savana_year_method=savana_year_method,
    )

    def _normalize_depth(depth_val):
        try:
            depth = int(depth_val)
        except Exception:
            depth = int(const.MAHA_DHASA_DEPTH.DEHA)
        lo, hi = int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY), int(const.MAHA_DHASA_DEPTH.DEHA)
        return min(hi, max(lo, depth))

    target_depth = _normalize_depth(dhasa_level_index)

    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

    def _is_zero_length(s, e, eps_seconds=1.0):
        return (_tuple_to_jd(e) - _tuple_to_jd(s)) * 86400.0 <= eps_seconds

    def _as_tuple_lords(x):
        return (x,) if isinstance(x, int) else tuple(x)

    y, m, d, fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y, m, d)
    tob = (fh, 0, 0)

    running_all = []

    # Step 1: Calculate the core Mahadashas
    maha_rows = get_dhasa_antardhasa(
        dob,
        tob,
        place,
        divisional_chart_factor=divisional_chart_factor,
        years=years,
        months=months,
        sixty_hours=sixty_hours,
        chara_method=chara_method,
        gender=gender,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        round_duration=False,
        dhasa_duration_type=dhasa_duration_type,
        savana_year_method=savana_year_method,
        **kwargs,
    )
    
    maha_for_utils = [(_as_tuple_lords(row[0]), row[1]) for row in maha_rows]

    # Find the active Mahadasha window
    rd1 = utils.get_running_dhasa_for_given_date(current_jd, maha_for_utils)
    running = [_as_tuple_lords(rd1[0]), rd1[1], rd1[2]]
    running_all.append(running)

    if target_depth == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
        return running_all

    # Step 2: Iterate down into nested depths (Antara, Pratyantara, Sookshma, etc.)
    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        children = chara_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            chara_method=chara_method,
            gender=gender,
            divisional_chart_factor=divisional_chart_factor,
            years=years,
            months=months,
            sixty_hours=sixty_hours,
            dhasa_duration_type=dhasa_duration_type,
            savana_year_method=savana_year_method,
            **kwargs,
        )
        
        if not children:
            # Fallback safe padding if a sub-period list ends prematurely
            running = [parent_lords + (parent_lords[-1],), parent_end, parent_end]
            running_all.append(running)
            continue

        # Format and pass child list to find active runtime window
        child_for_utils = [(r[0], r[1]) for r in children]
        rd_child = utils.get_running_dhasa_for_given_date(current_jd, child_for_utils)
        
        running = [_as_tuple_lords(rd_child[0]), rd_child[1], rd_child[2]]
        running_all.append(running)

    return running_all

if __name__ == "__main__":
    utils.set_language('en')
    dob = drik.Date(1996, 12, 7)
    tob = (10,34,0)
    #dob = drik.Date(2004, 6, 25)
    #tob = (14, 47, 0)
    place = drik.Place('Chennai,IN', 13.0389, 80.2619, +5.5)
    jd_at_dob = utils.julian_day_number(dob, tob)
    chara_dhasa_method = const.CHARA_TYPE.KN_RAO
    const.dhasa_year_duration_default = const.DHASA_YEAR_DURATION.TRUE_TROPICAL_YEAR
    #"""
    cd = get_dhasa_antardhasa(dob,tob, place, dhasa_level_index=2,
                                        chara_method=chara_dhasa_method, gender=1)
    # Initialize as an empty dict to naturally capture collection order
    lord_seq = {}
    for (lords, start, dur) in cd:
        parent_sign = utils.RAASI_SHORT_LIST[lords[0]]
        sub_sign = utils.RAASI_SHORT_LIST[lords[1]]
        
        # Initialize the dictionary entry if the parent sign is seen for the first time
        # Structure: [ [list of sub_signs], total_duration ]
        if parent_sign not in lord_seq:
            lord_seq[parent_sign] = [[], 0.0]
            
        # Append sub_sign to the list and add duration to the total
        lord_seq[parent_sign][0].append(sub_sign)
        lord_seq[parent_sign][1] += dur
        
    # Example of how to print or use the resulting dictionary
    for k, (sub_lords, total_dur) in lord_seq.items():
        sub_lords_str = ','.join(sub_lords)
        print(f"\t{k}: ([{sub_lords_str}], {total_dur})")
        
    exit()
    #"""
    from datetime import datetime
    current_date_str, current_time_str = datetime.now().strftime('%Y,%m,%d;%H:%M:%S').split(';')
    y, m, d = map(int, current_date_str.split(','))
    hh, mm, ss = map(int, current_time_str.split(':'))
    fh = hh + mm / 60 + ss / 3600
    print(utils.date_time_tuple_to_date_time_string(y, m, d, fh))
    current_jd = utils.julian_day_number(drik.Date(y, m, d), (hh, mm, ss))
    import time
    if chara_dhasa_method == const.CHARA_TYPE.MIND_SUTRA:
        print("Skipping old method for MindSutra as it is not supported.")
        exit()  # MindSutra is not supported in the old method, skip it
    for dd in const.DHASA_YEAR_DURATION:
        yd = drik.dhasa_year_duration(
            jd=jd_at_dob,
            place=place,
            dhasa_duration_type=dd,
        )

        print("\n" + "-" * 80)
        print("Dhasa duration method:", dd.name, dd.value)
        print("Resolved year duration days:", yd)
        print("-" * 80)
    
        start_time = time.time()
        print(
            "Dehā        :",
            get_running_dhasa_for_given_date(
                current_jd,
                jd_at_dob,
                place,
                dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
                dhasa_duration_type=dd,
                chara_method=chara_dhasa_method,
            ),
        )
        print('new method elapsed time', time.time() - start_time)
        start_time = time.time()
        ad = get_dhasa_antardhasa(
            dob,
            tob,
            place,
            dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
            dhasa_duration_type=dd,
            chara_method=chara_dhasa_method,
        )
        print(
            utils.get_running_dhasa_at_all_levels_for_given_date(
                current_jd,
                ad,
                const.MAHA_DHASA_DEPTH.DEHA,
                extract_running_period_for_all_levels=True,
            )
        )
        print('old method elapsed time', time.time() - start_time)
    exit()
    from jhora.tests import pvr_tests
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.chara_dhasa_test()
    exit()
