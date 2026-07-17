"""The zone/offset layer behind "where the user is now" (§40).

The bug this all exists to prevent: a person born in India, living in the US,
whose 7am digest arrived at 8:30pm the evening before. So the tests that matter
are the ones about a zone that *isn't* the birth zone, and about DST — which
India has never had, which is why the codebase went so long without noticing.
"""
from datetime import datetime, timezone as dt_timezone

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
