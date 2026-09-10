"""The chart's forward calendar and its alerts (§70).

Two halves, tested differently:

  • The **compute** is pure and deterministic, so it is checked against the
    owner's chart with a fixed `from_date` — including the one event §67 worked
    out by hand and threw away (Saturn leaving the 8th on 2027-06-03).
  • The **delivery** rules are checked without a database: which events are due,
    how a kind filter narrows them, and that the preference whitelist cannot
    store a kind the compute never emits.
"""
import pytest

from astrology import EVENT_KINDS, AstrologyCompute

from .conftest import CHART1, _compute_args

AYAN = "TRUE_CITRA"
FROM = "2026-09-10"          # fixed, so every assertion below is reproducible


@pytest.fixture(scope="module")
def calendar():
    return AstrologyCompute.get_upcoming_events(
        months=36, from_date=FROM, ayanamsa=AYAN, **_compute_args(CHART1))


def test_the_calendar_computes(calendar):
    assert calendar["status"] == "success"
    assert calendar["from_date"] == FROM
    assert calendar["events"], "a chart always has something coming"
    assert calendar["lagna_sign"] == "Taurus"


def test_every_event_kind_is_one_the_registry_knows(calendar):
    """`EVENT_KINDS` feeds the compute's counts, the notification preferences and
    the UI's filter chips. A kind in one and not the others is a dead chip."""
    assert {e["kind"] for e in calendar["events"]} <= set(EVENT_KINDS)
    assert set(calendar["counts"]) == set(EVENT_KINDS)


def test_events_are_sorted_and_inside_the_window(calendar):
    dates = [e["date"] for e in calendar["events"]]
    assert dates == sorted(dates)
    assert all(calendar["from_date"] <= d <= calendar["to_date"] for d in dates)


def test_keys_are_unique_and_stable(calendar):
    """The key is what stops a refresh re-alerting on an event already sent, so
    it must be unique within a run and identical across runs."""
    keys = [e["key"] for e in calendar["events"]]
    assert len(keys) == len(set(keys))
    again = AstrologyCompute.get_upcoming_events(
        months=36, from_date=FROM, ayanamsa=AYAN, **_compute_args(CHART1))
    assert [e["key"] for e in again["events"]] == keys


def test_the_event_sixty_seven_threw_away(calendar):
    """§67 computed exactly this date in passing, to answer a question, and kept
    nothing. It is the reason this feature exists."""
    saturn = [e for e in calendar["events"] if e["kind"] == "saturn"]
    assert any(e["date"] == "2027-06-03" and "ends" in e["title"] for e in saturn), \
        [(e["date"], e["title"]) for e in saturn]


def test_events_are_counted_from_this_chart(calendar):
    """"Saturn enters Aries" is an almanac; "Saturn enters your 12th" is a
    reading. Every moving-planet event carries the house from each reference the
    app reads a transit from."""
    movers = [e for e in calendar["events"] if e["kind"] in ("ingress", "station")]
    assert movers
    for e in movers:
        assert 1 <= e["house_from_lagna"] <= 12
        assert 1 <= e["house_from_moon"] <= 12
        assert 1 <= e["house_from_al"] <= 12          # §60's third reference
    assert any("your" in e["title"] for e in movers)


def test_fast_planets_do_not_flood_the_calendar(calendar):
    """The Sun changes sign every 30 days and Mercury faster still. Alerting on
    those is a monthly almanac, not news about your chart."""
    ingress_planets = {e["planet"] for e in calendar["events"]
                       if e["kind"] == "ingress"}
    assert not ingress_planets & {"Sun", "Mercury", "Venus"}
    assert "Saturn" in ingress_planets or "Jupiter" in ingress_planets


def test_both_kinds_of_eclipse_are_reported(calendar):
    """Lunar eclipses were silently missing everywhere: the engine fills the
    phases an eclipse *lacks* with a JD-zero sentinel rather than None, so a
    penumbral eclipse (which has no partial phase) came out dated -4713-11-24
    and was dropped downstream. Found while building this (§70)."""
    kinds = {e["title"].split()[0].lower() for e in calendar["events"]
             if e["kind"] == "eclipse"}
    assert "lunar" in kinds and "solar" in kinds


def test_a_dasha_change_is_named_at_the_right_level(calendar):
    """Level 2 is the Antardasha (Bhukti); "Antara" collides with it and makes a
    reader place a level-3 lord one rung too high."""
    dasha = [e for e in calendar["events"] if e["kind"] == "dasha"]
    assert dasha, "36 months should contain at least one period change"
    for e in dasha:
        assert "Antardasha (Bhukti)" in e["title"] or "Mahadasha" in e["title"]
        assert "Antara " not in e["title"]


def test_the_horizon_is_bounded():
    """`months` is clamped, so a hand-built request cannot ask for a century of
    daily scanning."""
    r = AstrologyCompute.get_upcoming_events(
        months=9999, from_date=FROM, ayanamsa=AYAN, **_compute_args(CHART1))
    assert r["months"] == 60


# ── Delivery rules (no database) ────────────────────────────────────────────

def test_only_known_kinds_can_be_stored_as_a_preference():
    """An unknown kind here would be a filter that silently matches nothing —
    the user would switch alerts on and never hear anything."""
    import notifications
    assert set(notifications.DEFAULT_PREFS["event_kinds"]) == set(EVENT_KINDS)


def test_the_preferences_ui_and_the_compute_read_one_list():
    """Two lists that must agree are a bug waiting to happen (§52): the kinds the
    compute emits, the kinds a user may subscribe to, and the chips the UI draws
    are all `EVENT_KINDS`."""
    import events
    assert events.HORIZON_MONTHS >= 1
    from routes import notifications as notif_routes   # imports must resolve
    assert notif_routes.EVENT_KINDS is EVENT_KINDS


def test_due_window_and_claim_rules_are_pure(monkeypatch):
    """`due()` is where a lead time turns into a date range. Checked directly
    rather than through Mongo: the range arithmetic is the part that decides
    whether someone is told three days early or three days late."""
    import asyncio
    from datetime import datetime, timedelta

    import events as events_mod

    captured = {}

    class _Cursor:
        def sort(self, *_a, **_k):
            return self

        def __aiter__(self):
            async def _gen():
                return
                yield  # pragma: no cover - an empty async iterator
            return _gen()

    class _Collection:
        def find(self, query):
            captured["query"] = query
            return _Cursor()

    monkeypatch.setattr(events_mod, "get_database", lambda: {"chart_events": _Collection()})
    prefs = {"event_lead_days": 5, "event_kinds": ["saturn", "nonsense"]}
    asyncio.run(events_mod.due("u", prefs, today="2026-09-10"))

    q = captured["query"]
    assert q["notified_at"] is None                 # never re-tell
    assert q["kind"]["$in"] == ["saturn"]           # the bogus kind is dropped
    assert q["date"]["$lte"] == "2026-09-15"        # today + lead
    # A crossing missed while the deployment was down is still worth sending;
    # one from last month is noise.
    floor = datetime.strptime("2026-09-10", "%Y-%m-%d") - timedelta(
        days=events_mod.LATE_GRACE_DAYS)
    assert q["date"]["$gte"] == floor.strftime("%Y-%m-%d")


def test_alerts_do_nothing_when_switched_off():
    import asyncio
    import events as events_mod
    result = asyncio.run(events_mod.send_alerts_for_user("u", {"event_alerts": False}))
    assert result == {"status": "skipped", "reason": "disabled"}
