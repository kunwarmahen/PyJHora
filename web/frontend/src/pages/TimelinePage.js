import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CalendarRange, Sparkles, Sun, Moon } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { useRestoreReading } from "../hooks/useRestoreReading";
import { RecentReadings } from "../components/RecentReadings";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { Card } from "../components/Card";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { useSettings } from "../contexts/SettingsContext";
import { intlLocale } from "../utils/format";
import "../styles/Dashboard.css";
import "../styles/Shared.css";
import "../styles/Timeline.css";

const readModelConfig = () => {
  const providerType = localStorage.getItem("ai_provider_type") || "ollama";
  return {
    providerType,
    model: localStorage.getItem("ai_model") || "",
    baseUrl:
      providerType === "ollama"
        ? localStorage.getItem("ai_base_url") || undefined
        : undefined,
    legacyProvider: providerType === "ollama" ? "qwen" : providerType,
    maxTokens: parseInt(localStorage.getItem("ai_max_tokens") || "0", 10) || undefined,
  };
};

// Classical-ish, distinct hues per graha (works on the saffron/cream ground).
const PLANET_COLORS = {
  Sun: "#E08A34",
  Moon: "#8C99A6",
  Mars: "#C0392B",
  Mercury: "#2E9E5B",
  Jupiter: "#D4A017",
  Venus: "#CF6B9E",
  Saturn: "#4A5568",
  Rahu: "#6B5B95",
  Ketu: "#8A6D3B",
};
const planetColor = (p) => PLANET_COLORS[p] || "#8a6a3a";

const PHASE_COLORS = {
  sade_sati: "#B23A48",
  ashtama: "#8E3B46",
  kantaka: "#C97B54",
};

const ms = (d) => new Date(`${d}T00:00:00`).getTime();

const formatDate = (dateStr, locale = "en-US") => {
  if (!dateStr) return "—";
  try {
    return new Date(`${dateStr}T00:00:00`).toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
};

// viewBox geometry (scales to any width via width:100%).
const W = 1000;
const PX0 = 8; // plot left
const PX1 = W - 8; // plot right
const PW = PX1 - PX0;

export const TimelinePage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();
  const { settings } = useSettings();
  const ayanamsa = settings.ayanamsa;

  const [span, setSpan] = useState(10); // ± years
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedDate, setSelectedDate] = useState(null);

  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");

  const svgRef = useRef(null);

  const [pendingReading, setPendingReading] = useState(null);
  useRestoreReading((r) => {
    if (r.context?.target_date) setSelectedDate(r.context.target_date);
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
    setAiAnalysis("");
    setAiError("");
    setSelectedDate(null);
    try {
      const res = await astrologyService.getLifeTimeline(birthDetails, {
        yearsBefore: span,
        yearsAfter: span,
        ayanamsa,
      });
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("timeline.calcError"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, span, ayanamsa, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    load();
  }, [selectedProfile, navigate, load]);

  // ── Date ⇄ x mapping over the display window ──────────────────────────
  const win = data?.window;
  const t0 = win ? ms(win.start_date) : 0;
  const t1 = win ? ms(win.end_date) : 1;
  const xFor = useCallback(
    (dateStr) => {
      const f = (ms(dateStr) - t0) / (t1 - t0 || 1);
      return PX0 + Math.max(0, Math.min(1, f)) * PW;
    },
    [t0, t1]
  );
  const dateAtX = useCallback(
    (xView) => {
      const f = Math.max(0, Math.min(1, (xView - PX0) / PW));
      const d = new Date(t0 + f * (t1 - t0));
      return d.toISOString().slice(0, 10);
    },
    [t0, t1]
  );

  const handleSvgClick = (e) => {
    if (!svgRef.current || !win) return;
    const rect = svgRef.current.getBoundingClientRect();
    const xView = ((e.clientX - rect.left) / rect.width) * W;
    setSelectedDate(dateAtX(xView));
    setAiAnalysis("");
    setAiError("");
  };

  // Year gridlines across the window.
  const yearTicks = useMemo(() => {
    if (!win) return [];
    const y0 = new Date(`${win.start_date}T00:00:00`).getFullYear();
    const y1 = new Date(`${win.end_date}T00:00:00`).getFullYear();
    const step = y1 - y0 > 24 ? 4 : y1 - y0 > 12 ? 2 : 1;
    const ticks = [];
    for (let y = Math.ceil(y0 / step) * step; y <= y1; y += step) {
      ticks.push({ year: y, x: xFor(`${y}-01-01`) });
    }
    return ticks;
  }, [win, xFor]);

  // "What's running" at the selected date, derived from the loaded data.
  const selection = useMemo(() => {
    if (!selectedDate || !data) return null;
    const covers = (o) => o.start_date <= selectedDate && selectedDate <= o.end_date;
    const near = (dateStr) => {
      const diff = Math.abs(ms(dateStr) - ms(selectedDate));
      return diff <= 285 * 864e5; // ~9.5 months
    };
    return {
      maha: (data.maha_bands || []).find(covers) || null,
      bhukti: (data.bhukti_bands || []).find(covers) || null,
      saturn: (data.saturn_phases || []).find(covers) || null,
      ingresses: (data.ingresses || []).filter((i) => near(i.date)),
      eclipses: (data.eclipses || []).filter((e) => near(e.date)),
    };
  }, [selectedDate, data]);

  const handleAi = async () => {
    if (!birthDetails || !selectedDate) return;
    setAiLoading(true);
    setAiError("");
    try {
      const res = await astrologyService.analyzeLifeTimelineAI(
        birthDetails,
        { targetDate: selectedDate, personName: birthDetails.name },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("timeline.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  // ── Lane geometry (viewBox units) ─────────────────────────────────────
  const LANES = {
    axisTop: 6,
    mahaY: 30,
    mahaH: 46,
    bhuktiY: 82,
    bhuktiH: 26,
    satY: 116,
    satH: 28,
    ingY: 152,
    eclY: 182,
    bottom: 208,
  };

  const maha = data?.maha_bands || [];
  const bhukti = data?.bhukti_bands || [];
  const phases = data?.saturn_phases || [];
  const ingresses = data?.ingresses || [];
  const eclipses = data?.eclipses || [];

  // Returns SVG-rect attributes (width/height, not w/h — those are ignored).
  const segRect = (o, y, height) => {
    const x = xFor(o.start_date);
    const width = Math.max(2, xFor(o.end_date) - x);
    return { x, y, width, height };
  };

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<CalendarRange size={24} />}
        title={t("timeline.title")}
        subtitle={t("timeline.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <RecentReadings source="timeline" profileId={selectedProfile?._id} />
        <ProfileBanner profile={selectedProfile} />

        <p className="card-note">{t("timeline.intro")}</p>

        <div className="page-controls">
          <div className="controls-group">
            <label className="control-label">{t("timeline.spanLabel")}</label>
            <select
              className="control-input"
              value={span}
              onChange={(e) => setSpan(parseInt(e.target.value, 10))}
            >
              {[5, 10, 15, 20].map((y) => (
                <option key={y} value={y}>
                  {t("timeline.spanOption", { count: y })}
                </option>
              ))}
            </select>
          </div>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("timeline.loading")} />
          </Card>
        ) : data ? (
          <div className="fade-in">
            <div className="info-pills">
              <span className="info-pill">
                {t("timeline.moonSign", { sign: data.moon_sign })}
              </span>
              <span className="info-pill">
                {formatDate(win.start_date, locale)} – {formatDate(win.end_date, locale)}
              </span>
            </div>

            {/* ── The timeline chart ── */}
            <div className="ui-card ui-card--accent-indigo ui-card--pad-lg ui-card--flush mt-lg">
              <p className="card-note">{t("timeline.clickHint")}</p>
              <div className="tl-scroll">
                <svg
                  ref={svgRef}
                  className="tl-svg"
                  viewBox={`0 0 ${W} ${LANES.bottom}`}
                  preserveAspectRatio="none"
                  onClick={handleSvgClick}
                >
                  {/* Year gridlines + labels */}
                  {yearTicks.map((tk) => (
                    <g key={tk.year}>
                      <line
                        x1={tk.x}
                        y1={LANES.mahaY}
                        x2={tk.x}
                        y2={LANES.bottom - 6}
                        className="tl-grid"
                      />
                      <text x={tk.x} y={LANES.axisTop + 12} className="tl-year">
                        {tk.year}
                      </text>
                    </g>
                  ))}

                  {/* Maha dasha band */}
                  {maha.map((m, i) => {
                    const r = segRect(m, LANES.mahaY, LANES.mahaH);
                    return (
                      <g key={`m${i}`}>
                        <rect
                          {...r}
                          rx="4"
                          fill={planetColor(m.lord)}
                          fillOpacity={m.is_current ? 0.95 : 0.78}
                          className="tl-seg"
                        />
                        {r.width > 40 && (
                          <text x={r.x + 6} y={r.y + 27} className="tl-seg-label">
                            {m.lord}
                          </text>
                        )}
                      </g>
                    );
                  })}

                  {/* Bhukti band (current maha only) */}
                  {bhukti.map((b, i) => {
                    const r = segRect(b, LANES.bhuktiY, LANES.bhuktiH);
                    return (
                      <g key={`b${i}`}>
                        <rect
                          {...r}
                          rx="3"
                          fill={planetColor(b.lord)}
                          fillOpacity={b.is_current ? 0.9 : 0.5}
                          stroke="#fff"
                          strokeOpacity="0.5"
                          strokeWidth="0.5"
                        />
                        {r.width > 26 && (
                          <text x={r.x + 4} y={r.y + 17} className="tl-seg-label tl-seg-label--sm">
                            {b.lord.slice(0, 2)}
                          </text>
                        )}
                      </g>
                    );
                  })}

                  {/* Saturn phases */}
                  {phases.map((p, i) => {
                    const r = segRect(p, LANES.satY, LANES.satH);
                    return (
                      <g key={`p${i}`}>
                        <rect
                          {...r}
                          rx="3"
                          fill={PHASE_COLORS[p.kind] || "#999"}
                          fillOpacity={p.is_current ? 0.92 : 0.72}
                        />
                        {r.width > 46 && (
                          <text x={r.x + 5} y={r.y + 18} className="tl-seg-label tl-seg-label--sm">
                            {p.kind === "sade_sati"
                              ? t(`timeline.phase.${p.phase}`)
                              : t(`timeline.phase.${p.kind}`)}
                          </text>
                        )}
                      </g>
                    );
                  })}

                  {/* Ingress markers */}
                  {ingresses.map((ig, i) => {
                    const x = xFor(ig.date);
                    return (
                      <g key={`i${i}`}>
                        <line
                          x1={x}
                          y1={LANES.ingY - 6}
                          x2={x}
                          y2={LANES.ingY + 8}
                          stroke={planetColor(ig.planet)}
                          strokeWidth="2"
                        />
                        <circle cx={x} cy={LANES.ingY - 8} r="3.5" fill={planetColor(ig.planet)} />
                      </g>
                    );
                  })}

                  {/* Eclipse markers */}
                  {eclipses.map((e, i) => {
                    const x = xFor(e.date);
                    const hit = e.on_natal_nakshatra;
                    return (
                      <circle
                        key={`e${i}`}
                        cx={x}
                        cy={LANES.eclY}
                        r={hit ? 5.5 : 4}
                        fill={e.kind === "solar" ? "#E0A020" : "#3A4A66"}
                        stroke={hit ? "#C0392B" : "#fff"}
                        strokeWidth={hit ? 2 : 0.6}
                      />
                    );
                  })}

                  {/* Today line */}
                  <line
                    x1={xFor(win.today)}
                    y1={LANES.mahaY - 4}
                    x2={xFor(win.today)}
                    y2={LANES.bottom - 2}
                    className="tl-today"
                  />
                  <text x={xFor(win.today)} y={LANES.bottom - 1} className="tl-today-label">
                    {t("timeline.today")}
                  </text>

                  {/* Selected marker */}
                  {selectedDate && (
                    <line
                      x1={xFor(selectedDate)}
                      y1={LANES.mahaY - 4}
                      x2={xFor(selectedDate)}
                      y2={LANES.bottom - 2}
                      className="tl-selected"
                    />
                  )}
                </svg>
              </div>

              {/* Lane legend */}
              <div className="tl-legend">
                <span className="tl-legend__row">
                  <b>{t("timeline.laneMaha")}</b> · <b>{t("timeline.laneBhukti")}</b> ·{" "}
                  <b>{t("timeline.laneSaturn")}</b> · <b>{t("timeline.laneIngress")}</b> ·{" "}
                  <b>{t("timeline.laneEclipse")}</b>
                </span>
                <span className="tl-legend__item">
                  <span className="tl-dot" style={{ background: "#E0A020" }} /> {t("timeline.solar")}
                </span>
                <span className="tl-legend__item">
                  <span className="tl-dot" style={{ background: "#3A4A66" }} /> {t("timeline.lunar")}
                </span>
                <span className="tl-legend__item">
                  <span className="tl-dot tl-dot--hit" /> {t("timeline.eclipseHit")}
                </span>
              </div>
            </div>

            {/* ── Selected-window panel ── */}
            {selection && (
              <div className="ui-card ui-card--accent ui-card--pad-lg ui-card--flush mt-xl">
                <h3 className="ui-card-header ui-card-header--sm">
                  {t("timeline.windowTitle", { date: formatDate(selectedDate, locale) })}
                </h3>
                <div className="tl-window-grid">
                  <div className="tl-window-item">
                    <div className="tl-window-item__label">{t("timeline.dashaLabel")}</div>
                    <div className="tl-window-item__value">
                      {selection.maha ? (
                        <>
                          <span
                            className="tl-chip"
                            style={{ background: planetColor(selection.maha.lord) }}
                          >
                            {selection.maha.lord}
                          </span>
                          {selection.bhukti && (
                            <>
                              {" / "}
                              <span
                                className="tl-chip"
                                style={{ background: planetColor(selection.bhukti.lord) }}
                              >
                                {selection.bhukti.lord}
                              </span>
                            </>
                          )}
                        </>
                      ) : (
                        "—"
                      )}
                    </div>
                  </div>
                  <div className="tl-window-item">
                    <div className="tl-window-item__label">{t("timeline.saturnLabel")}</div>
                    <div className="tl-window-item__value">
                      {selection.saturn ? selection.saturn.description : t("timeline.saturnNone")}
                    </div>
                  </div>
                </div>

                {(selection.ingresses.length > 0 || selection.eclipses.length > 0) && (
                  <div className="tl-events">
                    {selection.ingresses.map((ig, i) => (
                      <span key={`wi${i}`} className="tl-event">
                        <span className="tl-dot" style={{ background: planetColor(ig.planet) }} />
                        {formatDate(ig.date, locale)} · {ig.planet} → {ig.to_sign}
                      </span>
                    ))}
                    {selection.eclipses.map((e, i) => (
                      <span key={`we${i}`} className="tl-event">
                        {e.kind === "solar" ? <Sun size={13} /> : <Moon size={13} />}
                        {formatDate(e.date, locale)} · {t(`timeline.${e.kind}`)} · {e.nakshatra}
                        {e.on_natal_nakshatra && (
                          <b className="tl-event__hit">
                            {" "}
                            {t("timeline.onNatal", { planets: e.natal_planets.join(", ") })}
                          </b>
                        )}
                      </span>
                    ))}
                  </div>
                )}

                {/* AI reading for the window */}
                <div className="mt-lg">
                  <ErrorBanner message={aiError} />
                  {!aiAnalysis && !aiLoading && (
                    <p className="ai-panel__hint">{t("timeline.aiHint")}</p>
                  )}
                  {aiLoading && <LoadingState message={t("timeline.aiLoading")} />}
                  {aiAnalysis && !aiLoading && (
                    <div className="sbc-ai-markdown ai-panel__reading">
                      <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                      {aiModel && (
                        <div className="ai-panel__meta">
                          {t("timeline.aiModel", { model: aiModel })}
                        </div>
                      )}
                    </div>
                  )}
                  {!aiLoading && (
                    <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                      <Sparkles size={18} />
                      {aiAnalysis ? t("timeline.aiRegenerate") : t("timeline.aiGenerate")}
                    </button>
                  )}
                </div>
                <p className="card-note">{t("timeline.disclaimer")}</p>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default TimelinePage;
