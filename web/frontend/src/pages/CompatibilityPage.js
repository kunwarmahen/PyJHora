import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import { Heart, User, Users, Sparkles, GitCompareArrows } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { formatDate, orDash, errorMessage } from "../utils/format";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { useSettings } from "../contexts/SettingsContext";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

// Read the model config the user already picked in "Ask Astrologer". The server
// resolves the actual API key (per-user stored key → env key), so we only need
// the provider/model selection here — no key handling on this page.
const readModelConfig = () => {
  const providerType = localStorage.getItem("ai_provider_type") || "ollama";
  return {
    providerType,
    model: localStorage.getItem("ai_model") || "",
    baseUrl: providerType === "ollama" ? localStorage.getItem("ai_base_url") || undefined : undefined,
    legacyProvider: providerType === "ollama" ? "qwen" : providerType,
  };
};

const toBirthDetails = (p) => ({
  name: p.birth_details.name,
  dob: p.birth_details.dob,
  tob: p.birth_details.tob,
  place: p.birth_details.place,
  latitude: parseFloat(p.birth_details.latitude),
  longitude: parseFloat(p.birth_details.longitude),
  timezone: parseFloat(p.birth_details.timezone),
});

export const CompatibilityPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile, profiles, loadProfiles } = useProfile();

  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;
  const chartStyle = settings.chartStyle;
  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;

  const [secondProfile, setSecondProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [chartA, setChartA] = useState(null);
  const [chartB, setChartB] = useState(null);

  // AI analysis is on-demand (uses the model picked in "Ask Astrologer").
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");

  // Redirect if no profile selected
  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }

    loadProfiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, navigate]);

  const resetResults = () => {
    setResult(null);
    setChartA(null);
    setChartB(null);
    setAiAnalysis("");
    setAiError("");
    setAiModel("");
  };

  const handleCalculate = async () => {
    if (!secondProfile) {
      setError(t("compat.errSelectSecond"));
      return;
    }

    setLoading(true);
    setError("");
    setAiAnalysis("");
    setAiError("");

    const person1Data = toBirthDetails(selectedProfile);
    const person2Data = toBirthDetails(secondProfile);

    try {
      // Score + both birth charts in parallel — the charts power the side-by-side
      // visual comparison, the score powers the Ashtakoot breakdown.
      const [compat, ra, rb] = await Promise.all([
        astrologyService.getCompatibility(person1Data, person2Data),
        astrologyService.calculateBirthChart(person1Data, ayanamsa),
        astrologyService.calculateBirthChart(person2Data, ayanamsa),
      ]);
      if (compat.data?.error) {
        setError(compat.data.error);
        return;
      }
      setResult(compat.data);
      setChartA(ra.data);
      setChartB(rb.data);
    } catch (err) {
      setError(errorMessage(err, t("compat.calcError")));
    } finally {
      setLoading(false);
    }
  };

  const handleAiAnalysis = async () => {
    if (!secondProfile) return;
    setAiLoading(true);
    setAiError("");
    try {
      const response = await astrologyService.analyzeCompatibilityAI(
        toBirthDetails(selectedProfile),
        toBirthDetails(secondProfile),
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(response.data.ai_analysis || "");
      setAiModel(response.data.model || response.data.provider || "");
    } catch (err) {
      setAiError(errorMessage(err, t("compat.aiError")));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) {
    return null;
  }

  const nameA = selectedProfile.profile_name;
  const nameB = secondProfile?.profile_name || t("compare.person2");

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Heart size={24} />}
        title={t("compat.title")}
        subtitle={t("compat.subtitle")}
        accent="saffron"
      />

      {/* Content */}
      <div className="dashboard-content">
        <ErrorBanner message={error} />

        {/* Profile Selection Card */}
        <div className="ui-card ui-card--accent fade-in">
          <h3 className="ui-card-header">
            <Users size={24} />
            {t("compat.selectProfiles")}
          </h3>

          <div className="person-grid">
            {/* Person 1 - Selected Profile */}
            <div className="compat-person compat-person--a">
              <h4 className="compat-person__head">
                <User size={20} /> {t("compare.person1")}
              </h4>
              <div className="compat-person__card">
                <p className="compat-person__name">{selectedProfile.profile_name}</p>
                <div className="detail-list">
                  <div>
                    <strong>{t("common.name")}:</strong>{" "}
                    {selectedProfile.birth_details.name || t("common.anonymous")}
                  </div>
                  <div>
                    <strong>{t("common.dateOfBirth")}:</strong>{" "}
                    {formatDate(selectedProfile.birth_details.dob)}
                  </div>
                  <div>
                    <strong>{t("common.timeOfBirth")}:</strong>{" "}
                    {orDash(selectedProfile.birth_details.tob)}
                  </div>
                  <div>
                    <strong>{t("common.place")}:</strong>{" "}
                    {orDash(selectedProfile.birth_details.place)}
                  </div>
                </div>
              </div>
            </div>

            {/* Person 2 - Select from profiles */}
            <div className="compat-person compat-person--b">
              <h4 className="compat-person__head">
                <User size={20} /> {t("compare.person2")}
              </h4>
              <label className="compat-person__select-label">{t("compat.selectToCompare")}</label>
              <select
                className="form-select"
                value={secondProfile?._id || ""}
                onChange={(e) => {
                  const profile = profiles.find((p) => p._id === e.target.value);
                  setSecondProfile(profile || null);
                  resetResults();
                }}
              >
                <option value="">{t("compat.selectPlaceholder")}</option>
                {profiles
                  .filter((p) => p._id !== selectedProfile._id)
                  .map((profile) => (
                    <option key={profile._id} value={profile._id}>
                      {profile.profile_name} ({profile.birth_details.name || t("common.anonymous")})
                    </option>
                  ))}
              </select>

              {secondProfile && (
                <div className="compat-person__card is-spaced">
                  <p className="compat-person__name">{secondProfile.profile_name}</p>
                  <div className="detail-list">
                    <div>
                      <strong>{t("common.name")}:</strong>{" "}
                      {secondProfile.birth_details.name || t("common.anonymous")}
                    </div>
                    <div>
                      <strong>{t("common.dateOfBirth")}:</strong>{" "}
                      {formatDate(secondProfile.birth_details.dob)}
                    </div>
                    <div>
                      <strong>{t("common.timeOfBirth")}:</strong>{" "}
                      {orDash(secondProfile.birth_details.tob)}
                    </div>
                    <div>
                      <strong>{t("common.place")}:</strong>{" "}
                      {orDash(secondProfile.birth_details.place)}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Calculate Button */}
          <button
            className="ui-btn ui-btn--primary ui-btn--block ui-btn--lg"
            style={{ marginTop: "var(--space-lg)" }}
            onClick={handleCalculate}
            disabled={loading || !secondProfile}
          >
            <Heart size={20} />
            {loading ? t("compat.calculating") : t("compat.check")}
          </button>
        </div>

        {/* Loading State */}
        {loading && (
          <Card>
            <LoadingState message={t("compat.loading")} />
          </Card>
        )}

        {/* Results */}
        {result && !loading && (
          <div className="ui-card ui-card--accent fade-in">
            <h3 className="ui-card-header">
              <Heart size={24} />
              {t("compat.results")}
            </h3>

            {/* Total Score Display */}
            <div className="score-box">
              <div className="score-box__label">{t("compat.totalScore")}</div>
              <div className="score-box__value">
                {result.total_score}
                <span className="score-box__value-max">/{result.max_score || 36}</span>
              </div>
              <div className="score-box__status">
                {t("compat.status")}: {result.status}
              </div>
              {(result.boy?.nakshatra || result.girl?.nakshatra) && (
                <div className="score-box__nakshatras">
                  {nameA}: {result.boy?.nakshatra} ({t("compat.pada")} {result.boy?.pada}) &nbsp;•&nbsp;{" "}
                  {nameB}: {result.girl?.nakshatra} ({t("compat.pada")} {result.girl?.pada})
                </div>
              )}
            </div>

            {/* Ashtakoot Breakdown */}
            <h4 className="card-subhead">{t("compat.breakdown")}</h4>
            <div className="koota-grid">
              {(result.kootas || []).map((koota) => {
                const tier =
                  koota.score >= koota.max * 0.7
                    ? "good"
                    : koota.score >= koota.max * 0.4
                      ? "mid"
                      : "low";
                return (
                  <div key={koota.key} className="koota-card" title={koota.description}>
                    <div className="koota-card__name">{koota.name}</div>
                    <div className={`koota-card__score koota-card__score--${tier}`}>
                      {koota.score}
                    </div>
                    <div className="koota-card__max">{t("compat.outOf", { max: koota.max })}</div>
                  </div>
                );
              })}
            </div>

            {/* Side-by-side charts for visual comparison */}
            {chartA && chartB && (
              <>
                <h4 className="card-subhead">
                  <GitCompareArrows size={20} />
                  {t("compat.charts")}
                </h4>
                <div className="chart-grid" style={{ marginBottom: "var(--space-xl)" }}>
                  <Card title={nameA} accent="saffron">
                    <Kundali
                      planets={chartA.planets}
                      lagna={chartA.lagna}
                      title={nameA}
                      exportable
                    />
                  </Card>
                  <Card title={nameB} accent="vermillion">
                    <Kundali
                      planets={chartB.planets}
                      lagna={chartB.lagna}
                      title={nameB}
                      exportable
                    />
                  </Card>
                </div>
              </>
            )}

            {/* AI Analysis (on-demand) */}
            <div className="ai-panel">
              <h4 className="ai-panel__title">
                <Sparkles size={20} style={{ color: "var(--saffron)" }} />
                {t("compat.aiAnalysis")}
              </h4>

              <ErrorBanner message={aiError} />

              {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("compat.aiHint")}</p>}

              {aiLoading && <LoadingState message={t("compat.aiLoading")} />}

              {aiAnalysis && !aiLoading && (
                <div className="sbc-ai-markdown ai-panel__reading">
                  <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                  {aiModel && (
                    <div className="ai-panel__meta">{t("compat.aiModel", { model: aiModel })}</div>
                  )}
                </div>
              )}

              {!aiLoading && (
                <button className="ui-btn ui-btn--ai" onClick={handleAiAnalysis}>
                  <Sparkles size={18} />
                  {aiAnalysis ? t("compat.aiRegenerate") : t("compat.aiGenerate")}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
