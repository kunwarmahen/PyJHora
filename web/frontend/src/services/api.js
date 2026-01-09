import axios from "axios";

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
  calculateBirthChart: (birthDetails) =>
    api.post("/api/astrology/birth-chart", birthDetails),
  getBirthChart: (chartId) => api.get(`/api/astrology/birth-chart/${chartId}`),
  getHoroscope: (birthDetails, useQwen = false) =>
    api.post("/api/astrology/horoscope", birthDetails, {
      params: { use_qwen: useQwen }
    }),
  getDoshas: (birthDetails) => api.post("/api/astrology/doshas", birthDetails),
  getYogas: (birthDetails) => api.post("/api/astrology/yogas", birthDetails),
  getDhasa: (birthDetails, dashaType = "vimsottari") =>
    api.post("/api/astrology/dhasa", {
      ...birthDetails,
      dhasa_type: dashaType,
    }),
  getTransits: (birthDetails, currentDate = null) =>
    api.post("/api/astrology/transit", {
      ...birthDetails,
      current_date: currentDate,
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
  askQuestion: (birthDetails, question, llmProvider = "qwen") =>
    api.post("/api/astrology/ask", {
      birth_details: birthDetails,
      question: question,
      llm_provider: llmProvider,
    }),

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
