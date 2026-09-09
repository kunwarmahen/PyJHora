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
""" Karana Based Chathuraaseethi Sama Dasa """

from jhora import const, utils
from jhora.panchanga import drik


year_duration = const.sidereal_year

seed_lord = 0

# Exclude Rahu and Ketu, last two entries.
dhasa_adhipathi_dict = {
    key: const.karana_lords[key]
    for key in list(const.karana_lords.keys())[:-2]
}

# Duration 12 years each. Total 84 years.
dhasa_adhipathi_list = {k: 12 for k in range(len(dhasa_adhipathi_dict))}

# count_direction:
#   1  => zodiac
#  -1  => anti-zodiac
count_direction = 1


def _dhasa_adhipathi(karana_index):
    for key, value in dhasa_adhipathi_dict.items():
        karana_list, durn = value

        if karana_index in karana_list:
            return key, durn

    raise ValueError("No dhasa adhipathi found for karana_index={}".format(karana_index))


def _next_adhipati(lord, dirn=1):
    """Returns next lord after lord in the adhipati list."""
    keys = list(dhasa_adhipathi_list.keys())
    current = keys.index(lord)
    next_lord = keys[(current + dirn) % len(keys)]

    return next_lord


def _maha_dhasa(karana_index):
    """
    Returns maha dhasa lord and duration for the given karana index.

    This is kept for API/internal compatibility.
    """
    return _dhasa_adhipathi(karana_index)


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


def _dhasa_start(jd, place):
    _, _, _, birth_time_hrs = utils.jd_to_gregorian(jd)

    karana_info = drik.karana(jd, place)
    k_frac = utils.get_fraction(
        karana_info[1],
        karana_info[2],
        birth_time_hrs,
    )

    lord, res = _dhasa_adhipathi(karana_info[0])

    fraction_elapsed = 1.0 - k_frac

    start_jd = drik._get_dhasa_start_jd(
        jd,
        place,
        fraction_elapsed=fraction_elapsed,
        total_dasa_years=res,
    )

    return [lord, start_jd, res]


def get_dhasa_bhukthi(
    dob,
    tob,
    place,
    use_tribhagi_variation=False,
    divisional_chart_factor=1,
    chart_method=1,
    antardhasa_option=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
    round_duration=True,
    dhasa_duration_type=None,
    savana_year_method=None,
):
    """
    Provides Karana Chathuraaseethi Sama dhasa-bhukthi for a given birth date/time.

    Return format is preserved:
        [
            [lords_tuple, start_tuple, duration_years],
            ...
        ]

    dhasa_level_index:
        1 = Maha only
        2 = Antara
        3 = Pratyantara
        4 = Sookshma
        5 = Prana
        6 = Deha

    Note:
        End JD is used internally only to calculate the next start JD.
        It is not returned from this function.
    """
    global year_duration

    if not (
        const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY
        <= dhasa_level_index
        <= const.MAHA_DHASA_DEPTH.DEHA
    ):
        raise ValueError("dhasa_level_index must be in 1..6 (1=Maha .. 6=Deha).")

    jd = utils.julian_day_number(dob, tob)

    year_duration = drik.dhasa_year_duration(
        jd=jd,
        place=place,
        dhasa_duration_type=dhasa_duration_type,
        savana_year_method=savana_year_method,
    )

    tribhagi_factor = 1.0
    dhasa_cycles = 1

    if use_tribhagi_variation:
        tribhagi_factor = 1.0 / 3.0
        dhasa_cycles = int(dhasa_cycles / tribhagi_factor)

    dhasa_lord, start_jd, _ = _dhasa_start(jd, place)

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


def karana_chathuraaseethi_sama_immediate_children(
    parent_lords,
    parent_start,
    parent_duration=None,
    parent_end=None,
    *,
    jd_at_dob,
    place,
    antardhasa_option=1,
    dhasa_duration_type=None,
    savana_year_method=None,
    **kwargs,
):
    """
    Karana Chathuraaseethi Sama immediate children.

    Rules:
        - Child order via _antardhasa(parent_lord, antardhasa_option)
        - Equal split at this level
        - Last child end forced to parent_end

    Returns:
        [
            [lords_tuple_with_child, child_start_tuple, child_end_tuple],
            ...
        ]

    Note:
        This function intentionally returns start and end tuples because
        the running-dhasa navigator needs parent-child boundaries.
    """
    global year_duration

    year_duration = drik.dhasa_year_duration(
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

    n = len(child_lords)
    child_years = parent_years / n

    children = []
    cursor = start_jd

    for i, cl in enumerate(child_lords):
        child_start = cursor

        if i == n - 1:
            child_end = end_jd
        else:
            child_end = _next_jd_by_dhasa_years(
                child_start,
                child_years,
            )

        children.append(
            [
                path + (cl,),
                _jd_to_tuple(child_start),
                _jd_to_tuple(child_end),
            ]
        )

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
    antardhasa_option=1,
    use_tribhagi_variation=False,
    divisional_chart_factor=1,
    chart_method=1,
    round_duration=False,
    dhasa_duration_type=None,
    savana_year_method=None,
    **kwargs,
):
    """
    Karana Chathuraaseethi Sama runner.

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
            r
            for r in children_rows
            if not _is_zero_length(r[1], r[2], eps_seconds=eps_seconds)
        ]

        if not filtered:
            return []

        filtered.sort(key=lambda r: _tuple_to_jd(r[1]))

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
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        antardhasa_option=antardhasa_option,
        dhasa_level_index=const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
        round_duration=False,
        dhasa_duration_type=dhasa_duration_type,
        savana_year_method=savana_year_method,
    )

    maha_for_utils = []

    for row in maha_rows:
        lords_any = row[0]
        start_t = row[1]
        maha_for_utils.append((_as_tuple_lords(lords_any), start_t))

    running_all = []

    rd1 = utils.get_running_dhasa_for_given_date(
        current_jd,
        maha_for_utils,
    )

    lords1 = _as_tuple_lords(rd1[0])
    running = [lords1, rd1[1], rd1[2]]
    running_all.append(running)

    if target_depth == int(const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY):
        return running_all

    for depth in range(2, target_depth + 1):
        parent_lords, parent_start, parent_end = running

        children = karana_chathuraaseethi_sama_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            antardhasa_option=antardhasa_option,
            dhasa_duration_type=dhasa_duration_type,
            savana_year_method=savana_year_method,
            **kwargs,
        )

        if not children:
            running = [
                parent_lords + (parent_lords[-1],),
                parent_end,
                parent_end,
            ]
            running_all.append(running)
            continue

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

            lords_k = _as_tuple_lords(rdk[0])
            running = [lords_k, rdk[1], rdk[2]]

        running_all.append(running)

    return running_all

if __name__ == "__main__":
    utils.set_language("en")

    dob = drik.Date(1996, 12, 7)
    tob = (10, 34, 0)

    place = drik.Place("Chennai,IN", 13.0389, 80.2619, +5.5)

    jd_at_dob = utils.julian_day_number(dob, tob)
    for dd in const.DHASA_YEAR_DURATION:
        const.dhasa_year_duration_default = dd
        print(dd.name,get_dhasa_bhukthi(dob, tob, place, dhasa_level_index=1)[0])
    exit()

    from datetime import datetime
    import time

    current_date_str, current_time_str = datetime.now().strftime("%Y,%m,%d;%H:%M:%S").split(";")

    y, m, d = map(int, current_date_str.split(","))
    hh, mm, ss = map(int, current_time_str.split(":"))
    fh = hh + mm / 60 + ss / 3600

    print(utils.date_time_tuple_to_date_time_string(y, m, d, fh))

    current_jd = utils.julian_day_number(drik.Date(y, m, d), (hh, mm, ss))

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
            "Deha:",
            get_running_dhasa_for_given_date(
                current_jd,
                jd_at_dob,
                place,
                dhasa_level_index=const.MAHA_DHASA_DEPTH.DEHA,
                dhasa_duration_type=dd,
            ),
        )

        print("new method elapsed time", time.time() - start_time)

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
            )
        )

        print("old method elapsed time", time.time() - start_time)

    exit()

    from jhora.tests import pvr_tests

    const.use_24hour_format_in_to_dms = False
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.karana_chathuraseethi_sama_test()
# Modified by Sundar Sundaresan, USA. carnaticmusicguru2015@comcast.net
# Downloaded from https://github.com/naturalstupid/PyJHora

# This file is part of the "PyJHora" Python library
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# at your option any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
