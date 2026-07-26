import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from "react";
import i18n from "i18next";
import { DEFAULT_AYANAMSA } from "../constants/jyotish";
import { resolveUiMode, UI_MODE_DEFAULT, UI_MODE_STORAGE_KEY } from "../config/uiMode";
import { SIGN_LABEL_DEFAULT, SIGN_LABEL_STORAGE_KEY } from "../config/signLabel";
import { STARTUP_PROFILE_DEFAULT, STARTUP_PROFILE_STORAGE_KEY } from "../config/startupProfile";
import {
  applyTheme,
  readThemePref,
  THEME_DEFAULT,
  THEME_STORAGE_KEY,
  watchSystemTheme,
} from "../config/theme";
import {
  applyDensity,
  readDensityPref,
  DENSITY_DEFAULT,
  DENSITY_STORAGE_KEY,
} from "../config/density";
import { claimPrefsOwner } from "../config/prefsOwner";
import { astrologyService } from "../services/api";
import { useAuth } from "./AuthContext";

/**
 * A single, app-wide home for the user-tunable preferences that used to be
 * edited from scattered per-page dropdowns/toggles. It reads and writes the
 * SAME localStorage keys those pages already use, so the Settings page is the
 * canonical editor while every page continues to pick the values up. Values
 * that shouldn't be here (page-local ephemera like a transit date) are left out.
 *
 * The LLM/model preferences (SYNCED_KEYS) are ALSO persisted server-side per
 * user, so the choice follows them across devices and the scheduled daily digest
 * can render its AI narrative with the model they actually picked. localStorage
 * stays the fast local cache; on login we pull the server copy, and each change
 * is debounced back up.
 */

// localStorage key for each setting. Kept identical to the historical keys so
// existing pages keep reading the right value with no change.
export const SETTING_KEYS = {
  language: "lang", // also owned by i18next's language detector
  uiMode: UI_MODE_STORAGE_KEY,
  theme: THEME_STORAGE_KEY,
  density: DENSITY_STORAGE_KEY,
  startupProfile: STARTUP_PROFILE_STORAGE_KEY,
  ayanamsa: "ayanamsa",
  chartStyle: "chartStyle",
  signLabel: SIGN_LABEL_STORAGE_KEY,
  panchangaSystem: "panchanga_system",
  praveshaBasis: "pravesha_basis",
  varnadaMethod: "varnada_method",
  aiProviderType: "ai_provider_type",
  aiModel: "ai_model",
  aiBaseUrl: "ai_base_url",
  aiMode: "ai_mode",
  aiMaxTokens: "ai_max_tokens",
};

// The preferences synced to the server (cross-device). The non-secret LLM/model
// choice, plus the Essentials/Everything view mode — API keys have their own
// encrypted store. Each of these must also be in user_settings.PREFERENCE_KEYS
// server-side, which is a whitelist: a key missing there is dropped silently.
const SYNCED_KEYS = [
  "uiMode",
  "theme",
  "density",
  "startupProfile",
  "aiProviderType",
  "aiModel",
  "aiBaseUrl",
  "aiMode",
  "aiMaxTokens",
];
// Discrete one-click choices, pushed to the server immediately rather than on
// the 600ms debounce. The debounce is there to coalesce typing (aiBaseUrl,
// aiModel); for a toggle it only opens a race. A reload inside that window
// leaves the server holding the OLD value, and the login sync below then
// reasserts it over the correct local one — so the user's click silently
// reverts on the next page load. Visible immediately with the theme toggle.
const IMMEDIATE_KEYS = ["theme", "density", "uiMode", "startupProfile"];
// Settings that only mean anything under the provider they were chosen for: a
// model id belongs to one vendor's catalogue, an endpoint to one server. Left
// standing across a provider switch they are sent to the NEW provider, which is
// how a Gemini model id reached Ollama ("model 'gemini-…' not found") after the
// user removed their Gemini key and went back to local. Cleared on the switch;
// blank means "the server's default for whichever provider is selected now".
const PROVIDER_SCOPED_KEYS = ["aiModel", "aiBaseUrl"];
// storageKey -> settingKey, to apply a server payload (keyed by storage key).
const STORAGE_TO_SETTING = Object.fromEntries(
  Object.entries(SETTING_KEYS).map(([settingKey, storageKey]) => [storageKey, settingKey])
);

const DEFAULTS = {
  language: "en",
  // How much of the app to advertise: "simple" = the Essentials set, "advanced"
  // = Everything. A pure VIEW preference — it must never touch aiMode, the
  // prompt or the tool catalogue (owner decision, todo.md §36).
  uiMode: UI_MODE_DEFAULT,
  // "light" | "dark" | "system". System is the default so a user whose machine
  // is already dark never gets shown the light theme first (owner, §37).
  theme: THEME_DEFAULT,
  // "compact" | "comfortable" — how much room cards and tiles take (§15).
  density: DENSITY_DEFAULT,
  // What login does with the profile picker: "resume" the last-used/default
  // profile, or always "ask".
  startupProfile: STARTUP_PROFILE_DEFAULT,
  ayanamsa: DEFAULT_AYANAMSA,
  chartStyle: "north",
  // How a house's rasi is labelled: "number" | "glyph" | "number_glyph" | "abbr".
  signLabel: SIGN_LABEL_DEFAULT,
  panchangaSystem: "drik",
  // Which pravesha ladder the period readings default to:
  // "solar" (Tajaka: Varshaphal / Maasa Pravesha) or "lunar" (tithi: Tithi
  // Pravesha / birth-tithi return). Pages may override it locally.
  praveshaBasis: "solar",
  // Which published derivation of the Varnada lagna to use, "1".."4". Method 1
  // (Sanjay Rath) is the default because it is the one that reproduces
  // Jagannatha Hora's V1..V12 exactly — consistent with the app's other
  // JHora-matching defaults (True Chitra ayanamsa, mean nodes).
  varnadaMethod: "1",
  aiProviderType: "ollama",
  aiModel: "",
  aiBaseUrl: "",
  aiMode: "pass_all",
  aiMaxTokens: 0, // 0 = use the provider/server default
};

const read = (key) => {
  try {
    const v = localStorage.getItem(SETTING_KEYS[key]);
    return v === null ? DEFAULTS[key] : v;
  } catch {
    return DEFAULTS[key];
  }
};

const readNumber = (key) => {
  const n = parseInt(read(key), 10);
  return Number.isFinite(n) ? n : DEFAULTS[key];
};

// Coerce a stored (string) value to the in-state type for one setting key.
const coerce = (key, value) =>
  key === "aiMaxTokens"
    ? Number.isFinite(parseInt(value, 10))
      ? parseInt(value, 10)
      : DEFAULTS.aiMaxTokens
    : value;

const SettingsContext = createContext(null);

export const SettingsProvider = ({ children }) => {
  const { user } = useAuth();
  const [settings, setSettings] = useState(() => ({
    language: read("language"),
    uiMode: resolveUiMode(),
    theme: readThemePref(),
    density: readDensityPref(),
    startupProfile: read("startupProfile"),
    ayanamsa: read("ayanamsa"),
    chartStyle: read("chartStyle"),
    signLabel: read("signLabel"),
    panchangaSystem: read("panchangaSystem"),
    praveshaBasis: read("praveshaBasis"),
    varnadaMethod: read("varnadaMethod"),
    aiProviderType: read("aiProviderType"),
    aiModel: read("aiModel"),
    aiBaseUrl: read("aiBaseUrl"),
    aiMode: read("aiMode"),
    aiMaxTokens: readNumber("aiMaxTokens"),
  }));

  // Mirror of `settings` so callbacks can read the current values without being
  // rebuilt (and re-subscribed) on every change.
  const settingsRef = useRef(settings);
  settingsRef.current = settings;

  // Debounced server push of synced preferences.
  const pendingPush = useRef({});
  const pushTimer = useRef(null);
  const loggedIn = useRef(!!user);
  loggedIn.current = !!user;

  const flushPush = useCallback(() => {
    const patch = pendingPush.current;
    pendingPush.current = {};
    if (Object.keys(patch).length === 0) return;
    astrologyService.putPreferences(patch).catch(() => {
      // Best-effort — the value is already saved locally; try again next change.
    });
  }, []);

  const schedulePush = useCallback(
    (settingKey, value) => {
      pendingPush.current[SETTING_KEYS[settingKey]] = String(value);
      if (pushTimer.current) clearTimeout(pushTimer.current);
      pushTimer.current = setTimeout(flushPush, 600);
    },
    [flushPush]
  );

  // Persist ONE key: localStorage, the immediate side effects, and the server
  // mirror. The React state update is the caller's, so a cascade of keys lands
  // in a single render.
  const persistSetting = useCallback(
    (key, value) => {
      const storageKey = SETTING_KEYS[key];
      if (!storageKey) return;
      try {
        localStorage.setItem(storageKey, String(value));
      } catch {
        // ignore quota / privacy-mode failures
      }
      // Theme is special: restamp <html> so the switch is immediate. The
      // pre-paint script in index.html only covers the first load.
      if (key === "theme") {
        applyTheme(value);
      } else if (key === "density") {
        applyDensity(value);
      }
      // Language is special: drive i18next so the switch is immediate app-wide.
      if (key === "language") {
        try {
          i18n.changeLanguage(value);
        } catch {
          // ignore
        }
      }
      // Mirror synced prefs up to the server so they follow the user's devices.
      if (loggedIn.current && SYNCED_KEYS.includes(key)) {
        pendingPush.current[SETTING_KEYS[key]] = String(value);
        if (IMMEDIATE_KEYS.includes(key)) {
          if (pushTimer.current) clearTimeout(pushTimer.current);
          flushPush();
        } else {
          schedulePush(key, value);
        }
      }
    },
    [schedulePush, flushPush]
  );

  const updateSetting = useCallback(
    (key, value) => {
      if (!SETTING_KEYS[key]) return;
      const patch = { [key]: value };
      // Changing provider drops the model/endpoint picked for the old one —
      // see PROVIDER_SCOPED_KEYS.
      if (key === "aiProviderType" && value !== settingsRef.current.aiProviderType) {
        PROVIDER_SCOPED_KEYS.forEach((k) => {
          patch[k] = DEFAULTS[k];
        });
      }
      Object.entries(patch).forEach(([k, v]) => persistSetting(k, v));
      setSettings((prev) => ({ ...prev, ...patch }));
    },
    [persistSetting]
  );

  // On login, pull the server copy of the synced prefs (server is source of
  // truth). If the server has nothing yet, seed it from this device so an
  // existing user's current choice starts syncing.
  useEffect(() => {
    if (!user) return undefined;
    let cancelled = false;
    (async () => {
      try {
        // Whose cache is this? Logout leaves the preferences behind, so the next
        // person to sign in on this browser would otherwise inherit the previous
        // user's account settings — and the seed below would write them onto
        // their account for good. See config/prefsOwner.js. A foreign cache is
        // dropped and NOT seeded: this user falls back to the server defaults
        // until they choose for themselves.
        const foreignCache = claimPrefsOwner(user?.username);
        if (foreignCache) {
          const cleared = {};
          SYNCED_KEYS.forEach((k) => {
            try {
              localStorage.removeItem(SETTING_KEYS[k]);
            } catch {
              // ignore
            }
            cleared[k] = DEFAULTS[k];
          });
          if (!cancelled) setSettings((prev) => ({ ...prev, ...cleared }));
        }
        const res = await astrologyService.getPreferences();
        if (cancelled) return;
        const serverPrefs = res.data?.preferences || {};
        const applied = {};
        let anyServer = false;
        Object.entries(serverPrefs).forEach(([storageKey, value]) => {
          const settingKey = STORAGE_TO_SETTING[storageKey];
          if (!settingKey || !SYNCED_KEYS.includes(settingKey)) return;
          anyServer = true;
          try {
            localStorage.setItem(storageKey, String(value));
          } catch {
            // ignore
          }
          applied[settingKey] = coerce(settingKey, value);
        });
        // An account with preferences but no ui_mode predates the
        // Essentials/Everything split: grandfather it into Everything and write
        // that back, so the same user on a fresh browser (empty localStorage, so
        // resolveUiMode() saw no prior use) doesn't get a shrunken app.
        if (anyServer && !(SETTING_KEYS.uiMode in serverPrefs)) {
          applied.uiMode = "advanced";
          try {
            localStorage.setItem(SETTING_KEYS.uiMode, "advanced");
          } catch {
            // ignore
          }
          astrologyService.putPreferences({ [SETTING_KEYS.uiMode]: "advanced" }).catch(() => {});
        }
        if (Object.keys(applied).length) {
          setSettings((prev) => ({ ...prev, ...applied }));
        }
        if (!anyServer && !foreignCache) {
          const seed = {};
          SYNCED_KEYS.forEach((k) => {
            // uiMode via resolveUiMode, not read() — the seed must carry the
            // grandfathered value, not the bare "simple" default.
            seed[SETTING_KEYS[k]] = String(k === "uiMode" ? resolveUiMode() : read(k));
          });
          astrologyService.putPreferences(seed).catch(() => {});
        }
      } catch {
        // Offline / not critical — local cache still applies.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  // Keep <html> in step with the preference — covers the server copy landing
  // at login, which can disagree with what the pre-paint script stamped.
  useEffect(() => {
    applyTheme(settings.theme);
    applyDensity(settings.density);
  }, [settings.theme, settings.density]);

  // While on "system", follow the OS flipping with the tab already open.
  // Re-subscribing per preference change is what makes the listener idle on an
  // explicit light/dark choice instead of fighting it.
  useEffect(() => {
    if (settings.theme !== "system") return undefined;
    return watchSystemTheme(() => applyTheme("system"));
  }, [settings.theme]);

  // Flush any pending push on unmount.
  useEffect(
    () => () => {
      if (pushTimer.current) {
        clearTimeout(pushTimer.current);
        flushPush();
      }
    },
    [flushPush]
  );

  return (
    <SettingsContext.Provider value={{ settings, updateSetting }}>
      {children}
    </SettingsContext.Provider>
  );
};

export const useSettings = () => {
  const ctx = useContext(SettingsContext);
  if (!ctx) {
    throw new Error("useSettings must be used within SettingsProvider");
  }
  return ctx;
};
