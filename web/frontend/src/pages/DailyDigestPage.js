import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Sun, Moon, Sparkles, Bell, Clock, Orbit, Star, ShieldAlert } from "lucide-react";
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

const ymd = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const nowParts = () => {
  const d = new Date();
  return {
    date: ymd(d),
    time: `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`,
    tz: -d.getTimezoneOffset() / 60,
  };
};

// Walk the calendar day by day. Built from local Y/M/D parts (not a UTC-parsed
// timestamp) so the month/year rollover and DST are handled by the Date itself.
const shiftDays = (dateStr, delta) => {
  const [y, m, d] = dateStr.split("-").map(Number);
  const dt = new Date(y, m - 1, d + delta);
  return ymd(dt);
};

const formatDate = (dateStr, locale = "en-US") => {
  if (!dateStr) return "—";
  try {
    return new Date(`${dateStr}T00:00:00`).toLocaleDateString(locale, {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
};

export const DailyDigestPage = () => {
  const navigate = useNavigate();
  const ln = useLocalizeName();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [digest, setDigest] = useState(null);
  // Which day the card is cast for. Defaults to today; the ± stepper walks it.
  const [anchor, setAnchor] = useState(() => nowParts().date);
  const isToday = anchor === nowParts().date;

  // The day's pravesha ladder, taken from the global Settings value — the same one
  // the scheduled email digest uses, so the page and the email read alike. There is
  // no toggle: unlike the month, the *day* is the same calendar day on either ladder,
  // so the basis only ever coloured the narrative. The chart it used to draw here
  // lives on the Tithi Pravesha page, which shows every rung of the lunar ladder.
  const basis = settings.praveshaBasis || "solar";

  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");
  // Reopen a saved reading from History (apply the saved text once load settles).
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
      const { time, tz } = nowParts();
      const res = await astrologyService.getDailyDigest(birthDetails, {
        date: anchor,
        currentTime: time,
        currentTz: tz,
        basis,
        ayanamsa,
      });
      setDigest(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("digest.error"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, ayanamsa, anchor, basis, t]);

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
      const { time, tz } = nowParts();
      const res = await astrologyService.analyzeDailyDigestAI(
        birthDetails,
        { date: anchor, currentTime: time, currentTz: tz, basis, personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("digest.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const panch = digest?.panchanga;
  const dasha = digest?.dasha;
  const transits = digest?.transits;
  const highlights = digest?.highlights || [];
  // The difficult side of the day: each entry is {text, scope} — "today" is what
  // changed, "standing" is the months-long backdrop it sits in.
  const cautions = digest?.cautions || [];
  const avoidWindows = digest?.avoid_windows || [];

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Sun size={24} />}
        title={t("digest.title")}
        subtitle={t("digest.subtitle")}
        accent="saffron"
      />

      <div className="dashboard-content">
        <RecentReadings source="daily_digest" profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />

        <div className="page-controls">
          {/* ± day stepper — the same look-ahead/look-back the annual page has,
              one calendar day at a time. The whole card (panchanga, transits,
              dasha) recomputes for the day you land on. */}
          <div className="controls-group">
            <div className="stepper">
              <button
                type="button"
                className="stepper__btn"
                onClick={() => setAnchor((a) => shiftDays(a, -1))}
                aria-label={t("digest.prevDay")}
                title={t("digest.prevDay")}
              >
                −
              </button>
              <span className="stepper__label" style={{ minWidth: "13rem" }}>
                {formatDate(anchor, locale)}
              </span>
              <button
                type="button"
                className="stepper__btn"
                onClick={() => setAnchor((a) => shiftDays(a, 1))}
                aria-label={t("digest.nextDay")}
                title={t("digest.nextDay")}
              >
                +
              </button>
            </div>
            <button
              className="control-btn"
              onClick={() => (isToday ? load() : setAnchor(nowParts().date))}
            >
              {isToday ? t("digest.refresh") : t("digest.today")}
            </button>
            <button className="control-btn" onClick={() => navigate("/settings")}>
              <Bell size={14} /> {t("digest.notifySettings")}
            </button>
          </div>

          {/* The day's chart lives on the Tithi Pravesha page (its "Day" rung), which
              carries every rung of the lunar ladder. This page stays a summary. */}
          <div className="controls-group controls-group--end">
            <button className="control-btn" onClick={() => navigate("/tithi-pravesha")}>
              <Moon size={14} /> {t("digest.tpLink")}
            </button>
          </div>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("digest.loading")} />
          </Card>
        ) : digest ? (
          <div className="fade-in">
            {/* Highlights */}
            <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush">
              <h3 className="ui-card-header ui-card-header--sm">
                <Star size={18} /> {t("digest.highlights")}
              </h3>
              <ul className="digest-highlights">
                {highlights.map((h, i) => (
                  <li
                    key={i}
                    className={h.startsWith("⚠") ? "digest-hl digest-hl--warn" : "digest-hl"}
                  >
                    {h}
                  </li>
                ))}
              </ul>
            </div>

            {/* What the day asks care with. Its own card rather than more bullets
                in Highlights: a hard transit listed among neutral facts reads as
                another neutral fact. */}
            {cautions.length > 0 && (
              <div className="ui-card ui-card--pad-lg ui-card--flush digest-cautions mt-xl">
                <h3 className="ui-card-header ui-card-header--sm">
                  <ShieldAlert size={18} /> {t("digest.cautions")}
                </h3>
                <p className="text-muted digest-cautions__hint">{t("digest.cautionsHint")}</p>
                <ul className="digest-highlights">
                  {cautions.map((c, i) => (
                    <li key={i} className="digest-hl digest-hl--caution">
                      <span
                        className={`digest-scope digest-scope--${c.scope || "standing"}`}
                        title={
                          c.scope === "today"
                            ? t("digest.cautionsHint")
                            : t("digest.cautionsHint")
                        }
                      >
                        {c.scope === "today" ? t("digest.scopeToday") : t("digest.scopeStanding")}
                      </span>
                      {c.text}
                    </li>
                  ))}
                </ul>
                {avoidWindows.length > 0 && (
                  <>
                    <h4 className="digest-cautions__sub">{t("digest.avoidWindows")}</h4>
                    <p className="text-muted digest-cautions__hint">{t("digest.avoidHint")}</p>
                    <ul className="digest-highlights">
                      {avoidWindows.map((w, i) => (
                        <li key={i} className="digest-hl">
                          {w.name} · {w.start}–{w.end}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}

            <div className="chart-grid mt-xl">
              {/* Panchanga snapshot */}
              {panch && (
                <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush">
                  <h3 className="ui-card-header ui-card-header--sm">
                    <Sun size={18} /> {t("digest.panchanga")}
                  </h3>
                  <div className="detail-list digest-details">
                    <div>
                      <span className="kv-label">{t("digest.tithi")}</span>
                      <span className="kv-value">{panch.tithi?.name}</span>
                    </div>
                    <div>
                      <span className="kv-label">{t("digest.nakshatra")}</span>
                      <span className="kv-value">{ln(panch.nakshatra?.name, "nakshatra")}</span>
                    </div>
                    <div>
                      <span className="kv-label">{t("digest.yoga")}</span>
                      <span className="kv-value">{panch.yoga?.name}</span>
                    </div>
                    <div>
                      <span className="kv-label">{t("digest.vaara")}</span>
                      <span className="kv-value">{panch.vaara?.name}</span>
                    </div>
                    <div>
                      <span className="kv-label">{t("digest.sunrise")}</span>
                      <span className="kv-value">
                        {panch.sunrise} / {panch.sunset}
                      </span>
                    </div>
                    {panch.abhijit && (
                      <div>
                        <span className="kv-label">{t("digest.abhijit")}</span>
                        <span className="kv-value">
                          {panch.abhijit.start}–{panch.abhijit.end}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Dasha snapshot */}
              {dasha && (
                <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush">
                  <h3 className="ui-card-header ui-card-header--sm">
                    <Clock size={18} /> {t("digest.dasha")}
                  </h3>
                  <div className="detail-list digest-details">
                    <div>
                      <span className="kv-label">{t("digest.mahadasha")}</span>
                      <span className="kv-value">{dasha.maha_lord}</span>
                    </div>
                    {dasha.bhukti && (
                      <div>
                        <span className="kv-label">{t("digest.bhukti")}</span>
                        <span className="kv-value">
                          {dasha.bhukti.lord} → {dasha.bhukti.end_date}
                        </span>
                      </div>
                    )}
                    {dasha.next_maha && (
                      <div>
                        <span className="kv-label">{t("digest.nextMaha")}</span>
                        <span className="kv-value">{dasha.next_maha}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Transit highlights */}
            {transits && (
              <div className="ui-card ui-card--accent-gold ui-card--pad-lg ui-card--flush mt-xl">
                <h3 className="ui-card-header ui-card-header--sm">
                  <Orbit size={18} /> {t("digest.transits")}
                </h3>
                {transits.sade_sati && (
                  <p className="digest-hl digest-hl--warn">{t("digest.sadeSati")}</p>
                )}
                {transits.retrograde?.length > 0 && (
                  <p className="digest-retro">
                    <span className="kv-label">{t("digest.retrograde")}:</span>{" "}
                    {transits.retrograde.join(", ")}
                  </p>
                )}
                {transits.upcoming?.length > 0 && (
                  <ul className="detail-list digest-details">
                    {transits.upcoming.map((u, i) => (
                      <li key={i}>
                        <span className="kv-label">{u.planet}</span>
                        <span className="kv-value">
                          → {u.to_sign} · {u.date}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {/* AI reading */}
            <div className="mt-xl">
              <Card title={t("digest.aiTitle")} icon={<Sparkles size={24} />} accent="saffron">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && (
                  <p className="ai-panel__hint">{t("digest.aiHint")}</p>
                )}
                {aiLoading && <LoadingState message={t("digest.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">
                        {t("digest.aiModel", { model: aiModel })}
                      </div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("digest.aiRegenerate") : t("digest.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("digest.disclaimer")}</p>
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default DailyDigestPage;
