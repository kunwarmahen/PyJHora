import React, { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { GitCompareArrows, Users, Sparkles } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { DEFAULT_AYANAMSA } from "../constants/jyotish";
import "../styles/Dashboard.css";

const PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"];

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

// One "Lagna / Moon / Sun / planet → sign" row, comparing the two charts.
const compareRows = (a, b) => {
  const rows = [
    { label: "Lagna", a: a?.lagna?.sign_name, b: b?.lagna?.sign_name },
    { label: "Moon", a: a?.d1_chart?.Moon?.sign_name, b: b?.d1_chart?.Moon?.sign_name },
    { label: "Sun", a: a?.d1_chart?.Sun?.sign_name, b: b?.d1_chart?.Sun?.sign_name },
  ];
  PLANETS.forEach((pl) => {
    rows.push({
      label: pl,
      a: a?.d1_chart?.[pl]?.sign_name,
      b: b?.d1_chart?.[pl]?.sign_name,
      sub: true,
    });
  });
  return rows;
};

export const ComparePage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile, profiles, loadProfiles } = useProfile();

  const ayanamsa = localStorage.getItem("ayanamsa") || DEFAULT_AYANAMSA;
  const chartStyle = localStorage.getItem("chartStyle") || "north";
  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;

  const [secondId, setSecondId] = useState("");
  const [chartA, setChartA] = useState(null);
  const [chartB, setChartB] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // AI comparison is on-demand (uses the model picked in "Ask Astrologer").
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    loadProfiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, navigate]);

  const secondProfile = useMemo(
    () => profiles?.find((p) => p._id === secondId) || null,
    [profiles, secondId]
  );

  useEffect(() => {
    // Any change to the pairing invalidates a prior AI reading.
    setAiAnalysis("");
    setAiError("");
    setAiModel("");
    if (!selectedProfile || !secondProfile) {
      setChartA(null);
      setChartB(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([
      astrologyService.calculateBirthChart(toBirthDetails(selectedProfile), ayanamsa),
      astrologyService.calculateBirthChart(toBirthDetails(secondProfile), ayanamsa),
    ])
      .then(([ra, rb]) => {
        if (cancelled) return;
        setChartA(ra.data);
        setChartB(rb.data);
      })
      .catch((e) => {
        if (!cancelled) setError(e.response?.data?.detail || t("compare.calcError"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, secondProfile, ayanamsa]);

  const handleAiAnalysis = async () => {
    if (!selectedProfile || !secondProfile) return;
    setAiLoading(true);
    setAiError("");
    try {
      const response = await astrologyService.compareChartsAI(
        toBirthDetails(selectedProfile),
        toBirthDetails(secondProfile),
        { name1: selectedProfile.profile_name, name2: secondProfile.profile_name },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(response.data.ai_analysis || "");
      setAiModel(response.data.model || response.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("compare.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const otherProfiles = (profiles || []).filter((p) => p._id !== selectedProfile._id);
  const nameA = selectedProfile.profile_name;
  const nameB = secondProfile?.profile_name || t("compare.person2");

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<GitCompareArrows size={24} />}
        title={t("compare.title")}
        subtitle={t("compare.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <Card title={t("compare.selectSecond")} icon={<Users size={24} />} accent="saffron">
          <div className="ui-field-grid">
            <div className="ui-datafield">
              <div className="ui-datafield-label">{t("compare.person1")}</div>
              <div className="ui-datafield-value">{nameA}</div>
            </div>
            <label className="ui-datafield" style={{ cursor: "pointer" }}>
              <div className="ui-datafield-label">{t("compare.person2")}</div>
              <select
                value={secondId}
                onChange={(e) => setSecondId(e.target.value)}
                style={{
                  width: "100%",
                  marginTop: "var(--space-xs)",
                  padding: "var(--space-sm)",
                  borderRadius: "var(--radius-md)",
                  border: "2px solid var(--sandalwood)",
                  background: "white",
                  color: "var(--cosmic-indigo)",
                  fontWeight: 600,
                }}
              >
                <option value="">{t("compare.chooseProfile")}</option>
                {otherProfiles.map((p) => (
                  <option key={p._id} value={p._id}>
                    {p.profile_name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {otherProfiles.length === 0 && (
            <p style={{ color: "var(--text-secondary)", marginTop: "var(--space-md)" }}>
              {t("compare.needTwo")}
            </p>
          )}
        </Card>

        <ErrorBanner message={error} />

        {loading && (
          <Card>
            <LoadingState message={t("compare.calcBoth")} />
          </Card>
        )}

        {!loading && chartA && chartB && (
          <>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
                gap: "var(--space-xl)",
              }}
            >
              <Card title={nameA} accent="saffron">
                <Kundali planets={chartA.planets} lagna={chartA.lagna} title={nameA} exportable />
              </Card>
              <Card title={nameB} accent="vermillion">
                <Kundali planets={chartB.planets} lagna={chartB.lagna} title={nameB} exportable />
              </Card>
            </div>

            <Card
              title={t("compare.placements")}
              icon={<GitCompareArrows size={24} />}
              accent="indigo"
            >
              <div style={{ overflowX: "auto" }}>
                <table className="adv-table">
                  <thead>
                    <tr>
                      <th>{t("compare.body")}</th>
                      <th>{nameA}</th>
                      <th>{nameB}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {compareRows(chartA, chartB).map((r) => (
                      <tr key={r.label}>
                        <td style={{ fontWeight: r.sub ? 400 : 700 }}>{r.label}</td>
                        <td
                          style={{
                            background: r.a && r.a === r.b ? "rgba(255,153,51,0.12)" : undefined,
                          }}
                        >
                          {r.a || "—"}
                        </td>
                        <td
                          style={{
                            background: r.a && r.a === r.b ? "rgba(255,153,51,0.12)" : undefined,
                          }}
                        >
                          {r.b || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p
                style={{
                  color: "var(--text-secondary)",
                  marginTop: "var(--space-md)",
                  fontSize: "0.85rem",
                }}
              >
                {t("compare.highlightNote")}
              </p>
            </Card>

            {/* AI comparison (on-demand, neutral — not marriage matching) */}
            <Card title={t("compare.aiTitle")} icon={<Sparkles size={24} />} accent="indigo">
              <ErrorBanner message={aiError} />

              {!aiAnalysis && !aiLoading && (
                <p
                  style={{
                    color: "var(--text-secondary)",
                    marginBottom: "var(--space-md)",
                    fontSize: "0.9rem",
                  }}
                >
                  {t("compare.aiHint")}
                </p>
              )}

              {aiLoading && <LoadingState message={t("compare.aiLoading")} />}

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
                      {t("compare.aiModel", { model: aiModel })}
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
                  {aiAnalysis ? t("compare.aiRegenerate") : t("compare.aiGenerate")}
                </button>
              )}
            </Card>
          </>
        )}
      </div>
    </div>
  );
};

export default ComparePage;
