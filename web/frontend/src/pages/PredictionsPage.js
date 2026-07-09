import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import { AlertCircle, CheckCircle, MapPin } from "lucide-react";
import { astrologyService } from "../services/api";
import LocationSearch from "../components/LocationSearch";
import "../styles/Forms.css";

// Read the user's AI provider/model choice (Settings → AI, persisted in
// localStorage) so predictions run through the unified LLM service — the same
// path every other AI page uses. A blank model lets the server fall back to its
// configured default (e.g. OLLAMA_DEFAULT_MODEL).
const readModelConfig = () => {
  const providerType = localStorage.getItem("ai_provider_type") || "ollama";
  return {
    providerType,
    model: localStorage.getItem("ai_model") || "",
    baseUrl: providerType === "ollama" ? localStorage.getItem("ai_base_url") || undefined : undefined,
    legacyProvider: providerType === "ollama" ? "qwen" : providerType,
    maxTokens: parseInt(localStorage.getItem("ai_max_tokens") || "0", 10) || undefined,
  };
};

// UI prediction type → the LLM service's prediction_type keyword.
const AI_TYPE = { horoscope: "general", health: "health", career: "career" };

export const PredictionsPage = () => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState({
    name: "",
    dob: "",
    tob: "",
    place: "",
    latitude: null,
    longitude: null,
    timezone: null,
  });
  const [predictionType, setPredictionType] = useState("horoscope");
  const [useAi, setUseAi] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [aiReading, setAiReading] = useState("");
  const [aiModel, setAiModel] = useState("");
  const [aiError, setAiError] = useState("");

  const predictionTypes = [
    { value: "horoscope", label: t("predictions.typeHoroscope") },
    { value: "health", label: t("predictions.typeHealth") },
    { value: "career", label: t("predictions.typeCareer") },
    { value: "transit", label: t("predictions.typeTransit") },
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
      setError(t("predictions.errLocation"));
      return;
    }

    setLoading(true);
    setError("");
    setAiError("");
    setAiReading("");
    setAiModel("");

    try {
      const birthDetails = {
        name: formData.name,
        dob: formData.dob,
        tob: formData.tob,
        place: formData.place,
        latitude: formData.latitude,
        longitude: formData.longitude,
        timezone: formData.timezone,
      };

      // Transits are a separate deterministic view; everything else shows the
      // horoscope chart data (optionally with an AI-written reading below it).
      if (predictionType === "transit") {
        const response = await astrologyService.getTransits(birthDetails);
        setResult(response.data);
        return;
      }

      const response = await astrologyService.getHoroscope(birthDetails);
      setResult(response.data);

      if (useAi) {
        try {
          const aiRes = await astrologyService.generatePrediction(
            birthDetails,
            AI_TYPE[predictionType] || "general",
            readModelConfig()
          );
          setAiReading(aiRes.data?.prediction || "");
          setAiModel(aiRes.data?.model || aiRes.data?.provider || "");
        } catch (err) {
          setAiError(err.response?.data?.detail || t("predictions.aiError"));
        }
      }
    } catch (err) {
      setError(err.response?.data?.detail || t("predictions.genError"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <div className="form-wrapper">
        <h1>{t("predictions.title")}</h1>
        <p className="subtitle">{t("predictions.subtitle")}</p>

        {error && (
          <div className="error-box">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="astrology-form">
          <div className="form-row">
            <div className="form-group">
              <label>{t("predictions.name")} *</label>
              <input
                type="text"
                name="name"
                value={formData.name}
                onChange={handleInputChange}
                placeholder={t("predictions.namePlaceholder")}
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>{t("predictions.dobLabel")} *</label>
              <input
                type="date"
                name="dob"
                value={formData.dob}
                onChange={handleInputChange}
                required
              />
            </div>

            <div className="form-group">
              <label>{t("predictions.tobLabel")} *</label>
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
              <label>📍 {t("predictions.placeLabel")} *</label>
              <LocationSearch onLocationSelect={handleLocationSelect} />

              {formData.latitude && formData.longitude && (
                <div className="location-info-box">
                  <MapPin size={16} color="#4CAF50" />
                  <div>
                    <strong>{formData.place}</strong>
                    <br />
                    <small>
                      Lat: {formData.latitude}°, Lon: {formData.longitude}°, TZ: UTC+
                      {formData.timezone}
                    </small>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>{t("predictions.typeLabel")} *</label>
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
              id="useAi"
              checked={useAi}
              onChange={(e) => setUseAi(e.target.checked)}
              disabled={predictionType === "transit"}
            />
            <label htmlFor="useAi">{t("predictions.useAi")}</label>
          </div>

          <button type="submit" className="submit-btn" disabled={loading}>
            {loading ? t("predictions.generating") : t("predictions.generate")}
          </button>
        </form>

        {result && (
          <div className="result-box">
            <div className="result-header">
              <CheckCircle size={24} className="success" />
              <h2>{t("predictions.generated")}</h2>
            </div>

            <div className="result-content">
              <div className="prediction-section">
                {result.lagna && (
                  <div className="info-item">
                    <strong>{t("birthChart.lagnaAscendant")}:</strong>
                    <span>
                      {typeof result.lagna === "object"
                        ? result.lagna.sign_name ||
                          `Rasi ${result.lagna.house || result.lagna.rasi || ""}`
                        : result.lagna}
                    </span>
                  </div>
                )}
                {result.moon_sign && (
                  <div className="info-item">
                    <strong>{t("predictions.moonSign")}:</strong>
                    <span>
                      {typeof result.moon_sign === "object"
                        ? result.moon_sign.sign_name || result.moon_sign
                        : result.moon_sign}
                    </span>
                  </div>
                )}
                {result.sun_sign && (
                  <div className="info-item">
                    <strong>{t("predictions.sunSign")}:</strong>
                    <span>
                      {typeof result.sun_sign === "object"
                        ? result.sun_sign.sign_name || result.sun_sign
                        : result.sun_sign}
                    </span>
                  </div>
                )}
              </div>

              {result.planetary_positions && Object.keys(result.planetary_positions).length > 0 && (
                <div className="predictions-detail">
                  <h3>{t("predictions.planetaryPositions")}</h3>
                  {Object.entries(result.planetary_positions).map(([planet, data]) => (
                    <div key={planet} className="prediction-item">
                      <strong>{planet}:</strong>
                      <p>
                        {data.sign_name} - {data.nakshatra} ({t("common.pada")} {data.pada})
                        <br />
                        <small style={{ color: "#888" }}>
                          {t("predictions.longitude")}: {data.longitude?.toFixed(2)}°
                        </small>
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {result.predictions && Object.keys(result.predictions).length > 0 && (
                <div className="predictions-detail">
                  <h3>{t("predictions.detailed")}</h3>
                  {Object.entries(result.predictions).map(([key, value]) => (
                    <div key={key} className="prediction-item">
                      <strong className="capitalize">{key}:</strong>
                      <p>{value}</p>
                    </div>
                  ))}
                </div>
              )}

              {aiError && (
                <div className="error-box">
                  <AlertCircle size={18} />
                  <span>{aiError}</span>
                </div>
              )}

              {aiReading && (
                <div className="ai-prediction">
                  <h3>{t("predictions.astrological")}</h3>
                  <div className="sbc-ai-markdown">
                    <ReactMarkdown>{aiReading}</ReactMarkdown>
                  </div>
                  {aiModel && (
                    <p className="subtitle" style={{ marginTop: 8 }}>
                      {t("predictions.aiModel", { model: aiModel })}
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
