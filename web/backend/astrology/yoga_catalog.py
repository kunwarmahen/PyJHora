"""Yoga detection: which of PyJHora's 284 combinations we run, how we label them,
and the handful of engine rules we correct.

Why this exists (investigated 2026-09-26 against the owner's and a second family chart's JHora
yoga tabs): `yoga.get_yoga_details` runs every entry in yoga_msgs_en.json — the
classical catalogue JHora shows, then BV Raman's house-by-house list from
*300 Important Combinations* (Matrunasa, Anapathya, Rogagrastha …). Many of the
latter are broad OR-clauses, so a chart averaged ~30 "yogas" (19-47 over 200
random charts) where JHora shows the teens, and the AI was told Matrunasa
(mother's early death) was present on 94% of charts.

So each yoga now carries:
  tier    "classical" — the catalogue JHora lists (PVR, *Vedic Astrology: An
          Integrated Approach*) — the first 96 entries of the message file
          (Chandra/Surya, Pancha Mahapurusha, Naabhasa, Gaja-Kesari … Harsha/
          Sarala/Vimala) plus the two Naabhasa sankhya yogas filed later (Yuga,
          Gola) and BVR's specific Dhana yogas, which JHora also lists.
          "extended"  — BV Raman's house-specific combinations. Still computed and
          shown on request, never sent to the AI.
  nature  "supportive" | "challenging" — so the UI and the AI can hold the
          afflicting ones at arm's length instead of stating them as facts.

Detection is language-independent (English keys) — see get_yogas.
"""
from .engine import yoga, charts, house, utils, const, drik

# ── Catalogue shape ────────────────────────────────────────────────────────

# Same yoga, same rule, second spelling further down the file. Dropping the
# second copy — JHora lists each once, and the old output showed both
# "Kedaara" and "Kedara" for the same four-sign spread.
DUPLICATE_KEYS = frozenset({
    "vallaki_yoga",   # = veenaa_yoga (7 signs)
    "dama_yoga",      # = daama_yoga (6 signs)
    "kedara_yoga",    # = kedaara_yoga (4 signs)
    "sula_yoga",      # = soola_yoga (3 signs)
})

CLASSICAL_KEYS = frozenset({
    # Surya / Chandra
    "vesi_yoga", "vosi_yoga", "ubhayachara_yoga", "nipuna_yoga",
    "sunaphaa_yoga", "anaphaa_yoga", "duradhara_yoga", "kemadruma_yoga",
    "chandra_mangala_yoga", "adhi_yoga",
    # Pancha Mahapurusha
    "ruchaka_yoga", "bhadra_yoga", "sasa_yoga", "maalavya_yoga", "hamsa_yoga",
    # Naabhasa — aasraya, dala, aakriti, sankhya
    "rajju_yoga", "musala_yoga", "nala_yoga", "srik_yoga", "maalaa_yoga",
    "sarpa_yoga", "gadaa_yoga", "sakata_yoga", "vihanga_yoga",
    "sringaataka_yoga", "hala_yoga", "vajra_yoga", "yava_yoga", "kamala_yoga",
    "vaapi_yoga", "yoopa_yoga", "sara_yoga", "ishu_yoga", "sakti_yoga",
    "danda_yoga", "nav_yoga", "naukaa_yoga", "koota_yoga", "chatra_yoga",
    "chaapa_yoga", "ardha_chandra_yoga", "chakra_yoga", "samudra_yoga",
    "veenaa_yoga", "daama_yoga", "paasa_yoga", "kedaara_yoga", "soola_yoga",
    "yuga_yoga", "gola_yoga",
    # Lagna / named yogas
    "subha_yoga", "asubha_yoga", "gaja_kesari_yoga", "guru_mangala_yoga",
    "amala_yoga", "parvata_yoga", "kaahala_yoga", "chaamara_yoga",
    "sankha_yoga", "bheri_yoga", "mridanga_yoga", "sreenaatha_yoga",
    "matsya_yoga", "koorma_yoga", "khadga_yoga", "kusuma_yoga",
    "kalaanidhi_yoga", "kalpadruma_yoga", "lagnaadhi_yoga",
    "hari_yoga", "hara_yoga", "brahma_yoga", "vishnu_yoga", "siva_yoga",
    "trilochana_yoga", "gouri_yoga", "chandikaa_yoga", "lakshmi_yoga",
    "saarada_yoga", "bhaarathi_yoga", "saraswathi_yoga", "amsaavatara_yoga",
    "devendra_yoga", "indra_yoga", "ravi_yoga", "bhaaskara_yoga",
    "kulavardhana_yoga", "vasumathi_yoga", "gandharva_yoga", "go_yoga",
    "vidyut_yoga", "chapa_yoga", "pushkala_yoga", "makuta_yoga", "jaya_yoga",
    "harsha_yoga", "sarala_yoga", "vimala_yoga",
    # Dhana (BVR 118-128 — the specific lagna/5th-house wealth combinations
    # JHora lists as "Dhana")
    "dhana_yoga_118", "dhana_yoga_119", "dhana_yoga_120", "dhana_yoga_121",
    "dhana_yoga_122", "dhana_yoga_123", "dhana_yoga_124", "dhana_yoga_125",
    "dhana_yoga_126", "dhana_yoga_127", "dhana_yoga_128",
})

# Afflicting combinations. Matched by prefix so the numbered BVR variants
# (dharidhra_yoga_144 … _153, matrunasa_yoga_198/_199 …) come along.
# tests/test_yoga_catalog.py pins the full classification against the engine's
# key list so a new upstream yoga can't land unlabelled.
_CHALLENGING_PREFIXES = (
    # classical
    "kemadruma_yoga", "sakata_yoga", "sarpa_yoga", "asubha_yoga", "paasa_yoga",
    "soola_yoga", "yuga_yoga", "gola_yoga",
    # BV Raman house-specific
    "vanchana_chora_bheethi_yoga", "dhur_yoga", "dharidhra_yoga",
    "rogagrastha_yoga", "krisanga_yoga", "dehasthoulya_yoga",
    "parihasaka_yoga", "asatyavadi_yoga", "jada_yoga", "mooka_yoga",
    "netranasa_yoga", "andha_yoga", "durmukha_yoga", "parannabhojana_yoga",
    "sraddhannabhuktha_yoga", "sarpaganda_yoga", "vakchalana_yoga",
    "vishaprayoga_yoga", "sodaranasa_yoga", "grihanasa_yoga",
    "bandhubhisthyaktha_yoga", "matrunasa_yoga", "kapata_yoga",
    "matru_satrutwa_yoga", "anapathya_yoga", "sarpasaapa_yoga",
    "pithru_saapa_sutakshaya_yoga", "maathru_saapa_sutakshaya_yoga",
    "bhraathru_saapa_sutakshaya_yoga", "pretha_saapa_yoga", "aputhra_yoga",
    "kaalanirdesat_puthranaasa_yoga", "buddhi_jada_yoga", "jara_yoga",
    "jarajaputra_yoga", "bahu_sthree_yoga", "bhaga_chumbana_yoga",
    "jananatpurvam_pitru_marana_yoga", "apakeerthi_yoga", "galakarna_yoga",
    "vrana_yoga", "sisnavyadhi_yoga", "kushtaroga_yoga", "kshayaroga_yoga",
    "bhandhana_yoga", "karascheda_yoga", "sirachcheda_yoga",
    "dhurmarana_yoga", "yuddha_marana_yoga", "pittharoga_yoga",
    "putrakalatraheena_yoga", "bharyasahavyabhichara_yoga",
    "vamsacheda_yoga", "guhyaroga_yoga", "angaheena_yoga",
    "swetakushta_yoga", "pisacha_grastha_yoga", "vaatharoga_yoga",
    "mathibhramana_yoga", "khalwata_yoga", "nishturabhashi_yoga",
    "rajabhrashta_yoga", "raja_bhanga_yoga",
)


def tier_of(key: str) -> str:
    return "classical" if key in CLASSICAL_KEYS else "extended"


def nature_of(key: str) -> str:
    return "challenging" if key.startswith(_CHALLENGING_PREFIXES) else "supportive"


def for_ai(result: dict) -> list:
    """The yogas an AI reading may see: the classical tier only.

    The extended BV Raman list is deliberately withheld — it is where the broad
    "mother's early death / childlessness / chronic illness" combinations live,
    and a model handed "Matrunasa Yoga is present" states it as fact however it
    is caveated. Each entry keeps its `nature` so the prompt can mark the
    challenging classical ones (Kemadruma, Sakata, Sarpa …).
    """
    if result.get("status") != "success":
        return []
    return [y for y in result.get("yogas", []) if y.get("tier") == "classical"]


# Upstream message text that contradicts its own rule. English only — the other
# languages carry their own translations of the (correct) rule.
DESCRIPTION_FIXES_EN = {
    # The code (correctly) checks Cancer, Jupiter's exaltation; the message
    # says Capricorn, his debilitation.
    "hamsa_yoga": "Jupiter is in a quadrant (1st, 4th, 7th or 10th) in Sagittarius, "
                  "Pisces or Cancer — his own or exaltation sign.",
}


# ── Benefic / malefic for yoga rules ───────────────────────────────────────
#
# `charts.benefics_and_malefics` (PVR's method) makes any Krishna-paksha Moon a
# malefic and turns Mercury malefic when joined by Rahu alone. a family chart's JHora
# (tithi 22, Mercury with Rahu in Sg) nevertheless shows Maalaa — benefics in
# three kendras, which only holds with that Moon and Mercury benefic — and no
# Asubha for a lagna holding Mercury + Rahu. What reproduces JHora:
#   * Moon — BV Raman (the source of this catalogue): "From the eighth day of
#     the bright half the Moon is full and strong. She is weak from the eighth
#     day of the dark half." So benefic for tithis 8-22 inclusive.
#   * Mercury — malefic only when joined by more of Sun/Mars/Saturn/weak Moon
#     than of benefics; the nodes do not taint him.
# Used only by the yoga rules we override below, not engine-wide.

def _yoga_benefics_malefics(jd, place, p_to_h):
    tithi = drik.tithi(jd, place)[0]
    moon_benefic = 8 <= tithi <= 22
    benefics = {const.JUPITER_ID, const.VENUS_ID}
    malefics = {const.SUN_ID, const.MARS_ID, const.SATURN_ID, const.RAHU_ID, const.KETU_ID}
    (benefics if moon_benefic else malefics).add(const.MOON_ID)
    me_sign = p_to_h[const.MERCURY_ID]
    with_me = [p for p in range(7) if p != const.MERCURY_ID and p_to_h[p] == me_sign]
    bad = sum(1 for p in with_me if p in malefics)
    good = sum(1 for p in with_me if p in benefics)
    (malefics if bad > good else benefics).add(const.MERCURY_ID)
    return benefics, malefics


class _Chart:
    """The Rasi chart in the shapes the rule helpers want, computed once."""

    def __init__(self, jd, place):
        self.jd, self.place = jd, place
        self.pp = charts.divisional_chart(jd, place, 1)[:const._pp_count_upto_ketu]
        self.chart_1d = utils.get_house_planet_list_from_planet_positions(self.pp)
        self.p_to_h = utils.get_planet_to_house_dict_from_chart(self.chart_1d)
        self.asc = self.p_to_h[const._ascendant_symbol]
        self.benefics, self.malefics = _yoga_benefics_malefics(jd, place, self.p_to_h)
        # the engine's own classification, for rules we fix but whose benefic
        # definition wasn't in question
        self.engine_benefics, self.engine_malefics = charts.benefics_and_malefics(jd, place, 1)

    def occupants(self, sign):
        return [p for p in range(9) if self.p_to_h[p] == sign]

    def house(self, n):
        """Sign index of the nth house from lagna (1-based)."""
        return (self.asc + n - 1) % 12

    def strength(self, p):
        return const.house_strengths_of_planets[p][self.p_to_h[p]]


# ── Rules we correct ───────────────────────────────────────────────────────

def _kendra_count(c, group):
    return sum(1 for n in (1, 4, 7, 10) if any(p in group for p in c.occupants(c.house(n))))


def _maalaa(c):
    """Naabhasa: benefics occupy three kendras."""
    return _kendra_count(c, c.benefics) == 3


def _sarpa(c):
    """Naabhasa: malefics occupy three kendras."""
    return _kendra_count(c, c.malefics) == 3


def _subha(c):
    return bool(yoga.__dict__["__subha_yoga_calculation"](
        c.chart_1d, set(c.benefics), set(c.malefics), False, True))


def _asubha(c):
    return bool(yoga._asubha_yoga_calculation(
        c.chart_1d, set(c.benefics), set(c.malefics), use_affliction_check=False))


def _amala(c):
    """Only natural benefics in the 10th from lagna or Moon. Upstream tests *any*
    benefic there, so a 10th holding Sun + Venus qualified."""
    for base in (c.asc, c.p_to_h[const.MOON_ID]):
        occ = c.occupants((base + 9) % 12)
        if occ and all(p in c.benefics for p in occ):
            return True
    return False


def _parvata(c):
    """JHora: "kendras have benefics, 7th and 8th have no malefics". Upstream
    demanded kendras hold ONLY benefics, which a Sun in lagna beside Mercury and
    Venus (owner's chart, where JHora shows Parvata) fails."""
    kendra_benefic = any(p in c.benefics for n in (1, 4, 7, 10) for p in c.occupants(c.house(n)))
    no_malefic_7_8 = not any(p in c.malefics for n in (7, 8) for p in c.occupants(c.house(n)))
    return kendra_benefic and no_malefic_7_8


def _mridanga(c):
    """Planets in own/exaltation signs in kendras AND in trikonas, lagna lord
    strong. Upstream let one planet in the lagna — a kendra and a trikona at
    once — satisfy both halves (owner's chart: lone Venus in Taurus lagna;
    JHora shows no Mridanga)."""
    strong = [p for p in range(9) if c.strength(p) > const._FRIEND]
    in_kendra = {p for p in strong if c.p_to_h[p] in {c.house(n) for n in (1, 4, 7, 10)}}
    in_trine = {p for p in strong if c.p_to_h[p] in {c.house(n) for n in (1, 5, 9)}}
    distinct = any(a != b for a in in_kendra for b in in_trine)
    lagna_lord = house.house_owner_from_planet_positions(c.pp, c.asc)
    return distinct and c.strength(lagna_lord) > const._FRIEND


def _chandikaa(c):
    """Fixed lagna aspected by the 6th lord, and the Sun joining the lords of the
    navamsa signs of the 6th and 9th lords. JHora counts the 6th lord *in* the
    lagna (owner's chart: Venus in Taurus); upstream required a graha aspect."""
    if c.asc not in const.fixed_signs:
        return False
    nav = charts.divisional_chart(c.jd, c.place, 9)[:const._pp_count_upto_ketu]
    nav_p_to_h = {p: h for p, (h, _) in nav}
    l6 = house.house_owner_from_planet_positions(c.pp, c.house(6))
    l9 = house.house_owner_from_planet_positions(c.pp, c.house(9))
    d6 = house.house_owner_from_planet_positions(c.pp, nav_p_to_h[l6])
    d9 = house.house_owner_from_planet_positions(c.pp, nav_p_to_h[l9])
    l6_on_lagna = c.p_to_h[l6] == c.asc or c.asc in house.aspected_rasis_of_the_planet(c.chart_1d, l6)
    sun = c.p_to_h[const.SUN_ID]
    return l6_on_lagna and sun == c.p_to_h[d6] == c.p_to_h[d9]


def _matrunasa_198(c):
    """Moon hemmed in, joined or aspected by evil planets. Upstream counted a
    waning Moon as joining *itself*, and read "aspected" as rasi drishti — 94%
    of random charts."""
    moon = c.p_to_h[const.MOON_ID]
    evil = set(c.engine_malefics) - {const.MOON_ID}
    joined = any(p in evil for p in c.occupants(moon) if p != const.MOON_ID)
    arp, _, _ = house.graha_drishti_from_chart(c.chart_1d)
    aspected = any(p in evil and moon in hs for p, hs in arp.items())
    hemmed = (any(p in evil for p in c.occupants((moon - 1) % 12))
              and any(p in evil for p in c.occupants((moon + 1) % 12)))
    return joined or aspected or hemmed


def _kaahala(c):
    """4th lord and Jupiter in mutual kendras, lagna lord strong. Upstream judged
    the lagna lord's strength in the *lagna sign* rather than the sign it sits
    in (so always "own sign"), and let the 4th lord BE Jupiter (Sg/Pi lagna —
    trivially "in a kendra from himself"; a family chart's JHora shows no Kaahala)."""
    l4 = house.house_owner_from_planet_positions(c.pp, c.house(4))
    if l4 == const.JUPITER_ID:
        return False
    if (c.p_to_h[l4] - c.p_to_h[const.JUPITER_ID]) % 3 != 0:
        return False
    lagna_lord = house.house_owner_from_planet_positions(c.pp, c.asc)
    return utils.is_planet_strong(lagna_lord, c.p_to_h[lagna_lord], include_neutral_samam=True)


RULE_OVERRIDES = {
    "kaahala_yoga": _kaahala,
    "maalaa_yoga": _maalaa,
    "sarpa_yoga": _sarpa,
    "subha_yoga": _subha,
    "asubha_yoga": _asubha,
    "amala_yoga": _amala,
    "parvata_yoga": _parvata,
    "mridanga_yoga": _mridanga,
    "chandikaa_yoga": _chandikaa,
    "matrunasa_yoga_198": _matrunasa_198,
}


def detect(jd, place):
    """Run the catalogue on the Rasi chart.

    Returns ([(key, [name, description, benefits]), ...], catalogue_size) with
    English text, in engine order. Mirrors `yoga.get_yoga_details` — same keys,
    same `<key>_from_jd_place` functions — except for DUPLICATE_KEYS and
    RULE_OVERRIDES.
    """
    msgs = yoga.get_yoga_resources(language="en")
    c = _Chart(jd, place)
    found = []
    for key, details in msgs.items():
        if key in DUPLICATE_KEYS:
            continue
        try:
            rule = RULE_OVERRIDES.get(key)
            present = rule(c) if rule else getattr(yoga, key + "_from_jd_place")(
                jd=jd, place=place, divisional_chart_factor=1)
        except Exception as e:  # one broken rule must not sink the rest
            print(f"[yogas] {key} failed: {e}")
            continue
        if present:
            details = list(details)
            if key in DESCRIPTION_FIXES_EN and len(details) > 1:
                details[1] = DESCRIPTION_FIXES_EN[key]
            found.append((key, details))
    return found, len(msgs) - len(DUPLICATE_KEYS & set(msgs))
