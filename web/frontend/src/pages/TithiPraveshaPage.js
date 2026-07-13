import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Moon, Sparkles, Compass, Clock, Star } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { useSettings } from "../contexts/SettingsContext";
import { useRestoreReading } from "../hooks/useRestoreReading";
import { RecentReadings } from "../components/RecentReadings";
import { astrologyService } from "../services/api";
import { intlLocale } from "../utils/format";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { TithiAshtottariTree } from "../components/TithiAshtottariTree";
import { PLANET_ABBR, AYANAMSAS } from "../constants/jyotish";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

const PLANET_ORDER = [
  "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu",
];

// The lunar (tithi) pravesha ladder, shortest rung first. Each is a real pravesha
// window — the moment a tithi / paksha / lunar month / lunar year opens — not an
// arbitrary slice of the calendar.
const RUNGS = [
  { key: "tithi", labelKey: "tp.rungTithi" },
  { key: "paksha", labelKey: "tp.rungPaksha" },
  { key: "month", labelKey: "tp.rungMonth" },
  { key: "annual", labelKey: "tp.rungAnnual" },
];

const ymd = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

const today = () => ymd(new Date());

// Built from local Y/M/D parts (not a UTC-parsed timestamp) so month/year rollover
// and DST are handled by Date itself.
const shiftDays = (dateStr, delta) => {
  const [y, m, d] = dateStr.split("-").map(Number);
  return ymd(new Date(y, m - 1, d + delta));
};

const ordinal = (n) => {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
};

const formatDate = (dateStr, locale = "en-US") => {
  if (!dateStr) return "—";
  try {
    // A bare "YYYY-MM-DD" parses as UTC midnight, which renders a day early west of
    // Greenwich; pin date-only strings to local midnight.
    const local = /^\d{4}-\d{2}-\d{2}$/.test(dateStr) ? `${dateStr}T00:00:00` : dateStr;
    return new Date(local).toLocaleDateString(locale, {
      year: "numeric", month: "short", day: "numeric",
    });
  } catch {
    return "—";
  }
};

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

/**
 * **Tithi Pravesha** — the lunar-return chart, on any rung of the lunar ladder.
 *
 * One page, four cadences: the running tithi (~1 day), the paksha (~14.8d), the
 * lunar month (~29.5d) and the Tithi Pravesha year proper (~354/384d). Each is cast
 * at the *instant* its window opens, and each carries that window's compressed Tithi
 * Ashtottari — the whole 108-unit cycle fitted to the window, drillable to six levels.
 *
 * The solar counterpart (Varshaphal, the Tajaka return) lives on `/varshaphal`; the
 * two are read alongside each other, which is why they are separate pages.
 */
export const TithiPraveshaPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const chartStyle = settings.chartStyle;
  const ayanamsa = settings.ayanamsa;
  const ayanamsaLabel = AYANAMSAS.find((a) => a.value === ayanamsa)?.label || ayanamsa;

  const [rung, setRung] = useState("annual");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  // The ± stepper walks the ladder by re-anchoring a *date*, and the backend snaps
  // that date to the window containing it. The annual rung is the exception: it
  // addresses windows by year, which is also what History saves.
  const [anchor, setAnchor] = useState(() => today());
  const birthYear = selectedProfile?.birth_details?.dob
    ? parseInt(selectedProfile.birth_details.dob.split("-")[0], 10)
    : 1900;
  const [year, setYear] = useState(() => new Date().getFullYear());
  const isAnnual = rung === "annual";

  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");

  // Reopen a saved reading from History. Every rung is saved under the one
  // `tithi_pravesha` source, so restore the rung/window it was actually cast for,
  // then apply the saved text once the chart load has settled (or it gets clobbered).
  const [pendingReading, setPendingReading] = useState(null);
  useRestoreReading((r) => {
    if (r.context?.rung) setRung(r.context.rung);
    if (r.context?.year != null) setYear(r.context.year);
    if (r.context?.date) setAnchor(r.context.date);
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
    // A new window invalidates the previous reading.
    setAiAnalysis("");
    setAiError("");
    setAiModel("");
    try {
      const res = await astrologyService.getLunarPravesha(birthDetails, {
        rung,
        ...(rung === "annual" ? { year } : { date: anchor }),
        ayanamsa,
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("tp.calcError"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, rung, year, anchor, ayanamsa, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    load();
  }, [selectedProfile, navigate, load]);

  // Hop one whole window. Pravesha windows are NOT a fixed number of days (a paksha
  // runs 13–16d, a lunar year 354 or 384), so step off the boundaries the backend
  // just returned rather than adding a nominal length: one day past the end always
  // lands in the next window, one day before the start in the previous one, whatever
  // their true lengths. Keeps the walk contiguous — no gaps, no repeats.
  const step = (dir) => {
    if (isAnnual) {
      setYear((y) => Math.max(birthYear, y + dir));
      return;
    }
    const w = result?.window;
    if (!w?.start || !w?.end) return;
    setAnchor(dir > 0 ? shiftDays(w.end, 1) : shiftDays(w.start, -1));
  };

  // Switching rung re-anchors on the *current* window's start, so you stay where you
  // are on the timeline instead of being thrown back to today.
  const changeRung = (key) => {
    if (key === rung) return;
    const start = result?.window?.start;
    if (key === "annual") {
      if (start) setYear(parseInt(start.slice(0, 4), 10));
    } else if (start) {
      setAnchor(start);
    }
    setRung(key);
  };

  const isNow = isAnnual ? year === new Date().getFullYear() : anchor === today();
  const goNow = () => (isAnnual ? setYear(new Date().getFullYear()) : setAnchor(today()));

  const handleAi = async () => {
    if (!birthDetails) return;
    setAiLoading(true);
    setAiError("");
    try {
      const res = await astrologyService.analyzeTithiPraveshaAI(
        birthDetails,
        {
          rung,
          ...(isAnnual ? { year } : { date: anchor }),
          personName: birthDetails.name,
        },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("tp.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;
  const planets = result?.planets || {};
  const orderedPlanets = PLANET_ORDER.filter((p) => planets[p]).map((p) => [p, planets[p]]);
  const window_ = result?.window;
  const ta = result?.tithi_ashtottari;
  // Muntha, year-lord and the Sahams are reckoned from the age in YEARS — they carry
  // no meaning on a tithi or a fortnight, so they show only on the annual rung.
  const sahams = isAnnual ? result?.sahams || [] : [];
  const tajakaYogas = isAnnual ? result?.tajaka_yogas || [] : [];

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Moon size={24} />}
        title={t("tp.title")}
        subtitle={t("tp.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />
        <RecentReadings source="tithi_pravesha" profileId={selectedProfile?._id} />

        <div className="page-controls">
          {/* Which rung of the lunar ladder. */}
          <div className="controls-group">
            <label className="control-label">
              <Moon size={18} style={{ color: "var(--saffron)" }} />
              {t("tp.window")}
            </label>
            <div className="chart-toggle" role="group" aria-label={t("tp.window")}>
              {RUNGS.map((r) => (
                <button
                  key={r.key}
                  type="button"
                  className={`chart-toggle__btn${rung === r.key ? " is-active" : ""}`}
                  aria-pressed={rung === r.key}
                  onClick={() => changeRung(r.key)}
                >
                  {t(r.labelKey)}
                </button>
              ))}
            </div>
          </div>

          {/* ± one whole window of the selected rung. */}
          <div className="controls-group controls-group--end">
            <div className="stepper">
              <button
                type="button"
                className="stepper__btn"
                onClick={() => step(-1)}
                aria-label={t("tp.prev")}
                title={t("tp.prev")}
                disabled={isAnnual && year <= birthYear}
              >
                −
              </button>
              <span className="stepper__label" style={{ minWidth: "12rem", textAlign: "center" }}>
                {isAnnual
                  ? year
                  : `${formatDate(window_?.start, locale)} → ${formatDate(window_?.end, locale)}`}
              </span>
              <button
                type="button"
                className="stepper__btn"
                onClick={() => step(1)}
                aria-label={t("tp.next")}
                title={t("tp.next")}
              >
                +
              </button>
            </div>
            <button className="control-btn" onClick={() => (isNow ? load() : goNow())}>
              {isNow ? t("tp.refresh") : t("tp.now")}
            </button>
          </div>
        </div>

        {/* What this window is, and the exact instant the chart is cast at — the
            pravesha moment is solved in degrees, not rounded to the day. */}
        {window_ && (
          <p className="settings-hint">
            {t("tp.windowLine", {
              start: window_.start,
              end: window_.end,
              days: window_.span_days,
              label: result?.label || "",
            })}
            {window_.start_at && (
              <>
                <br />
                {t("tp.entryAt", { at: window_.start_at.replace("T", " ") })}
              </>
            )}
          </p>
        )}

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("tp.loading")} />
          </Card>
        ) : result ? (
          <div className="fade-in">
            <div className="info-pills">
              <span className="info-pill">
                {t("tp.lagna")}: <strong className="text-indigo">{result.lagna?.sign_name}</strong>
              </span>
              <span className="info-pill">
                {/* Only the annual window is entered *on* the natal tithi; the shorter
                    rungs are named for what they are (a tithi, a paksha, a return). */}
                {isAnnual ? t("tp.entryTithi") : t("tp.thisWindow")}:{" "}
                <strong className="text-vermillion">{result.label || "—"}</strong>
              </span>
              {/* Year-reckoned; annual rung only. */}
              {isAnnual && result.muntha && (
                <span className="info-pill">
                  {t("tp.muntha")}: <strong className="text-saffron">{result.muntha.sign_name}</strong>
                  {result.muntha.house ? ` (${ordinal(result.muntha.house)} ${t("tp.houseWord")})` : ""}
                </span>
              )}
              {isAnnual && result.year_lord && (
                <span className="info-pill">
                  {t("tp.yearLord")}:{" "}
                  <strong className="text-vermillion">{result.year_lord.planet || "—"}</strong>
                </span>
              )}
              <span className="info-pill">
                {t("transit.ayanamsa")}: <strong className="text-indigo">{ayanamsaLabel}</strong>
              </span>
            </div>

            <div className="chart-grid mt-xl">
              <div className="ui-card ui-card--accent ui-card--pad-lg">
                <h3 className="ui-card-header ui-card-header--sm">
                  <Compass size={18} /> {t("tp.chart")}
                </h3>
                <Kundali
                  planets={planets}
                  lagna={result.lagna}
                  exportable
                  title={`${t("tp.title")} — ${result.label || ""}`}
                />
              </div>

              <div className="ui-card ui-card--accent-indigo ui-card--pad-lg">
                <h3 className="ui-card-header ui-card-header--sm">
                  <Star size={18} /> {t("tp.placements")}
                </h3>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("tp.planet")}</th>
                        <th>{t("tp.sign")}</th>
                        <th>{t("tp.house")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orderedPlanets.map(([p, v]) => (
                        <tr key={p}>
                          <td className="fw-700">
                            <span className="text-saffron">{PLANET_ABBR[p] || p}</span> {p}
                          </td>
                          <td className="text-secondary">
                            {v.sign_name} <span className="text-muted">{v.degrees}°</span>
                          </td>
                          <td className="text-indigo">{v.house}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Sahams + Tajaka yogas — annual rung only (see above). */}
            {sahams.length > 0 && (
              <div className="ui-card ui-card--accent-gold ui-card--flush mt-xl">
                <h3 className="ui-card-header ui-card-header--sm">
                  <Star size={20} /> {t("tp.sahams")}
                </h3>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("tp.saham")}</th>
                        <th>{t("tp.sign")}</th>
                        <th>{t("tp.house")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sahams.map((s, i) => (
                        <tr key={i}>
                          <td className="fw-700 text-saffron">{s.name}</td>
                          <td className="text-secondary">
                            {s.sign_name} <span className="text-muted">{s.degrees}°</span>
                          </td>
                          <td className="text-indigo">{s.house}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {tajakaYogas.length > 0 && (
              <div className="ui-card ui-card--accent-indigo ui-card--flush mt-xl">
                <h3 className="ui-card-header ui-card-header--sm">
                  <Sparkles size={20} /> {t("tp.tajakaYogas")}
                </h3>
                <div className="digest-highlights">
                  {tajakaYogas.map((y, i) => (
                    <div key={i} className="digest-hl">
                      <strong className="text-saffron">{y.name}</strong>
                      {y.pair ? ` (${y.pair.join(" / ")})` : ""}
                      {y.description ? ` — ${y.description}` : ""}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* The window's compressed Tithi Ashtottari — on every rung. */}
            <div className="ui-card ui-card--accent-indigo ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm" style={{ fontSize: "1.25rem" }}>
                <Clock size={20} /> {t("tp.dasha")}
              </h3>
              {ta?.periods?.length > 0 ? (
                <>
                  <p className="card-intro">{ta.system}</p>
                  <p className="card-note">{t("tp.dashaHint")}</p>
                  <TithiAshtottariTree periods={ta.periods} birthDetails={birthDetails} />
                </>
              ) : (
                <p className="card-note">{t("tp.noDasha")}</p>
              )}
            </div>

            {/* AI reading of whichever window is on screen. */}
            <div className="mt-xl">
              <Card title={t("tp.aiTitle")} icon={<Sparkles size={24} />} accent="gold">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("tp.aiHint")}</p>}
                {aiLoading && <LoadingState message={t("tp.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">{t("tp.aiModel", { model: aiModel })}</div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="btn btn-primary mt-md" onClick={handleAi}>
                    <Sparkles size={16} />{" "}
                    {aiAnalysis ? t("tp.aiRegenerate") : t("tp.aiGenerate")}
                  </button>
                )}
                <p className="card-note mt-md">{t("tp.disclaimer")}</p>
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};
