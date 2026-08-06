import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Bird, Sparkles, Sun, Moon, ThumbsUp, ThumbsDown, MapPin } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { useRestoreReading } from "../hooks/useRestoreReading";
import { RecentReadings } from "../components/RecentReadings";
import { intlLocale, todayISO } from "../utils/format";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { useSettings } from "../contexts/SettingsContext";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

// This page got the local-calendar date right on its own; it now shares the
// helper so there is one place to be right.
const todayLocal = todayISO;

// Read the model the user already picked in "Ask Astrologer".
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

const formatDate = (dateStr, locale = "en-US") => {
  if (!dateStr) return "—";
  try {
    return new Date(`${dateStr}T00:00:00`).toLocaleDateString(locale, {
      weekday: "long",
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch (e) {
    return dateStr;
  }
};

export const PanchaPakshiPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [date, setDate] = useState(todayLocal);

  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");
  // Reopen a saved reading from History (restore the date + saved text).
  const [pendingReading, setPendingReading] = useState(null);
  useRestoreReading((r) => {
    if (r.context?.date) setDate(r.context.date);
    setPendingReading({ reading: r.reading, model: r.model });
  });
  useEffect(() => {
    if (pendingReading && !loading) {
      setAiAnalysis(pendingReading.reading);
      setAiModel(pendingReading.model);
      setPendingReading(null);
    }
  }, [pendingReading, loading]);

  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;

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
    setAiModel("");
    try {
      const res = await astrologyService.getPanchaPakshi(birthDetails, date);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("panchaPakshi.calcError"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, date, t]);

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
      const res = await astrologyService.analyzePanchaPakshiAI(
        birthDetails,
        { date, personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("panchaPakshi.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const bird = result?.birth_bird || {};
  const segments = result?.segments || [];
  const best = result?.best_times || [];
  const avoid = result?.avoid_times || [];

  const TimeWindow = ({ w }) => (
    <li className={`pp-window${w.running ? " is-running" : ""}`}>
      <span className="pp-window__time">
        {w.start}–{w.end}
      </span>
      <span className={`pp-eff pp-eff-${w.effect_score}`}>{w.effect}</span>
      <span className="pp-window__act text-secondary">
        {w.main_activity} / {w.sub_activity}
      </span>
    </li>
  );

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Bird size={24} />}
        title={t("panchaPakshi.title")}
        subtitle={t("panchaPakshi.subtitle")}
        accent="terracotta"
      />

      <div className="dashboard-content">
        <RecentReadings source="panchapakshi" profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />

        {/* Controls */}
        <div className="page-controls">
          <div className="controls-group">
            <label className="control-label">{t("panchaPakshi.date")}</label>
            <input
              type="date"
              className="control-input"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
            <button className="control-btn" onClick={() => setDate(todayLocal())}>
              {t("panchaPakshi.today")}
            </button>
          </div>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("panchaPakshi.loading")} />
          </Card>
        ) : result ? (
          <div className="fade-in">
            {/* Birth-bird badge */}
            <div className="pp-bird-card ui-card ui-card--accent ui-card--pad-lg">
              <div className="pp-bird-badge">
                <Bird size={40} />
              </div>
              <div>
                <div className="pp-bird-name">{bird.name}</div>
                <div className="text-secondary">
                  {t("panchaPakshi.birthBirdOf", {
                    star: bird.star_name,
                    paksha: bird.paksha,
                  })}
                </div>
                <div className="info-pills" style={{ marginTop: "0.6rem" }}>
                  <span className="info-pill">{formatDate(result.date, locale)}</span>
                  <span className="info-pill">
                    <Sun size={14} style={{ color: "var(--saffron)" }} /> {result.sunrise}
                  </span>
                  <span className="info-pill">
                    <Moon size={14} style={{ color: "var(--cosmic-indigo)" }} /> {result.sunset}
                  </span>
                  <span className="info-pill">{result.paksha} paksha</span>
                  {/* Every window below is on this place's wall clock. Naming it
                      is the difference between a usable timing and a number. */}
                  {result.place && (
                    <span className="info-pill">
                      <MapPin size={14} style={{ color: "var(--cosmic-indigo)" }} />{" "}
                      {result.place}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Best / avoid summary */}
            <div className="chart-grid mt-xl">
              <div className="ui-card ui-card--pad-lg ui-card--flush pp-summary pp-summary--good">
                <h3 className="ui-card-header ui-card-header--sm">
                  <ThumbsUp size={18} />
                  {t("panchaPakshi.bestTimes")}
                </h3>
                <ul className="pp-window-list">
                  {best.map((w, i) => (
                    <TimeWindow key={i} w={w} />
                  ))}
                </ul>
              </div>
              <div className="ui-card ui-card--pad-lg ui-card--flush pp-summary pp-summary--bad">
                <h3 className="ui-card-header ui-card-header--sm">
                  <ThumbsDown size={18} />
                  {t("panchaPakshi.avoidTimes")}
                </h3>
                <ul className="pp-window-list">
                  {avoid.map((w, i) => (
                    <TimeWindow key={i} w={w} />
                  ))}
                </ul>
              </div>
            </div>

            {/* Day timeline */}
            <div className="ui-card ui-card--accent-indigo ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm" style={{ fontSize: "1.25rem" }}>
                <Bird size={20} />
                {t("panchaPakshi.timeline")}
              </h3>
              <p className="card-intro">{t("panchaPakshi.timelineIntro")}</p>
              <div className="pp-timeline">
                {segments.map((seg, i) => (
                  <div key={i} className={`pp-segment pp-segment--${seg.phase}`}>
                    <div className="pp-segment__head">
                      {seg.phase === "day" ? (
                        <Sun size={16} style={{ color: "var(--saffron)" }} />
                      ) : (
                        <Moon size={16} style={{ color: "var(--cosmic-indigo)" }} />
                      )}
                      <span className="pp-segment__time">
                        {seg.start}–{seg.end}
                      </span>
                      <span className="pp-segment__bird">
                        {seg.main_bird} · {seg.main_activity}
                      </span>
                    </div>
                    <div className="pp-segment__subs">
                      {seg.sub.map((s, j) => (
                        <div
                          key={j}
                          className={`pp-sub pp-eff-bg-${s.effect_score}${
                            s.running ? " is-running" : ""
                          }`}
                          title={`${s.start}–${s.end} · ${s.sub_bird} ${s.sub_activity} · ${s.effect}`}
                        >
                          <span className="pp-sub__time">{s.start}</span>
                          <span className="pp-sub__act">{s.sub_activity}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <div className="pp-legend">
                {[
                  ["pp-eff-bg-4", t("panchaPakshi.effVeryGood")],
                  ["pp-eff-bg-3", t("panchaPakshi.effGood")],
                  ["pp-eff-bg-2", t("panchaPakshi.effAverage")],
                  ["pp-eff-bg-1", t("panchaPakshi.effBad")],
                  ["pp-eff-bg-0", t("panchaPakshi.effVeryBad")],
                ].map(([cls, label]) => (
                  <span key={cls} className="pp-legend__item">
                    <span className={`pp-legend__swatch ${cls}`} />
                    {label}
                  </span>
                ))}
              </div>
            </div>

            {/* AI reading */}
            <div className="mt-xl">
              <Card
                title={t("panchaPakshi.aiTitle")}
                icon={<Sparkles size={24} />}
                accent="terracotta"
              >
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && (
                  <p className="ai-panel__hint">{t("panchaPakshi.aiHint")}</p>
                )}
                {aiLoading && <LoadingState message={t("panchaPakshi.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">
                        {t("panchaPakshi.aiModel", { model: aiModel })}
                      </div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("panchaPakshi.aiRegenerate") : t("panchaPakshi.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("panchaPakshi.disclaimer")}</p>
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};
