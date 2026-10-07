"""§86 — the daily periods-to-avoid calendar feed.

Rahu Kalam, Yamaganda and Gulika Kalam as timed iCal events, at the reader's
stored current location. DB-free: the location lookup is stubbed.
"""
from datetime import date, datetime, timedelta, timezone

import pytest

import ical
from astrology import AstrologyCompute

CARY = {"place": "Cary, NC", "latitude": 35.7915, "longitude": -78.7811,
        "timezone": "America/New_York"}


# ── tokens ──────────────────────────────────────────────────────────────────
def test_periods_token_round_trips():
    assert ical.verify_periods_token(ical.make_periods_token("alice")) == "alice"


def test_a_tampered_periods_token_is_rejected():
    tok = ical.make_periods_token("alice")
    payload, sig = tok.split(".", 1)
    forged = ical._b64(b"mallory") + "." + sig
    assert ical.verify_periods_token(forged) is None
    assert ical.verify_periods_token("garbage") is None


def test_chart_and_periods_tokens_are_not_interchangeable():
    # Separate signing domains: neither feed's link opens the other.
    chart = ical.make_token("alice", "p1")
    periods = ical.make_periods_token("alice")
    assert ical.verify_periods_token(chart) is None
    assert ical.verify_token(periods) is None


# ── events ──────────────────────────────────────────────────────────────────
def test_three_windows_a_day_matching_the_panchanga():
    start = date(2026, 10, 6)
    evs = ical.gather_avoid_periods(CARY, days=3, start=start)
    assert len(evs) == 9  # never "success with nothing in it"
    titles = {e["title"] for e in evs}
    assert titles == {"⛔ Rahu Kalam", "⛔ Yamaganda", "⛔ Gulika Kalam"}

    # The feed's local clock times are exactly the panchanga card's.
    p = AstrologyCompute.get_panchanga(date="2026-10-06", lat=CARY["latitude"],
                                       lon=CARY["longitude"], tz=-4.0)
    edt = timezone(timedelta(hours=-4))
    rahu = next(e for e in evs if e["title"] == "⛔ Rahu Kalam")
    assert rahu["start"].astimezone(edt).strftime("%H:%M") == p["rahu_kalam"]["start"]
    assert rahu["end"].astimezone(edt).strftime("%H:%M") == p["rahu_kalam"]["end"]
    assert all(e["start"].tzinfo is not None and e["end"] > e["start"] for e in evs)


def test_the_offset_follows_dst_day_by_day():
    # US DST ends 2026-11-01. Compare two Saturdays either side of it (Rahu
    # Kalam is a weekday-fixed slice of the daylight). The sun doesn't care
    # about clocks: the UTC instant barely moves while the wall-clock time
    # drops by about an hour — and the event text must quote that new local
    # time, which only a per-day offset gets right.
    evs = ical.gather_avoid_periods(CARY, days=8, start=date(2026, 10, 31))
    rahu = [e for e in evs if e["title"] == "⛔ Rahu Kalam"]
    before, after = rahu[0], rahu[7]
    assert abs((after["start"] - timedelta(days=7)) - before["start"]) < timedelta(minutes=15)
    est = timezone(timedelta(hours=-5))
    assert after["start"].astimezone(est).strftime("%H:%M") in after["desc"]


def test_no_location_means_no_events_not_a_guess():
    assert ical.gather_avoid_periods({}) == []
    assert ical.gather_avoid_periods({"timezone": "America/New_York"}) == []


# ── serialisation ───────────────────────────────────────────────────────────
def test_timed_events_serialise_in_utc_with_stable_uids():
    evs = ical.gather_avoid_periods(CARY, days=2, start=date(2026, 10, 6))
    a = ical.build_ics("X", evs)
    b = ical.build_ics("X", evs[1:])  # a refresh that dropped yesterday's first
    assert "DTSTART:2026" in a and "DTEND:2026" in a and "VALUE=DATE" not in a
    uids = lambda s: [l for l in s.split("\r\n") if l.startswith("UID:")]
    assert len(set(uids(a))) == len(evs)
    # Keyed on the instant, not the list position — so the app updates, not duplicates.
    assert set(uids(b)) <= set(uids(a))


def test_all_day_events_still_serialise_as_dates():
    body = ical.build_ics("X", [{"date": "2030-01-01", "title": "t", "desc": "d"}])
    assert "DTSTART;VALUE=DATE:20300101" in body


# ── endpoints ───────────────────────────────────────────────────────────────
@pytest.fixture
def stub_location(monkeypatch):
    import user_settings
    state = {"loc": CARY}

    async def _loc(_uid):
        return state["loc"]

    monkeypatch.setattr(user_settings, "get_current_location", _loc)
    return state


def test_token_endpoint_reports_whether_a_location_is_set(client, stub_location):
    r = client.get("/api/calendar/periods-token")
    assert r.status_code == 200
    body = r.json()
    assert body["has_location"] is True and body["place"] == "Cary, NC"
    assert body["path"] == f"/api/calendar/periods/{body['token']}.ics"

    stub_location["loc"] = None
    assert client.get("/api/calendar/periods-token").json()["has_location"] is False


def test_feed_serves_ics_and_rejects_bad_tokens(client, stub_location):
    tok = ical.make_periods_token("test-user")
    r = client.get(f"/api/calendar/periods/{tok}.ics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    assert r.text.count("BEGIN:VEVENT") == 3 * ical.PERIODS_DAYS
    assert client.get("/api/calendar/periods/nope.ics").status_code == 403
    # A chart-feed token must not open the periods feed.
    assert client.get(f"/api/calendar/periods/{ical.make_token('test-user', 'p')}.ics").status_code == 403


def test_feed_is_empty_not_an_error_without_a_location(client, stub_location):
    stub_location["loc"] = None
    r = client.get(f"/api/calendar/periods/{ical.make_periods_token('test-user')}.ics")
    assert r.status_code == 200 and "BEGIN:VEVENT" not in r.text
