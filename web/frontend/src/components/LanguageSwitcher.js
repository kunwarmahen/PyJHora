import React from "react";
import { useTranslation } from "react-i18next";
import { Globe } from "lucide-react";
import { LANGUAGES } from "../i18n";
import "../styles/LanguageSwitcher.css";

/**
 * Compact language selector. A native <select> wrapped with a globe icon so it
 * stays usable on touch and keyboard. Persisting the choice is handled by the
 * i18next language detector (localStorage key "lang"). Shows on every page via
 * the Dashboard navbar / PageHeader nav-right slot.
 */
export const LanguageSwitcher = ({ className = "" }) => {
  const { i18n, t } = useTranslation();
  // Detector may return a region-tagged code (e.g. "en-US"); match the base.
  const current = LANGUAGES.find((l) => i18n.language?.startsWith(l.code))?.code || "en";

  return (
    <label className={`lang-switcher ${className}`} title={t("nav.language")}>
      <Globe size={16} aria-hidden="true" />
      <span className="lang-switcher-label">{t("nav.language")}</span>
      <select
        value={current}
        onChange={(e) => i18n.changeLanguage(e.target.value)}
        aria-label={t("nav.language")}
      >
        {LANGUAGES.map((l) => (
          <option key={l.code} value={l.code}>
            {l.native}
          </option>
        ))}
      </select>
    </label>
  );
};

export default LanguageSwitcher;
