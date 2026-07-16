import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Orbit, Sparkles, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { useRestoreReading } from "../hooks/useRestoreReading";
import { RecentReadings } from "../components/RecentReadings";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { Card } from "../components/Card";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { useSettings } from "../contexts/SettingsContext";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import "../styles/Gochara.css";

const readModelConfig = () => {
  const providerType = localStorage.getItem("ai_provider_type") || "ollama";
  return {
    providerType,
    model: localStorage.getItem("ai_model") || "",
    baseUrl:
      providerType === "ollama" ? localStorage.getItem("ai_base_url") || undefined : undefined,
    legacyProvider: providerType === "ollama" ? "qwen" : providerType,
    maxTokens: parseInt(localStorage.getItem("ai_max_tokens") || "0", 10) || undefined,
  };
};

const ToneIcon = ({ tone }) => {
  if (tone === "good") return <CheckCircle2 size={18} className="goc-ic goc-ic--good" />;
  if (tone === "caution") return <AlertTriangle size={18} className="goc-ic goc-ic--caution" />;
  return <XCircle size={18} className="goc-ic goc-ic--bad" />;
};

export const GocharaPhalaPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");

  const [pendingReading, setPendingReading] = useState(null);
  useRestoreReading((r) => setPendingReading({ reading: r.reading, model: r.model }));
  useEffect(() => {
    if (pendingReading && !loading) {
      setAiAnalysis(pendingReading.reading);
      setAiModel(pendingReading.model);
      setPendingReading(null);
    }
  }, [pendingReading, loading]);

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
    setAiAnalysis("");
    setAiError("");
    try {
      const tz = -new Date().getTimezoneOffset() / 60;
      const res = await astrologyService.getGocharaPhala(birthDetails, null, tz, ayanamsa);
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("gochara.calcError"));
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

  const handleAi = async () => {
    if (!birthDetails) return;
    setAiLoading(true);
    setAiError("");
    try {
      const tz = -new Date().getTimezoneOffset() / 60;
      const res = await astrologyService.analyzeGocharaPhalaAI(
        birthDetails,
        { personName: birthDetails.name, currentTz: tz },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("gochara.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const rows = data?.results || [];

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Orbit size={24} />}
        title={t("gochara.title")}
        subtitle={t("gochara.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <RecentReadings source="gochara_phala" profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />
        <p className="card-note">{t("gochara.intro")}</p>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("gochara.loading")} />
          </Card>
        ) : data ? (
          <div className="fade-in">
            <div className="info-pills">
              <span className="info-pill">{t("gochara.moonSign", { sign: data.moon_sign })}</span>
              <span className="info-pill">{t("gochara.asOf", { date: data.transit_date })}</span>
              <span className="info-pill">
                {t("gochara.favourableSummary", {
                  count: data.favourable_count,
                  total: data.total,
                })}
              </span>
            </div>

            <div className="mt-xl">
              <Card className="ui-card--flush">
                <div className="goc-table-wrap">
                  <table className="data-table goc-table">
                    <thead>
                      <tr>
                        <th>{t("gochara.colPlanet")}</th>
                        <th>{t("gochara.colHouse")}</th>
                        <th>{t("gochara.colVerdict")}</th>
                        <th>{t("gochara.colVedha")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr key={r.planet} className={`goc-row goc-row--${r.tone}`}>
                          <td className="goc-planet">{r.planet}</td>
                          <td>{t("gochara.houseFromMoon", { n: r.house_from_moon })}</td>
                          <td className="goc-verdict">
                            <ToneIcon tone={r.tone} />
                            <span>{r.verdict}</span>
                          </td>
                          <td>
                            {r.obstructed_by && r.obstructed_by.length
                              ? t("gochara.vedhaBy", { planets: r.obstructed_by.join(", ") })
                              : t("gochara.noVedha")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>

            {/* AI reading */}
            <div className="mt-xl">
              <Card title={t("gochara.aiTitle")} icon={<Sparkles size={24} />} accent="indigo">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("gochara.aiHint")}</p>}
                {aiLoading && <LoadingState message={t("gochara.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">{t("gochara.aiModel", { model: aiModel })}</div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("gochara.aiRegenerate") : t("gochara.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("gochara.disclaimer")}</p>
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default GocharaPhalaPage;
