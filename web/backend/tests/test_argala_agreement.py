"""Argala is computed in two places and they must agree (§79.3).

`get_argala` (Sensitive Points → Argala, and the sensitive-points AI reading)
and `get_jaimini` (the Jaimini page's 1st/7th argala, the `get_jaimini` AI tool
and the Jaimini AI reading) both call the engine's `house.get_argala`. Its rows
are indexed by HOUSE counted from the Lagna (row 0 = 1st house) — the engine
already adds the ascendant offset. `get_jaimini` used to index them by SIGN
(lagna_sign + h - 1), offsetting by the Lagna twice, so for every chart whose
Lagna isn't Aries it reported another house's argala as the 1st's and 7th's.

Both reference charts have non-Aries lagnas, which is the case that bug hid in.
"""
import pytest

from astrology import AstrologyCompute as A


def _names(entries):
    return sorted(p for e in entries for p in e["planets"])


@pytest.mark.parametrize("args_fixture", ["args1", "args2"])
def test_jaimini_argala_matches_the_twelve_house_table(args_fixture, request):
    args = request.getfixturevalue(args_fixture)
    full = A.get_argala(**args)
    jaimini = A.get_jaimini(**args)
    assert full["status"] == "success" and jaimini["status"] == "success"
    assert full["lagna_sign"] != 0, "pick a chart whose Lagna isn't Aries"

    by_bhava = {row["bhava"]: row for row in full["houses"]}
    assert [a["house"] for a in jaimini["argala"]] == [1, 7]
    for a in jaimini["argala"]:
        row = by_bhava[a["house"]]
        assert a["sign_name"] == row["sign_name"]
        assert sorted(a["argala"]) == _names(row["argala"])
        assert sorted(a["virodhargala"]) == _names(row["virodhargala"])


def test_the_twelve_house_table_is_not_empty(args1):
    # "success with nothing in it" is the shape a dead feature takes.
    rows = A.get_argala(**args1)["houses"]
    assert len(rows) == 12
    assert any(r["argala"] for r in rows)
