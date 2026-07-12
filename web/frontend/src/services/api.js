import axios from "axios";
import { DEFAULT_AYANAMSA } from "../constants/jyotish";

// Base URL for the backend API. Prefer an explicit REACT_APP_API_URL, but when
// it's unset default to the SAME host the page was served from (on port 8000).
// That way the app works from any device on the LAN with no per-device config:
// desktop via localhost, a phone via the machine's hostname/IP, etc. — the API
// host always matches the page host, so it can't drift to localhost on a phone.
const deriveApiUrl = () => {
  if (typeof window !== "undefined" && window.location) {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8000`;
  }
  return "http://localhost:8000";
};

// REACT_APP_API_URL semantics:
//   unset              -> same host, port 8000 (LAN self-host; see deriveApiUrl above)
//   "" (empty string)  -> same ORIGIN, relative paths ("/api/..."). For reverse-proxy
//                         deploys where a single hostname fronts both the app and the
//                         API (nginx + Cloudflare Tunnel): no port, no cross-origin, no
//                         CORS. This is what the NAS build (Dockerfile.nas) bakes in.
//   "http://host:port" -> pinned absolute backend URL
const rawApiUrl = process.env.REACT_APP_API_URL;
export const API_URL = rawApiUrl === undefined ? deriveApiUrl() : rawApiUrl;

if (rawApiUrl === undefined) {
  // eslint-disable-next-line no-console
  console.info(`[config] REACT_APP_API_URL unset; using same-host default ${API_URL}.`);
}

const api = axios.create({
  baseURL: API_URL,
  timeout: parseInt(process.env.REACT_APP_API_TIMEOUT || "30000"),
  headers: {
    "Content-Type": "application/json",
  },
});

// Token storage helpers. Both the short-lived access token and the long-lived
// refresh token live in localStorage (v1 — same as before; a refresh token is
// what keeps you signed in across access-token expiry). Known XSS tradeoff vs
// httpOnly cookies; acceptable given the app already used localStorage bearers.
const ACCESS_KEY = "access_token";
const REFRESH_KEY = "refresh_token";

export const setTokens = ({ access_token, refresh_token } = {}) => {
  if (access_token) localStorage.setItem(ACCESS_KEY, access_token);
  if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token);
};
export const getRefreshToken = () => localStorage.getItem(REFRESH_KEY);
export const clearTokens = () => {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
};

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(ACCESS_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Birth-chart-bound AI endpoints whose saved readings should be grouped under the
// currently-selected profile in the unified history. We inject `profile_id` from
// localStorage so every reading page doesn't have to thread it through by hand.
// (Location-driven tools — Muhurta / Prashna / Almanac — are intentionally absent
// so their readings land in the "No profile" bucket. `ask` sends its own id.)
const PROFILE_READING_PATHS = new Set([
  "/api/astrology/varshaphal-analysis",
  "/api/astrology/bhrigu-markers-analysis",
  "/api/astrology/remedies-analysis",
  "/api/astrology/daily-digest-analysis",
  "/api/astrology/weekly-digest-analysis",
  "/api/astrology/monthly-digest-analysis",
  "/api/astrology/sensitive-points-analysis",
  "/api/astrology/celestial-analysis",
  "/api/astrology/pancha-pakshi-analysis",
  "/api/astrology/sarvatobhadra-analysis",
  "/api/astrology/compatibility-analysis",
  "/api/astrology/compare-analysis",
  "/api/astrology/rectify-birth-time/explain",
  "/api/astrology/rectify-birth-time/events/explain",
  "/api/astrology/predict",
]);

api.interceptors.request.use((config) => {
  if (
    (config.method || "").toLowerCase() === "post" &&
    PROFILE_READING_PATHS.has(config.url) &&
    config.data &&
    typeof config.data === "object" &&
    config.data.profile_id == null
  ) {
    try {
      const p = JSON.parse(localStorage.getItem("selectedProfile") || "null");
      if (p && p._id) config.data = { ...config.data, profile_id: p._id };
    } catch (e) {
      /* no selected profile — reading saved without one */
    }
  }
  return config;
});

// --- Silent refresh on 401 -------------------------------------------------
// When a call 401s (access token expired), transparently exchange the refresh
// token for a fresh pair and retry the original request ONCE — so the user
// isn't bounced to /login every ACCESS_TOKEN_EXPIRE_MINUTES. A single in-flight
// refresh is shared across concurrent 401s. Only a failed refresh logs out.
let refreshPromise = null;

const doRefresh = async () => {
  const refresh_token = getRefreshToken();
  if (!refresh_token) throw new Error("no refresh token");
  // Bare axios (not `api`) so this request skips the interceptors below and
  // can't recurse into another refresh attempt.
  const resp = await axios.post(`${API_URL}/api/auth/refresh`, { refresh_token });
  setTokens(resp.data);
  return resp.data.access_token;
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config || {};
    const status = error.response?.status;
    const isAuthCall = (original.url || "").includes("/api/auth/");

    if (status !== 401 || isAuthCall) {
      return Promise.reject(error);
    }

    if (!original._retried) {
      original._retried = true;
      try {
        if (!refreshPromise) {
          refreshPromise = doRefresh().finally(() => {
            refreshPromise = null;
          });
        }
        const newAccess = await refreshPromise;
        original.headers = { ...(original.headers || {}), Authorization: `Bearer ${newAccess}` };
        return api(original);
      } catch (e) {
        // Refresh failed — fall through to a hard logout.
      }
    }

    clearTokens();
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export const authService = {
  register: (username, email, password, name, rememberMe = false) =>
    api.post("/api/auth/register", { username, email, password, name, remember_me: rememberMe }),
  login: (username, password, rememberMe = false) =>
    api.post("/api/auth/login", { username, password, remember_me: rememberMe }),
  // Sign in with Google: `credential` is the ID token from Google Identity Services.
  googleLogin: (credential, rememberMe = false) =>
    api.post("/api/auth/google", { credential, remember_me: rememberMe }),
  refresh: (refresh_token) => api.post("/api/auth/refresh", { refresh_token }),
  logout: (refresh_token) => api.post("/api/auth/logout", { refresh_token }),
  changePassword: (currentPassword, newPassword) =>
    api.post("/api/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    }),
  updateEmail: (email) => api.put("/api/auth/email", { email }),
  updateName: (name) => api.put("/api/auth/name", { name }),
  logoutOtherDevices: () => api.post("/api/auth/logout-all"),
  deleteAccount: (password) =>
    api.delete("/api/auth/account", { data: { password } }),
  getProfile: () => api.get("/api/user/profile"),
  // Forgot / reset password (email link). `identifier` = username or email.
  forgotPassword: (identifier) =>
    api.post("/api/auth/forgot-password", { identifier }),
  resetPassword: (token, newPassword) =>
    api.post("/api/auth/reset-password", { token, new_password: newPassword }),
};

// Daily-digest notification preferences + Web Push (§16).
export const notificationsService = {
  getPrefs: () => api.get("/api/notifications/prefs"),
  setPrefs: (prefs) => api.put("/api/notifications/prefs", prefs),
  subscribePush: (subscription) =>
    api.post("/api/notifications/push/subscribe", { subscription }),
  unsubscribePush: (endpoint) =>
    api.post("/api/notifications/push/unsubscribe", { endpoint }),
  sendDigestNow: (cadence = "daily") =>
    api.post("/api/notifications/digest/send", null, { params: { cadence } }),
};

export const astrologyService = {
  calculateBirthChart: (birthDetails, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/birth-chart", birthDetails, { params: { ayanamsa } }),
  getBirthChart: (chartId) => api.get(`/api/astrology/birth-chart/${chartId}`),
  getDivisionalChart: (birthDetails, varga = 9, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/divisional-chart", birthDetails, {
      params: { varga, ayanamsa },
    }),
  getHoroscope: (birthDetails) =>
    api.post("/api/astrology/horoscope", birthDetails),
  getPanchanga: ({ place, latitude, longitude, timezone, date, system } = {}) =>
    api.get("/api/astrology/panchanga", {
      params: { place, latitude, longitude, timezone, date, system },
    }),
  // Almanac (§9.2): planetary hours, eclipses, festival/vratha dates.
  getPlanetaryHours: ({ place, latitude, longitude, timezone, date } = {}) =>
    api.get("/api/astrology/almanac/hora", {
      params: { place, latitude, longitude, timezone, date },
    }),
  getEclipses: ({ place, latitude, longitude, timezone, fromDate, count } = {}) =>
    api.get("/api/astrology/almanac/eclipses", {
      params: { place, latitude, longitude, timezone, from_date: fromDate, count },
    }),
  getFestivals: ({ place, latitude, longitude, timezone, start, end, types } = {}) =>
    api.get("/api/astrology/almanac/festivals", {
      params: {
        place, latitude, longitude, timezone, start, end,
        types: Array.isArray(types) ? types.join(",") : types,
      },
    }),
  getConjunctions: ({ place, latitude, longitude, timezone, start, end, maxSep } = {}) =>
    api.get("/api/astrology/almanac/conjunctions", {
      params: { place, latitude, longitude, timezone, start, end, max_sep: maxSep },
    }),
  // Plain-language AI day-guide from the almanac (panchanga + hora), location-driven.
  analyzeAlmanacAI: ({ place, latitude, longitude, timezone, date, system } = {}, model = {}) =>
    api.post(
      "/api/astrology/almanac-analysis",
      {
        place,
        latitude,
        longitude,
        timezone,
        date,
        system,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
      },
      { timeout: 300000 }
    ),
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
  // Bhava (house-cusp) chart — Bhava Chalit / cuspal division (Sripati/Placidus/KP/Equal).
  getBhavaChart: (birthDetails, method = "SRIPATI", ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/bhava-chart", birthDetails, {
      params: { method, ayanamsa },
    }),
  // Sidereal ephemeris + ingress calendar over a date window.
  getEphemeris: ({ startDate, days = 30, place, latitude, longitude, timezone, ayanamsa = DEFAULT_AYANAMSA } = {}) =>
    api.get("/api/astrology/ephemeris", {
      params: {
        start_date: startDate,
        days,
        place,
        latitude,
        longitude,
        timezone,
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
  // Graha drishti (aspects): per-graha houses/planets aspected + strength %.
  getAspects: (birthDetails, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/aspects", birthDetails, { params: { ayanamsa } }),
  // Dedicated Raja Yogas (Kendra-Trikona pairs + named special types).
  getRajaYogas: (birthDetails, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/raja-yogas", birthDetails, { params: { ayanamsa } }),
  // Ayu (longevity) category — Alpa/Madhya/Purna + factors.
  getLongevity: (birthDetails, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/longevity", birthDetails, { params: { ayanamsa } }),
  // Sensitive points (§11.1): Sphutas + 36 Sahams + Argala, aggregated.
  getSensitivePoints: (birthDetails, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/sensitive-points", birthDetails, { params: { ayanamsa } }),
  analyzeSensitivePointsAI: (birthDetails, opts = {}, model = {}) =>
    api.post(
      "/api/astrology/sensitive-points-analysis",
      {
        birth_details: birthDetails,
        person_name: opts.personName,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),
  // Vedic clock & retrograde (§11.2). Location-driven (not birth-chart bound).
  getVedicClock: ({ place, latitude, longitude, timezone, date } = {}) =>
    api.post("/api/astrology/vedic-clock", null, {
      params: { place, latitude, longitude, timezone, date },
    }),
  getRetrograde: ({ place, latitude, longitude, timezone, date } = {}) =>
    api.post("/api/astrology/retrograde", null, {
      params: { place, latitude, longitude, timezone, date },
    }),
  analyzeCelestialAI: (birthDetails, opts = {}, model = {}) =>
    api.post(
      "/api/astrology/celestial-analysis",
      {
        birth_details: birthDetails,
        date: opts.date,
        person_name: opts.personName,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),
  // Sudarsana Chakra — three wheels (Lagna/Moon/Sun) for a solar-return year.
  getSudarsanaChakra: (birthDetails, yearOffset = 0, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/sudarsana-chakra", birthDetails, {
      params: { year_offset: yearOffset, ayanamsa },
    }),
  // Pancha Pakshi Sastra — birth bird + day's activity-strength timeline.
  getPanchaPakshi: (birthDetails, date = null) =>
    api.post("/api/astrology/pancha-pakshi", birthDetails, {
      params: date ? { date } : {},
    }),
  // Plain-language AI reading of today's Pancha Pakshi timing.
  analyzePanchaPakshiAI: (birthDetails, opts = {}, model = {}) =>
    api.post(
      "/api/astrology/pancha-pakshi-analysis",
      {
        birth_details: birthDetails,
        date: opts.date,
        person_name: opts.personName,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),
  // Varshaphal / Tajaka annual (solar-return) horoscope for a target year.
  getVarshaphal: (birthDetails, year, ayanamsa = DEFAULT_AYANAMSA, dashaSystem = "mudda") =>
    api.post("/api/astrology/varshaphal", birthDetails, {
      params: { year, ayanamsa, dasha_system: dashaSystem },
    }),
  // Plain-language AI year-ahead reading of the Varshaphal chart.
  analyzeVarshaphalAI: (birthDetails, year, opts = {}, model = {}) =>
    api.post(
      "/api/astrology/varshaphal-analysis",
      {
        birth_details: birthDetails,
        year,
        person_name: opts.personName,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),
  // EXPERIMENTAL birth-time rectification (BV Raman suddhi methods).
  rectifyBirthTime: (birthDetails, method = "nakshatra", gender = null, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/rectify-birth-time", birthDetails, {
      params: { method, ...(gender != null ? { gender } : {}), ayanamsa },
    }),
  // Plain-language AI note on why the suggested (rectified) time fits better.
  explainRectificationAI: (birthDetails, opts = {}, model = {}) =>
    api.post(
      "/api/astrology/rectify-birth-time/explain",
      {
        birth_details: birthDetails,
        method: opts.method || "nakshatra",
        gender: opts.gender,
        person_name: opts.personName,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),
  // EXPERIMENTAL event-based rectification — scans candidate times for the best
  // dasha/transit fit to the supplied dated life events.
  rectifyByEvents: (birthDetails, events, windowMinutes = 120, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post(
      "/api/astrology/rectify-birth-time/events",
      {
        birth_details: birthDetails,
        events,
        window_minutes: windowMinutes,
        ayanamsa,
      },
      { timeout: 300000 }
    ),
  // Plain-language AI note on why the event-matched time fits the events.
  explainEventRectificationAI: (birthDetails, opts = {}, model = {}) =>
    api.post(
      "/api/astrology/rectify-birth-time/events/explain",
      {
        birth_details: birthDetails,
        events: opts.events || [],
        window_minutes: opts.windowMinutes || 120,
        person_name: opts.personName,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),
  // Conversational rectification: one interview turn → { reply, events, ready }.
  rectifyChat: (birthDetails, messages, collectedEvents = [], opts = {}, model = {}) =>
    api.post(
      "/api/astrology/rectify-birth-time/chat",
      {
        birth_details: birthDetails,
        messages,
        collected_events: collectedEvents,
        person_name: opts.personName,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),
  // Shareable read-only chart link.
  createShare: (birthDetails, ayanamsa = DEFAULT_AYANAMSA, profileName = null) =>
    api.post("/api/astrology/share", {
      birth_details: birthDetails,
      ayanamsa,
      profile_name: profileName,
    }),
  getSharedChart: (token) => api.get(`/api/astrology/share/${token}`),
  getCompatibility: (maleBirthDetails, femaleBirthDetails) =>
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
    }),
  getUserCharts: () => api.get("/api/user/charts"),

  // ---- Muhurta / electional astrology (§16) ----
  // Location-driven: find auspicious windows for an activity over a date range.
  getMuhurta: ({ activity, startDate, endDate, place, latitude, longitude, timezone } = {}) =>
    api.post("/api/astrology/muhurta", null, {
      params: {
        activity, start_date: startDate, end_date: endDate,
        place, latitude, longitude, timezone,
      },
    }),
  analyzeMuhurtaAI: ({ activity, startDate, endDate, place, latitude, longitude, timezone } = {}, model = {}) =>
    api.post(
      "/api/astrology/muhurta-analysis",
      {
        activity, start_date: startDate, end_date: endDate,
        place, latitude, longitude, timezone,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
      },
      { timeout: 300000 }
    ),

  // ---- Prashna / horary (§16) ----
  // Cast a chart for the moment (defaults to now + here) and read it. The
  // -analysis endpoint returns both the reading and the chart.
  getPrashna: ({ question, date, time, place, latitude, longitude, timezone, ayanamsa } = {}) =>
    api.post("/api/astrology/prashna", null, {
      params: { question, date, time, place, latitude, longitude, timezone, ayanamsa },
    }),
  analyzePrashnaAI: ({ question, date, time, place, latitude, longitude, timezone } = {}, model = {}) =>
    api.post(
      "/api/astrology/prashna-analysis",
      {
        question, date, time, place, latitude, longitude, timezone,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),

  // ---- Daily digest (§16) ----
  getDailyDigest: (birthDetails, { date, currentTime, currentTz, ayanamsa = DEFAULT_AYANAMSA } = {}) =>
    api.post("/api/astrology/daily-digest", birthDetails, {
      params: { date, current_time: currentTime, current_tz: currentTz, ayanamsa },
    }),
  analyzeDailyDigestAI: (birthDetails, opts = {}, model = {}) =>
    api.post(
      "/api/astrology/daily-digest-analysis",
      {
        birth_details: birthDetails,
        date: opts.date,
        current_time: opts.currentTime,
        current_tz: opts.currentTz,
        person_name: opts.personName,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),

  // ---- Weekly & monthly digests (§25) ----
  getWeeklyDigest: (birthDetails, { date, ayanamsa = DEFAULT_AYANAMSA } = {}) =>
    api.post("/api/astrology/weekly-digest", birthDetails, { params: { date, ayanamsa } }),
  getMonthlyDigest: (birthDetails, { date, ayanamsa = DEFAULT_AYANAMSA } = {}) =>
    api.post("/api/astrology/monthly-digest", birthDetails, { params: { date, ayanamsa } }),
  analyzePeriodDigestAI: (period, birthDetails, opts = {}, model = {}) =>
    api.post(
      `/api/astrology/${period}-digest-analysis`,
      {
        birth_details: birthDetails,
        date: opts.date,
        person_name: opts.personName,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),

  // ---- Muhurta sub-tools: Choghadiya / Panchaka / Tarabala / Chandrabala ----
  // Location-driven; pass birthDetails to personalize Tarabala + Chandrabala.
  getMuhurtaSubtools: ({ date, place, latitude, longitude, timezone, birthDetails } = {}) =>
    api.post("/api/astrology/muhurta/subtools", {
      date, place, latitude, longitude, timezone,
      birth_details: birthDetails || undefined,
    }),

  // ---- Nadi / Bhrigu-style yearly markers ----
  getBhriguMarkers: (birthDetails, { fromAge, years = 12, ayanamsa = DEFAULT_AYANAMSA } = {}) =>
    api.post("/api/astrology/bhrigu-markers", birthDetails, {
      params: { from_age: fromAge, years, ayanamsa },
    }),
  analyzeBhriguMarkersAI: (birthDetails, opts = {}, model = {}) =>
    api.post(
      "/api/astrology/bhrigu-markers-analysis",
      {
        birth_details: birthDetails,
        from_age: opts.fromAge,
        years: opts.years || 12,
        person_name: opts.personName,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),

  // ---- Remedies (gemstones / mantras / deities per weak planet) ----
  getRemedies: (birthDetails, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/remedies", birthDetails, { params: { ayanamsa } }),
  analyzeRemediesAI: (birthDetails, opts = {}, model = {}) =>
    api.post(
      "/api/astrology/remedies-analysis",
      {
        birth_details: birthDetails,
        person_name: opts.personName,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),

  // ---- KP (Krishnamurti Paddhati) (§16) ----
  // KP always reads on the KP ayanamsa (forced server-side).
  getKpDetails: (birthDetails) =>
    api.post("/api/astrology/kp", birthDetails),
  analyzeKpAI: (birthDetails, opts = {}, model = {}) =>
    api.post(
      "/api/astrology/kp-analysis",
      {
        birth_details: birthDetails,
        person_name: opts.personName,
        profile_id: opts.profileId,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
      },
      { timeout: 300000 }
    ),
  // KP horary (Prasna) — a number 1-249 fixes the ascendant, cast for now+here.
  getKpHorary: ({ number, date, time, place, latitude, longitude, timezone } = {}) =>
    api.post("/api/astrology/kp-horary", null, {
      params: { number, date, time, place, latitude, longitude, timezone },
    }),
  analyzeKpHoraryAI: ({ number, question, date, time, place, latitude, longitude, timezone } = {}, model = {}) =>
    api.post(
      "/api/astrology/kp-horary-analysis",
      {
        number, question, date, time, place, latitude, longitude, timezone,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
      },
      { timeout: 300000 }
    ),

  // ---- Jaimini deep-dive (§16) ----
  getJaimini: (birthDetails, ayanamsa = DEFAULT_AYANAMSA) =>
    api.post("/api/astrology/jaimini", birthDetails, { params: { ayanamsa } }),
  analyzeJaiminiAI: (birthDetails, opts = {}, model = {}) =>
    api.post(
      "/api/astrology/jaimini-analysis",
      {
        birth_details: birthDetails,
        person_name: opts.personName,
        profile_id: opts.profileId,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),

  // ---- Chart of the moment / "now" chart (§16) ----
  getNowChart: ({ place, latitude, longitude, timezone, currentTime, currentTz, ayanamsa = DEFAULT_AYANAMSA } = {}) =>
    api.post("/api/astrology/now-chart", null, {
      params: {
        place, latitude, longitude, timezone,
        current_time: currentTime, current_tz: currentTz, ayanamsa,
      },
    }),
  analyzeNowChartAI: ({ place, latitude, longitude, timezone, currentTime, currentTz } = {}, model = {}) =>
    api.post(
      "/api/astrology/now-chart-analysis",
      {
        place, latitude, longitude, timezone,
        current_time: currentTime, current_tz: currentTz,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),

  // New LLM Q&A endpoints
  getLlmProviders: () => api.get("/api/llm/providers"),

  // Catalog of tools the AI astrologer can call (capability disclosure page)
  getAiTools: () => api.get("/api/ai/tools"),

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
        max_tokens: model.maxTokens || undefined,
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
  // Unified AI history: every chat + saved reading across all tools (no profile
  // filter → the global History page). Each item carries source/kind/route/context.
  listHistory: () => api.get("/api/ai/conversations"),
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

  // System health / diagnostics
  getHealth: () => api.get("/health"),

  // Per-user API keys (encrypted server-side; status returns masked values only)
  getApiKeys: () => api.get("/api/user/api-keys"),
  setApiKey: (provider, apiKey) => api.put(`/api/user/api-keys/${provider}`, { api_key: apiKey }),
  deleteApiKey: (provider) => api.delete(`/api/user/api-keys/${provider}`),

  // Cross-device UI preferences (non-secret; e.g. the chosen LLM provider/model)
  getPreferences: () => api.get("/api/user/preferences"),
  putPreferences: (preferences) => api.put("/api/user/preferences", { preferences }),

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
        max_tokens: model.maxTokens || undefined,
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
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),

  // Neutral AI comparison of two charts (Compare Charts page) — not marriage matching.
  compareChartsAI: (person1, person2, names = {}, model = {}) =>
    api.post(
      "/api/astrology/compare-analysis",
      {
        person1_details: person1,
        person2_details: person2,
        person1_name: names.name1,
        person2_name: names.name2,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),

  // Sarvatobhadra Chakra: the 9×9 grid with today's transits + vedha mapped on it.
  getSarvatobhadra: (
    birthDetails,
    {
      nameNakshatra = null,
      currentDate = null,
      currentTime = null,
      currentTz = null,
      ayanamsa = DEFAULT_AYANAMSA,
    } = {}
  ) =>
    api.post("/api/astrology/sarvatobhadra", birthDetails, {
      params: {
        name_nakshatra: nameNakshatra,
        current_date: currentDate,
        current_time: currentTime,
        current_tz: currentTz,
        ayanamsa,
      },
    }),

  // Plain-language AI reading of the Sarvatobhadra transit picture.
  analyzeSarvatobhadraAI: (birthDetails, opts = {}, model = {}) =>
    api.post(
      "/api/astrology/sarvatobhadra-analysis",
      {
        birth_details: birthDetails,
        person_name: opts.personName,
        name_nakshatra: opts.nameNakshatra,
        current_date: opts.currentDate,
        current_time: opts.currentTime,
        current_tz: opts.currentTz,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),

  // ---- Learn the Chart (AI quiz) ----
  // Generate a quiz grounded in this chart; returns questions without answer keys.
  generateQuiz: (birthDetails, opts = {}, model = {}) =>
    api.post(
      "/api/astrology/quiz/generate",
      {
        birth_details: birthDetails,
        profile_id: opts.profileId,
        topics: opts.topics,
        level: opts.level,
        adaptive: opts.adaptive,
        num_mcq: opts.numMcq,
        num_free: opts.numFree,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),

  // Grade a quiz session's answers; returns per-question feedback + reasoning.
  gradeQuiz: (sessionId, answers, model = {}) =>
    api.post(
      "/api/astrology/quiz/grade",
      {
        session_id: sessionId,
        answers,
        llm_provider: model.legacyProvider || "qwen",
        provider_type: model.providerType,
        model: model.model,
        base_url: model.baseUrl,
        api_key: model.apiKey,
        max_tokens: model.maxTokens || undefined,
        ayanamsa: model.ayanamsa,
      },
      { timeout: 300000 }
    ),

  getQuizHistory: (profileId = null) =>
    api.get("/api/astrology/quiz/history", { params: { profile_id: profileId } }),

  getQuizStats: (profileId = null) =>
    api.get("/api/astrology/quiz/stats", { params: { profile_id: profileId } }),

  deleteQuiz: (sessionId) => api.delete(`/api/astrology/quiz/${sessionId}`),
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
          max_tokens: model.maxTokens || undefined,
          vargas: model.vargas,
          sections: model.sections,
          ayanamsa: model.ayanamsa,
          mode: model.mode,
          source: model.source,
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
