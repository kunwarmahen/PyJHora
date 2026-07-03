import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { HelpCircle, Sparkles, MapPin, Moon, Sunrise } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { useSettings } from "../contexts/SettingsContext";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
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

export const PrashnaPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;
  const chartStyle = settings.chartStyle;

  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [chart, setChart] = useState(null);
  const [reading, setReading] = useState("");
  const [model, setModel] = useState("");

  if (!selectedProfile) {
    navigate("/profile-selection");
    return null;
  }

  // Prashna is cast for the moment + current location. We use the querent's
  // browser geolocation when granted, else fall back to the profile's place.
  const getLocation = () =>
    new Promise((resolve) => {
      const fallback = {
        place: selectedProfile.birth_details.place,
        latitude: selectedProfile.birth_details.latitude,
        longitude: selectedProfile.birth_details.longitude,
        timezone: selectedProfile.birth_details.timezone,
      };
      if (!navigator.geolocation) return resolve(fallback);
      navigator.geolocation.getCurrentPosition(
        (pos) =>
          resolve({
            place: t("prashna.currentLocation"),
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
            timezone: -new Date().getTimezoneOffset() / 60,
          }),
        () => resolve(fallback),
        { timeout: 6000 }
      );
    });

  const cast = async () => {
    setLoading(true);
    setError("");
    setChart(null);
    setReading("");
    try {
      const loc = await getLocation();
      const res = await astrologyService.analyzePrashnaAI(
        { question, ...loc },
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
          <p className="card-note">
            <MapPin size={13} /> {t("prashna.locationNote")}
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
                  {lagna.sign_name}
                </span>
                <span className="info-pill">
                  <Moon size={14} style={{ color: "var(--cosmic-indigo)" }} /> {t("prashna.moon")}:{" "}
                  {moon.sign_name} ({moon.nakshatra})
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
                    {model && <div className="ai-panel__meta">{t("prashna.aiModel", { model })}</div>}
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
