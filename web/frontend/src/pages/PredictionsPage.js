import React, { useState, useEffect, useMemo, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Target, Sparkles } from "lucide-react";
import Markdown from "../components/Markdown";
import { useProfile } from "../contexts/ProfileContext";
import { useSettings } from "../contexts/SettingsContext";
import { astrologyService } from "../services/api";
import { useRestoreReading } from "../hooks/useRestoreReading";
import { RecentReadings } from "../components/RecentReadings";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { Card } from "../components/Card";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Tabs, useTabs } from "../components/Tabs";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import { returnHere } from "../utils/returnTo";

// Read the user's AI provider/model choice (Settings → AI, persisted in
// localStorage) — the same path every other AI page uses. A blank model lets the
// server fall back to its configured default.
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

// The topics the backend's prediction prompt knows (`llm/prompts.py`
// `_build_prediction_prompt` → type_specific). An unknown key would silently
// fall back to "general", so this list must stay a subset of that one.
export const TOPICS = ["general", "career", "relationships", "health"];

/**
 * Topic Reading (§79.3) — a focused AI reading of the selected chart on one area
 * of life. Part of the Reports hub: the Life Report covers everything in
 * chapters; this answers "just tell me about my career".
 *
 * This was the app's original /predictions form: it took birth details by hand,
 * ignored the selected profile, repeated the Birth Chart's positions and the
 * Transits page's table, had no header (so no way back into the app), and
 * dropped the `?reading=` id History opens it with. The route stays /predictions
 * so saved readings still reopen here.
 */
export const PredictionsPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;

  // The topic lives in the URL (`?tab=career`) like every tab bar, so a topic is
  // linkable from search and survives a refresh.
  const topicTabs = useMemo(
    () => TOPICS.map((key) => ({ key, label: t(`predictions.topic.${key}`) })),
    [t]
  );
  const { tabs, active: topic, setActive } = useTabs(topicTabs);
  const [reading, setReading] = useState("");
  const [model, setModel] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // A reading belongs to the topic it was written for: switching topic clears
  // it — except the one switch a History restore makes to reach its own topic.
  const keepOnSwitch = useRef(false);
  useEffect(() => {
    if (keepOnSwitch.current) {
      keepOnSwitch.current = false;
      return;
    }
    setReading("");
    setModel("");
    setError("");
  }, [topic]);

  // Reopened from History (`?reading=`): show the saved text under the topic it
  // was written for. Applied one render later, as KPPage does, so the topic's
  // `?tab=` write lands after the hook has dropped `?reading=` from the URL
  // rather than racing it.
  const [pending, setPending] = useState(null);
  useRestoreReading((r) => setPending(r));
  useEffect(() => {
    if (!pending) return;
    const saved = pending.context?.prediction_type;
    if (TOPICS.includes(saved) && saved !== topic) {
      keepOnSwitch.current = true;
      setActive(saved);
    }
    setReading(pending.reading);
    setModel(pending.model);
    setPending(null);
  }, [pending, topic, setActive]);

  useEffect(() => {
    if (!selectedProfile) navigate("/profile-selection", returnHere());
  }, [selectedProfile, navigate]);

  const birthDetails = useMemo(() => {
    if (!selectedProfile) return null;
    const b = selectedProfile.birth_details;
    return {
      name: b.name,
      dob: b.dob,
      tob: b.tob,
      place: b.place,
      latitude: parseFloat(b.latitude),
      longitude: parseFloat(b.longitude),
      timezone: parseFloat(b.timezone),
    };
  }, [selectedProfile]);

  const generate = async () => {
    if (!birthDetails) return;
    setLoading(true);
    setError("");
    try {
      const res = await astrologyService.generatePrediction(birthDetails, topic, {
        ...readModelConfig(),
        ayanamsa,
      });
      setReading(res.data?.prediction || "");
      setModel(res.data?.model || res.data?.provider || "");
    } catch (err) {
      setError(err.response?.data?.detail || t("predictions.aiError"));
    } finally {
      setLoading(false);
    }
  };

  if (!selectedProfile) return null;

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Target size={24} />}
        title={t("predictions.title")}
        subtitle={t("predictions.subtitle")}
        accent="gold"
      />
      <main id="page-content" className="page-main">
        <div className="dashboard-content">
          <RecentReadings source="prediction" profileId={selectedProfile._id} />
          <ProfileBanner profile={selectedProfile} />
          <p className="card-note">{t("predictions.intro")}</p>

          <Tabs
            tabs={tabs}
            active={topic}
            onChange={setActive}
            ariaLabel={t("predictions.topicLabel")}
          />
          <p className="card-note">{t(`predictions.topicHint.${topic}`)}</p>

          <div className="mt-xl">
            <Card
              title={t("predictions.readingTitle")}
              icon={<Sparkles size={24} />}
              accent="indigo"
            >
              <ErrorBanner message={error} />
              {!reading && !loading && <p className="ai-panel__hint">{t("predictions.hint")}</p>}
              {loading && <LoadingState message={t("predictions.generating")} />}
              {reading && !loading && (
                <div className="sbc-ai-markdown ai-panel__reading">
                  <Markdown>{reading}</Markdown>
                  {model && (
                    <div className="ai-panel__meta">{t("predictions.aiModel", { model })}</div>
                  )}
                </div>
              )}
              {!loading && (
                <button className="ui-btn ui-btn--ai" onClick={generate}>
                  <Sparkles size={18} />
                  {reading ? t("predictions.regenerate") : t("predictions.generate")}
                </button>
              )}
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
};

export default PredictionsPage;
