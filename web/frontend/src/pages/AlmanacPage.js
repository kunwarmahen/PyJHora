import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CalendarDays, MapPin, Clock, Moon, Sun, PartyPopper, Swords } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { PanchangaPanel } from "../components/PanchangaPanel";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

/**
 * Reverse-geocode via BigDataCloud's free, key-less client endpoint (same as
 * PanchangaPanel). Cosmetic only — the almanac needs lat/lon/tz, not the name.
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

const todayISO = () => new Date().toISOString().split("T")[0];
const addDaysISO = (iso, days) => {
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  return d.toISOString().split("T")[0];
};

/* ── Planetary hours (hora) ────────────────────────────────────────────── */
const HoraPanel = ({ loc }) => {
  const { t } = useTranslation();
  const [date, setDate] = useState(todayISO());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    if (loc.latitude == null || loc.longitude == null) return;
    setLoading(true);
    setError("");
    astrologyService
      .getPlanetaryHours({ ...loc, date })
      .then((r) => setData(r.data))
      .catch(() => setError(t("almanac.unavailable")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loc.place, loc.latitude, loc.longitude, loc.timezone, date]);

  useEffect(() => {
    load();
  }, [load]);

  const dayHoras = (data?.horas || []).filter((h) => h.period === "day");
  const nightHoras = (data?.horas || []).filter((h) => h.period === "night");

  const renderBlock = (horas, label) => (
    <div className="almanac-hora-block">
      <div className="almanac-subhead">{label}</div>
      <div className="almanac-hora-grid">
        {horas.map((h) => (
          <div
            key={h.index}
            className={`almanac-hora${h.benefic ? " is-benefic" : " is-malefic"}${
              h.current ? " is-current" : ""
            }`}
          >
            <span className="almanac-hora-time">
              {h.start} – {h.end}
            </span>
            <span className="almanac-hora-planet">{h.planet}</span>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="panchanga-panel">
      <div className="panchanga-header">
        <h3>
          <Clock size={24} style={{ color: "var(--saffron)" }} />
          {t("almanac.horaTitle")}
        </h3>
        <div className="panchanga-controls">
          <input
            type="date"
            className="panchanga-date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            aria-label={t("almanac.date")}
          />
        </div>
      </div>
      <p className="almanac-note">{t("almanac.horaNote")}</p>

      {loading && <div className="panchanga-status">{t("almanac.loading")}</div>}
      {error && !loading && <div className="panchanga-status">{error}</div>}

      {data && !loading && !error && (
        <>
          {renderBlock(dayHoras, t("almanac.daytime"))}
          {renderBlock(nightHoras, t("almanac.nighttime"))}
        </>
      )}
    </div>
  );
};

/* ── Eclipses ──────────────────────────────────────────────────────────── */
const EclipsePanel = ({ loc }) => {
  const { t } = useTranslation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    if (loc.latitude == null || loc.longitude == null) return;
    setLoading(true);
    setError("");
    astrologyService
      .getEclipses({ ...loc, count: 3 })
      .then((r) => setData(r.data))
      .catch(() => setError(t("almanac.unavailable")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loc.place, loc.latitude, loc.longitude, loc.timezone]);

  useEffect(() => {
    load();
  }, [load]);

  const instant = (i) => (i ? `${i.date} · ${i.time}` : "—");

  const renderList = (list, kind, Icon) => (
    <div className="almanac-ecl-col">
      <div className="almanac-subhead">
        <Icon size={16} /> {kind}
      </div>
      {(list || []).map((e, idx) => (
        <div key={idx} className="almanac-ecl-card">
          <div className="almanac-ecl-head">
            <span className={`almanac-ecl-type type-${e.type}`}>{e.type}</span>
            <span className="almanac-ecl-date">{e.date}</span>
          </div>
          <div className="almanac-ecl-times">
            <span>
              <strong>{t("almanac.begins")}</strong> {instant(e.begin)}
            </span>
            <span>
              <strong>{t("almanac.maximum")}</strong> {instant(e.maximum)}
            </span>
            <span>
              <strong>{t("almanac.ends")}</strong> {instant(e.end)}
            </span>
          </div>
        </div>
      ))}
      {(!list || list.length === 0) && (
        <div className="panchanga-status">{t("almanac.noneFound")}</div>
      )}
    </div>
  );

  return (
    <div className="panchanga-panel">
      <div className="panchanga-header">
        <h3>
          <Moon size={24} style={{ color: "var(--saffron)" }} />
          {t("almanac.eclipsesTitle")}
        </h3>
      </div>
      <p className="almanac-note">{t("almanac.eclipsesNote")}</p>

      {loading && <div className="panchanga-status">{t("almanac.loading")}</div>}
      {error && !loading && <div className="panchanga-status">{error}</div>}

      {data && !loading && !error && (
        <div className="almanac-ecl-grid">
          {renderList(data.solar, t("almanac.solar"), Sun)}
          {renderList(data.lunar, t("almanac.lunar"), Moon)}
        </div>
      )}
    </div>
  );
};

/* ── Festivals / vrathas ───────────────────────────────────────────────── */
const FESTIVAL_KEYS = [
  "ekadashi",
  "pradosham",
  "purnima",
  "amavasya",
  "sankashti",
  "chaturthi",
  "ashtami",
];
const DEFAULT_FESTIVALS = ["ekadashi", "pradosham", "purnima", "amavasya", "sankashti"];

const FestivalPanel = ({ loc }) => {
  const { t } = useTranslation();
  const [start, setStart] = useState(todayISO());
  const [end, setEnd] = useState(() => addDaysISO(todayISO(), 45));
  const [types, setTypes] = useState(DEFAULT_FESTIVALS);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    if (loc.latitude == null || loc.longitude == null) return;
    setLoading(true);
    setError("");
    astrologyService
      .getFestivals({ ...loc, start, end, types })
      .then((r) => setData(r.data))
      .catch(() => setError(t("almanac.unavailable")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loc.place, loc.latitude, loc.longitude, loc.timezone, start, end, types]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleType = (key) =>
    setTypes((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );

  const events = data?.events || [];

  return (
    <div className="panchanga-panel">
      <div className="panchanga-header">
        <h3>
          <PartyPopper size={24} style={{ color: "var(--saffron)" }} />
          {t("almanac.festivalsTitle")}
        </h3>
        <div className="panchanga-controls">
          <input
            type="date"
            className="panchanga-date"
            value={start}
            max={end}
            onChange={(e) => setStart(e.target.value)}
            aria-label={t("almanac.startDate")}
          />
          <span className="almanac-range-sep">–</span>
          <input
            type="date"
            className="panchanga-date"
            value={end}
            min={start}
            onChange={(e) => setEnd(e.target.value)}
            aria-label={t("almanac.endDate")}
          />
        </div>
      </div>

      <div className="almanac-chips">
        {FESTIVAL_KEYS.map((key) => (
          <button
            key={key}
            type="button"
            className={`almanac-chip${types.includes(key) ? " is-on" : ""}`}
            onClick={() => toggleType(key)}
          >
            {t(`almanac.festivalTypes.${key}`)}
          </button>
        ))}
      </div>

      {loading && <div className="panchanga-status">{t("almanac.loading")}</div>}
      {error && !loading && <div className="panchanga-status">{error}</div>}

      {data && !loading && !error && events.length === 0 && (
        <div className="panchanga-status">{t("almanac.noneFound")}</div>
      )}

      {events.length > 0 && !loading && !error && (
        <div className="almanac-fest-list">
          {events.map((ev, idx) => (
            <div key={idx} className="almanac-fest-row">
              <span className="almanac-fest-date">{ev.date}</span>
              <span className="almanac-fest-body">
                <span className="almanac-fest-name">{ev.name}</span>
                <span className="almanac-fest-meaning">{ev.meaning}</span>
              </span>
              {ev.ends && (
                <span className="almanac-fest-ends">
                  {t("almanac.tithiEnds", { time: ev.ends })}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/* ── Conjunctions (Graha Yuddha) ───────────────────────────────────────── */
const ConjunctionPanel = ({ loc }) => {
  const { t } = useTranslation();
  const [start, setStart] = useState(todayISO());
  const [end, setEnd] = useState(() => addDaysISO(todayISO(), 90));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    if (loc.latitude == null || loc.longitude == null) return;
    setLoading(true);
    setError("");
    astrologyService
      .getConjunctions({ ...loc, start, end })
      .then((r) => setData(r.data))
      .catch(() => setError(t("almanac.unavailable")))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loc.place, loc.latitude, loc.longitude, loc.timezone, start, end]);

  useEffect(() => {
    load();
  }, [load]);

  const events = data?.events || [];

  return (
    <div className="panchanga-panel">
      <div className="panchanga-header">
        <h3>
          <Swords size={24} style={{ color: "var(--saffron)" }} />
          {t("almanac.conjunctionsTitle")}
        </h3>
        <div className="panchanga-controls">
          <input
            type="date"
            className="panchanga-date"
            value={start}
            max={end}
            onChange={(e) => setStart(e.target.value)}
            aria-label={t("almanac.startDate")}
          />
          <span className="almanac-range-sep">–</span>
          <input
            type="date"
            className="panchanga-date"
            value={end}
            min={start}
            onChange={(e) => setEnd(e.target.value)}
            aria-label={t("almanac.endDate")}
          />
        </div>
      </div>
      <p className="almanac-note">{t("almanac.conjunctionsNote")}</p>

      {loading && <div className="panchanga-status">{t("almanac.loading")}</div>}
      {error && !loading && <div className="panchanga-status">{error}</div>}

      {data && !loading && !error && events.length === 0 && (
        <div className="panchanga-status">{t("almanac.noneFound")}</div>
      )}

      {events.length > 0 && !loading && !error && (
        <div className="almanac-fest-list">
          {events.map((ev, idx) => (
            <div key={idx} className="almanac-fest-row">
              <span className="almanac-fest-date">{ev.closest_date}</span>
              <span className="almanac-fest-body">
                <span className="almanac-fest-name">
                  {ev.planet1} &amp; {ev.planet2}
                  {ev.war && <span className="almanac-war-tag">{t("almanac.war")}</span>}
                </span>
                <span className="almanac-fest-meaning">
                  {t("almanac.conjWindow", { from: ev.from, to: ev.to })}
                </span>
              </span>
              <span className="almanac-fest-ends">
                {t("almanac.separation", { deg: ev.separation })}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

/* ── Page ──────────────────────────────────────────────────────────────── */
export const AlmanacPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile } = useProfile();

  const [source, setSource] = useState("birth");
  const [currentLoc, setCurrentLoc] = useState(null);
  const [geoLoading, setGeoLoading] = useState(false);
  const [geoError, setGeoError] = useState("");

  useEffect(() => {
    if (!selectedProfile) navigate("/profile-selection");
  }, [selectedProfile, navigate]);

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

  if (!selectedProfile) return null;

  const bd = selectedProfile.birth_details || {};
  const birthLoc = {
    place: bd.place,
    latitude: parseFloat(bd.latitude),
    longitude: parseFloat(bd.longitude),
    timezone: parseFloat(bd.timezone),
  };
  const loc = source === "current" && currentLoc ? currentLoc : birthLoc;

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        title={t("almanac.title")}
        subtitle={t("almanac.subtitle")}
        accent="gold"
        icon={<CalendarDays size={24} />}
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        {/* Shared location control for every almanac section */}
        <div className="almanac-locbar">
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
          <span className="almanac-locname">
            <MapPin size={14} /> {loc.place || "—"}
          </span>
        </div>
        {geoError && <div className="panchanga-status">{geoError}</div>}

        <PanchangaPanel {...loc} hideLocationToggle />
        <HoraPanel loc={loc} />
        <EclipsePanel loc={loc} />
        <FestivalPanel loc={loc} />
        <ConjunctionPanel loc={loc} />
      </div>
    </div>
  );
};
