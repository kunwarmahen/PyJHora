import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Gem, Sparkles, Sun, ShieldAlert } from "lucide-react";
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
    baseUrl:
      providerType === "ollama"
        ? localStorage.getItem("ai_base_url") || undefined
        : undefined,
    legacyProvider: providerType === "ollama" ? "qwen" : providerType,
    maxTokens: parseInt(localStorage.getItem("ai_max_tokens") || "0", 10) || undefined,
  };
};

export const RemediesPage = () => {
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
  // Reopen a saved reading from History (chart recomputes for the restored
  // profile; the exact saved AI text is applied once the load settles).
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
      const res = await astrologyService.getRemedies(birthDetails, ayanamsa);
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("remedies.calcError"));
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
      const res = await astrologyService.analyzeRemediesAI(
        birthDetails,
        { personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("remedies.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const remedies = data?.remedies || [];
  const weak = (data?.planets || []).filter((p) => p.weak);

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Gem size={24} />}
        title={t("remedies.title")}
        subtitle={t("remedies.subtitle")}
        accent="terracotta"
      />

      <div className="dashboard-content">
        <RecentReadings source="remedies" profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />

        <p className="readonly-banner">
          <ShieldAlert size={15} /> {t("remedies.disclaimer")}
        </p>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("remedies.loading")} />
          </Card>
        ) : data ? (
          <div className="fade-in">
            <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush">
              <h3 className="ui-card-header ui-card-header--sm">
                <Sun size={18} /> {t("remedies.weakHeader", { count: remedies.length })}
              </h3>
              {remedies.length === 0 ? (
                <p className="card-note">{t("remedies.noneWeak")}</p>
              ) : (
                <div className="rem-grid">
                  {remedies.map((r) => (
                    <div key={r.planet} className="rem-card">
                      <div className="rem-card__head">
                        <span className="rem-card__planet">{r.planet}</span>
                        <span className="rem-card__reason">{r.reason}</span>
                      </div>
                      <dl className="rem-card__body">
                        <div>
                          <dt>{t("remedies.gemstone")}</dt>
                          <dd>{r.gemstone}</dd>
                        </div>
                        <div>
                          <dt>{t("remedies.mantra")}</dt>
                          <dd>
                            {r.mantra}
                            {r.mantra_count && (
                              <span className="text-secondary"> ({r.mantra_count})</span>
                            )}
                          </dd>
                        </div>
                        <div>
                          <dt>{t("remedies.deity")}</dt>
                          <dd>{r.deity}</dd>
                        </div>
                        <div>
                          <dt>{t("remedies.day")}</dt>
                          <dd>{r.day}</dd>
                        </div>
                        <div>
                          <dt>{t("remedies.donation")}</dt>
                          <dd>{r.donation}</dd>
                        </div>
                        <div>
                          <dt>{t("remedies.color")}</dt>
                          <dd>{r.color}</dd>
                        </div>
                      </dl>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Dignity overview */}
            <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm">{t("remedies.dignityHeader")}</h3>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("remedies.planet")}</th>
                      <th>{t("remedies.sign")}</th>
                      <th>{t("remedies.house")}</th>
                      <th>{t("remedies.dignity")}</th>
                      <th>{t("remedies.strength")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.planets || []).map((p) => (
                      <tr key={p.planet} className={p.weak ? "rem-row--weak" : ""}>
                        <td>{p.planet}</td>
                        <td>{p.sign_name}</td>
                        <td>{p.house}</td>
                        <td>{t(`remedies.dignities.${p.dignity}`, p.dignity)}</td>
                        <td>{p.strength_ratio != null ? p.strength_ratio.toFixed(2) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {weak.length > 0 && (
                <p className="card-note">{t("remedies.weakFootnote")}</p>
              )}
            </div>

            {/* AI reading */}
            <div className="mt-xl">
              <Card title={t("remedies.aiTitle")} icon={<Sparkles size={24} />} accent="terracotta">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("remedies.aiHint")}</p>}
                {aiLoading && <LoadingState message={t("remedies.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">{t("remedies.aiModel", { model: aiModel })}</div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("remedies.aiRegenerate") : t("remedies.aiGenerate")}
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

export default RemediesPage;
