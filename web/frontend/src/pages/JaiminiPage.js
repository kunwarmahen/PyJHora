import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Layers, Sparkles, Sun, Anchor } from "lucide-react";
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

export const JaiminiPage = () => {
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
    try {
      const res = await astrologyService.getJaimini(birthDetails, ayanamsa);
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("jaimini.calcError"));
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
      const res = await astrologyService.analyzeJaiminiAI(
        birthDetails,
        { personName: birthDetails.name, profileId: selectedProfile?._id },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("jaimini.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const ck = data?.chara_karakas || [];
  const kk = data?.karakamsa || {};
  const sw = data?.swamsa || {};
  const argala = data?.argala || [];

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Layers size={24} />}
        title={t("jaimini.title")}
        subtitle={t("jaimini.subtitle")}
        accent="terracotta"
      />

      <div className="dashboard-content">
        <RecentReadings source="jaimini" profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("jaimini.loading")} />
          </Card>
        ) : data ? (
          <div className="fade-in">
            {/* Chara Karakas */}
            <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush">
              <h3 className="ui-card-header ui-card-header--sm">
                <Sun size={18} /> {t("jaimini.karakasHeader")}
              </h3>
              <p className="card-note">{t("jaimini.karakasNote")}</p>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("jaimini.karaka")}</th>
                      <th>{t("jaimini.planet")}</th>
                      <th>{t("jaimini.sign")}</th>
                      <th>{t("jaimini.house")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ck.map((k) => (
                      <tr key={k.karaka} className={k.karaka.startsWith("Atma") ? "rem-row--weak" : ""}>
                        <td><strong>{k.karaka}</strong></td>
                        <td>{k.planet}</td>
                        <td>{k.sign_name}</td>
                        <td>{k.house || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Karakamsa + Swamsa */}
            <div className="card-grid mt-xl">
              <div className="ui-card ui-card--accent-indigo ui-card--pad-lg">
                <h3 className="ui-card-header ui-card-header--sm">{t("jaimini.karakamsa")}</h3>
                <p className="card-intro">
                  {t("jaimini.karakamsaDesc", { planet: data.atmakaraka, sign: kk.sign_name })}
                </p>
                <dl className="detail-list">
                  <div><strong>{t("jaimini.occupants")}:</strong> {(kk.occupants || []).join(", ") || t("jaimini.none")}</div>
                  <div><strong>{t("jaimini.aspects")}:</strong> {(kk.aspecting_planets || []).join(", ") || t("jaimini.none")}</div>
                </dl>
              </div>
              <div className="ui-card ui-card--accent ui-card--pad-lg">
                <h3 className="ui-card-header ui-card-header--sm">{t("jaimini.swamsa")}</h3>
                <p className="card-intro">{t("jaimini.swamsaDesc", { sign: sw.sign_name })}</p>
                <dl className="detail-list">
                  <div><strong>{t("jaimini.occupants")}:</strong> {(sw.occupants || []).join(", ") || t("jaimini.none")}</div>
                  <div><strong>{t("jaimini.aspects")}:</strong> {(sw.aspecting_planets || []).join(", ") || t("jaimini.none")}</div>
                </dl>
              </div>
            </div>

            {/* Argala */}
            <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm">
                <Anchor size={18} /> {t("jaimini.argalaHeader")}
              </h3>
              <p className="card-note">{t("jaimini.argalaNote")}</p>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("jaimini.house")}</th>
                      <th>{t("jaimini.sign")}</th>
                      <th>{t("jaimini.argala")}</th>
                      <th>{t("jaimini.virodhargala")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {argala.map((a) => (
                      <tr key={a.house}>
                        <td><strong>{a.house}</strong></td>
                        <td>{a.sign_name}</td>
                        <td>{(a.argala || []).join(", ") || "—"}</td>
                        <td className="text-secondary">{(a.virodhargala || []).join(", ") || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* AI reading */}
            <div className="mt-xl">
              <Card title={t("jaimini.aiTitle")} icon={<Sparkles size={24} />} accent="terracotta">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("jaimini.aiHint")}</p>}
                {aiLoading && <LoadingState message={t("jaimini.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && <div className="ai-panel__meta">{t("jaimini.aiModel", { model: aiModel })}</div>}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("jaimini.aiRegenerate") : t("jaimini.aiGenerate")}
                  </button>
                )}
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default JaiminiPage;
