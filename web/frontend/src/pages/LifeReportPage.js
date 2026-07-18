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

// How often to ask the server how the run is going. Chapters take tens of
// seconds each, so this is about keeping the progress honest, not low latency.
const POLL_MS = 4000;

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

  const [chapters, setChapters] = useState([]); // catalog [{key,title}]
  const [job, setJob] = useState(null); // server-side run (progress + report)
  const [restored, setRestored] = useState(null); // {text, model} from history
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);

  // Restore a saved report from history (opens as a read-only snapshot).
  useRestoreReading((r) => {
    if (r.reading) setRestored({ text: r.reading, model: r.model || "" });
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

  // Pick up whatever the server already has for this profile: a run still in
  // progress (so a phone that slept re-attaches to it) or the last finished
  // report (so the page opens on it instead of a blank slate).
  const loadJob = useCallback(async () => {
    if (!selectedProfile?._id) return null;
    try {
      const res = await astrologyService.getLifeReportJob(selectedProfile._id);
      const data = res.data && res.data.status !== "none" ? res.data : null;
      setJob(data);
      return data;
    } catch {
      return null; // transient — polling will try again
    }
  }, [selectedProfile]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    loadChapters();
    loadJob();
  }, [selectedProfile, navigate, loadChapters, loadJob]);

  const running = job?.status === "running";

  // Poll while a run is in flight. Generation itself lives on the server, so the
  // page can be backgrounded or reloaded without affecting it — this only keeps
  // the display current. iOS freezes timers while the screen is off, so also
  // refresh the moment the tab becomes visible again for an instant catch-up.
  useEffect(() => {
    if (!running) return undefined;
    const id = setInterval(loadJob, POLL_MS);
    const onVisible = () => {
      if (document.visibilityState === "visible") loadJob();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [running, loadJob]);

  const generate = async (regenerate = false) => {
    if (!birthDetails) return;
    setError("");
    setRestored(null);
    setStarting(true);
    try {
      const res = await astrologyService.startLifeReport(
        birthDetails,
        { personName: birthDetails.name, profileId: selectedProfile?._id, regenerate },
        { ...readModelConfig(), ayanamsa }
      );
      setJob(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("lifeReport.error"));
    } finally {
      setStarting(false);
    }
  };

  const cancel = async () => {
    if (!job?.job_id) return;
    try {
      await astrologyService.cancelLifeReport(job.job_id);
    } catch {
      /* already finished — the next poll settles it */
    }
    loadJob();
  };

  if (!selectedProfile) return null;

  // Chapter rows come from the running/finished job (they carry the text); before
  // any job exists, fall back to the catalog so the chapter list is still shown.
  const rows = job?.chapters?.length
    ? job.chapters
    : chapters.map((c) => ({ ...c, status: "pending", text: "" }));
  const total = job?.total || chapters.length;
  const doneCount = job?.done_count || 0;
  const reportModel = restored ? restored.model : job?.model || job?.provider || "";
  const anyDone = Boolean(restored) || doneCount > 0;
  const jobError = job?.status === "error" ? job.error : "";

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

        <ErrorBanner message={error || jobError} />

        {/* Controls + progress */}
        <div className="lr-controls">
          <button
            className="ui-btn ui-btn--ai"
            onClick={() => generate(anyDone)}
            disabled={running || starting}
          >
            <Sparkles size={18} />
            {running
              ? t("lifeReport.generating", { n: Math.min(doneCount + 1, total), total })
              : anyDone
                ? t("lifeReport.regenerate")
                : t("lifeReport.generate")}
          </button>
          {running && (
            <button className="ui-btn ui-btn--ghost" onClick={cancel}>
              {t("lifeReport.cancel")}
            </button>
          )}
          {anyDone && !running && (
            <>
              <button className="ui-btn ui-btn--ghost" onClick={() => window.print()}>
                <Printer size={18} />
                {t("lifeReport.print")}
              </button>
              {job?.status === "done" && !restored && (
                <span className="lr-saved">
                  <Check size={16} /> {t("lifeReport.saved")}
                </span>
              )}
            </>
          )}
        </div>

        {/* Reassure the user they can leave — this is the whole point of moving
            generation to the server. */}
        {running && <p className="card-note lr-keeps-running">{t("lifeReport.keepsRunning")}</p>}

        {/* Chapter progress chips (live) */}
        {running && (
          <div className="lr-progress">
            {rows.map((c) => {
              const st = c.status || "pending";
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
              {reportModel && (
                <p className="lr-doc__meta">{t("lifeReport.model", { model: reportModel })}</p>
              )}
            </div>

            {restored ? (
              <div className="lr-chapter sbc-ai-markdown">
                <ReactMarkdown>{restored.text}</ReactMarkdown>
              </div>
            ) : (
              rows.map((c) =>
                c.status === "done" && c.text ? (
                  <div className="lr-chapter" key={c.key}>
                    <h2>{c.title}</h2>
                    <div className="sbc-ai-markdown">
                      <ReactMarkdown>{c.text}</ReactMarkdown>
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
