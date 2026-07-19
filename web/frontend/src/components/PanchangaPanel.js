import React, { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { Sun, Sunrise, Sunset, MapPin } from "lucide-react";
import { astrologyService } from "../services/api";
import { useSettings } from "../contexts/SettingsContext";
import { useLocalizeName } from "../i18n/localizeName";

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
export const PanchangaPanel = ({
  place,
  latitude,
  longitude,
  timezone,
  hideLocationToggle = false,
}) => {
  const { t } = useTranslation();
  const ln = useLocalizeName();
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

  // Ephemeris engine ('drik' | 'surya_siddhanta') is a global setting now.
  const { settings } = useSettings();
  const system = settings.panchangaSystem;

  const birthLoc = { place, latitude, longitude, timezone };
  const activeLoc = source === "current" && currentLoc ? currentLoc : birthLoc;

  const requestCurrentLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setGeoError(t("panchanga.geoUnsupported"));
      return;
    }
    setGeoLoading(true);
    setGeoError("");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = Number(pos.coords.latitude.toFixed(4));
        const lon = Number(pos.coords.longitude.toFixed(4));
        // getTimezoneOffset() is (UTC - local) in minutes; negate for the
        // east-positive offset Jyotir AI expects (e.g. IST -330 → +5.5).
        const tz = -new Date().getTimezoneOffset() / 60;
        const name = (await reverseGeocode(lat, lon)) || t("panchanga.currentLocation");
        setCurrentLoc({ place: name, latitude: lat, longitude: lon, timezone: tz });
        setSource("current");
        setGeoLoading(false);
      },
      (err) => {
        setGeoError(
          err.code === err.PERMISSION_DENIED
            ? t("panchanga.permissionDenied")
            : t("panchanga.geoFailed")
        );
        setGeoLoading(false);
      },
      { timeout: 10000, maximumAge: 600000 }
    );
  }, [t]);

  const useCurrent = () => {
    if (currentLoc) setSource("current");
    else requestCurrentLocation();
  };

  const load = useCallback(() => {
    if (activeLoc.latitude == null || activeLoc.longitude == null) return;
    setLoading(true);
    setError("");
    astrologyService
      .getPanchanga({ ...activeLoc, date, system })
      .then((r) => setData(r.data))
      .catch(() => setError(t("panchanga.unavailable")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeLoc.place, activeLoc.latitude, activeLoc.longitude, activeLoc.timezone, date, system]);

  useEffect(() => {
    load();
  }, [load]);

  const limbs = data && [
    { label: t("panchanga.tithi"), value: data.tithi?.name, ends: data.tithi?.ends },
    { label: t("panchanga.vaara"), value: data.vaara?.name },
    {
      label: t("common.nakshatra"),
      value: ln(data.nakshatra?.name, "nakshatra"),
      ends: data.nakshatra?.ends,
      sub: data.nakshatra?.pada ? `${t("common.pada")} ${data.nakshatra.pada}` : null,
    },
    { label: t("panchanga.yoga"), value: data.yoga?.name, ends: data.yoga?.ends },
    { label: t("panchanga.karana"), value: data.karana?.name, ends: data.karana?.ends },
  ];

  const range = (p) => (p && p.start ? `${p.start} – ${p.end}` : "—");

  return (
    <div className="panchanga-panel">
      <div className="panchanga-header">
        <h3>
          <Sun size={24} style={{ color: "var(--saffron)" }} />
          {t("panchanga.title")}
        </h3>
        <div className="panchanga-controls">
          {!hideLocationToggle && (
            <div
              className="chart-style-toggle"
              role="group"
              aria-label={t("panchanga.almanacLocation")}
            >
              <button
                className={source === "birth" ? "active" : ""}
                onClick={() => setSource("birth")}
              >
                {t("panchanga.birthPlace")}
              </button>
              <button
                className={source === "current" ? "active" : ""}
                onClick={useCurrent}
                disabled={geoLoading}
              >
                {geoLoading ? t("panchanga.locating") : t("panchanga.currentLocation")}
              </button>
            </div>
          )}
          <input
            type="date"
            className="panchanga-date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            aria-label={t("panchanga.almanacDate")}
          />
        </div>
      </div>

      <div className="panchanga-place">
        <MapPin size={14} /> {activeLoc.place || "—"}
      </div>
      {geoError && <div className="panchanga-status">{geoError}</div>}

      {loading && <div className="panchanga-status">{t("panchanga.loadingAlmanac")}</div>}
      {error && !loading && <div className="panchanga-status">{error}</div>}

      {data && !loading && !error && (
        <>
          <div className="panchanga-limbs">
            {limbs.map((l) => (
              <div key={l.label} className="panchanga-limb">
                <span className="panchanga-limb-label">{l.label}</span>
                <span className="panchanga-limb-value">{l.value || "—"}</span>
                {l.sub && <span className="panchanga-limb-sub">{l.sub}</span>}
                {l.ends && (
                  <span className="panchanga-limb-sub">
                    {t("panchanga.until", { time: l.ends })}
                  </span>
                )}
              </div>
            ))}
          </div>

          <div className="panchanga-suntimes">
            <span>
              <Sunrise size={16} /> {t("panchanga.sunrise")} {data.sunrise}
            </span>
            <span>
              <Sunset size={16} /> {t("panchanga.sunset")} {data.sunset}
            </span>
          </div>

          {data.hijri && (
            <div className="panchanga-place">
              {t("panchanga.hijri")}: {data.hijri.day} {data.hijri.month_name} {data.hijri.year} AH
            </div>
          )}

          <div className="panchanga-periods">
            <div className="panchanga-period inauspicious">
              <span className="panchanga-period-label">{t("panchanga.rahuKalam")}</span>
              <span className="panchanga-period-time">{range(data.rahu_kalam)}</span>
            </div>
            <div className="panchanga-period inauspicious">
              <span className="panchanga-period-label">{t("panchanga.yamaganda")}</span>
              <span className="panchanga-period-time">{range(data.yamaganda)}</span>
            </div>
            <div className="panchanga-period inauspicious">
              <span className="panchanga-period-label">{t("panchanga.gulikaKalam")}</span>
              <span className="panchanga-period-time">{range(data.gulika)}</span>
            </div>
            <div className="panchanga-period auspicious">
              <span className="panchanga-period-label">{t("panchanga.abhijit")}</span>
              <span className="panchanga-period-time">{range(data.abhijit)}</span>
            </div>
          </div>

          {data.durmuhurtam && data.durmuhurtam.length > 0 && (
            <div className="panchanga-durmuhurtam">
              <span className="panchanga-period-label">{t("panchanga.durmuhurtam")}</span>
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
