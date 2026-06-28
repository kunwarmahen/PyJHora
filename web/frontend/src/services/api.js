import axios from "axios";
import { DEFAULT_AYANAMSA } from "../constants/jyotish";

const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_URL,
  timeout: parseInt(process.env.REACT_APP_API_TIMEOUT || "30000"),
  headers: {
    "Content-Type": "application/json",
  },
});

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export const authService = {
  register: (username, email, password) =>
    api.post("/api/auth/register", { username, email, password }),
  login: (username, password) =>
    api.post("/api/auth/login", { username, password }),
  getProfile: () => api.get("/api/user/profile"),
};

export const astrologyService = {
  calculateBirthChart: (birthDetails, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/birth-chart", birthDetails, { params: { ayanamsa } }),
  getBirthChart: (chartId) => api.get(`/api/astrology/birth-chart/${chartId}`),
  getDivisionalChart: (birthDetails, varga = 9, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/divisional-chart", birthDetails, {
      params: { varga, ayanamsa },
    }),
  getHoroscope: (birthDetails, useQwen = false) =>
    api.post("/api/astrology/horoscope", birthDetails, {
      params: { use_qwen: useQwen }
    }),
  getPanchanga: ({ place, latitude, longitude, timezone, date } = {}) =>
    api.get("/api/astrology/panchanga", {
      params: { place, latitude, longitude, timezone, date },
    }),
  getDoshas: (birthDetails, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/doshas", birthDetails, { params: { ayanamsa } }),
  getYogas: (birthDetails, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/yogas", birthDetails, { params: { ayanamsa } }),
  getDhasa: (birthDetails, dashaType = "vimsottari") =>
    api.post("/api/astrology/dhasa", birthDetails, {
      params: { dhasa_type: dashaType },
    }),
  // Lazily fetch the immediate children of a Vimsottari node. `lordsPath` is the
  // chain of lord names from the Maha Dasha down, e.g. ["Venus", "Saturn"].
  getDhasaChildren: (birthDetails, lordsPath = []) =>
    api.post("/api/astrology/dhasa/children", birthDetails, {
      params: { lords: lordsPath.join(",") },
    }),
  getTransits: (birthDetails, currentDate = null, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/transit", birthDetails, {
      params: { current_date: currentDate, ayanamsa },
    }),
  getCompatibility: (maleBirthDetails, femaleBirthDetails, useQwen = false) =>
    api.post("/api/astrology/compatibility", {
      male_dob: maleBirthDetails.dob,
      male_tob: maleBirthDetails.tob,
      male_place: maleBirthDetails.place,
      male_latitude: maleBirthDetails.latitude,
      male_longitude: maleBirthDetails.longitude,
      male_timezone: maleBirthDetails.timezone,
      female_dob: femaleBirthDetails.dob,
      female_tob: femaleBirthDetails.tob,
      female_place: femaleBirthDetails.place,
      female_latitude: femaleBirthDetails.latitude,
      female_longitude: femaleBirthDetails.longitude,
      female_timezone: femaleBirthDetails.timezone,
      use_qwen: useQwen,
    }),
  getUserCharts: () => api.get("/api/user/charts"),

  // New LLM Q&A endpoints
  getLlmProviders: () => api.get("/api/llm/providers"),

  askQuestion: (birthDetails, question, model = {}) =>
    api.post(
      "/api/astrology/ask",
      {
        birth_details: birthDetails,
        question: question,
        // Back-compat: still send llm_provider; new fields take precedence server-side
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        vargas: model.vargas,
        ayanamsa: model.ayanamsa,
      },
      // Local models can be slow to load + generate; allow up to 5 minutes
      { timeout: 300000 }
    ),

  generatePrediction: (birthDetails, predictionType = "general", llmProvider = "qwen") =>
    api.post("/api/astrology/predict", {
      birth_details: birthDetails,
      prediction_type: predictionType,
      llm_provider: llmProvider,
    }),

  analyzeCompatibilityAI: (maleBirthDetails, femaleBirthDetails, llmProvider = "qwen") =>
    api.post("/api/astrology/compatibility-analysis", {
      male_details: maleBirthDetails,
      female_details: femaleBirthDetails,
      llm_provider: llmProvider,
    }),
};

export default api;
