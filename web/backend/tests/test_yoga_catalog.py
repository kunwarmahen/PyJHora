"""Yoga detection vs Jagannatha Hora (2026-09-26).

Users were shown ~30 yogas per chart (19-47 over 200 random charts) where JHora
shows the teens. Most of the gap is catalogue breadth — PyJHora also runs BV
Raman's house-by-house list — plus a handful of rule bugs. See
astrology/yoga_catalog.py.

The owner's expected set is JHora's own yoga tab (owner's screenshot), minus its
raja-yoga family (Rajayoga, Yogada, Raja Sambandha …), which is a separate
section here. A second family chart (7/7 named yogas; it is what fixed the Moon/Mercury
benefic rule and Kaahala) is checked from a git-ignored local file — its birth
data is deliberately NOT kept in the repo.
"""
import json
import os
import random
import statistics

import pytest

from astrology import AstrologyCompute as A
from astrology import engine, yoga_catalog
from jhora import utils
from jhora.horoscope.chart import charts, house, yoga
from jhora.panchanga import drik
import swisseph as swe

OWNER = dict(dob="1976-06-04", tob="05:45:02", place="Shahgarh",
             lat=27.845278, lon=78.334167, tz=5.5)
# Synthetic: Sagittarius lagna, Jupiter (= 4th lord) in a kendra in own sign,
# so it carries Hamsa and trips upstream's self-pairing Kaahala.
SYNTH = dict(dob="2002-07-06", tob="02:00", place="Chennai",
             lat=13.0827, lon=80.2707, tz=5.5)


def _classical(args):
    r = A.get_yogas(**args)
    assert r["status"] == "success"
    return {y["key"] for y in r["yogas"] if y["tier"] == "classical"}


def test_owner_classical_yogas_match_jhora():
    # JHora: Malavya, Vosi, Nipuna, Anaphaa, Kedaara, Parvata, Sankha,
    # Kalpadruma, Chandika, Dhana.
    # Known gap: JHora's Dhana ("Venus in Ta lagna, conjoined or aspected by
    # Mercury, Saturn") credits Saturn in Cancer, which has no graha drishti on
    # Taurus — only a rasi aspect. Not generalised from one row.
    assert _classical(OWNER) == {
        "maalavya_yoga", "vosi_yoga", "nipuna_yoga", "anaphaa_yoga",
        "kedaara_yoga", "parvata_yoga", "sankha_yoga", "kalpadruma_yoga",
        "chandikaa_yoga",
    }


_PRIVATE_REFS = os.path.join(os.path.dirname(__file__), "private_jhora_refs.json")


def _private_refs():
    """Family charts checked against JHora — birth data kept out of git and the
    image (web/.gitignore, .dockerignore). Absent anywhere but the owner's box."""
    if not os.path.exists(_PRIVATE_REFS):
        return []
    with open(_PRIVATE_REFS) as f:
        return json.load(f).get("charts", [])


@pytest.mark.skipif(not os.path.exists(_PRIVATE_REFS), reason="no local private_jhora_refs.json")
@pytest.mark.parametrize("ref", _private_refs(), ids=lambda r: r["label"])
def test_private_family_charts_match_jhora(ref):
    assert _classical(ref["args"]) == set(ref["expected_classical"])


def test_classical_count_is_jhora_sized():
    """Classical tier averages ~8 on random charts; the old output averaged ~30."""
    rng = random.Random(7)
    counts = []
    for _ in range(20):
        args = dict(dob=f"{rng.randint(1940, 2015)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                    tob=f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}", place="x",
                    lat=rng.uniform(10, 30), lon=rng.uniform(70, 88), tz=5.5)
        counts.append(len(_classical(args)))
    assert 4 <= statistics.mean(counts) <= 12


# ── Catalogue shape ────────────────────────────────────────────────────────

def _engine_keys():
    return set(yoga.get_yoga_resources(language="en"))


def test_catalogue_lists_only_real_engine_keys():
    keys = _engine_keys()
    assert yoga_catalog.CLASSICAL_KEYS <= keys
    assert yoga_catalog.DUPLICATE_KEYS <= keys
    assert set(yoga_catalog.RULE_OVERRIDES) <= keys
    for prefix in yoga_catalog._CHALLENGING_PREFIXES:  # typo guard
        assert any(k.startswith(prefix) for k in keys), prefix


def test_new_upstream_yogas_are_noticed():
    """An upstream addition lands 'extended/supportive' by default; this pins the
    catalogue size so someone decides its tier and nature on purpose."""
    assert len(_engine_keys()) == 284


def test_duplicates_are_dropped():
    keys = {y["key"] for y in A.get_yogas(**OWNER)["yogas"]}
    assert "kedaara_yoga" in keys and "kedara_yoga" not in keys


def test_hamsa_description_names_cancer_not_capricorn():
    r = A.get_yogas(**SYNTH)
    hamsa = next(y for y in r["yogas"] if y["key"] == "hamsa_yoga")
    assert "Cancer" in hamsa["description"] and "Capricorn" not in hamsa["description"]


def test_ai_sees_classical_only():
    r = A.get_yogas(**OWNER)
    assert any(y["tier"] == "extended" for y in r["yogas"])
    ai = yoga_catalog.for_ai(r)
    assert ai and all(y["tier"] == "classical" for y in ai)
    assert "matrunasa_yoga_198" not in {y["key"] for y in ai}


def test_prompt_marks_challenging_yogas():
    from llm_service import llm_service

    block = llm_service._render_context_block({"today": "2026-09-26", "yogas": [
        {"name": "Gaja-Kesari Yoga", "nature": "supportive"},
        {"name": "Kemadruma Yoga", "nature": "challenging"},
    ]})
    assert "Kemadruma Yoga [challenging]" in block
    assert "Gaja-Kesari Yoga [challenging]" not in block


# ── Engine tripwires ───────────────────────────────────────────────────────

def _owner_chart_1d():
    jd = swe.julday(1976, 6, 4, 5 + 45 / 60 + 2 / 3600)
    place = drik.Place("Shahgarh", OWNER["lat"], OWNER["lon"], OWNER["tz"])
    pp = charts.divisional_chart(jd, place, 1)[:10]
    return utils.get_house_planet_list_from_planet_positions(pp)


def test_graha_drishti_patch_and_upstream_tripwire():
    ch = _owner_chart_1d()  # Rahu in Libra; Jupiter + Ketu in Aries (its 7th)
    assert set(house.graha_drishti_of_the_planet(ch, 7)) == {4, 8}
    # Upstream still folds rasi drishti in. When this fails, upstream is fixed:
    # delete the patch in engine.py.
    raw = set(engine._engine_graha_drishti_of_the_planet(ch, 7))
    assert raw > {4, 8}


def test_kaahala_upstream_tripwire():
    """Upstream accepts the 4th lord being Jupiter itself (Sg lagna)."""
    jd = swe.julday(2002, 7, 6, 2)
    place = drik.Place("Chennai", SYNTH["lat"], SYNTH["lon"], SYNTH["tz"])
    assert yoga.kaahala_yoga_from_jd_place(jd, place) is True
    assert "kaahala_yoga" not in _classical(SYNTH)
