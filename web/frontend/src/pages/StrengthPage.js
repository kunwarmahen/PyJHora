import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Gauge, Sparkles, Layers, Home } from "lucide-react";
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
import "../styles/Strength.css";

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

// Colour per shadbala source (six-fold). Distinct hues on the saffron ground.
const COMPONENT_COLORS = {
  sthana: "#ff9933",
  kaala: "#2d3561",
  dig: "#2E9E5B",
  cheshta: "#E27B5A",
  naisargika: "#d4af37",
  drik: "#6B5B95",
};

const SUFFICIENT = "#2E9E5B";
const DEFICIENT = "#e34234";

// A ratio bar: fill to ratio (capped at 2.0), with the 1.0 "required" threshold.
const RatioBar = ({ ratio, sufficient }) => {
  const pct = Math.max(2, Math.min(ratio / 2.0, 1) * 100);
  return (
    <div className="st-track" title={`ratio ${ratio}`}>
      <div
        className="st-fill"
        style={{ width: `${pct}%`, background: sufficient ? SUFFICIENT : DEFICIENT }}
      />
      <div className="st-threshold" style={{ left: "50%" }} />
    </div>
  );
};

export const StrengthPage = () => {
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
      const res = await astrologyService.getStrength(birthDetails, ayanamsa);
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("strength.calcError"));
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
      const res = await astrologyService.analyzeStrengthAI(
        birthDetails,
        { personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("strength.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const components = data?.components || [];
  const planets = (data?.planets || []).slice().sort((a, b) => a.rank - b.rank);
  const bhava = data?.bhava_bala || [];
  const vimsopaka = data?.vimsopaka || [];
  const vMax = data?.vimsopaka_max || 20;

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Gauge size={24} />}
        title={t("strength.title")}
        subtitle={t("strength.subtitle")}
        accent="gold"
      />

      <div className="dashboard-content">
        <RecentReadings source="strength" profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />
        <p className="card-note">{t("strength.intro")}</p>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("strength.loading")} />
          </Card>
        ) : data ? (
          <div className="fade-in">
            {/* Shadbala ratio */}
            <Card title={t("strength.shadbalaTitle")} icon={<Gauge size={24} />} accent="saffron">
              <p className="card-intro">{t("strength.shadbalaIntro")}</p>
              <div className="st-rows">
                {planets.map((p) => (
                  <div key={p.planet} className="st-row">
                    <div className="st-row__label">
                      <span className="st-rank">#{p.rank}</span> {p.planet}
                    </div>
                    <RatioBar ratio={p.strength_ratio} sufficient={p.sufficient} />
                    <div className="st-row__val">
                      {p.total_rupa} / {p.required_rupa}
                      <span className="st-ratio"> ×{p.strength_ratio}</span>
                    </div>
                  </div>
                ))}
              </div>
              <p className="card-note">{t("strength.thresholdNote")}</p>
            </Card>

            {/* Six-fold composition */}
            <div className="mt-xl">
              <Card
                title={t("strength.compositionTitle")}
                icon={<Layers size={24} />}
                accent="indigo"
              >
                <p className="card-intro">{t("strength.compositionIntro")}</p>
                <div className="st-legend">
                  {components.map((c) => (
                    <span key={c} className="st-legend__item">
                      <span className="st-swatch" style={{ background: COMPONENT_COLORS[c] }} />
                      {t(`strength.component.${c}`)}
                    </span>
                  ))}
                </div>
                <div className="st-rows">
                  {planets.map((p) => {
                    const total =
                      components.reduce((s, c) => s + (p[c] || 0), 0) || 1;
                    return (
                      <div key={p.planet} className="st-row">
                        <div className="st-row__label">{p.planet}</div>
                        <div className="st-stack">
                          {components.map((c) => {
                            const w = ((p[c] || 0) / total) * 100;
                            if (w <= 0) return null;
                            return (
                              <div
                                key={c}
                                className="st-stack__seg"
                                style={{ width: `${w}%`, background: COMPONENT_COLORS[c] }}
                                title={`${t(`strength.component.${c}`)}: ${p[c]}`}
                              />
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>
            </div>

            {/* Bhava Bala */}
            <div className="mt-xl">
              <Card title={t("strength.bhavaTitle")} icon={<Home size={24} />} accent="terracotta">
                <p className="card-intro">{t("strength.bhavaIntro")}</p>
                <div className="st-rows">
                  {bhava.map((b) => (
                    <div key={b.house} className="st-row">
                      <div className="st-row__label st-row__label--bhava">
                        <span className="st-rank">H{b.house}</span>
                        <span className="st-bhava-sig">{b.signification}</span>
                      </div>
                      <RatioBar ratio={b.strength_ratio} sufficient={b.sufficient} />
                      <div className="st-row__val">
                        {b.rupa}
                        <span className="st-ratio"> ×{b.strength_ratio}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>

            {/* Vimsopaka Bala */}
            <div className="mt-xl">
              <Card
                title={t("strength.vimsopakaTitle")}
                icon={<Layers size={24} />}
                accent="gold"
              >
                <p className="card-intro">{t("strength.vimsopakaIntro")}</p>
                <div className="st-rows">
                  {vimsopaka.map((v) => (
                    <div key={v.planet} className="st-row">
                      <div className="st-row__label">{v.planet}</div>
                      <div className="st-track" title={`${v.shodhasavarga}/${vMax}`}>
                        <div
                          className="st-fill st-fill--vim"
                          style={{ width: `${(v.shodhasavarga / vMax) * 100}%` }}
                        />
                      </div>
                      <div className="st-row__val">
                        {v.shodhasavarga}
                        <span className="st-ratio">/{vMax}</span>
                      </div>
                    </div>
                  ))}
                </div>
                <p className="card-note">{t("strength.vimsopakaNote")}</p>
              </Card>
            </div>

            {/* AI reading */}
            <div className="mt-xl">
              <Card title={t("strength.aiTitle")} icon={<Sparkles size={24} />} accent="gold">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("strength.aiHint")}</p>}
                {aiLoading && <LoadingState message={t("strength.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">{t("strength.aiModel", { model: aiModel })}</div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("strength.aiRegenerate") : t("strength.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("strength.disclaimer")}</p>
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default StrengthPage;
