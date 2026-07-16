"""Classical reference tables + pure helpers for the Nakshatra-profile (§5.7) and
Gochara-phala-with-vedha (§5.6) features.

These are well-established, traditional Jyotish tables (janma-nakshatra
attributes; the Moon-referenced gochara result houses and their vedha
obstructions). They carry no engine dependency — `astrology.py` gathers the live
chart data (Moon's nakshatra, current transit signs) and calls the helpers here,
so the data stays testable in isolation.
"""

from typing import Dict, List, Any

# --------------------------------------------------------------------------- #
# §5.7  Nakshatra attributes (0-based: Ashwini .. Revati)
# --------------------------------------------------------------------------- #
NAKSHATRA_NAMES = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada",
    "Revati",
]

# Presiding deity per nakshatra.
NAKSHATRA_DEITY = [
    "Ashwini Kumaras", "Yama", "Agni", "Brahma (Prajapati)", "Soma (Chandra)",
    "Rudra", "Aditi", "Brihaspati", "Nagas (Sarpas)", "Pitris (Ancestors)",
    "Bhaga", "Aryaman", "Savitar (Surya)", "Tvashtar (Vishwakarma)", "Vayu",
    "Indra-Agni", "Mitra", "Indra", "Nirriti", "Apas (Waters)",
    "Vishwadevas", "Vishnu", "Ashta Vasus", "Varuna", "Aja Ekapada",
    "Ahir Budhnya", "Pushan",
]

# Iconic symbol.
NAKSHATRA_SYMBOL = [
    "Horse's head", "Yoni (female organ)", "Razor / flame", "Ox-cart / chariot",
    "Deer's head", "Teardrop / diamond", "Bow and quiver", "Cow's udder / lotus",
    "Coiled serpent", "Royal throne", "Front legs of a bed / hammock",
    "Back legs of a bed", "Hand / closed fist", "Bright jewel / pearl",
    "Young shoot swaying in the wind / coral", "Triumphal archway / potter's wheel",
    "Lotus", "Circular amulet / earring", "Bunch of tied roots",
    "Elephant tusk / fan", "Elephant tusk / small bed / planks", "Ear / three footprints",
    "Drum (mridanga) / flute", "Empty circle / 100 physicians",
    "Sword / front legs of a funeral cot", "Twins / back legs of a funeral cot",
    "Pair of fish / drum",
]

# Gana — temperament class.
NAKSHATRA_GANA = [
    "Deva", "Manushya", "Rakshasa", "Manushya", "Deva", "Manushya", "Deva",
    "Deva", "Rakshasa", "Rakshasa", "Manushya", "Manushya", "Deva", "Rakshasa",
    "Deva", "Rakshasa", "Deva", "Rakshasa", "Rakshasa", "Manushya", "Manushya",
    "Deva", "Rakshasa", "Rakshasa", "Manushya", "Manushya", "Deva",
]

# Nadi (dosha / ayurvedic constitution) — Aadi (Vata) / Madhya (Pitta) / Antya (Kapha).
NAKSHATRA_NADI = [
    "Aadi (Vata)", "Madhya (Pitta)", "Antya (Kapha)", "Antya (Kapha)",
    "Madhya (Pitta)", "Aadi (Vata)", "Aadi (Vata)", "Madhya (Pitta)",
    "Antya (Kapha)", "Antya (Kapha)", "Madhya (Pitta)", "Aadi (Vata)",
    "Aadi (Vata)", "Madhya (Pitta)", "Antya (Kapha)", "Antya (Kapha)",
    "Madhya (Pitta)", "Aadi (Vata)", "Aadi (Vata)", "Madhya (Pitta)",
    "Antya (Kapha)", "Antya (Kapha)", "Madhya (Pitta)", "Aadi (Vata)",
    "Aadi (Vata)", "Madhya (Pitta)", "Antya (Kapha)",
]

# Yoni (animal) + its polarity, used for sexual/temperamental compatibility.
NAKSHATRA_YONI = [
    "Horse (M)", "Elephant (M)", "Sheep (F)", "Serpent (M)", "Serpent (F)",
    "Dog (F)", "Cat (F)", "Sheep (M)", "Cat (M)", "Rat (M)", "Rat (F)",
    "Cow (M)", "Buffalo (F)", "Tiger (F)", "Buffalo (M)", "Tiger (M)",
    "Deer (F)", "Deer (M)", "Dog (M)", "Monkey (M)", "Mongoose (F)",
    "Monkey (F)", "Lion (F)", "Horse (F)", "Lion (M)", "Cow (F)", "Elephant (F)",
]

# Guna (quality) — Sattva / Rajas / Tamas, the primary spiritual mode.
NAKSHATRA_GUNA = [
    "Rajas", "Rajas", "Rajas", "Rajas", "Tamas", "Tamas", "Sattva", "Sattva",
    "Sattva", "Tamas", "Rajas", "Rajas", "Rajas", "Tamas", "Tamas", "Sattva",
    "Tamas", "Sattva", "Tamas", "Rajas", "Rajas", "Rajas", "Tamas", "Tamas",
    "Sattva", "Sattva", "Sattva",
]

# The four naming syllables (Chandra naamakshara), one per pada (1-4).
NAKSHATRA_SYLLABLES = [
    ["Chu", "Che", "Cho", "La"], ["Li", "Lu", "Le", "Lo"],
    ["A", "Ee", "U", "Ea"], ["O", "Va", "Vi", "Vu"], ["Ve", "Vo", "Ka", "Ki"],
    ["Ku", "Gha", "Nga", "Chha"], ["Ke", "Ko", "Ha", "Hi"],
    ["Hu", "He", "Ho", "Da"], ["Dee", "Doo", "De", "Do"], ["Ma", "Mi", "Mu", "Me"],
    ["Mo", "Ta", "Ti", "Tu"], ["Te", "To", "Pa", "Pi"], ["Pu", "Sha", "Na", "Tha"],
    ["Pe", "Po", "Ra", "Ri"], ["Ru", "Re", "Ro", "Ta"], ["Ti", "Tu", "Te", "To"],
    ["Na", "Ni", "Nu", "Ne"], ["No", "Ya", "Yi", "Yu"], ["Ye", "Yo", "Bha", "Bhi"],
    ["Bhu", "Dha", "Pha", "Dha"], ["Bhe", "Bho", "Ja", "Ji"],
    ["Ju", "Je", "Jo", "Kha"], ["Ga", "Gi", "Gu", "Ge"], ["Go", "Sa", "Si", "Su"],
    ["Se", "So", "Da", "Di"], ["Du", "Tha", "Jha", "Tra"], ["De", "Do", "Cha", "Chi"],
]

# Short evocative theme per nakshatra (layman one-liner).
NAKSHATRA_THEME = [
    "Swift healing, fresh starts and pioneering energy",
    "Restraint, transformation and creative struggle",
    "Sharp focus, purifying fire and determination",
    "Growth, beauty, fertility and sensual comfort",
    "Searching, curiosity and gentle questing",
    "Storms, breakthrough and emotional intensity",
    "Renewal, return, safety and boundless nurture",
    "Nourishment, care, prosperity and steadiness",
    "Penetrating insight, cunning and hidden depths",
    "Ancestry, tradition, authority and pride",
    "Pleasure, romance, relaxation and play",
    "Service, contracts, patronage and generosity",
    "Skill of the hands, craft and clever manifestation",
    "Artistry, design, brilliance and structured beauty",
    "Independence, movement, diplomacy and adaptability",
    "Ambition, focus, devotion and single-minded drive",
    "Friendship, balance, devotion and cooperation",
    "Seniority, courage, protection and hidden power",
    "Roots, upheaval, investigation and destruction-to-renew",
    "Invincibility, early vigour and purposeful advance",
    "Lasting victory, integrity and unshakable resolve",
    "Learning, listening, connection and wisdom",
    "Wealth, rhythm, music and generous abundance",
    "Healing, mysticism, veiling and independence",
    "Deep vision, sacrifice, austerity and idealism",
    "Depth, patience, cosmic support and steadiness",
    "Completion, nourishment, safe passage and kindness",
]

# Ruling planet per nakshatra (Vimsottari lord), 0-based.
NAKSHATRA_LORD = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn",
    "Mercury", "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter",
    "Saturn", "Mercury", "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu",
    "Jupiter", "Saturn", "Mercury",
]

# Varna from Moon's sign (0-based rasi Aries..Pisces) — the Ashtakoot varna axis.
_RASI_VARNA = [
    "Kshatriya", "Vaishya", "Shudra", "Brahmin", "Kshatriya", "Vaishya",
    "Shudra", "Brahmin", "Kshatriya", "Vaishya", "Shudra", "Brahmin",
]


def nakshatra_profile(nak_index: int, pada: int, moon_rasi: int) -> Dict[str, Any]:
    """Static janma-nakshatra attributes. `nak_index` 0-based (0=Ashwini),
    `pada` 1-4, `moon_rasi` 0-based (for varna)."""
    i = nak_index % 27
    p = max(1, min(4, pada))
    return {
        "name": NAKSHATRA_NAMES[i],
        "index": i + 1,
        "pada": p,
        "lord": NAKSHATRA_LORD[i],
        "deity": NAKSHATRA_DEITY[i],
        "symbol": NAKSHATRA_SYMBOL[i],
        "gana": NAKSHATRA_GANA[i],
        "yoni": NAKSHATRA_YONI[i],
        "nadi": NAKSHATRA_NADI[i],
        "guna": NAKSHATRA_GUNA[i],
        "varna": _RASI_VARNA[moon_rasi % 12],
        "theme": NAKSHATRA_THEME[i],
        "naming_syllable": NAKSHATRA_SYLLABLES[i][p - 1],
        "all_syllables": NAKSHATRA_SYLLABLES[i],
    }


# --------------------------------------------------------------------------- #
# §5.6  Gochara-phala (Moon-referenced transit results) + vedha (obstruction)
# --------------------------------------------------------------------------- #
# Favourable houses counted from the natal Moon (1 = Moon's own sign) for each
# transiting graha. A transit landing on one of these houses gives its good
# result *unless* another graha occupies that house's vedha (obstruction) point.
GOCHARA_GOOD_HOUSES: Dict[str, List[int]] = {
    "Sun":     [3, 6, 10, 11],
    "Moon":    [1, 3, 6, 7, 10, 11],
    "Mars":    [3, 6, 11],
    "Mercury": [2, 4, 6, 8, 10, 11],
    "Jupiter": [2, 5, 7, 9, 11],
    "Venus":   [1, 2, 3, 4, 5, 8, 9, 11, 12],
    "Saturn":  [3, 6, 11],
    "Rahu":    [3, 6, 11],
    "Ketu":    [3, 6, 11],
}

# For each planet, the vedha (obstructing) house for each of its favourable
# houses. If another planet sits in the vedha house, the good result is annulled.
GOCHARA_VEDHA: Dict[str, Dict[int, int]] = {
    "Sun":     {3: 9, 6: 12, 10: 4, 11: 5},
    "Moon":    {1: 5, 3: 9, 6: 12, 7: 2, 10: 4, 11: 8},
    "Mars":    {3: 12, 6: 9, 11: 5},
    "Mercury": {2: 5, 4: 3, 6: 9, 8: 1, 10: 8, 11: 12},
    "Jupiter": {2: 12, 5: 4, 7: 3, 9: 10, 11: 8},
    "Venus":   {1: 8, 2: 7, 3: 1, 4: 10, 5: 9, 8: 5, 9: 11, 11: 6, 12: 3},
    "Saturn":  {3: 12, 6: 9, 11: 5},
    "Rahu":    {3: 12, 6: 9, 11: 5},
    "Ketu":    {3: 12, 6: 9, 11: 5},
}

# Classical mutual-vedha exceptions: these pairs never obstruct each other.
_VEDHA_EXEMPT = [{"Sun", "Saturn"}, {"Moon", "Mercury"}, {"Jupiter", "Venus"}]

_GOCHARA_ORDER = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus",
                  "Saturn", "Rahu", "Ketu"]


def _house_from(moon_rasi: int, rasi: int) -> int:
    """1-based house of `rasi` counted from the Moon's sign (both 0-based)."""
    return ((rasi - moon_rasi) % 12) + 1


def gochara_phala(moon_rasi: int, transit_rasi: Dict[str, int]) -> List[Dict[str, Any]]:
    """Moon-referenced gochara verdict per graha.

    `moon_rasi`   — natal Moon's 0-based sign.
    `transit_rasi`— {planet_name: current 0-based sign}.

    Returns one row per planet: the house-from-Moon it transits, whether that is
    a classically favourable position, and — if favourable — whether a vedha
    (another graha in the obstruction house) cancels the good result.
    """
    # Which house-from-Moon each planet currently occupies.
    house_of = {p: _house_from(moon_rasi, r) for p, r in transit_rasi.items()}
    rows: List[Dict[str, Any]] = []
    for planet in _GOCHARA_ORDER:
        if planet not in house_of:
            continue
        house = house_of[planet]
        good_houses = GOCHARA_GOOD_HOUSES.get(planet, [])
        is_good = house in good_houses
        vedha_house = GOCHARA_VEDHA.get(planet, {}).get(house) if is_good else None
        obstructors: List[str] = []
        if vedha_house is not None:
            for other, oh in house_of.items():
                if other == planet or oh != vedha_house:
                    continue
                if {planet, other} in _VEDHA_EXEMPT:
                    continue  # friendly pair — no mutual vedha
                obstructors.append(other)

        if is_good and not obstructors:
            verdict, tone = "Favourable", "good"
        elif is_good and obstructors:
            verdict, tone = "Favourable but obstructed (vedha)", "caution"
        else:
            verdict, tone = "Unfavourable", "bad"

        rows.append({
            "planet": planet,
            "house_from_moon": house,
            "favourable_position": is_good,
            "vedha_house": vedha_house,
            "obstructed_by": obstructors,
            "verdict": verdict,
            "tone": tone,
        })
    return rows
