import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Orbit, Calendar, TrendingUp, RotateCcw } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { useSettings } from "../contexts/SettingsContext";
import { astrologyService } from "../services/api";
import { intlLocale } from "../utils/format";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { TransitChat } from "../components/TransitChat";
import { PLANET_ABBR, AYANAMSAS } from "../constants/jyotish";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

const pad2 = (n) => String(n).padStart(2, "0");

// Local calendar date (NOT toISOString, which is UTC and can be off by a day).
const dateISO = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
// Local wall-clock HH:MM.
const timeISO = (d) => `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
// UTC offset of a date in float hours (e.g. 5.5 IST, -5 EST); honours DST.
const tzOffset = (d) => -d.getTimezoneOffset() / 60;

const formatDate = (dateStr, locale = "en-US") => {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch (e) {
    return "—";
  }
};

// Order grahas the traditional way for the table.
const PLANET_ORDER = [
  "Sun",
  "Moon",
  "Mars",
  "Mercury",
  "Jupiter",
  "Venus",
  "Saturn",
  "Rahu",
  "Ketu",
];

const ordinal = (n) => {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
};

export const TransitPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  // The transit moment is stored as epoch ms (a primitive, so effect deps stay
  // stable). Defaults to "now"; the date/time inputs and the ±steppers move it.
  const [momentMs, setMomentMs] = useState(() => Date.now());
  const moment = useMemo(() => new Date(momentMs), [momentMs]);
  const transitDate = dateISO(moment);
  const transitTime = timeISO(moment);

  // Shift the moment by ±n of a field (honours month/year rollover and DST).
  const shift = (field, amount) => {
    const d = new Date(momentMs);
    if (field === "minute") d.setMinutes(d.getMinutes() + amount);
    else if (field === "hour") d.setHours(d.getHours() + amount);
    else if (field === "day") d.setDate(d.getDate() + amount);
    else if (field === "year") d.setFullYear(d.getFullYear() + amount);
    setMomentMs(d.getTime());
  };

  const setDatePart = (value) => {
    if (!value) return;
    const [y, m, dd] = value.split("-").map(Number);
    const d = new Date(momentMs);
    d.setFullYear(y, m - 1, dd);
    setMomentMs(d.getTime());
  };

  const setTimePart = (value) => {
    if (!value) return;
    const [hh, mm] = value.split(":").map(Number);
    const d = new Date(momentMs);
    d.setHours(hh, mm, 0, 0);
    setMomentMs(d.getTime());
  };

  // Chart style + ayanamsa come from global Settings now.
  const { settings } = useSettings();
  const chartStyle = settings.chartStyle;
  const ayanamsa = settings.ayanamsa;
  const ayanamsaLabel = AYANAMSAS.find((a) => a.value === ayanamsa)?.label || ayanamsa;

  const birthDetails = useMemo(
    () =>
      selectedProfile
        ? {
            name: selectedProfile.birth_details.name,
            dob: selectedProfile.birth_details.dob,
            tob: selectedProfile.birth_details.tob,
            place: selectedProfile.birth_details.place,
            latitude: selectedProfile.birth_details.latitude,
            longitude: selectedProfile.birth_details.longitude,
            timezone: selectedProfile.birth_details.timezone,
          }
        : null,
    [selectedProfile]
  );

  const loadTransits = useCallback(async () => {
    if (!birthDetails) return;
    setLoading(true);
    setError("");
    try {
      // Anchor the snapshot to the chosen wall-clock moment in the viewer's
      // timezone (DST-aware for the chosen date). Fast movers (esp. the Moon,
      // ~0.5°/hr) follow the exact minute so the ±steppers are meaningful.
      const d = new Date(momentMs);
      const res = await astrologyService.getTransits(
        birthDetails,
        dateISO(d),
        ayanamsa,
        timeISO(d),
        tzOffset(d)
      );
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("transit.calcError"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, momentMs, ayanamsa, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    loadTransits();
  }, [selectedProfile, navigate, loadTransits]);

  if (!selectedProfile) return null;

  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;
  const planets = result?.planets || {};
  const orderedPlanets = PLANET_ORDER.filter((p) => planets[p]).map((p) => [p, planets[p]]);

  // The snapshot is anchored to a specific wall-clock moment, so show date + time.
  const transitMoment = result
    ? `${formatDate(result.transit_date, locale)}${
        result.transit_time ? `, ${result.transit_time}` : ""
      }`
    : "";

  // ±1 steppers, fastest-moving unit first so the row reads minute → year.
  const stepUnits = [
    { field: "minute", label: t("transit.unitMinute") },
    { field: "hour", label: t("transit.unitHour") },
    { field: "day", label: t("transit.unitDay") },
    { field: "year", label: t("transit.unitYear") },
  ];

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Orbit size={24} />}
        title={t("transit.title")}
        subtitle={t("transit.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        {/* Controls */}
        <div className="page-controls">
          <div className="controls-group">
            <label className="control-label">
              <Calendar size={18} style={{ color: "var(--saffron)" }} />
              {t("transit.transitDate")}
            </label>
            <input
              type="date"
              className="control-input"
              value={transitDate}
              onChange={(e) => setDatePart(e.target.value)}
            />
            <input
              type="time"
              className="control-input"
              value={transitTime}
              onChange={(e) => setTimePart(e.target.value)}
            />
            <button
              className="control-btn"
              onClick={() => setMomentMs(Date.now())}
              title={t("transit.nowHint")}
            >
              <RotateCcw size={14} /> {t("transit.now")}
            </button>
          </div>

          {/* ± steppers: nudge the moment by a minute / hour / day / year */}
          <div className="controls-group">
            {stepUnits.map(({ field, label }) => (
              <div key={field} className="stepper">
                <button
                  type="button"
                  className="stepper__btn"
                  onClick={() => shift(field, -1)}
                  aria-label={`-1 ${label}`}
                >
                  −
                </button>
                <span className="stepper__label">{label}</span>
                <button
                  type="button"
                  className="stepper__btn"
                  onClick={() => shift(field, 1)}
                  aria-label={`+1 ${label}`}
                >
                  +
                </button>
              </div>
            ))}
          </div>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("transit.loading")} />
          </Card>
        ) : result ? (
          <div className="fade-in">
            {/* Natal reference */}
            <div className="info-pills">
              <span className="info-pill">{t("transit.asOf", { moment: transitMoment })}</span>
              <span className="info-pill">
                {t("transit.natalLagna")}:{" "}
                <strong className="text-saffron">{result.natal?.lagna?.sign_name}</strong>
              </span>
              <span className="info-pill">
                {t("transit.natalMoon")}:{" "}
                <strong className="text-indigo">{result.natal?.moon?.sign_name}</strong>
              </span>
              <span className="info-pill">
                {t("transit.ayanamsa")}: <strong className="text-indigo">{ayanamsaLabel}</strong>
              </span>
            </div>

            <div className="chart-grid">
              {/* Transit chart over natal lagna */}
              <Kundali
                planets={planets}
                lagna={result.lagna}
                title={t("transit.gochara")}
                subtitle={t("transit.transitsOn", {
                  date: formatDate(result.transit_date, locale),
                })}
                exportable
              />

              {/* Transit table */}
              <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush">
                <h3 className="ui-card-header ui-card-header--sm">
                  <Orbit size={18} />
                  {t("transit.transitingGrahas")}
                </h3>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("common.planet")}</th>
                        <th>{t("common.sign")}</th>
                        <th>{t("common.nakshatra")}</th>
                        <th className="text-center">{t("transit.fromLagna")}</th>
                        <th className="text-center">{t("transit.fromMoon")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orderedPlanets.map(([name, p]) => (
                        <tr key={name}>
                          <td className="fw-700 text-indigo">
                            {PLANET_ABBR[name] || name}{" "}
                            <span style={{ fontWeight: 400 }} className="text-secondary">
                              {name}
                            </span>
                            {p.retrograde && (
                              <span className="retro-badge" title={t("transit.retrograde")}>
                                ℞
                              </span>
                            )}
                          </td>
                          <td>
                            {p.sign_name}{" "}
                            <span className="text-muted">
                              {p.degrees != null ? `${p.degrees.toFixed(1)}°` : ""}
                            </span>
                          </td>
                          <td className="text-secondary">
                            {p.nakshatra}
                            {p.nakshatra_pada ? ` (${p.nakshatra_pada})` : ""}
                          </td>
                          <td className="text-center fw-600 text-saffron">
                            {ordinal(p.house_from_lagna)}
                          </td>
                          <td className="text-center fw-600 text-vermillion">
                            {ordinal(p.house_from_moon)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="card-note">{t("transit.houseNote")}</p>
              </div>
            </div>

            {/* Upcoming ingresses */}
            {result.upcoming && result.upcoming.length > 0 && (
              <div className="ui-card ui-card--accent ui-card--flush mt-xl">
                <h3 className="ui-card-header ui-card-header--sm" style={{ fontSize: "1.25rem" }}>
                  <TrendingUp size={20} />
                  {t("transit.upcoming")}
                </h3>
                <div className="card-grid">
                  {result.upcoming.map((u, i) => (
                    <div key={i} className="ingress-card">
                      <div className="ingress-card__planet">{u.planet}</div>
                      <div className="ingress-card__signs">
                        {u.from_sign} → <strong>{u.to_sign}</strong>
                      </div>
                      <div className="ingress-card__date">{formatDate(u.date, locale)}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Interpret these transits with the AI astrologer (transit-scoped) */}
            <TransitChat
              birthDetails={birthDetails}
              profile={selectedProfile}
              result={result}
              ayanamsa={ayanamsa}
            />
          </div>
        ) : null}
      </div>
    </div>
  );
};
