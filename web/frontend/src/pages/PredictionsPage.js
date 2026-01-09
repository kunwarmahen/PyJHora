import React, { useState } from 'react';
import { Zap, AlertCircle, CheckCircle, MapPin } from 'lucide-react';
import { astrologyService } from '../services/api';
import LocationSearch from '../components/LocationSearch';
import '../styles/Forms.css';

export const PredictionsPage = () => {
  const [formData, setFormData] = useState({
    name: '',
    dob: '',
    tob: '',
    place: '',
    latitude: null,
    longitude: null,
    timezone: null,
  });
  const [predictionType, setPredictionType] = useState('horoscope');
  const [useQwen, setUseQwen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const predictionTypes = [
    { value: 'horoscope', label: 'Horoscope & General Predictions' },
    { value: 'health', label: 'Health Predictions' },
    { value: 'career', label: 'Career Predictions' },
    { value: 'transit', label: 'Current Transits' },
  ];

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleLocationSelect = (location) => {
    setFormData((prev) => ({
      ...prev,
      place: location.place,
      latitude: location.latitude,
      longitude: location.longitude,
      timezone: location.timezone,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Validate location data
    if (!formData.latitude || !formData.longitude || !formData.timezone) {
      setError('Please search for a location using the location search above');
      return;
    }

    setLoading(true);
    setError('');

    try {
      let response;
      const birthDetails = {
        name: formData.name,
        dob: formData.dob,
        tob: formData.tob,
        place: formData.place,
        latitude: formData.latitude,
        longitude: formData.longitude,
        timezone: formData.timezone,
      };

      switch (predictionType) {
        case 'horoscope':
          response = await astrologyService.getHoroscope(birthDetails, useQwen);
          break;
        case 'transit':
          response = await astrologyService.getTransits(birthDetails);
          break;
        default:
          response = await astrologyService.getHoroscope(birthDetails, useQwen);
      }

      setResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to generate predictions');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <div className="form-wrapper">
        <h1>Predictions</h1>
        <p className="subtitle">Get personalized astrological predictions</p>

        {error && (
          <div className="error-box">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="astrology-form">
          <div className="form-row">
            <div className="form-group">
              <label>Name *</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleInputChange}
                placeholder="Your full name"
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Date of Birth (YYYY-MM-DD) *</label>
              <input
                type="date"
                name="dob"
                value={formData.dob}
                onChange={handleInputChange}
                required
              />
            </div>

            <div className="form-group">
              <label>Time of Birth (HH:MM:SS) *</label>
              <input
                type="time"
                name="tob"
                value={formData.tob}
                onChange={handleInputChange}
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group full-width">
              <label>📍 Place of Birth *</label>
              <LocationSearch onLocationSelect={handleLocationSelect} />

              {formData.latitude && formData.longitude && (
                <div className="location-info-box">
                  <MapPin size={16} color="#4CAF50" />
                  <div>
                    <strong>{formData.place}</strong>
                    <br />
                    <small>
                      Lat: {formData.latitude}°, Lon: {formData.longitude}°, TZ: UTC+{formData.timezone}
                    </small>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Prediction Type *</label>
              <select value={predictionType} onChange={(e) => setPredictionType(e.target.value)}>
                {predictionTypes.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-group checkbox">
            <input
              type="checkbox"
              id="useQwen"
              checked={useQwen}
              onChange={(e) => setUseQwen(e.target.checked)}
            />
            <label htmlFor="useQwen">Use AI (Qwen) for enhanced predictions</label>
          </div>

          <button type="submit" className="submit-btn" disabled={loading}>
            {loading ? 'Generating...' : 'Generate Predictions'}
          </button>
        </form>

        {result && (
          <div className="result-box">
            <div className="result-header">
              <CheckCircle size={24} className="success" />
              <h2>Predictions Generated</h2>
            </div>

            <div className="result-content">
              <div className="prediction-section">
                {result.lagna && (
                  <div className="info-item">
                    <strong>Lagna (Ascendant):</strong>
                    <span>
                      {typeof result.lagna === 'object'
                        ? result.lagna.sign_name || `Rasi ${result.lagna.house || result.lagna.rasi || ''}`
                        : result.lagna}
                    </span>
                  </div>
                )}
                {result.moon_sign && (
                  <div className="info-item">
                    <strong>Moon Sign:</strong>
                    <span>
                      {typeof result.moon_sign === 'object'
                        ? result.moon_sign.sign_name || result.moon_sign
                        : result.moon_sign}
                    </span>
                  </div>
                )}
                {result.sun_sign && (
                  <div className="info-item">
                    <strong>Sun Sign:</strong>
                    <span>
                      {typeof result.sun_sign === 'object'
                        ? result.sun_sign.sign_name || result.sun_sign
                        : result.sun_sign}
                    </span>
                  </div>
                )}
              </div>

              {result.planetary_positions && Object.keys(result.planetary_positions).length > 0 && (
                <div className="predictions-detail">
                  <h3>Planetary Positions</h3>
                  {Object.entries(result.planetary_positions).map(([planet, data]) => (
                    <div key={planet} className="prediction-item">
                      <strong>{planet}:</strong>
                      <p>
                        {data.sign_name} - {data.nakshatra} (Pada {data.pada})
                        <br />
                        <small style={{color: '#888'}}>Longitude: {data.longitude?.toFixed(2)}°</small>
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {result.predictions && Object.keys(result.predictions).length > 0 && (
                <div className="predictions-detail">
                  <h3>Detailed Predictions</h3>
                  {Object.entries(result.predictions).map(([key, value]) => (
                    <div key={key} className="prediction-item">
                      <strong className="capitalize">{key}:</strong>
                      <p>{value}</p>
                    </div>
                  ))}
                </div>
              )}

              {result.ai_prediction && (
                <div className="ai-prediction">
                  <h3>Astrological Predictions</h3>
                  <div style={{ whiteSpace: 'pre-line' }}>
                    {result.ai_prediction.split('**').map((part, i) =>
                      i % 2 === 1 ? <strong key={i}>{part}</strong> : part
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
