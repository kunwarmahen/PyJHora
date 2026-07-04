import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CalendarRange, ChevronLeft, ChevronRight, TrendingUp } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { useSettings } from "../contexts/SettingsContext";
import { astrologyService } from "../services/api";
import { intlLocale } from "../utils/format";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { PLANET_ABBR, RASI_ABBR, AYANAMSAS } from "../constants/jyotish";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

const pad2 = (n) => String(n).padStart(2, "0");
const dateISO = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;

const WINDOWS = [30, 60, 92];

const fmtDay = (iso, locale) => {
  try {
    return new Date(iso + "T00:00:00").toLocaleDateString(locale, {
      month: "short",
      day: "numeric",
    });
  } catch (e) {
    return iso;
  }
};
const fmtWeekday = (iso, locale) => {
  try {
    return new Date(iso + "T00:00:00").toLocaleDateString(locale, { weekday: "short" });
  } catch (e) {
    return "";
  }
};

// Sign name → compact abbreviation (Ar, Ta, …) for the dense ephemeris grid.
const SIGN_ABBR = {
  Aries: "Ar", Taurus: "Ta", Gemini: "Ge", Cancer: "Cn", Leo: "Le", Virgo: "Vi",
  Libra: "Li", Scorpio: "Sc", Sagittarius: "Sg", Capricorn: "Cp", Aquarius: "Aq", Pisces: "Pi",
};

export const EphemerisPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;
  const ayanamsaLabel = AYANAMSAS.find((a) => a.value === ayanamsa)?.label || ayanamsa;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [days, setDays] = useState(30);
  // Window start; defaults to the 1st of the current month.
  const [startMs, setStartMs] = useState(() => {
    const n = new Date();
    return new Date(n.getFullYear(), n.getMonth(), 1).getTime();
  });
  const start = useMemo(() => new Date(startMs), [startMs]);

  const shiftWindow = (dir) => {
    const d = new Date(startMs);
    d.setDate(d.getDate() + dir * days);
    setStartMs(d.getTime());
  };
  const jumpToday = () => {
    const n = new Date();
    setStartMs(new Date(n.getFullYear(), n.getMonth(), 1).getTime());
  };

  const loadEphemeris = useCallback(async () => {
    if (!selectedProfile) return;
    setLoading(true);
    setError("");
    try {
      const b = selectedProfile.birth_details;
      const res = await astrologyService.getEphemeris({
        startDate: dateISO(new Date(startMs)),
        days,
        place: b.place,
        latitude: b.latitude,
        longitude: b.longitude,
        timezone: b.timezone,
        ayanamsa,
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("ephemeris.calcError"));
    } finally {
      setLoading(false);
    }
  }, [selectedProfile, startMs, days, ayanamsa, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    loadEphemeris();
  }, [selectedProfile, navigate, loadEphemeris]);

  if (!selectedProfile) return null;

  const order = result?.planet_order || [];
  const rows = result?.rows || [];
  const ingresses = result?.ingresses || [];
  const todayISO = dateISO(new Date());

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<CalendarRange size={24} />}
        title={t("ephemeris.title")}
        subtitle={t("ephemeris.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        {/* Controls: window nav + span */}
        <div className="page-controls">
          <div className="controls-group">
            <button className="control-btn" onClick={() => shiftWindow(-1)}>
              <ChevronLeft size={14} /> {t("ephemeris.prev")}
            </button>
            <span className="control-label" style={{ minWidth: 0 }}>
              {fmtDay(result?.start_date || dateISO(start), locale)}
              {result?.end_date ? ` – ${fmtDay(result.end_date, locale)}` : ""}
            </span>
            <button className="control-btn" onClick={() => shiftWindow(1)}>
              {t("ephemeris.next")} <ChevronRight size={14} />
            </button>
            <button className="control-btn" onClick={jumpToday}>
              {t("ephemeris.today")}
            </button>
          </div>
          <div className="controls-group">
            <label className="control-label">{t("ephemeris.span")}</label>
            <select
              className="control-input"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
            >
              {WINDOWS.map((w) => (
                <option key={w} value={w}>
                  {t("ephemeris.dayCount", { count: w })}
                </option>
              ))}
            </select>
          </div>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("ephemeris.loading")} />
          </Card>
        ) : result ? (
          <div className="fade-in">
            <div className="info-pills">
              <span className="info-pill">
                {t("ephemeris.ayanamsa")}:{" "}
                <strong className="text-indigo">{ayanamsaLabel}</strong>
              </span>
              <span className="info-pill">{t("ephemeris.noonNote")}</span>
            </div>

            {/* Ingress calendar */}
            <div className="ui-card ui-card--accent ui-card--flush mb-xl">
              <h3 className="ui-card-header ui-card-header--sm" style={{ fontSize: "1.25rem" }}>
                <TrendingUp size={20} />
                {t("ephemeris.ingresses")}
              </h3>
              {ingresses.length ? (
                <div className="card-grid">
                  {ingresses.map((u, i) => (
                    <div key={i} className="ingress-card">
                      <div className="ingress-card__planet">
                        {PLANET_ABBR[u.planet] || u.planet} {u.planet}
                        {u.retrograde && (
                          <span className="retro-badge" title={t("ephemeris.retrograde")}>
                            ℞
                          </span>
                        )}
                      </div>
                      <div className="ingress-card__signs">
                        {u.from_sign} → <strong>{u.to_sign}</strong>
                      </div>
                      <div className="ingress-card__date">{fmtDay(u.date, locale)}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="card-note">{t("ephemeris.noIngress")}</p>
              )}
            </div>

            {/* Ephemeris grid */}
            <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush">
              <h3 className="ui-card-header ui-card-header--sm">
                <CalendarRange size={18} />
                {t("ephemeris.grid")}
              </h3>
              <div className="table-scroll">
                <table className="data-table ephemeris-table">
                  <thead>
                    <tr>
                      <th>{t("ephemeris.date")}</th>
                      {order.map((p) => (
                        <th key={p} className="text-center" title={p}>
                          {PLANET_ABBR[p] || p}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.date} className={row.date === todayISO ? "is-today" : ""}>
                        <td className="fw-600 text-secondary" style={{ whiteSpace: "nowrap" }}>
                          {fmtDay(row.date, locale)}{" "}
                          <span className="text-muted">{fmtWeekday(row.date, locale)}</span>
                        </td>
                        {order.map((p) => {
                          const cell = row.planets[p];
                          if (!cell) return <td key={p} className="text-center text-muted">—</td>;
                          return (
                            <td key={p} className="text-center" style={{ whiteSpace: "nowrap" }}>
                              <span className="fw-600">{Math.floor(cell.degrees)}°</span>{" "}
                              <span className="text-saffron">
                                {SIGN_ABBR[cell.sign_name] || RASI_ABBR[cell.sign - 1] || cell.sign_name}
                              </span>
                              {cell.retrograde && <span className="retro-badge">℞</span>}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="card-note">{t("ephemeris.gridNote")}</p>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};
