"""Language routing for PyJHora's message resources (§5 P3).

PyJHora ships yoga/raja-yoga/dosha message files for en/ta/te/hi/ka/ml only — there
is no Sanskrit file. Rather than drop `sa` users back to English, we route them to
Hindi, which shares the script and most of this vocabulary with Sanskrit. These tests
pin that decision, plus the fact that the yoga endpoint's free text really does come
back translated (which the frontend name-mapping layer cannot do).
"""
from astrology import AstrologyCompute as A
from astrology.engine import to_engine_language

# Owner's chart (todo §26) — the one with JHora screenshots to compare against.
CHART = dict(dob="1976-06-04", tob="05:45:02", place="Aligarh, India",
             lat=27.845709, lon=78.333733, tz=5.5)


def is_devanagari(s):
    return any("ऀ" <= ch <= "ॿ" for ch in s or "")


class TestToEngineLanguage:
    def test_passes_through_languages_pyjhora_ships(self):
        for lang in ("en", "hi", "ta", "te", "ka", "ml"):
            assert to_engine_language(lang) == lang

    def test_sanskrit_routes_to_hindi_not_english(self):
        # The whole point: `sa` must NOT silently fall back to English.
        assert to_engine_language("sa") == "hi"

    def test_unsupported_language_falls_back_to_english(self):
        assert to_engine_language("fr") == "en"
        assert to_engine_language("") == "en"
        assert to_engine_language(None) == "en"

    def test_handles_region_variants_and_case(self):
        assert to_engine_language("hi-IN") == "hi"
        assert to_engine_language("SA") == "hi"


class TestYogaLocalization:
    """The names AND descriptions come from PyJHora, so both must translate."""

    @staticmethod
    def _yogas(lang):
        r = A.get_yogas(**CHART, lang=lang)
        assert r.get("status") == "success", r
        return r

    def test_same_yogas_detected_regardless_of_language(self):
        """Language must move the labels and NOTHING else.

        This is the regression that matters: PyJHora drives yoga detection off its
        message file's keys, and yoga_msgs_hi.json's keys differ from the English
        ones — so asking it for Hindi directly changed which yogas were reported
        (en found yukthi_samanwithavagmi_yoga_154, hi found
        yukthi_samanwithavagmi_yoga). We detect in English and translate after.
        """
        en, hi, sa = self._yogas("en"), self._yogas("hi"), self._yogas("sa")
        assert en["found"] == hi["found"] == sa["found"]
        keys = {y["key"] for y in en["yogas"]}
        assert keys == {y["key"] for y in hi["yogas"]}
        assert keys == {y["key"] for y in sa["yogas"]}

    def test_hindi_returns_devanagari_names_and_descriptions(self):
        """Every yoga upstream CAN translate must come back in Devanagari — names and
        the free text both, which is the whole reason to route this through PyJHora
        rather than the frontend name tables."""
        from jhora.horoscope.chart import yoga as _yoga
        hi_msgs = _yoga.get_yoga_resources(language="hi")

        translatable = [y for y in self._yogas("hi")["yogas"] if y["key"] in hi_msgs]
        assert translatable, "expected some translatable yogas in this chart"
        for y in translatable:
            assert is_devanagari(y["name"]), y
            assert is_devanagari(y["description"]), y

    def test_sanskrit_gets_hindi_rather_than_english(self):
        sa = {y["key"]: y["name"] for y in self._yogas("sa")["yogas"]}
        hi = {y["key"]: y["name"] for y in self._yogas("hi")["yogas"]}
        en = {y["key"]: y["name"] for y in self._yogas("en")["yogas"]}
        assert sa == hi
        assert sa != en

    def test_a_key_missing_from_the_translation_falls_back_to_english(self):
        """yoga_msgs_hi.json has no yukthi_samanwithavagmi_yoga_154, and that yoga is
        present in this chart — so it must render its English name, never a blank."""
        hi = {y["key"]: y for y in self._yogas("hi")["yogas"]}
        stray = hi.get("yukthi_samanwithavagmi_yoga_154")
        assert stray is not None, "fixture chart no longer has the untranslated yoga"
        assert stray["name"] and stray["name"].isascii()
        assert stray["description"]

    def test_english_is_still_the_default(self):
        r = A.get_yogas(**CHART)
        assert r["status"] == "success"
        assert all(ch.isascii() for ch in r["yogas"][0]["name"])


class TestRajaYogaLocalization:
    """Only the yogas PyJHora *names* translate. The Kendra-Trikona pairs are computed
    and labelled by our own backend, so they stay English until §5 covers them — this
    pins that split so the half-translated section is a known state, not a surprise."""

    @staticmethod
    def _named(lang):
        r = A.get_raja_yogas(**CHART, lang=lang)
        assert r.get("status") == "success", r
        return [y["name"] for y in r["raja_yogas"] if y["type"] != "kendra_trikona"]

    def test_engine_named_raja_yogas_translate(self):
        named = self._named("hi")
        assert named, "expected at least one engine-named raja yoga for this chart"
        assert any(is_devanagari(n) for n in named), named

    def test_sanskrit_gets_hindi(self):
        assert self._named("sa") == self._named("hi")

    def test_english_default_unchanged(self):
        assert all(n.isascii() for n in self._named("en"))


# ── Doshas (owner decision, 2026-07-19) ──────────────────────────────────────
# English keeps our curated descriptions; other languages take PyJHora's, because
# a weaker translation beats untranslated English — but swapping English for
# weaker English would be a pure loss, so `en` never does.

def test_doshas_english_keeps_our_curated_text():
    d = A.get_doshas(**CHART, lang="en")["doshas"]
    kala = next(x for x in d if x["key"] == "kala_sarpa")
    assert "Rahu–Ketu axis" in kala["description"]
    assert not is_devanagari(kala["description"])


def test_doshas_hindi_uses_the_engine_text():
    d = A.get_doshas(**CHART, lang="hi")["doshas"]
    assert any(is_devanagari(x["description"]) for x in d)


def test_doshas_sanskrit_routes_to_hindi():
    # Same stopgap as yogas: no Sanskrit dosha file upstream.
    hi = A.get_doshas(**CHART, lang="hi")["doshas"]
    sa = A.get_doshas(**CHART, lang="sa")["doshas"]
    assert [x["description"] for x in sa] == [x["description"] for x in hi]


def test_language_never_moves_the_astrology():
    # Unlike yogas, dosha detection is boolean and never reads the message file.
    # If this ever fails, the language is changing WHAT is detected, not just its
    # wording — which is the §4.3 trap.
    base = A.get_doshas(**CHART, lang="en")
    for lang in ("hi", "sa", "ta", "nonsense"):
        other = A.get_doshas(**CHART, lang=lang)
        assert other["present_count"] == base["present_count"]
        assert [x["key"] for x in other["doshas"]] == [x["key"] for x in base["doshas"]]
        assert [x["present"] for x in other["doshas"]] == [x["present"] for x in base["doshas"]]


def test_dosha_descriptions_are_plain_text():
    # PyJHora wraps its dosha text in <html> with <br> breaks; the UI renders
    # plain text, so markup must never reach the reader.
    for lang in ("en", "hi"):
        for x in A.get_doshas(**CHART, lang=lang)["doshas"]:
            assert "<" not in x["description"], (lang, x["key"])


def test_every_dosha_has_a_description_in_every_language():
    # A missing engine key must fall back to our text, never to a blank card.
    for lang in ("en", "hi", "sa"):
        for x in A.get_doshas(**CHART, lang=lang)["doshas"]:
            assert x["description"].strip(), (lang, x["key"])
