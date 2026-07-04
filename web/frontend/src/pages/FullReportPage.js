import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { FileText, Printer } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { useSettings } from "../contexts/SettingsContext";
import { astrologyService } from "../services/api";
import { intlLocale, formatDate, orDash } from "../utils/format";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { PLANET_ABBR, AYANAMSAS } from "../constants/jyotish";
import { SITE_TITLE } from "../config/branding";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import "../styles/Report.css";

const PLANET_ORDER = [
  "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu",
];
const ordinal = (n) => {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
};

export const FullReportPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const chartStyle = settings.chartStyle;
  const ayanamsa = settings.ayanamsa;
  const ayanamsaLabel = AYANAMSAS.find((a) => a.value === ayanamsa)?.label || ayanamsa;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);

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

  const load = useCallback(async () => {
    if (!birthDetails) return;
    setLoading(true);
    setError("");
    // Each source is independent — one failing (e.g. an env-specific dasha path)
    // must not blank the whole report, so gather with allSettled and degrade.
    const val = (r) => (r.status === "fulfilled" ? r.value.data : null);
    try {
      const [chart, yogas, doshas, transits, dhasa] = await Promise.allSettled([
        astrologyService.calculateBirthChart(birthDetails, ayanamsa),
        astrologyService.getYogas(birthDetails, ayanamsa),
        astrologyService.getDoshas(birthDetails, ayanamsa),
        astrologyService.getTransits(birthDetails, null, ayanamsa),
        astrologyService.getDhasa(birthDetails, "vimsottari"),
      ]);
      const chartData = val(chart);
      if (!chartData) {
        setError(t("report.calcError"));
        return;
      }
      setData({
        chart: chartData,
        yogas: val(yogas),
        doshas: val(doshas),
        transits: val(transits),
        dhasa: val(dhasa),
      });
    } catch (err) {
      setError(err.response?.data?.detail || t("report.calcError"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, ayanamsa, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    load();
  }, [selectedProfile, navigate, load]);

  if (!selectedProfile) return null;

  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;
  const chart = data?.chart;
  const bd = selectedProfile.birth_details;

  const d1Planets = chart?.d1_chart || {};
  const orderedPlanets = PLANET_ORDER.filter((p) => d1Planets[p]).map((p) => [p, d1Planets[p]]);

  const yogasPresent = (data?.yogas?.yogas || []).slice(0, 30);
  const doshasPresent = (data?.doshas?.doshas || []).filter((d) => d.present);
  const dhasaList = (data?.dhasa?.dashas || data?.dhasa?.periods || []).slice(0, 9);

  return (
    <div className="dashboard-container report-page">
      <PageHeader
        icon={<FileText size={24} />}
        title={t("report.title")}
        subtitle={t("report.subtitle")}
        accent="gold"
      />

      <div className="dashboard-content">
        {/* Print toolbar — hidden on paper */}
        <div className="report-toolbar no-print">
          <button
            className="control-btn report-print-btn"
            onClick={() => window.print()}
            disabled={loading || !chart}
          >
            <Printer size={16} /> {t("report.print")}
          </button>
          <span className="text-muted">{t("report.printHint")}</span>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("report.loading")} />
          </Card>
        ) : chart ? (
          <div className="report-sheet fade-in">
            {/* Masthead */}
            <header className="report-masthead">
              <h1 className="report-name">{orDash(bd.name)}</h1>
              <p className="report-tagline">{t("report.tagline")}</p>
              <div className="report-meta">
                <span>
                  <strong>{t("report.born")}:</strong> {formatDate(bd.dob, locale)}
                  {bd.tob ? `, ${bd.tob}` : ""}
                </span>
                <span>
                  <strong>{t("report.place")}:</strong> {orDash(bd.place)}
                </span>
                <span>
                  <strong>{t("report.ayanamsa")}:</strong> {ayanamsaLabel}
                </span>
                <span>
                  <strong>{t("report.generated")}:</strong> {formatDate(new Date().toISOString(), locale)}
                </span>
              </div>
            </header>

            {/* Vitals */}
            <section className="report-section">
              <h2 className="report-h2">{t("report.vitals")}</h2>
              <div className="report-vitals">
                <div className="report-vital">
                  <span className="report-vital__label">{t("report.lagna")}</span>
                  <span className="report-vital__value">
                    {chart.lagna?.sign_name}
                    <em>{chart.lagna?.nakshatra ? ` · ${chart.lagna.nakshatra}` : ""}</em>
                  </span>
                </div>
                <div className="report-vital">
                  <span className="report-vital__label">{t("report.moonSign")}</span>
                  <span className="report-vital__value">{d1Planets.Moon?.sign_name || "—"}</span>
                </div>
                <div className="report-vital">
                  <span className="report-vital__label">{t("report.nakshatra")}</span>
                  <span className="report-vital__value">
                    {d1Planets.Moon?.nakshatra || "—"}
                    {d1Planets.Moon?.nakshatra_pada ? ` (${d1Planets.Moon.nakshatra_pada})` : ""}
                  </span>
                </div>
                <div className="report-vital">
                  <span className="report-vital__label">{t("report.sunSign")}</span>
                  <span className="report-vital__value">{d1Planets.Sun?.sign_name || "—"}</span>
                </div>
              </div>
            </section>

            {/* Charts */}
            <section className="report-section report-charts">
              <h2 className="report-h2">{t("report.charts")}</h2>
              <div className="report-chart-grid">
                <Kundali
                  planets={chart.planets}
                  lagna={chart.lagna}
                  title={t("report.rasi")}
                  subtitle="D1"
                />
                <Kundali
                  planets={chart.d9_chart}
                  lagna={chart.d9_lagna}
                  title={t("report.navamsa")}
                  subtitle="D9"
                />
              </div>
            </section>

            {/* Planetary positions */}
            <section className="report-section">
              <h2 className="report-h2">{t("report.positions")}</h2>
              <table className="data-table report-table">
                <thead>
                  <tr>
                    <th>{t("report.graha")}</th>
                    <th>{t("report.sign")}</th>
                    <th>{t("report.degree")}</th>
                    <th>{t("report.nakshatraPada")}</th>
                  </tr>
                </thead>
                <tbody>
                  {orderedPlanets.map(([name, p]) => (
                    <tr key={name}>
                      <td className="fw-700">
                        {PLANET_ABBR[name] || name} <span className="text-secondary">{name}</span>
                      </td>
                      <td>{p.sign_name}</td>
                      <td className="text-secondary">
                        {p.degrees != null ? `${p.degrees.toFixed(2)}°` : "—"}
                      </td>
                      <td className="text-secondary">
                        {p.nakshatra}
                        {p.nakshatra_pada ? ` (${p.nakshatra_pada})` : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            {/* Dasha timeline (guarded — may be unavailable) */}
            {dhasaList.length > 0 && (
              <section className="report-section">
                <h2 className="report-h2">{t("report.dasha")}</h2>
                <table className="data-table report-table">
                  <thead>
                    <tr>
                      <th>{t("report.mahadasha")}</th>
                      <th>{t("report.start")}</th>
                      <th>{t("report.end")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dhasaList.map((d, i) => (
                      <tr key={i}>
                        <td className="fw-600">{d.lord || d.planet || d.name || d.dhasa_lord}</td>
                        <td className="text-secondary">{formatDate(d.start || d.start_date, locale)}</td>
                        <td className="text-secondary">{formatDate(d.end || d.end_date, locale)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            )}

            {/* Yogas */}
            {yogasPresent.length > 0 && (
              <section className="report-section">
                <h2 className="report-h2">
                  {t("report.yogas")} <span className="report-count">({yogasPresent.length})</span>
                </h2>
                <ul className="report-list">
                  {yogasPresent.map((y) => (
                    <li key={y.key}>
                      <strong>{y.name}</strong>
                      {y.benefits ? <span className="report-list__note"> — {y.benefits}</span> : null}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Doshas */}
            {data?.doshas?.doshas && (
              <section className="report-section">
                <h2 className="report-h2">{t("report.doshas")}</h2>
                {doshasPresent.length > 0 ? (
                  <ul className="report-list">
                    {doshasPresent.map((d) => (
                      <li key={d.key}>
                        <strong>{d.name}</strong>
                        {d.description ? <span className="report-list__note"> — {d.description}</span> : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-secondary">{t("report.noDoshas")}</p>
                )}
              </section>
            )}

            {/* Current transits */}
            {data?.transits?.planets && (
              <section className="report-section">
                <h2 className="report-h2">
                  {t("report.transits")}{" "}
                  <span className="report-count">
                    {data.transits.transit_date ? `· ${formatDate(data.transits.transit_date, locale)}` : ""}
                  </span>
                </h2>
                <table className="data-table report-table">
                  <thead>
                    <tr>
                      <th>{t("report.graha")}</th>
                      <th>{t("report.sign")}</th>
                      <th className="text-center">{t("report.fromMoon")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {PLANET_ORDER.filter((p) => data.transits.planets[p]).map((name) => {
                      const p = data.transits.planets[name];
                      return (
                        <tr key={name}>
                          <td className="fw-600">
                            {PLANET_ABBR[name] || name} <span className="text-secondary">{name}</span>
                            {p.retrograde ? " ℞" : ""}
                          </td>
                          <td>{p.sign_name}</td>
                          <td className="text-center">{ordinal(p.house_from_moon)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </section>
            )}

            <footer className="report-footer">
              <span>{t("report.footer", { brand: SITE_TITLE })}</span>
            </footer>
          </div>
        ) : null}
      </div>
    </div>
  );
};
