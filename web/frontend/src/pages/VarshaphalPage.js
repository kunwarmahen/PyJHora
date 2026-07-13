import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CalendarClock, Sparkles, Star, Compass, Clock, Sun, Moon } from "lucide-react";
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
import { TithiAshtottariTree } from "../components/TithiAshtottariTree";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { PLANET_ABBR, AYANAMSAS } from "../constants/jyotish";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

const PLANET_ORDER = [
  "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu",
];

// Selectable annual-dasha systems (labels are i18n keys). Keys match the backend
// VARSHA_DASHA_SYSTEMS. Mudda + Patyayini are planet-ruled; Narayana is sign-ruled.
const DASHA_SYSTEMS = [
  { key: "mudda", labelKey: "varshaphal.dashaMudda" },
  { key: "patyayini", labelKey: "varshaphal.dashaPatyayini" },
  { key: "narayana", labelKey: "varshaphal.dashaNarayana" },
];

const ordinal = (n) => {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
};

const formatDate = (dateStr, locale = "en-US") => {
  if (!dateStr) return "—";
  try {
    // A bare "YYYY-MM-DD" is parsed by JS as *UTC* midnight, so west of Greenwich
    // it renders as the previous day — the pravesha date would disagree with the
    // pravesha instant shown beside it. Pin date-only strings to local midnight.
    const local = /^\d{4}-\d{2}-\d{2}$/.test(dateStr) ? `${dateStr}T00:00:00` : dateStr;
    return new Date(local).toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch (e) {
    return "—";
  }
};

// Read the model the user already picked in "Ask Astrologer".
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

export const VarshaphalPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const birthYear = selectedProfile?.birth_details?.dob
    ? parseInt(selectedProfile.birth_details.dob.split("-")[0], 10)
    : 1900;
  const [year, setYear] = useState(() => new Date().getFullYear());

  const [dashaSystem, setDashaSystem] = useState(
    () => localStorage.getItem("varsha_dasha") || "mudda"
  );
  const [dashaLoading, setDashaLoading] = useState(false);
  // The main fetch reads the dasha system via a ref so a system change does NOT
  // recreate loadVarshaphal / trigger the full-page reload — switching systems is
  // handled by changeDasha (a soft, in-place update of just the dasha table).
  const dashaRef = useRef(dashaSystem);
  useEffect(() => {
    dashaRef.current = dashaSystem;
  }, [dashaSystem]);

  const { settings } = useSettings();
  const chartStyle = settings.chartStyle;
  const ayanamsa = settings.ayanamsa;
  const ayanamsaLabel = AYANAMSAS.find((a) => a.value === ayanamsa)?.label || ayanamsa;

  // Which annual return this page shows: "solar" = Varshaphal (Tajaka solar
  // return), "lunar" = Tithi Pravesha (the natal tithi + lunar month recurring).
  // Defaults to the global setting; overridable here per reading.
  const [basis, setBasis] = useState(settings.praveshaBasis || "solar");
  useEffect(() => setBasis(settings.praveshaBasis || "solar"), [settings.praveshaBasis]);

  const stepYear = (delta) => setYear((y) => Math.max(birthYear, y + delta));

  // Switching dasha system only changes the annual-dasha table, so refresh it
  // in place (no full-page loading state / scroll jump). Falls back gracefully.
  const changeDasha = async (key) => {
    if (key === dashaSystem) return;
    setDashaSystem(key);
    localStorage.setItem("varsha_dasha", key);
    if (!birthDetails) return;
    setDashaLoading(true);
    try {
      const res = await astrologyService.getVarshaphal(birthDetails, year, ayanamsa, key);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("varshaphal.calcError"));
    } finally {
      setDashaLoading(false);
    }
  };

  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");
  // Reopen a saved reading from History: restore the year, then apply the exact
  // saved text once the factual (chart) load has settled so it isn't clobbered.
  const [pendingReading, setPendingReading] = useState(null);
  useRestoreReading((r) => {
    if (r.context?.year != null) setYear(r.context.year);
    // Both annual returns land on this page, so restore the one the reading was
    // actually generated from (History deep-links tithi_pravesha here too).
    if (r.source === "tithi_pravesha") setBasis("lunar");
    else if (r.source === "varshaphal") setBasis("solar");
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

  const loadVarshaphal = useCallback(async () => {
    if (!birthDetails) return;
    setLoading(true);
    setError("");
    // A new year (or basis) invalidates the previous AI reading.
    setAiAnalysis("");
    setAiError("");
    setAiModel("");
    try {
      // Solar = Varshaphal (Tajaka solar return). Lunar = Tithi Pravesha (the
      // lunar return). Both compute layers return the same shape — lagna /
      // planets / muntha / year_lord / sahams / tajaka_yogas / annual_dasha — so
      // everything below renders from `result` regardless of which was fetched.
      const res =
        basis === "lunar"
          ? await astrologyService.getTithiPravesha(birthDetails, { year, ayanamsa })
          : await astrologyService.getVarshaphal(birthDetails, year, ayanamsa, dashaRef.current);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("varshaphal.calcError"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, year, ayanamsa, basis, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    loadVarshaphal();
  }, [selectedProfile, navigate, loadVarshaphal]);

  const handleAi = async () => {
    if (!birthDetails) return;
    setAiLoading(true);
    setAiError("");
    try {
      const res =
        basis === "lunar"
          ? await astrologyService.analyzeTithiPraveshaAI(
              birthDetails,
              { year, personName: birthDetails.name },
              { ...readModelConfig(), ayanamsa }
            )
          : await astrologyService.analyzeVarshaphalAI(
              birthDetails,
              year,
              { personName: birthDetails.name },
              { ...readModelConfig(), ayanamsa }
            );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("varshaphal.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const isLunar = basis === "lunar";
  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;
  const planets = result?.planets || {};
  const orderedPlanets = PLANET_ORDER.filter((p) => planets[p]).map((p) => [p, planets[p]]);
  const sahams = result?.sahams || [];
  const tajakaYogas = result?.tajaka_yogas || [];
  // Lunar returns the compressed Tithi Ashtottari; solar returns Mudda/Patyayini/
  // Narayana. Both land under `annual_dasha`, so the table below reads either.
  const annualDasha = result?.tithi_ashtottari || result?.annual_dasha;
  const periods = annualDasha?.periods || [];

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<CalendarClock size={24} />}
        title={t(isLunar ? "varshaphal.titleLunar" : "varshaphal.title")}
        subtitle={t(isLunar ? "varshaphal.subtitleLunar" : "varshaphal.subtitle")}
        accent="gold"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />
        <RecentReadings source={isLunar ? "tithi_pravesha" : "varshaphal"} profileId={selectedProfile?._id} />

        {/* Controls */}
        <div className="page-controls">
          <div className="controls-group">
            <label className="control-label">
              <CalendarClock size={18} style={{ color: "var(--saffron)" }} />
              {t("varshaphal.year")}
            </label>
            <div className="stepper">
              <button
                type="button"
                className="stepper__btn"
                onClick={() => stepYear(-1)}
                aria-label="-1 year"
                disabled={year <= birthYear}
              >
                −
              </button>
              <input
                type="number"
                className="control-input"
                style={{ width: "6rem", textAlign: "center" }}
                value={year}
                min={birthYear}
                onChange={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (!Number.isNaN(v)) setYear(Math.max(birthYear, v));
                }}
              />
              <button
                type="button"
                className="stepper__btn"
                onClick={() => stepYear(1)}
                aria-label="+1 year"
              >
                +
              </button>
            </div>
          </div>

          {/* Annual-dasha system picker — MIDDLE, and solar only. The lunar return
              is paired with Tithi Ashtottari (a tithi-reckoned dasha for a
              tithi-reckoned chart), which has no alternatives to choose between.
              It must render BEFORE the basis toggle: `.page-controls` is
              space-between, so keeping the basis toggle last pins it to the right
              whether or not this picker is present (otherwise it hops
              middle↔right as you switch basis). */}
          {!isLunar && (
            <div className="controls-group">
              <label className="control-label">
                <Clock size={18} style={{ color: "var(--saffron)" }} />
                {t("varshaphal.annualDasha")}
              </label>
              <div className="chart-toggle">
                {DASHA_SYSTEMS.map((s) => (
                  <button
                    key={s.key}
                    className={`chart-toggle__btn${dashaSystem === s.key ? " is-active" : ""}`}
                    onClick={() => changeDasha(s.key)}
                  >
                    {t(s.labelKey)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Which annual return: solar (Varshaphal) or lunar (Tithi Pravesha).
              Always rendered LAST so space-between keeps it hard right. */}
          <div className="controls-group controls-group--end">
            <label className="control-label">
              <Moon size={18} style={{ color: "var(--saffron)" }} />
              {t("varshaphal.basis")}
            </label>
            <div className="chart-toggle" role="group" aria-label={t("varshaphal.basis")}>
              <button
                type="button"
                className={`chart-toggle__btn${!isLunar ? " is-active" : ""}`}
                aria-pressed={!isLunar}
                onClick={() => setBasis("solar")}
                title={t("varshaphal.basisSolarHint")}
              >
                <Sun size={14} /> {t("varshaphal.basisSolar")}
              </button>
              <button
                type="button"
                className={`chart-toggle__btn${isLunar ? " is-active" : ""}`}
                aria-pressed={isLunar}
                onClick={() => setBasis("lunar")}
                title={t("varshaphal.basisLunarHint")}
              >
                <Moon size={14} /> {t("varshaphal.basisLunar")}
              </button>
            </div>
          </div>
        </div>

        {/* What window this reading actually covers, and the instant the chart is
            cast at — the pravesha moment is solved in degrees, not rounded to the
            day, so it is worth showing (it drives both the lagna and the dasha). */}
        {isLunar && result?.window && (
          <p className="settings-hint">
            {t("varshaphal.lunarWindow", {
              start: result.window.start,
              end: result.window.end,
              days: result.window.span_days,
              tithi: result.label || "",
            })}
            {result.window.start_at && (
              <>
                <br />
                {t("varshaphal.lunarEntryAt", {
                  at: result.window.start_at.replace("T", " "),
                })}
              </>
            )}
          </p>
        )}

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("varshaphal.loading")} />
          </Card>
        ) : result ? (
          <div className="fade-in">
            {/* Year summary */}
            <div className="info-pills">
              <span className="info-pill">
                {t("varshaphal.forYear")}:{" "}
                <strong className="text-saffron">{isLunar ? year : result.year}</strong>
              </span>
              <span className="info-pill">
                {isLunar ? t("varshaphal.lunarYearBegins") : t("varshaphal.solarYearBegins")}:{" "}
                <strong>
                  {formatDate(isLunar ? result.window?.start : result.year_entry?.date, locale)}
                </strong>
                {!isLunar && result.year_entry?.time ? `, ${result.year_entry.time}` : ""}
              </span>
              {isLunar && result.label && (
                <span className="info-pill">
                  {t("varshaphal.entryTithi")}:{" "}
                  <strong className="text-vermillion">{result.label}</strong>
                </span>
              )}
              <span className="info-pill">
                {isLunar ? t("varshaphal.tpLagna") : t("varshaphal.annualLagna")}:{" "}
                <strong className="text-indigo">{result.lagna?.sign_name}</strong>
              </span>
              <span className="info-pill">
                {t("varshaphal.muntha")}:{" "}
                <strong className="text-saffron">{result.muntha?.sign_name}</strong>
                {result.muntha?.house ? ` (${ordinal(result.muntha.house)} ${t("varshaphal.houseWord")})` : ""}
              </span>
              <span className="info-pill">
                {t("varshaphal.yearLord")}:{" "}
                <strong className="text-vermillion">
                  {result.year_lord?.planet || "—"}
                </strong>
              </span>
              <span className="info-pill">
                {t("transit.ayanamsa")}: <strong className="text-indigo">{ayanamsaLabel}</strong>
              </span>
            </div>

            <div className="chart-grid">
              {/* Annual (Tajaka) chart */}
              <Kundali
                planets={planets}
                lagna={result.lagna}
                title={t("varshaphal.annualChart", { year: result.year })}
                subtitle={t("varshaphal.tajaka")}
                exportable
              />

              {/* Annual placements table */}
              <div className="ui-card ui-card--accent-gold ui-card--pad-lg ui-card--flush">
                <h3 className="ui-card-header ui-card-header--sm">
                  <Compass size={18} />
                  {t("varshaphal.placements")}
                </h3>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("common.planet")}</th>
                        <th>{t("common.sign")}</th>
                        <th className="text-center">{t("varshaphal.houseWord")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orderedPlanets.map(([name, p]) => (
                        <tr key={name}>
                          <td className="fw-700 text-indigo">
                            {PLANET_ABBR[name] || name}{" "}
                            <span style={{ fontWeight: 400 }} className="text-secondary">
                              {name}
                            </span>
                          </td>
                          <td>
                            {p.sign_name}{" "}
                            <span className="text-muted">
                              {p.degrees != null ? `${p.degrees.toFixed(1)}°` : ""}
                            </span>
                          </td>
                          <td className="text-center fw-600 text-saffron">
                            {ordinal(p.house)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="card-note">{t("varshaphal.houseNote")}</p>
              </div>
            </div>

            {/* Sahams */}
            {sahams.length > 0 && (
              <div className="ui-card ui-card--accent ui-card--flush mt-xl">
                <h3 className="ui-card-header ui-card-header--sm" style={{ fontSize: "1.25rem" }}>
                  <Star size={20} />
                  {t("varshaphal.sahams")}
                </h3>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("varshaphal.saham")}</th>
                        <th>{t("varshaphal.significance")}</th>
                        <th>{t("common.sign")}</th>
                        <th className="text-center">{t("varshaphal.houseWord")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sahams.map((s) => (
                        <tr key={s.name}>
                          <td className="fw-700 text-saffron">{s.name}</td>
                          <td className="text-secondary">{s.significance}</td>
                          <td>
                            {s.sign_name}{" "}
                            <span className="text-muted">
                              {s.degrees != null ? `${s.degrees.toFixed(1)}°` : ""}
                            </span>
                          </td>
                          <td className="text-center fw-600 text-indigo">{ordinal(s.house)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Tajaka yogas */}
            <div className="ui-card ui-card--accent-gold ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm" style={{ fontSize: "1.25rem" }}>
                <Sparkles size={20} />
                {t("varshaphal.tajakaYogas")}
              </h3>
              {tajakaYogas.length > 0 ? (
                <div className="card-grid">
                  {tajakaYogas.map((y, i) => (
                    <div key={i} className="ui-card ui-card--pad-lg">
                      <div className="fw-700 text-saffron">
                        {y.name}
                        {y.pair && (
                          <span className="text-secondary fw-400"> · {y.pair.join(" – ")}</span>
                        )}
                      </div>
                      <div className="text-secondary" style={{ fontSize: "0.85rem", marginTop: "0.35rem" }}>
                        {y.description}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="card-note">{t("varshaphal.noYogas")}</p>
              )}
            </div>

            {/* Annual dasha */}
            <div className="ui-card ui-card--accent-indigo ui-card--flush mt-xl">
              <h3 className="ui-card-header ui-card-header--sm" style={{ fontSize: "1.25rem" }}>
                <Clock size={20} />
                {t("varshaphal.annualDasha")}
              </h3>
              <p className="card-intro">{annualDasha?.system}</p>

              {dashaLoading ? (
                <LoadingState message={t("varshaphal.loading")} />
              ) : /* The lunar return's dasha is a tree, not a table: the whole
                     108-unit Ashtottari cycle compressed into this one lunar year,
                     drillable to six levels. The solar (Tajaka) dashas stay a flat
                     table — they have no sub-levels to open. */
              annualDasha?.expandable && periods.length > 0 ? (
                <>
                  <p className="card-note">
                    {t("varshaphal.taDrillHint", {
                      months: annualDasha?.lunar_months,
                    })}
                  </p>
                  <TithiAshtottariTree periods={periods} birthDetails={birthDetails} />
                </>
              ) : periods.length > 0 ? (
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>
                          {annualDasha?.lord_type === "raasi"
                            ? t("varshaphal.periodSign")
                            : t("varshaphal.period")}
                        </th>
                        <th>{t("varshaphal.from")}</th>
                        <th>{t("varshaphal.to")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {periods.map((p, i) => (
                        <tr key={i} className={p.current ? "is-current" : ""}>
                          <td className="fw-700 text-indigo">
                            {p.lord_name}
                            {p.current && (
                              <span className="info-pill" style={{ marginLeft: "0.5rem" }}>
                                {t("varshaphal.current")}
                              </span>
                            )}
                          </td>
                          <td className="text-secondary">{formatDate(p.start, locale)}</td>
                          <td className="text-secondary">{formatDate(p.end, locale)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="card-note">{t("varshaphal.noDasha")}</p>
              )}
            </div>

            {/* AI year-ahead reading */}
            <div className="mt-xl">
              <Card title={t("varshaphal.aiTitle")} icon={<Sparkles size={24} />} accent="gold">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("varshaphal.aiHint")}</p>}
                {aiLoading && <LoadingState message={t("varshaphal.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">
                        {t("varshaphal.aiModel", { model: aiModel })}
                      </div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("varshaphal.aiRegenerate") : t("varshaphal.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("varshaphal.disclaimer")}</p>
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};
