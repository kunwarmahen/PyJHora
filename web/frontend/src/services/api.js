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
        conversation_id: model.conversationId,
        profile_id: model.profileId,
      },
      // Local models can be slow to load + generate; allow up to 5 minutes
      { timeout: 300000 }
    ),

  // Conversation history (saved Q&A per profile)
  listConversations: (profileId) =>
    api.get("/api/ai/conversations", { params: { profile_id: profileId } }),
  getConversation: (id) => api.get(`/api/ai/conversations/${id}`),
  deleteConversation: (id) => api.delete(`/api/ai/conversations/${id}`),

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

/**
 * Stream an AI answer over SSE (fetch + ReadableStream — axios can't stream in
 * the browser). Calls callbacks as events arrive. Returns a function to abort.
 *   callbacks: { onMeta, onToken, onDone, onError }
 */
export const streamAskQuestion = (birthDetails, question, model = {}, callbacks = {}) => {
  const controller = new AbortController();
  const { onMeta, onToken, onDone, onError } = callbacks;

  (async () => {
    try {
      const resp = await fetch(`${API_URL}/api/astrology/ask/stream`, {
        method: "POST",
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({
          birth_details: birthDetails,
          question,
          llm_provider: model.legacyProvider || "qwen",
          provider_type: model.providerType,
          model: model.model,
          base_url: model.baseUrl,
          api_key: model.apiKey,
          vargas: model.vargas,
          ayanamsa: model.ayanamsa,
          conversation_id: model.conversationId,
          profile_id: model.profileId,
        }),
      });

      if (!resp.ok || !resp.body) {
        const text = await resp.text().catch(() => "");
        throw new Error(text || `Request failed (${resp.status})`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE frames are separated by a blank line
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const frame = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const dataLine = frame.split("\n").find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          let evt;
          try {
            evt = JSON.parse(dataLine.slice(5).trim());
          } catch (e) {
            continue;
          }
          if (evt.type === "meta") onMeta && onMeta(evt);
          else if (evt.type === "token") onToken && onToken(evt.text);
          else if (evt.type === "done") onDone && onDone(evt);
          else if (evt.type === "error") onError && onError(new Error(evt.message));
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") onError && onError(err);
    }
  })();

  return () => controller.abort();
};

export default api;
