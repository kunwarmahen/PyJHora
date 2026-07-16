"""Location lookup: forward search and reverse geocode.

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None


class GeoMixin:

    @staticmethod
    def search_location(query: str = "", *args, **kwargs):
        """Geocode a free-text place query to [display_name, lat, lon, tz_offset].

        Coordinates come from OpenStreetMap (Nominatim via geopy) and the UTC
        offset from timezonefinder (both already Jyotir AI dependencies). The tz
        offset reflects the place's *current* rules (incl. DST), which is what
        the form needs when picking a location. Returns None when nothing
        matches so the endpoint can report a friendly "not found"."""
        if not ENGINE_AVAILABLE:
            return None
        q = (query or "").strip()
        if not q:
            return None
        try:
            from geopy.geocoders import Nominatim

            geolocator = Nominatim(user_agent="JyotirAIWeb", timeout=10)
            loc = geolocator.geocode(q, language="en")
            if not loc:
                return None
            lat = round(loc.latitude, 6)
            lon = round(loc.longitude, 6)
            tz = utils.get_place_timezone_offset(lat, lon)
            return [loc.address, lat, lon, round(float(tz), 2)]
        except Exception as e:
            print(f"Location search error: {e}")
            return None

    @staticmethod
    def reverse_geocode(latitude, longitude, *args, **kwargs):
        """Resolve a clicked map point to [display_name, lat, lon, tz_offset].

        Used by the interactive map picker: the lat/long already come from the
        pin, so the timezone is computed offline with timezonefinder (no network
        needed) and Nominatim reverse-geocoding only supplies a friendly place
        name. If the reverse lookup fails we still return coordinates + tz with a
        synthesised label so a clicked point is always usable."""
        if not ENGINE_AVAILABLE:
            return None
        try:
            lat = round(float(latitude), 6)
            lon = round(float(longitude), 6)
        except (TypeError, ValueError):
            return None
        # Timezone is always derivable from coordinates alone (offline).
        try:
            tz = round(float(utils.get_place_timezone_offset(lat, lon)), 2)
        except Exception as e:
            print(f"Reverse geocode timezone error: {e}")
            tz = 0.0
        place = f"{lat}, {lon}"
        try:
            from geopy.geocoders import Nominatim

            geolocator = Nominatim(user_agent="JyotirAIWeb", timeout=10)
            loc = geolocator.reverse((lat, lon), language="en", zoom=10)
            if loc and loc.address:
                place = loc.address
        except Exception as e:
            # Network/rate-limit issues should not break the picker; keep coords.
            print(f"Reverse geocode lookup error: {e}")
        return [place, lat, lon, tz]
