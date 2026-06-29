import axios from "axios";
import { DEFAULT_AYANAMSA } from "../constants/jyotish";

// Fail loudly when the API base URL isn't configured. In a production build a
// missing REACT_APP_API_URL silently points the app at localhost, which then
// fails with confusing CORS/connection errors — so make it a hard error there,
// and a visible warning in development (where the localhost default is fine).
const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

if (!process.env.REACT_APP_API_URL) {
  const msg = "REACT_APP_API_URL is not set. Configure it in web/frontend/.env (see .env.example).";
  if (process.env.NODE_ENV === "production") {
    throw new Error(`[config] ${msg} A production build must have REACT_APP_API_URL set.`);
  }
  // eslint-disable-next-line no-console
  console.warn(`[config] ${msg} Falling back to ${API_URL}.`);
}

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
  login: (username, password) => api.post("/api/auth/login", { username, password }),
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
      params: { use_qwen: useQwen },
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
  getTransits: (
    birthDetails,
    currentDate = null,
    ayanamsa = DEFAULT_AYANAMSA,
    currentTime = null,
    currentTz = null
  ) =>
    api.post("/api/astrology/transit", birthDetails, {
      params: {
        current_date: currentDate,
        current_time: currentTime,
        current_tz: currentTz,
        ayanamsa,
      },
    }),
  // Other (non-Vimsottari) dasha systems.
  getDashaSystems: () => api.get("/api/astrology/dasha-systems"),
  getDashaPeriods: (birthDetails, dhasaType) =>
    api.post("/api/astrology/dasha-periods", birthDetails, {
      params: { dhasa_type: dhasaType },
    }),
  // Ashtakavarga (Bhinna + Sarva).
  getAshtakavarga: (birthDetails, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/ashtakavarga", birthDetails, { params: { ayanamsa } }),
  // Advanced chart details: arudha padas, karakas, special lagnas, upagrahas.
  getChartDetails: (birthDetails, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/chart-details", birthDetails, { params: { ayanamsa } }),
  // Shadbala / planetary strength.
  getShadbala: (birthDetails, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/shadbala", birthDetails, { params: { ayanamsa } }),
  // Shareable read-only chart link.
  createShare: (birthDetails, ayanamsa = DEFAULT_AYANAMSA, profileName = null) =>
    api.post("/api/astrology/share", {
      birth_details: birthDetails,
      ayanamsa,
      profile_name: profileName,
    }),
  getSharedChart: (token) => api.get(`/api/astrology/share/${token}`),
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
  // Lazy-load the full "Behind the scenes" tool results for one saved answer.
  getConversationTrace: (conversationId, traceId) =>
    api.get(`/api/ai/conversations/${conversationId}/traces/${traceId}`),
  deleteConversation: (id) => api.delete(`/api/ai/conversations/${id}`),
  // Thumbs up/down on a specific assistant message (rating: "up"|"down"|null)
  submitFeedback: (conversationId, messageIndex, rating) =>
    api.post(`/api/ai/conversations/${conversationId}/feedback`, {
      message_index: messageIndex,
      rating,
    }),

  // Per-user API keys (encrypted server-side; status returns masked values only)
  getApiKeys: () => api.get("/api/user/api-keys"),
  setApiKey: (provider, apiKey) => api.put(`/api/user/api-keys/${provider}`, { api_key: apiKey }),
  deleteApiKey: (provider) => api.delete(`/api/user/api-keys/${provider}`),

  generatePrediction: (birthDetails, predictionType = "general", model = {}) =>
    api.post(
      "/api/astrology/predict",
      {
        birth_details: birthDetails,
        prediction_type: predictionType,
        // Back-compat: still send llm_provider; new fields take precedence server-side
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        vargas: model.vargas,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),

  analyzeCompatibilityAI: (maleBirthDetails, femaleBirthDetails, model = {}) =>
    api.post(
      "/api/astrology/compatibility-analysis",
      {
        male_details: maleBirthDetails,
        female_details: femaleBirthDetails,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),
};

/**
 * Stream an AI answer over SSE (fetch + ReadableStream — axios can't stream in
 * the browser). Calls callbacks as events arrive. Returns a function to abort.
 *   callbacks: { onMeta, onToken, onDone, onError }
 */
export const streamAskQuestion = (birthDetails, question, model = {}, callbacks = {}) => {
  const controller = new AbortController();
  const { onMeta, onToken, onDone, onError, onToolCall, onToolResult, onNotice } = callbacks;

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
          sections: model.sections,
          ayanamsa: model.ayanamsa,
          mode: model.mode,
          conversation_id: model.conversationId,
          profile_id: model.profileId,
          regenerate: model.regenerate || false,
        }),
      });

      if (resp.status === 429) {
        const detail =
          (await resp.json().catch(() => null))?.detail || "Rate limit reached. Please slow down.";
        throw new Error(detail);
      }

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
          else if (evt.type === "tool_call") onToolCall && onToolCall(evt);
          else if (evt.type === "tool_result") onToolResult && onToolResult(evt);
          else if (evt.type === "notice") onNotice && onNotice(evt);
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
