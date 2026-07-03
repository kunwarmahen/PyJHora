import React, { createContext, useContext, useState, useCallback } from "react";
import i18n from "i18next";
import { DEFAULT_AYANAMSA } from "../constants/jyotish";

/**
 * A single, app-wide home for the user-tunable preferences that used to be
 * edited from scattered per-page dropdowns/toggles. It reads and writes the
 * SAME localStorage keys those pages already use, so the Settings page is the
 * canonical editor while every page continues to pick the values up. Values
 * that shouldn't be here (page-local ephemera like a transit date) are left out.
 */

// localStorage key for each setting. Kept identical to the historical keys so
// existing pages keep reading the right value with no change.
export const SETTING_KEYS = {
  language: "lang", // also owned by i18next's language detector
  ayanamsa: "ayanamsa",
  chartStyle: "chartStyle",
  panchangaSystem: "panchanga_system",
  aiProviderType: "ai_provider_type",
  aiModel: "ai_model",
  aiBaseUrl: "ai_base_url",
  aiMode: "ai_mode",
  aiMaxTokens: "ai_max_tokens",
};

const DEFAULTS = {
  language: "en",
  ayanamsa: DEFAULT_AYANAMSA,
  chartStyle: "north",
  panchangaSystem: "drik",
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

const SettingsContext = createContext(null);

export const SettingsProvider = ({ children }) => {
  const [settings, setSettings] = useState(() => ({
    language: read("language"),
    ayanamsa: read("ayanamsa"),
    chartStyle: read("chartStyle"),
    panchangaSystem: read("panchangaSystem"),
    aiProviderType: read("aiProviderType"),
    aiModel: read("aiModel"),
    aiBaseUrl: read("aiBaseUrl"),
    aiMode: read("aiMode"),
    aiMaxTokens: readNumber("aiMaxTokens"),
  }));

  const updateSetting = useCallback((key, value) => {
    const storageKey = SETTING_KEYS[key];
    if (!storageKey) return;
    try {
      localStorage.setItem(storageKey, String(value));
    } catch {
      // ignore quota / privacy-mode failures
    }
    // Language is special: drive i18next so the switch is immediate app-wide.
    if (key === "language") {
      try {
        i18n.changeLanguage(value);
      } catch {
        // ignore
      }
    }
    setSettings((prev) => ({ ...prev, [key]: value }));
  }, []);

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
