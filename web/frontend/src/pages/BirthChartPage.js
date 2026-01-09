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
import { astrologyService } from "../services/api";
import { NorthIndianChart } from "../components/NorthIndianChart";
import "../styles/Dashboard.css";

export const BirthChartPage = () => {
  const navigate = useNavigate();
  const { selectedProfile } = useProfile();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  // Redirect if no profile selected, otherwise calculate chart
  useEffect(() => {
    if (!selectedProfile) {
      navigate('/profile-selection');
      return;
    }

    calculateChart();
  }, [selectedProfile, navigate]);

  const calculateChart = async () => {
    if (!selectedProfile) return;

    setLoading(true);
    setError("");

    try {
      const birthDetails = {
        name: selectedProfile.birth_details.name,
        dob: selectedProfile.birth_details.dob,
        tob: selectedProfile.birth_details.tob,
        place: selectedProfile.birth_details.place,
        latitude: parseFloat(selectedProfile.birth_details.latitude),
        longitude: parseFloat(selectedProfile.birth_details.longitude),
        timezone: parseFloat(selectedProfile.birth_details.timezone),
      };

      const response = await astrologyService.calculateBirthChart(birthDetails);
      setResult(response.data);
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
                    {selectedProfile.birth_details.dob.split('T')[0]}
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
                    {selectedProfile.birth_details.tob}
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
                    {selectedProfile.birth_details.place}
                  </div>
                </div>
              </div>
            </div>

            {/* North Indian Chart */}
            <NorthIndianChart chartData={result} />

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
          </div>
        ) : null}
      </div>
    </div>
  );
};
