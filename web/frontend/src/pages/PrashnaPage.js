import React, { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { HelpCircle, Sparkles, MapPin, Moon, Sunrise } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { useCurrentLocation } from "../contexts/LocationContext";
import { momentPlace } from "../config/currentLocation";
import { useSettings } from "../contexts/SettingsContext";
import { astrologyService } from "../services/api";
import { useRestoreReading } from "../hooks/useRestoreReading";
import { RecentReadings } from "../components/RecentReadings";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
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

export const PrashnaPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const ln = useLocalizeName();
  const { selectedProfile } = useProfile();
  const { location, loaded: locationLoaded } = useCurrentLocation();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;
  const chartStyle = settings.chartStyle;

  // Prashna is cast for the moment AND the place the querent is standing in, so
  // this resolves the same way every other "here" in the app does: the location
  // they confirmed once, else their birth place. It used to raise a browser GPS
  // prompt mid-cast and silently fall back to the birth place when refused —
  // which is a different chart, not a rounder one, and said so nowhere.
  const loc = useMemo(
    () => (locationLoaded ? momentPlace(location, selectedProfile?.birth_details) : null),
    [locationLoaded, location, selectedProfile]
  );

  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [chart, setChart] = useState(null);
  const [reading, setReading] = useState("");
  const [model, setModel] = useState("");
  // Reopen a saved Prashna reading from History: restore the question + text, and
  // recast the (deterministic) chart from the saved inputs so the reading — which
  // renders next to the chart — is visible. No AI re-generation.
  const [pendingReading, setPendingReading] = useState(null);
  useRestoreReading((r) => {
    if (r.context?.question) setQuestion(r.context.question);
    setPendingReading({ reading: r.reading, model: r.model, context: r.context });
  });
  useEffect(() => {
    if (pendingReading && !loading) {
      const c = pendingReading.context || {};
      setReading(pendingReading.reading);
      setModel(pendingReading.model);
      astrologyService
        .getPrashna({
          question: c.question,
          date: c.date,
          time: c.time,
          place: c.place,
          latitude: c.latitude,
          longitude: c.longitude,
          timezone: c.timezone,
          ayanamsa: c.ayanamsa,
        })
        .then((res) => setChart(res.data))
        .catch(() => {});
      setPendingReading(null);
    }
  }, [pendingReading, loading]);

  if (!selectedProfile) {
    navigate("/profile-selection");
    return null;
  }

  const cast = async () => {
    if (!loc) return;
    setLoading(true);
    setError("");
    setChart(null);
    setReading("");
    try {
      const res = await astrologyService.analyzePrashnaAI(
        { question, place: loc.place, latitude: loc.latitude,
          longitude: loc.longitude, timezone: loc.timezone },
        { ...readModelConfig(), ayanamsa }
      );
      setChart(res.data.chart || null);
      setReading(res.data.reading || "");
      setModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setError(err.response?.data?.detail || t("prashna.error"));
    } finally {
      setLoading(false);
    }
  };

  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;
  const moment = chart?.moment;
  const moon = chart?.moon || {};
  const lagna = chart?.lagna || {};

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<HelpCircle size={24} />}
        title={t("prashna.title")}
        subtitle={t("prashna.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />
        <RecentReadings source="prashna" />

        <Card>
          <p className="card-intro">{t("prashna.intro")}</p>
          <div className="prashna-composer">
            <textarea
              className="control-input prashna-question"
              rows={2}
              placeholder={t("prashna.placeholder")}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <button className="ui-btn ui-btn--ai" onClick={cast} disabled={loading}>
              <Sparkles size={18} /> {t("prashna.cast")}
            </button>
          </div>
          {/* Name the place rather than describing the mechanism: the old copy
              promised "your current location (with your permission)", which was
              a browser GPS prompt that no longer happens and never said where
              the chart actually landed when it was refused. */}
          <p className="card-note">
            <MapPin size={13} />{" "}
            {loc
              ? t(loc.source === "birth" ? "prashna.locationNoteBirth" : "prashna.locationNoteAt", {
                  place: loc.place,
                })
              : t("prashna.locationNote")}
          </p>
        </Card>

        <ErrorBanner message={error} />

        {loading && (
          <Card>
            <LoadingState message={t("prashna.casting")} />
          </Card>
        )}

        {chart && !loading && (
          <div className="fade-in mt-xl">
            {moment && (
              <div className="info-pills" style={{ marginBottom: "1rem" }}>
                <span className="info-pill">
                  {moment.date} {moment.time}
                </span>
                <span className="info-pill">
                  <Sunrise size={14} style={{ color: "var(--saffron)" }} /> {t("prashna.lagna")}:{" "}
                  {ln(lagna.sign_name, "rasi")}
                </span>
                <span className="info-pill">
                  <Moon size={14} style={{ color: "var(--cosmic-indigo)" }} /> {t("prashna.moon")}:{" "}
                  {ln(moon.sign_name, "rasi")} ({ln(moon.nakshatra, "nakshatra")})
                </span>
                {chart.hora_lord && (
                  <span className="info-pill">{t("prashna.hora", { lord: chart.hora_lord })}</span>
                )}
              </div>
            )}

            <div className="chart-grid">
              <Kundali
                planets={chart.planets || {}}
                lagna={chart.lagna}
                title={t("prashna.chartTitle")}
                subtitle={moment ? `${moment.date} ${moment.time}` : ""}
                exportable
              />

              <Card title={t("prashna.readingTitle")} icon={<Sparkles size={22} />} accent="indigo">
                {reading ? (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{reading}</ReactMarkdown>
                    {model && (
                      <div className="ai-panel__meta">{t("prashna.aiModel", { model })}</div>
                    )}
                  </div>
                ) : (
                  <p className="ai-panel__hint">{t("prashna.noReading")}</p>
                )}
                <p className="card-note">{t("prashna.disclaimer")}</p>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PrashnaPage;
