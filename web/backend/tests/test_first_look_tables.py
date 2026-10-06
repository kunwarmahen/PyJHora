"""The frontend's birth-star sentences are a copy of reference_data's tables
(§76.3 — enumerations translate on the frontend, docs/I18N_DATA_LAYER_DESIGN.md).
Two copies of one table drift; this pins them, by position, which is the only
correspondence between nakshatra lists that is safe (the doc's trap 4.1)."""
import json
import os

import reference_data as r

EN = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "i18n",
                  "locales", "en.json")


def test_star_tables_match_reference_data():
    stars = json.load(open(EN, encoding="utf-8"))["firstLook"]["stars"]
    assert len(stars) == 27
    for i in range(27):
        s = stars[str(i + 1)]
        assert (s["symbol"], s["deity"], s["theme"]) == (
            r.NAKSHATRA_SYMBOL[i], r.NAKSHATRA_DEITY[i], r.NAKSHATRA_THEME[i]), r.NAKSHATRA_NAMES[i]
