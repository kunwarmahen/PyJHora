import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import en from "./locales/en.json";

// Only English is bundled with the app (§68.4). hi.json and sa.json are 164 KB
// of JSON between them, and every visitor was paying for both in the initial
// bundle to read a UI in one language. They are fetched as their own chunk the
// first time that language is actually selected — see `ensureLanguage`, which
// index.js awaits before the first paint so a Hindi user never sees a flash of
// English. Nothing about the data layer changes: this is when the UI strings
// arrive, not which layer owns them (see docs/I18N_DATA_LAYER_DESIGN.md).
const LOADERS = {
  hi: () => import("./locales/hi.json"),
  sa: () => import("./locales/sa.json"),
};

// Supported UI languages. `dir` is here so RTL can be added later without
// touching the switcher; all current languages are LTR.
export const LANGUAGES = [
  { code: "en", label: "English", native: "English" },
  { code: "hi", label: "Hindi", native: "हिन्दी" },
  { code: "sa", label: "Sanskrit", native: "संस्कृतम्" },
];

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { en: { translation: en } },
    fallbackLng: "en",
    supportedLngs: LANGUAGES.map((l) => l.code),
    interpolation: { escapeValue: false }, // React already escapes
    detection: {
      // Persist the user's choice; check localStorage before the browser.
      order: ["localStorage", "navigator"],
      lookupLocalStorage: "lang",
      caches: ["localStorage"],
    },
  });

/**
 * Make sure `code`'s strings are loaded, fetching the locale chunk if needed.
 *
 * Resolves immediately for English (bundled) and for anything already loaded.
 * Re-applying the language after the bundle lands is what re-renders the tree —
 * react-i18next listens for `languageChanged`, not for a resource being added.
 */
export const ensureLanguage = async (code) => {
  const lng = String(code || "en").split("-")[0];
  const load = LOADERS[lng];
  if (!load || i18n.hasResourceBundle(lng, "translation")) return;
  try {
    const mod = await load();
    i18n.addResourceBundle(lng, "translation", mod.default || mod, true, true);
    if (i18n.language && i18n.language.split("-")[0] === lng) {
      await i18n.changeLanguage(lng);
    }
  } catch {
    // A failed locale fetch (offline, bad deploy) falls back to English rather
    // than taking the app down.
  }
};

// Covers every switch site — the settings picker, the server-synced preference
// and the detector's own choice — without any of them needing to know that the
// strings are fetched.
i18n.on("languageChanged", (lng) => {
  ensureLanguage(lng);
});

export default i18n;
