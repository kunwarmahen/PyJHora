import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Star, Sparkles } from "lucide-react";
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
import { intlLocale } from "../utils/format";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import "../styles/Nakshatra.css";
import { useLocalizeName } from "../i18n/localizeName";

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

const TONE_CLASS = {
  very_good: "nak-tone--vgood",
  good: "nak-tone--good",
  neutral: "nak-tone--neutral",
  caution: "nak-tone--caution",
  bad: "nak-tone--bad",
};

const fmtDay = (dateStr, locale) => {
  try {
    return new Date(`${dateStr}T00:00:00`).toLocaleDateString(locale, {
      day: "numeric",
      month: "short",
    });
  } catch {
    return dateStr;
  }
};

export const NakshatraProfilePage = () => {
  const navigate = useNavigate();
  const ln = useLocalizeName();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
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
      const res = await astrologyService.getNakshatraProfile(birthDetails, null, ayanamsa);
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("nakshatra.calcError"));
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
      const res = await astrologyService.analyzeNakshatraProfileAI(
        birthDetails,
        { personName: birthDetails.name, currentDate: data?.calendar_from },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("nakshatra.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const p = data?.profile || {};
  const attrs = [
    ["attrLord", p.lord],
    ["attrDeity", p.deity],
    ["attrSymbol", p.symbol],
    ["attrGana", p.gana],
    ["attrYoni", p.yoni],
    ["attrNadi", p.nadi],
    ["attrGuna", p.guna],
    ["attrVarna", p.varna],
  ];

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Star size={24} />}
        title={t("nakshatra.title")}
        subtitle={t("nakshatra.subtitle")}
        accent="gold"
      />

      <div className="dashboard-content">
        <RecentReadings source="nakshatra_profile" profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />
        <p className="card-note">{t("nakshatra.intro")}</p>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("nakshatra.loading")} />
          </Card>
        ) : data ? (
          <div className="fade-in">
            {/* Hero */}
            <div className="nak-hero">
              <div className="nak-hero__star">
                <Star size={30} />
              </div>
              <div>
                <div className="nak-hero__name">{p.name}</div>
                <div className="nak-hero__sub">
                  {t("nakshatra.pada", { n: p.pada })} · {t("nakshatra.moonSign", { sign: data.moon_sign })}
                </div>
                <div className="nak-hero__theme">{p.theme}</div>
              </div>
              <div className="nak-hero__syllable" title={t("nakshatra.attrSyllable")}>
                {p.naming_syllable}
              </div>
            </div>

            {/* Attributes */}
            <div className="mt-xl">
              <Card title={p.name} icon={<Star size={22} />} accent="gold">
                <div className="nak-attrs">
                  {attrs.map(([key, val]) => (
                    <div className="nak-attr" key={key}>
                      <span className="nak-attr__label">{t(`nakshatra.${key}`)}</span>
                      <span className="nak-attr__value">{val}</span>
                    </div>
                  ))}
                </div>
                <div className="nak-syllables">
                  <span className="nak-attr__label">{t("nakshatra.syllablesTitle")}</span>
                  <div className="nak-syllables__row">
                    {(p.all_syllables || []).map((s, i) => (
                      <span
                        key={i}
                        className={`nak-syllable${i + 1 === p.pada ? " nak-syllable--active" : ""}`}
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              </Card>
            </div>

            {/* Tarabala calendar */}
            <div className="mt-xl">
              <Card title={t("nakshatra.tarabalaTitle")} icon={<Sparkles size={22} />} accent="saffron">
                <p className="card-intro">{t("nakshatra.tarabalaIntro")}</p>
                <p className="card-note">{t("nakshatra.from", { date: data.calendar_from })}</p>
                <div className="nak-cal">
                  {(data.tarabala_calendar || []).map((c) => (
                    <div
                      key={c.date}
                      className={`nak-cal__cell ${TONE_CLASS[c.tone] || "nak-tone--neutral"}`}
                      title={`${ln(c.nakshatra, "nakshatra")} · ${c.tarabala}`}
                    >
                      <span className="nak-cal__date">{fmtDay(c.date, locale)}</span>
                      <span className="nak-cal__tara">{c.tarabala}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>

            {/* AI reading */}
            <div className="mt-xl">
              <Card title={t("nakshatra.aiTitle")} icon={<Sparkles size={24} />} accent="indigo">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("nakshatra.aiHint")}</p>}
                {aiLoading && <LoadingState message={t("nakshatra.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">{t("nakshatra.aiModel", { model: aiModel })}</div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("nakshatra.aiRegenerate") : t("nakshatra.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("nakshatra.disclaimer")}</p>
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default NakshatraProfilePage;
