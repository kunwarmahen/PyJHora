# Places, coordinates and timezones

Every chart needs a latitude, a longitude and a UTC offset. Nobody knows those
for their birthplace, so the app finds them from a place name or a map pin.

> Replaces six 2025 notes (`LOCATION_*`, `README_LOCATION_FEATURE`,
> `INTEGRATION_EXAMPLE`, `BUGFIX_SUMMARY`, `TESTING_GUIDE`, now in
> `docs/archive/`). They described a local city database and a Google Maps
> scraper that no longer exist.

## How a place is found

| Way in | Component | Endpoint | Where it's used |
|---|---|---|---|
| Type a place name | `components/LocationSearch.js` | `POST /api/location/search` | profile form, Settings → Location |
| Drop a pin | `components/MapPicker.js` (Leaflet + OSM tiles, lazy-loaded) | `POST /api/location/reverse` | profile form |
| Browser timezone | `components/LocationPrompt.js` | `POST /api/user/location/from-zone` | dashboard ("you seem to be on …") |

**Search** (`astrology/compute_geo.py: search_location`): OpenStreetMap
Nominatim via `geopy` for the coordinates, then `timezonefinder` (through
PyJHora's `utils.get_place_timezone_offset`) for the offset. Returns
`{success, place, latitude, longitude, timezone}`, or `success: false` with a
"try 'City, Country'" message. Nothing is cached server-side.

**Reverse** (`reverse_geocode`): the pin already gives lat/long, so the timezone
is computed offline; Nominatim only supplies a friendly name, and a failed lookup
still returns coordinates + offset with a synthesised label.

**The map picker can be switched off** for a deployment: `MAP_PICKER_ENABLED=false`
(backend, returns 403) together with `REACT_APP_ENABLE_MAP_PICKER=false`
(frontend, hides the button). Keep the two in sync.

## Things that bite

- **The offset is today's rule, not the birth year's.** `timezonefinder` gives
  the place's current offset (including DST). For a birth in a year with
  different rules — war time, pre-1947 India, a DST birth — the user must
  correct the timezone field by hand. The form shows it for that reason.
- **Offline, the form can't be submitted**: the lat/long inputs are hidden and
  filled by the geocoder. For tests, seed a profile over `/api/profiles/save`
  (see the `verify` skill).
- **Birth place vs where you live** are different things: the chart uses the
  birth place; "today", sunrise-based timings and digests use the reader's
  current location (Settings → Location). See README → *Current location*.

## Trying it

```bash
curl -s -X POST localhost:8000/api/location/search \
  -H 'Content-Type: application/json' -d '{"query":"Chennai, India"}'
```
