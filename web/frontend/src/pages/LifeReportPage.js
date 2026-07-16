import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ScrollText, Sparkles, Printer, Check, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { useRestoreReading } from "../hooks/useRestoreReading";
import { RecentReadings } from "../components/RecentReadings";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { useSettings } from "../contexts/SettingsContext";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import "../styles/LifeReport.css";

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

export const LifeReportPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;

  const [chapters, setChapters] = useState([]); // [{key,title}]
  const [results, setResults] = useState({}); // key -> {text, status}
  const [running, setRunning] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const [error, setError] = useState("");
  const [model, setModel] = useState("");
  const [saved, setSaved] = useState(false);

  // Restore a saved report from history (opens as a read-only snapshot).
  useRestoreReading((r) => {
    if (r.reading) {
      setResults({ __restored: { text: r.reading, status: "done", title: "" } });
      setModel(r.model || "");
    }
  });

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

  const loadChapters = useCallback(async () => {
    try {
      const res = await astrologyService.getLifeReportChapters();
      setChapters(res.data?.chapters || []);
    } catch (err) {
      setError(err.response?.data?.detail || t("lifeReport.loadError"));
    }
  }, [t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    loadChapters();
  }, [selectedProfile, navigate, loadChapters]);

  const assembledMarkdown = useCallback(() => {
    if (results.__restored) return results.__restored.text;
    return chapters
      .filter((c) => results[c.key]?.status === "done")
      .map((c) => `## ${c.title}\n\n${results[c.key].text}`)
      .join("\n\n");
  }, [chapters, results]);

  const generate = async () => {
    if (!birthDetails || !chapters.length) return;
    setRunning(true);
    setError("");
    setSaved(false);
    setResults({});
    const mcfg = { ...readModelConfig(), ayanamsa };
    const opts = { personName: birthDetails.name, profileId: selectedProfile?._id };
    let lastModel = "";
    for (let i = 0; i < chapters.length; i++) {
      const ch = chapters[i];
      setActiveIdx(i);
      setResults((r) => ({ ...r, [ch.key]: { status: "active", text: "" } }));
      try {
        const res = await astrologyService.generateLifeReportChapter(
          birthDetails,
          ch.key,
          opts,
          mcfg
        );
        lastModel = res.data.model || res.data.provider || lastModel;
        setResults((r) => ({ ...r, [ch.key]: { status: "done", text: res.data.text } }));
      } catch (err) {
        setResults((r) => ({ ...r, [ch.key]: { status: "error", text: "" } }));
        setError(err.response?.data?.detail || t("lifeReport.error"));
        setRunning(false);
        setActiveIdx(-1);
        return;
      }
    }
    setActiveIdx(-1);
    setModel(lastModel);
    setRunning(false);
    // The save-when-complete effect below handles persistence from fresh state
    // (avoids the stale-closure `results` here).
  };

  // Save uses a fresh assembly once all chapters resolved (covers the stale-closure case).
  useEffect(() => {
    if (running || activeIdx !== -1) return;
    const done = chapters.length && chapters.every((c) => results[c.key]?.status === "done");
    if (done && !saved && !results.__restored) {
      astrologyService
        .saveLifeReport(birthDetails, assembledMarkdown(), {
          personName: birthDetails?.name,
          profileId: selectedProfile?._id,
        }, { ...readModelConfig(), ayanamsa })
        .then(() => setSaved(true))
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, activeIdx, results]);

  if (!selectedProfile) return null;

  const anyDone =
    results.__restored || chapters.some((c) => results[c.key]?.status === "done");
  const total = chapters.length;

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<ScrollText size={24} />}
        title={t("lifeReport.title")}
        subtitle={t("lifeReport.subtitle")}
        accent="gold"
      />

      <div className="dashboard-content">
        <RecentReadings source="life_report" profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />
        <p className="card-note">{t("lifeReport.intro")}</p>

        <ErrorBanner message={error} />

        {/* Controls + progress */}
        <div className="lr-controls">
          <button className="ui-btn ui-btn--ai" onClick={generate} disabled={running}>
            <Sparkles size={18} />
            {running
              ? t("lifeReport.generating", { n: activeIdx + 1, total })
              : anyDone
                ? t("lifeReport.regenerate")
                : t("lifeReport.generate")}
          </button>
          {anyDone && !running && (
            <>
              <button className="ui-btn ui-btn--ghost" onClick={() => window.print()}>
                <Printer size={18} />
                {t("lifeReport.print")}
              </button>
              {saved && (
                <span className="lr-saved">
                  <Check size={16} /> {t("lifeReport.saved")}
                </span>
              )}
            </>
          )}
        </div>

        {/* Chapter progress chips (live) */}
        {running && (
          <div className="lr-progress">
            {chapters.map((c, i) => {
              const st = results[c.key]?.status || "pending";
              return (
                <span key={c.key} className={`lr-chip lr-chip--${st}`}>
                  {st === "active" && <Loader2 size={14} className="lr-spin" />}
                  {st === "done" && <Check size={14} />}
                  {c.title}
                </span>
              );
            })}
          </div>
        )}

        {/* The report */}
        {anyDone && (
          <div className="lr-doc mt-xl">
            <div className="lr-doc__head">
              <h1>{t("lifeReport.forName", { name: birthDetails.name || "" })}</h1>
              {model && <p className="lr-doc__meta">{t("lifeReport.model", { model })}</p>}
            </div>

            {results.__restored ? (
              <div className="lr-chapter sbc-ai-markdown">
                <ReactMarkdown>{results.__restored.text}</ReactMarkdown>
              </div>
            ) : (
              chapters.map((c) =>
                results[c.key]?.status === "done" ? (
                  <div className="lr-chapter" key={c.key}>
                    <h2>{c.title}</h2>
                    <div className="sbc-ai-markdown">
                      <ReactMarkdown>{results[c.key].text}</ReactMarkdown>
                    </div>
                  </div>
                ) : null
              )
            )}

            <p className="card-note lr-disclaimer">{t("lifeReport.disclaimer")}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default LifeReportPage;
