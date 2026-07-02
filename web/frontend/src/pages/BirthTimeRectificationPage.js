import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Clock4, Sparkles, AlertTriangle, ArrowRight, Check } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { errorMessage } from "../utils/format";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { DEFAULT_AYANAMSA, AYANAMSAS } from "../constants/jyotish";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

// The three BV Raman suddhi methods the backend exposes. `needsGender` gates the
// gender selector (janma suddhi is the only one that needs it).
const METHODS = [
  { key: "nakshatra", labelKey: "rectify.methodNakshatra", needsGender: false },
  { key: "lagna", labelKey: "rectify.methodLagna", needsGender: false },
  { key: "janma", labelKey: "rectify.methodJanma", needsGender: true },
];

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

export const BirthTimeRectificationPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile, updateProfile } = useProfile();

  const [method, setMethod] = useState(
    () => localStorage.getItem("rectify_method") || "nakshatra"
  );
  const [gender, setGender] = useState(null); // 0=male, 1=female (janma only)
  const [chartStyle, setChartStyle] = useState(() => localStorage.getItem("chartStyle") || "north");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);

  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");

  const ayanamsa = localStorage.getItem("ayanamsa") || DEFAULT_AYANAMSA;
  const ayanamsaLabel = AYANAMSAS.find((a) => a.value === ayanamsa)?.label || ayanamsa;

  const activeMethod = METHODS.find((m) => m.key === method) || METHODS[0];

  const setStyle = (style) => {
    setChartStyle(style);
    localStorage.setItem("chartStyle", style);
  };

  const chooseMethod = (key) => {
    setMethod(key);
    localStorage.setItem("rectify_method", key);
  };

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

  const rectify = useCallback(async () => {
    if (!birthDetails) return;
    // Janma suddhi can't run until the user picks a gender.
    if (activeMethod.needsGender && gender == null) {
      setResult(null);
      return;
    }
    setLoading(true);
    setError("");
    setResult(null);
    setApplied(false);
    setAiAnalysis("");
    setAiError("");
    setAiModel("");
    try {
      const res = await astrologyService.rectifyBirthTime(
        birthDetails,
        method,
        activeMethod.needsGender ? gender : null,
        ayanamsa
      );
      setResult(res.data);
    } catch (err) {
      setError(errorMessage(err, t("rectify.calcError")));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, method, gender, activeMethod, ayanamsa, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    rectify();
  }, [selectedProfile, navigate, rectify]);

  const handleApply = async () => {
    if (!result?.suggested || !selectedProfile) return;
    if (!window.confirm(t("rectify.applyConfirm", { time: result.suggested.tob }))) return;
    setApplying(true);
    try {
      const newDetails = {
        ...selectedProfile.birth_details,
        dob: result.suggested.dob,
        tob: result.suggested.tob,
      };
      const res = await updateProfile(
        selectedProfile._id,
        selectedProfile.profile_name,
        newDetails
      );
      if (res?.success) {
        setApplied(true);
      } else {
        setError(res?.error || t("rectify.applyError"));
      }
    } catch (err) {
      setError(errorMessage(err, t("rectify.applyError")));
    } finally {
      setApplying(false);
    }
  };

  const handleAi = async () => {
    if (!birthDetails) return;
    setAiLoading(true);
    setAiError("");
    try {
      const res = await astrologyService.explainRectificationAI(
        birthDetails,
        {
          method,
          gender: activeMethod.needsGender ? gender : undefined,
          personName: birthDetails.name,
        },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(errorMessage(err, t("rectify.aiError")));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;
  const needGender = activeMethod.needsGender && gender == null;
  const suggested = result?.suggested;
  const before = result?.before || {};
  const after = result?.after || {};

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Clock4 size={24} />}
        title={t("rectify.title")}
        subtitle={t("rectify.subtitle")}
        accent="terracotta"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        {/* Experimental disclaimer — always visible, this is the core caveat. */}
        <div className="readonly-banner" style={{ display: "flex", gap: "0.6rem", alignItems: "flex-start" }}>
          <AlertTriangle size={20} style={{ flexShrink: 0, marginTop: "0.1rem" }} />
          <span>{t("rectify.experimental")}</span>
        </div>

        {/* Controls */}
        <div className="page-controls">
          <div className="controls-group">
            <label className="control-label">
              <Clock4 size={18} style={{ color: "var(--saffron)" }} />
              {t("rectify.method")}
            </label>
            <div className="chart-toggle">
              {METHODS.map((m) => (
                <button
                  key={m.key}
                  className={`chart-toggle__btn${method === m.key ? " is-active" : ""}`}
                  onClick={() => chooseMethod(m.key)}
                >
                  {t(m.labelKey)}
                </button>
              ))}
            </div>
          </div>

          {/* Gender picker — only for janma suddhi */}
          {activeMethod.needsGender && (
            <div className="controls-group">
              <label className="control-label">{t("rectify.gender")}</label>
              <div className="chart-toggle">
                <button
                  className={`chart-toggle__btn${gender === 0 ? " is-active" : ""}`}
                  onClick={() => setGender(0)}
                >
                  {t("rectify.male")}
                </button>
                <button
                  className={`chart-toggle__btn${gender === 1 ? " is-active" : ""}`}
                  onClick={() => setGender(1)}
                >
                  {t("rectify.female")}
                </button>
              </div>
            </div>
          )}

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

        <p className="card-intro">{t(`rectify.methodDesc.${method}`)}</p>

        <ErrorBanner message={error} />

        {needGender ? (
          <Card>
            <p className="card-note">{t("rectify.genderPrompt")}</p>
          </Card>
        ) : loading ? (
          <Card>
            <LoadingState message={t("rectify.loading")} />
          </Card>
        ) : result ? (
          <div className="fade-in">
            {/* Outcome summary */}
            <div className="info-pills">
              <span className="info-pill">
                {t("rectify.entered")}:{" "}
                <strong className="text-indigo">{result.entered?.tob}</strong>
              </span>
              {suggested ? (
                <>
                  <span className="info-pill">
                    {t("rectify.suggested")}:{" "}
                    <strong className="text-saffron">{suggested.tob}</strong>
                    {suggested.dob !== result.entered?.dob ? ` (${suggested.dob})` : ""}
                  </span>
                  <span className="info-pill">
                    {t("rectify.delta")}:{" "}
                    <strong className="text-vermillion">
                      {result.delta_minutes > 0 ? "+" : ""}
                      {result.delta_minutes} {t("rectify.minutes")}
                    </strong>
                  </span>
                </>
              ) : (
                <span className="info-pill">
                  <strong className="text-saffron">
                    {result.already_consistent
                      ? t("rectify.alreadyConsistent")
                      : t("rectify.notConverged")}
                  </strong>
                </span>
              )}
              <span className="info-pill">
                {t("transit.ayanamsa")}: <strong className="text-indigo">{ayanamsaLabel}</strong>
              </span>
            </div>

            <p className="card-note">{result.note}</p>

            {/* Before / after fast-movers */}
            {suggested && (
              <div className="ui-card ui-card--accent ui-card--flush mt-xl">
                <h3 className="ui-card-header ui-card-header--sm">{t("rectify.whatMoved")}</h3>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th />
                        <th>{t("rectify.entered")}</th>
                        <th />
                        <th>{t("rectify.suggested")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td className="fw-700 text-indigo">{t("rectify.moonStar")}</td>
                        <td>
                          {before.moon?.nakshatra} · {t("rectify.pada")} {before.moon?.pada}
                        </td>
                        <td className="text-center">
                          <ArrowRight size={16} style={{ color: "var(--saffron)" }} />
                        </td>
                        <td className="fw-600 text-saffron">
                          {after.moon?.nakshatra} · {t("rectify.pada")} {after.moon?.pada}
                        </td>
                      </tr>
                      <tr>
                        <td className="fw-700 text-indigo">{t("rectify.risingSign")}</td>
                        <td>
                          {before.lagna?.sign_name}{" "}
                          <span className="text-muted">({before.lagna?.nakshatra})</span>
                        </td>
                        <td className="text-center">
                          <ArrowRight size={16} style={{ color: "var(--saffron)" }} />
                        </td>
                        <td className="fw-600 text-saffron">
                          {after.lagna?.sign_name}{" "}
                          <span className="text-muted">({after.lagna?.nakshatra})</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Apply to profile */}
                <div className="mt-xl">
                  {applied ? (
                    <div className="info-pill" style={{ color: "var(--saffron)" }}>
                      <Check size={16} /> {t("rectify.applied")}
                    </div>
                  ) : (
                    <button
                      className="ui-btn ui-btn--primary"
                      onClick={handleApply}
                      disabled={applying}
                    >
                      {applying ? t("rectify.applying") : t("rectify.apply")}
                    </button>
                  )}
                  <p className="card-note">{t("rectify.applyNote")}</p>
                </div>
              </div>
            )}

            {/* Before / after charts */}
            {result.before_chart?.status === "success" && (
              <div className="chart-grid mt-xl">
                <Kundali
                  planets={result.before_chart.planets}
                  lagna={result.before_chart.lagna}
                  title={t("rectify.chartEntered")}
                  subtitle={result.entered?.tob}
                />
                {suggested && result.after_chart?.status === "success" && (
                  <Kundali
                    planets={result.after_chart.planets}
                    lagna={result.after_chart.lagna}
                    title={t("rectify.chartSuggested")}
                    subtitle={suggested.tob}
                  />
                )}
              </div>
            )}

            {/* AI explanation */}
            {suggested && (
              <div className="mt-xl">
                <Card title={t("rectify.aiTitle")} icon={<Sparkles size={24} />} accent="gold">
                  <ErrorBanner message={aiError} />
                  {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("rectify.aiHint")}</p>}
                  {aiLoading && <LoadingState message={t("rectify.aiLoading")} />}
                  {aiAnalysis && !aiLoading && (
                    <div className="sbc-ai-markdown ai-panel__reading">
                      <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                      {aiModel && (
                        <div className="ai-panel__meta">
                          {t("rectify.aiModel", { model: aiModel })}
                        </div>
                      )}
                    </div>
                  )}
                  {!aiLoading && (
                    <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                      <Sparkles size={18} />
                      {aiAnalysis ? t("rectify.aiRegenerate") : t("rectify.aiGenerate")}
                    </button>
                  )}
                  <p className="card-note">{t("rectify.disclaimer")}</p>
                </Card>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
};
