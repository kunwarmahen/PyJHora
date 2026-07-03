import React, { useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CalendarCheck, Sparkles, MapPin, Clock, Star, Compass, Moon } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
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

const todayISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const addDaysISO = (iso, days) => {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const ACTIVITIES = ["general", "marriage", "travel", "business", "housewarming", "education", "medical"];

const QUALITY_CLASS = {
  excellent: "muh-q--excellent",
  good: "muh-q--good",
  average: "muh-q--average",
  avoid: "muh-q--avoid",
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

export const MuhurtaPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();

  const [activity, setActivity] = useState("general");
  const [startDate, setStartDate] = useState(todayISO);
  const [endDate, setEndDate] = useState(() => addDaysISO(todayISO(), 14));

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");

  // Day sub-tools (Choghadiya / Panchaka / Tarabala / Chandrabala).
  const [subDate, setSubDate] = useState(todayISO);
  const [subData, setSubData] = useState(null);
  const [subLoading, setSubLoading] = useState(false);
  const [subError, setSubError] = useState("");

  const loc = useMemo(
    () =>
      selectedProfile
        ? {
            place: selectedProfile.birth_details.place,
            latitude: selectedProfile.birth_details.latitude,
            longitude: selectedProfile.birth_details.longitude,
            timezone: selectedProfile.birth_details.timezone,
          }
        : null,
    [selectedProfile]
  );

  const run = useCallback(async () => {
    if (!loc) return;
    setLoading(true);
    setError("");
    setResult(null);
    setAiAnalysis("");
    setAiError("");
    try {
      const res = await astrologyService.getMuhurta({ activity, startDate, endDate, ...loc });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("muhurta.calcError"));
    } finally {
      setLoading(false);
    }
  }, [loc, activity, startDate, endDate, t]);

  const runSubtools = useCallback(async () => {
    if (!loc) return;
    setSubLoading(true);
    setSubError("");
    try {
      const birthDetails = selectedProfile
        ? {
            name: selectedProfile.birth_details.name,
            dob: selectedProfile.birth_details.dob,
            tob: selectedProfile.birth_details.tob,
            place: selectedProfile.birth_details.place,
            latitude: selectedProfile.birth_details.latitude,
            longitude: selectedProfile.birth_details.longitude,
            timezone: selectedProfile.birth_details.timezone,
          }
        : undefined;
      const res = await astrologyService.getMuhurtaSubtools({
        date: subDate,
        ...loc,
        birthDetails,
      });
      setSubData(res.data);
    } catch (err) {
      setSubError(err.response?.data?.detail || t("muhurta.subtools.error"));
    } finally {
      setSubLoading(false);
    }
  }, [loc, subDate, selectedProfile, t]);

  const handleAi = async () => {
    if (!loc) return;
    setAiLoading(true);
    setAiError("");
    try {
      const res = await astrologyService.analyzeMuhurtaAI(
        { activity, startDate, endDate, ...loc },
        readModelConfig()
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("muhurta.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) {
    // Muhurta is location-driven but we key location off the profile's place.
    navigate("/profile-selection");
    return null;
  }

  const windows = result?.best_windows || [];
  const days = result?.days || [];

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<CalendarCheck size={24} />}
        title={t("muhurta.title")}
        subtitle={t("muhurta.subtitle")}
        accent="gold"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        <div className="page-controls">
          <div className="controls-group">
            <label className="control-label">{t("muhurta.activity")}</label>
            <select
              className="control-input"
              value={activity}
              onChange={(e) => setActivity(e.target.value)}
            >
              {ACTIVITIES.map((a) => (
                <option key={a} value={a}>
                  {t(`muhurta.activities.${a}`)}
                </option>
              ))}
            </select>
          </div>
          <div className="controls-group">
            <label className="control-label">{t("muhurta.from")}</label>
            <input
              type="date"
              className="control-input"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
            <label className="control-label">{t("muhurta.to")}</label>
            <input
              type="date"
              className="control-input"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
            <button className="control-btn" onClick={run}>
              <Star size={14} /> {t("muhurta.find")}
            </button>
          </div>
        </div>

        <p className="card-note">
          <MapPin size={13} /> {t("muhurta.locationNote", { place: loc.place || "—" })}
        </p>

        {/* Day sub-tools: Choghadiya / Panchaka / Tarabala / Chandrabala */}
        <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush mt-xl">
          <h3 className="ui-card-header ui-card-header--sm">
            <Compass size={18} /> {t("muhurta.subtools.title")}
          </h3>
          <p className="card-note">{t("muhurta.subtools.intro")}</p>
          <div className="page-controls">
            <div className="controls-group">
              <label className="control-label">{t("muhurta.subtools.date")}</label>
              <input
                type="date"
                className="control-input"
                value={subDate}
                onChange={(e) => setSubDate(e.target.value)}
              />
              <button className="control-btn" onClick={runSubtools} disabled={subLoading}>
                <Star size={14} /> {t("muhurta.subtools.check")}
              </button>
            </div>
          </div>
          <ErrorBanner message={subError} />
          {subLoading && <LoadingState message={t("muhurta.subtools.loading")} />}
          {subData && !subLoading && (
            <div className="fade-in">
              {/* Personal status: Panchaka / Tarabala / Chandrabala */}
              <div className="muh-status-grid">
                <div className="muh-status">
                  <div className="muh-status__label">{t("muhurta.subtools.panchaka")}</div>
                  <div className="muh-status__value">
                    {subData.panchaka?.active
                      ? subData.panchaka?.type
                      : t("muhurta.subtools.panchakaFree")}
                    <span
                      className={`muh-badge muh-badge--${subData.panchaka?.active ? "bad" : "good"}`}
                    >
                      {subData.panchaka?.active ? t("muhurta.subtools.avoid") : t("muhurta.subtools.clear")}
                    </span>
                  </div>
                  <div className="muh-status__note">{subData.panchaka?.meaning}</div>
                </div>

                {subData.tarabala && (
                  <div className="muh-status">
                    <div className="muh-status__label">{t("muhurta.subtools.tarabala")}</div>
                    <div className="muh-status__value">
                      {subData.tarabala.tara}
                      <span className={`muh-badge muh-badge--${subData.tarabala.quality}`}>
                        {t(`muhurta.subtools.quality.${subData.tarabala.quality}`)}
                      </span>
                    </div>
                    <div className="muh-status__note">
                      {t("muhurta.subtools.tarabalaNote", {
                        birth: subData.tarabala.birth_star,
                        today: subData.tarabala.today_star,
                      })}
                    </div>
                  </div>
                )}

                {subData.chandrabala && (
                  <div className="muh-status">
                    <div className="muh-status__label">
                      <Moon size={12} /> {t("muhurta.subtools.chandrabala")}
                    </div>
                    <div className="muh-status__value">
                      {t("muhurta.subtools.house", { n: subData.chandrabala.position })}
                      <span className={`muh-badge muh-badge--${subData.chandrabala.quality}`}>
                        {t(`muhurta.subtools.quality.${subData.chandrabala.quality}`)}
                      </span>
                    </div>
                    <div className="muh-status__note">
                      {t("muhurta.subtools.chandrabalaNote", {
                        birth: subData.chandrabala.birth_moon_sign,
                        transit: subData.chandrabala.transit_moon_sign,
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* Choghadiya day + night */}
              <div className="muh-sub-columns mt-xl">
                {["day", "night"].map((period) => (
                  <div key={period} className="muh-chog-col">
                    <h4>{t(`muhurta.subtools.${period}`)}</h4>
                    <ul className="muh-chog-list">
                      {(subData.choghadiya || [])
                        .filter((c) => c.period === period)
                        .map((c, i) => (
                          <li
                            key={i}
                            className={`muh-chog muh-chog--${c.nature}${c.current ? " muh-chog--current" : ""}`}
                          >
                            <span className="muh-chog__name">
                              {t(`muhurta.subtools.chog.${c.name}`, c.name)}
                            </span>
                            <span className="muh-chog__time">
                              {c.start}–{c.end}
                            </span>
                            {c.current && <span className="muh-chog__now">{t("muhurta.subtools.now")}</span>}
                          </li>
                        ))}
                    </ul>
                  </div>
                ))}
              </div>
              <p className="card-note">{t("muhurta.subtools.note")}</p>
            </div>
          )}
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("muhurta.loading")} />
          </Card>
        ) : result ? (
          <div className="fade-in">
            {/* Best windows */}
            <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush">
              <h3 className="ui-card-header ui-card-header--sm">
                <Clock size={18} /> {t("muhurta.bestWindows", { activity: result.activity_label })}
              </h3>
              {windows.length === 0 ? (
                <p className="card-note">{t("muhurta.noWindows")}</p>
              ) : (
                <ul className="muh-window-list">
                  {windows.map((w, i) => (
                    <li key={i} className="muh-window">
                      <span className="muh-window__date">{formatDate(w.date, locale)}</span>
                      <span className="muh-window__time">
                        {w.start}–{w.end}
                      </span>
                      <span className={`muh-q ${QUALITY_CLASS[w.quality] || ""}`}>{w.label}</span>
                      <span className="muh-window__reason text-secondary">{w.reason}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Day-by-day ratings */}
            <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm">
                <CalendarCheck size={18} /> {t("muhurta.dayRatings")}
              </h3>
              <div className="muh-day-grid">
                {days.map((d) => (
                  <div key={d.date} className={`muh-day ${QUALITY_CLASS[d.rating] || ""}`}>
                    <div className="muh-day__date">{formatDate(d.date, locale)}</div>
                    <div className={`muh-day__rating`}>{t(`muhurta.ratings.${d.rating}`)}</div>
                    <div className="muh-day__limbs text-secondary">
                      {d.nakshatra?.name} · {d.tithi?.name}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* AI rationale */}
            <div className="mt-xl">
              <Card title={t("muhurta.aiTitle")} icon={<Sparkles size={24} />} accent="gold">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("muhurta.aiHint")}</p>}
                {aiLoading && <LoadingState message={t("muhurta.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && <div className="ai-panel__meta">{t("muhurta.aiModel", { model: aiModel })}</div>}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("muhurta.aiRegenerate") : t("muhurta.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("muhurta.disclaimer")}</p>
              </Card>
            </div>
          </div>
        ) : (
          <Card>
            <p className="card-intro">{t("muhurta.intro")}</p>
          </Card>
        )}
      </div>
    </div>
  );
};

export default MuhurtaPage;
