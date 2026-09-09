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
"""
        Calculates Tithi Ashtottari (=108) Dasha-bhukthi-antara-sukshma-prana
        Ref: https://www.indiadivine.org/content/topic/1488164-vedavyasa-tithi-ashtottari-dasa-tutorial/

"""

from collections import OrderedDict as Dict

from jhora import const, utils
from jhora.panchanga import drik
from jhora.horoscope.chart import house


year_duration = const.sidereal_year
human_life_span_for_ashtottari_dhasa = 108

"""
    {ashtottari adhipati:[(tithis),dasa_length]}
"""

ashtottari_adhipathi_list = [0, 1, 2, 3, 6, 4, 7, 5]

ashtottari_adhipathi_dict = {
    0: [(1, 9, 16, 24), 6],
    1: [(2, 10, 17, 25), 15],
    2: [(3, 11, 18, 26), 8],
    3: [(4, 12, 19, 27), 17],
    6: [(7, 15, 22), 10],
    4: [(5, 13, 20, 28), 19],
    7: [(8, 23, 30), 12],
    5: [(6, 14, 21, 29), 21],
}


def _ashtottari_adhipathi(tithi_index):
    for key, value in ashtottari_adhipathi_dict.items():
        tithi_list, durn = value

        if tithi_index in tithi_list:
            return key, durn

    raise ValueError("No Ashtottari adhipathi found for tithi_index={}".format(tithi_index))


def _ashtottari_dasha_start_date(jd, place, tithi_index=1):
    _, _, _, birth_time_hrs = utils.jd_to_gregorian(jd)

    tit = drik.tithi(
        jd,
        place,
        tithi_index=tithi_index,
    )

    t_frac = utils.get_fraction(
        tit[1],
        tit[2],
        birth_time_hrs,
    )

    lord, res = _ashtottari_adhipathi(tit[0])

    start_jd = drik._get_dhasa_start_jd(
        jd,
        place,
        fraction_elapsed=(1.0 - t_frac),
        total_dasa_years=res,
    )

    return [lord, start_jd]


def _ashtottari_next_adhipati(lord, dirn=1):
    """Returns next lord after lord in the adhipati list."""
    current = ashtottari_adhipathi_list.index(lord)
    next_index = (current + dirn) % len(ashtottari_adhipathi_list)

    return ashtottari_adhipathi_list[next_index]


def ashtottari_mahadasa(jd, place, tithi_index):
    """
    Returns a dictionary of all mahadashas and their start JDs.

    Returns:
        OrderedDict:
            {mahadhasa_lord_index: start_jd}
    """
    lord, start_date = _ashtottari_dasha_start_date(
        jd,
        place,
        tithi_index,
    )

    retval = Dict()

    for _ in range(len(ashtottari_adhipathi_list)):
        retval[lord] = start_date

        lord_duration = ashtottari_adhipathi_dict[lord][1]

        start_date = drik._get_dhasa_end_jd(
            start_jd=start_date,
            place=place,
            total_dasa_years=lord_duration,
        )

        lord = _ashtottari_next_adhipati(lord)

    return retval


def ashtottari_bhukthi(dhasa_lord, start_date, place, antardhasa_option=3):
    """
    Compute all bhukthis of given Mahadasa lord and its start date.
    """
    global human_life_span_for_ashtottari_dhasa, ashtottari_adhipathi_dict

    lord = dhasa_lord

    if antardhasa_option in [3, 4]:
        lord = _ashtottari_next_adhipati(lord, dirn=1)
    elif antardhasa_option in [5, 6]:
        lord = _ashtottari_next_adhipati(lord, dirn=-1)

    dirn = 1 if antardhasa_option in [1, 3, 5] else -1

    dhasa_lord_duration = ashtottari_adhipathi_dict[dhasa_lord][1]

    retval = Dict()

    for _ in range(len(ashtottari_adhipathi_list)):
        retval[lord] = start_date

        lord_duration = ashtottari_adhipathi_dict[lord][1]

        factor = (
            lord_duration
            * dhasa_lord_duration
            / human_life_span_for_ashtottari_dhasa
        )

        start_date = drik._get_dhasa_end_jd(
            start_jd=start_date,
            place=place,
            total_dasa_years=factor,
        )

        lord = _ashtottari_next_adhipati(lord, dirn)

    return retval


def ashtottari_anthara(dhasa_lord, bhukthi_lord, bhukthi_lord_start_date, place):
    """
    Compute all antharas for given Mahadasa lord, Bhukthi lord and Bhukthi start date.
    """
    global human_life_span_for_ashtottari_dhasa, ashtottari_adhipathi_dict

    dhasa_lord_duration = ashtottari_adhipathi_dict[dhasa_lord][1]
    bhukthi_lord_duration = ashtottari_adhipathi_dict[bhukthi_lord][1]

    retval = Dict()

    lord = _ashtottari_next_adhipati(bhukthi_lord)

    for _ in range(len(ashtottari_adhipathi_list)):
        retval[lord] = bhukthi_lord_start_date

        lord_duration = ashtottari_adhipathi_dict[lord][1]

        factor = (
            lord_duration
            * dhasa_lord_duration
            * bhukthi_lord_duration
            / human_life_span_for_ashtottari_dhasa
            / human_life_span_for_ashtottari_dhasa
        )

        bhukthi_lord_start_date = drik._get_dhasa_end_jd(
            start_jd=bhukthi_lord_start_date,
            place=place,
            total_dasa_years=factor,
        )

        lord = _ashtottari_next_adhipati(lord)

    return retval


def get_dhasa_bhukthi(
    jd,
    place,
    use_tribhagi_variation=False,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
    tithi_index=1,
    antardhasa_option=3,
    dhasa_duration_type=None,
    savana_year_method=None,
):
    """
    Provides Tithi Ashtottari dhasa-bhukthi for a given Julian day.

    This is Ashtottari Dhasa based on tithi instead of nakshatra.

    Return format:
        [
            [lords_tuple, start_tuple, duration_years],
            ...
        ]

    End JD is used internally only to calculate the next start JD.
    """
    global human_life_span_for_ashtottari_dhasa, year_duration, ashtottari_adhipathi_dict

    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6.")

    year_duration = drik.dhasa_year_duration(
        jd=jd,
        place=place,
        dhasa_duration_type=dhasa_duration_type,
        savana_year_method=savana_year_method,
    )

    orig_H = human_life_span_for_ashtottari_dhasa
    orig_dict = {
        k: [v[0], v[1]]
        for k, v in ashtottari_adhipathi_dict.items()
    }

    try:
        dhasa_cycles = 1

        if use_tribhagi_variation:
            tribhagi_factor = 1.0 / 3.0
            dhasa_cycles = int(dhasa_cycles / tribhagi_factor)

            human_life_span_for_ashtottari_dhasa = orig_H * tribhagi_factor

            ashtottari_adhipathi_dict = {
                k: [v[0], round(v[1] * tribhagi_factor, 6)]
                for k, v in orig_dict.items()
            }

        H = human_life_span_for_ashtottari_dhasa

        dashas = ashtottari_mahadasa(
            jd,
            place,
            tithi_index,
        )

        dhasa_bhukthi = []

        def _next_jd_by_dhasa_years(start_jd_local, duration_years):
            return drik._get_dhasa_end_jd(
                start_jd=start_jd_local,
                place=place,
                total_dasa_years=duration_years,
            )

        def _emit_row(lords_tuple, start_jd_local, duration_years):
            dhasa_bhukthi.append(
                [
                    lords_tuple,
                    utils.jd_to_gregorian(start_jd_local),
                    float(duration_years),
                ]
            )

        def _child_start_and_dir(parent_lord):
            lord = parent_lord

            if antardhasa_option in [3, 4]:
                lord = _ashtottari_next_adhipati(parent_lord, dirn=1)
            elif antardhasa_option in [5, 6]:
                lord = _ashtottari_next_adhipati(parent_lord, dirn=-1)

            dirn = 1 if antardhasa_option in [1, 3, 5] else -1

            return lord, dirn

        def _children_of(parent_lord, parent_start_jd, parent_end_jd, parent_years):
            """
            One full child cycle under parent_lord.

            child_years = parent_years * Y(child) / H.
            End JD is used internally only to calculate next start.
            """
            start_lord, dirn = _child_start_and_dir(parent_lord)

            jd_cursor = parent_start_jd
            lord = start_lord

            for idx in range(len(ashtottari_adhipathi_list)):
                Y = ashtottari_adhipathi_dict[lord][1]
                dur_yrs = parent_years * (Y / H)

                child_start_jd = jd_cursor

                if idx == len(ashtottari_adhipathi_list) - 1:
                    child_end_jd = parent_end_jd
                else:
                    child_end_jd = _next_jd_by_dhasa_years(
                        child_start_jd,
                        dur_yrs,
                    )

                yield lord, child_start_jd, child_end_jd, dur_yrs

                jd_cursor = child_end_jd

                if jd_cursor >= parent_end_jd:
                    break

                lord = _ashtottari_next_adhipati(lord, dirn)

        def _current_cycle_items(md_items, cycle_start_jd):
            """
            Builds one cycle of mahadasha start JDs using _get_dhasa_end_jd.
            """
            items = []
            cursor = cycle_start_jd

            for lord, _old_start in md_items:
                items.append((lord, cursor))

                cursor = _next_jd_by_dhasa_years(
                    cursor,
                    ashtottari_adhipathi_dict[lord][1],
                )

            return items, cursor

        md_items_base = list(dashas.items())
        cycle_start_jd = md_items_base[0][1]

        for _ in range(dhasa_cycles):
            md_items, next_cycle_start_jd = _current_cycle_items(
                md_items_base,
                cycle_start_jd,
            )

            for idx, (lord, maha_start) in enumerate(md_items):
                if idx < len(md_items) - 1:
                    maha_end = md_items[idx + 1][1]
                else:
                    maha_end = next_cycle_start_jd

                maha_years = (maha_end - maha_start) / year_duration

                if dhasa_level_index == const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY:
                    _emit_row(
                        (lord,),
                        maha_start,
                        maha_years,
                    )
                    continue

                if dhasa_level_index == const.MAHA_DHASA_DEPTH.ANTARA:
                    for blord, bstart, bend, byears in _children_of(
                        lord,
                        maha_start,
                        maha_end,
                        maha_years,
                    ):
                        _emit_row(
                            (lord, blord),
                            bstart,
                            byears,
                        )
                    continue

                def _recurse(level, parent_lord, parent_start_jd, parent_end_jd, parent_years, prefix):
                    if level == dhasa_level_index:
                        _emit_row(
                            prefix,
                            parent_start_jd,
                            parent_years,
                        )
                        return

                    for clord, cstart, cend, cyears in _children_of(
                        parent_lord,
                        parent_start_jd,
                        parent_end_jd,
                        parent_years,
                    ):
                        _recurse(
                            level + 1,
                            clord,
                            cstart,
                            cend,
                            cyears,
                            prefix + (clord,),
                        )

                _recurse(
                    level=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
                    parent_lord=lord,
                    parent_start_jd=maha_start,
                    parent_end_jd=maha_end,
                    parent_years=maha_years,
                    prefix=(lord,),
                )

            cycle_start_jd = next_cycle_start_jd

        return dhasa_bhukthi

    finally:
        human_life_span_for_ashtottari_dhasa = orig_H
        ashtottari_adhipathi_dict = orig_dict


def tithi_ashtottari_immediate_children(
    parent_lords,
    parent_start,
    parent_duration=None,
    parent_end=None,
    jd_at_dob=None,
    place=None,
    antardhasa_option=3,
    use_tribhagi_variation=False,
    dhasa_duration_type=None,
    savana_year_method=None,
):
    """
    Tithi Ashtottari immediate children under the given parent span.

    Returns:
        [
            [lords_tuple_with_child, child_start_tuple, child_end_tuple],
            ...
        ]
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
        raise ValueError("place is required for exact Tithi Ashtottari child boundary calculation.")

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

    def _child_start_and_dir(parent_lord_local):
        lord = parent_lord_local

        if antardhasa_option in [3, 4]:
            lord = _ashtottari_next_adhipati(parent_lord_local, dirn=1)
        elif antardhasa_option in [5, 6]:
            lord = _ashtottari_next_adhipati(parent_lord_local, dirn=-1)

        dirn = 1 if antardhasa_option in [1, 3, 5] else -1

        return lord, dirn

    H = float(human_life_span_for_ashtottari_dhasa)

    start_lord, dirn = _child_start_and_dir(parent_lord)

    jd_cursor = start_jd
    lord = start_lord

    children = []
    N = len(ashtottari_adhipathi_list)

    for idx in range(N):
        Y = float(ashtottari_adhipathi_dict[lord][1])
        child_years = parent_years * (Y / H)

        child_start = jd_cursor

        if idx == N - 1:
            child_end = end_jd
        else:
            child_end = _next_jd_by_dhasa_years(
                child_start,
                child_years,
            )

        children.append(
            [
                path + (lord,),
                _jd_to_tuple(child_start),
                _jd_to_tuple(child_end),
            ]
        )

        jd_cursor = child_end

        if jd_cursor >= end_jd:
            break

        lord = _ashtottari_next_adhipati(lord, dirn)

    if children:
        children[-1][2] = _jd_to_tuple(end_jd)

    return children


def get_running_dhasa_for_given_date(
    current_jd,
    jd_at_dob,
    place,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
    tithi_index=1,
    antardhasa_option=3,
    use_tribhagi_variation=False,
    round_duration=False,
    dhasa_duration_type=None,
    savana_year_method=None,
):
    """
    Tithi Ashtottari runner.

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

    maha_rows = get_dhasa_bhukthi(
        jd=jd_at_dob,
        place=place,
        use_tribhagi_variation=use_tribhagi_variation,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        tithi_index=tithi_index,
        antardhasa_option=antardhasa_option,
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

        children = tithi_ashtottari_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
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
'------ main -----------'
if __name__ == "__main__":
    utils.set_language('en')
    dob = drik.Date(1996, 12, 7)
    tob = (10, 34, 0)
    place = drik.Place('Chennai,IN', 13.0389, 80.2619, +5.5)
    jd_at_dob = utils.julian_day_number(dob, tob)
    from datetime import datetime
    current_date_str, current_time_str = datetime.now().strftime('%Y,%m,%d;%H:%M:%S').split(';')
    y, m, d = map(int, current_date_str.split(','))
    hh, mm, ss = map(int, current_time_str.split(':'))
    fh = hh + mm / 60 + ss / 3600
    print(utils.date_time_tuple_to_date_time_string(y, m, d, fh))
    current_jd = utils.julian_day_number(drik.Date(y, m, d), (hh, mm, ss))
    for dd in const.DHASA_YEAR_DURATION:
        const.dhasa_year_duration_default = dd
        print(dd.name,get_dhasa_bhukthi(jd_at_dob, place, dhasa_level_index=1)[0])
    exit()
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
            jd_at_dob,
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
            )
        )
        print('old method elapsed time', time.time() - start_time)

    exit()
    from jhora.tests import pvr_tests
    const.use_24hour_format_in_to_dms = False
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.tithi_ashtottari_tests()
