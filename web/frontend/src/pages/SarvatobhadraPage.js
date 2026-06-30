import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Grid3x3, Calendar, RotateCcw, Sparkles, Crosshair } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { intlLocale } from "../utils/format";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { PLANET_ABBR, DEFAULT_AYANAMSA, AYANAMSAS } from "../constants/jyotish";
import "../styles/Dashboard.css";

const pad2 = (n) => String(n).padStart(2, "0");
const dateISO = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
const timeISO = (d) => `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
const tzOffset = (d) => -d.getTimezoneOffset() / 60;

const formatDate = (dateStr, locale = "en-US") => {
  if (!dateStr) return "—";
  try {
    return new Date(dateStr).toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch (e) {
    return "—";
  }
};

// 27 nakshatras with the traditional starting syllables of names — lets a user
// pick their "naama nakshatra" (name star) without us guessing transliteration.
const NAAMA_NAKSHATRAS = [
  "Ashwini (Chu, Che, Cho, La)",
  "Bharani (Li, Lu, Le, Lo)",
  "Krittika (A, I, U, E)",
  "Rohini (O, Va, Vi, Vu)",
  "Mrigashira (Ve, Vo, Ka, Ki)",
  "Ardra (Ku, Gha, Nga, Chha)",
  "Punarvasu (Ke, Ko, Ha, Hi)",
  "Pushya (Hu, He, Ho, Da)",
  "Ashlesha (Di, Du, De, Do)",
  "Magha (Ma, Mi, Mu, Me)",
  "Purva Phalguni (Mo, Ta, Ti, Tu)",
  "Uttara Phalguni (Te, To, Pa, Pi)",
  "Hasta (Pu, Sha, Na, Tha)",
  "Chitra (Pe, Po, Ra, Ri)",
  "Swati (Ru, Re, Ro, Ta)",
  "Vishakha (Ti, Tu, Te, To)",
  "Anuradha (Na, Ni, Nu, Ne)",
  "Jyeshtha (No, Ya, Yi, Yu)",
  "Mula (Ye, Yo, Bha, Bhi)",
  "Purva Ashadha (Bhu, Dha, Pha, Dha)",
  "Uttara Ashadha (Bhe, Bho, Ja, Ji)",
  "Shravana (Ju, Je, Jo, Kha)",
  "Dhanishta (Ga, Gi, Gu, Ge)",
  "Shatabhisha (Go, Sa, Si, Su)",
  "Purva Bhadrapada (Se, So, Da, Di)",
  "Uttara Bhadrapada (Du, Tha, Jha, Tra)",
  "Revati (De, Do, Cha, Chi)",
];

// Read the model the user already picked in "Ask Astrologer" (same as ComparePage).
const readModelConfig = () => {
  const providerType = localStorage.getItem("ai_provider_type") || "ollama";
  return {
    providerType,
    model: localStorage.getItem("ai_model") || "",
    baseUrl: providerType === "ollama" ? localStorage.getItem("ai_base_url") || undefined : undefined,
    legacyProvider: providerType === "ollama" ? "qwen" : providerType,
  };
};

// Per-type base background for a chakra cell.
const CELL_BG = {
  nakshatra: "#fff7ed", // warm cream (outer star ring)
  akshara: "#ffffff",
  rasi: "#eef2ff", // pale indigo (sign ring)
  tithi: "#fef3c7", // amber (centre)
};
const CELL_FG = {
  nakshatra: "var(--saffron)",
  akshara: "var(--text-muted)",
  rasi: "var(--cosmic-indigo)",
  tithi: "#b45309",
};

export const SarvatobhadraPage = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const locale = intlLocale(i18n.language);
  const { selectedProfile } = useProfile();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [momentMs, setMomentMs] = useState(() => Date.now());
  const [nameNak, setNameNak] = useState(""); // "" = not set; else "1".."27"

  const moment = useMemo(() => new Date(momentMs), [momentMs]);
  const transitDate = dateISO(moment);
  const transitTime = timeISO(moment);

  const ayanamsa = localStorage.getItem("ayanamsa") || DEFAULT_AYANAMSA;
  const ayanamsaLabel = AYANAMSAS.find((a) => a.value === ayanamsa)?.label || ayanamsa;

  // AI reading (on-demand, uses the model picked in Ask Astrologer).
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState("");
  const [aiAnalysis, setAiAnalysis] = useState("");
  const [aiModel, setAiModel] = useState("");

  const setDatePart = (value) => {
    if (!value) return;
    const [y, m, dd] = value.split("-").map(Number);
    const d = new Date(momentMs);
    d.setFullYear(y, m - 1, dd);
    setMomentMs(d.getTime());
  };
  const setTimePart = (value) => {
    if (!value) return;
    const [hh, mm] = value.split(":").map(Number);
    const d = new Date(momentMs);
    d.setHours(hh, mm, 0, 0);
    setMomentMs(d.getTime());
  };

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

  const loadChakra = useCallback(async () => {
    if (!birthDetails) return;
    setLoading(true);
    setError("");
    setAiAnalysis("");
    setAiError("");
    setAiModel("");
    try {
      const d = new Date(momentMs);
      const res = await astrologyService.getSarvatobhadra(birthDetails, {
        nameNakshatra: nameNak ? Number(nameNak) : null,
        currentDate: dateISO(d),
        currentTime: timeISO(d),
        currentTz: tzOffset(d),
        ayanamsa,
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || t("sbc.calcError"));
    } finally {
      setLoading(false);
    }
  }, [birthDetails, momentMs, nameNak, ayanamsa, t]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    loadChakra();
  }, [selectedProfile, navigate, loadChakra]);

  const handleAi = async () => {
    if (!birthDetails) return;
    setAiLoading(true);
    setAiError("");
    try {
      const d = new Date(momentMs);
      const res = await astrologyService.analyzeSarvatobhadraAI(
        birthDetails,
        {
          personName: birthDetails.name,
          nameNakshatra: nameNak ? Number(nameNak) : null,
          currentDate: dateISO(d),
          currentTime: timeISO(d),
          currentTz: tzOffset(d),
        },
        { ...readModelConfig(), ayanamsa }
      );
      setAiAnalysis(res.data.ai_analysis || "");
      setAiModel(res.data.model || res.data.provider || "");
    } catch (err) {
      setAiError(err.response?.data?.detail || t("sbc.aiError"));
    } finally {
      setAiLoading(false);
    }
  };

  // ── Derived overlay maps for the grid ──────────────────────────────────────
  const { anchorByCell, vedhaSourceCells, planetNature } = useMemo(() => {
    const anchorByCell = {};
    const vedhaSourceCells = {};
    const planetNature = {};
    if (!result) return { anchorByCell, vedhaSourceCells, planetNature };
    (result.planets || []).forEach((p) => {
      planetNature[p.name] = p.nature;
    });
    Object.values(result.anchors || {}).forEach((a) => {
      const [r, c] = a.cell;
      anchorByCell[`${r},${c}`] = a;
      // The cell facing the anchor across the chakra is where vedha originates.
      const mkey = `${8 - r},${8 - c}`;
      if (result.placements && result.placements[mkey]) {
        vedhaSourceCells[mkey] = a;
      }
    });
    return { anchorByCell, vedhaSourceCells, planetNature };
  }, [result]);

  if (!selectedProfile) return null;

  const placements = result?.placements || {};

  const chip = (bg) => ({
    padding: "var(--space-xs) var(--space-md)",
    background: bg || "white",
    borderRadius: "var(--radius-full)",
    boxShadow: "var(--shadow-sm)",
    fontSize: "0.8125rem",
  });

  const renderCell = (cell) => {
    const key = `${cell.row},${cell.col}`;
    const anchor = anchorByCell[key];
    const isVedhaSource = vedhaSourceCells[key];
    const grahas = placements[key] || [];
    const isCenter = cell.type === "tithi";

    return (
      <div
        key={key}
        title={
          anchor
            ? `${anchor.label}: ${anchor.name}`
            : isVedhaSource
            ? `Casts vedha on ${isVedhaSource.label} (${isVedhaSource.name})`
            : cell.label
        }
        style={{
          position: "relative",
          aspectRatio: "1 / 1",
          minWidth: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "2px",
          background: anchor ? "rgba(255, 153, 51, 0.18)" : CELL_BG[cell.type] || "white",
          border: anchor
            ? "2px solid var(--saffron)"
            : isVedhaSource
            ? "2px dashed var(--vermillion)"
            : "1px solid var(--sandalwood)",
          borderRadius: "4px",
          overflow: "hidden",
          textAlign: "center",
        }}
      >
        <span
          style={{
            fontSize: isCenter ? "0.5rem" : "0.56rem",
            fontWeight: cell.type === "akshara" ? 400 : 700,
            color: CELL_FG[cell.type] || "var(--text-secondary)",
            lineHeight: 1.05,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            maxWidth: "100%",
          }}
        >
          {cell.label}
        </span>
        {grahas.length > 0 && (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "1px",
              justifyContent: "center",
              marginTop: "1px",
            }}
          >
            {grahas.map((g) => (
              <span
                key={g}
                style={{
                  fontSize: "0.5rem",
                  fontWeight: 800,
                  lineHeight: 1,
                  padding: "1px 2px",
                  borderRadius: "3px",
                  color: "white",
                  background:
                    planetNature[g] === "benefic" ? "var(--forest-green, #2e7d32)" : "var(--vermillion)",
                }}
              >
                {PLANET_ABBR[g] || g.slice(0, 2)}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Grid3x3 size={24} />}
        title={t("sbc.title")}
        subtitle={t("sbc.subtitle")}
        accent="saffron"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        {/* Controls */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "var(--space-md)",
            marginBottom: "var(--space-lg)",
          }}
        >
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-sm)",
              fontWeight: 600,
              color: "var(--cosmic-indigo)",
            }}
          >
            <Calendar size={18} style={{ color: "var(--saffron)" }} />
            {t("sbc.date")}
          </label>
          <input
            type="date"
            value={transitDate}
            onChange={(e) => setDatePart(e.target.value)}
            style={{
              padding: "var(--space-sm) var(--space-md)",
              borderRadius: "var(--radius-md)",
              border: "2px solid var(--sandalwood)",
              fontWeight: 600,
              background: "white",
            }}
          />
          <input
            type="time"
            value={transitTime}
            onChange={(e) => setTimePart(e.target.value)}
            style={{
              padding: "var(--space-sm) var(--space-md)",
              borderRadius: "var(--radius-md)",
              border: "2px solid var(--sandalwood)",
              fontWeight: 600,
              background: "white",
            }}
          />
          <button
            onClick={() => setMomentMs(Date.now())}
            title={t("sbc.nowHint")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-xs)",
              padding: "var(--space-sm) var(--space-md)",
              borderRadius: "var(--radius-md)",
              border: "2px solid var(--sandalwood)",
              background: "white",
              color: "var(--cosmic-indigo)",
              fontWeight: 600,
              cursor: "pointer",
              fontSize: "0.8125rem",
            }}
          >
            <RotateCcw size={14} /> {t("sbc.now")}
          </button>

          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-sm)",
              fontWeight: 600,
              color: "var(--cosmic-indigo)",
              marginLeft: "auto",
            }}
          >
            {t("sbc.nameStar")}
          </label>
          <select
            value={nameNak}
            onChange={(e) => setNameNak(e.target.value)}
            title={t("sbc.nameStarHint")}
            style={{
              padding: "var(--space-sm) var(--space-md)",
              borderRadius: "var(--radius-md)",
              border: "2px solid var(--sandalwood)",
              fontWeight: 600,
              background: "white",
              maxWidth: "260px",
            }}
          >
            <option value="">{t("sbc.nameStarNone")}</option>
            {NAAMA_NAKSHATRAS.map((label, i) => (
              <option key={i} value={String(i + 1)}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <Card>
            <LoadingState message={t("sbc.loading")} />
          </Card>
        ) : result ? (
          <div style={{ opacity: 0, animation: "fadeIn 0.6s ease-out forwards" }}>
            {/* Context chips */}
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "var(--space-sm)",
                marginBottom: "var(--space-lg)",
                color: "var(--text-secondary)",
              }}
            >
              <span style={chip()}>
                {t("sbc.asOf", {
                  moment: `${formatDate(result.transit_date, locale)}, ${result.transit_time}`,
                })}
              </span>
              <span style={chip()}>
                {t("sbc.ayanamsa")}: <strong>{ayanamsaLabel}</strong>
              </span>
              <span style={chip()}>
                {result.transit_panchanga?.same_tithi_group
                  ? t("sbc.tithiMatch", { group: result.transit_panchanga.tithi_group })
                  : t("sbc.tithiToday", { group: result.transit_panchanga?.tithi_group })}
              </span>
              <span style={chip()}>
                {result.transit_panchanga?.same_weekday
                  ? t("sbc.weekdayMatch", { day: result.transit_panchanga.weekday })
                  : t("sbc.weekdayToday", { day: result.transit_panchanga?.weekday })}
              </span>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                gap: "var(--space-xl)",
                alignItems: "start",
              }}
            >
              {/* The chakra grid */}
              <Card
                title={t("sbc.chakraTitle")}
                icon={<Grid3x3 size={22} />}
                accent="saffron"
              >
                <div style={{ overflowX: "auto" }}>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(9, 1fr)",
                      gap: "2px",
                      minWidth: "320px",
                      maxWidth: "460px",
                      margin: "0 auto",
                    }}
                  >
                    {result.grid.flat().map(renderCell)}
                  </div>
                </div>

                {/* Legend */}
                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: "var(--space-md)",
                    marginTop: "var(--space-md)",
                    fontSize: "0.75rem",
                    color: "var(--text-secondary)",
                  }}
                >
                  <span>
                    <span
                      style={{
                        display: "inline-block",
                        width: 12,
                        height: 12,
                        background: "rgba(255,153,51,0.4)",
                        border: "2px solid var(--saffron)",
                        borderRadius: 3,
                        verticalAlign: "middle",
                        marginRight: 4,
                      }}
                    />
                    {t("sbc.legendAnchor")}
                  </span>
                  <span>
                    <span
                      style={{
                        display: "inline-block",
                        width: 12,
                        height: 12,
                        border: "2px dashed var(--vermillion)",
                        borderRadius: 3,
                        verticalAlign: "middle",
                        marginRight: 4,
                      }}
                    />
                    {t("sbc.legendVedha")}
                  </span>
                  <span>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "0 3px",
                        background: "var(--forest-green, #2e7d32)",
                        color: "white",
                        borderRadius: 3,
                        fontSize: "0.6rem",
                        fontWeight: 800,
                        marginRight: 4,
                      }}
                    >
                      Ju
                    </span>
                    {t("sbc.legendBenefic")}
                  </span>
                  <span>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "0 3px",
                        background: "var(--vermillion)",
                        color: "white",
                        borderRadius: 3,
                        fontSize: "0.6rem",
                        fontWeight: 800,
                        marginRight: 4,
                      }}
                    >
                      Sa
                    </span>
                    {t("sbc.legendMalefic")}
                  </span>
                </div>
              </Card>

              {/* Findings + anchors */}
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-xl)" }}>
                <Card title={t("sbc.anchorsTitle")} icon={<Crosshair size={22} />} accent="indigo">
                  <ul style={{ margin: 0, paddingLeft: "1.1rem", lineHeight: 1.9 }}>
                    {Object.values(result.anchors).map((a) => (
                      <li key={a.label} style={{ color: "var(--text-secondary)" }}>
                        {a.label}:{" "}
                        <strong style={{ color: "var(--cosmic-indigo)" }}>{a.name}</strong>
                      </li>
                    ))}
                  </ul>
                </Card>

                <Card title={t("sbc.findingsTitle")} icon={<Sparkles size={22} />} accent="saffron">
                  {result.findings.length === 0 ? (
                    <p style={{ color: "var(--text-secondary)", margin: 0 }}>{t("sbc.findingsNone")}</p>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-sm)" }}>
                      {result.findings.map((f, i) => (
                        <div
                          key={i}
                          style={{
                            padding: "var(--space-sm) var(--space-md)",
                            borderRadius: "var(--radius-md)",
                            border: "1px solid var(--sandalwood)",
                            borderLeft: `4px solid ${
                              f.tone === "supportive" ? "var(--forest-green, #2e7d32)" : "var(--vermillion)"
                            }`,
                            background: "white",
                            fontSize: "0.875rem",
                          }}
                        >
                          <strong style={{ color: "var(--cosmic-indigo)" }}>{f.planet}</strong>{" "}
                          <span style={{ color: "var(--text-muted)" }}>({f.planet_nature})</span>{" "}
                          {f.kind === "occupation" ? t("sbc.findOccupies") : t("sbc.findVedha")}{" "}
                          <strong style={{ color: "var(--saffron)" }}>{f.anchor_label}</strong>{" "}
                          ({f.anchor_name})
                        </div>
                      ))}
                    </div>
                  )}
                  <p
                    style={{
                      margin: "var(--space-md) 0 0",
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                    }}
                  >
                    {t("sbc.vedhaNote")}
                  </p>
                </Card>
              </div>
            </div>

            {/* AI reading */}
            <div style={{ marginTop: "var(--space-xl)" }}>
              <Card title={t("sbc.aiTitle")} icon={<Sparkles size={24} />} accent="indigo">
                <ErrorBanner message={aiError} />
                {!aiAnalysis && !aiLoading && (
                  <p style={{ color: "var(--text-secondary)", marginBottom: "var(--space-md)", fontSize: "0.9rem" }}>
                    {t("sbc.aiHint")}
                  </p>
                )}
                {aiLoading && <LoadingState message={t("sbc.aiLoading")} />}
                {aiAnalysis && !aiLoading && (
                  <div
                    style={{
                      padding: "var(--space-md)",
                      background: "white",
                      borderRadius: "var(--radius-md)",
                      fontSize: "1rem",
                      lineHeight: "1.8",
                      color: "var(--cosmic-indigo)",
                      whiteSpace: "pre-wrap",
                      marginBottom: "var(--space-md)",
                    }}
                  >
                    {aiAnalysis}
                    {aiModel && (
                      <div
                        style={{
                          marginTop: "var(--space-md)",
                          paddingTop: "var(--space-sm)",
                          borderTop: "1px solid var(--sandalwood)",
                          fontSize: "0.8rem",
                          color: "var(--text-secondary)",
                        }}
                      >
                        {t("sbc.aiModel", { model: aiModel })}
                      </div>
                    )}
                  </div>
                )}
                {!aiLoading && (
                  <button
                    onClick={handleAi}
                    style={{
                      padding: "var(--space-md) var(--space-lg)",
                      background: "linear-gradient(135deg, var(--cosmic-indigo) 0%, var(--saffron) 100%)",
                      color: "white",
                      border: "none",
                      borderRadius: "var(--radius-md)",
                      fontSize: "1rem",
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-sm)",
                    }}
                  >
                    <Sparkles size={18} />
                    {aiAnalysis ? t("sbc.aiRegenerate") : t("sbc.aiGenerate")}
                  </button>
                )}
                <p
                  style={{
                    margin: "var(--space-md) 0 0",
                    fontSize: "0.75rem",
                    color: "var(--text-muted)",
                  }}
                >
                  {t("sbc.disclaimer")}
                </p>
              </Card>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};
