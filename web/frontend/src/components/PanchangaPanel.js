import React, { useState, useEffect, useCallback } from "react";
import { Sun, Sunrise, Sunset, MapPin } from "lucide-react";
import { astrologyService } from "../services/api";

/**
 * Reverse-geocode coordinates to a "City, Country" label using BigDataCloud's
 * free, key-less, CORS-enabled client endpoint. Returns null on any failure —
 * the panchanga itself only needs lat/lon/timezone, so the name is cosmetic.
 */
async function reverseGeocode(latitude, longitude) {
  try {
    const res = await fetch(
      `https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${latitude}&longitude=${longitude}&localityLanguage=en`
    );
    const d = await res.json();
    const city = d.city || d.locality || d.principalSubdivision;
    return [city, d.countryName].filter(Boolean).join(", ") || null;
  } catch {
    return null;
  }
}

/**
 * Daily almanac (Panchanga) for a location. Defaults to the profile's birth
 * place, but can switch to the device's current location (browser geolocation)
 * for a true "today, here" almanac. A date picker lets the user check any day.
 * Self-contained: fetches independently so a failure never blanks the page.
 */
export const PanchangaPanel = ({ place, latitude, longitude, timezone }) => {
  const today = new Date().toISOString().split("T")[0];
  const [date, setDate] = useState(today);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Location source: 'birth' (profile) or 'current' (device geolocation).
  const [source, setSource] = useState("birth");
  const [currentLoc, setCurrentLoc] = useState(null);
  const [geoLoading, setGeoLoading] = useState(false);
  const [geoError, setGeoError] = useState("");

  const birthLoc = { place, latitude, longitude, timezone };
  const activeLoc = source === "current" && currentLoc ? currentLoc : birthLoc;

  const requestCurrentLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setGeoError("Geolocation isn't supported by this browser.");
      return;
    }
    setGeoLoading(true);
    setGeoError("");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = Number(pos.coords.latitude.toFixed(4));
        const lon = Number(pos.coords.longitude.toFixed(4));
        // getTimezoneOffset() is (UTC - local) in minutes; negate for the
        // east-positive offset PyJHora expects (e.g. IST -330 → +5.5).
        const tz = -new Date().getTimezoneOffset() / 60;
        const name = (await reverseGeocode(lat, lon)) || "Current location";
        setCurrentLoc({ place: name, latitude: lat, longitude: lon, timezone: tz });
        setSource("current");
        setGeoLoading(false);
      },
      (err) => {
        setGeoError(
          err.code === err.PERMISSION_DENIED
            ? "Location permission denied."
            : "Couldn't get your current location."
        );
        setGeoLoading(false);
      },
      { timeout: 10000, maximumAge: 600000 }
    );
  }, []);

  const useCurrent = () => {
    if (currentLoc) setSource("current");
    else requestCurrentLocation();
  };

  const load = useCallback(() => {
    if (activeLoc.latitude == null || activeLoc.longitude == null) return;
    setLoading(true);
    setError("");
    astrologyService
      .getPanchanga({ ...activeLoc, date })
      .then((r) => setData(r.data))
      .catch(() => setError("Panchanga unavailable for this place/date."))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeLoc.place, activeLoc.latitude, activeLoc.longitude, activeLoc.timezone, date]);

  useEffect(() => {
    load();
  }, [load]);

  const limbs = data && [
    { label: "Tithi", value: data.tithi?.name, ends: data.tithi?.ends },
    { label: "Vaara", value: data.vaara?.name },
    {
      label: "Nakshatra",
      value: data.nakshatra?.name,
      ends: data.nakshatra?.ends,
      sub: data.nakshatra?.pada ? `Pada ${data.nakshatra.pada}` : null,
    },
    { label: "Yoga", value: data.yoga?.name, ends: data.yoga?.ends },
    { label: "Karana", value: data.karana?.name, ends: data.karana?.ends },
  ];

  const range = (p) => (p && p.start ? `${p.start} – ${p.end}` : "—");

  return (
    <div className="panchanga-panel">
      <div className="panchanga-header">
        <h3>
          <Sun size={24} style={{ color: "var(--saffron)" }} />
          Panchanga
        </h3>
        <div className="panchanga-controls">
          <div className="chart-style-toggle" role="group" aria-label="Almanac location">
            <button
              className={source === "birth" ? "active" : ""}
              onClick={() => setSource("birth")}
            >
              Birth place
            </button>
            <button
              className={source === "current" ? "active" : ""}
              onClick={useCurrent}
              disabled={geoLoading}
            >
              {geoLoading ? "Locating…" : "Current location"}
            </button>
          </div>
          <input
            type="date"
            className="panchanga-date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            aria-label="Almanac date"
          />
        </div>
      </div>

      <div className="panchanga-place">
        <MapPin size={14} /> {activeLoc.place || "—"}
      </div>
      {geoError && <div className="panchanga-status">{geoError}</div>}

      {loading && <div className="panchanga-status">Loading almanac…</div>}
      {error && !loading && <div className="panchanga-status">{error}</div>}

      {data && !loading && !error && (
        <>
          <div className="panchanga-limbs">
            {limbs.map((l) => (
              <div key={l.label} className="panchanga-limb">
                <span className="panchanga-limb-label">{l.label}</span>
                <span className="panchanga-limb-value">{l.value || "—"}</span>
                {l.sub && <span className="panchanga-limb-sub">{l.sub}</span>}
                {l.ends && <span className="panchanga-limb-sub">until {l.ends}</span>}
              </div>
            ))}
          </div>

          <div className="panchanga-suntimes">
            <span>
              <Sunrise size={16} /> Sunrise {data.sunrise}
            </span>
            <span>
              <Sunset size={16} /> Sunset {data.sunset}
            </span>
          </div>

          <div className="panchanga-periods">
            <div className="panchanga-period inauspicious">
              <span className="panchanga-period-label">Rahu Kalam</span>
              <span className="panchanga-period-time">{range(data.rahu_kalam)}</span>
            </div>
            <div className="panchanga-period inauspicious">
              <span className="panchanga-period-label">Yamaganda</span>
              <span className="panchanga-period-time">{range(data.yamaganda)}</span>
            </div>
            <div className="panchanga-period inauspicious">
              <span className="panchanga-period-label">Gulika Kalam</span>
              <span className="panchanga-period-time">{range(data.gulika)}</span>
            </div>
            <div className="panchanga-period auspicious">
              <span className="panchanga-period-label">Abhijit Muhurta</span>
              <span className="panchanga-period-time">{range(data.abhijit)}</span>
            </div>
          </div>

          {data.durmuhurtam && data.durmuhurtam.length > 0 && (
            <div className="panchanga-durmuhurtam">
              <span className="panchanga-period-label">Durmuhurtam</span>
              <span>
                {data.durmuhurtam.map((d, i) => (
                  <span key={i} className="panchanga-durm-slot">
                    {d.start} – {d.end}
                  </span>
                ))}
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
};
