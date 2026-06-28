import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Orbit, Calendar, TrendingUp, RotateCcw } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { PLANET_ABBR, DEFAULT_AYANAMSA, AYANAMSAS } from "../constants/jyotish";
import "../styles/Dashboard.css";

const todayISO = () => new Date().toISOString().slice(0, 10);

const formatDate = (dateStr) => {
  if (!dateStr) return "N/A";
  try {
    return new Date(dateStr).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch (e) {
    return "N/A";
  }
};

// Order grahas the traditional way for the table.
const PLANET_ORDER = [
  "Sun",
  "Moon",
  "Mars",
  "Mercury",
  "Jupiter",
  "Venus",
  "Saturn",
  "Rahu",
  "Ketu",
];

const ordinal = (n) => {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
};

export const TransitPage = () => {
  const navigate = useNavigate();
  const { selectedProfile } = useProfile();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [transitDate, setTransitDate] = useState(todayISO());

  const [chartStyle, setChartStyle] = useState(() => localStorage.getItem("chartStyle") || "north");
  const ayanamsa = localStorage.getItem("ayanamsa") || DEFAULT_AYANAMSA;
  const ayanamsaLabel = AYANAMSAS.find((a) => a.value === ayanamsa)?.label || ayanamsa;

  const setStyle = (style) => {
    setChartStyle(style);
    localStorage.setItem("chartStyle", style);
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

  const loadTransits = useCallback(async () => {
    if (!birthDetails) return;
    setLoading(true);
    setError("");
    try {
      const res = await astrologyService.getTransits(birthDetails, transitDate, ayanamsa);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to calculate transits");
    } finally {
      setLoading(false);
    }
  }, [birthDetails, transitDate, ayanamsa]);

  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }
    loadTransits();
  }, [selectedProfile, navigate, loadTransits]);

  if (!selectedProfile) return null;

  const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;
  const planets = result?.planets || {};
  const orderedPlanets = PLANET_ORDER.filter((p) => planets[p]).map((p) => [p, planets[p]]);

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Orbit size={24} />}
        title="Transits (Gochara)"
        subtitle="Where the grahas move today, over your natal chart"
        accent="indigo"
      />

      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        {/* Controls */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "var(--space-md)",
            marginBottom: "var(--space-xl)",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-sm)",
              flexWrap: "wrap",
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
              Transit date
            </label>
            <input
              type="date"
              value={transitDate}
              onChange={(e) => setTransitDate(e.target.value)}
              style={{
                padding: "var(--space-sm) var(--space-md)",
                borderRadius: "var(--radius-md)",
                border: "2px solid var(--sandalwood)",
                fontSize: "0.9375rem",
                fontWeight: 600,
                color: "var(--text-primary)",
                background: "white",
              }}
            />
            <button
              onClick={() => setTransitDate(todayISO())}
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
              <RotateCcw size={14} /> Today
            </button>
          </div>

          {/* Chart style toggle */}
          <div
            style={{
              display: "flex",
              gap: "4px",
              background: "white",
              padding: "4px",
              borderRadius: "var(--radius-md)",
              boxShadow: "var(--shadow-sm)",
            }}
          >
            {["north", "south"].map((style) => (
              <button
                key={style}
                onClick={() => setStyle(style)}
                style={{
                  padding: "var(--space-sm) var(--space-md)",
                  borderRadius: "var(--radius-sm)",
                  border: "none",
                  cursor: "pointer",
                  fontWeight: 600,
                  fontSize: "0.8125rem",
                  textTransform: "capitalize",
                  background: chartStyle === style ? "var(--saffron)" : "transparent",
                  color: chartStyle === style ? "white" : "var(--text-secondary)",
                }}
              >
                {style} Indian
              </button>
            ))}
          </div>
        </div>

        <ErrorBanner message={error} />

        {loading ? (
          <div
            style={{
              background: "white",
              borderRadius: "var(--radius-xl)",
              padding: "var(--space-3xl)",
              textAlign: "center",
              boxShadow: "var(--shadow-lg)",
            }}
          >
            <div className="spinner" style={{ margin: "0 auto var(--space-xl)" }}></div>
            <h3 style={{ color: "var(--cosmic-indigo)", marginBottom: "var(--space-sm)" }}>
              Calculating transits
            </h3>
            <p style={{ color: "var(--text-secondary)" }}>Locating the grahas…</p>
          </div>
        ) : result ? (
          <div style={{ opacity: 0, animation: "fadeIn 0.6s ease-out forwards" }}>
            {/* Natal reference */}
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "var(--space-md)",
                marginBottom: "var(--space-xl)",
                fontSize: "0.875rem",
                color: "var(--text-secondary)",
              }}
            >
              <span
                style={{
                  padding: "var(--space-xs) var(--space-md)",
                  background: "white",
                  borderRadius: "var(--radius-full)",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                Natal Lagna:{" "}
                <strong style={{ color: "var(--saffron)" }}>
                  {result.natal?.lagna?.sign_name}
                </strong>
              </span>
              <span
                style={{
                  padding: "var(--space-xs) var(--space-md)",
                  background: "white",
                  borderRadius: "var(--radius-full)",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                Natal Moon:{" "}
                <strong style={{ color: "var(--cosmic-indigo)" }}>
                  {result.natal?.moon?.sign_name}
                </strong>
              </span>
              <span
                style={{
                  padding: "var(--space-xs) var(--space-md)",
                  background: "white",
                  borderRadius: "var(--radius-full)",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                Ayanamsa: <strong style={{ color: "var(--cosmic-indigo)" }}>{ayanamsaLabel}</strong>
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
              {/* Transit chart over natal lagna */}
              <Kundali
                planets={planets}
                lagna={result.lagna}
                title="Gochara"
                subtitle={`Transits • ${formatDate(result.transit_date)}`}
              />

              {/* Transit table */}
              <div
                style={{
                  background: "white",
                  borderRadius: "var(--radius-xl)",
                  padding: "var(--space-lg)",
                  boxShadow: "var(--shadow-lg)",
                  borderTop: "4px solid var(--cosmic-indigo)",
                }}
              >
                <h3
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-sm)",
                    marginTop: 0,
                    marginBottom: "var(--space-md)",
                    color: "var(--cosmic-indigo)",
                    fontSize: "1.125rem",
                  }}
                >
                  <Orbit size={18} style={{ color: "var(--saffron)" }} />
                  Transiting Grahas
                </h3>
                <div style={{ overflowX: "auto" }}>
                  <table
                    style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem" }}
                  >
                    <thead>
                      <tr
                        style={{
                          textAlign: "left",
                          color: "var(--text-muted)",
                          textTransform: "uppercase",
                          fontSize: "0.6875rem",
                          letterSpacing: "0.5px",
                        }}
                      >
                        <th style={{ padding: "var(--space-xs)" }}>Planet</th>
                        <th style={{ padding: "var(--space-xs)" }}>Sign</th>
                        <th style={{ padding: "var(--space-xs)" }}>Nakshatra</th>
                        <th style={{ padding: "var(--space-xs)", textAlign: "center" }}>
                          From Lagna
                        </th>
                        <th style={{ padding: "var(--space-xs)", textAlign: "center" }}>
                          From Moon
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {orderedPlanets.map(([name, p]) => (
                        <tr key={name} style={{ borderTop: "1px solid var(--sandalwood)" }}>
                          <td
                            style={{
                              padding: "var(--space-sm) var(--space-xs)",
                              fontWeight: 700,
                              color: "var(--cosmic-indigo)",
                            }}
                          >
                            {PLANET_ABBR[name] || name}{" "}
                            <span style={{ fontWeight: 400, color: "var(--text-secondary)" }}>
                              {name}
                            </span>
                            {p.retrograde && (
                              <span
                                title="Retrograde"
                                style={{
                                  marginLeft: "6px",
                                  padding: "1px 5px",
                                  background: "rgba(227, 66, 52, 0.12)",
                                  color: "var(--vermillion)",
                                  borderRadius: "var(--radius-sm)",
                                  fontSize: "0.625rem",
                                  fontWeight: 700,
                                }}
                              >
                                ℞
                              </span>
                            )}
                          </td>
                          <td style={{ padding: "var(--space-sm) var(--space-xs)" }}>
                            {p.sign_name}{" "}
                            <span style={{ color: "var(--text-muted)" }}>
                              {p.degrees != null ? `${p.degrees.toFixed(1)}°` : ""}
                            </span>
                          </td>
                          <td
                            style={{
                              padding: "var(--space-sm) var(--space-xs)",
                              color: "var(--text-secondary)",
                            }}
                          >
                            {p.nakshatra}
                            {p.nakshatra_pada ? ` (${p.nakshatra_pada})` : ""}
                          </td>
                          <td
                            style={{
                              padding: "var(--space-sm) var(--space-xs)",
                              textAlign: "center",
                              fontWeight: 600,
                              color: "var(--saffron)",
                            }}
                          >
                            {ordinal(p.house_from_lagna)}
                          </td>
                          <td
                            style={{
                              padding: "var(--space-sm) var(--space-xs)",
                              textAlign: "center",
                              fontWeight: 600,
                              color: "var(--vermillion)",
                            }}
                          >
                            {ordinal(p.house_from_moon)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p
                  style={{
                    margin: "var(--space-md) 0 0",
                    fontSize: "0.75rem",
                    color: "var(--text-muted)",
                  }}
                >
                  House counted inclusively from the natal Lagna and natal Moon. Moon-based houses
                  drive classic gochara results.
                </p>
              </div>
            </div>

            {/* Upcoming ingresses */}
            {result.upcoming && result.upcoming.length > 0 && (
              <div
                style={{
                  marginTop: "var(--space-xl)",
                  background: "white",
                  borderRadius: "var(--radius-xl)",
                  padding: "var(--space-xl)",
                  boxShadow: "var(--shadow-lg)",
                  borderTop: "4px solid var(--saffron)",
                }}
              >
                <h3
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-sm)",
                    marginTop: 0,
                    marginBottom: "var(--space-md)",
                    color: "var(--cosmic-indigo)",
                    fontSize: "1.25rem",
                  }}
                >
                  <TrendingUp size={20} style={{ color: "var(--saffron)" }} />
                  Key Upcoming Transits
                </h3>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                    gap: "var(--space-md)",
                  }}
                >
                  {result.upcoming.map((u, i) => (
                    <div
                      key={i}
                      style={{
                        padding: "var(--space-md)",
                        border: "1px solid var(--sandalwood)",
                        borderRadius: "var(--radius-lg)",
                        background: "var(--sacred-white)",
                      }}
                    >
                      <div style={{ fontSize: "1rem", fontWeight: 700, color: "var(--saffron)" }}>
                        {u.planet}
                      </div>
                      <div
                        style={{
                          fontSize: "0.875rem",
                          color: "var(--text-primary)",
                          marginTop: "var(--space-xs)",
                        }}
                      >
                        {u.from_sign} → <strong>{u.to_sign}</strong>
                      </div>
                      <div
                        style={{
                          fontSize: "0.8125rem",
                          color: "var(--text-secondary)",
                          marginTop: "2px",
                        }}
                      >
                        {formatDate(u.date)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
};
