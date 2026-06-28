import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  Calendar,
  User,
  MapPin,
  Clock,
  Star,
} from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { formatDate, orDash } from "../utils/format";
import { astrologyService } from "../services/api";
import { NorthIndianChart } from "../components/NorthIndianChart";
import { SouthIndianChart } from "../components/SouthIndianChart";
import { PanchangaPanel } from "../components/PanchangaPanel";
import { AYANAMSAS, DEFAULT_AYANAMSA, VARGAS, DEFAULT_VARGA } from "../constants/jyotish";
import "../styles/Dashboard.css";

export const BirthChartPage = () => {
  const navigate = useNavigate();
  const { selectedProfile } = useProfile();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [doshas, setDoshas] = useState(null);
  const [yogas, setYogas] = useState(null);
  const [chartStyle, setChartStyle] = useState(
    () => localStorage.getItem("chartStyle") || "north"
  );
  const [ayanamsa, setAyanamsa] = useState(
    () => localStorage.getItem("ayanamsa") || DEFAULT_AYANAMSA
  );
  const [varga, setVarga] = useState(
    () => Number(localStorage.getItem("varga")) || DEFAULT_VARGA
  );
  const [vargaChart, setVargaChart] = useState(null);
  const [vargaLoading, setVargaLoading] = useState(false);

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

  // Redirect if no profile selected; (re)calculate when profile or ayanamsa changes
  useEffect(() => {
    if (!selectedProfile) {
      navigate('/profile-selection');
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
      setError(err.response?.data?.detail || "Failed to calculate chart");
    } finally {
      setLoading(false);
    }
  };

  if (!selectedProfile) {
    return null;
  }

  return (
    <div className="dashboard-container mandala-bg">
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-brand">
          <button onClick={() => navigate('/dashboard')} style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-sm)',
            color: 'var(--saffron)',
            padding: 'var(--space-sm) var(--space-md)',
            borderRadius: 'var(--radius-md)',
            transition: 'all 0.3s ease'
          }}
          onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255, 153, 51, 0.1)'}
          onMouseOut={(e) => e.currentTarget.style.background = 'none'}>
            <ArrowLeft size={20} />
            <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>Back</span>
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)', marginLeft: 'var(--space-lg)' }}>
            <div style={{
              width: '48px',
              height: '48px',
              background: 'linear-gradient(135deg, var(--saffron) 0%, var(--vermillion) 100%)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white'
            }}>
              <Calendar size={24} />
            </div>
            <div>
              <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Birth Chart</h1>
              <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                Rasi & Navamsa Charts
              </p>
            </div>
          </div>
        </div>
      </nav>

      {/* Content */}
      <div className="dashboard-content">
        {/* Profile Banner */}
        <div className="profile-banner fade-in">
          <div className="profile-banner-left">
            <div className="profile-avatar-large">
              <User size={32} />
            </div>
            <div className="profile-info">
              <h2>{selectedProfile.profile_name}</h2>
              <div className="profile-meta">
                <span>{selectedProfile.birth_details.name || 'Anonymous'}</span>
                <span className="separator">•</span>
                <span>{formatDate(selectedProfile.birth_details.dob)}</span>
                <span className="separator">•</span>
                <span>{orDash(selectedProfile.birth_details.place)}</span>
              </div>
            </div>
          </div>
          <button onClick={() => navigate('/profile-selection')} className="change-profile-btn">
            <Star size={16} />
            <span>Change Chart</span>
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div style={{
            background: 'rgba(227, 66, 52, 0.1)',
            border: '2px solid rgba(227, 66, 52, 0.3)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-lg)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-md)',
            color: 'var(--vermillion)',
            marginBottom: 'var(--space-xl)',
            animation: 'fadeIn 0.5s ease-out'
          }}>
            <AlertCircle size={24} />
            <span style={{ fontWeight: 500 }}>{error}</span>
          </div>
        )}

        {/* Loading State */}
        {loading ? (
          <div style={{
            background: 'white',
            borderRadius: 'var(--radius-xl)',
            padding: 'var(--space-3xl)',
            textAlign: 'center',
            boxShadow: 'var(--shadow-lg)',
            animation: 'fadeIn 0.6s ease-out'
          }}>
            <div className="spinner" style={{ margin: '0 auto var(--space-xl)' }}></div>
            <h3 style={{ color: 'var(--cosmic-indigo)', marginBottom: 'var(--space-sm)' }}>
              Calculating Birth Chart
            </h3>
            <p style={{ color: 'var(--text-secondary)' }}>
              Analyzing planetary positions and generating charts...
            </p>
          </div>
        ) : result ? (
          <div style={{ opacity: 0, animation: 'fadeIn 0.6s ease-out forwards' }}>
            {/* Chart Details Card */}
            <div style={{
              background: 'white',
              borderRadius: 'var(--radius-xl)',
              padding: 'var(--space-xl)',
              marginBottom: 'var(--space-xl)',
              boxShadow: 'var(--shadow-lg)',
              borderTop: '4px solid var(--saffron)'
            }}>
              <h3 style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-sm)',
                marginBottom: 'var(--space-lg)',
                color: 'var(--cosmic-indigo)',
                fontSize: '1.5rem'
              }}>
                <Star size={24} style={{ color: 'var(--saffron)' }} />
                Chart Details
              </h3>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                gap: 'var(--space-lg)'
              }}>
                <div style={{
                  padding: 'var(--space-md)',
                  background: 'var(--sacred-white)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--sandalwood)'
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-sm)',
                    marginBottom: 'var(--space-sm)',
                    color: 'var(--saffron)'
                  }}>
                    <User size={16} />
                    <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
                      Name
                    </span>
                  </div>
                  <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--cosmic-indigo)' }}>
                    {selectedProfile.birth_details.name || selectedProfile.profile_name}
                  </div>
                </div>
                <div style={{
                  padding: 'var(--space-md)',
                  background: 'var(--sacred-white)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--sandalwood)'
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-sm)',
                    marginBottom: 'var(--space-sm)',
                    color: 'var(--saffron)'
                  }}>
                    <Calendar size={16} />
                    <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
                      Date of Birth
                    </span>
                  </div>
                  <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--cosmic-indigo)' }}>
                    {formatDate(selectedProfile.birth_details.dob)}
                  </div>
                </div>
                <div style={{
                  padding: 'var(--space-md)',
                  background: 'var(--sacred-white)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--sandalwood)'
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-sm)',
                    marginBottom: 'var(--space-sm)',
                    color: 'var(--saffron)'
                  }}>
                    <Clock size={16} />
                    <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
                      Time of Birth
                    </span>
                  </div>
                  <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--cosmic-indigo)' }}>
                    {orDash(selectedProfile.birth_details.tob)}
                  </div>
                </div>
                <div style={{
                  padding: 'var(--space-md)',
                  background: 'var(--sacred-white)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--sandalwood)'
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-sm)',
                    marginBottom: 'var(--space-sm)',
                    color: 'var(--saffron)'
                  }}>
                    <MapPin size={16} />
                    <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
                      Place
                    </span>
                  </div>
                  <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--cosmic-indigo)' }}>
                    {orDash(selectedProfile.birth_details.place)}
                  </div>
                </div>
              </div>
            </div>

            {/* Chart style toggle: North / South Indian */}
            {(() => {
              const Kundali = chartStyle === "south" ? SouthIndianChart : NorthIndianChart;
              const styleLabel = chartStyle === "south" ? "South Indian" : "North Indian";
              return (
                <>
                  <div className="chart-controls">
                    <div className="chart-style-toggle" role="group" aria-label="Chart style">
                      <button
                        className={chartStyle === "north" ? "active" : ""}
                        onClick={() => changeChartStyle("north")}
                      >
                        North Indian
                      </button>
                      <button
                        className={chartStyle === "south" ? "active" : ""}
                        onClick={() => changeChartStyle("south")}
                      >
                        South Indian
                      </button>
                    </div>

                    <label className="ayanamsa-select">
                      <span>Ayanamsa</span>
                      <select value={ayanamsa} onChange={(e) => changeAyanamsa(e.target.value)}>
                        {AYANAMSAS.map((a) => (
                          <option key={a.value} value={a.value}>{a.label}</option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <Kundali chartData={result} title="Rasi Chart" subtitle={`D1 · ${styleLabel}`} />

                  {/* Divisional (varga) chart with picker */}
                  {(() => {
                    const vargaMeta = VARGAS.find((v) => v.value === varga) || VARGAS[0];
                    return (
                      <div className="varga-section">
                        <label className="ayanamsa-select varga-picker">
                          <span>Divisional Chart</span>
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
                            <span>Calculating {vargaMeta.code} chart…</span>
                          </div>
                        ) : vargaChart && vargaChart.planets ? (
                          <Kundali
                            planets={vargaChart.planets}
                            lagna={vargaChart.lagna}
                            title={`${vargaMeta.name} Chart`}
                            subtitle={`${vargaMeta.code} · ${styleLabel}`}
                          />
                        ) : (
                          <div className="varga-empty">Divisional chart unavailable.</div>
                        )}
                      </div>
                    );
                  })()}
                </>
              );
            })()}

            {/* Nakshatra Information Section */}
            {result.lagna || result.d1_chart ? (
              <div style={{
                background: 'white',
                borderRadius: 'var(--radius-xl)',
                padding: 'var(--space-xl)',
                marginTop: 'var(--space-xl)',
                boxShadow: 'var(--shadow-lg)',
                borderTop: '4px solid var(--saffron)'
              }}>
                <h3 style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-sm)',
                  marginBottom: 'var(--space-lg)',
                  color: 'var(--cosmic-indigo)',
                  fontSize: '1.5rem'
                }}>
                  <Star size={24} style={{ color: 'var(--saffron)' }} />
                  Nakshatra Information
                </h3>

                {/* Lagna Nakshatra */}
                {result.lagna && result.lagna.nakshatra && (
                  <div style={{
                    padding: 'var(--space-lg)',
                    background: 'linear-gradient(135deg, rgba(255, 153, 51, 0.05) 0%, rgba(255, 153, 51, 0.15) 100%)',
                    borderRadius: 'var(--radius-lg)',
                    marginBottom: 'var(--space-lg)',
                    border: '2px solid var(--saffron)'
                  }}>
                    <h4 style={{
                      color: 'var(--saffron)',
                      marginBottom: 'var(--space-md)',
                      fontSize: '1.125rem',
                      fontWeight: 700
                    }}>
                      Lagna (Ascendant)
                    </h4>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-md)' }}>
                      <div>
                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Sign: </span>
                        <span style={{ color: 'var(--cosmic-indigo)', fontWeight: 600 }}>{result.lagna.sign_name}</span>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Nakshatra: </span>
                        <span style={{ color: 'var(--cosmic-indigo)', fontWeight: 600 }}>{result.lagna.nakshatra}</span>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Pada: </span>
                        <span style={{ color: 'var(--cosmic-indigo)', fontWeight: 600 }}>{result.lagna.nakshatra_pada}</span>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>Degrees: </span>
                        <span style={{ color: 'var(--cosmic-indigo)', fontWeight: 600 }}>{result.lagna.degrees}°</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Planetary Nakshatras */}
                {result.d1_chart && (
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: 'var(--space-md)'
                  }}>
                    {Object.entries(result.d1_chart).map(([planet, data]) => (
                      <div key={planet} style={{
                        padding: 'var(--space-md)',
                        background: 'var(--sacred-white)',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--sandalwood)',
                        transition: 'all 0.3s ease'
                      }}
                      onMouseOver={(e) => {
                        e.currentTarget.style.transform = 'translateY(-2px)';
                        e.currentTarget.style.boxShadow = 'var(--shadow-md)';
                      }}
                      onMouseOut={(e) => {
                        e.currentTarget.style.transform = 'translateY(0)';
                        e.currentTarget.style.boxShadow = 'none';
                      }}>
                        <h5 style={{
                          color: 'var(--saffron)',
                          marginBottom: 'var(--space-sm)',
                          fontSize: '1rem',
                          fontWeight: 700
                        }}>
                          {planet}
                        </h5>
                        <div style={{ fontSize: '0.875rem', lineHeight: '1.6' }}>
                          <div style={{ marginBottom: 'var(--space-xs)' }}>
                            <span style={{ color: 'var(--text-secondary)' }}>Sign: </span>
                            <span style={{ color: 'var(--cosmic-indigo)', fontWeight: 600 }}>{data.sign_name}</span>
                          </div>
                          {data.nakshatra && (
                            <>
                              <div style={{ marginBottom: 'var(--space-xs)' }}>
                                <span style={{ color: 'var(--text-secondary)' }}>Nakshatra: </span>
                                <span style={{ color: 'var(--cosmic-indigo)', fontWeight: 600 }}>{data.nakshatra}</span>
                              </div>
                              <div style={{ marginBottom: 'var(--space-xs)' }}>
                                <span style={{ color: 'var(--text-secondary)' }}>Pada: </span>
                                <span style={{ color: 'var(--cosmic-indigo)', fontWeight: 600 }}>{data.nakshatra_pada}</span>
                              </div>
                            </>
                          )}
                          <div>
                            <span style={{ color: 'var(--text-secondary)' }}>Degrees: </span>
                            <span style={{ color: 'var(--cosmic-indigo)', fontWeight: 600 }}>{data.degrees}°</span>
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
              <div style={{
                background: 'white',
                borderRadius: 'var(--radius-xl)',
                padding: 'var(--space-xl)',
                marginTop: 'var(--space-xl)',
                boxShadow: 'var(--shadow-lg)',
                borderTop: '4px solid var(--saffron)'
              }}>
                <h3 style={{
                  display: 'flex', alignItems: 'center', gap: 'var(--space-sm)',
                  marginBottom: 'var(--space-lg)', color: 'var(--cosmic-indigo)', fontSize: '1.5rem'
                }}>
                  <Star size={24} style={{ color: 'var(--saffron)' }} />
                  Yogas
                  <span className="section-count">{yogas.length} found</span>
                </h3>
                <div className="yoga-grid">
                  {yogas.map((y) => (
                    <div key={y.key} className="yoga-card">
                      <div className="yoga-name">{y.name}</div>
                      {y.description && <p className="yoga-desc">{y.description}</p>}
                      {y.benefits && (
                        <div className="yoga-benefit">
                          <span className="yoga-benefit-label">Effects</span>
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
              <div style={{
                background: 'white',
                borderRadius: 'var(--radius-xl)',
                padding: 'var(--space-xl)',
                marginTop: 'var(--space-xl)',
                boxShadow: 'var(--shadow-lg)',
                borderTop: '4px solid var(--saffron)'
              }}>
                <h3 style={{
                  display: 'flex', alignItems: 'center', gap: 'var(--space-sm)',
                  marginBottom: 'var(--space-lg)', color: 'var(--cosmic-indigo)', fontSize: '1.5rem'
                }}>
                  <Star size={24} style={{ color: 'var(--saffron)' }} />
                  Doshas
                </h3>
                <div className="dosha-grid">
                  {doshas.map((d) => (
                    <div key={d.key} className={`dosha-card${d.present ? ' present' : ''}`}>
                      <div className="dosha-head">
                        <span className="dosha-name">{d.name}</span>
                        <span className={`dosha-badge ${d.present ? 'yes' : 'no'}`}>
                          {d.present ? 'Present' : 'Absent'}
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
