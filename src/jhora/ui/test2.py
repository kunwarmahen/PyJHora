#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# py -- routines for computing tithi, vara, etc.
#
# Copyright (C) 2013 Satish BD  <bdsatish@gmail.com>
# Downloaded from https://github.com/bdsatish/drik-panchanga
#
# This file is part of the "drik-panchanga" Python library
# for computing Hindu luni-solar calendar based on the Swiss ephemeris
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
# Copyright (C) Open Astro Technologies, USA.
# Modified by Sundar Sundaresan, USA. carnaticmusicguru2015@comcast.net
# Downloaded from https://github.com/naturalstupid/PyJHora
"""
    To calculate Rashmi Dhasa Bhukthu
"""
from jhora import const, utils
from jhora.horoscope.chart import charts
from jhora.panchanga import drik
MAX_RAYS = {0: 10, 1: 9, 2: 5, 3: 5, 4: 7, 5: 16, 6: 4}
one_year_duration = const.sidereal_year
vimsottari_adhipati = (
    lambda nak, seed_star=3: const.vimsottari_adhipati_list[
        (nak - seed_star + 3) % (len(const.vimsottari_adhipati_list))
    ]
)
def vimsottari_next_adhipati(lord, direction=1):
    """Returns next guy after `lord` in the adhipati_list"""
    current = const.vimsottari_adhipati_list.index(lord)
    next_index = (current + direction) % len(const.vimsottari_adhipati_list)
    return const.vimsottari_adhipati_list[next_index]

def get_rashmi_dhasa_bhuthi(
    dob, tob, place,
    divisional_chart_factor=1,
    years=1, months=1, sixty_hours=1,
    dhasa_level_index=2, 
    dhasa_method=1,      # 1=Highest Ray (BPHS), 2=Natural, 3=Vimshottari Order
    vimsottari_method_seed_star=3,
    max_cycles=10,
    use_real_combusion_limits = True,
):
    # --- 1. Constants & Tables (BPHS Canonical) ---
    MAX_RAYS = {0: 10, 1: 9, 2: 5, 3: 5, 4: 7, 5: 16, 6: 4}
    DEEP_EXALT = {0: 10, 1: 33, 2: 298, 3: 165, 4: 95, 5: 357, 6: 200}
    EXALT_SIGNS = {0: 0, 1: 1, 2: 9, 3: 5, 4: 3, 5: 11, 6: 6}
    OWNERS = {0: 2, 1: 5, 2: 3, 3: 1, 4: 0, 5: 3, 6: 5, 7: 2, 8: 4, 9: 6, 10: 6, 11: 4}
    VIM_LIST = const.vimsottari_adhipati_list
    ONE_YEAR_DAYS = 365.242199
    TARGET_SPAN = const.human_life_span_for_vimsottari_dhasa

    # --- 2. Initial Setup ---
    jd_birth = utils.julian_day_number(dob, tob)
    # Using your solar entry API
    jd_start = drik.next_solar_date(jd_birth, place, years, months, sixty_hours)
    
    d1_pos = charts.divisional_chart(jd_start, place, divisional_chart_factor)
    d9_pos = charts.divisional_chart(jd_start, place, 9)
    
    sun_z, sun_l = next(pos for p_id, pos in d1_pos if p_id == 0)
    sun_abs_lon = (sun_z * 30) + sun_l
    retro_planets = drik.planets_in_retrograde(jd_start, place)
    # --- 3. Shuddha Rashmi Calculation ---
    planet_rays = {}
    for p_id, (zod, lon) in d1_pos[const.SUN_ID+1:const._pp_count_upto_saturn]: # Sun to Saturn
        idx = p_id -1
        if use_real_combusion_limits:
            combusion_limit = const.combustion_range_of_planets_from_sun_while_in_retrogade[idx] if p_id in retro_planets else const.combustion_range_of_planets_from_sun[idx]
        else:
            combusion_limit = 8.0
        abs_lon = (zod * 30) + lon
        deb_lon = (DEEP_EXALT[p_id] + 180) % 360
        dist = abs(abs_lon - deb_lon)
        if dist > 180: dist = 360 - dist
        # Base Rays
        rays = (dist / 180.0) * MAX_RAYS[p_id]
        # MULTIPLIERS (As required by BPHS for "Real" Rashmi Dasa)
        d9_zod = next(z for pid, (z, l) in d9_pos if pid == p_id)
        if zod == EXALT_SIGNS[p_id]: 
            rays *= 2.0  # Exaltation Sign multiplier
        if zod == d9_zod: 
            rays *= 2.0  # Vargottama multiplier (can stack with Exaltation)
        elif zod == OWNERS.get(zod): 
            rays *= (4.0/3.0) # Own Sign multiplier (4/3)
        # REDUCTIONS
        if p_id != 0 and abs(abs_lon - sun_abs_lon) < combusion_limit:
            rays *= 0.5 # Combustion reduction
        planet_rays[p_id] = round(rays, 8)
    total_rays = sum(planet_rays.values())
    # --- 4. Determine Sequence Order & Balance ---
    balance_factor = 1.0
    if dhasa_method == 1:
        # BPHS: Highest Strength/Rays Starts
        order = sorted(planet_rays.keys(), key=lambda x: planet_rays[x], reverse=True)
    elif dhasa_method == 2:
        # Natural Naisargika Order (Sun to Saturn)
        order = const.SUN_TO_SATURN
    elif dhasa_method == 3:
        # Vimshottari Hybrid
        moon_z, moon_l = next(pos for p_id, pos in d1_pos if p_id == 1)
        moon_abs_lon = (moon_z * 30) + moon_l
        nak_val = moon_abs_lon / (360/27)
        # Determining start lord using your seed_star argument
        start_lord = VIM_LIST[(int(nak_val) - vimsottari_method_seed_star + 3) % len(VIM_LIST)]
        # Build order using your next_adhipati API
        order = [start_lord]
        for _ in range(len(VIM_LIST) - 1):
            order.append(vimsottari_next_adhipati(order[-1]))
        # Filter Rahu/Ketu as they have 0 rays
        order = [p for p in order if p in planet_rays and planet_rays[p] > 0]
        # Calculate Balance from Nakshatra percentage
        balance_factor = 1.0 - (nak_val - int(nak_val))
    # --- 5. Recursive Engine ---
    results = []
    total_duration_years = 0.0
    jd_tracker = jd_start

    def recurse_dasa(current_depth, parent_duration, lords_list, is_first_maha):
        nonlocal jd_tracker, total_duration_years
        
        for i, p_id in enumerate(order):
            if total_duration_years >= TARGET_SPAN: return 
            if current_depth == 1:
                duration = planet_rays.get(p_id, 0)
                # Apply balance factor only to the first lord in the first cycle
                if is_first_maha and i == 0:
                    duration *= balance_factor
            else:
                duration = parent_duration * (planet_rays.get(p_id, 0) / total_rays)
            if duration <= 0: continue
            new_lords = lords_list + [p_id]
            if current_depth == dhasa_level_index:
                y, m, d, fh = utils.jd_to_gregorian(jd_tracker)
                results.append([(y, m, d, fh)] + new_lords + [round(duration, 8)])
                jd_tracker += (duration * ONE_YEAR_DAYS)
                total_duration_years += duration
            else:
                recurse_dasa(current_depth + 1, duration, new_lords, False)
    # --- 6. Cycle Execution ---
    cycles = 0
    while total_duration_years < TARGET_SPAN and cycles < max_cycles:
        recurse_dasa(1, None, [], (cycles == 0))
        cycles += 1
        if total_rays <= 0: break 
    return results

if __name__ == "__main__":
    utils.set_language('en')
    dob = drik.Date(1996,12,7); tob = (10,34,0); place = drik.Place('Chennai,India',13.03862,80.261818,5.5)
    rd = get_rashmi_dhasa_bhuthi(dob, tob, place,dhasa_level_index=2,dhasa_method=1,use_real_combusion_limits=True)
    for row in rd:
        print(row)
    