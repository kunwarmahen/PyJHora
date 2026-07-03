import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Crosshair, Sparkles, Target, ShieldAlert } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { Card } from "../components/Card";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { DEFAULT_AYANAMSA } from "../constants/jyotish";
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
  };
};

export const SensitivePointsPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile } = useProfile();
  const ayanamsa = localStorage.getItem("ayanamsa") || DEFAULT_AYANAMSA;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");

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
      const res = await astrologyService.getSensitivePoints(birthDetails, ayanamsa);
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("sensitive.calcError"));
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
      const res = await astrologyService.analyzeSensitivePointsAI(
        birthDetails,
        { personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("sensitive.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const sphutas = data?.sphuta?.sphutas || [];
  const sahams = data?.sahams?.sahams || [];
  const argala = (data?.argala?.houses || []).filter(
    (h) => h.net !== "none" && h.net !== "balanced"
  );

  const netLabel = (net) =>
    net === "argala"
      ? t("sensitive.netArgala")
      : net === "virodhargala"
      ? t("sensitive.netVirodha")
      : t("sensitive.netBalanced");

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Crosshair size={24} />}
        title={t("sensitive.title")}
        subtitle={t("sensitive.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        {loading && (
          <Card>
            <LoadingState message={t("sensitive.loading")} />
          </Card>
        )}
        <ErrorBanner message={error} />

        {!loading && !error && data && (
          <div className="fade-in">
            <p className="card-intro">{t("sensitive.intro")}</p>

            {/* Sphutas */}
            <Card
              title={t("sensitive.sphutaTitle")}
              icon={<Target size={22} />}
              accent="saffron"
              count={sphutas.length}
            >
              <p className="card-note">{t("sensitive.sphutaNote")}</p>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("sensitive.colPoint")}</th>
                      <th>{t("sensitive.colMeaning")}</th>
                      <th>{t("sensitive.colSign")}</th>
                      <th>{t("sensitive.colHouse")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sphutas.map((s) => (
                      <tr key={s.name}>
                        <td className="fw-700">{s.name}</td>
                        <td className="text-secondary">{s.significance}</td>
                        <td>
                          {s.sign_name} {s.degrees}°
                        </td>
                        <td>{s.house}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            {/* Sahams */}
            <div className="mt-xl">
              <Card
                title={t("sensitive.sahamTitle")}
                icon={<Sparkles size={22} />}
                accent="gold"
                count={sahams.length}
              >
                <p className="card-note">{t("sensitive.sahamNote")}</p>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("sensitive.colSaham")}</th>
                        <th>{t("sensitive.colMeaning")}</th>
                        <th>{t("sensitive.colSign")}</th>
                        <th>{t("sensitive.colHouse")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sahams.map((s) => (
                        <tr key={s.name}>
                          <td className="fw-700">{s.name}</td>
                          <td className="text-secondary">{s.significance}</td>
                          <td>
                            {s.sign_name} {s.degrees}°
                          </td>
                          <td>{s.house}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>

            {/* Argala */}
            <div className="mt-xl">
              <Card
                title={t("sensitive.argalaTitle")}
                icon={<ShieldAlert size={22} />}
                accent="vermillion"
                count={argala.length}
              >
                <p className="card-note">{t("sensitive.argalaNote")}</p>
                {argala.length === 0 ? (
                  <p className="text-secondary">{t("sensitive.argalaEmpty")}</p>
                ) : (
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>{t("sensitive.colHouse")}</th>
                          <th>{t("sensitive.colSign")}</th>
                          <th>{t("sensitive.colArgala")}</th>
                          <th>{t("sensitive.colVirodha")}</th>
                          <th>{t("sensitive.colNet")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {argala.map((h) => (
                          <tr key={h.bhava}>
                            <td className="fw-700">{h.bhava}</td>
                            <td>{h.sign_name}</td>
                            <td>
                              {h.argala
                                .map((a) => `${a.planets.join(", ")} (${a.from})`)
                                .join("; ") || "—"}
                            </td>
                            <td>
                              {h.virodhargala
                                .map((a) => `${a.planets.join(", ")} (${a.from})`)
                                .join("; ") || "—"}
                            </td>
                            <td>
                              <span className={`sp-net sp-net--${h.net}`}>
                                {netLabel(h.net)}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            </div>

            {/* AI reading */}
            <div className="mt-xl">
              <Card
                title={t("sensitive.aiTitle")}
                icon={<Sparkles size={24} />}
                accent="gold"
              >
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && (
                  <p className="ai-panel__hint">{t("sensitive.aiHint")}</p>
                )}
                {aiLoading && <LoadingState message={t("sensitive.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">
                        {t("sensitive.aiModel", { model: aiModel })}
                      </div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("sensitive.aiRegenerate") : t("sensitive.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("sensitive.disclaimer")}</p>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SensitivePointsPage;
