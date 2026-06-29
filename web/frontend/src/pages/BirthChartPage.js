import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Calendar, User, MapPin, Clock, Star, Share2, Copy, Check } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { formatDate, orDash } from "../utils/format";
import { astrologyService } from "../services/api";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { PanchangaPanel } from "../components/PanchangaPanel";
import { PageHeader } from "../components/PageHeader";
import { ProfileBanner } from "../components/ProfileBanner";
import { ErrorBanner } from "../components/ErrorBanner";
import { LoadingState } from "../components/LoadingState";
import { Card } from "../components/Card";
import { DataField } from "../components/DataField";
import { AYANAMSAS, DEFAULT_AYANAMSA, VARGAS, DEFAULT_VARGA } from "../constants/jyotish";
import "../styles/Dashboard.css";

export const BirthChartPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { selectedProfile } = useProfile();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [doshas, setDoshas] = useState(null);
  const [yogas, setYogas] = useState(null);
  const [chartStyle, setChartStyle] = useState(() => localStorage.getItem("chartStyle") || "north");
  const [ayanamsa, setAyanamsa] = useState(
    () => localStorage.getItem("ayanamsa") || DEFAULT_AYANAMSA
  );
  const [varga, setVarga] = useState(() => Number(localStorage.getItem("varga")) || DEFAULT_VARGA);
  const [vargaChart, setVargaChart] = useState(null);
  const [vargaLoading, setVargaLoading] = useState(false);
  const [shareUrl, setShareUrl] = useState("");
  const [shareBusy, setShareBusy] = useState(false);
  const [shareCopied, setShareCopied] = useState(false);

  const changeChartStyle = (style) => {
    setChartStyle(style);
    localStorage.setItem("chartStyle", style);
  };

  const changeAyanamsa = (value) => {
    setAyanamsa(value);
    localStorage.setItem("ayanamsa", value);
  };

  const changeVarga = (value) => {
    setVarga(value);
    localStorage.setItem("varga", String(value));
  };

  const buildBirthDetails = () => ({
    name: selectedProfile.birth_details.name,
    dob: selectedProfile.birth_details.dob,
    tob: selectedProfile.birth_details.tob,
    place: selectedProfile.birth_details.place,
    latitude: parseFloat(selectedProfile.birth_details.latitude),
    longitude: parseFloat(selectedProfile.birth_details.longitude),
    timezone: parseFloat(selectedProfile.birth_details.timezone),
  });

  const handleShare = async () => {
    setShareBusy(true);
    try {
      const res = await astrologyService.createShare(
        buildBirthDetails(),
        ayanamsa,
        selectedProfile.profile_name
      );
      const url = `${window.location.origin}${res.data.path}`;
      setShareUrl(url);
      try {
        await navigator.clipboard.writeText(url);
        setShareCopied(true);
        setTimeout(() => setShareCopied(false), 2500);
      } catch {
        /* clipboard may be blocked; the link is still shown to copy manually */
      }
    } catch (err) {
      setError(err.response?.data?.detail || t("birthChart.shareError"));
    } finally {
      setShareBusy(false);
    }
  };

  // Redirect if no profile selected; (re)calculate when profile or ayanamsa changes
  useEffect(() => {
    if (!selectedProfile) {
      navigate("/profile-selection");
      return;
    }

    calculateChart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProfile, navigate, ayanamsa]);

  // Load the selected divisional (varga) chart. The Rasi (D1) and Navamsa (D9)
  // come back with the main birth-chart response, so reuse those instead of an
  // extra request; everything else is fetched on demand.
  useEffect(() => {
    if (!result || !selectedProfile) return;

    if (varga === 1) {
      setVargaChart({ planets: result.planets, lagna: result.lagna });
      return;
    }
    if (varga === 9 && result.d9_chart && result.d9_lagna) {
      setVargaChart({ planets: result.d9_chart, lagna: result.d9_lagna });
      return;
    }

    let cancelled = false;
    setVargaLoading(true);
    setVargaChart(null);
    astrologyService
      .getDivisionalChart(buildBirthDetails(), varga, ayanamsa)
      .then((r) => {
        if (!cancelled) setVargaChart(r.data);
      })
      .catch(() => {
        if (!cancelled) setVargaChart(null);
      })
      .finally(() => {
        if (!cancelled) setVargaLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result, varga, ayanamsa]);

  const calculateChart = async () => {
    if (!selectedProfile) return;

    setLoading(true);
    setError("");

    try {
      const birthDetails = buildBirthDetails();

      const response = await astrologyService.calculateBirthChart(birthDetails, ayanamsa);
      setResult(response.data);

      // Yogas & doshas load independently — a failure here shouldn't blank the chart.
      setDoshas(null);
      setYogas(null);
      astrologyService
        .getDoshas(birthDetails, ayanamsa)
        .then((r) => setDoshas(r.data?.doshas || null))
        .catch(() => setDoshas(null));
      astrologyService
        .getYogas(birthDetails, ayanamsa)
        .then((r) => setYogas(r.data?.yogas || null))
        .catch(() => setYogas(null));
    } catch (err) {
      setError(err.response?.data?.detail || t("birthChart.calcError"));
    } finally {
      setLoading(false);
    }
  };

  if (!selectedProfile) {
    return null;
  }

  return (
    <div className="dashboard-container mandala-bg">
      <PageHeader
        icon={<Calendar size={24} />}
        title={t("birthChart.title")}
        subtitle={t("birthChart.subtitle")}
        accent="saffron"
      />

      {/* Content */}
      <div className="dashboard-content">
        <ProfileBanner profile={selectedProfile} />

        <ErrorBanner message={error} />

        {/* Loading State */}
        {loading ? (
          <Card>
            <LoadingState message={t("birthChart.loading")} />
          </Card>
        ) : result ? (
          <div style={{ opacity: 0, animation: "fadeIn 0.6s ease-out forwards" }}>
            {/* Chart Details Card */}
            <Card
              title={t("birthChart.chartDetails")}
              icon={<Star size={24} />}
              actions={
                <button
                  className="chart-export-btn"
                  onClick={handleShare}
                  disabled={shareBusy}
                  title={t("birthChart.shareTitle")}
                  style={{ marginLeft: "auto", padding: "6px 12px", fontSize: "0.8125rem" }}
                >
                  {shareCopied ? <Check size={14} /> : <Share2 size={14} />}
                  <span>
                    {shareBusy
                      ? "…"
                      : shareCopied
                        ? t("birthChart.linkCopied")
                        : t("birthChart.share")}
                  </span>
                </button>
              }
            >
              <div className="ui-field-grid">
                <DataField
                  label={t("common.name")}
                  icon={<User size={16} />}
                  value={selectedProfile.birth_details.name || selectedProfile.profile_name}
                />
                <DataField
                  label={t("common.dateOfBirth")}
                  icon={<Calendar size={16} />}
                  value={formatDate(selectedProfile.birth_details.dob)}
                />
                <DataField
                  label={t("common.timeOfBirth")}
                  icon={<Clock size={16} />}
                  value={orDash(selectedProfile.birth_details.tob)}
                />
                <DataField
                  label={t("common.place")}
                  icon={<MapPin size={16} />}
                  value={orDash(selectedProfile.birth_details.place)}
                />
              </div>
              {shareUrl && (
                <div
                  style={{
                    marginTop: "var(--space-lg)",
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-sm)",
                    flexWrap: "wrap",
                  }}
                >
                  <Copy size={14} style={{ color: "var(--saffron)", flexShrink: 0 }} />
                  <input
                    readOnly
                    value={shareUrl}
                    onFocus={(e) => e.target.select()}
                    style={{
                      flex: 1,
                      minWidth: "220px",
                      padding: "var(--space-sm) var(--space-md)",
                      border: "1px solid var(--sandalwood)",
                      borderRadius: "var(--radius-md)",
                      background: "var(--sacred-white)",
                      color: "var(--cosmic-indigo)",
                      fontSize: "0.8125rem",
                    }}
                  />
                </div>
              )}
            </Card>

            {/* Chart style toggle: North / South Indian */}
            {(() => {
              const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;
              const styleLabel =
                chartStyle === "south" ? t("birthChart.southIndian") : t("birthChart.northIndian");
              return (
                <>
                  <div className="chart-controls">
                    <div
                      className="chart-style-toggle"
                      role="group"
                      aria-label={t("birthChart.divisionalChart")}
                    >
                      <button
                        className={chartStyle === "north" ? "active" : ""}
                        onClick={() => changeChartStyle("north")}
                      >
                        {t("birthChart.northIndian")}
                      </button>
                      <button
                        className={chartStyle === "south" ? "active" : ""}
                        onClick={() => changeChartStyle("south")}
                      >
                        {t("birthChart.southIndian")}
                      </button>
                    </div>

                    <label className="ayanamsa-select">
                      <span>{t("birthChart.ayanamsa")}</span>
                      <select value={ayanamsa} onChange={(e) => changeAyanamsa(e.target.value)}>
                        {AYANAMSAS.map((a) => (
                          <option key={a.value} value={a.value}>
                            {a.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <Kundali
                    chartData={result}
                    title={t("birthChart.rasiChart")}
                    subtitle={`D1 · ${styleLabel}`}
                    exportable
                  />

                  {/* Divisional (varga) chart with picker */}
                  {(() => {
                    const vargaMeta = VARGAS.find((v) => v.value === varga) || VARGAS[0];
                    return (
                      <div className="varga-section">
                        <label className="ayanamsa-select varga-picker">
                          <span>{t("birthChart.divisionalChart")}</span>
                          <select
                            value={varga}
                            onChange={(e) => changeVarga(Number(e.target.value))}
                          >
                            {VARGAS.map((v) => (
                              <option key={v.value} value={v.value}>
                                {v.code} · {v.name}
                              </option>
                            ))}
                          </select>
                          <span className="varga-significance">{vargaMeta.significance}</span>
                        </label>

                        {vargaLoading ? (
                          <div className="varga-loading">
                            <div className="spinner"></div>
                            <span>
                              {t("birthChart.calculatingChart", { code: vargaMeta.code })}
                            </span>
                          </div>
                        ) : vargaChart && vargaChart.planets ? (
                          <Kundali
                            planets={vargaChart.planets}
                            lagna={vargaChart.lagna}
                            title={t("birthChart.nameChart", { name: vargaMeta.name })}
                            subtitle={`${vargaMeta.code} · ${styleLabel}`}
                            exportable
                          />
                        ) : (
                          <div className="varga-empty">{t("birthChart.chartUnavailable")}</div>
                        )}
                      </div>
                    );
                  })()}
                </>
              );
            })()}

            {/* Nakshatra Information Section */}
            {result.lagna || result.d1_chart ? (
              <div
                style={{
                  background: "white",
                  borderRadius: "var(--radius-xl)",
                  padding: "var(--space-xl)",
                  marginTop: "var(--space-xl)",
                  boxShadow: "var(--shadow-lg)",
                  borderTop: "4px solid var(--saffron)",
                }}
              >
                <h3
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-sm)",
                    marginBottom: "var(--space-lg)",
                    color: "var(--cosmic-indigo)",
                    fontSize: "1.5rem",
                  }}
                >
                  <Star size={24} style={{ color: "var(--saffron)" }} />
                  {t("birthChart.nakshatraInfo")}
                </h3>

                {/* Lagna Nakshatra */}
                {result.lagna && result.lagna.nakshatra && (
                  <div
                    style={{
                      padding: "var(--space-lg)",
                      background:
                        "linear-gradient(135deg, rgba(255, 153, 51, 0.05) 0%, rgba(255, 153, 51, 0.15) 100%)",
                      borderRadius: "var(--radius-lg)",
                      marginBottom: "var(--space-lg)",
                      border: "2px solid var(--saffron)",
                    }}
                  >
                    <h4
                      style={{
                        color: "var(--saffron)",
                        marginBottom: "var(--space-md)",
                        fontSize: "1.125rem",
                        fontWeight: 700,
                      }}
                    >
                      {t("birthChart.lagnaAscendant")}
                    </h4>
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                        gap: "var(--space-md)",
                      }}
                    >
                      <div>
                        <span style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
                          {t("common.sign")}:{" "}
                        </span>
                        <span style={{ color: "var(--cosmic-indigo)", fontWeight: 600 }}>
                          {result.lagna.sign_name}
                        </span>
                      </div>
                      <div>
                        <span style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
                          {t("common.nakshatra")}:{" "}
                        </span>
                        <span style={{ color: "var(--cosmic-indigo)", fontWeight: 600 }}>
                          {result.lagna.nakshatra}
                        </span>
                      </div>
                      <div>
                        <span style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
                          {t("common.pada")}:{" "}
                        </span>
                        <span style={{ color: "var(--cosmic-indigo)", fontWeight: 600 }}>
                          {result.lagna.nakshatra_pada}
                        </span>
                      </div>
                      <div>
                        <span style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
                          {t("common.degrees")}:{" "}
                        </span>
                        <span style={{ color: "var(--cosmic-indigo)", fontWeight: 600 }}>
                          {result.lagna.degrees}°
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Planetary Nakshatras */}
                {result.d1_chart && (
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                      gap: "var(--space-md)",
                    }}
                  >
                    {Object.entries(result.d1_chart).map(([planet, data]) => (
                      <div
                        key={planet}
                        style={{
                          padding: "var(--space-md)",
                          background: "var(--sacred-white)",
                          borderRadius: "var(--radius-md)",
                          border: "1px solid var(--sandalwood)",
                          transition: "all 0.3s ease",
                        }}
                        onMouseOver={(e) => {
                          e.currentTarget.style.transform = "translateY(-2px)";
                          e.currentTarget.style.boxShadow = "var(--shadow-md)";
                        }}
                        onMouseOut={(e) => {
                          e.currentTarget.style.transform = "translateY(0)";
                          e.currentTarget.style.boxShadow = "none";
                        }}
                      >
                        <h5
                          style={{
                            color: "var(--saffron)",
                            marginBottom: "var(--space-sm)",
                            fontSize: "1rem",
                            fontWeight: 700,
                          }}
                        >
                          {planet}
                        </h5>
                        <div style={{ fontSize: "0.875rem", lineHeight: "1.6" }}>
                          <div style={{ marginBottom: "var(--space-xs)" }}>
                            <span style={{ color: "var(--text-secondary)" }}>
                              {t("common.sign")}:{" "}
                            </span>
                            <span style={{ color: "var(--cosmic-indigo)", fontWeight: 600 }}>
                              {data.sign_name}
                            </span>
                          </div>
                          {data.nakshatra && (
                            <>
                              <div style={{ marginBottom: "var(--space-xs)" }}>
                                <span style={{ color: "var(--text-secondary)" }}>
                                  {t("common.nakshatra")}:{" "}
                                </span>
                                <span style={{ color: "var(--cosmic-indigo)", fontWeight: 600 }}>
                                  {data.nakshatra}
                                </span>
                              </div>
                              <div style={{ marginBottom: "var(--space-xs)" }}>
                                <span style={{ color: "var(--text-secondary)" }}>
                                  {t("common.pada")}:{" "}
                                </span>
                                <span style={{ color: "var(--cosmic-indigo)", fontWeight: 600 }}>
                                  {data.nakshatra_pada}
                                </span>
                              </div>
                            </>
                          )}
                          <div>
                            <span style={{ color: "var(--text-secondary)" }}>
                              {t("common.degrees")}:{" "}
                            </span>
                            <span style={{ color: "var(--cosmic-indigo)", fontWeight: 600 }}>
                              {data.degrees}°
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : null}

            {/* Panchanga (daily almanac) for the profile's location */}
            <PanchangaPanel
              place={selectedProfile.birth_details.place}
              latitude={parseFloat(selectedProfile.birth_details.latitude)}
              longitude={parseFloat(selectedProfile.birth_details.longitude)}
              timezone={parseFloat(selectedProfile.birth_details.timezone)}
            />

            {/* Yogas */}
            {yogas && yogas.length > 0 && (
              <div
                style={{
                  background: "white",
                  borderRadius: "var(--radius-xl)",
                  padding: "var(--space-xl)",
                  marginTop: "var(--space-xl)",
                  boxShadow: "var(--shadow-lg)",
                  borderTop: "4px solid var(--saffron)",
                }}
              >
                <h3
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-sm)",
                    marginBottom: "var(--space-lg)",
                    color: "var(--cosmic-indigo)",
                    fontSize: "1.5rem",
                  }}
                >
                  <Star size={24} style={{ color: "var(--saffron)" }} />
                  {t("birthChart.yogas")}
                  <span className="section-count">
                    {t("birthChart.yogasFound", { count: yogas.length })}
                  </span>
                </h3>
                <div className="yoga-grid">
                  {yogas.map((y) => (
                    <div key={y.key} className="yoga-card">
                      <div className="yoga-name">{y.name}</div>
                      {y.description && <p className="yoga-desc">{y.description}</p>}
                      {y.benefits && (
                        <div className="yoga-benefit">
                          <span className="yoga-benefit-label">{t("birthChart.effects")}</span>
                          {y.benefits}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Doshas */}
            {doshas && doshas.length > 0 && (
              <div
                style={{
                  background: "white",
                  borderRadius: "var(--radius-xl)",
                  padding: "var(--space-xl)",
                  marginTop: "var(--space-xl)",
                  boxShadow: "var(--shadow-lg)",
                  borderTop: "4px solid var(--saffron)",
                }}
              >
                <h3
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-sm)",
                    marginBottom: "var(--space-lg)",
                    color: "var(--cosmic-indigo)",
                    fontSize: "1.5rem",
                  }}
                >
                  <Star size={24} style={{ color: "var(--saffron)" }} />
                  {t("birthChart.doshas")}
                </h3>
                <div className="dosha-grid">
                  {doshas.map((d) => (
                    <div key={d.key} className={`dosha-card${d.present ? " present" : ""}`}>
                      <div className="dosha-head">
                        <span className="dosha-name">{d.name}</span>
                        <span className={`dosha-badge ${d.present ? "yes" : "no"}`}>
                          {d.present ? t("birthChart.present") : t("birthChart.absent")}
                        </span>
                      </div>
                      <p className="dosha-desc">{d.description}</p>
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
