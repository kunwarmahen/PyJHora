import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import {
  Heart, User, Users, Sparkles, GitCompareArrows, Grid3x3, ListChecks, Flame,
  Home, CalendarRange, Shield,
} from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { formatDate, orDash, errorMessage } from "../utils/format";
import { astrologyService } from "../services/api";
import { useRestoreReading } from "../hooks/useRestoreReading";
import { RecentReadings } from "../components/RecentReadings";
import { PageHeader } from "../components/PageHeader";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { MarriageTimeline } from "../components/MarriageTimeline";
import { useSettings } from "../contexts/SettingsContext";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

// Read the model config the user already picked in "Ask Astrologer". The server
// resolves the actual API key (per-user stored key → env key), so we only need
// the provider/model selection here — no key handling on this page.
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

const toBirthDetails = (p) => ({
  name: p.birth_details.name,
  dob: p.birth_details.dob,
  tob: p.birth_details.tob,
  place: p.birth_details.place,
  latitude: parseFloat(p.birth_details.latitude),
  longitude: parseFloat(p.birth_details.longitude),
  timezone: parseFloat(p.birth_details.timezone),
});

// Marriage significators whose Mahadasha activates relationship themes for a
// person: their own 7th lord plus the two universal karakas (Venus, Jupiter).
const significantLords = (person) => {
  const s = new Set(["Venus", "Jupiter"]);
  if (person?.seventh_lord) s.add(person.seventh_lord);
  return s;
};

// One partner's 7th-house deep-dive card (§2.6).
const SeventhPersonCard = ({ t, name, m, accent }) => {
  if (!m) return null;
  const lord = m.seventh_lord_condition || {};
  const ven = m.karakas?.Venus || {};
  const jup = m.karakas?.Jupiter || {};
  const cond = (c) =>
    c && c.sign
      ? `${c.sign} · ${t("compat.seventh.house")} ${c.house} · ${c.dignity}${
          c.retrograde ? ` · ${t("compat.seventh.retro")}` : ""
        } · ${t("compat.seventh.navamsa")} ${c.navamsa_sign}`
      : "—";
  return (
    <div className={`ui-card ui-card--pad-lg ui-card--accent-${accent === "saffron" ? "saffron" : "vermillion"}`}>
      <h5 className="compat-person__name">{name}</h5>
      <div className="detail-list">
        <div>
          <strong>{t("compat.seventh.lagna")}:</strong> {m.lagna_sign}
        </div>
        <div>
          <strong>{t("compat.seventh.seventhSign")}:</strong> {m.seventh_sign}
        </div>
        <div>
          <strong>{t("compat.seventh.seventhLord")} ({m.seventh_lord}):</strong> {cond(lord)}
        </div>
        <div>
          <strong>{t("compat.seventh.occupants")}:</strong>{" "}
          {m.occupants?.length
            ? m.occupants.map((o) => `${o.name} (${o.dignity})`).join(", ")
            : t("compat.seventh.none")}
        </div>
        <div>
          <strong>{t("compat.seventh.venus")}:</strong> {cond(ven)}
        </div>
        <div>
          <strong>{t("compat.seventh.jupiter")}:</strong> {cond(jup)}
        </div>
        {m.upapada && (
          <div>
            <strong>{t("compat.seventh.upapada")}:</strong> {m.upapada.sign} ({m.upapada.lord})
          </div>
        )}
      </div>
    </div>
  );
};

const SeventhHousePanel = ({ t, marriage, nameA, nameB }) => {
  const sh = marriage?.seventh_house;
  if (!sh) return <p className="card-note">{t("compat.seventh.intro")}</p>;
  return (
    <div className="fade-in">
      <h4 className="card-subhead">
        <Home size={20} />
        {t("compat.seventh.title")}
      </h4>
      <p className="card-note">{t("compat.seventh.intro")}</p>
      <div className="person-grid">
        <SeventhPersonCard t={t} name={nameA} m={sh.male} accent="saffron" />
        <SeventhPersonCard t={t} name={nameB} m={sh.female} accent="vermillion" />
      </div>
    </div>
  );
};

// One partner's current Saturn (Sade Sati / Ashtama / Kantaka) status.
const SaturnOutlook = ({ t, name, data }) => {
  const cur = data?.current || {};
  const rows = [
    { key: "sadeSati", label: t("compat.timeline.sadeSati"), p: cur.sade_sati },
    { key: "ashtama", label: t("compat.timeline.ashtama"), p: cur.ashtama },
    { key: "kantaka", label: t("compat.timeline.kantaka"), p: cur.kantaka },
  ].filter((r) => r.p);
  return (
    <div className="ui-card ui-card--pad-lg">
      <h5 className="compat-person__name">{name}</h5>
      {rows.length ? (
        <ul className="detail-list">
          {rows.map((r) => (
            <li key={r.key} className="rem-row--weak">
              <strong>{r.label}</strong>
              {r.p?.current_phase ? ` — ${r.p.current_phase}` : ""}{" "}
              <span className="text-secondary">
                ({r.p.start_date} → {r.p.end_date})
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-secondary">{t("compat.timeline.clear")}</p>
      )}
    </div>
  );
};

export const CompatibilityPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile, profiles, loadProfiles } = useProfile();

  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;
  const chartStyle = settings.chartStyle;
  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;

  const [secondProfile, setSecondProfile] = useState(null);
  const [ctab, setCtab] = useState("ashtakoot");
  // Top-level workspace tab: Guna Milan (score) / 7th House / Timeline (§2.6).
  const [wtab, setWtab] = useState("guna");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [chartA, setChartA] = useState(null);
  const [chartB, setChartB] = useState(null);
  const [marriage, setMarriage] = useState(null);
  // Timeline data is fetched lazily the first time the Timeline tab is opened.
  const [dashaA, setDashaA] = useState(null);
  const [dashaB, setDashaB] = useState(null);
  const [saturnA, setSaturnA] = useState(null);
  const [saturnB, setSaturnB] = useState(null);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineError, setTimelineError] = useState("");

  // AI analysis is on-demand (uses the model picked in "Ask Astrologer").
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");
  // Reopen a saved reading from History: recompute the (result-gated) score +
  // both charts from the saved pair so the saved reading is visible. Factual
  // only — no AI re-generation.
  const [pendingReading, setPendingReading] = useState(null);
  useRestoreReading((r) => setPendingReading({ reading: r.reading, model: r.model, context: r.context }));
  useEffect(() => {
    if (pendingReading && !loading) {
      const c = pendingReading.context || {};
      setAiAnalysis(pendingReading.reading);
      setAiModel(pendingReading.model);
      if (c.male_details && c.female_details) {
        Promise.all([
          astrologyService.getCompatibility(c.male_details, c.female_details),
          astrologyService.calculateBirthChart(c.male_details, c.ayanamsa),
          astrologyService.calculateBirthChart(c.female_details, c.ayanamsa),
        ])
          .then(([compat, ra, rb]) => {
            if (!compat.data?.error) {
              setResult(compat.data);
              setChartA(ra.data);
              setChartB(rb.data);
            }
          })
          .catch(() => {});
      }
      setPendingReading(null);
    }
  }, [pendingReading, loading]);

  // Redirect if no profile selected
  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }

    loadProfiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, navigate]);

  const resetResults = () => {
    setResult(null);
    setChartA(null);
    setChartB(null);
    setMarriage(null);
    setDashaA(null);
    setDashaB(null);
    setSaturnA(null);
    setSaturnB(null);
    setTimelineError("");
    setWtab("guna");
    setAiAnalysis("");
    setAiError("");
    setAiModel("");
  };

  const handleCalculate = async () => {
    if (!secondProfile) {
      setError(t("compat.errSelectSecond"));
      return;
    }

    setLoading(true);
    setError("");
    setAiAnalysis("");
    setAiError("");

    const person1Data = toBirthDetails(selectedProfile);
    const person2Data = toBirthDetails(secondProfile);

    try {
      // Score + both birth charts (D1 + D9) + the 7th-house workspace in
      // parallel — the charts power the side-by-side visual comparison, the
      // score powers the Ashtakoot breakdown, the workspace the 7th-house tab.
      const [compat, ra, rb, mw] = await Promise.all([
        astrologyService.getCompatibility(person1Data, person2Data),
        astrologyService.calculateBirthChart(person1Data, ayanamsa),
        astrologyService.calculateBirthChart(person2Data, ayanamsa),
        astrologyService.getMarriageWorkspace(person1Data, person2Data, ayanamsa).catch(() => null),
      ]);
      if (compat.data?.error) {
        setError(compat.data.error);
        return;
      }
      setResult(compat.data);
      setChartA(ra.data);
      setChartB(rb.data);
      if (mw?.data?.status === "success") setMarriage(mw.data);
    } catch (err) {
      setError(errorMessage(err, t("compat.calcError")));
    } finally {
      setLoading(false);
    }
  };

  // Lazily load the dasha-overlap + Saturn-outlook data the first time the
  // Timeline tab is opened (heavier calls kept off the main compatibility path).
  useEffect(() => {
    if (wtab !== "timeline" || !result || !secondProfile) return;
    if (dashaA && dashaB) return; // already loaded
    let cancelled = false;
    const p1 = toBirthDetails(selectedProfile);
    const p2 = toBirthDetails(secondProfile);
    setTimelineLoading(true);
    setTimelineError("");
    Promise.all([
      astrologyService.getDhasa(p1),
      astrologyService.getDhasa(p2),
      astrologyService.getSaturnTransits(p1, ayanamsa).catch(() => null),
      astrologyService.getSaturnTransits(p2, ayanamsa).catch(() => null),
    ])
      .then(([da, db, sa, sb]) => {
        if (cancelled) return;
        setDashaA(da.data);
        setDashaB(db.data);
        setSaturnA(sa?.data || null);
        setSaturnB(sb?.data || null);
      })
      .catch(() => {
        if (!cancelled) setTimelineError(t("compat.timeline.error"));
      })
      .finally(() => {
        if (!cancelled) setTimelineLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wtab, result, secondProfile]);

  const handleAiAnalysis = async () => {
    if (!secondProfile) return;
    setAiLoading(true);
    setAiError("");
    try {
      const response = await astrologyService.analyzeCompatibilityAI(
        toBirthDetails(selectedProfile),
        toBirthDetails(secondProfile),
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(response.data.ai_analysis || "");
      setAiModel(response.data.model || response.data.provider || "");
    } catch (err) {
      setAiError(errorMessage(err, t("compat.aiError")));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) {
    return null;
  }

  const nameA = selectedProfile.profile_name;
  const nameB = secondProfile?.profile_name || t("compare.person2");

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Heart size={24} />}
        title={t("compat.title")}
        subtitle={t("compat.subtitle")}
        accent="saffron"
      />

      {/* Content */}
      <div className="dashboard-content">
        <RecentReadings source="compatibility" />
        <ErrorBanner message={error} />

        {/* Profile Selection Card */}
        <div className="ui-card ui-card--accent fade-in">
          <h3 className="ui-card-header">
            <Users size={24} />
            {t("compat.selectProfiles")}
          </h3>

          <div className="person-grid">
            {/* Person 1 - Selected Profile */}
            <div className="compat-person compat-person--a">
              <h4 className="compat-person__head">
                <User size={20} /> {t("compare.person1")}
              </h4>
              <div className="compat-person__card">
                <p className="compat-person__name">{selectedProfile.profile_name}</p>
                <div className="detail-list">
                  <div>
                    <strong>{t("common.name")}:</strong>{" "}
                    {selectedProfile.birth_details.name || t("common.anonymous")}
                  </div>
                  <div>
                    <strong>{t("common.dateOfBirth")}:</strong>{" "}
                    {formatDate(selectedProfile.birth_details.dob)}
                  </div>
                  <div>
                    <strong>{t("common.timeOfBirth")}:</strong>{" "}
                    {orDash(selectedProfile.birth_details.tob)}
                  </div>
                  <div>
                    <strong>{t("common.place")}:</strong>{" "}
                    {orDash(selectedProfile.birth_details.place)}
                  </div>
                </div>
              </div>
            </div>

            {/* Person 2 - Select from profiles */}
            <div className="compat-person compat-person--b">
              <h4 className="compat-person__head">
                <User size={20} /> {t("compare.person2")}
              </h4>
              <label className="compat-person__select-label">{t("compat.selectToCompare")}</label>
              <select
                className="form-select"
                value={secondProfile?._id || ""}
                onChange={(e) => {
                  const profile = profiles.find((p) => p._id === e.target.value);
                  setSecondProfile(profile || null);
                  resetResults();
                }}
              >
                <option value="">{t("compat.selectPlaceholder")}</option>
                {profiles
                  .filter((p) => p._id !== selectedProfile._id)
                  .map((profile) => (
                    <option key={profile._id} value={profile._id}>
                      {profile.profile_name} ({profile.birth_details.name || t("common.anonymous")})
                    </option>
                  ))}
              </select>

              {secondProfile && (
                <div className="compat-person__card is-spaced">
                  <p className="compat-person__name">{secondProfile.profile_name}</p>
                  <div className="detail-list">
                    <div>
                      <strong>{t("common.name")}:</strong>{" "}
                      {secondProfile.birth_details.name || t("common.anonymous")}
                    </div>
                    <div>
                      <strong>{t("common.dateOfBirth")}:</strong>{" "}
                      {formatDate(secondProfile.birth_details.dob)}
                    </div>
                    <div>
                      <strong>{t("common.timeOfBirth")}:</strong>{" "}
                      {orDash(secondProfile.birth_details.tob)}
                    </div>
                    <div>
                      <strong>{t("common.place")}:</strong>{" "}
                      {orDash(secondProfile.birth_details.place)}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Calculate Button */}
          <button
            className="ui-btn ui-btn--primary ui-btn--block ui-btn--lg"
            style={{ marginTop: "var(--space-lg)" }}
            onClick={handleCalculate}
            disabled={loading || !secondProfile}
          >
            <Heart size={20} />
            {loading ? t("compat.calculating") : t("compat.check")}
          </button>
        </div>

        {/* Loading State */}
        {loading && (
          <Card>
            <LoadingState message={t("compat.loading")} />
          </Card>
        )}

        {/* Results */}
        {result && !loading && (
          <div className="ui-card ui-card--accent fade-in">
            <h3 className="ui-card-header">
              <Heart size={24} />
              {t("compat.results")}
            </h3>

            {/* Total Score Display */}
            <div className="score-box">
              <div className="score-box__label">{t("compat.totalScore")}</div>
              <div className="score-box__value">
                {result.total_score}
                <span className="score-box__value-max">/{result.max_score || 36}</span>
              </div>
              <div className="score-box__status">
                {t("compat.status")}: {result.status}
              </div>
              {(result.boy?.nakshatra || result.girl?.nakshatra) && (
                <div className="score-box__nakshatras">
                  {nameA}: {result.boy?.nakshatra} ({t("compat.pada")} {result.boy?.pada}) &nbsp;•&nbsp;{" "}
                  {nameB}: {result.girl?.nakshatra} ({t("compat.pada")} {result.girl?.pada})
                </div>
              )}
            </div>

            {/* Workspace tabs: Guna Milan / 7th House / Timeline (§2.6) */}
            <div className="chart-toggle chart-toggle--workspace" style={{ marginTop: "var(--space-lg)" }}>
              <button className={`chart-toggle__btn ${wtab === "guna" ? "is-active" : ""}`} onClick={() => setWtab("guna")}>
                <Heart size={16} /> {t("compat.ws.gunaMilan")}
              </button>
              <button className={`chart-toggle__btn ${wtab === "seventh" ? "is-active" : ""}`} onClick={() => setWtab("seventh")}>
                <Home size={16} /> {t("compat.ws.seventhHouse")}
              </button>
              <button className={`chart-toggle__btn ${wtab === "timeline" ? "is-active" : ""}`} onClick={() => setWtab("timeline")}>
                <CalendarRange size={16} /> {t("compat.ws.timeline")}
              </button>
            </div>

            {wtab === "guna" && (
            <>
            {/* System tabs: Ashtakoot / Dashakoota / Mangal dosha */}
            <div className="chart-toggle" style={{ marginTop: "var(--space-lg)" }}>
              <button className={`chart-toggle__btn ${ctab === "ashtakoot" ? "is-active" : ""}`} onClick={() => setCtab("ashtakoot")}>
                <Grid3x3 size={16} /> {t("compat.tabs.ashtakoot")}
              </button>
              <button className={`chart-toggle__btn ${ctab === "dashakoota" ? "is-active" : ""}`} onClick={() => setCtab("dashakoota")}>
                <ListChecks size={16} /> {t("compat.tabs.dashakoota")}
              </button>
              <button className={`chart-toggle__btn ${ctab === "mangal" ? "is-active" : ""}`} onClick={() => setCtab("mangal")}>
                <Flame size={16} /> {t("compat.tabs.mangal")}
              </button>
            </div>

            {/* Ashtakoot Breakdown */}
            {ctab === "ashtakoot" && (
              <>
                <h4 className="card-subhead">{t("compat.breakdown")}</h4>
                <div className="koota-grid">
                  {(result.kootas || []).map((koota) => {
                    const tier =
                      koota.score >= koota.max * 0.7
                        ? "good"
                        : koota.score >= koota.max * 0.4
                          ? "mid"
                          : "low";
                    return (
                      <div key={koota.key} className="koota-card" title={koota.description}>
                        <div className="koota-card__name">{koota.name}</div>
                        <div className={`koota-card__score koota-card__score--${tier}`}>
                          {koota.score}
                        </div>
                        <div className="koota-card__max">{t("compat.outOf", { max: koota.max })}</div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}

            {/* Dashakoota (South / Tamil 10-porutham) */}
            {ctab === "dashakoota" && result.dashakoota && (
              <>
                <h4 className="card-subhead">
                  {t("compat.dashakoota.title")} — {result.dashakoota.score}/{result.dashakoota.max}
                </h4>
                <p className="card-note">{t("compat.dashakoota.intro")}</p>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("compat.dashakoota.porutham")}</th>
                        <th>{t("compat.dashakoota.status")}</th>
                        <th>{t("compat.dashakoota.meaning")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.dashakoota.poruthams.map((p) => (
                        <tr key={p.key} className={p.ok ? "" : "rem-row--weak"}>
                          <td><strong>{p.name}</strong></td>
                          <td>{p.ok ? "✓ " + t("compat.dashakoota.ok") : "✕ " + t("compat.dashakoota.no")}</td>
                          <td className="text-secondary">{p.description}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {/* Mangal (Kuja) dosha */}
            {ctab === "mangal" && result.mangal_dosha && (
              <>
                <h4 className="card-subhead">{t("compat.mangal.title")}</h4>
                <p className="score-box__status" style={{ marginBottom: "var(--space-md)" }}>
                  {result.mangal_dosha.verdict}
                </p>
                <div className="person-grid">
                  {[
                    { key: "boy", name: nameA, m: result.mangal_dosha.boy },
                    { key: "girl", name: nameB, m: result.mangal_dosha.girl },
                  ].map(({ key, name, m }) => (
                    <div key={key} className="ui-card ui-card--pad-lg">
                      <h5 className="compat-person__name">{name}</h5>
                      <p>
                        <strong>{t("compat.mangal.status")}:</strong>{" "}
                        {m.manglik ? t("compat.mangal.manglik") : t("compat.mangal.notManglik")}
                        {" "}({t("compat.mangal.marsIn", { sign: m.mars_sign })})
                      </p>
                      {Object.keys(m.from || {}).length > 0 && (
                        <p className="text-secondary">
                          {t("compat.mangal.from")}:{" "}
                          {Object.entries(m.from)
                            .map(([ref, h]) => `${ref} (${h})`)
                            .join(", ")}
                        </p>
                      )}
                      {(m.cancellations || []).length > 0 && (
                        <ul className="detail-list">
                          {m.cancellations.map((c, i) => (
                            <li key={i}>{c}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* Side-by-side charts for visual comparison — Rasi (D1) + Navamsa (D9) */}
            {chartA && chartB && (
              <>
                <h4 className="card-subhead">
                  <GitCompareArrows size={20} />
                  {t("compat.charts")} — {t("varga.rasiD1", "Rasi (D1)")}
                </h4>
                <div className="chart-grid" style={{ marginBottom: "var(--space-xl)" }}>
                  <Card title={nameA} accent="saffron">
                    <Kundali planets={chartA.planets} lagna={chartA.lagna} title={nameA} exportable />
                  </Card>
                  <Card title={nameB} accent="vermillion">
                    <Kundali planets={chartB.planets} lagna={chartB.lagna} title={nameB} exportable />
                  </Card>
                </div>
                {chartA.d9_chart && chartB.d9_chart && (
                  <>
                    <h4 className="card-subhead">
                      <GitCompareArrows size={20} />
                      {t("compat.charts")} — {t("varga.navamsaD9", "Navamsa (D9) — marriage")}
                    </h4>
                    <div className="chart-grid" style={{ marginBottom: "var(--space-xl)" }}>
                      <Card title={nameA} accent="saffron">
                        <Kundali planets={chartA.d9_chart} lagna={chartA.d9_lagna} title={`${nameA} · D9`} exportable />
                      </Card>
                      <Card title={nameB} accent="vermillion">
                        <Kundali planets={chartB.d9_chart} lagna={chartB.d9_lagna} title={`${nameB} · D9`} exportable />
                      </Card>
                    </div>
                  </>
                )}
              </>
            )}
            </>
            )}

            {wtab === "seventh" && (
              <SeventhHousePanel t={t} marriage={marriage} nameA={nameA} nameB={nameB} />
            )}

            {wtab === "timeline" && (
              <div className="fade-in">
                <h4 className="card-subhead">
                  <CalendarRange size={20} />
                  {t("compat.timeline.title")}
                </h4>
                <p className="card-note">{t("compat.timeline.intro")}</p>
                {timelineError && <ErrorBanner message={timelineError} />}
                {timelineLoading ? (
                  <LoadingState message={t("compat.timeline.loading")} />
                ) : (
                  <>
                    <MarriageTimeline
                      t={t}
                      nameA={nameA}
                      nameB={nameB}
                      dashaA={dashaA}
                      dashaB={dashaB}
                      sigA={significantLords(marriage?.seventh_house?.male)}
                      sigB={significantLords(marriage?.seventh_house?.female)}
                    />
                    <h4 className="card-subhead" style={{ marginTop: "var(--space-xl)" }}>
                      <Shield size={20} />
                      {t("compat.timeline.saturnTitle")}
                    </h4>
                    <p className="card-note">{t("compat.timeline.saturnIntro")}</p>
                    <div className="person-grid">
                      <SaturnOutlook t={t} name={nameA} data={saturnA} accent="saffron" />
                      <SaturnOutlook t={t} name={nameB} data={saturnB} accent="vermillion" />
                    </div>
                  </>
                )}
              </div>
            )}

            {/* AI Analysis (on-demand) */}
            <div className="ai-panel">
              <h4 className="ai-panel__title">
                <Sparkles size={20} style={{ color: "var(--saffron)" }} />
                {t("compat.aiAnalysis")}
              </h4>

              <ErrorBanner message={aiError} />

              {!aiAnalysis && !aiLoading && <p className="ai-panel__hint">{t("compat.aiHint")}</p>}

              {aiLoading && <LoadingState message={t("compat.aiLoading")} />}

              {aiAnalysis && !aiLoading && (
                <div className="sbc-ai-markdown ai-panel__reading">
                  <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                  {aiModel && (
                    <div className="ai-panel__meta">{t("compat.aiModel", { model: aiModel })}</div>
                  )}
                </div>
              )}

              {!aiLoading && (
                <button className="ui-btn ui-btn--ai" onClick={handleAiAnalysis}>
                  <Sparkles size={18} />
                  {aiAnalysis ? t("compat.aiRegenerate") : t("compat.aiGenerate")}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
