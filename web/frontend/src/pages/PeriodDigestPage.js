import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  CalendarDays,
  CalendarRange,
  Sparkles,
  Bell,
  Clock,
  Orbit,
  Star,
  Moon,
  Sun,
  ShieldAlert,
  Sprout,
} from "lucide-react";
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

const todayStr = () => ymd(new Date());

const shiftDays = (dateStr, delta) => {
  const [y, m, d] = dateStr.split("-").map(Number);
  return ymd(new Date(y, m - 1, d + delta));
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

// One page, two cadences on the pravesha ladders.
//
//   period="fortnightly" → the running paksha (Shukla/Krishna, ~14.8d) and its
//        Paksha Pravesha chart. Lunar-only: Tajaka's solar ladder has no
//        fortnight rung, so no basis toggle is offered here.
//   period="monthly"     → the month, on whichever ladder `basis` selects:
//        solar = Maasa Pravesha (~30.4d), lunar = birth-tithi return (~29.5d).
//
// The basis defaults to the global Settings value and can be overridden locally.
const PeriodDigestPage = ({ period }) => {
  const isMonth = period === "monthly";
  const navigate = useNavigate();
  const ln = useLocalizeName();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;
  const source = isMonth ? "monthly_digest" : "fortnightly_digest";

  // Per-page override of the global pravesha basis (monthly only).
  const [basis, setBasis] = useState(settings.praveshaBasis || "solar");
  useEffect(() => setBasis(settings.praveshaBasis || "solar"), [settings.praveshaBasis]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [digest, setDigest] = useState(null);
  // Any date inside the window we want; the backend snaps it to the pravesha
  // window that contains it. Defaults to today; the ± stepper walks it.
  const [anchor, setAnchor] = useState(todayStr);
  const isCurrent = anchor === todayStr();

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
      const res = isMonth
        ? await astrologyService.getMonthlyDigest(birthDetails, { date: anchor, basis, ayanamsa })
        : await astrologyService.getFortnightlyDigest(birthDetails, { date: anchor, ayanamsa });
      setDigest(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("periodDigest.error"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, ayanamsa, isMonth, basis, anchor, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    load();
  }, [selectedProfile, navigate, load]);

  // Hop a whole window at a time. Pravesha windows are not a fixed number of days
  // (a paksha runs ~13–15d, a lunar month ~29.5d, a Maasa ~30.4d), so we step off
  // the boundaries the backend just returned rather than adding a nominal length:
  // one day past the end lands in the next window, one day before the start in the
  // previous one, whatever their true lengths turn out to be.
  const stepWindow = (dir) => {
    if (!digest?.start_date || !digest?.end_date) return;
    setAnchor(dir > 0 ? shiftDays(digest.end_date, 1) : shiftDays(digest.start_date, -1));
  };

  const handleAi = async () => {
    if (!birthDetails) return;
    setAiLoading(true);
    setAiError("");
    try {
      const res = await astrologyService.analyzePeriodDigestAI(
        isMonth ? "monthly" : "fortnightly",
        birthDetails,
        { date: anchor, basis: isMonth ? basis : undefined, personName: birthDetails.name },
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
  // Each entry is {text, scope} — see the daily page. Only the daily card has
  // avoid-windows (a window is not a clock time).
  const cautions = digest?.cautions || [];
  // Where the window's dated Tara Bala days land — the one genuinely day-by-day
  // thing a fortnight or month reading has to offer.
  const supports = digest?.supports || [];

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={isMonth ? <CalendarRange size={24} /> : <CalendarDays size={24} />}
        title={t(isMonth ? "periodDigest.monthTitle" : "periodDigest.fortnightTitle")}
        subtitle={t(isMonth ? "periodDigest.monthSubtitle" : "periodDigest.fortnightSubtitle")}
        accent="saffron"
      />

      <div className="dashboard-content">
        <RecentReadings source={source} profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />

        <div className="page-controls">
          <div className="controls-group">
            <div className="stepper">
              <button
                type="button"
                className="stepper__btn"
                onClick={() => stepWindow(-1)}
                disabled={loading || !digest}
                aria-label={t(isMonth ? "periodDigest.prevMonth" : "periodDigest.prevFortnight")}
                title={t(isMonth ? "periodDigest.prevMonth" : "periodDigest.prevFortnight")}
              >
                −
              </button>
              <span className="stepper__label" style={{ minWidth: "14rem" }}>
                {formatDate(digest?.start_date, locale)} → {formatDate(digest?.end_date, locale)}
                {digest?.span_days
                  ? ` · ${t("periodDigest.spanDays", { count: digest.span_days })}`
                  : ""}
              </span>
              <button
                type="button"
                className="stepper__btn"
                onClick={() => stepWindow(1)}
                disabled={loading || !digest}
                aria-label={t(isMonth ? "periodDigest.nextMonth" : "periodDigest.nextFortnight")}
                title={t(isMonth ? "periodDigest.nextMonth" : "periodDigest.nextFortnight")}
              >
                +
              </button>
            </div>
            <button
              className="control-btn"
              onClick={() => (isCurrent ? load() : setAnchor(todayStr()))}
            >
              {isCurrent ? t("periodDigest.refresh") : t("periodDigest.current")}
            </button>
            <button className="control-btn" onClick={() => navigate("/settings")}>
              <Bell size={14} /> {t("periodDigest.notifySettings")}
            </button>
            {/* The window's pravesha chart + Tithi Ashtottari live there now. */}
            <button className="control-btn" onClick={() => navigate("/tithi-pravesha")}>
              <Moon size={14} /> {t("periodDigest.tpLink")}
            </button>
          </div>

          {/* Monthly only — and this is NOT the chart-basis toggle that was removed
              from the Daily page and from Varshaphal. It picks **which month the
              digest covers**: the solar month (Maasa Pravesha, ~30.4d) or the lunar
              one (your birth tithi returning, ~29.5d). Those are genuinely different
              windows — for 2026-07-13, 6 Jul→6 Aug versus 19 Jun→19 Jul — with
              different transit events in them. So it is labelled as the window choice
              it is, not as a "basis", or it reads as leftover duplication.
              (A *day* is the same calendar day on either ladder, which is exactly why
              the Daily page has no such control; the fortnight is lunar by definition.)
              Uses the shared .chart-toggle segmented control, which is the one
              pattern in the app that actually paints an active state. */}
          {isMonth && (
            <div className="controls-group">
              <span className="control-label">{t("periodDigest.monthType")}</span>
              <div className="chart-toggle" role="group" aria-label={t("periodDigest.monthType")}>
                <button
                  type="button"
                  className={`chart-toggle__btn${basis === "solar" ? " is-active" : ""}`}
                  aria-pressed={basis === "solar"}
                  onClick={() => setBasis("solar")}
                  title={t("periodDigest.solarMonthHint")}
                >
                  <Sun size={14} /> {t("periodDigest.solarMonth")}
                </button>
                <button
                  type="button"
                  className={`chart-toggle__btn${basis === "lunar" ? " is-active" : ""}`}
                  aria-pressed={basis === "lunar"}
                  onClick={() => setBasis("lunar")}
                  title={t("periodDigest.lunarMonthHint")}
                >
                  <Moon size={14} /> {t("periodDigest.lunarMonth")}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* What window the reading actually covers — this is not a calendar month/week. */}
        {digest?.window_label && (
          <p className="settings-hint">
            {t("periodDigest.windowNote", { window: digest.window_label })}
          </p>
        )}

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState
              message={t(isMonth ? "periodDigest.loadingMonth" : "periodDigest.loadingFortnight")}
            />
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
                  <li
                    key={i}
                    className={h.startsWith("⚠") ? "digest-hl digest-hl--warn" : "digest-hl"}
                  >
                    {h}
                  </li>
                ))}
              </ul>
            </div>

            {supports.length > 0 && (
              <div className="ui-card ui-card--pad-lg ui-card--flush digest-supports mt-xl">
                <h3 className="ui-card-header ui-card-header--sm">
                  <Sprout size={18} /> {t("periodDigest.supports")}
                </h3>
                <p className="text-muted digest-cautions__hint">
                  {t("periodDigest.supportsHint")}
                </p>
                <ul className="digest-highlights">
                  {supports.map((c, i) => (
                    <li key={i} className="digest-hl digest-hl--support">
                      <span className={`digest-scope digest-scope--${c.scope || "standing"}`}>
                        {c.scope === "today"
                          ? t("periodDigest.scopeToday")
                          : t("periodDigest.scopeStanding")}
                      </span>
                      {c.text}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* What this window asks care with — kept out of Highlights so a
                testing transit isn't read as one more neutral fact. */}
            {cautions.length > 0 && (
              <div className="ui-card ui-card--pad-lg ui-card--flush digest-cautions mt-xl">
                <h3 className="ui-card-header ui-card-header--sm">
                  <ShieldAlert size={18} /> {t("periodDigest.cautions")}
                </h3>
                <p className="text-muted digest-cautions__hint">
                  {t("periodDigest.cautionsHint")}
                </p>
                <ul className="digest-highlights">
                  {cautions.map((c, i) => (
                    <li key={i} className="digest-hl digest-hl--caution">
                      <span className={`digest-scope digest-scope--${c.scope || "standing"}`}>
                        {c.scope === "today"
                          ? t("periodDigest.scopeToday")
                          : t("periodDigest.scopeStanding")}
                      </span>
                      {c.text}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="chart-grid mt-xl">
              {/* Opening panchanga */}
              {panch && (
                <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush">
                  <h3 className="ui-card-header ui-card-header--sm">
                    <CalendarDays size={18} /> {t("periodDigest.panchanga")}
                  </h3>
                  <div className="detail-list digest-details">
                    <div>
                      <span className="kv-label">{t("periodDigest.tithi")}</span>
                      <span className="kv-value">{panch.tithi?.name}</span>
                    </div>
                    <div>
                      <span className="kv-label">{t("periodDigest.nakshatra")}</span>
                      <span className="kv-value">{ln(panch.nakshatra?.name, "nakshatra")}</span>
                    </div>
                    <div>
                      <span className="kv-label">{t("periodDigest.vaara")}</span>
                      <span className="kv-value">{panch.vaara?.name}</span>
                    </div>
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
                    <div>
                      <span className="kv-label">{t("periodDigest.mahadasha")}</span>
                      <span className="kv-value">{dasha.maha_lord}</span>
                    </div>
                    {dasha.bhukti && (
                      <div>
                        <span className="kv-label">{t("periodDigest.bhukti")}</span>
                        <span className="kv-value">
                          {dasha.bhukti.lord} → {dasha.bhukti.end_date}
                        </span>
                      </div>
                    )}
                    {dasha.next_maha && (
                      <div>
                        <span className="kv-label">{t("periodDigest.nextMaha")}</span>
                        <span className="kv-value">{dasha.next_maha}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* The progressed (pravesha) chart that backs this window is no longer
                drawn here. It — with its Muntha, its Tajaka yogas and its compressed
                Tithi Ashtottari — lives on the Tithi Pravesha page, which shows every
                rung of the lunar ladder. This page stays a summary of the period, and
                links across rather than rendering the same chart twice. (Muntha and
                the year-lord were the tell: both are reckoned from the age in *years*,
                so they never meant anything on a fortnight in the first place.) */}

            {/* Transit events in the window */}
            <div className="ui-card ui-card--accent-gold ui-card--pad-lg ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm">
                <Orbit size={18} /> {t("periodDigest.events")}
              </h3>
              {transits?.sade_sati && (
                <p className="digest-hl digest-hl--warn">{t("periodDigest.sadeSati")}</p>
              )}
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
                title={t(isMonth ? "periodDigest.aiTitleMonth" : "periodDigest.aiTitleFortnight")}
                icon={<Sparkles size={24} />}
                accent="saffron"
              >
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && (
                  <p className="ai-panel__hint">
                    {t(isMonth ? "periodDigest.aiHintMonth" : "periodDigest.aiHintFortnight")}
                  </p>
                )}
                {aiLoading && <LoadingState message={t("periodDigest.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">
                        {t("periodDigest.aiModel", { model: aiModel })}
                      </div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis
                      ? t("periodDigest.aiRegenerate")
                      : t(
                          isMonth
                            ? "periodDigest.aiGenerateMonth"
                            : "periodDigest.aiGenerateFortnight"
                        )}
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

export const FortnightlyDigestPage = () => <PeriodDigestPage period="fortnightly" />;
export const MonthlyDigestPage = () => <PeriodDigestPage period="monthly" />;

export default PeriodDigestPage;
