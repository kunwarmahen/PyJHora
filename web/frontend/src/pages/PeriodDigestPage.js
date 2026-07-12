import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CalendarDays, CalendarRange, Sparkles, Bell, Clock, Orbit, Star, Compass } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { useSettings } from "../contexts/SettingsContext";
import { astrologyService } from "../services/api";
import { useRestoreReading } from "../hooks/useRestoreReading";
import { RecentReadings } from "../components/RecentReadings";
import { intlLocale } from "../utils/format";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
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

const todayStr = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const formatDate = (dateStr, locale = "en-US") => {
  if (!dateStr) return "—";
  try {
    return new Date(`${dateStr}T00:00:00`).toLocaleDateString(locale, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
};

// One page, two cadences. `period` is "weekly" or "monthly"; everything below
// (compute call, source tag, copy, and whether the Maasa Pravesha card shows)
// keys off it, so the weekly and monthly pages stay in lockstep.
const PeriodDigestPage = ({ period }) => {
  const isMonth = period === "monthly";
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;
  const source = isMonth ? "monthly_digest" : "weekly_digest";

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [digest, setDigest] = useState(null);

  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");
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
      const opts = { date: todayStr(), ayanamsa };
      const res = isMonth
        ? await astrologyService.getMonthlyDigest(birthDetails, opts)
        : await astrologyService.getWeeklyDigest(birthDetails, opts);
      setDigest(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("periodDigest.error"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, ayanamsa, isMonth, t]);

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
      const res = await astrologyService.analyzePeriodDigestAI(
        period === "monthly" ? "monthly" : "weekly",
        birthDetails,
        { date: todayStr(), personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("periodDigest.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const panch = digest?.panchanga;
  const dasha = digest?.dasha;
  const transits = digest?.transits;
  const events = digest?.events || [];
  const highlights = digest?.highlights || [];
  const pravesh = digest?.pravesh;

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={isMonth ? <CalendarRange size={24} /> : <CalendarDays size={24} />}
        title={t(isMonth ? "periodDigest.monthTitle" : "periodDigest.weekTitle")}
        subtitle={t(isMonth ? "periodDigest.monthSubtitle" : "periodDigest.weekSubtitle")}
        accent="saffron"
      />

      <div className="dashboard-content">
        <RecentReadings source={source} profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />

        <div className="page-controls">
          <div className="controls-group">
            <span className="control-label">
              {formatDate(digest?.start_date, locale)} → {formatDate(digest?.end_date, locale)}
              {digest?.span_days ? ` · ${t("periodDigest.spanDays", { count: digest.span_days })}` : ""}
            </span>
            <button className="control-btn" onClick={load}>
              {t("periodDigest.refresh")}
            </button>
            <button className="control-btn" onClick={() => navigate("/settings")}>
              <Bell size={14} /> {t("periodDigest.notifySettings")}
            </button>
          </div>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t(isMonth ? "periodDigest.loadingMonth" : "periodDigest.loadingWeek")} />
          </Card>
        ) : digest ? (
          <div className="fade-in">
            {/* Highlights */}
            <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush">
              <h3 className="ui-card-header ui-card-header--sm">
                <Star size={18} /> {t("periodDigest.highlights")}
              </h3>
              <ul className="digest-highlights">
                {highlights.map((h, i) => (
                  <li key={i} className={h.startsWith("⚠") ? "digest-hl digest-hl--warn" : "digest-hl"}>
                    {h}
                  </li>
                ))}
              </ul>
            </div>

            <div className="chart-grid mt-xl">
              {/* Opening panchanga */}
              {panch && (
                <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush">
                  <h3 className="ui-card-header ui-card-header--sm">
                    <CalendarDays size={18} /> {t("periodDigest.panchanga")}
                  </h3>
                  <div className="detail-list digest-details">
                    <div><span className="kv-label">{t("periodDigest.tithi")}</span><span className="kv-value">{panch.tithi?.name}</span></div>
                    <div><span className="kv-label">{t("periodDigest.nakshatra")}</span><span className="kv-value">{panch.nakshatra?.name}</span></div>
                    <div><span className="kv-label">{t("periodDigest.vaara")}</span><span className="kv-value">{panch.vaara?.name}</span></div>
                  </div>
                </div>
              )}

              {/* Dasha snapshot */}
              {dasha && (
                <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush">
                  <h3 className="ui-card-header ui-card-header--sm">
                    <Clock size={18} /> {t("periodDigest.dasha")}
                  </h3>
                  <div className="detail-list digest-details">
                    <div><span className="kv-label">{t("periodDigest.mahadasha")}</span><span className="kv-value">{dasha.maha_lord}</span></div>
                    {dasha.bhukti && (
                      <div><span className="kv-label">{t("periodDigest.bhukti")}</span><span className="kv-value">{dasha.bhukti.lord} → {dasha.bhukti.end_date}</span></div>
                    )}
                    {dasha.next_maha && (
                      <div><span className="kv-label">{t("periodDigest.nextMaha")}</span><span className="kv-value">{dasha.next_maha}</span></div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Maasa Pravesha (monthly only) */}
            {isMonth && pravesh && (
              <div className="ui-card ui-card--accent-gold ui-card--pad-lg ui-card--flush mt-xl">
                <h3 className="ui-card-header ui-card-header--sm">
                  <Compass size={18} /> {t("periodDigest.pravesh")}
                </h3>
                <div className="detail-list digest-details">
                  <div><span className="kv-label">{t("periodDigest.praveshLagna")}</span><span className="kv-value">{pravesh.lagna?.sign_name}</span></div>
                  <div>
                    <span className="kv-label">{t("periodDigest.muntha")}</span>
                    <span className="kv-value">
                      {pravesh.muntha?.sign_name} · {t("periodDigest.house", { n: pravesh.muntha?.house })}
                    </span>
                  </div>
                  {pravesh.year_lord && (
                    <div><span className="kv-label">{t("periodDigest.yearLord")}</span><span className="kv-value">{pravesh.year_lord.planet}</span></div>
                  )}
                </div>
                {pravesh.tajaka_yogas?.length > 0 && (
                  <>
                    <p className="kv-label mt-md">{t("periodDigest.tajakaYogas")}</p>
                    <ul className="digest-highlights">
                      {pravesh.tajaka_yogas.map((y, i) => (
                        <li key={i} className="digest-hl">
                          <strong>{y.name}</strong>
                          {y.pair ? ` (${y.pair.join(" / ")})` : ""}
                          {y.description ? ` — ${y.description}` : ""}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}

            {/* Transit events in the window */}
            <div className="ui-card ui-card--accent-gold ui-card--pad-lg ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm">
                <Orbit size={18} /> {t("periodDigest.events")}
              </h3>
              {transits?.sade_sati && <p className="digest-hl digest-hl--warn">{t("periodDigest.sadeSati")}</p>}
              {transits?.retrograde?.length > 0 && (
                <p className="digest-retro">
                  <span className="kv-label">{t("periodDigest.retrograde")}:</span>{" "}
                  {transits.retrograde.join(", ")}
                </p>
              )}
              {events.length > 0 ? (
                <ul className="detail-list digest-details">
                  {events.map((e, i) => (
                    <li key={i}>
                      <span className="kv-label">{e.planet}</span>
                      <span className="kv-value">
                        {e.text} · {e.date}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="ai-panel__hint">{t("periodDigest.noEvents")}</p>
              )}
            </div>

            {/* AI reading */}
            <div className="mt-xl">
              <Card
                title={t(isMonth ? "periodDigest.aiTitleMonth" : "periodDigest.aiTitleWeek")}
                icon={<Sparkles size={24} />}
                accent="saffron"
              >
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && (
                  <p className="ai-panel__hint">{t(isMonth ? "periodDigest.aiHintMonth" : "periodDigest.aiHintWeek")}</p>
                )}
                {aiLoading && <LoadingState message={t("periodDigest.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && <div className="ai-panel__meta">{t("periodDigest.aiModel", { model: aiModel })}</div>}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis
                      ? t("periodDigest.aiRegenerate")
                      : t(isMonth ? "periodDigest.aiGenerateMonth" : "periodDigest.aiGenerateWeek")}
                  </button>
                )}
                <p className="card-note">{t("periodDigest.disclaimer")}</p>
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export const WeeklyDigestPage = () => <PeriodDigestPage period="weekly" />;
export const MonthlyDigestPage = () => <PeriodDigestPage period="monthly" />;

export default PeriodDigestPage;
