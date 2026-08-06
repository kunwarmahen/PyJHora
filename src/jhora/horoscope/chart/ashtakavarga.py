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
        V4.8.9
             - added rasimana multipler option - because PVR Book differs from other sources
             - PVR book is missing 3c rule in _ekadhipatya_sodhana which is added
             - with these changes PVR example results are matching now
"""
import numpy as np
from jhora import const, utils

planet_list = ['sun','moon','mars','mercury','jupiter','venus','saturn','lagnam']
raasi_list=['Mesham','Rishabam','Mithunam','Katakam','Simmam','Kanni','Thulaam','Vrichigam','Dhanusu','Makaram','Kumbam','Meenam']
raasi_index = lambda planet,planet_positions_in_chart: [i for i,raasi in enumerate(planet_positions_in_chart) if planet !=const._ascendant_symbol and planet.lower() in raasi.lower() ][0]
def get_ashtaka_varga(house_to_planet_list, 
                      reverse_ashtakavarga=None,
                      consolidate_houses=None,
                      include_lagna_as_planet=None,
                      moon_benefic_9_from_moon=None,
                      moon_malefic_9_from_mars=None,
                      moon_benefic_2_from_jupiter=None,
                      moon_malefic_12_from_jupiter=None,
                      venus_benefic_4_from_mars=None,
                      venus_malefic_5_from_mars=None):
    """
        get binna, samudhaya and prastara varga from the given horoscope chart
        @param house_to_planet_list: 1-D array [0..11] with planets in each raasi
            Example: ['','','','','2','7','1/5','0','3/4','L','','6/8']
        @return: 
            binna_ashtaka_varga - 2-D List [0..7][0..7] 0=Sun..7=Lagnam
            samudhaya ashtaka varga - 1D List [0..11] 0=Aries 11=Pisces
            prastara ashtaka varga - 3D List [0..7][0..7][0..11]
    """
    if reverse_ashtakavarga is None:
        reverse_ashtakavarga = getattr(const, 'ashtakavarga_reverse_ashtakavarga', False)
    if consolidate_houses is None:
        consolidate_houses = getattr(const, 'ashtakavarga_consolidate_houses', False)
    if include_lagna_as_planet is None:
        include_lagna_as_planet = getattr(const, 'ashtakavarga_include_lagna_as_planet', False)
        
    if moon_benefic_9_from_moon is None:
        moon_benefic_9_from_moon = getattr(const, 'p_v_moon_benefic_9_from_moon',True)
    if moon_malefic_9_from_mars is None:
        moon_malefic_9_from_mars = getattr(const, 'p_v_moon_malefic_9_from_mars',True)
    if moon_benefic_2_from_jupiter is None:
        moon_benefic_2_from_jupiter = getattr(const, 'p_v_moon_benefic_2_from_jupiter',True)
    if moon_malefic_12_from_jupiter is None:
        moon_malefic_12_from_jupiter = getattr(const, 'p_v_moon_malefic_12_from_jupiter',True)
    if venus_benefic_4_from_mars is None:
        venus_benefic_4_from_mars = getattr(const, 'p_v_venus_benefic_4_from_mars',True)
    if venus_malefic_5_from_mars is None:
        venus_malefic_5_from_mars = getattr(const, 'p_v_venus_malefic_5_from_mars',True)

    p_to_h = utils.get_planet_to_house_dict_from_chart(house_to_planet_list)
    raasi_ashtaka = [[0 for r in range(12)] for p in range(8)] # Sun..Saturn, Lagnam
    prastara_ashtaka_varga = [[[0 for r in range(12)] for p1 in range(10)] for p2 in range(8)]
    
    working_dict = {k: [list(lst) for lst in v] for k, v in const.ashtaka_varga_dict.items()}
    
    moon_key = str(const.MOON_ID)
    venus_key = str(const.VENUS_ID)
    
    # Rule A: Moon is benefic in the 9th from Moon
    if moon_benefic_9_from_moon:
        if 9 not in working_dict[moon_key][const.MOON_ID]:
            working_dict[moon_key][const.MOON_ID].append(9)
            working_dict[moon_key][const.MOON_ID].sort()
    else:
        if 9 in working_dict[moon_key][const.MOON_ID]:
            working_dict[moon_key][const.MOON_ID].remove(9)
            
    # Rule B: Moon is malefic in the 9th from Mars
    if moon_malefic_9_from_mars:
        if 9 in working_dict[moon_key][const.MARS_ID]:
            working_dict[moon_key][const.MARS_ID].remove(9)
    else:
        if 9 not in working_dict[moon_key][const.MARS_ID]:
            working_dict[moon_key][const.MARS_ID].append(9)
            working_dict[moon_key][const.MARS_ID].sort()
            
    # Rule C: Moon is benefic in the 2nd from Jupiter
    if moon_benefic_2_from_jupiter:
        if 2 not in working_dict[moon_key][const.JUPITER_ID]:
            working_dict[moon_key][const.JUPITER_ID].append(2)
            working_dict[moon_key][const.JUPITER_ID].sort()
    else:
        if 2 in working_dict[moon_key][const.JUPITER_ID]:
            working_dict[moon_key][const.JUPITER_ID].remove(2)
            
    # Rule D: Moon is malefic in the 12th from Jupiter (so 12 is missing in Parashari if malefic)
    if moon_malefic_12_from_jupiter:
        if 12 in working_dict[moon_key][const.JUPITER_ID]:
            working_dict[moon_key][const.JUPITER_ID].remove(12)
    else:
        if 12 not in working_dict[moon_key][const.JUPITER_ID]:
            working_dict[moon_key][const.JUPITER_ID].append(12)
            working_dict[moon_key][const.JUPITER_ID].sort()
            
    # Rule E: Venus is benefic in the 4th from Mars
    if venus_benefic_4_from_mars:
        if 4 not in working_dict[venus_key][const.MARS_ID]:
            working_dict[venus_key][const.MARS_ID].append(4)
            working_dict[venus_key][const.MARS_ID].sort()
    else:
        if 4 in working_dict[venus_key][const.MARS_ID]:
            working_dict[venus_key][const.MARS_ID].remove(4)
            
    # Rule F: Venus is malefic in the 5th from Mars (so 5 is missing in Parashari if malefic)
    if venus_malefic_5_from_mars:
        if 5 in working_dict[venus_key][const.MARS_ID]:
            working_dict[venus_key][const.MARS_ID].remove(5)
    else:
        if 5 not in working_dict[venus_key][const.MARS_ID]:
            working_dict[venus_key][const.MARS_ID].append(5)
            working_dict[venus_key][const.MARS_ID].sort()

    # 2. Map values into the BAV and Prastara Arrays
    for key in working_dict.keys():
        p = int(key)
        planet_raasi_list = working_dict[key]
        for op, other_planet in enumerate(planet_raasi_list):
            if op == 7:  # Lagnam
                pr = p_to_h[const._ascendant_symbol]
            else:
                pr = p_to_h[op]
    
            for raasi in other_planet:
                r = (raasi - 1 + pr) % 12
                if reverse_ashtakavarga:
                    raasi_ashtaka[op][r] += 1
                    prastara_ashtaka_varga[op][p][r] = 1
                    prastara_ashtaka_varga[op][-1][r] += 1
                else:
                    raasi_ashtaka[p][r] += 1
                    prastara_ashtaka_varga[p][op][r] = 1
                    prastara_ashtaka_varga[p][-1][r] += 1
                    
    binna_ashtaka_varga = raasi_ashtaka[0:8][:]
    prastara_ashtaka_varga = prastara_ashtaka_varga[0:8][0:9][:]
    
    # 3. Dynamic adjustment for collective SAV calculations 
    limit = 8 if include_lagna_as_planet else 7
    
    if consolidate_houses:
        samudhaya_ashtaka_varga = []
        for h in range(12):
            house_sum = 0
            for p_idx in range(limit):
                ph = p_to_h[const._ascendant_symbol] if p_idx == 7 else p_to_h[p_idx]
                r = (h + ph) % 12
                house_sum += binna_ashtaka_varga[p_idx][r]
            samudhaya_ashtaka_varga.append(house_sum)
    else:
        samudhaya_ashtaka_varga = np.asarray(binna_ashtaka_varga[:limit]).sum(axis=0).tolist()
        
    return binna_ashtaka_varga, samudhaya_ashtaka_varga, prastara_ashtaka_varga

def _trikona_sodhana(binna_ashtaka_varga):
    bav = binna_ashtaka_varga[:]
    for p in const.SUN_TO_SATURN:
        for r in range(4):
            if bav[p][r+const.HOUSE_1]==0 or bav[p][r+const.HOUSE_5]==0 or bav[p][r+const.HOUSE_9]==0:
                #print('Rule 1:If atleast one rasi has zero, no reduction is necessary.',p,r,bav[p][r],bav[p][r+4],bav[p][r+8])
                continue
            elif bav[p][r+const.HOUSE_1]==bav[p][r+const.HOUSE_5] and bav[p][r+const.HOUSE_5]==bav[p][r+const.HOUSE_9]:
                #print('Rule (2) If the three rasis have the same value, make them all zero.',p,r,bav[p][r],bav[p][r+4],bav[p][r+8])
                bav[p][r+const.HOUSE_1]=0
                bav[p][r+const.HOUSE_5]=0
                bav[p][r+const.HOUSE_9]=0
            else:
                #print('Rule (3) Take the lowest value out of the three. Subtract it from all the values.',p,r,bav[p][r],bav[p][r+4],bav[p][r+8])
                min_value = min([bav[p][r+const.HOUSE_1],bav[p][r+const.HOUSE_5],bav[p][r+const.HOUSE_9]])
                #print('before',p,r,min_value,bav[p][r],bav[p][r+4],bav[p][r+8])
                bav[p][r+const.HOUSE_1] -= min_value
                bav[p][r+const.HOUSE_5] -= min_value
                bav[p][r+const.HOUSE_9] -= min_value
                #print('after',p,r,min_value,bav[p][r],bav[p][r+4],bav[p][r+8])
    return bav
def _ekadhipatya_sodhana(binna_ashtaka_varga_after_trikona, chart_1d):
    """
        V4.8.9 - Changes per Issue #52 from "Askthesages"

        Note:
        In Ekaadhipatya Sodhana Rule (3), the printed text commonly states:
          - if the empty rasi has a lower value -> set it to 0
          - if the empty rasi has a higher value -> set it equal to the occupied rasi
        but it does not explicitly mention the equal-value case.

        Following several secondary Ekadhipatya references, when one rasi is occupied
        and the other is empty, and both have equal values, the empty rasi is also
        reduced to zero. This reproduces the published Chart 7 SoAV/Sodhya-Pinda
        values when used with the alternate Rasimana multipliers. 
        See e.g. Horosoft / AstroVastuTips style explanations of Ekadhipatya Shodhana.
    """
    bav = [row[:] for row in binna_ashtaka_varga_after_trikona]

    rasi_owners = const.ashtakavarga_rasi_owners
    dual_pairs = [x for x in rasi_owners if isinstance(x, tuple)]  # the 5 co-owned (r1,r2) pairs

    for p, (r1, r2) in [(_p, _pr) for _p in const.SUN_TO_SATURN for _pr in dual_pairs]:
        r1_occupied = not (chart_1d[r1].strip() == '')
        r2_occupied = not (chart_1d[r2].strip() == '')

        # Rule 1: if either rasi has zero, no reduction.
        # Rule 2: if both rasis are occupied, no reduction.
        if (bav[p][r1] == 0 or bav[p][r2] == 0) or (r1_occupied and r2_occupied):
            continue

        elif (not r1_occupied) and (not r2_occupied):  # Rule 4 - both rasis empty
            # Rule 4(b): if different, replace the higher value with the lower value.
            if bav[p][r1] != bav[p][r2]:
                min_value = min(bav[p][r1], bav[p][r2])
                bav[p][r1] = min_value
                bav[p][r2] = min_value
            # Rule 4(a): if equal, replace both with zero.
            else:
                bav[p][r1] = 0
                bav[p][r2] = 0

        else:
            # Rule 3: one rasi occupied, the other empty.
            # The PVR Book lists only "lower" and "higher" cases for the empty rasi
            # and omits the equal-value case.
            #
            # Following secondary Ekadhipatya references, if the occupied and empty
            # rasis have equal values, the empty rasi is also reduced to zero.
            # In short:
            #   empty < occupied  -> empty = 0
            #   empty = occupied  -> empty = 0
            #   empty > occupied  -> empty = occupied

            if r1_occupied:  # r2 is empty
                if bav[p][r2] <= bav[p][r1]:
                    bav[p][r2] = 0
                else:
                    bav[p][r2] = bav[p][r1]

            else:  # r1 is empty
                if bav[p][r1] <= bav[p][r2]:
                    bav[p][r1] = 0
                else:
                    bav[p][r1] = bav[p][r2]

    return bav

def _get_planet_positions(chart_1d):
    planet_houses = [-1 for p in const.SUN_TO_SATURN]
    for p,planet in enumerate(planet_list[0:-1]): # Excluding Lagnam
        for house,rasi in enumerate(chart_1d):
            if planet.lower() in rasi.lower():
                planet_houses[p] = house
                break
    return planet_houses
def _sodhya_pindas(binna_ashtaka_varga_after_ekadhipatya, chart_1d, rasimana_option=None):
    if rasimana_option is None:
        rasimana_multipliers = const.ashtakavarga_rasimana_multipliers
    elif rasimana_option in (
        const.RASIMANA_MULTIPLIER_OPTION.RASIMANA_ALTERNATE,
        const.RASIMANA_MULTIPLIER_OPTION.RASIMANA_PVR
    ):
        rasimana_multipliers = const.RASIMANA_MULTIPLIERS[rasimana_option]
    else:
        raise ValueError(
            f"rasimana_option {rasimana_option} should be one of "
            f"const.RASIMANA_MULTIPLIER_OPTION.RASIMANA_PVR or "
            f"const.RASIMANA_MULTIPLIER_OPTION.RASIMANA_ALTERNATE"
        )
    grahamana_multipliers = const.ashtakavarga_grahamana_multipliers

    bav = [row[:] for row in binna_ashtaka_varga_after_ekadhipatya]
    raasi_pindas = [0 for _ in const.SUN_TO_SATURN]
    graha_pindas = [0 for _ in const.SUN_TO_SATURN]
    sodhya_pindas = [0 for _ in const.SUN_TO_SATURN]

    p_to_h = utils.get_planet_to_house_dict_from_chart(chart_1d)

    for p in const.SUN_TO_SATURN:
        raasi_pindas[p] = int(sum(np.multiply(bav[p], rasimana_multipliers)))
        graha_pindas[p] = sum(
            grahamana_multipliers[rp] * bav[p][p_to_h[rp]]
            for rp in const.SUN_TO_SATURN
        )
        sodhya_pindas[p] = raasi_pindas[p] + graha_pindas[p]

    return raasi_pindas, graha_pindas, sodhya_pindas

def sodhaya_pindas(binna_ashtaka_varga,house_to_planet_chart, rasimana_option=None):
    """
        Get sodhaya pindas from binna ashtaka varga
        @param param:binna_ashtaka_varga - 2-D List [0..7][0..7] 0=Sun..7=Lagnam - of BAV values
        NOTE: To pass binn ashtaka varga as parameter - you need to get it from get_ashtaka_varga function
        @return: raasi_pindas,graha_pindas,sodhya_pindas
                raasi_pindas : raasi pindas of planets 0=Sun to 6=Saturn [0..6]
                graha_pindas : graha pindas of planets 0=Sun to 6=Saturn [0..6]
                sidhaya_pindas : sodhaya pindas of planets 0=Sun to 6=Saturn [0..6]
        NOTE: PVR Book gives Rasimana Multipliers as (7, 10, 8, 4, 10, 6, 7, 8, 9, 5, 11, 12)
            Whereas:
                Ref: 1. https://astrobix.com/learn/360-shodhya-pinda-of-ashtakavarga.html and
                     2. https://www.horosoft.net/learnastro_Zodiacal_Planetary_Products.html
                     gives Rasimana multipliers as (7, 10, 8, 4, 10, 5, 7, 8, 9, 5, 11, 12)
                Notice: Virgo multipler is 6 in PVR's book and is 5 in above references
    """
    if rasimana_option is None:
        rasimana_multipliers = const.ashtakavarga_rasimana_multipliers
    elif rasimana_option in (
        const.RASIMANA_MULTIPLIER_OPTION.RASIMANA_ALTERNATE,
        const.RASIMANA_MULTIPLIER_OPTION.RASIMANA_PVR
    ):
        rasimana_multipliers = const.RASIMANA_MULTIPLIERS[rasimana_option]
    else:
        raise ValueError(
            f"rasimana_option {rasimana_option} should be one of "
            f"const.RASIMANA_MULTIPLIER_OPTION.RASIMANA_PVR or "
            f"const.RASIMANA_MULTIPLIER_OPTION.RASIMANA_ALTERNATE"
        )

    binna_ashtaka_varga_after_trikona = _trikona_sodhana(binna_ashtaka_varga)
    #print('bav after trikona',binna_ashtaka_varga_after_trikona)
    binna_ashtaka_varga_after_ekadhipatya = _ekadhipatya_sodhana(binna_ashtaka_varga_after_trikona,house_to_planet_chart)
    """ binna_ashtaka_varga_after_ekadhipatya is called Sodhita Ashtakavarga"""
    #print('Sodhita Ashtakavarga\n',binna_ashtaka_varga_after_ekadhipatya)
    raasi_pindas,graha_pindas,sodhya_pindas = _sodhya_pindas(binna_ashtaka_varga_after_ekadhipatya,house_to_planet_chart,
                                                             rasimana_option=rasimana_option)
    return raasi_pindas,graha_pindas,sodhya_pindas
if __name__ == "__main__":
    from jhora.tests.pvr_tests import test_example
    # Chart 7 from the book
    chapter = 'Chaper 12.3 ashtaka_varga_tests'
    exercise = 'Exercise 22/Chart 7:'
    chart_7 = ['6/1/7','','','','','','8/4','L','3/2','0','5','']
    bav, sav,pav = get_ashtaka_varga(chart_7)
    bav_e = [[4,2,3,4,6,5,5,3,2,6,6,2],
             [6,3,5,3,5,5,6,3,3,4,4,2],
             [3,2,3,4,2,5,4,3,3,4,3,3],
             [4,6,4,3,4,7,4,5,6,3,5,3],
             [4,4,3,5,6,5,6,4,6,4,3,6],
             [3,5,5,4,6,2,3,6,5,2,7,4],
             [3,2,2,3,5,6,3,4,1,3,6,1]]
    test_example(chapter+exercise+' BAV',bav_e,bav[:-1])#,assert_result=True)
    sav_e = [27,24,25,26,34,35,31,28,26,26,34,21]
    test_example(chapter+exercise+' SAV',sav_e,sav)#,assert_result=True)
    sp_e_book = ([152,85,52,95,68,154,162],[81,55,43,33,56,54,63],[233,140,95,128,124,208,225])
    sp_e = ([155, 86, 55, 99, 93, 154, 166], [81, 55, 43, 33, 56, 54, 63], [236, 141, 98, 132, 149, 208, 229])
    sp = sodhaya_pindas(bav, chart_7)
    test_example(chapter+exercise+' Sodhaya Pindas',sp_e_book,sp)
    #print(chapter+exercise+' Sodhaya Pindas:\n NOTE: Not clear why this case SP failed to match the book\n'+
    #      ' Examples 40,41 & 42 based on Chart 12 are matching BAV, SAV and SP.\n So the calculations in this code is thus verified\n'+
    #      'Expected Values from Book:',sp_e_book)
