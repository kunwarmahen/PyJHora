import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Globe, Sparkles, RefreshCw, MapPin } from "lucide-react";
import { Link } from "react-router-dom";
import Markdown from "../components/Markdown";
import { useProfile } from "../contexts/ProfileContext";
import { useCurrentLocation } from "../contexts/LocationContext";
import { momentPlace } from "../config/currentLocation";
import { astrologyService } from "../services/api";
import { useRestoreReading } from "../hooks/useRestoreReading";
import { RecentReadings } from "../components/RecentReadings";
import { PageHeader } from "../components/PageHeader";
import { Card } from "../components/Card";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { useSettings } from "../contexts/SettingsContext";
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

export const NowChartPage = () => {
  const { t } = useTranslation();
  const ln = useLocalizeName();
  const { selectedProfile } = useProfile();
  const { location, loaded: locationLoaded } = useCurrentLocation();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;
  const chartStyle = settings.chartStyle;
  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Where "here" is. Resolved from the location the user confirmed once, else
  // their birth place — never from a GPS prompt raised on arrival, and never
  // from the backend's hardcoded Chennai default, which this page used to reach
  // by passing no coordinates at all. See config/currentLocation#momentPlace.
  // Null until the stored location has been fetched: "not loaded yet" looks
  // like "there is none", and casting on that difference showed the birth-place
  // chart for a beat before replacing it with the right one.
  const loc = useMemo(
    () => (locationLoaded ? momentPlace(location, selectedProfile?.birth_details) : null),
    [locationLoaded, location, selectedProfile]
  );

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

  const load = useCallback(async () => {
    if (!loc) {
      // Nothing to cast for. Waiting on the location fetch is not the same as
      // knowing there is none, so only the latter stops the spinner.
      setData(null);
      setLoading(!locationLoaded);
      return;
    }
    setLoading(true);
    setError("");
    setAiAnalysis("");
    try {
      const res = await astrologyService.getNowChart({
        place: loc.place,
        latitude: loc.latitude,
        longitude: loc.longitude,
        timezone: loc.timezone,
        currentTz: loc.timezone,
        ayanamsa,
      });
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("now.calcError"));
    } finally {
      setLoading(false);
    }
  }, [loc, locationLoaded, ayanamsa, t]);

  useEffect(() => {
    load();
  }, [load]);

  const handleAi = async () => {
    setAiLoading(true);
    setAiError("");
    try {
      const res = await astrologyService.analyzeNowChartAI(
        {
          place: loc?.place,
          latitude: loc?.latitude,
          longitude: loc?.longitude,
          timezone: loc?.timezone,
          currentTz: loc?.timezone,
        },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.reading || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("now.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  const panch = data?.panchanga || {};

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Globe size={24} />}
        title={t("now.title")}
        subtitle={t("now.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <RecentReadings source="now_chart" />

        <div
          style={{ display: "flex", justifyContent: "flex-end", marginBottom: "var(--space-md)" }}
        >
          <button className="ui-btn ui-btn--secondary" onClick={load} disabled={loading || !loc}>
            <RefreshCw size={16} /> {t("now.refresh")}
          </button>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("now.loading")} />
          </Card>
        ) : !loc ? (
          <Card accent="indigo">
            <p className="ai-panel__hint">{t("now.noPlace")}</p>
            <Link to="/settings?tab=location" className="ui-btn ui-btn--secondary">
              <MapPin size={16} /> {t("now.setLocation")}
            </Link>
          </Card>
        ) : data ? (
          <div className="fade-in">
            {data.moment && (
              <p className="card-note">
                {t("now.asOf", { date: data.moment.date, time: data.moment.time })}
                {loc.place
                  ? ` · ${t(loc.source === "birth" ? "now.castForBirth" : "now.castFor", {
                      place: loc.place,
                    })}`
                  : ""}
              </p>
            )}
            {loc.source === "birth" && (
              <p className="card-note">
                {t("now.castForBirthHint")}{" "}
                <Link to="/settings?tab=location">{t("now.setLocation")}</Link>
              </p>
            )}

            <div className="chart-grid">
              <Card title={t("now.chartTitle")} accent="indigo">
                <Kundali
                  planets={data.planets}
                  lagna={data.lagna}
                  title={t("now.chartTitle")}
                  exportable
                />
              </Card>
            </div>

            {panch.tithi && (
              <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush mt-xl">
                <h3 className="ui-card-header ui-card-header--sm">{t("now.panchanga")}</h3>
                <div className="info-pills">
                  {panch.vaara?.name && <span className="info-pill">{panch.vaara.name}</span>}
                  {panch.tithi?.name && <span className="info-pill">{panch.tithi.name}</span>}
                  {panch.nakshatra?.name && (
                    <span className="info-pill">{ln(panch.nakshatra.name, "nakshatra")}</span>
                  )}
                  {panch.yoga?.name && <span className="info-pill">{panch.yoga.name}</span>}
                  {data.hora_lord && (
                    <span className="info-pill">{t("now.hora", { lord: data.hora_lord })}</span>
                  )}
                </div>
              </div>
            )}

            <div className="mt-xl">
              <Card title={t("now.aiTitle")} icon={<Sparkles size={24} />} accent="indigo">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("now.aiHint")}</p>}
                {aiLoading && <LoadingState message={t("now.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <Markdown>{aiAnalysis}</Markdown>
                    {aiModel && (
                      <div className="ai-panel__meta">{t("now.aiModel", { model: aiModel })}</div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("now.aiRegenerate") : t("now.aiGenerate")}
                  </button>
                )}
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default NowChartPage;
