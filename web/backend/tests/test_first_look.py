"""The newcomer's first look (§76.3/§76.7) and its funnel (§76.8).

The first look is the one screen a newcomer sees before anything else, so it must
agree with the pages they open next, and it must not pretend to a precision an
unknown birth time can't give.
"""
import pytest

import funnel
import ratelimit
from astrology import AstrologyCompute as A
from tests.conftest import CHART1, CHART2, _compute_args


@pytest.fixture(scope="module")
def look1():
    return A.get_first_look(current_tz=5.5, **_compute_args(CHART1))


# ── It agrees with the pages a newcomer opens next ───────────────────────────

@pytest.mark.parametrize("args_fixture", ["args1", "args2"])
def test_agrees_with_the_birth_chart_and_dasha_pages(args_fixture, request):
    args = request.getfixturevalue(args_fixture)
    look = A.get_first_look(current_tz=5.5, **args)
    chart = A.calculate_birth_chart(**args)
    dashas = A.get_dashas(current_tz=5.5, **args)
    assert look["status"] == "success"
    assert look["rising"]["sign_num"] == chart["lagna"]["sign_num"]
    moon = chart["d1_chart"]["Moon"]
    assert (look["moon"]["sign_num"], look["moon"]["nakshatra"], look["moon"]["pada"]) == (
        moon["sign_num"], moon["nakshatra"], moon["nakshatra_pada"])
    assert look["chapter"]["maha"]["lord"] == dashas["current_dasha"]["lord"]
    assert look["chapter"]["maha"]["start_date"] == dashas["current_dasha"]["start_date"]
    # The antardasha is the bhukti running on the chapter's own "today".
    today = look["chapter"]["today"]
    antar = look["chapter"]["antar"]
    assert antar["start_date"] <= today <= antar["end_date"]


def test_owner_chart_golden(look1):
    # 1976-06-04 05:45:02 Shahgarh — JHora-verified (conftest).
    assert look1["rising"]["sign_name"] == "Taurus"
    assert look1["moon"]["sign_name"] == "Leo"
    assert look1["moon"]["nakshatra"] == "Magha"
    assert look1["moon"]["nakshatra_index"] == 10      # 1-based: Magha is the 10th star
    assert look1["chapter"]["maha"]["lord"] == "Rahu"
    assert look1["chapter"]["approximate"] is False


def test_is_structured_data_only(look1):
    """No prose: every sentence is the frontend's, keyed by these values, so it
    translates (docs/I18N_DATA_LAYER_DESIGN.md layer A). A string longer than a
    name or a date here would be prose sneaking in."""
    def strings(o):
        if isinstance(o, dict):
            for v in o.values():
                yield from strings(v)
        elif isinstance(o, list):
            for v in o:
                yield from strings(v)
        elif isinstance(o, str):
            yield o
    assert max(len(s) for s in strings(look1)) <= 20


# ── Honest about an unknown birth time ───────────────────────────────────────

def test_unknown_time_withholds_the_rising_sign(args1):
    look = A.get_first_look(time_accuracy="unknown", current_tz=5.5,
                            **{**args1, "tob": "12:00:00"})
    assert look["rising"] is None
    assert look["chapter"]["approximate"] is True


def test_unknown_time_flags_a_moon_that_changed_sign_that_day(args1):
    # On 1976-06-04 the Moon crossed from Cancer into Leo — and from Ashlesha into
    # Magha — so neither can be stated without the time.
    look = A.get_first_look(time_accuracy="unknown", current_tz=5.5,
                            **{**args1, "tob": "12:00:00"})
    m = look["moon"]
    assert m["sign_certain"] is False and m["star_certain"] is False
    assert m["day_range"]["start"]["sign_name"] == "Cancer"
    assert m["day_range"]["end"]["sign_name"] == "Leo"


def test_exact_time_is_certain(look1):
    assert look1["moon"]["sign_certain"] is True and look1["moon"]["star_certain"] is True
    assert "day_range" not in look1["moon"]


# ── The routes ───────────────────────────────────────────────────────────────

def _body(chart, **extra):
    return {"birth_details": chart, **extra}


def test_signed_in_route(client):
    r = client.post("/api/astrology/first-look", json=_body(CHART1, current_tz=5.5))
    assert r.status_code == 200, r.text
    assert r.json()["moon"]["nakshatra"] == "Magha"


def test_public_route_needs_no_account(client):
    r = client.post("/api/public/first-look", json=_body(CHART2, current_tz=5.5),
                    headers={"x-forwarded-for": "198.51.100.7"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "success"


@pytest.mark.parametrize("patch, needle", [
    ({"dob": "04/06/1976"}, "YYYY-MM-DD"),
    ({"tob": "5.45"}, "YYYY-MM-DD"),
    ({"dob": "1500-01-01"}, "1800"),
    ({"latitude": None}, "place"),
    ({"latitude": 123.0}, "range"),
    ({"timezone": 20.0}, "range"),
])
def test_public_route_rejects_bad_input(client, patch, needle):
    r = client.post("/api/public/first-look", json=_body({**CHART2, **patch}),
                    headers={"x-forwarded-for": "198.51.100.8"})
    assert r.status_code == 422
    assert needle in r.text


def test_public_route_is_rate_limited(client, monkeypatch):
    monkeypatch.setenv("PUBLIC_RATE_LIMIT_PER_MIN", "2")
    ip = {"x-forwarded-for": "203.0.113.99"}
    codes = [client.post("/api/public/first-look", json=_body(CHART2), headers=ip).status_code
             for _ in range(3)]
    assert codes == [200, 200, 429]
    # Another caller is unaffected.
    other = client.post("/api/public/first-look", json=_body(CHART2),
                        headers={"x-forwarded-for": "203.0.113.100"})
    assert other.status_code == 200


def test_global_cap_holds_whatever_the_caller_key(monkeypatch):
    monkeypatch.setenv("PUBLIC_RATE_LIMIT_GLOBAL_PER_HOUR", "3")
    monkeypatch.setattr(ratelimit, "_public_all", ratelimit.deque())
    results = [ratelimit.public_check(f"forged-{i}")[0] for i in range(4)]
    assert results == [True, True, True, False]


def test_funnel_beacon_accepts_only_anonymous_steps(client):
    assert client.post("/api/public/funnel", json={"event": "landing_view"}).status_code == 200
    # A client must not be able to claim an account milestone.
    assert client.post("/api/public/funnel", json={"event": "first_ask"}).status_code == 422
    assert client.post("/api/public/funnel", json={"event": "nonsense"}).status_code == 422


# ── The funnel's arithmetic ──────────────────────────────────────────────────

def test_median_minutes_ignores_missing_and_backwards_pairs():
    from datetime import datetime, timedelta, timezone
    t0 = datetime(2026, 10, 1, tzinfo=timezone.utc)
    pairs = [(t0, t0 + timedelta(minutes=1)), (t0, t0 + timedelta(minutes=3)),
             (t0, t0 + timedelta(minutes=10)), (t0, None), (t0, t0 - timedelta(minutes=5))]
    assert funnel._median_minutes(pairs) == 3.0
    assert funnel._median_minutes([]) is None


def test_parse_accepts_both_stored_forms():
    from datetime import datetime, timezone
    assert funnel._parse("2026-10-01T10:00:00+00:00") == datetime(2026, 10, 1, 10, tzinfo=timezone.utc)
    assert funnel._parse(datetime(2026, 10, 1, 10)).tzinfo is not None   # naive → UTC
    assert funnel._parse("garbage") is None and funnel._parse(None) is None


def test_steps_are_ordered_and_split():
    assert set(funnel.ANON_EVENTS).isdisjoint(funnel.MILESTONES)
    assert funnel.EVENTS[0] == "landing_view" and funnel.EVENTS[-1] == "returned_day7"
