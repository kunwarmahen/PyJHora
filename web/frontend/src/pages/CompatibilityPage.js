import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Heart, AlertCircle, ArrowLeft, User } from 'lucide-react';
import { useProfile } from '../contexts/ProfileContext';
import { astrologyService } from '../services/api';
import '../styles/Forms.css';

export const CompatibilityPage = () => {
  const navigate = useNavigate();
  const { selectedProfile, profiles, loadProfiles } = useProfile();

  const [secondProfile, setSecondProfile] = useState(null);
  const [useQwen, setUseQwen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  // Redirect if no profile selected
  useEffect(() => {
    if (!selectedProfile) {
      navigate('/profile-selection');
      return;
    }

    loadProfiles();
  }, [selectedProfile, navigate]);

  const handleCalculate = async () => {
    if (!secondProfile) {
      setError('Please select a second profile for compatibility check');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const person1Data = {
        dob: selectedProfile.birth_details.dob,
        tob: selectedProfile.birth_details.tob,
        place: selectedProfile.birth_details.place,
        latitude: parseFloat(selectedProfile.birth_details.latitude),
        longitude: parseFloat(selectedProfile.birth_details.longitude),
        timezone: parseFloat(selectedProfile.birth_details.timezone),
      };

      const person2Data = {
        dob: secondProfile.birth_details.dob,
        tob: secondProfile.birth_details.tob,
        place: secondProfile.birth_details.place,
        latitude: parseFloat(secondProfile.birth_details.latitude),
        longitude: parseFloat(secondProfile.birth_details.longitude),
        timezone: parseFloat(secondProfile.birth_details.timezone),
      };

      const response = await astrologyService.getCompatibility(person1Data, person2Data, useQwen);
      setResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to calculate compatibility');
    } finally {
      setLoading(false);
    }
  };

  if (!selectedProfile) {
    return null;
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <button onClick={() => navigate('/dashboard')} className="back-button">
          <ArrowLeft size={20} />
        </button>
        <Heart size={32} />
        <div>
          <h1>Compatibility Check</h1>
          <p>Compare two birth charts</p>
        </div>
      </div>

      <div className="form-wrapper">
        {error && (
          <div className="error-box">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        <div style={{ display: 'grid', gap: '20px' }}>
          {/* Person 1 - Selected Profile */}
          <div style={{ padding: '20px', background: 'white', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
            <h3 style={{ marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <User size={20} /> Person 1 (Selected Profile)
            </h3>
            <div style={{ padding: '15px', background: '#f0f9ff', borderRadius: '8px' }}>
              <p style={{ margin: '0 0 8px 0', fontWeight: '600' }}>{selectedProfile.profile_name}</p>
              <div style={{ fontSize: '14px', color: '#666' }}>
                <div>{selectedProfile.birth_details.name || 'Anonymous'}</div>
                <div>{selectedProfile.birth_details.dob.split('T')[0]} at {selectedProfile.birth_details.tob}</div>
                <div>{selectedProfile.birth_details.place}</div>
              </div>
            </div>
          </div>

          {/* Person 2 - Select from profiles */}
          <div style={{ padding: '20px', background: 'white', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
            <h3 style={{ marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <User size={20} /> Person 2
            </h3>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500' }}>
              Select Profile to Compare:
            </label>
            <select
              value={secondProfile?._id || ''}
              onChange={(e) => {
                const profile = profiles.find(p => p._id === e.target.value);
                setSecondProfile(profile || null);
                setResult(null); // Clear previous results
              }}
              style={{ width: '100%', padding: '12px', borderRadius: '8px', border: '2px solid #e0e0e0', fontSize: '16px' }}
            >
              <option value="">-- Select a profile to compare --</option>
              {profiles.filter(p => p._id !== selectedProfile._id).map(profile => (
                <option key={profile._id} value={profile._id}>
                  {profile.profile_name} ({profile.birth_details.name || 'Anonymous'})
                </option>
              ))}
            </select>

            {secondProfile && (
              <div style={{ marginTop: '15px', padding: '15px', background: '#fef3f2', borderRadius: '8px' }}>
                <p style={{ margin: '0 0 8px 0', fontWeight: '600' }}>{secondProfile.profile_name}</p>
                <div style={{ fontSize: '14px', color: '#666' }}>
                  <div>{secondProfile.birth_details.name || 'Anonymous'}</div>
                  <div>{secondProfile.birth_details.dob.split('T')[0]} at {secondProfile.birth_details.tob}</div>
                  <div>{secondProfile.birth_details.place}</div>
                </div>
              </div>
            )}
          </div>

          {/* AI Toggle */}
          <div style={{ padding: '15px', background: 'white', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input
              type="checkbox"
              id="useQwen"
              checked={useQwen}
              onChange={(e) => setUseQwen(e.target.checked)}
              style={{ width: '20px', height: '20px' }}
            />
            <label htmlFor="useQwen" style={{ cursor: 'pointer', fontSize: '16px' }}>Use AI for detailed compatibility analysis</label>
          </div>

          {/* Calculate Button */}
          <button
            onClick={handleCalculate}
            disabled={loading || !secondProfile}
            style={{
              padding: '16px',
              background: secondProfile ? 'linear-gradient(135deg, #ff9933 0%, #e34234 100%)' : '#ccc',
              color: 'white',
              border: 'none',
              borderRadius: '12px',
              fontSize: '18px',
              fontWeight: '600',
              cursor: secondProfile ? 'pointer' : 'not-allowed',
              boxShadow: secondProfile ? '0 4px 16px rgba(255, 153, 51, 0.3)' : 'none',
              transition: 'all 0.3s ease'
            }}
          >
            {loading ? 'Calculating Compatibility...' : 'Check Compatibility'}
          </button>
        </div>

        {result && (
          <div className="result-box" style={{ marginTop: '30px' }}>
            <div className="result-header">
              <Heart size={24} style={{ color: '#ff9933' }} />
              <h2>Compatibility Score</h2>
            </div>

            <div className="result-content">
              <div className="score-display">
                <div className="score-item">
                  <span className="label">Total Score:</span>
                  <span className="value">{result.total_score}/36</span>
                </div>
              </div>

              <div className="compatibility-items">
                <div className="item">
                  <span>Dina:</span>
                  <span>{result.dinam}/6</span>
                </div>
                <div className="item">
                  <span>Gana:</span>
                  <span>{result.ganam}/6</span>
                </div>
                <div className="item">
                  <span>Yoni:</span>
                  <span>{result.yoni}/6</span>
                </div>
                <div className="item">
                  <span>Rasi:</span>
                  <span>{result.rasi}/7</span>
                </div>
                <div className="item">
                  <span>Rajju:</span>
                  <span>{result.rajju}/3</span>
                </div>
                <div className="item">
                  <span>Vedha:</span>
                  <span>{result.vedha}/3</span>
                </div>
              </div>

              <div className="status-section">
                <p>
                  <strong>Status:</strong> {result.status}
                </p>
              </div>

              {result.ai_analysis && (
                <div className="ai-analysis">
                  <h3>AI Analysis</h3>
                  <p>{result.ai_analysis}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
