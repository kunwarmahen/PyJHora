import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Clock, AlertCircle, ArrowLeft, User, Star, ChevronDown, ChevronRight, Calendar } from "lucide-react";
import { useProfile } from "../contexts/ProfileContext";
import { astrologyService } from "../services/api";
import "../styles/Dashboard.css";

export const DhasaPage = () => {
  const navigate = useNavigate();
  const { selectedProfile } = useProfile();

  const [dashaType, setDashaType] = useState("vimsottari");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [expandedDashas, setExpandedDashas] = useState({});
  const [currentDate] = useState(new Date());

  const dashaTypes = [
    { value: "vimsottari", label: "Vimsottari" },
    { value: "ashtottari", label: "Ashtottari" },
    { value: "yogini", label: "Yogini" },
    { value: "shodasottari", label: "Shodasottari" },
  ];

  // Redirect if no profile selected, otherwise calculate dasha
  useEffect(() => {
    if (!selectedProfile) {
      navigate('/profile-selection');
      return;
    }

    calculateDasha();
  }, [selectedProfile, dashaType, navigate]);

  const calculateDasha = async () => {
    if (!selectedProfile) return;

    setLoading(true);
    setError("");

    try {
      const response = await astrologyService.getDhasa(
        {
          name: selectedProfile.birth_details.name,
          dob: selectedProfile.birth_details.dob,
          tob: selectedProfile.birth_details.tob,
          place: selectedProfile.birth_details.place,
        },
        dashaType
      );
      setResult(response.data);

      // Auto-expand current dasha if found
      if (response.data.current_dasha) {
        setExpandedDashas({ [response.data.current_dasha.lord]: true });
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to calculate Dasha");
    } finally {
      setLoading(false);
    }
  };

  const toggleDasha = (lord) => {
    setExpandedDashas(prev => ({
      ...prev,
      [lord]: !prev[lord]
    }));
  };

  // Helper function to check if a period is current
  const isCurrentPeriod = (startDate, endDate) => {
    if (!startDate || !endDate) return false;
    try {
      const start = new Date(startDate);
      const end = new Date(endDate);
      return currentDate >= start && currentDate <= end;
    } catch (e) {
      return false;
    }
  };

  // Helper function to format date
  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    } catch (e) {
      return 'N/A';
    }
  };

  // Find current Maha Dasha from sequence
  const getCurrentMahaDasha = () => {
    if (!result || !result.dasha_sequence) return null;

    for (const dasha of result.dasha_sequence) {
      if (dasha.start_date && dasha.end_date) {
        if (isCurrentPeriod(dasha.start_date, dasha.end_date)) {
          return dasha;
        }
      }
    }
    return null;
  };

  // Find current sub-period (Antar Dasha) within a Maha Dasha
  const getCurrentSubPeriod = (mahaDasha) => {
    if (!mahaDasha || !mahaDasha.sub_periods) return null;

    for (const subPeriod of mahaDasha.sub_periods) {
      if (subPeriod.start_date && subPeriod.end_date) {
        if (isCurrentPeriod(subPeriod.start_date, subPeriod.end_date)) {
          return subPeriod;
        }
      }
    }
    return null;
  };

  const currentMahaDasha = getCurrentMahaDasha();
  const currentSubPeriod = currentMahaDasha ? getCurrentSubPeriod(currentMahaDasha) : null;

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
              background: 'linear-gradient(135deg, var(--cosmic-indigo) 0%, var(--cosmic-indigo-light) 100%)',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white'
            }}>
              <Clock size={24} />
            </div>
            <div>
              <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Dasha Periods</h1>
              <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                Planetary Time Periods
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
                <span>{selectedProfile.birth_details.dob.split('T')[0]}</span>
                <span className="separator">•</span>
                <span>{selectedProfile.birth_details.place}</span>
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

        {/* Dasha Type Selector */}
        <div style={{
          background: 'white',
          borderRadius: 'var(--radius-xl)',
          padding: 'var(--space-xl)',
          marginBottom: 'var(--space-xl)',
          boxShadow: 'var(--shadow-lg)',
          borderTop: '4px solid var(--cosmic-indigo)',
          opacity: 0,
          animation: 'fadeIn 0.6s ease-out forwards'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 'var(--space-lg)',
            flexWrap: 'wrap',
            gap: 'var(--space-md)'
          }}>
            <h3 style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-sm)',
              margin: 0,
              color: 'var(--cosmic-indigo)',
              fontSize: '1.25rem'
            }}>
              <Clock size={20} style={{ color: 'var(--saffron)' }} />
              Select Dasha System
            </h3>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-sm)',
              padding: 'var(--space-sm) var(--space-md)',
              background: 'rgba(255, 153, 51, 0.1)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.875rem',
              color: 'var(--saffron)',
              fontWeight: 600
            }}>
              <Calendar size={16} />
              Today: {currentDate.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
            </div>
          </div>
          <select
            value={dashaType}
            onChange={(e) => setDashaType(e.target.value)}
            style={{
              width: '100%',
              padding: 'var(--space-md)',
              borderRadius: 'var(--radius-md)',
              border: '2px solid var(--sandalwood)',
              fontSize: '1rem',
              background: 'var(--sacred-white)',
              color: 'var(--text-primary)',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.3s ease'
            }}
            onFocus={(e) => e.target.style.borderColor = 'var(--saffron)'}
            onBlur={(e) => e.target.style.borderColor = 'var(--sandalwood)'}
          >
            {dashaTypes.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>

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
              Calculating {dashaType.charAt(0).toUpperCase() + dashaType.slice(1)} Dasha
            </h3>
            <p style={{ color: 'var(--text-secondary)' }}>
              Analyzing planetary periods...
            </p>
          </div>
        ) : result ? (
          <div style={{ opacity: 0, animation: 'fadeIn 0.6s ease-out forwards', animationDelay: '0.2s' }}>
            {/* Current Period Highlight */}
            {currentMahaDasha && (
              <div style={{
                background: 'linear-gradient(135deg, rgba(255, 153, 51, 0.1) 0%, rgba(226, 123, 90, 0.1) 100%)',
                border: '3px solid var(--saffron)',
                borderRadius: 'var(--radius-xl)',
                padding: 'var(--space-xl)',
                marginBottom: 'var(--space-xl)',
                boxShadow: '0 0 24px rgba(255, 153, 51, 0.2)',
                animation: 'pulse-glow 3s ease-in-out infinite'
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-sm)',
                  marginBottom: 'var(--space-md)'
                }}>
                  <div style={{
                    width: '40px',
                    height: '40px',
                    background: 'linear-gradient(135deg, var(--saffron) 0%, var(--vermillion) 100%)',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    fontWeight: 700
                  }}>
                    <Clock size={20} />
                  </div>
                  <h3 style={{ margin: 0, color: 'var(--cosmic-indigo)', fontSize: '1.5rem' }}>
                    Current Period
                  </h3>
                </div>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                  gap: 'var(--space-md)',
                  marginTop: 'var(--space-lg)'
                }}>
                  <div>
                    <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 'var(--space-xs)' }}>
                      Maha Dasha
                    </div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--saffron)' }}>
                      {currentMahaDasha.lord}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 'var(--space-xs)' }}>
                      Duration
                    </div>
                    <div style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--cosmic-indigo)' }}>
                      {currentMahaDasha.duration_years} years
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 'var(--space-xs)' }}>
                      Period
                    </div>
                    <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--cosmic-indigo)' }}>
                      {formatDate(currentMahaDasha.start_date)} - {formatDate(currentMahaDasha.end_date)}
                    </div>
                  </div>
                  {currentSubPeriod && (
                    <div>
                      <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)', marginBottom: 'var(--space-xs)' }}>
                        Current Sub-Period
                      </div>
                      <div style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--vermillion)' }}>
                        {currentSubPeriod.lord}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: 'var(--space-xs)' }}>
                        {formatDate(currentSubPeriod.start_date)} - {formatDate(currentSubPeriod.end_date)}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* All Dasha Periods */}
            <div style={{
              background: 'white',
              borderRadius: 'var(--radius-xl)',
              padding: 'var(--space-xl)',
              boxShadow: 'var(--shadow-lg)',
              borderTop: '4px solid var(--cosmic-indigo)'
            }}>
              <h3 style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-sm)',
                marginBottom: 'var(--space-xl)',
                color: 'var(--cosmic-indigo)',
                fontSize: '1.5rem'
              }}>
                <Star size={24} style={{ color: 'var(--saffron)' }} />
                All Maha Dasha Periods
              </h3>

              {/* Dasha Sequence with Expandable Sub-Periods */}
              {result.dasha_sequence && result.dasha_sequence.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
                  {result.dasha_sequence.map((dasha, index) => {
                    const isCurrent = isCurrentPeriod(dasha.start_date, dasha.end_date);
                    const isExpanded = expandedDashas[dasha.lord];
                    const hasSubPeriods = dasha.sub_periods && dasha.sub_periods.length > 0;

                    return (
                      <div key={index} style={{
                        border: isCurrent ? '2px solid var(--saffron)' : '2px solid var(--sandalwood)',
                        borderRadius: 'var(--radius-lg)',
                        overflow: 'hidden',
                        transition: 'all 0.3s ease',
                        background: isCurrent ? 'rgba(255, 153, 51, 0.05)' : 'var(--sacred-white)'
                      }}>
                        {/* Maha Dasha Header */}
                        <div
                          onClick={() => hasSubPeriods && toggleDasha(dasha.lord)}
                          style={{
                            padding: 'var(--space-lg)',
                            cursor: hasSubPeriods ? 'pointer' : 'default',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            transition: 'background 0.2s ease'
                          }}
                          onMouseOver={(e) => hasSubPeriods && (e.currentTarget.style.background = 'rgba(255, 153, 51, 0.08)')}
                          onMouseOut={(e) => hasSubPeriods && (e.currentTarget.style.background = 'transparent')}
                        >
                          <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'auto 1fr auto auto', gap: 'var(--space-lg)', alignItems: 'center' }}>
                            <div style={{
                              width: '40px',
                              height: '40px',
                              background: isCurrent ? 'linear-gradient(135deg, var(--saffron) 0%, var(--vermillion) 100%)' : 'linear-gradient(135deg, var(--cosmic-indigo) 0%, var(--cosmic-indigo-light) 100%)',
                              borderRadius: '50%',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: 'white',
                              fontWeight: 700,
                              fontSize: '0.875rem'
                            }}>
                              {dasha.order || index + 1}
                            </div>
                            <div>
                              <div style={{ fontSize: '1.125rem', fontWeight: 700, color: isCurrent ? 'var(--saffron)' : 'var(--cosmic-indigo)', marginBottom: 'var(--space-xs)' }}>
                                {dasha.lord}
                              </div>
                              <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                                {dasha.duration_years} years
                                {dasha.start_date && dasha.end_date && (
                                  <span> • {formatDate(dasha.start_date)} to {formatDate(dasha.end_date)}</span>
                                )}
                              </div>
                            </div>
                            {isCurrent && (
                              <div style={{
                                padding: 'var(--space-xs) var(--space-md)',
                                background: 'var(--saffron)',
                                color: 'white',
                                borderRadius: 'var(--radius-full)',
                                fontSize: '0.75rem',
                                fontWeight: 700,
                                textTransform: 'uppercase',
                                letterSpacing: '0.5px'
                              }}>
                                Current
                              </div>
                            )}
                            {hasSubPeriods && (
                              <div style={{ color: 'var(--saffron)', transition: 'transform 0.3s ease', transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}>
                                <ChevronDown size={24} />
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Sub-Periods (Antar Dasha) */}
                        {hasSubPeriods && isExpanded && (
                          <div style={{
                            borderTop: '1px solid var(--sandalwood)',
                            padding: 'var(--space-lg)',
                            background: 'white'
                          }}>
                            <h4 style={{
                              fontSize: '1rem',
                              fontWeight: 600,
                              color: 'var(--cosmic-indigo)',
                              marginBottom: 'var(--space-md)',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 'var(--space-sm)'
                            }}>
                              <ChevronRight size={18} style={{ color: 'var(--saffron)' }} />
                              Sub-Periods (Antar Dasha)
                            </h4>
                            <div style={{ display: 'grid', gap: 'var(--space-sm)' }}>
                              {dasha.sub_periods.map((subPeriod, subIndex) => {
                                const isCurrentSub = isCurrentPeriod(subPeriod.start_date, subPeriod.end_date);

                                return (
                                  <div key={subIndex} style={{
                                    padding: 'var(--space-md)',
                                    background: isCurrentSub ? 'rgba(227, 66, 52, 0.1)' : 'var(--sacred-white)',
                                    border: isCurrentSub ? '2px solid var(--vermillion)' : '1px solid var(--sandalwood)',
                                    borderRadius: 'var(--radius-md)',
                                    display: 'grid',
                                    gridTemplateColumns: 'auto 1fr auto',
                                    gap: 'var(--space-md)',
                                    alignItems: 'center'
                                  }}>
                                    <div style={{
                                      width: '32px',
                                      height: '32px',
                                      background: isCurrentSub ? 'linear-gradient(135deg, var(--vermillion) 0%, var(--terracotta) 100%)' : 'var(--sandalwood)',
                                      borderRadius: '50%',
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'center',
                                      color: isCurrentSub ? 'white' : 'var(--cosmic-indigo)',
                                      fontWeight: 600,
                                      fontSize: '0.75rem'
                                    }}>
                                      {subIndex + 1}
                                    </div>
                                    <div>
                                      <div style={{ fontSize: '0.9375rem', fontWeight: 600, color: isCurrentSub ? 'var(--vermillion)' : 'var(--cosmic-indigo)' }}>
                                        {subPeriod.lord}
                                      </div>
                                      <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                                        {subPeriod.duration_months && `${subPeriod.duration_months} months`}
                                        {subPeriod.start_date && subPeriod.end_date && (
                                          <span> • {formatDate(subPeriod.start_date)} to {formatDate(subPeriod.end_date)}</span>
                                        )}
                                      </div>
                                    </div>
                                    {isCurrentSub && (
                                      <div style={{
                                        padding: 'var(--space-xs) var(--space-sm)',
                                        background: 'var(--vermillion)',
                                        color: 'white',
                                        borderRadius: 'var(--radius-sm)',
                                        fontSize: '0.6875rem',
                                        fontWeight: 700,
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.5px'
                                      }}>
                                        Now
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};
