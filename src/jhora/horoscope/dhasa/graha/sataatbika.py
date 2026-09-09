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
from jhora import const, utils
from jhora.panchanga import drik
from jhora.horoscope.chart import charts


year_duration = const.sidereal_year

"""Applicability: Lagna in the same sign in rasi and navamsa."""

# seed_star = 27  # Revati
seed_lord = 0

# Total 100 years.
dhasa_adhipathi_list = {
    0: 5,
    1: 5,
    5: 10,
    3: 10,
    4: 20,
    2: 20,
    6: 30,
}

count_direction = 1


def applicability_check(dob, tob, place):
    """Lagna in the same sign in rasi and navamsa."""
    jd = utils.julian_day_number(dob, tob)

    lagna_rasi = charts.rasi_chart(jd, place)[0]

    lagna_navamsa = charts.divisional_chart(
        jd,
        place,
        divisional_chart_factor=9,
    )[0]

    return lagna_rasi[1][0] == lagna_navamsa[1][0]


def _next_adhipati(lord, dirn=1):
    """Returns next lord after lord in the adhipati list."""
    keys = list(dhasa_adhipathi_list.keys())
    current = keys.index(lord)
    next_lord = keys[(current + dirn) % len(keys)]

    return next_lord


def _get_dhasa_dict(seed_star=27):
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


def _maha_dhasa(nak, seed_star=27):
    dhasa_adhipathi_dict = _get_dhasa_dict(seed_star)

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


def _dhasa_start(
    jd,
    place,
    star_position_from_moon=1,
    divisional_chart_factor=1,
    chart_method=1,
    seed_star=27,
    dhasa_starting_planet=1,
):
    one_star = 360 / 27.0

    planet_long = charts.get_chart_element_longitude(
        jd=jd,
        place=place,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        star_position_from_moon=star_position_from_moon,
        dhasa_starting_planet=dhasa_starting_planet,
    )

    nak = int(planet_long / one_star)
    rem = planet_long - nak * one_star

    lord, res = _maha_dhasa(nak + 1, seed_star)
    fraction_elapsed = rem / one_star

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
    divisional_chart_factor=1,
    chart_method=1,
    star_position_from_moon=1,
    use_tribhagi_variation=False,
    seed_star=27,
    dhasa_starting_planet=1,
    antardhasa_option=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
    round_duration=True,
    dhasa_duration_type=None,
    savana_year_method=None,
):
    """
    Returns dhasa segments at the selected depth level.

    Return format:
        [
            [lords_tuple, start_tuple, duration_years],
            ...
        ]

    End JD is used internally only to calculate the next start JD.
    """
    utils.validate_star_index(seed_star)

    global year_duration

    if not (1 <= dhasa_level_index <= 6):
        raise ValueError("dhasa_level_index must be in 1..6.")

    tribhagi_factor = 1.0
    dhasa_cycles = 1

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
        star_position_from_moon=star_position_from_moon,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        seed_star=seed_star,
        dhasa_starting_planet=dhasa_starting_planet,
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
        durn = round(duration_years, dhasa_level_index) if round_duration else duration_years

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


def nakshathra_dhasa_progression(
    jd_at_dob,
    place,
    jd_current,
    star_position_from_moon=1,
    use_tribhagi_variation=False,
    divisional_chart_factor=1,
    chart_method=1,
    seed_star=27,
    antardhasa_option=1,
    dhasa_starting_planet=1,
    dhasa_level_index=const.MAHA_DHASA_DEPTH.ANTARA,
    get_running_dhasa=True,
    dhasa_duration_type=None,
    savana_year_method=None,
):
    """
    Nakshathra dhasa progression.

    For divisional charts:
        First calculate progression for rasi, then apply varga division
        to progressed rasi longitudes.
    """
    utils.validate_star_index(seed_star)

    y, m, d, fh = utils.jd_to_gregorian(jd_at_dob)
    dob = drik.Date(y, m, d)
    tob = (fh, 0, 0)

    DLI = dhasa_level_index

    vd = get_dhasa_bhukthi(
        dob,
        tob,
        place,
        star_position_from_moon=star_position_from_moon,
        use_tribhagi_variation=use_tribhagi_variation,
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        seed_star=seed_star,
        antardhasa_option=antardhasa_option,
        dhasa_starting_planet=dhasa_starting_planet,
        dhasa_level_index=DLI,
        dhasa_duration_type=dhasa_duration_type,
        savana_year_method=savana_year_method,
    )

    vdc = None

    if get_running_dhasa:
        vd_for_utils = [(row[0], row[1]) for row in vd]

        vdc = utils.get_running_dhasa_for_given_date(
            jd_current,
            vd_for_utils,
        )

        print(vdc)

    jds = [
        utils.julian_day_number(
            drik.Date(row[1][0], row[1][1], row[1][2]),
            (row[1][3], 0, 0),
        )
        for row in vd
    ]

    planet_long = charts.get_chart_element_longitude(
        jd_at_dob,
        place,
        divisional_chart_factor=1,
        chart_method=chart_method,
        star_position_from_moon=star_position_from_moon,
        dhasa_starting_planet=dhasa_starting_planet,
    )

    birth_star_index = int((planet_long % 360.0) // utils.ONE_NAK)

    prog_long = utils.progressed_abs_long_general(
        jds,
        jd_current,
        birth_star_index,
        dhasa_level_index=DLI,
        total_lords_in_dhasa=len(dhasa_adhipathi_list),
    )

    progression_correction = utils.norm360(prog_long - planet_long)

    if get_running_dhasa:
        return progression_correction, vdc

    return progression_correction


def sataatbika_immediate_children(
    parent_lords,
    parent_start,
    parent_duration=None,
    parent_end=None,
    jd_at_dob=None,
    place=None,
    antardhasa_option=1,
    star_position_from_moon=1,
    use_tribhagi_variation=False,
    divisional_chart_factor=1,
    chart_method=1,
    seed_star=27,
    dhasa_starting_planet=1,
    dhasa_duration_type=None,
    savana_year_method=None,
):
    """
    Sataatbika immediate children under the given parent span.

    Returns:
        [
            [lords_tuple_with_child, child_start_tuple, child_end_tuple],
            ...
        ]
    """
    utils.validate_star_index(seed_star)

    global year_duration

    if jd_at_dob is not None and place is not None:
        year_duration = drik.dhasa_year_duration(
            jd=jd_at_dob,
            place=place,
            dhasa_duration_type=dhasa_duration_type,
            savana_year_method=savana_year_method,
        )

    if place is None:
        raise ValueError("place is required for exact Sataatbika child boundary calculation.")

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
    cursor = start_jd

    for idx, cl in enumerate(child_lords):
        child_start = cursor

        if idx == len(child_lords) - 1:
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
    antardhasa_option=1,
    star_position_from_moon=1,
    use_tribhagi_variation=False,
    divisional_chart_factor=1,
    chart_method=1,
    seed_star=27,
    dhasa_starting_planet=1,
    round_duration=False,
    dhasa_duration_type=None,
    savana_year_method=None,
):
    """
    Sataatbika runner. Narrows Maha to requested depth.

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
    utils.validate_star_index(seed_star)

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
        divisional_chart_factor=divisional_chart_factor,
        chart_method=chart_method,
        star_position_from_moon=star_position_from_moon,
        use_tribhagi_variation=use_tribhagi_variation,
        seed_star=seed_star,
        dhasa_starting_planet=dhasa_starting_planet,
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

        children = sataatbika_immediate_children(
            parent_lords=parent_lords,
            parent_start=parent_start,
            parent_end=parent_end,
            jd_at_dob=jd_at_dob,
            place=place,
            antardhasa_option=antardhasa_option,
            star_position_from_moon=star_position_from_moon,
            use_tribhagi_variation=use_tribhagi_variation,
            divisional_chart_factor=divisional_chart_factor,
            chart_method=chart_method,
            seed_star=seed_star,
            dhasa_starting_planet=dhasa_starting_planet,
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
    for dd in const.DHASA_YEAR_DURATION:
        const.dhasa_year_duration_default = dd
        print(dd.name,get_dhasa_bhukthi(dob, tob, place, dhasa_level_index=1)[0])
    exit()
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
            )
        )
        print('old method elapsed time', time.time() - start_time)
    exit()
    from jhora.tests import pvr_tests
    pvr_tests._STOP_IF_ANY_TEST_FAILED = True
    pvr_tests.sataatbika_test()
