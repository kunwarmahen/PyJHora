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
    Release History:
        V4.8.9 - minor argument call fixes.
        V4.9.0 - dhasa start date calculation now uses drik._get_dhasa_star_jd() 
                to calculate dhasa start date using how much Sun has tranversed.
"""
""" Tithi Yogini Dasa """
""" TODO: To implement in jhora.panchanga.drik general tithi based on any 2 planets and call here """
from jhora import const, utils
from jhora.panchanga import drik


year_duration = const.sidereal_year

"""dhasa_adhipathi_dict = {planet: [(tithi list), dhasa duration]}"""

from jhora import const, utils
from jhora.panchanga import drik


year_duration = const.sidereal_year

"""Tithi Yogini Dhasa."""

seed_star = 7
seed_lord = 0

dhasa_adhipathi_list = {
    1: 1,
    0: 2,
    4: 3,
    2: 4,
    3: 5,
    6: 6,
    5: 7,
    7: 8,
}

dhasa_adhipathi_dict = {
    0: [(1, 9, 16, 24), 2],
    1: [(2, 10, 17, 25), 1],
    2: [(3, 11, 18, 26), 4],
    3: [(4, 12, 19, 27), 5],
    6: [(7, 15, 22), 6],
    4: [(5, 13, 20, 28), 3],
    7: [(8, 23, 30), 8],
    5: [(6, 14, 21, 29), 7],
}

count_direction = 1


def yogini_adhipathi(tithi_index):
    for key, value in dhasa_adhipathi_dict.items():
        tithi_list, durn = value

        if tithi_index in tithi_list:
            return key, durn

    raise ValueError("No Yogini adhipathi found for tithi_index={}".format(tithi_index))


def _next_adhipati(lord, dirn=1):
    """Returns next lord after lord in the adhipati list."""
    keys = list(dhasa_adhipathi_list.keys())
    current = keys.index(lord)
    next_lord = keys[(current + dirn) % len(keys)]

    return next_lord


def _get_dhasa_dict():
    dhasa_dict = {k: [] for k in dhasa_adhipathi_list.keys()}

    nak = seed_star - 1
    lord = seed_lord
    lord_index = list(dhasa_adhipathi_list.keys()).index(lord)

    for _ in range(27):
        dhasa_dict[lord].append(nak + 1)
        nak = (nak + count_direction) % 27
        lord_index = (lord_index + 1) % len(dhasa_adhipathi_list)
        lord = list(dhasa_adhipathi_list.keys())[lord_index]

    return dhasa_dict


def _maha_dhasa(nak):
    return [
        (_dhasa_lord, dhasa_adhipathi_list[_dhasa_lord])
        for _dhasa_lord, _star_list in dhasa_adhipathi_dict.items()
        if nak in _star_list
    ][0]


def _antardhasa(dhasa_lord, antardhasa_option=1):
    lord = dhasa_lord

    if antardhasa_option in [3, 4]:
        lord = _next_adhipati(dhasa_lord, dirn=1)
    elif antardhasa_option in [5, 6]:
        lord = _next_adhipati(dhasa_lord, dirn=-1)

    dirn = 1 if antardhasa_option in [1, 3, 5] else -1

    bhukthis = []

    for _ in range(len(dhasa_adhipathi_list)):
        bhukthis.append(lord)
        lord = _next_adhipati(lord, dirn)

    return bhukthis


def _dhasa_start(jd, place, tithi_index=1):
    _, _, _, birth_time_hrs = utils.jd_to_gregorian(jd)

    tit = drik.tithi(
        jd,
        place,
        tithi_index,
    )

    t_frac = utils.get_fraction(
        tit[1],
        tit[2],
        birth_time_hrs,
    )

    lord, res = yogini_adhipathi(tit[0])

    start_jd = drik._get_dhasa_start_jd(
        jd,
        place,
        fraction_elapsed=(1.0 - t_frac),
        total_dasa_years=res,
    )

    return [lord, start_jd, res]


def get_dhasa_bhukthi(
    dob,
    tob,
    place,
    use_tribhagi_variation=False,
    tithi_index=1,
    antardhasa_option=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
    round_duration=True,
    dhasa_duration_type=None,
    savana_year_method=None,
):
    """
    Provides Tithi Yogini dhasa-bhukthi for a given birth date and time.

    This is Yogini dhasa based on tithi instead of nakshatra.

    Return format:
        [
            [lords_tuple, start_tuple, duration_years],
            ...
        ]

    End JD is used internally only to calculate the next start JD.

    dhasa_level_index:
        1 = Maha only
        2 = Antara
        3 = Pratyantara
        4 = Sookshma
        5 = Prana
        6 = Deha
    """
    global year_duration

    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6.")

    tribhagi_factor = 1.0
    dhasa_cycles = 3

    if use_tribhagi_variation:
        tribhagi_factor = 1.0 / 3.0
        dhasa_cycles = int(dhasa_cycles / tribhagi_factor)

    jd = utils.julian_day_number(dob, tob)

    year_duration = drik.dhasa_year_duration(
        jd=jd,
        place=place,
        dhasa_duration_type=dhasa_duration_type,
        savana_year_method=savana_year_method,
    )

    dhasa_lord, start_jd, _ = _dhasa_start(
        jd,
        place,
        tithi_index,
    )

    retval = []

    def _next_jd_by_dhasa_years(start_jd_local, duration_years):
        return drik._get_dhasa_end_jd(
            start_jd=start_jd_local,
            place=place,
            total_dasa_years=duration_years,
        )

    def _children_of(parent_lord):
        return list(
            _antardhasa(
                parent_lord,
                antardhasa_option=antardhasa_option,
            )
        )

    def _emit_row(lords_tuple, start_jd_local, duration_years):
        durn = (
            round(duration_years, dhasa_level_index + 1)
            if round_duration
            else duration_years
        )

        retval.append(
            [
                lords_tuple,
                utils.jd_to_gregorian(start_jd_local),
                durn,
            ]
        )

    def _recurse(
        level,
        parent_lord,
        parent_start_jd,
        parent_duration_years,
        prefix,
    ):
        bhukthis = _children_of(parent_lord)

        if not bhukthis:
            return

        child_dur = parent_duration_years / len(bhukthis)
        jd_cursor = parent_start_jd

        for blord in bhukthis:
            child_start_jd = jd_cursor

            if level < dhasa_level_index:
                _recurse(
                    level + 1,
                    blord,
                    child_start_jd,
                    child_dur,
                    prefix + (blord,),
                )
            else:
                _emit_row(
                    prefix + (blord,),
                    child_start_jd,
                    child_dur,
                )

            jd_cursor = _next_jd_by_dhasa_years(
                child_start_jd,
                child_dur,
            )

    for _ in range(dhasa_cycles):
        for _ in range(len(dhasa_adhipathi_list)):
            maha_dur = dhasa_adhipathi_list[dhasa_lord] * tribhagi_factor
            maha_start_jd = start_jd

            if dhasa_level_index == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
                _emit_row(
                    (dhasa_lord,),
                    maha_start_jd,
                    maha_dur,
                )
            else:
                _recurse(
                    level=const.MAHA_DHASA_DEPTH.ANTARA,
                    parent_lord=dhasa_lord,
                    parent_start_jd=maha_start_jd,
                    parent_duration_years=maha_dur,
                    prefix=(dhasa_lord,),
                )

            start_jd = _next_jd_by_dhasa_years(
                maha_start_jd,
                maha_dur,
            )

            dhasa_lord = _next_adhipati(dhasa_lord)

    return retval


def tithi_yogini_immediate_children(
    parent_lords,
    parent_start,
    parent_duration=None,
    parent_end=None,
    jd_at_dob=None,
    place=None,
    tithi_index=1,
    antardhasa_option=1,
    use_tribhagi_variation=False,
    dhasa_duration_type=None,
    savana_year_method=None,
):
    """
    Tithi Yogini immediate children under the given parent span.

    Returns:
        [
            [lords_tuple_with_child, child_start_tuple, child_end_tuple],
            ...
        ]

    This function intentionally returns start and end tuples because
    the running-dhasa navigator needs parent-child boundaries.
    """
    global year_duration

    if jd_at_dob is not None and place is not None:
        year_duration = drik.dhasa_year_duration(
            jd=jd_at_dob,
            place=place,
            dhasa_duration_type=dhasa_duration_type,
            savana_year_method=savana_year_method,
        )

    if place is None:
        raise ValueError("place is required for exact Tithi Yogini child boundary calculation.")

    if isinstance(parent_lords, int):
        path = (parent_lords,)
    elif isinstance(parent_lords, (list, tuple)) and parent_lords:
        path = tuple(parent_lords)
    else:
        raise ValueError("parent_lords must be int or non-empty tuple/list of ints")

    parent_lord = path[-1]

    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(
            drik.Date(y, m, d),
            (fh, 0, 0),
        )

    def _jd_to_tuple(jd_val):
        return utils.jd_to_gregorian(jd_val)

    def _next_jd_by_dhasa_years(start_jd_local, duration_years):
        return drik._get_dhasa_end_jd(
            start_jd=start_jd_local,
            place=place,
            total_dasa_years=duration_years,
        )

    start_jd = _tuple_to_jd(parent_start)

    if (parent_duration is None) == (parent_end is None):
        raise ValueError("Provide exactly one of parent_duration or parent_end.")

    if parent_end is None:
        parent_years = float(parent_duration)

        end_jd = _next_jd_by_dhasa_years(
            start_jd,
            parent_years,
        )
    else:
        end_jd = _tuple_to_jd(parent_end)
        parent_years = (end_jd - start_jd) / year_duration

    if end_jd <= start_jd:
        return []

    child_lords = list(
        _antardhasa(
            parent_lord,
            antardhasa_option=antardhasa_option,
        )
    )

    if not child_lords:
        return []

    child_years = parent_years / len(child_lords)

    children = []
    jd_cursor = start_jd

    for idx, blord in enumerate(child_lords):
        child_start = jd_cursor

        if idx == len(child_lords) - 1:
            child_end = end_jd
        else:
            child_end = _next_jd_by_dhasa_years(
                child_start,
                child_years,
            )

        children.append(
            [
                path + (blord,),
                _jd_to_tuple(child_start),
                _jd_to_tuple(child_end),
            ]
        )

        jd_cursor = child_end

        if jd_cursor >= end_jd:
            break

    if children:
        children[-1][2] = _jd_to_tuple(end_jd)

    return children


def get_running_dhasa_for_given_date(
    current_jd,
    jd_at_dob,
    place,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
    tithi_index=1,
    antardhasa_option=1,
    use_tribhagi_variation=False,
    round_duration=False,
    dhasa_duration_type=None,
    savana_year_method=None,
):
    """
    Tithi Yogini runner.

    Returns:
        [
            [(l1,),              start1, end1],
            [(l1,l2),            start2, end2],
            [(l1,l2,l3),         start3, end3],
            [(l1,l2,l3,l4),      start4, end4],
            [(l1,l2,l3,l4,l5),   start5, end5],
            [(l1,l2,l3,l4,l5,l6),start6, end6],
        ]
    """
    global year_duration

    year_duration = drik.dhasa_year_duration(
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

        lo = int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY)
        hi = int(const.MAHA_DHASA_DEPTH.DEHA)

        return min(hi, max(lo, depth))

    def _tuple_to_jd(t):
        y, m, d, fh = t
        return utils.julian_day_number(
            drik.Date(y, m, d),
            (fh, 0, 0),
        )

    def _is_zero_length(s, e, eps_seconds=1.0):
        return (_tuple_to_jd(e) - _tuple_to_jd(s)) * 86400.0 <= eps_seconds

    def _to_utils_periods(children_rows, parent_end_tuple, eps_seconds=1.0):
        filtered = [
            row
            for row in children_rows
            if not _is_zero_length(row[1], row[2], eps_seconds=eps_seconds)
        ]

        if not filtered:
            return []

        filtered.sort(key=lambda row: _tuple_to_jd(row[1]))

        proj = []
        prev = None

        for lords, st, _en in filtered:
            sjd = _tuple_to_jd(st)

            if prev is None or sjd > prev:
                proj.append((lords, st))
                prev = sjd

        proj.append((proj[-1][0], parent_end_tuple))

        return proj

    def _as_tuple_lords(x):
        return (x,) if isinstance(x, int) else tuple(x)

    target_depth = _normalize_depth(dhasa_level_index)

    y, m, d, fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y, m, d)
    tob = (fh, 0, 0)

    maha_rows = get_dhasa_bhukthi(
        dob,
        tob,
        place,
        use_tribhagi_variation=use_tribhagi_variation,
        tithi_index=tithi_index,
        antardhasa_option=antardhasa_option,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        round_duration=False,
        dhasa_duration_type=dhasa_duration_type,
        savana_year_method=savana_year_method,
    )

    maha_for_utils = [
        (_as_tuple_lords(row[0]), row[1])
        for row in maha_rows
    ]

    rd1 = utils.get_running_dhasa_for_given_date(
        current_jd,
        maha_for_utils,
    )

    running = [
        _as_tuple_lords(rd1[0]),
        rd1[1],
        rd1[2],
    ]

    running_all = [running]

    if target_depth == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
        return running_all

    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        children = tithi_yogini_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            tithi_index=tithi_index,
            antardhasa_option=antardhasa_option,
            use_tribhagi_variation=use_tribhagi_variation,
            dhasa_duration_type=dhasa_duration_type,
            savana_year_method=savana_year_method,
        )

        if not children:
            running = [
                parent_lords + (parent_lords[-1],),
                parent_end,
                parent_end,
            ]
            running_all.append(running)
            break

        periods_for_utils = _to_utils_periods(
            children,
            parent_end_tuple=parent_end,
        )

        if not periods_for_utils:
            last = children[-1]
            running = [last[0], last[1], last[1]]
        else:
            rdk = utils.get_running_dhasa_for_given_date(
                current_jd,
                periods_for_utils,
            )

            running = [
                _as_tuple_lords(rdk[0]),
                rdk[1],
                rdk[2],
            ]

        running_all.append(running)

    return running_all
if __name__ == "__main__":
    utils.set_language('en')
    dob = drik.Date(1996, 12, 7)
    tob = (10, 34, 0)
    place = drik.Place('Chennai,IN', 13.0389, 80.2619, +5.5)
    for dd in const.DHASA_YEAR_DURATION:
        const.dhasa_year_duration_default = dd
        print(dd.name,get_dhasa_bhukthi(dob,tob, place, dhasa_level_index=1))
    exit()
    jd_at_dob = utils.julian_day_number(dob, tob)
    from datetime import datetime
    current_date_str, current_time_str = datetime.now().strftime('%Y,%m,%d;%H:%M:%S').split(';')
    y, m, d = map(int, current_date_str.split(','))
    hh, mm, ss = map(int, current_time_str.split(':'))
    fh = hh + mm / 60 + ss / 3600
    print(utils.date_time_tuple_to_date_time_string(y, m, d, fh))
    current_jd = utils.julian_day_number(drik.Date(y, m, d), (hh, mm, ss))
    import time
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
            ),
        )
        print('new method elapsed time', time.time() - start_time)

        start_time = time.time()
        ad = get_dhasa_bhukthi(
            dob,
            tob,
            place,
            dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
            dhasa_duration_type=dd,
        )
        print(
            utils.get_running_dhasa_at_all_levels_for_given_date(
                current_jd,
                ad,
                const.MAHA_DHASA_DEPTH.DEHA,
                extract_running_period_for_all_levels=True,
                dhasa_cycle_count=3,
            )
        )
        print('old method elapsed time', time.time() - start_time)

    exit()
    from jhora.tests import pvr_tests
    const.use_24hour_format_in_to_dms = False
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.tithi_yogini_test()
