import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Aperture, Sparkles, CheckCircle2, AlertTriangle } from "lucide-react";
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
import "../styles/SadeSati.css";
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

const PHASE_COLORS = { rising: "#F0B860", peak: "#B23A48", setting: "#C97B54" };
const ms = (d) => new Date(`${d}T00:00:00`).getTime();

const fmt = (dateStr, locale) => {
  if (!dateStr) return "—";
  try {
    return new Date(`${dateStr}T00:00:00`).toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
    });
  } catch {
    return dateStr;
  }
};

export const SadeSatiPage = () => {
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
      const res = await astrologyService.getSaturnTransits(birthDetails, ayanamsa);
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("sadeSati.calcError"));
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
      const res = await astrologyService.analyzeSaturnTransitsAI(
        birthDetails,
        { personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("sadeSati.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const cur = data?.current || {};
  const periods = data?.sade_sati_periods || [];
  const ashtama = data?.ashtama_periods || [];
  const kantaka = data?.kantaka_periods || [];

  // Current-status banner: which Saturn transit (if any) is running.
  const status = !data
    ? null
    : cur.sade_sati
      ? {
          tone: "active",
          text: t("sadeSati.statusSadeSati", {
            phase: t(`sadeSati.phase.${cur.sade_sati.current_phase}`),
            end: fmt(cur.sade_sati.end_date, locale),
          }),
        }
      : cur.ashtama
        ? {
            tone: "warn",
            text: t("sadeSati.statusAshtama", { end: fmt(cur.ashtama.end_date, locale) }),
          }
        : cur.kantaka
          ? {
              tone: "warn",
              text: t("sadeSati.statusKantaka", { end: fmt(cur.kantaka.end_date, locale) }),
            }
          : { tone: "clear", text: t("sadeSati.statusClear") };

  // A phase bar within a cycle, proportional to its span.
  const PhaseBar = ({ cycle }) => {
    const start = ms(cycle.start_date);
    const end = ms(cycle.end_date);
    const span = end - start || 1;
    return (
      <div className="ss-bar">
        {cycle.phases.map((ph) => {
          const left = ((ms(ph.start_date) - start) / span) * 100;
          const width = ((ms(ph.end_date) - ms(ph.start_date)) / span) * 100;
          return (
            <div
              key={ph.phase}
              className="ss-bar__seg"
              style={{
                left: `${left}%`,
                width: `${width}%`,
                background: PHASE_COLORS[ph.phase],
              }}
              title={`${t(`sadeSati.phase.${ph.phase}`)} · ${ln(ph.sign_name, "rasi")}`}
            />
          );
        })}
      </div>
    );
  };

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Aperture size={24} />}
        title={t("sadeSati.title")}
        subtitle={t("sadeSati.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <RecentReadings source="saturn_transits" profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />
        <p className="card-note">{t("sadeSati.intro")}</p>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("sadeSati.loading")} />
          </Card>
        ) : data ? (
          <div className="fade-in">
            {/* Current status banner */}
            {status && (
              <div className={`ss-status ss-status--${status.tone}`}>
                {status.tone === "clear" ? <CheckCircle2 size={20} /> : <AlertTriangle size={20} />}
                <span>{status.text}</span>
              </div>
            )}

            <div className="info-pills">
              <span className="info-pill">{t("sadeSati.moonSign", { sign: data.moon_sign })}</span>
            </div>

            {/* Sade Sati cycles */}
            <div className="ss-cycles">
              {periods.map((c, i) => (
                <div
                  key={i}
                  className={`ss-cycle${c.is_current ? " ss-cycle--current" : ""}${
                    c.is_past ? " ss-cycle--past" : ""
                  }`}
                >
                  <div className="ss-cycle__head">
                    <span className="ss-cycle__range">
                      {fmt(c.start_date, locale)} – {fmt(c.end_date, locale)}
                    </span>
                    <span className="ss-cycle__tag">
                      {c.is_current
                        ? t("sadeSati.current")
                        : c.is_past
                          ? t("sadeSati.past")
                          : t("sadeSati.upcoming")}
                    </span>
                  </div>
                  <PhaseBar cycle={c} />
                  <div className="ss-phases">
                    {c.phases.map((ph) => (
                      <div
                        key={ph.phase}
                        className={`ss-phase${
                          c.is_current && c.current_phase === ph.phase ? " ss-phase--now" : ""
                        }`}
                      >
                        <span
                          className="ss-phase__dot"
                          style={{ background: PHASE_COLORS[ph.phase] }}
                        />
                        <span className="ss-phase__name">{t(`sadeSati.phase.${ph.phase}`)}</span>
                        <span className="ss-phase__sign">{ln(ph.sign_name, "rasi")}</span>
                        <span className="ss-phase__dates">
                          {fmt(ph.start_date, locale)} – {fmt(ph.end_date, locale)}
                        </span>
                        {ph.retrograde_reentry && (
                          <span className="ss-phase__retro" title={t("sadeSati.retroHint")}>
                            ℞
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              {periods.length === 0 && <p className="card-note">{t("sadeSati.noSadeSati")}</p>}
            </div>

            {/* Ashtama + Kantaka */}
            <div className="mt-xl">
              <Card
                title={t("sadeSati.otherTitle")}
                icon={<Aperture size={24} />}
                accent="terracotta"
              >
                <p className="card-intro">{t("sadeSati.otherIntro")}</p>
                <div className="ss-other-grid">
                  <div>
                    <h4 className="ss-other-h">{t("sadeSati.ashtama")}</h4>
                    {ashtama.map((a, i) => (
                      <div
                        key={i}
                        className={`ss-other-row${a.is_current ? " is-current" : ""}${
                          a.is_past ? " is-past" : ""
                        }`}
                      >
                        {fmt(a.start_date, locale)} – {fmt(a.end_date, locale)}
                        {a.is_current && <span className="ss-now-tag">{t("sadeSati.now")}</span>}
                      </div>
                    ))}
                  </div>
                  <div>
                    <h4 className="ss-other-h">{t("sadeSati.kantaka")}</h4>
                    {kantaka.map((k, i) => (
                      <div
                        key={i}
                        className={`ss-other-row${k.is_current ? " is-current" : ""}${
                          k.is_past ? " is-past" : ""
                        }`}
                      >
                        {fmt(k.start_date, locale)} – {fmt(k.end_date, locale)}
                        {k.is_current && <span className="ss-now-tag">{t("sadeSati.now")}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              </Card>
            </div>

            {/* AI reading */}
            <div className="mt-xl">
              <Card title={t("sadeSati.aiTitle")} icon={<Sparkles size={24} />} accent="indigo">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && (
                  <p className="ai-panel__hint">{t("sadeSati.aiHint")}</p>
                )}
                {aiLoading && <LoadingState message={t("sadeSati.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">
                        {t("sadeSati.aiModel", { model: aiModel })}
                      </div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("sadeSati.aiRegenerate") : t("sadeSati.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("sadeSati.disclaimer")}</p>
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default SadeSatiPage;
