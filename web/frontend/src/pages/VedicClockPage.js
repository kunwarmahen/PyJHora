import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Clock, Sparkles, RotateCcw, Sunrise, Sunset } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { Card } from "../components/Card";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import "../styles/Dashboard.css";
import "../styles/Shared.css";

const RETRO_PLANETS = ["Mars", "Mercury", "Jupiter", "Venus", "Saturn"];

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
  };
};

// Polar → cartesian on the clock dial (0 ghati at top, clockwise).
const polar = (cx, cy, r, ghatiFraction) => {
  const a = (ghatiFraction * 2 * Math.PI) - Math.PI / 2;
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
};

/** SVG dial with 60 ghati ticks, a shaded day arc, and a live hand. */
const ClockDial = ({ liveGhati, dayGhati }) => {
  const cx = 110;
  const cy = 110;
  const r = 96;
  const ticks = [];
  for (let g = 0; g < 60; g += 1) {
    const inner = polar(cx, cy, g % 5 === 0 ? r - 12 : r - 6, g / 60);
    const outer = polar(cx, cy, r, g / 60);
    ticks.push(
      <line
        key={g}
        x1={inner[0]}
        y1={inner[1]}
        x2={outer[0]}
        y2={outer[1]}
        stroke={g % 5 === 0 ? "#2D3561" : "#c9bfa8"}
        strokeWidth={g % 5 === 0 ? 2 : 1}
      />
    );
  }
  // Day arc (sunrise..sunset) as a background wedge.
  const dayFrac = Math.max(0, Math.min(60, dayGhati || 0)) / 60;
  const arcEnd = polar(cx, cy, r, dayFrac);
  const arcStart = polar(cx, cy, r, 0);
  const largeArc = dayFrac > 0.5 ? 1 : 0;
  const dayPath =
    dayGhati != null
      ? `M ${cx} ${cy} L ${arcStart[0]} ${arcStart[1]} A ${r} ${r} 0 ${largeArc} 1 ${arcEnd[0]} ${arcEnd[1]} Z`
      : null;

  const handFrac = liveGhati != null ? (liveGhati % 60) / 60 : null;
  const hand = handFrac != null ? polar(cx, cy, r - 16, handFrac) : null;

  return (
    <svg viewBox="0 0 220 220" className="vc-clock-svg" role="img" aria-label="Vedic clock">
      <circle cx={cx} cy={cy} r={r} fill="#fffaf2" stroke="#e8ddc9" strokeWidth="2" />
      {dayPath && <path d={dayPath} fill="rgba(255,179,71,0.16)" />}
      {ticks}
      {hand && (
        <>
          <line
            x1={cx}
            y1={cy}
            x2={hand[0]}
            y2={hand[1]}
            stroke="#FF9933"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <circle cx={hand[0]} cy={hand[1]} r="4" fill="#E34234" />
        </>
      )}
      <circle cx={cx} cy={cy} r="5" fill="#2D3561" />
    </svg>
  );
};

/** SVG polyline of the vakra-gathi (retrograde) epicycle loop. */
const RetrogradeLoop = ({ x, y }) => {
  if (!x || !x.length) return null;
  const size = 320;
  const pad = 14;
  const scale = (size - 2 * pad) / 2;
  const pts = x
    .map((xi, i) => {
      const px = pad + scale * (1 + xi);
      const py = pad + scale * (1 - y[i]); // flip y for screen coords
      return `${px.toFixed(1)},${py.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="vc-retro-svg" role="img" aria-label="Retrograde loop">
      <circle cx={size / 2} cy={size / 2} r="4" fill="#E34234" />
      <polyline points={pts} fill="none" stroke="#2D3561" strokeWidth="1.4" opacity="0.85" />
    </svg>
  );
};

export const VedicClockPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile } = useProfile();

  const [clock, setClock] = useState(null);
  const [retro, setRetro] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [planet, setPlanet] = useState("Saturn");

  // Live ghati animation: anchor on the snapshot ghati+vighati, then advance by
  // real elapsed seconds since the fetch (1 ghati = 1440 s, tz-independent).
  const [liveGhati, setLiveGhati] = useState(null);
  const anchorRef = useRef(null);

  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");

  const loc = useMemo(
    () =>
      selectedProfile
        ? {
            place: selectedProfile.birth_details.place,
            latitude: selectedProfile.birth_details.latitude,
            longitude: selectedProfile.birth_details.longitude,
            timezone: selectedProfile.birth_details.timezone,
          }
        : null,
    [selectedProfile]
  );

  const birthDetails = useMemo(
    () => (selectedProfile ? { ...selectedProfile.birth_details } : null),
    [selectedProfile]
  );

  const load = useCallback(async () => {
    if (!loc) return;
    setLoading(true);
    setError("");
    setAiAnalysis("");
    try {
      const [c, r] = await Promise.all([
        astrologyService.getVedicClock(loc),
        astrologyService.getRetrograde(loc),
      ]);
      setClock(c.data);
      setRetro(r.data);
      if (c.data?.ghati != null) {
        anchorRef.current = {
          ghati: c.data.ghati + (c.data.vighati || 0) / 60,
          at: Date.now(),
        };
        setLiveGhati(anchorRef.current.ghati);
      } else {
        anchorRef.current = null;
        setLiveGhati(null);
      }
    } catch (err) {
      setError(err.response?.data?.detail || t("vedicClock.calcError"));
    } finally {
      setLoading(false);
    }
  }, [loc, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    load();
  }, [selectedProfile, navigate, load]);

  // Tick the live ghati every second from the snapshot anchor.
  useEffect(() => {
    if (!anchorRef.current) return undefined;
    const id = setInterval(() => {
      const { ghati, at } = anchorRef.current;
      const elapsedGhati = (Date.now() - at) / 1000 / 1440; // 1440 s per ghati
      setLiveGhati((ghati + elapsedGhati) % 60);
    }, 1000);
    return () => clearInterval(id);
  }, [clock]);

  const handleAi = async () => {
    if (!birthDetails) return;
    setAiLoading(true);
    setAiError("");
    try {
      const res = await astrologyService.analyzeCelestialAI(
        birthDetails,
        { personName: birthDetails.name },
        readModelConfig()
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("vedicClock.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  if (!selectedProfile) return null;

  const ghatiInt = liveGhati != null ? Math.floor(liveGhati) : null;
  const vighatiInt = liveGhati != null ? Math.floor((liveGhati - ghatiInt) * 60) : null;
  const dayGhati = clock ? (clock.day_length_hours / 24) * 60 : null;
  const selected = (retro?.planets || []).find((p) => p.planet === planet);
  const hora = clock?.current_hora;
  const panch = clock?.panchanga || {};

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Clock size={24} />}
        title={t("vedicClock.title")}
        subtitle={t("vedicClock.subtitle")}
        accent="indigo"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        {loading && (
          <Card>
            <LoadingState message={t("vedicClock.loading")} />
          </Card>
        )}
        <ErrorBanner message={error} />

        {!loading && !error && clock && (
          <div className="fade-in">
            <div className="vc-grid">
              {/* Live Vedic clock */}
              <Card title={t("vedicClock.clockTitle")} icon={<Clock size={22} />} accent="saffron">
                <div className="vc-clock-wrap">
                  <ClockDial liveGhati={liveGhati} dayGhati={dayGhati} />
                  <div className="vc-readout">
                    {ghatiInt != null ? (
                      <div className="vc-ghati">
                        {ghatiInt}
                        <small> {t("vedicClock.ghati")} </small>
                        {vighatiInt}
                        <small> {t("vedicClock.vighati")}</small>
                      </div>
                    ) : (
                      <div className="text-secondary">{t("vedicClock.notToday")}</div>
                    )}
                    {hora && (
                      <div className={`vc-hora ${hora.benefic ? "benefic" : "malefic"}`}>
                        {t("vedicClock.horaLord", { planet: hora.planet })}
                      </div>
                    )}
                  </div>
                  <div className="info-pills">
                    <span className="info-pill">
                      <Sunrise size={14} /> {clock.sunrise}
                    </span>
                    <span className="info-pill">
                      <Sunset size={14} /> {clock.sunset}
                    </span>
                  </div>
                  <div className="info-pills">
                    {panch.tithi && (
                      <span className="info-pill">{t("panchanga.tithi")}: {panch.tithi}</span>
                    )}
                    {panch.nakshatra && (
                      <span className="info-pill">{t("common.nakshatra")}: {panch.nakshatra}</span>
                    )}
                    {panch.yoga && (
                      <span className="info-pill">{t("panchanga.yoga")}: {panch.yoga}</span>
                    )}
                  </div>
                </div>
              </Card>

              {/* Retrograde loop */}
              <Card
                title={t("vedicClock.retroTitle")}
                icon={<RotateCcw size={22} />}
                accent="gold"
              >
                <div className="vc-planet-toggle">
                  {RETRO_PLANETS.map((p) => (
                    <button
                      key={p}
                      className={p === planet ? "active" : ""}
                      onClick={() => setPlanet(p)}
                    >
                      {p}
                    </button>
                  ))}
                </div>
                {selected && (
                  <RetrogradeLoop x={selected.orbit_x} y={selected.orbit_y} />
                )}
                {selected && (
                  <p className="card-note text-center">
                    <span
                      className={`vc-retro-badge ${
                        selected.retrograde ? "is-retro" : "is-direct"
                      }`}
                    >
                      {selected.retrograde
                        ? t("vedicClock.retrograde")
                        : t("vedicClock.direct")}
                    </span>{" "}
                    {selected.next_station &&
                      t("vedicClock.nextStation", {
                        becomes: t(`vedicClock.becomes.${selected.next_station.becomes}`),
                        date: selected.next_station.date,
                      })}
                  </p>
                )}
              </Card>
            </div>

            {/* Retrograde status table */}
            <div className="mt-xl">
              <Card title={t("vedicClock.statusTitle")} icon={<RotateCcw size={22} />}>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("vedicClock.colPlanet")}</th>
                        <th>{t("vedicClock.colStatus")}</th>
                        <th>{t("vedicClock.colNextStation")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(retro?.planets || []).map((p) => (
                        <tr key={p.planet}>
                          <td className="fw-700">{p.planet}</td>
                          <td>
                            <span
                              className={`vc-retro-badge ${
                                p.retrograde ? "is-retro" : "is-direct"
                              }`}
                            >
                              {p.retrograde
                                ? t("vedicClock.retrograde")
                                : t("vedicClock.direct")}
                            </span>
                          </td>
                          <td>
                            {p.next_station
                              ? `${p.next_station.date} → ${t(
                                  `vedicClock.becomes.${p.next_station.becomes}`
                                )}`
                              : "—"}
                          </td>
                        </tr>
                      ))}
                      {(retro?.nodes || []).map((n) => (
                        <tr key={n.planet}>
                          <td className="fw-700">{n.planet}</td>
                          <td>
                            <span className="vc-retro-badge is-retro">
                              {t("vedicClock.retrograde")}
                            </span>
                          </td>
                          <td className="text-secondary">{t("vedicClock.perpetual")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>

            {/* AI reading */}
            <div className="mt-xl">
              <Card title={t("vedicClock.aiTitle")} icon={<Sparkles size={24} />} accent="gold">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && (
                  <p className="ai-panel__hint">{t("vedicClock.aiHint")}</p>
                )}
                {aiLoading && <LoadingState message={t("vedicClock.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div className="sbc-ai-markdown ai-panel__reading">
                    <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                    {aiModel && (
                      <div className="ai-panel__meta">
                        {t("vedicClock.aiModel", { model: aiModel })}
                      </div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button className="ui-btn ui-btn--ai" onClick={handleAi}>
                    <Sparkles size={18} />
                    {aiAnalysis ? t("vedicClock.aiRegenerate") : t("vedicClock.aiGenerate")}
                  </button>
                )}
                <p className="card-note">{t("vedicClock.disclaimer")}</p>
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default VedicClockPage;
