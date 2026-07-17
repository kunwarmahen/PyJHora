// Localizes engine-returned names (rasis, nakshatras, grahas) for display.
//
// The UI chrome is translated through i18next, but chart *data* arrives from the
// backend in canonical English ("Krittika", "Aries", "Moon"). These names are values,
// not UI strings, so they don't belong in the locale JSON — they're keyed off the
// backend's tables and generated into nameLocales.generated.js instead. See
// scripts/gen-name-locales.js for where the translations come from.
//
// Falling back to the English input is deliberate and normal: an unmapped name (a new
// dasha lord, an upstream rename, a composite label) renders readable English rather
// than a missing-key marker.

import { useCallback } from "react";
import { useTranslation } from "react-i18next";

import NAME_LOCALES from "../constants/nameLocales.generated";

// Public `kind` values -> the generated table names.
const TABLES = {
  rasi: { full: "rasis", abbr: "rasisAbbr" },
  nakshatra: { full: "nakshatras", abbr: "nakshatrasAbbr" },
  graha: { full: "grahas", abbr: "grahasAbbr" },
};

/**
 * Translate one engine-returned name.
 *
 * @param {string} name  canonical English name from the backend, e.g. "Krittika"
 * @param {"rasi"|"nakshatra"|"graha"} kind
 * @param {string} lang  i18n language code ("en" | "hi" | "sa", or a region variant)
 * @param {{abbr?: boolean}} [opts]  abbr picks the compact chart-cell form
 * @returns {string} the localized name, or `name` unchanged if there's no mapping
 */
export function localizeName(name, kind, lang, opts = {}) {
  if (!name || typeof name !== "string") return name;

  // "hi-IN" and friends: the tables are keyed by base language.
  const base = String(lang || "en").split("-")[0];
  const tables = NAME_LOCALES[base];
  if (!tables) return name; // a language we have no name data for

  const table = TABLES[kind];
  if (!table) return name;

  return tables[opts.abbr ? table.abbr : table.full][name.trim()] || name;
}

/**
 * Hook form, bound to the active language — the usual way to call this from a
 * component: `const ln = useLocalizeName(); ln(p.sign_name, "rasi")`.
 */
export function useLocalizeName() {
  const { i18n } = useTranslation();
  const lang = i18n.language;
  return useCallback(
    (name, kind, opts) => localizeName(name, kind, lang, opts),
    [lang]
  );
}
