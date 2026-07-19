import React, { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import { GitCompareArrows, Users, Sparkles } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { errorMessage } from "../utils/format";
import { astrologyService } from "../services/api";
import { useRestoreReading } from "../hooks/useRestoreReading";
import { RecentReadings } from "../components/RecentReadings";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { useSettings } from "../contexts/SettingsContext";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import { useLocalizeName } from "../i18n/localizeName";

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
    maxTokens: parseInt(localStorage.getItem("ai_max_tokens") || "0", 10) || undefined,
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
// `ln` is passed in rather than hooked here: this is a module-level helper, so
// it can't call useLocalizeName() itself.
const compareRows = (a, b, ln) => {
  const rows = [
    {
      label: "Lagna",
      a: ln(a?.lagna?.sign_name, "rasi"),
      b: ln(b?.lagna?.sign_name, "rasi"),
    },
    {
      label: "Moon",
      a: ln(a?.d1_chart?.Moon?.sign_name, "rasi"),
      b: ln(b?.d1_chart?.Moon?.sign_name, "rasi"),
    },
    {
      label: "Sun",
      a: ln(a?.d1_chart?.Sun?.sign_name, "rasi"),
      b: ln(b?.d1_chart?.Sun?.sign_name, "rasi"),
    },
  ];
  PLANETS.forEach((pl) => {
    rows.push({
      label: pl,
      a: ln(a?.d1_chart?.[pl]?.sign_name, "rasi"),
      b: ln(b?.d1_chart?.[pl]?.sign_name, "rasi"),
      sub: true,
    });
  });
  return rows;
};

export const ComparePage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const ln = useLocalizeName();
  const { selectedProfile, profiles, loadProfiles } = useProfile();

  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;
  const chartStyle = settings.chartStyle;
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
  // Reopen a saved reading from History: recompute both charts from the saved
  // pair so the (chart-gated) comparison + saved reading are visible. Factual
  // only — no AI re-generation.
  const [pendingReading, setPendingReading] = useState(null);
  useRestoreReading((r) => setPendingReading({ reading: r.reading, model: r.model, context: r.context }));
  useEffect(() => {
    if (pendingReading && !loading) {
      const c = pendingReading.context || {};
      setAiAnalysis(pendingReading.reading);
      setAiModel(pendingReading.model);
      if (c.person1_details && c.person2_details) {
        Promise.all([
          astrologyService.calculateBirthChart(c.person1_details, c.ayanamsa),
          astrologyService.calculateBirthChart(c.person2_details, c.ayanamsa),
        ])
          .then(([ra, rb]) => {
            setChartA(ra.data);
            setChartB(rb.data);
          })
          .catch(() => {});
      }
      setPendingReading(null);
    }
  }, [pendingReading, loading]);

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
        if (!cancelled) setError(errorMessage(e, t("compare.calcError")));
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
      setAiError(errorMessage(err, t("compare.aiError")));
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
        <RecentReadings source="compare" />
        <Card title={t("compare.selectSecond")} icon={<Users size={24} />} accent="saffron">
          <div className="ui-field-grid">
            <div className="ui-datafield">
              <div className="ui-datafield-label">{t("compare.person1")}</div>
              <div className="ui-datafield-value">{nameA}</div>
            </div>
            <label className="ui-datafield" style={{ cursor: "pointer" }}>
              <div className="ui-datafield-label">{t("compare.person2")}</div>
              <select
                className="form-select"
                style={{ marginTop: "var(--space-xs)" }}
                value={secondId}
                onChange={(e) => setSecondId(e.target.value)}
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
            <p className="text-secondary" style={{ marginTop: "var(--space-md)" }}>
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
            <div className="chart-grid">
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
              <div className="table-scroll">
                <table className="adv-table">
                  <thead>
                    <tr>
                      <th>{t("compare.body")}</th>
                      <th>{nameA}</th>
                      <th>{nameB}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {compareRows(chartA, chartB, ln).map((r) => {
                      const match = r.a && r.a === r.b ? "is-match" : "";
                      return (
                        <tr key={r.label}>
                          <td className={r.sub ? "fw-400" : "fw-700"}>{r.label}</td>
                          <td className={match}>{r.a || "—"}</td>
                          <td className={match}>{r.b || "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="card-note" style={{ fontSize: "0.85rem" }}>
                {t("compare.highlightNote")}
              </p>
            </Card>

            {/* AI comparison (on-demand, neutral — not marriage matching) */}
            <Card title={t("compare.aiTitle")} icon={<Sparkles size={24} />} accent="indigo">
              <ErrorBanner message={aiError} />

              {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("compare.aiHint")}</p>}

              {aiLoading && <LoadingState message={t("compare.aiLoading")} />}

              {aiAnalysis && !aiLoading && (
                <div className="sbc-ai-markdown ai-panel__reading">
                  <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                  {aiModel && (
                    <div className="ai-panel__meta">{t("compare.aiModel", { model: aiModel })}</div>
                  )}
                </div>
              )}

              {!aiLoading && (
                <button className="ui-btn ui-btn--ai" onClick={handleAiAnalysis}>
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
