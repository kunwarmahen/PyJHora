"""The zone/offset layer behind "where the user is now" (§40).

The bug this all exists to prevent: a person born in India, living in the US,
whose 7am digest arrived at 8:30pm the evening before. So the tests that matter
are the ones about a zone that *isn't* the birth zone, and about DST — which
India has never had, which is why the codebase went so long without noticing.
"""
from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

import timezones


class TestZoneAt:
    def test_finds_the_zone_for_a_us_city(self):
        assert timezones.zone_at(41.88, -87.63) == "America/Chicago"

    def test_finds_the_zone_for_an_indian_city(self):
        assert timezones.zone_at(27.88, 78.08) == "Asia/Kolkata"

    def test_gives_a_nautical_zone_in_the_middle_of_an_ocean(self):
        # timezonefinder covers open water with the nautical Etc/GMT±N zones
        # rather than a gap, so even a mis-dropped map pin yields a usable zone.
        # (Etc/GMT is sign-inverted by POSIX convention: GMT+2 is UTC-2.)
        zone = timezones.zone_at(0.0, -30.0)
        assert zone == "Etc/GMT+2"
        assert timezones.offset_hours(zone) == -2.0

    def test_survives_junk_coordinates(self):
        assert timezones.zone_at("nonsense", None) is None


class TestOffsetHours:
    def test_india_has_no_dst_so_its_offset_never_moves(self):
        jan = datetime(2026, 1, 15, 12, tzinfo=dt_timezone.utc)
        jul = datetime(2026, 7, 15, 12, tzinfo=dt_timezone.utc)
        assert timezones.offset_hours("Asia/Kolkata", jan) == 5.5
        assert timezones.offset_hours("Asia/Kolkata", jul) == 5.5

    def test_chicago_moves_with_dst(self):
        # THE bug a stored float offset cannot express: one zone, two offsets.
        # Whichever number you store, you are wrong for half the year.
        jan = datetime(2026, 1, 15, 12, tzinfo=dt_timezone.utc)
        jul = datetime(2026, 7, 15, 12, tzinfo=dt_timezone.utc)
        assert timezones.offset_hours("America/Chicago", jan) == -6.0
        assert timezones.offset_hours("America/Chicago", jul) == -5.0

    def test_resolves_a_45_minute_zone_exactly(self):
        jan = datetime(2026, 1, 15, 12, tzinfo=dt_timezone.utc)
        assert timezones.offset_hours("Asia/Kathmandu", jan) == 5.75

    def test_treats_a_naive_datetime_as_utc(self):
        # Callers pass engine-shaped naive datetimes; guessing "local to the
        # server" instead would make the answer depend on where it's deployed.
        naive = datetime(2026, 7, 15, 12)
        aware = datetime(2026, 7, 15, 12, tzinfo=dt_timezone.utc)
        assert timezones.offset_hours("America/Chicago", naive) == \
            timezones.offset_hours("America/Chicago", aware)

    def test_defaults_to_now(self):
        assert timezones.offset_hours("Asia/Kolkata") == 5.5

    @pytest.mark.parametrize("junk", [None, "", "Mars/Olympus", "UTC+5.5", 5.5])
    def test_is_none_for_anything_that_is_not_a_zone(self, junk):
        # "+5.5" is the shape of the OLD stored value; it must not silently pass.
        assert timezones.offset_hours(junk) is None


class TestIsValidZone:
    def test_accepts_a_real_zone(self):
        assert timezones.is_valid_zone("America/Chicago") is True

    @pytest.mark.parametrize("junk", [None, "", "Mars/Olympus", "5.5"])
    def test_rejects_everything_else(self, junk):
        assert timezones.is_valid_zone(junk) is False


class TestRepresentativePlace:
    def test_names_the_zone_city(self):
        assert timezones.representative_place("America/Chicago") == "Chicago"
        assert timezones.representative_place("Asia/Kolkata") == "Kolkata"
        assert timezones.representative_place("Europe/London") == "London"

    def test_turns_underscores_into_spaces(self):
        # Geocoders want "New York", not "New_York".
        assert timezones.representative_place("America/New_York") == "New York"

    def test_takes_the_last_segment_of_a_three_part_zone(self):
        assert timezones.representative_place("America/Argentina/Buenos_Aires") == "Buenos Aires"
        assert timezones.representative_place("America/Indiana/Indianapolis") == "Indianapolis"

    @pytest.mark.parametrize("zone", ["Etc/GMT+2", "Etc/UTC", "UTC", "", None, "Asia"])
    def test_is_none_when_the_zone_names_no_city(self, zone):
        # Etc/* is open water and POSIX-inverted; a bare region names nothing.
        # None sends the caller back to asking the user, which is the honest path.
        assert timezones.representative_place(zone) is None

    def test_every_city_it_names_is_findable_in_its_own_zone(self):
        # The property the /from-zone endpoint's verification relies on: the
        # representative city really does sit in the zone that's named after it.
        # (Checked against coordinates, not a geocoder — no network here.)
        for zone, lat, lon in [
            ("America/Chicago", 41.88, -87.63),
            ("Asia/Kolkata", 22.57, 88.36),
            ("Europe/London", 51.51, -0.13),
        ]:
            assert timezones.representative_place(zone)
            assert timezones.zone_at(lat, lon) == zone


class TestLocalNow:
    def test_gives_the_wall_clock_in_that_zone(self):
        chicago = timezones.local_now("America/Chicago")
        kolkata = timezones.local_now("Asia/Kolkata")
        assert chicago is not None and kolkata is not None
        # The same instant, two wall clocks — which is the whole point: asking
        # "is it 7am for them yet?" has a different answer in each.
        assert chicago.utcoffset() != kolkata.utcoffset()

    def test_is_timezone_aware(self):
        # The scheduler compares .hour/.day; a naive datetime here would silently
        # be read as server-local.
        assert timezones.local_now("Asia/Kolkata").tzinfo is not None

    @pytest.mark.parametrize("junk", [None, "", "Mars/Olympus"])
    def test_is_none_for_a_bad_zone(self, junk):
        assert timezones.local_now(junk) is None


class TestNowAtTz:
    """`_now_at_tz` — the engine's answer to "what day is it *where the user is*".

    The transit computes used `datetime.now()`, which reads the server's clock.
    On a UTC pod that calls it Aug 6 at 02:50 while the user in Cary, NC is still
    on the evening of Aug 5 — so their gochara-phala was dated a day ahead. India
    never noticed: a UTC server is only ever 5.5h behind IST, never across
    midnight in the direction that shows.
    """

    def test_matches_the_offset_applied_to_utc(self):
        from astrology.engine import _now_at_tz

        for offset in (-4.0, 5.5, 0.0, -12.0, 14.0):
            expected = (datetime.now(dt_timezone.utc) + timedelta(hours=offset)).replace(tzinfo=None)
            assert abs((_now_at_tz(offset) - expected).total_seconds()) < 5

    def test_the_calendar_date_really_follows_the_offset(self):
        from astrology.engine import _now_at_tz

        # The inhabited offsets span 26 hours (Baker Island to Kiritimati), so
        # these two can never be on the same calendar day — whatever the server
        # clock says. This fails outright if "now" is server-local.
        assert _now_at_tz(-12.0).date() != _now_at_tz(14.0).date()

    def test_falls_back_to_the_server_clock_when_no_offset_is_known(self):
        from astrology.engine import _now_at_tz

        assert abs((_now_at_tz(None) - datetime.now()).total_seconds()) < 5

    def test_gochara_phala_dates_the_snapshot_in_the_viewers_zone(self):
        # The reported bug, end to end: same instant, same birth chart, two
        # viewers 26 hours apart — they must not be handed the same "today".
        from astrology import AstrologyCompute as A
        from astrology.engine import _now_at_tz

        def transit_date(current_tz):
            r = A.get_gochara_phala(
                dob="1976-06-04", tob="05:45:02", place="Shahgarh",
                lat=27.845278, lon=78.334167, tz=5.5, current_tz=current_tz)
            assert r["status"] == "success"
            return r["transit_date"]

        assert transit_date(-4.0) == _now_at_tz(-4.0).strftime("%Y-%m-%d")
        assert transit_date(-12.0) != transit_date(14.0)


class TestNowAtOffset:
    """The shared primitive the engine, the tool layer and the prompt layer all
    date "now" by. `timezones.now_at_offset` is the one implementation;
    `astrology.engine._now_at_tz` is an alias so the compute mixins can reach it."""

    def test_engine_alias_is_the_same_function(self):
        from astrology.engine import _now_at_tz

        a, b = _now_at_tz(-4.0), timezones.now_at_offset(-4.0)
        assert abs((a - b).total_seconds()) < 2

    def test_today_at_offset_is_an_iso_date(self):
        assert timezones.today_at_offset(-4.0) == timezones.now_at_offset(-4.0).strftime("%Y-%m-%d")

    def test_the_two_extreme_offsets_are_never_the_same_day(self):
        assert timezones.today_at_offset(-12.0) != timezones.today_at_offset(14.0)


class TestViewerTz:
    """`deps.viewer_tz` — which offset a reading is dated by, and in what order
    the candidates win. The stored current location (§40) is the reason the AI
    paths are right without the frontend sending anything.

    Driven with `asyncio.run` rather than pytest-asyncio, matching conftest's
    ASGI client — the suite deliberately carries no async-test plugin."""

    @staticmethod
    def _call(monkeypatch, location, **kwargs):
        import asyncio

        import deps

        async def _loc(_uid):
            if isinstance(location, Exception):
                raise location
            return location

        monkeypatch.setattr(deps.user_settings, "get_current_location", _loc)
        return asyncio.run(deps.viewer_tz("u", **kwargs))

    def test_an_explicit_offset_from_the_browser_wins(self, monkeypatch):
        got = self._call(monkeypatch, {"timezone": "Asia/Kolkata"},
                         explicit=-4.0, fallback=5.5)
        assert got == -4.0

    def test_falls_back_to_the_stored_current_location(self, monkeypatch):
        # Resolved from the zone *now*, so it is the DST-correct offset, not a
        # number frozen at the time the location was saved.
        got = self._call(monkeypatch, {"timezone": "America/New_York"}, fallback=5.5)
        assert got in (-5.0, -4.0)
        assert got == timezones.offset_hours("America/New_York")

    def test_uses_the_birth_offset_when_no_location_is_stored(self, monkeypatch):
        assert self._call(monkeypatch, None, fallback=5.5) == 5.5

    def test_ignores_a_stored_location_with_an_unusable_zone(self, monkeypatch):
        assert self._call(monkeypatch, {"timezone": "Mars/Olympus"}, fallback=5.5) == 5.5

    def test_a_broken_lookup_never_breaks_the_reading(self, monkeypatch):
        assert self._call(monkeypatch, RuntimeError("mongo is down"), fallback=5.5) == 5.5

    def test_none_when_nothing_at_all_is_known(self, monkeypatch):
        # Callers read this as "use the server clock" — a guess, but an explicit one.
        assert self._call(monkeypatch, None) is None


class TestViewerDateReachesTheComputes:
    """The plumbing, end to end: an offset handed in at the top must change what
    the layers below call "today". Each of these was reading the server clock.

    ±12/+14 are used throughout because those two offsets are 26 hours apart and
    so can never share a calendar day — the assertion holds whatever the CI box's
    own timezone is, which a fixed expected date would not.
    """

    CHART = {"dob": "1976-06-04", "tob": "05:45:02", "place": "Shahgarh",
             "lat": 27.845278, "lon": 78.334167, "tz": 5.5}

    def test_get_dashas_picks_the_current_period_by_the_viewers_date(self):
        from astrology import AstrologyCompute as A

        r = A.get_dashas(current_tz=-4.0, **self.CHART)
        assert r.get("status") != "failed"
        cur = r.get("current_dasha") or {}
        today = timezones.today_at_offset(-4.0)
        assert cur.get("start_date") <= today <= cur.get("end_date")

    def test_chart_context_publishes_the_viewers_today(self):
        from chart_context import build_chart_context

        bd = {"dob": "1976-06-04", "tob": "05:45:02", "place": "Shahgarh",
              "latitude": 27.845278, "longitude": 78.334167, "timezone": 5.5}
        quiet = {k: False for k in
                 ("dasha_tree", "yogas", "doshas", "transits",
                  "ashtakavarga", "shadbala", "aspects", "arudhas")}
        ctx = build_chart_context(bd, sections=quiet, vargas=[1], current_tz=-4.0)
        assert ctx["today"] == timezones.today_at_offset(-4.0)
        # And it is genuinely offset-driven, not incidentally the server's date.
        west = build_chart_context(bd, sections=quiet, vargas=[1], current_tz=-12.0)
        east = build_chart_context(bd, sections=quiet, vargas=[1], current_tz=14.0)
        assert west["today"] != east["today"]

    def test_the_prompt_states_the_readers_date_not_the_servers(self):
        # prompts.py reads ctx["today"]; this is the line the user actually sees
        # as "as of ..." in a reading.
        from llm_service import llm_service

        block = llm_service._render_context_block({"today": "2026-08-05"})
        assert "2026-08-05" in block

    def test_the_tool_layer_dates_by_the_viewer_too(self):
        # dispatch injects current_tz into every handler's kwargs.
        import tools as tool_registry

        bd = {"dob": "1976-06-04", "tob": "05:45:02", "place": "Shahgarh",
              "latitude": 27.845278, "longitude": 78.334167, "timezone": 5.5}
        west = tool_registry.dispatch("get_gochara_phala", {}, bd, current_tz=-12.0)
        east = tool_registry.dispatch("get_gochara_phala", {}, bd, current_tz=14.0)
        assert west["transit_date"] != east["transit_date"]
        assert east["transit_date"] == timezones.today_at_offset(14.0)

    def test_a_handler_that_does_not_care_still_accepts_the_injection(self):
        # Every handler takes **_, so injecting current_tz must not TypeError on
        # the ones with no notion of "now".
        import tools as tool_registry

        bd = {"dob": "1976-06-04", "tob": "05:45:02", "place": "Shahgarh",
              "latitude": 27.845278, "longitude": 78.334167, "timezone": 5.5}
        r = tool_registry.dispatch("get_natal_chart", {}, bd, current_tz=-4.0)
        assert "error" not in r


class TestPanchaPakshiReadsTheDayWhereYouStand:
    """Pancha Pakshi divides the interval between sunrise and sunset into ten
    periods and tells you which to act in. Computed at the birth place, a user in
    North Carolina got a day that begins when the sun rises over India — the
    timings were real, but for a clock they were not on.

    The split the fix rests on: the *bird* is a constant of the nativity, the
    *timeline* is a clock. So the bird must not move with the viewer, and
    everything else must.
    """

    BIRTH = {"dob": "1976-06-04", "tob": "05:45:02", "place": "Shahgarh",
             "lat": 27.845278, "lon": 78.334167, "tz": 5.5}
    # Two real places far enough apart that sunrise cannot coincide.
    INDIA = {"current_place": "Shahgarh", "current_lat": 27.845278,
             "current_lon": 78.334167, "current_tz": 5.5}
    CARY = {"current_place": "Cary, NC", "current_lat": 35.7915,
            "current_lon": -78.7811, "current_tz": -4.0}

    def _run(self, **over):
        from astrology import AstrologyCompute as A

        r = A.get_pancha_pakshi(date="2026-08-06", **self.BIRTH, **over)
        assert r["status"] == "success"
        return r

    def test_the_birth_bird_does_not_move_with_the_viewer(self):
        assert self._run(**self.INDIA)["birth_bird"] == self._run(**self.CARY)["birth_bird"]

    def test_sunrise_and_sunset_are_the_viewers_own(self):
        india, cary = self._run(**self.INDIA), self._run(**self.CARY)
        assert india["sunrise"] != cary["sunrise"]
        assert india["sunset"] != cary["sunset"]

    def test_the_activity_windows_are_on_the_viewers_clock(self):
        india, cary = self._run(**self.INDIA), self._run(**self.CARY)
        assert india["segments"][0]["start"] == india["sunrise"]
        assert cary["segments"][0]["start"] == cary["sunrise"]
        assert india["best_times"][0]["start"] != cary["best_times"][0]["start"]

    def test_the_result_names_the_place_its_timings_belong_to(self):
        cary = self._run(**self.CARY)
        assert cary["place"] == "Cary, NC"
        assert cary["timezone"] == -4.0
        # The birth place is still reported, just not conflated with the clock.
        assert cary["birth_place"] == "Shahgarh"

    def test_omitting_the_current_place_keeps_the_old_birth_place_behaviour(self):
        # Nobody who lives where they were born should see any change.
        assert self._run() == self._run(**self.INDIA)

    def test_the_default_day_is_the_viewers_day(self):
        from astrology import AstrologyCompute as A

        def day(tz):
            return A.get_pancha_pakshi(**self.BIRTH, current_lat=1.87,
                                       current_lon=-157.4, current_tz=tz)["date"]

        assert day(-12.0) != day(14.0)

    def test_the_tool_layer_gets_the_viewers_place_injected(self):
        import tools as tool_registry

        bd = {"dob": "1976-06-04", "tob": "05:45:02", "place": "Shahgarh",
              "latitude": 27.845278, "longitude": 78.334167, "timezone": 5.5}
        viewer = {"place": "Cary, NC", "latitude": 35.7915,
                  "longitude": -78.7811, "timezone": -4.0}
        r = tool_registry.dispatch("get_pancha_pakshi", {"date": "2026-08-06"},
                                   bd, viewer=viewer)
        assert r["place"] == "Cary, NC"
        assert r["best_times"][0]["start"] == self._run(**self.CARY)["best_times"][0]["start"]
