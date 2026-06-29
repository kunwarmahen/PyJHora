import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Heart, User, Users, Sparkles, GitCompareArrows } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { formatDate, orDash } from "../utils/format";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { DEFAULT_AYANAMSA } from "../constants/jyotish";
import "../styles/Dashboard.css";

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

  const ayanamsa = localStorage.getItem("ayanamsa") || DEFAULT_AYANAMSA;
  const chartStyle = localStorage.getItem("chartStyle") || "north";
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
      setError(err.response?.data?.detail || t("compat.calcError"));
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
      setAiError(err.response?.data?.detail || t("compat.aiError"));
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
        <div
          style={{
            background: "white",
            borderRadius: "var(--radius-xl)",
            padding: "var(--space-xl)",
            marginBottom: "var(--space-xl)",
            boxShadow: "var(--shadow-lg)",
            borderTop: "4px solid var(--saffron)",
            animation: "fadeIn 0.6s ease-out",
          }}
        >
          <h3
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-sm)",
              marginBottom: "var(--space-lg)",
              color: "var(--cosmic-indigo)",
              fontSize: "1.5rem",
            }}
          >
            <Users size={24} style={{ color: "var(--saffron)" }} />
            {t("compat.selectProfiles")}
          </h3>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
              gap: "var(--space-lg)",
            }}
          >
            {/* Person 1 - Selected Profile */}
            <div
              style={{
                padding: "var(--space-lg)",
                background:
                  "linear-gradient(135deg, rgba(255, 153, 51, 0.05) 0%, rgba(255, 153, 51, 0.15) 100%)",
                borderRadius: "var(--radius-lg)",
                border: "2px solid var(--saffron)",
              }}
            >
              <h4
                style={{
                  color: "var(--saffron)",
                  marginBottom: "var(--space-md)",
                  fontSize: "1.125rem",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-sm)",
                }}
              >
                <User size={20} /> {t("compare.person1")}
              </h4>
              <div
                style={{
                  padding: "var(--space-md)",
                  background: "white",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--sandalwood)",
                }}
              >
                <p
                  style={{
                    margin: "0 0 var(--space-sm) 0",
                    fontWeight: 600,
                    color: "var(--cosmic-indigo)",
                    fontSize: "1.125rem",
                  }}
                >
                  {selectedProfile.profile_name}
                </p>
                <div
                  style={{
                    fontSize: "0.875rem",
                    color: "var(--text-secondary)",
                    lineHeight: "1.6",
                  }}
                >
                  <div style={{ marginBottom: "var(--space-xs)" }}>
                    <strong>{t("common.name")}:</strong>{" "}
                    {selectedProfile.birth_details.name || t("common.anonymous")}
                  </div>
                  <div style={{ marginBottom: "var(--space-xs)" }}>
                    <strong>{t("common.dateOfBirth")}:</strong>{" "}
                    {formatDate(selectedProfile.birth_details.dob)}
                  </div>
                  <div style={{ marginBottom: "var(--space-xs)" }}>
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
            <div
              style={{
                padding: "var(--space-lg)",
                background:
                  "linear-gradient(135deg, rgba(227, 66, 52, 0.05) 0%, rgba(227, 66, 52, 0.15) 100%)",
                borderRadius: "var(--radius-lg)",
                border: "2px solid var(--vermillion)",
              }}
            >
              <h4
                style={{
                  color: "var(--vermillion)",
                  marginBottom: "var(--space-md)",
                  fontSize: "1.125rem",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-sm)",
                }}
              >
                <User size={20} /> {t("compare.person2")}
              </h4>
              <label
                style={{
                  display: "block",
                  marginBottom: "var(--space-sm)",
                  fontWeight: 600,
                  color: "var(--cosmic-indigo)",
                  fontSize: "0.875rem",
                }}
              >
                {t("compat.selectToCompare")}
              </label>
              <select
                value={secondProfile?._id || ""}
                onChange={(e) => {
                  const profile = profiles.find((p) => p._id === e.target.value);
                  setSecondProfile(profile || null);
                  resetResults();
                }}
                style={{
                  width: "100%",
                  padding: "var(--space-md)",
                  borderRadius: "var(--radius-md)",
                  border: "2px solid var(--sandalwood)",
                  fontSize: "1rem",
                  fontFamily: "inherit",
                  background: "white",
                  color: "var(--cosmic-indigo)",
                  cursor: "pointer",
                  transition: "all 0.3s ease",
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
                <div
                  style={{
                    marginTop: "var(--space-md)",
                    padding: "var(--space-md)",
                    background: "white",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--sandalwood)",
                    animation: "fadeIn 0.3s ease-out",
                  }}
                >
                  <p
                    style={{
                      margin: "0 0 var(--space-sm) 0",
                      fontWeight: 600,
                      color: "var(--cosmic-indigo)",
                      fontSize: "1.125rem",
                    }}
                  >
                    {secondProfile.profile_name}
                  </p>
                  <div
                    style={{
                      fontSize: "0.875rem",
                      color: "var(--text-secondary)",
                      lineHeight: "1.6",
                    }}
                  >
                    <div style={{ marginBottom: "var(--space-xs)" }}>
                      <strong>{t("common.name")}:</strong>{" "}
                      {secondProfile.birth_details.name || t("common.anonymous")}
                    </div>
                    <div style={{ marginBottom: "var(--space-xs)" }}>
                      <strong>{t("common.dateOfBirth")}:</strong>{" "}
                      {formatDate(secondProfile.birth_details.dob)}
                    </div>
                    <div style={{ marginBottom: "var(--space-xs)" }}>
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
            onClick={handleCalculate}
            disabled={loading || !secondProfile}
            style={{
              marginTop: "var(--space-lg)",
              width: "100%",
              padding: "var(--space-lg)",
              background: secondProfile
                ? "linear-gradient(135deg, var(--saffron) 0%, var(--vermillion) 100%)"
                : "var(--sandalwood)",
              color: "white",
              border: "none",
              borderRadius: "var(--radius-lg)",
              fontSize: "1.125rem",
              fontWeight: 700,
              cursor: secondProfile ? "pointer" : "not-allowed",
              boxShadow: secondProfile ? "var(--shadow-lg)" : "none",
              transition: "all 0.3s ease",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "var(--space-sm)",
            }}
            onMouseOver={(e) => {
              if (secondProfile) {
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.boxShadow = "0 8px 24px rgba(255, 153, 51, 0.4)";
              }
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = secondProfile ? "var(--shadow-lg)" : "none";
            }}
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
          <div
            style={{
              background: "white",
              borderRadius: "var(--radius-xl)",
              padding: "var(--space-xl)",
              boxShadow: "var(--shadow-lg)",
              borderTop: "4px solid var(--saffron)",
              animation: "fadeIn 0.6s ease-out",
            }}
          >
            <h3
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-sm)",
                marginBottom: "var(--space-lg)",
                color: "var(--cosmic-indigo)",
                fontSize: "1.5rem",
              }}
            >
              <Heart size={24} style={{ color: "var(--saffron)" }} />
              {t("compat.results")}
            </h3>

            {/* Total Score Display */}
            <div
              style={{
                padding: "var(--space-xl)",
                background:
                  "linear-gradient(135deg, rgba(255, 153, 51, 0.1) 0%, rgba(227, 66, 52, 0.1) 100%)",
                borderRadius: "var(--radius-lg)",
                marginBottom: "var(--space-xl)",
                textAlign: "center",
                border: "2px solid var(--saffron)",
              }}
            >
              <div
                style={{
                  fontSize: "0.875rem",
                  color: "var(--text-secondary)",
                  marginBottom: "var(--space-sm)",
                  textTransform: "uppercase",
                  letterSpacing: "1px",
                  fontWeight: 600,
                }}
              >
                {t("compat.totalScore")}
              </div>
              <div
                style={{
                  fontSize: "4rem",
                  fontWeight: 700,
                  background: "linear-gradient(135deg, var(--saffron) 0%, var(--vermillion) 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  marginBottom: "var(--space-sm)",
                }}
              >
                {result.total_score}
                <span style={{ fontSize: "2rem" }}>/{result.max_score || 36}</span>
              </div>
              <div
                style={{
                  padding: "var(--space-md)",
                  background: "white",
                  borderRadius: "var(--radius-md)",
                  display: "inline-block",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                <span
                  style={{ fontWeight: 700, color: "var(--cosmic-indigo)", fontSize: "1.125rem" }}
                >
                  {t("compat.status")}: {result.status}
                </span>
              </div>
              {(result.boy?.nakshatra || result.girl?.nakshatra) && (
                <div
                  style={{
                    marginTop: "var(--space-md)",
                    fontSize: "0.875rem",
                    color: "var(--text-secondary)",
                  }}
                >
                  {nameA}: {result.boy?.nakshatra} ({t("compat.pada")} {result.boy?.pada}) &nbsp;•&nbsp;{" "}
                  {nameB}: {result.girl?.nakshatra} ({t("compat.pada")} {result.girl?.pada})
                </div>
              )}
            </div>

            {/* Ashtakoot Breakdown */}
            <h4
              style={{
                color: "var(--cosmic-indigo)",
                marginBottom: "var(--space-md)",
                fontSize: "1.25rem",
                fontWeight: 700,
              }}
            >
              {t("compat.breakdown")}
            </h4>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
                gap: "var(--space-md)",
                marginBottom: "var(--space-xl)",
              }}
            >
              {(result.kootas || []).map((koota) => (
                <div
                  key={koota.key}
                  title={koota.description}
                  style={{
                    padding: "var(--space-md)",
                    background: "var(--sacred-white)",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid var(--sandalwood)",
                    textAlign: "center",
                    transition: "all 0.3s ease",
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.transform = "translateY(-2px)";
                    e.currentTarget.style.boxShadow = "var(--shadow-md)";
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.transform = "translateY(0)";
                    e.currentTarget.style.boxShadow = "none";
                  }}
                >
                  <div
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-secondary)",
                      marginBottom: "var(--space-xs)",
                      fontWeight: 600,
                    }}
                  >
                    {koota.name}
                  </div>
                  <div
                    style={{
                      fontSize: "1.5rem",
                      fontWeight: 700,
                      color:
                        koota.score >= koota.max * 0.7
                          ? "var(--emerald-green)"
                          : koota.score >= koota.max * 0.4
                            ? "var(--saffron)"
                            : "var(--vermillion)",
                    }}
                  >
                    {koota.score}
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    {t("compat.outOf", { max: koota.max })}
                  </div>
                </div>
              ))}
            </div>

            {/* Side-by-side charts for visual comparison */}
            {chartA && chartB && (
              <>
                <h4
                  style={{
                    color: "var(--cosmic-indigo)",
                    marginBottom: "var(--space-md)",
                    fontSize: "1.25rem",
                    fontWeight: 700,
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-sm)",
                  }}
                >
                  <GitCompareArrows size={20} style={{ color: "var(--saffron)" }} />
                  {t("compat.charts")}
                </h4>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
                    gap: "var(--space-xl)",
                    marginBottom: "var(--space-xl)",
                  }}
                >
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
            <div
              style={{
                padding: "var(--space-lg)",
                background:
                  "linear-gradient(135deg, rgba(52, 73, 94, 0.05) 0%, rgba(52, 73, 94, 0.1) 100%)",
                borderRadius: "var(--radius-lg)",
                border: "2px solid var(--cosmic-indigo)",
              }}
            >
              <h4
                style={{
                  color: "var(--cosmic-indigo)",
                  marginBottom: "var(--space-md)",
                  fontSize: "1.25rem",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "var(--space-sm)",
                }}
              >
                <Sparkles size={20} style={{ color: "var(--saffron)" }} />
                {t("compat.aiAnalysis")}
              </h4>

              <ErrorBanner message={aiError} />

              {!aiAnalysis && !aiLoading && (
                <p
                  style={{
                    color: "var(--text-secondary)",
                    marginBottom: "var(--space-md)",
                    fontSize: "0.9rem",
                  }}
                >
                  {t("compat.aiHint")}
                </p>
              )}

              {aiLoading && <LoadingState message={t("compat.aiLoading")} />}

              {aiAnalysis && !aiLoading && (
                <div
                  style={{
                    padding: "var(--space-md)",
                    background: "white",
                    borderRadius: "var(--radius-md)",
                    fontSize: "1rem",
                    lineHeight: "1.8",
                    color: "var(--cosmic-indigo)",
                    whiteSpace: "pre-wrap",
                    marginBottom: "var(--space-md)",
                  }}
                >
                  {aiAnalysis}
                  {aiModel && (
                    <div
                      style={{
                        marginTop: "var(--space-md)",
                        paddingTop: "var(--space-sm)",
                        borderTop: "1px solid var(--sandalwood)",
                        fontSize: "0.8rem",
                        color: "var(--text-secondary)",
                      }}
                    >
                      {t("compat.aiModel", { model: aiModel })}
                    </div>
                  )}
                </div>
              )}

              {!aiLoading && (
                <button
                  onClick={handleAiAnalysis}
                  style={{
                    padding: "var(--space-md) var(--space-lg)",
                    background:
                      "linear-gradient(135deg, var(--cosmic-indigo) 0%, var(--saffron) 100%)",
                    color: "white",
                    border: "none",
                    borderRadius: "var(--radius-md)",
                    fontSize: "1rem",
                    fontWeight: 600,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-sm)",
                  }}
                >
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
