import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CalendarClock, Sparkles, Star, Compass, Clock } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { intlLocale } from "../utils/format";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { PLANET_ABBR, DEFAULT_AYANAMSA, AYANAMSAS } from "../constants/jyotish";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

const PLANET_ORDER = [
  "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu",
];

const ordinal = (n) => {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
};

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

// Read the model the user already picked in "Ask Astrologer".
const readModelConfig = () => {
  const providerType = localStorage.getItem("ai_provider_type") || "ollama";
  return {
    providerType,
    model: localStorage.getItem("ai_model") || "",
    baseUrl: providerType === "ollama" ? localStorage.getItem("ai_base_url") || undefined : undefined,
    legacyProvider: providerType === "ollama" ? "qwen" : providerType,
  };
};

export const VarshaphalPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const birthYear = selectedProfile?.birth_details?.dob
    ? parseInt(selectedProfile.birth_details.dob.split("-")[0], 10)
    : 1900;
  const [year, setYear] = useState(() => new Date().getFullYear());

  const [chartStyle, setChartStyle] = useState(() => localStorage.getItem("chartStyle") || "north");
  const ayanamsa = localStorage.getItem("ayanamsa") || DEFAULT_AYANAMSA;
  const ayanamsaLabel = AYANAMSAS.find((a) => a.value === ayanamsa)?.label || ayanamsa;

  const setStyle = (style) => {
    setChartStyle(style);
    localStorage.setItem("chartStyle", style);
  };

  const stepYear = (delta) => setYear((y) => Math.max(birthYear, y + delta));

  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");

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

  const loadVarshaphal = useCallback(async () => {
    if (!birthDetails) return;
    setLoading(true);
    setError("");
    // A new year invalidates the previous AI reading.
    setAiAnalysis("");
    setAiError("");
    setAiModel("");
    try {
      const res = await astrologyService.getVarshaphal(birthDetails, year, ayanamsa);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("varshaphal.calcError"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, year, ayanamsa, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    loadVarshaphal();
  }, [selectedProfile, navigate, loadVarshaphal]);

  const handleAi = async () => {
    if (!birthDetails) return;
    setAiLoading(true);
    setAiError("");
    try {
      const res = await astrologyService.analyzeVarshaphalAI(
        birthDetails,
        year,
        { personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("varshaphal.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;
  const planets = result?.planets || {};
  const orderedPlanets = PLANET_ORDER.filter((p) => planets[p]).map((p) => [p, planets[p]]);
  const sahams = result?.sahams || [];
  const tajakaYogas = result?.tajaka_yogas || [];
  const periods = result?.annual_dasha?.periods || [];

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<CalendarClock size={24} />}
        title={t("varshaphal.title")}
        subtitle={t("varshaphal.subtitle")}
        accent="gold"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        {/* Controls */}
        <div className="page-controls">
          <div className="controls-group">
            <label className="control-label">
              <CalendarClock size={18} style={{ color: "var(--saffron)" }} />
              {t("varshaphal.year")}
            </label>
            <div className="stepper">
              <button
                type="button"
                className="stepper__btn"
                onClick={() => stepYear(-1)}
                aria-label="-1 year"
                disabled={year <= birthYear}
              >
                −
              </button>
              <input
                type="number"
                className="control-input"
                style={{ width: "6rem", textAlign: "center" }}
                value={year}
                min={birthYear}
                onChange={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (!Number.isNaN(v)) setYear(Math.max(birthYear, v));
                }}
              />
              <button
                type="button"
                className="stepper__btn"
                onClick={() => stepYear(1)}
                aria-label="+1 year"
              >
                +
              </button>
            </div>
          </div>

          {/* Chart style toggle */}
          <div className="chart-toggle">
            {["north", "south"].map((style) => (
              <button
                key={style}
                className={`chart-toggle__btn${chartStyle === style ? " is-active" : ""}`}
                onClick={() => setStyle(style)}
              >
                {style === "south" ? t("birthChart.southIndian") : t("birthChart.northIndian")}
              </button>
            ))}
          </div>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("varshaphal.loading")} />
          </Card>
        ) : result ? (
          <div className="fade-in">
            {/* Year summary */}
            <div className="info-pills">
              <span className="info-pill">
                {t("varshaphal.forYear")}:{" "}
                <strong className="text-saffron">{result.year}</strong>
              </span>
              <span className="info-pill">
                {t("varshaphal.solarYearBegins")}:{" "}
                <strong>{formatDate(result.year_entry?.date, locale)}</strong>
                {result.year_entry?.time ? `, ${result.year_entry.time}` : ""}
              </span>
              <span className="info-pill">
                {t("varshaphal.annualLagna")}:{" "}
                <strong className="text-indigo">{result.lagna?.sign_name}</strong>
              </span>
              <span className="info-pill">
                {t("varshaphal.muntha")}:{" "}
                <strong className="text-saffron">{result.muntha?.sign_name}</strong>
                {result.muntha?.house ? ` (${ordinal(result.muntha.house)} ${t("varshaphal.houseWord")})` : ""}
              </span>
              <span className="info-pill">
                {t("varshaphal.yearLord")}:{" "}
                <strong className="text-vermillion">
                  {result.year_lord?.planet || "—"}
                </strong>
              </span>
              <span className="info-pill">
                {t("transit.ayanamsa")}: <strong className="text-indigo">{ayanamsaLabel}</strong>
              </span>
            </div>

            <div className="chart-grid">
              {/* Annual (Tajaka) chart */}
              <Kundali
                planets={planets}
                lagna={result.lagna}
                title={t("varshaphal.annualChart", { year: result.year })}
                subtitle={t("varshaphal.tajaka")}
                exportable
              />

              {/* Annual placements table */}
              <div className="ui-card ui-card--accent-gold ui-card--pad-lg ui-card--flush">
                <h3 className="ui-card-header ui-card-header--sm">
                  <Compass size={18} />
                  {t("varshaphal.placements")}
                </h3>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("common.planet")}</th>
                        <th>{t("common.sign")}</th>
                        <th className="text-center">{t("varshaphal.houseWord")}</th>
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
                          </td>
                          <td>
                            {p.sign_name}{" "}
                            <span className="text-muted">
                              {p.degrees != null ? `${p.degrees.toFixed(1)}°` : ""}
                            </span>
                          </td>
                          <td className="text-center fw-600 text-saffron">
                            {ordinal(p.house)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="card-note">{t("varshaphal.houseNote")}</p>
              </div>
            </div>

            {/* Sahams */}
            {sahams.length > 0 && (
              <div className="ui-card ui-card--accent ui-card--flush mt-xl">
                <h3 className="ui-card-header ui-card-header--sm" style={{ fontSize: "1.25rem" }}>
                  <Star size={20} />
                  {t("varshaphal.sahams")}
                </h3>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("varshaphal.saham")}</th>
                        <th>{t("varshaphal.significance")}</th>
                        <th>{t("common.sign")}</th>
                        <th className="text-center">{t("varshaphal.houseWord")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sahams.map((s) => (
                        <tr key={s.name}>
                          <td className="fw-700 text-saffron">{s.name}</td>
                          <td className="text-secondary">{s.significance}</td>
                          <td>
                            {s.sign_name}{" "}
                            <span className="text-muted">
                              {s.degrees != null ? `${s.degrees.toFixed(1)}°` : ""}
                            </span>
                          </td>
                          <td className="text-center fw-600 text-indigo">{ordinal(s.house)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Tajaka yogas */}
            <div className="ui-card ui-card--accent-gold ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm" style={{ fontSize: "1.25rem" }}>
                <Sparkles size={20} />
                {t("varshaphal.tajakaYogas")}
              </h3>
              {tajakaYogas.length > 0 ? (
                <div className="card-grid">
                  {tajakaYogas.map((y, i) => (
                    <div key={i} className="ui-card ui-card--pad-lg">
                      <div className="fw-700 text-saffron">
                        {y.name}
                        {y.pair && (
                          <span className="text-secondary fw-400"> · {y.pair.join(" – ")}</span>
                        )}
                      </div>
                      <div className="text-secondary" style={{ fontSize: "0.85rem", marginTop: "0.35rem" }}>
                        {y.description}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="card-note">{t("varshaphal.noYogas")}</p>
              )}
            </div>

            {/* Annual dasha */}
            {periods.length > 0 && (
              <div className="ui-card ui-card--accent-indigo ui-card--flush mt-xl">
                <h3 className="ui-card-header ui-card-header--sm" style={{ fontSize: "1.25rem" }}>
                  <Clock size={20} />
                  {t("varshaphal.annualDasha")}
                </h3>
                <p className="card-intro">{result.annual_dasha?.system}</p>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("varshaphal.period")}</th>
                        <th>{t("varshaphal.from")}</th>
                        <th>{t("varshaphal.to")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {periods.map((p, i) => (
                        <tr key={i} className={p.current ? "is-current-row" : ""}>
                          <td className="fw-700 text-indigo">
                            {p.lord_name}
                            {p.current && (
                              <span className="info-pill" style={{ marginLeft: "0.5rem" }}>
                                {t("varshaphal.current")}
                              </span>
                            )}
                          </td>
                          <td className="text-secondary">{formatDate(p.start, locale)}</td>
                          <td className="text-secondary">{formatDate(p.end, locale)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* AI year-ahead reading */}
            <div className="mt-xl">
              <Card title={t("varshaphal.aiTitle")} icon={<Sparkles size={24} />} accent="gold">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("varshaphal.aiHint")}</p>}
                {aiLoading && <LoadingState message={t("varshaphal.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">
                        {t("varshaphal.aiModel", { model: aiModel })}
                      </div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("varshaphal.aiRegenerate") : t("varshaphal.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("varshaphal.disclaimer")}</p>
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};
