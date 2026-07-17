import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, Sparkles, X } from "lucide-react";
import { useSettings } from "../contexts/SettingsContext";
import { useLocation } from "react-router-dom";
import { isFeatureVisible } from "../config/features";
import "../styles/UiMode.css";

/**
 * Wraps in-page depth that only Everything mode advertises.
 *
 * In Everything mode it renders its children plainly — zero visual change from
 * before this component existed. In Essentials mode it collapses them behind one
 * "Show advanced details" disclosure: the content is still THERE and one click
 * away, because hiding is a matter of first impression, not of permission.
 *
 * `title` overrides the default disclosure label. `defaultOpen` is honoured only
 * in Essentials mode (Everything is always open).
 */
export const AdvancedOnly = ({ children, title, defaultOpen = false }) => {
  const { t } = useTranslation();
  const { settings } = useSettings();
  const [open, setOpen] = useState(defaultOpen);

  if (settings.uiMode === "advanced") return <>{children}</>;

  return (
    <div className={`advanced-only ${open ? "open" : ""}`}>
      <button
        type="button"
        className="advanced-only__toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Sparkles size={16} />
        <span>{title || t("uiMode.showAdvanced")}</span>
        <ChevronDown size={16} className="advanced-only__chevron" />
      </button>
      {open && <div className="advanced-only__body">{children}</div>}
    </div>
  );
};

/**
 * The banner an advanced page shows when you reach it in Essentials mode —
 * from a bookmark, a shared link, saved AI history, or a suggestion the model
 * made. The page renders normally; deep-links must never dead-end, so this
 * explains where you are rather than redirecting you away.
 */
export const AdvancedNotice = () => {
  const { t } = useTranslation();
  const { settings, updateSetting } = useSettings();
  const location = useLocation();
  const [dismissed, setDismissed] = useState(false);

  if (dismissed || isFeatureVisible(location.pathname, settings.uiMode)) return null;

  return (
    <div className="advanced-notice">
      <Sparkles size={18} className="advanced-notice__icon" />
      <p className="advanced-notice__text">{t("uiMode.advancedPageNotice")}</p>
      <button
        type="button"
        className="advanced-notice__cta"
        onClick={() => updateSetting("uiMode", "advanced")}
      >
        {t("uiMode.switchToEverything")}
      </button>
      <button
        type="button"
        className="advanced-notice__dismiss"
        aria-label={t("common.dismiss")}
        onClick={() => setDismissed(true)}
      >
        <X size={16} />
      </button>
    </div>
  );
};

export default AdvancedOnly;
