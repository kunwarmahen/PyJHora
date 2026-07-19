import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Waypoints, Sparkles, Compass, TrendingUp } from "lucide-react";
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

const formatDate = (dateStr, locale = "en-US") => {
  if (!dateStr) return "—";
  try {
    return new Date(`${dateStr}T00:00:00`).toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
};

export const BhriguMarkersPage = () => {
  const navigate = useNavigate();
  const ln = useLocalizeName();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;

  const [years, setYears] = useState(12);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  // Reopen a saved reading from History (restore the horizon + saved text).
  const [pendingReading, setPendingReading] = useState(null);
  useRestoreReading((r) => {
    if (r.context?.years != null) setYears(r.context.years);
    setPendingReading({ reading: r.reading, model: r.model });
  });
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
      const res = await astrologyService.getBhriguMarkers(birthDetails, { years, ayanamsa });
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("bhrigu.calcError"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, years, ayanamsa, t]);

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
      const res = await astrologyService.analyzeBhriguMarkersAI(
        birthDetails,
        { years, personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("bhrigu.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const bb = data?.bhrigu_bindu;
  const progression = data?.progression || [];
  const activations = data?.activations || [];

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Waypoints size={24} />}
        title={t("bhrigu.title")}
        subtitle={t("bhrigu.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <RecentReadings source="bhrigu" profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />

        <p className="card-note">{t("bhrigu.intro")}</p>

        <div className="page-controls">
          <div className="controls-group">
            <label className="control-label">{t("bhrigu.horizon")}</label>
            <select
              className="control-input"
              value={years}
              onChange={(e) => setYears(parseInt(e.target.value, 10))}
            >
              {[8, 12, 20, 30].map((y) => (
                <option key={y} value={y}>
                  {t("bhrigu.yearsOption", { count: y })}
                </option>
              ))}
            </select>
          </div>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("bhrigu.loading")} />
          </Card>
        ) : data ? (
          <div className="fade-in">
            {/* Bhrigu Bindu summary */}
            {bb && (
              <div className="info-pills">
                <span className="info-pill">
                  <Compass size={14} />{" "}
                  {t("bhrigu.bbSign", { sign: ln(bb.sign_name, "rasi"), deg: bb.degrees })}
                </span>
                <span className="info-pill">{t("bhrigu.bbHouse", { n: bb.house_from_lagna })}</span>
                <span className="info-pill">{t("bhrigu.moonSign", { sign: data.moon_sign })}</span>
                <span className="info-pill">{t("bhrigu.ageNow", { age: data.age_now })}</span>
              </div>
            )}

            {/* Annual progression */}
            <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm">
                <TrendingUp size={18} /> {t("bhrigu.progressionTitle")}
              </h3>
              <p className="card-note">{t("bhrigu.progressionIntro")}</p>
              <div className="bhrigu-prog-grid">
                {progression.map((p) => (
                  <div
                    key={p.age}
                    className={`bhrigu-prog${p.is_bhrigu_bindu ? " bhrigu-prog--bb" : ""}${
                      p.is_moon_sign ? " bhrigu-prog--moon" : ""
                    }${p.planets.length ? " bhrigu-prog--active" : ""}`}
                  >
                    <div className="bhrigu-prog__year">
                      {p.year}{" "}
                      <span className="text-secondary">· {t("bhrigu.age", { n: p.age })}</span>
                    </div>
                    <div className="bhrigu-prog__sign">
                      {ln(p.sign_name, "rasi")}{" "}
                      <span className="text-secondary">({ln(p.sign_lord, "graha")})</span>
                    </div>
                    <div className="bhrigu-prog__planets">
                      {p.planets.length ? p.planets.join(", ") : t("bhrigu.emptySign")}
                    </div>
                    {(p.is_bhrigu_bindu || p.is_moon_sign) && (
                      <div className="bhrigu-prog__tag">
                        {p.is_bhrigu_bindu ? t("bhrigu.bbTag") : t("bhrigu.moonTag")}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Activations */}
            <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm">
                <Sparkles size={18} /> {t("bhrigu.activationsTitle")}
              </h3>
              <p className="card-note">{t("bhrigu.activationsIntro")}</p>
              {activations.length === 0 ? (
                <p className="card-note">{t("bhrigu.noActivations")}</p>
              ) : (
                <ul className="bhrigu-activation-list">
                  {activations.map((a, i) => (
                    <li key={i} className="bhrigu-activation">
                      <span className="bhrigu-activation__date">{formatDate(a.date, locale)}</span>
                      <span className="bhrigu-activation__text">
                        {t("bhrigu.activationRow", {
                          planet: a.planet,
                          sign: ln(a.sign_name, "rasi"),
                          target: a.target,
                        })}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* AI reading */}
            <div className="mt-xl">
              <Card title={t("bhrigu.aiTitle")} icon={<Sparkles size={24} />} accent="indigo">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && (
                  <p className="ai-panel__hint">{t("bhrigu.aiHint")}</p>
                )}
                {aiLoading && <LoadingState message={t("bhrigu.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">
                        {t("bhrigu.aiModel", { model: aiModel })}
                      </div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("bhrigu.aiRegenerate") : t("bhrigu.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("bhrigu.disclaimer")}</p>
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default BhriguMarkersPage;
