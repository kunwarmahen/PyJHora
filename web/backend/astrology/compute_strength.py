"""Strength & condition: Ashtakavarga, planet conditions, avasthas, friendships, yogas/doshas.

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

import re as _re

from . import yoga_catalog
from .compute_match import _mangal_dosha

# Our catalog key -> the English display name PyJHora keys its dosha results by.
# Not derivable: upstream spells it "Manglik Dosha" where we say "Manglik (Kuja)
# Dosha", so the two lists have to be pinned to each other explicitly.
_DOSHA_ENGINE_KEY = {
    "kala_sarpa": "Kala Sarpa Dosha",
    "manglik": "Manglik Dosha",
    "pitru": "Pitru Dosha",
    "guru_chandala": "Guru Chandala Dosha",
    "ganda_moola": "Ganda Moola Dosha",
    "kalathra": "Kalathra Dosha",
    "ghata": "Ghata Dosha",
    "shrapit": "Shrapit Dosha",
}


def _strip_html(text: str) -> str:
    """PyJHora wraps its dosha text in <html> with <br> breaks; the UI renders
    plain text, so unwrap it rather than showing markup to the reader."""
    if not text:
        return text
    out = _re.sub(r"<br\s*/?>", "\n", text, flags=_re.I)
    out = _re.sub(r"<[^>]+>", "", out)
    return out.strip()

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None



def _load_dosha_prevalence() -> Dict[str, float]:
    """{dosha key: % of sampled charts} from dosha_prevalence.json, or {}."""
    import json as _json
    import os as _os
    path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                         "dosha_prevalence.json")
    try:
        with open(path) as f:
            return {k: v["percent"] for k, v in _json.load(f).get("doshas", {}).items()}
    except Exception:
        return {}


_DOSHA_PREVALENCE = _load_dosha_prevalence()


# Pitru Dosha under OUR rule, not PyJHora's (owner decision 2026-10-06, todo.md §83).
# Upstream's dosha.pitru_dosha ORs five broad conditions sourced to a newspaper
# article and fires for 88.8% of charts; dropping its widest condition still left
# 59.1%. Pitru = the father, whose significator is the Sun and whose house is the
# 9th, so we keep only the Sun-and-9th core: the Sun or Rahu in the 9th, or the
# Sun in one sign with Rahu or Ketu (an eclipse-type affliction). The Moon
# conditions (the mother) and the Venus/Mercury cluster are dropped. Measured
# prevalence: dosha_prevalence.json. Signs, not degrees — as upstream does.
_PITRU_REASONS = {
    "en": {
        "sun_9": "the Sun is in the 9th house",
        "rahu_9": "Rahu is in the 9th house",
        "sun_rahu": "the Sun shares a sign with Rahu",
        "sun_ketu": "the Sun shares a sign with Ketu",
    },
    "hi": {
        "sun_9": "सूर्य नौवें भाव में है",
        "rahu_9": "राहु नौवें भाव में है",
        "sun_rahu": "सूर्य और राहु एक ही राशि में हैं",
        "sun_ketu": "सूर्य और केतु एक ही राशि में हैं",
    },
}
_PITRU_TEXT = {
    "en": ("Linked to the father and ancestral karma: the Sun signifies the father and the "
           "9th house is the house of the father. Counted here when the Sun or Rahu is in the "
           "9th house, or the Sun shares a sign with Rahu or Ketu.", "In this chart: {}."),
    "hi": ("पिता और पूर्वजों के कर्म से जुड़ा दोष: सूर्य पिता का कारक है और नौवाँ भाव पितृ भाव है। "
           "यहाँ इसे तब माना जाता है जब सूर्य या राहु नौवें भाव में हो, या सूर्य राहु अथवा केतु "
           "के साथ एक ही राशि में हो।", "इस कुंडली में: {}।"),
}


# Manglik on the Birth Chart uses the Compatibility tab's rule, compute_match.
# _mangal_dosha (owner decision 2026-10-06, todo.md §86): Mars in 1/2/4/7/8/12 from
# the Lagna with no classical cancellation. Before, this tab used upstream's
# dosha.manglik (42.3%) and Compatibility ours (31.0%), so one reader could be
# Manglik on one tab and not on the other. One rule, one answer.
_MANGLIK_TEXT = {
    "en": ("Mars in the 1st, 2nd, 4th, 7th, 8th or 12th house from the Lagna, with no classical "
           "cancellation (Mars in its own or exalted sign, a sign-specific exception, or Jupiter "
           "with Mars). Traditionally weighed in marriage compatibility.",
           "In this chart: Mars is in the {h} house from the Lagna, in {sign}.",
           "Cancelled: {}"),
    "hi": ("लग्न से पहले, दूसरे, चौथे, सातवें, आठवें या बारहवें भाव में मंगल, जब कोई शास्त्रीय परिहार "
           "लागू न हो (मंगल स्वराशि या उच्च राशि में, राशि-विशेष का अपवाद, या मंगल के साथ गुरु)। "
           "विवाह मिलान में परंपरागत रूप से देखा जाता है।",
           "इस कुंडली में: मंगल लग्न से {h} भाव में, {sign} राशि में है।",
           "परिहार के कारण दोष निरस्त है: {}"),
}
# Hindi for _mangal_dosha's cancellation_codes (todo.md §85.2). Sign names are
# list_values_hi.txt's RAASI_LIST, the same source the frontend's tables use.
_RASI_HI = dict(zip(ZODIAC_NAMES, ("मेष", "वृषभ", "मिथुन", "कर्क", "सिंह", "कन्या",
                                   "तुला", "वृश्चिक", "धनु", "मकर", "कुंभ", "मीन")))
_MANGLIK_CANCEL_HI = {
    "own_sign": "मंगल अपनी राशि ({sign}) में है।",
    "exalted": "मंगल {sign} में उच्च का है।",
    "exception": "लग्न से {house} भाव में मंगल {sign} राशि में है — यह शास्त्रीय अपवाद है।",
    "jupiter": "गुरु मंगल के साथ युति में है, जिससे दोष निरस्त होता है।",
}
_ORDINAL_EN = {1: "1st", 2: "2nd", 4: "4th", 7: "7th", 8: "8th", 12: "12th"}
_ORDINAL_HI = {1: "पहले", 2: "दूसरे", 4: "चौथे", 7: "सातवें", 8: "आठवें", 12: "बारहवें"}


def _manglik_description(m: Dict, engine_lang: str) -> str:
    """The rule, then where Mars sits from the Lagna and any cancellation. Hindi
    builds the reasons from _mangal_dosha's cancellation_codes, never its English
    text, so the line is never mixed-language."""
    lang = engine_lang if engine_lang in _MANGLIK_TEXT else "en"
    rule, here, cancelled = _MANGLIK_TEXT[lang]
    h = m["from"].get("Lagna")
    if h is None:
        return rule
    if lang == "hi":
        text = f"{rule} {here.format(h=_ORDINAL_HI[h], sign=_RASI_HI.get(m['mars_sign'], m['mars_sign']))}"
        reasons = [_MANGLIK_CANCEL_HI[c["code"]].format(
                       sign=_RASI_HI.get(c.get("sign"), c.get("sign")),
                       house=_ORDINAL_HI.get(c.get("house"), c.get("house")))
                   for c in m.get("cancellation_codes", [])]
        return f"{text} {cancelled.format(' '.join(reasons))}" if reasons else text
    text = f"{rule} {here.format(h=_ORDINAL_EN[h], sign=m['mars_sign'])}"
    return f"{text} {cancelled.format(' '.join(m['cancellations']))}" if m["cancellations"] else text


def _pitru_reasons(planet_positions) -> List[str]:
    """Which of our Pitru Dosha conditions hold (keys of _PITRU_REASONS); [] = absent."""
    h = utils.get_planet_house_dictionary_from_planet_positions(planet_positions)
    ninth = (h["L"] + 8) % 12
    sun, rahu, ketu = h[const.SUN_ID], h[const.RAHU_ID], h[const.KETU_ID]
    found = []
    if sun == ninth:
        found.append("sun_9")
    if rahu == ninth:
        found.append("rahu_9")
    if sun == rahu:
        found.append("sun_rahu")
    if sun == ketu:
        found.append("sun_ketu")
    return found


def _pitru_description(reasons: List[str], engine_lang: str) -> str:
    lang = engine_lang if engine_lang in _PITRU_TEXT else "en"
    rule, here = _PITRU_TEXT[lang]
    if not reasons:
        return rule
    return f"{rule} {here.format('; '.join(_PITRU_REASONS[lang][r] for r in reasons))}"

class StrengthMixin:

    # The 8 BAV contributors, in Jyotir AI's order.
    _BAV_CONTRIBUTORS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter",
                         "Venus", "Saturn", "Ascendant"]

    @staticmethod
    def _ashtakavarga_tables(jd: float, place_obj) -> tuple:
        """Compute the natal Bhinna + Sarva bindu tables from a chart.

        Returns (bhinna, sarva) where `bhinna` maps each of the 8 contributors to
        a 12-element sign-indexed bindu row and `sarva` is the 12-element combined
        Sarvashtakavarga row. Shared by the Ashtakavarga endpoint and the transit
        join (§2.4) so both read identical numbers."""
        pp = charts.rasi_chart(jd, place_obj)
        h2p = utils.get_house_planet_list_from_planet_positions(pp)
        bav, sav, _ = ashtakavarga.get_ashtaka_varga(h2p)
        bhinna = {
            AstrologyCompute._BAV_CONTRIBUTORS[i]: [int(x) for x in row]
            for i, row in enumerate(bav)
        }
        sarva = [int(x) for x in sav]
        return bhinna, sarva

    @staticmethod
    def _bindu_chip(own_bav, sav_bindu) -> tuple:
        """Classical transit-strength chip for a graha over a given sign.

        The rule of thumb: a transit over a sign carrying more bindus in the
        graha's *own* Bhinnashtakavarga is supported, fewer is rough (own BAV
        >=5 good, ==4 neutral, <=3 weak on the 0-8 scale). The lunar nodes have
        no BAV of their own, so they fall back to the Sarva bindu total for the
        sign (>=30 good, >=25 neutral, else weak on the ~0-56 scale, avg ~28).
        Returns (strength, label)."""
        if own_bav is not None:
            if own_bav >= 5:
                return "good", "Supported"
            if own_bav == 4:
                return "neutral", "Neutral"
            return "weak", "Rough"
        # Nodes: judge on Sarvashtakavarga alone.
        if sav_bindu is not None:
            if sav_bindu >= 30:
                return "good", "Supported"
            if sav_bindu >= 25:
                return "neutral", "Neutral"
            return "weak", "Rough"
        return "neutral", "Neutral"

    @staticmethod
    def get_ashtakavarga(dob: str, tob: str, place: str,
                         lat: Optional[float] = None, lon: Optional[float] = None,
                         tz: Optional[float] = None,
                         ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Bhinna (per-contributor) + Sarva (combined) Ashtakavarga bindu tables."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, 5.5 if tz is None else tz)
            jd = swe.julday(year, month, day, hour + minute / 60.0)
            bhinna, sarva = AstrologyCompute._ashtakavarga_tables(jd, place_obj)
            return {
                "status": "success",
                "signs": ZODIAC_NAMES,
                "bhinna": bhinna,
                "sarva": sarva,
                "sarva_total": int(sum(sarva)),
            }
        except Exception as e:
            print(f"Ashtakavarga error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    # Gandanta ("knot") — the water→fire sign junctions: the last 3°20' of the
    # water signs (Cancer/Scorpio/Pisces) and the first 3°20' of the fire signs
    # that follow them (Leo/Sagittarius/Aries).
    _GANDANTA_WATER = {3, 7, 11}
    _GANDANTA_FIRE = {0, 4, 8}
    _GANDANTA_ARC = 3 + 20 / 60.0
    # Each flag's tone drives the UI colour + the AI framing.
    _CONDITION_TONES = {
        "combust": "challenging", "mrityu_bhaga": "challenging",
        "marana_karaka": "challenging", "gandanta": "challenging",
        "graha_yuddha": "challenging", "vargottama": "benefic",
        "pushkara_navamsa": "benefic", "pushkara_bhaga": "benefic",
        "retrograde": "neutral",
    }
    _CONDITION_LABELS = {
        "combust": "Combust (Asta)",
        "vargottama": "Vargottama",
        "pushkara_navamsa": "Pushkara Navamsa",
        "pushkara_bhaga": "Pushkara Bhaga",
        "mrityu_bhaga": "Mrityu Bhaga",
        "marana_karaka": "Marana Karaka Sthana",
        "gandanta": "Gandanta",
        "graha_yuddha": "Graha Yuddha (planetary war)",
        "retrograde": "Retrograde (Vakri)",
    }

    @staticmethod
    def get_planet_conditions(dob: str, tob: str, place: str,
                              lat: Optional[float] = None, lon: Optional[float] = None,
                              tz: Optional[float] = None,
                              ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Classical point-conditions ("flags") that colour a planet's reading but
        are invisible on the plain Kundali:

          • **Combust (Asta)** — too close to the Sun (engine `planets_in_combustion`).
          • **Vargottama** — same sign in D1 and D9 (a strengthening dignity).
          • **Pushkara Navamsa / Bhaga** — the auspicious nourishing degrees.
          • **Mrityu Bhaga** — the classical "fatal" degrees (engine table).
          • **Marana Karaka Sthana** — a planet in its death-like house.
          • **Gandanta** — sitting on a water→fire junction (a karmic knot).
          • **Graha Yuddha** — a planetary war (two tara-grahas within 1°).
          • **Retrograde (Vakri)** — moving backward.

        All engine-grounded; each flag carries a tone (benefic/challenging/neutral)
        for the UI and the AI framing."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            second = int(tp[2]) if len(tp) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, 5.5 if tz is None else tz)
            jd = swe.julday(year, month, day, hour + minute / 60.0 + second / 3600.0)

            d1 = charts.rasi_chart(jd, place_obj)
            d9 = charts.divisional_chart(jd, place_obj, divisional_chart_factor=9)
            lagna_rasi0 = d1[0][1][0]

            # ── Engine-computed condition sets ──────────────────────────────
            combust = set(charts.planets_in_combustion(d1))
            pna, pb = charts.planets_in_pushkara_navamsa_bhaga(d1)
            pna, pb = set(pna), set(pb)
            retro = set(drik.planets_in_retrograde(jd, place_obj))
            d9_sign = {p: d9[i][1][0] for i, (p, _v) in enumerate(d9[1:], start=1)
                       if isinstance(p, int)}
            # Mrityu bhaga (needs a Date + (h,m,s) tuple, and returns planet
            # index OR 'Md'/'L'); keep only the nine grahas.
            mrityu = set()
            try:
                mb = charts.planets_in_mrityu_bhaga(
                    drik.Date(year, month, day), (hour, minute, second), place_obj, d1)
                mrityu = {x[0] for x in mb if isinstance(x[0], int)}
            except Exception:
                pass
            mks = {p for p, _h in charts.get_planets_in_marana_karaka_sthana(d1)}

            # ── Graha Yuddha — tara-grahas sharing a sign within 1° ─────────
            yuddha = {}   # planet idx -> (partner name, separation°)
            taras = [(p, d1[p + 1][1][0], d1[p + 1][1][1]) for p in (2, 3, 4, 5, 6)]
            for a in range(len(taras)):
                for b in range(a + 1, len(taras)):
                    pa, sa, la = taras[a]; pb2, sb, lb = taras[b]
                    if sa == sb and abs(la - lb) <= 1.0:
                        sep = round(abs(la - lb), 2)
                        yuddha[pa] = (PLANET_NAMES[pb2], sep)
                        yuddha[pb2] = (PLANET_NAMES[pa], sep)

            planets = []
            counts = {"benefic": 0, "challenging": 0, "neutral": 0}
            for pidx in range(9):  # Sun..Ketu
                sign0, deg = d1[pidx + 1][1]
                flags = []

                def add(code, extra=None):
                    tone = AstrologyCompute._CONDITION_TONES[code]
                    f = {"code": code,
                         "label": AstrologyCompute._CONDITION_LABELS[code],
                         "tone": tone}
                    if extra:
                        f.update(extra)
                    flags.append(f)
                    counts[tone] += 1

                if pidx in combust:
                    add("combust")
                if pidx in d9_sign and d9_sign[pidx] == sign0:
                    add("vargottama")
                if pidx in pna:
                    add("pushkara_navamsa")
                if pidx in pb:
                    add("pushkara_bhaga")
                if pidx in mrityu:
                    add("mrityu_bhaga")
                if pidx in mks:
                    add("marana_karaka")
                if ((sign0 in AstrologyCompute._GANDANTA_WATER
                     and deg >= 30 - AstrologyCompute._GANDANTA_ARC)
                        or (sign0 in AstrologyCompute._GANDANTA_FIRE
                            and deg < AstrologyCompute._GANDANTA_ARC)):
                    add("gandanta")
                if pidx in yuddha:
                    partner, sep = yuddha[pidx]
                    add("graha_yuddha", {"partner": partner, "separation": sep})
                # Only the five tara-grahas: Rahu/Ketu are Mean nodes and thus
                # perpetually retrograde (noise), the luminaries never retrograde.
                if pidx in (2, 3, 4, 5, 6) and pidx in retro:
                    add("retrograde")

                planets.append({
                    "planet": PLANET_NAMES.get(pidx, str(pidx)),
                    "sign_name": ZODIAC_NAMES[sign0],
                    "degrees": round(deg, 2),
                    "house": ((sign0 - lagna_rasi0) % 12) + 1,
                    "flags": flags,
                })

            flagged = [p for p in planets if p["flags"]]
            return {
                "status": "success",
                "planets": planets,
                "flagged": flagged,
                "counts": counts,
                "flagged_count": len(flagged),
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    # ── Avasthas (planetary states) — engine has none, so computed here ──────
    # Sign lord (planet index) per rasi 0..11.
    _RASI_LORD_IDX = [2, 5, 3, 1, 0, 3, 5, 2, 4, 6, 6, 4]
    # Baladi (5 states by degree; strongest = Yuva). Each 6° of the sign.
    _BALADI_STATES = ["Bala", "Kumara", "Yuva", "Vriddha", "Mrita"]
    _BALADI_INFO = {
        "Bala": ("infant", "quarter strength"),
        "Kumara": ("adolescent", "half strength"),
        "Yuva": ("youth / prime", "full strength"),
        "Vriddha": ("old", "little strength"),
        "Mrita": ("dead", "no strength"),
    }
    _JAGRADADI_INFO = {
        "Jagrat": ("awake", "gives full results"),
        "Swapna": ("dreaming", "gives moderate results"),
        "Sushupti": ("sleeping", "gives weak results"),
    }
    _DEEPTADI_INFO = {
        "Deepta": ("radiant", "exalted — very strong", "benefic"),
        "Swastha": ("healthy", "own sign — strong", "benefic"),
        "Mudita": ("delighted", "friend's sign — comfortable", "benefic"),
        "Shanta": ("peaceful", "neutral sign — settled", "neutral"),
        "Deena": ("miserable", "enemy's sign — uneasy", "challenging"),
        "Dukhita": ("distressed", "debilitated — struggling", "challenging"),
        "Vikala": ("crippled", "combust — burnt by the Sun", "challenging"),
        "Khala": ("mischievous", "with a malefic — agitated", "challenging"),
        "Kopa": ("agitated", "in a planetary war — disturbed", "challenging"),
    }

    @staticmethod
    def get_avasthas(dob: str, tob: str, place: str,
                     lat: Optional[float] = None, lon: Optional[float] = None,
                     tz: Optional[float] = None,
                     ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """The classical **avasthas** (planetary states) for the seven grahas —
        desktop JHora shows these but the engine has no function for them, so they
        are computed here from longitude + dignity (like the Mangal-dosha and
        gandanta logic):

          • **Baladi** (5) — infant→dead by degree-in-sign (reversed in even signs);
            Yuva (prime) is strongest, Mrita (dead) gives nothing.
          • **Jagradadi** (3) — awake / dreaming / sleeping, by dignity (own-exalt /
            friend-neutral / enemy-debilitated).
          • **Deeptadi** (9) — a fuller dignity-and-affliction state (radiant …
            agitated); the affliction states (combust→Vikala, in war→Kopa, with a
            malefic→Khala) override the dignity base.

        A simplified but faithful classical mapping; the AI reading treats it as a
        strength nuance, not a verdict."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            from jhora import const as _const
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            second = int(tp[2]) if len(tp) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, 5.5 if tz is None else tz)
            jd = swe.julday(year, month, day, hour + minute / 60.0 + second / 3600.0)

            d1 = charts.rasi_chart(jd, place_obj)
            planet_sign = {p: d1[p + 1][1][0] for p in range(9)}
            combust = set(charts.planets_in_combustion(d1))
            # Malefic co-tenants (same sign) for Khala; nodes + Mars + Saturn.
            malefics = (2, 6, 7, 8)
            malefic_signs = {planet_sign[m] for m in malefics}
            # Graha yuddha (tara-grahas sharing a sign within 1°) for Kopa.
            yuddha = set()
            taras = [(p, d1[p + 1][1][0], d1[p + 1][1][1]) for p in (2, 3, 4, 5, 6)]
            for a in range(len(taras)):
                for b in range(a + 1, len(taras)):
                    if taras[a][1] == taras[b][1] and abs(taras[a][2] - taras[b][2]) <= 1.0:
                        yuddha.add(taras[a][0]); yuddha.add(taras[b][0])

            def dignity(name, p, sign0):
                if name in EXALTATION_SIGN:
                    if sign0 == EXALTATION_SIGN[name]:
                        return "exalted"
                    if sign0 == (EXALTATION_SIGN[name] + 6) % 12:
                        return "debilitated"
                lord = AstrologyCompute._RASI_LORD_IDX[sign0]
                if lord == p:
                    return "own"
                rel = _const.planet_relations[p][lord]
                return {3: "friend", 2: "neutral", 1: "enemy"}.get(rel, "neutral")

            planets = []
            for p in range(7):  # Sun..Saturn (avasthas are for the seven grahas)
                name = PLANET_NAMES[p]
                sign0, deg = d1[p + 1][1]

                # Baladi — 6° parts, reversed in even (2nd/4th/… ) signs.
                part = min(int(deg // 6), 4)
                odd_sign = (sign0 % 2 == 0)  # Aries(0) is the 1st = odd sign
                baladi = (AstrologyCompute._BALADI_STATES[part] if odd_sign
                          else AstrologyCompute._BALADI_STATES[4 - part])

                dig = dignity(name, p, sign0)

                # Jagradadi from dignity.
                if dig in ("exalted", "own"):
                    jagradadi = "Jagrat"
                elif dig in ("friend", "neutral"):
                    jagradadi = "Swapna"
                else:  # enemy / debilitated
                    jagradadi = "Sushupti"

                # Deeptadi — dignity base, overridden by affliction.
                base = {"exalted": "Deepta", "own": "Swastha", "friend": "Mudita",
                        "neutral": "Shanta", "enemy": "Deena",
                        "debilitated": "Dukhita"}[dig]
                if p in combust:
                    deeptadi = "Vikala"
                elif p in yuddha:
                    deeptadi = "Kopa"
                elif any(sign0 == ms and p not in malefics for ms in [planet_sign[m] for m in malefics]):
                    deeptadi = "Khala"
                else:
                    deeptadi = base

                bl_state, bl_str = AstrologyCompute._BALADI_INFO[baladi]
                jg_state, jg_eff = AstrologyCompute._JAGRADADI_INFO[jagradadi]
                dp_state, dp_desc, dp_tone = AstrologyCompute._DEEPTADI_INFO[deeptadi]
                planets.append({
                    "planet": name,
                    "sign_name": ZODIAC_NAMES[sign0],
                    "degrees": round(deg, 2),
                    "dignity": dig,
                    "baladi": {"state": baladi, "meaning": bl_state, "strength": bl_str},
                    "jagradadi": {"state": jagradadi, "meaning": jg_state, "effect": jg_eff},
                    "deeptadi": {"state": deeptadi, "meaning": dp_state,
                                 "description": dp_desc, "tone": dp_tone},
                })

            return {"status": "success", "planets": planets}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    # Compound-relationship code (engine) → (label, tone).
    _COMPOUND_REL = {
        4: ("Adhimitra", "benefic"),   # great friend
        3: ("Mitra", "benefic"),       # friend
        2: ("Sama", "neutral"),        # neutral
        1: ("Shatru", "challenging"),  # enemy
        0: ("Adhishatru", "challenging"),  # great enemy
    }

    @staticmethod
    def get_friendships(dob: str, tob: str, place: str,
                        lat: Optional[float] = None, lon: Optional[float] = None,
                        tz: Optional[float] = None,
                        ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Planetary relationships **in this chart** (compound = natural + temporal):

          • the 7×7 **compound-friendship matrix** (Adhimitra → Adhishatru),
          • the **house-lord placement** table (the lord of each bhava and the house
            it actually occupies), and
          • **Parivartana** (mutual sign exchange) between planets.

        Nothing in the UI showed who is whose friend once temporal placement is
        folded in; this surfaces it and feeds the AI's dignity reasoning."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            from jhora.horoscope.chart import house as _house
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, 5.5 if tz is None else tz)
            jd = swe.julday(year, month, day, hour + minute / 60.0)

            pp = charts.rasi_chart(jd, place_obj)
            lagna_rasi0 = pp[0][1][0]
            planet_sign = {pidx: rasi for pidx, (rasi, _d) in pp[1:]}
            h2p = utils.get_house_planet_list_from_planet_positions(pp)

            # ── Compound-friendship matrix (7 grahas) ───────────────────────
            comp = _house._get_compound_relationships_of_planets(h2p)
            matrix = []
            for p in range(7):
                rels = []
                for q in range(7):
                    if p == q:
                        rels.append({"to": PLANET_NAMES[q], "self": True})
                        continue
                    label, tone = AstrologyCompute._COMPOUND_REL.get(
                        comp[p][q], ("Sama", "neutral"))
                    rels.append({"to": PLANET_NAMES[q], "label": label, "tone": tone})
                matrix.append({"planet": PLANET_NAMES[p], "relations": rels})

            # ── House-lord placement ────────────────────────────────────────
            RASI_LORD_IDX = AstrologyCompute._RASI_LORD_IDX
            house_lords = []
            for h in range(1, 13):
                sign0 = (lagna_rasi0 + h - 1) % 12
                lord = RASI_LORD_IDX[sign0]
                lord_sign = planet_sign.get(lord)
                lord_house = ((lord_sign - lagna_rasi0) % 12) + 1 if lord_sign is not None else None
                house_lords.append({
                    "house": h,
                    "house_sign": ZODIAC_NAMES[sign0],
                    "signification": AstrologyCompute._BHAVA_SIGNIFICATION[h - 1],
                    "lord": PLANET_NAMES[lord],
                    "lord_house": lord_house,
                    "lord_sign": ZODIAC_NAMES[lord_sign] if lord_sign is not None else None,
                    "lord_house_signification": (
                        AstrologyCompute._BHAVA_SIGNIFICATION[lord_house - 1]
                        if lord_house else None),
                })

            # ── Parivartana (mutual sign exchange) among the 7 grahas ───────
            parivartana = []
            for a in range(7):
                for b in range(a + 1, 7):
                    sa, sb = planet_sign.get(a), planet_sign.get(b)
                    if sa is None or sb is None:
                        continue
                    if RASI_LORD_IDX[sa] == b and RASI_LORD_IDX[sb] == a:
                        parivartana.append({
                            "planets": [PLANET_NAMES[a], PLANET_NAMES[b]],
                            "signs": [ZODIAC_NAMES[sa], ZODIAC_NAMES[sb]],
                            "houses": [((sa - lagna_rasi0) % 12) + 1,
                                       ((sb - lagna_rasi0) % 12) + 1],
                        })

            return {
                "status": "success",
                "planets": [PLANET_NAMES[p] for p in range(7)],
                "matrix": matrix,
                "house_lords": house_lords,
                "parivartana": parivartana,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_doshas(dob: str, tob: str, place: str,
                   lat: Optional[float] = None, lon: Optional[float] = None,
                   tz: Optional[float] = None, ayanamsa: str = DEFAULT_AYANAMSA,
                   lang: str = "en") -> Dict:
        """Detect the common doshas for a birth chart (present/absent + description).

        Descriptions are language-conditional (owner decision, 2026-07-19). In
        English we keep the curated text below, which is better than upstream's.
        In another language we take PyJHora's, because a weaker translation still
        beats untranslated English — but swapping English for weaker English
        would be a pure loss, so `en` never does.

        Unlike yogas (see get_yogas), detection here is language-independent: the
        dosha.* predicates are booleans that never look at the message file, so
        the language cannot move the astrology. It only chooses the wording.
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = 5.5 if tz is None else tz
            jd = swe.julday(year, month, day, hour + minute / 60)
            place_obj = drik.Place(place, lat, lon, tz_offset)

            pp = charts.rasi_chart(jd, place_obj)
            h2p = utils.get_house_planet_list_from_planet_positions(pp)
            moon_rasi, moon_long = pp[2][1]  # pp[0]=Asc, pp[1]=Sun, pp[2]=Moon
            moon_star = drik.nakshatra_pada(moon_rasi * 30 + moon_long)[0]

            def _present(v):
                if isinstance(v, bool):
                    return v
                if isinstance(v, (list, tuple)):
                    return any(x is True for x in v)
                return bool(v)

            pitru = _pitru_reasons(pp)
            mangal = _mangal_dosha(pp)
            catalog = [
                ("kala_sarpa", "Kala Sarpa Dosha", dosha.kala_sarpa(h2p),
                 "All planets fall on one side of the Rahu–Ketu axis. Can bring delays and obstacles, often with strong results later in life."),
                # Compatibility's rule, not dosha.manglik — see _MANGLIK_TEXT.
                ("manglik", "Manglik (Kuja) Dosha", mangal["manglik"], None),
                # Our narrowed rule, not dosha.pitru_dosha — see _pitru_reasons.
                ("pitru", "Pitru Dosha", bool(pitru), None),
                ("guru_chandala", "Guru Chandala Dosha", dosha.guru_chandala_dosha(pp),
                 "Jupiter conjunct Rahu or Ketu. Can affect judgement, ethics and guidance."),
                ("ganda_moola", "Ganda Moola Dosha", dosha.ganda_moola(moon_star),
                 "Moon in a gandanta nakshatra (Ashwini, Ashlesha, Magha, Jyeshtha, Mula, Revati). A sensitive early period; remedies are advised."),
                ("kalathra", "Kalathra Dosha", dosha.kalathra(pp),
                 "Affliction to the 7th house and spouse significators, considered for marriage and partnerships."),
                ("ghata", "Ghata Dosha", dosha.ghata(pp),
                 "Mars–Saturn conjunction. Can bring friction, haste and accidents."),
                ("shrapit", "Shrapit Dosha", dosha.shrapit(pp),
                 "Rahu–Saturn conjunction. Associated with chronic, carried-over difficulties."),
            ]
            # PyJHora's variant-correct, translated descriptions. Its dict is
            # keyed by the ENGLISH display name in every language (the keys come
            # from the global utils.resource_strings, which we never switch), so
            # this map is stable — but fall back per-dosha rather than assuming.
            engine_lang = to_engine_language(lang)
            engine_text = {}
            if engine_lang != "en":
                try:
                    engine_text = dosha.get_dosha_details(jd, place_obj, language=engine_lang)
                except Exception as e:  # never lose the doshas over a translation
                    print(f"dosha translation unavailable ({engine_lang}): {e}")

            doshas = []
            for (k, n, v, d) in catalog:
                text = engine_text.get(_DOSHA_ENGINE_KEY.get(k, ""))
                if k == "pitru":
                    # Upstream's text explains upstream's five-condition rule, so
                    # it would contradict the verdict; ours is en + hi.
                    text, d = None, _pitru_description(pitru, engine_lang)
                elif k == "manglik":
                    # Same: upstream's text explains upstream's rule.
                    text, d = None, _manglik_description(mangal, engine_lang)
                doshas.append({
                    "key": k,
                    "name": n,
                    "present": _present(v),
                    "description": _strip_html(text) if text else d,
                    # How common it is under these same rules (§76.6) — measured,
                    # not quoted: scripts/dosha_prevalence.py. A newcomer told
                    # they "have" a dosha should know when most people do too.
                    "prevalence_percent": _DOSHA_PREVALENCE.get(k),
                })
            return {
                "status": "success",
                "doshas": doshas,
                "present_count": sum(1 for x in doshas if x["present"]),
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_yogas(dob: str, tob: str, place: str,
                  lat: Optional[float] = None, lon: Optional[float] = None,
                  tz: Optional[float] = None, ayanamsa: str = DEFAULT_AYANAMSA,
                  lang: str = "en") -> Dict:
        """Detect the yogas present in the Rasi chart (name + description + benefits).

        `lang` is the UI language; PyJHora returns the names AND the free-text
        descriptions in it (see to_engine_language for the sa -> hi routing).
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = 5.5 if tz is None else tz
            jd = swe.julday(year, month, day, hour + minute / 60)
            place_obj = drik.Place(place, lat, lon, tz_offset)

            # Detect in English ALWAYS, then translate the labels by key.
            #
            # PyJHora drives detection off the message file's KEYS — it iterates
            # msgs.items() and eval()s each key as a yoga function — so asking it for
            # Hindi directly would change *which yogas are found*, not just their
            # names: yoga_msgs_hi.json is missing yukthi_samanwithavagmi_yoga_154/_155
            # and adds dhana_yoga + yukthi_samanwithavagmi_yoga. English is the
            # canonical key set; language must never move the astrology.
            #
            # yoga_catalog.detect runs the same catalogue minus duplicate keys and
            # with the rules we correct; it also tiers each yoga classical vs
            # extended (BV Raman's house-specific list) — see its docstring.
            results, total = yoga_catalog.detect(jd, place_obj)
            engine_lang = to_engine_language(lang)
            # {key: [name, description, benefits]}
            translated = (
                yoga.get_yoga_resources(language=engine_lang) if engine_lang != "en" else {}
            )
            yogas = []
            for key, details in results:
                # details = [name, description, benefits]
                t = translated.get(key)  # missing key -> English, never a blank
                name, description, benefits = yoga_catalog.tidy(
                    key,
                    (t[0] if t else details[0]) if details else key,
                    (t[1] if t else details[1]) if len(details) > 1 else "",
                    (t[2] if t else details[2]) if len(details) > 2 else "",
                    english=not t,
                )
                yogas.append({
                    "key": key,
                    "name": name,
                    "description": description,
                    "benefits": benefits,
                    "tier": yoga_catalog.tier_of(key),
                    "nature": yoga_catalog.nature_of(key),
                })
            # classical first, supportive before challenging, then by name
            yogas.sort(key=lambda y: (y["tier"] != "classical",
                                      y["nature"] != "supportive", y["name"]))
            classical = sum(1 for y in yogas if y["tier"] == "classical")
            return {"status": "success", "yogas": yogas, "found": len(yogas),
                    "classical_count": classical, "total": total}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_raja_yogas(dob: str, tob: str, place: str,
                       lat: Optional[float] = None, lon: Optional[float] = None,
                       tz: Optional[float] = None,
                       ayanamsa: str = DEFAULT_AYANAMSA,
                       lang: str = "en") -> Dict:
        """Dedicated Raja Yoga analysis for the Rasi (D1) chart.

        Surfaces (a) the fundamental Kendra–Trikona raja yogas — a quadrant lord
        associated with a trine lord — and (b) the named special types
        (Dharma-Karmadhipati, Vipareeta with sub-type, Neecha-Bhanga) with their
        classical descriptions/benefits. A light dignity check labels each pair's
        strength. Birth details + ayanamsa are server-injected; ayanamsa reset.
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            from jhora.horoscope.chart import raja_yoga as ry

            y, m, d = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, 5.5 if tz is None else tz)
            jd = swe.julday(y, m, d, hour + minute / 60.0)

            pp = charts.rasi_chart(jd, place_obj)
            p_to_h = utils.get_planet_house_dictionary_from_planet_positions(pp)

            def _dignity(pidx, sign):
                """Coarse strength from the planet's house-strength in its sign."""
                try:
                    s = const.house_strengths_of_planets[pidx][sign]
                except Exception:
                    return "neutral"
                if s >= const._EXALTED_UCCHAM:
                    return "strong"
                if s <= const._DEBILITATED_NEECHAM:
                    return "weak"
                if s >= const._FRIEND:
                    return "good"
                return "neutral"

            yogas = []

            # (a) Kendra–Trikona raja yoga pairs (association of quadrant &
            #     trine lords). Strength is a blend of both planets' dignity.
            pairs = ry.get_raja_yoga_pairs_from_planet_positions(pp)
            for p1, p2 in pairs:
                d1 = _dignity(p1, p_to_h.get(p1, 0))
                d2 = _dignity(p2, p_to_h.get(p2, 0))
                order = {"strong": 3, "good": 2, "neutral": 1, "weak": 0}
                strength = min([d1, d2], key=lambda x: order[x])
                yogas.append({
                    "name": "Kendra-Trikona Raja Yoga",
                    "type": "kendra_trikona",
                    "planets": [PLANET_NAMES[p1], PLANET_NAMES[p2]],
                    "description": (f"Association of a quadrant (kendra) lord and a "
                                    f"trine (trikona) lord — {PLANET_NAMES[p1]} and "
                                    f"{PLANET_NAMES[p2]} — the core raja yoga that "
                                    f"confers status, authority and success."),
                    "benefits": "Rise in position, recognition and prosperity.",
                    "strength": strength,
                })

            # (b) Named special raja yogas (from the engine's msg resources).
            #     Detect in English and translate by key, for the same reason as
            #     get_yogas: PyJHora eval()s the message file's keys as function
            #     names, so the language must not decide what is detected. The
            #     raja-yoga key sets happen to match across languages today; this
            #     keeps that from mattering.
            try:
                details, _cnt, _tot = ry.get_raja_yoga_details(
                    jd, place_obj, divisional_chart_factor=1, language="en")
                engine_lang = to_engine_language(lang)
                translated = (
                    ry.get_raja_yoga_resources(language=engine_lang)
                    if engine_lang != "en" else {}
                )
                for key, val in details.items():
                    # val = [pairs_label, name, description, benefits]
                    label = val[0] if len(val) > 3 else ""
                    name = val[1] if len(val) > 3 else val[0]
                    desc = val[2] if len(val) > 3 else (val[1] if len(val) > 1 else "")
                    benefits = val[3] if len(val) > 3 else (val[2] if len(val) > 2 else "")
                    # The resource entry is [name, description, benefits] — no
                    # pairs_label, which get_raja_yoga_details inserts at index 0.
                    t = translated.get(key)
                    if t:
                        name = t[0] if len(t) > 0 else name
                        desc = t[1] if len(t) > 1 else desc
                        benefits = t[2] if len(t) > 2 else benefits
                    yogas.append({
                        "name": name,
                        "type": key,
                        "planets": [],
                        "pairs_label": label,
                        "description": desc,
                        "benefits": benefits,
                        "strength": "special",
                    })
            except Exception as inner:
                print(f"Raja yoga named-details skipped: {inner}")

            return {
                "status": "success",
                "count": len(yogas),
                "raja_yogas": yogas,
            }
        except Exception as e:
            print(f"Raja yoga error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_longevity(dob: str, tob: str, place: str,
                      lat: Optional[float] = None, lon: Optional[float] = None,
                      tz: Optional[float] = None,
                      ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Ayu (longevity) *category* from the classical Ayurdaya sign-pair method.

        Returns the ayu band — Alpa (short) / Madhya (medium) / Purna (long) —
        and the three contributing sign-pair verdicts (Lagna-lord vs 8th-lord,
        Lagna vs Moon, Lagna vs Hora-lagna). Deliberately returns a *category*
        and its factors, never a death date or age. Framed as conditional,
        multi-factorial guidance. Ayanamsa server-injected + reset.

        Reimplements the aggregation of the engine's `life_span_range` (which has
        a Py3 `dict.keys()[0]` bug in the all-three-agree branch) while reusing
        its per-pair rule and the same chart inputs.
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            import collections

            y, m, d = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, 5.5 if tz is None else tz)
            jd = swe.julday(y, m, d, hour + minute / 60.0)

            def _get_aayu(s1, s2):
                """Sign-pair → 0 Alpa / 1 Madhya / 2 Purna (Parashari movable/
                fixed/dual matrix). Mirrors the engine's local helper."""
                mv, fx, dl = const.movable_signs, const.fixed_signs, const.dual_signs
                if s1 in fx and s2 in fx:
                    return 0
                if s1 in mv and s2 in mv:
                    return 2
                if s1 in dl and s2 in dl:
                    return 1
                if (s1 in fx and s2 in mv) or (s1 in mv and s2 in fx):
                    return 1
                if (s1 in dl and s2 in mv) or (s1 in mv and s2 in dl):
                    return 0
                return 2  # fixed+dual

            pp = charts.rasi_chart(jd, place_obj)
            asc_house = pp[0][1][0]
            eighth_house = (asc_house + 7) % 12
            moon_house = pp[2][1][0]
            lagna_lord = house.house_owner_from_planet_positions(pp, asc_house)
            lagna_lord_house = pp[lagna_lord + 1][1][0]
            eighth_lord = house.house_owner_from_planet_positions(pp, eighth_house)
            eighth_lord_house = pp[eighth_lord + 1][1][0]
            # NOT drik.hora_lagna — it carries the special_ascendant timezone bug
            # (~14' late; see engine._kaala_lagna). Ayu here turns on which SIGN
            # the Hora Lagna falls in, so a 14' error flips the whole verdict
            # whenever HL sits near a cusp — and on the owner's own chart it sits
            # at 0°14' of Gemini, i.e. squarely inside that margin.
            hora_lagna = _kaala_lagna(jd, place_obj, KAALA_LAGNA_RATES["Hora Lagna"])[0]

            group = [
                _get_aayu(lagna_lord_house, eighth_lord_house),
                _get_aayu(asc_house, moon_house),
                _get_aayu(asc_house, hora_lagna),
            ]
            counter = collections.Counter(group)
            if len(counter) == 1:
                category = group[0]
            elif len(counter) == 2:
                category = max(counter, key=counter.get)
            else:
                category = group[-1]
                if moon_house == asc_house or moon_house == (asc_house + 6) % 12:
                    category = group[1]

            AYU = {0: ("Alpa", "Short ayu (conditional)"),
                   1: ("Madhya", "Medium ayu (conditional)"),
                   2: ("Purna", "Long ayu (conditional)")}
            cat_name, cat_desc = AYU[category]

            factor_labels = [
                ("Lagna lord & 8th lord", lagna_lord_house, eighth_lord_house),
                ("Lagna & Moon", asc_house, moon_house),
                ("Lagna & Hora Lagna", asc_house, hora_lagna),
            ]
            factors = []
            for (label, sa, sb), verdict in zip(factor_labels, group):
                factors.append({
                    "pair": label,
                    "signs": [ZODIAC_NAMES[sa], ZODIAC_NAMES[sb]],
                    "verdict": AYU[verdict][0],
                })

            return {
                "status": "success",
                "category": category,          # 0/1/2
                "category_name": cat_name,     # Alpa/Madhya/Purna
                "category_desc": cat_desc,
                "factors": factors,
            }
        except Exception as e:
            print(f"Longevity error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)
