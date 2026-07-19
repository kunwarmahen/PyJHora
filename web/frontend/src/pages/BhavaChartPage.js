import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Grid2x2, Home } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { useSettings } from "../contexts/SettingsContext";
import { astrologyService } from "../services/api";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { AYANAMSAS } from "../constants/jyotish";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import { useLocalizeName } from "../i18n/localizeName";

// House systems the UI offers (mirrors backend AstrologyCompute.BHAVA_METHODS).
const METHODS = [
  { value: "SRIPATI", key: "sripati" },
  { value: "PLACIDUS", key: "placidus" },
  { value: "KP", key: "kp" },
  { value: "EQUAL", key: "equal" },
];

const ordinal = (n) => {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
};

// Absolute ecliptic longitude (0–360) → "12°34' Sign" within its own sign.
const fmtCusp = (absLong, signName) => {
  const within = ((absLong % 30) + 30) % 30;
  const deg = Math.floor(within);
  const min = Math.round((within - deg) * 60);
  return `${deg}°${String(min).padStart(2, "0")}' ${signName}`;
};

export const BhavaChartPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const ln = useLocalizeName();
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const chartStyle = settings.chartStyle;
  const ayanamsa = settings.ayanamsa;
  const ayanamsaLabel = AYANAMSAS.find((a) => a.value === ayanamsa)?.label || ayanamsa;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [method, setMethod] = useState("SRIPATI");

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

  const loadChart = useCallback(async () => {
    if (!birthDetails) return;
    setLoading(true);
    setError("");
    try {
      const res = await astrologyService.getBhavaChart(birthDetails, method, ayanamsa);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("bhava.calcError"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, method, ayanamsa, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    loadChart();
  }, [selectedProfile, navigate, loadChart]);

  if (!selectedProfile) return null;

  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;
  const houses = result?.houses || [];

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Home size={24} />}
        title={t("bhava.title")}
        subtitle={t("bhava.subtitle")}
        accent="terracotta"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        {/* Controls: house-system selector */}
        <div className="page-controls">
          <div className="controls-group">
            <label className="control-label">
              <Grid2x2 size={18} style={{ color: "var(--saffron)" }} />
              {t("bhava.houseSystem")}
            </label>
            <select
              className="control-input"
              value={method}
              onChange={(e) => setMethod(e.target.value)}
            >
              {METHODS.map((m) => (
                <option key={m.value} value={m.value}>
                  {t(`bhava.methods.${m.key}`)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("bhava.loading")} />
          </Card>
        ) : result ? (
          <div className="fade-in">
            <div className="info-pills">
              <span className="info-pill">
                {t("bhava.system")}: <strong className="text-saffron">{result.method_label}</strong>
              </span>
              <span className="info-pill">
                {t("bhava.lagna")}:{" "}
                <strong className="text-indigo">{ln(result.lagna?.sign_name, "rasi")}</strong>
              </span>
              <span className="info-pill">
                {t("bhava.ayanamsa")}: <strong className="text-indigo">{ayanamsaLabel}</strong>
              </span>
            </div>

            <div className="chart-grid">
              {/* Bhava Chalit chart: grahas placed by house-cusp, not by sign */}
              <Kundali
                planets={result.planets}
                lagna={result.lagna}
                title={t("bhava.chalit")}
                subtitle={result.method_label}
                exportable
              />

              {/* House-cusp table */}
              <div className="ui-card ui-card--accent-gold ui-card--pad-lg ui-card--flush">
                <h3 className="ui-card-header ui-card-header--sm">
                  <Home size={18} />
                  {t("bhava.cuspTable")}
                </h3>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th className="text-center">{t("bhava.bhava")}</th>
                        <th>{t("bhava.sign")}</th>
                        <th>{t("bhava.cusp")}</th>
                        <th>{t("bhava.grahas")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {houses.map((h) => (
                        <tr key={h.bhava}>
                          <td className="text-center fw-700 text-saffron">{ordinal(h.bhava)}</td>
                          <td>{ln(h.sign_name, "rasi")}</td>
                          <td className="text-secondary">
                            {fmtCusp(h.cusp, ln(h.sign_name, "rasi"))}
                          </td>
                          <td>
                            {h.planets.length ? (
                              h.planets.map((p) => (
                                <span
                                  key={p}
                                  className="fw-600 text-indigo"
                                  style={{ marginRight: 6 }}
                                >
                                  {ln(p, "graha", { abbr: true })}
                                </span>
                              ))
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="card-note">{t("bhava.cuspNote")}</p>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};
