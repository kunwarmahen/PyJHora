import React from "react";
import { useTranslation } from "react-i18next";
import { Leaf, Layers3 } from "lucide-react";
import { useSettings } from "../contexts/SettingsContext";
import "../styles/UiMode.css";

/**
 * Essentials ⇄ Everything switch.
 *
 * Deliberately lives in the page chrome (NavDrawer) and not only in Settings:
 * someone who lands in Essentials must be able to SEE that there is more, and
 * find their way back up, without knowing to go hunting in a settings tab.
 */
export const UiModeToggle = ({ variant = "drawer" }) => {
  const { t } = useTranslation();
  const { settings, updateSetting } = useSettings();
  const mode = settings.uiMode;

  const options = [
    { value: "simple", labelKey: "uiMode.essentials", Icon: Leaf },
    { value: "advanced", labelKey: "uiMode.everything", Icon: Layers3 },
  ];

  return (
    <div className={`ui-mode-toggle ui-mode-toggle--${variant}`}>
      <span className="ui-mode-toggle__label">{t("uiMode.label")}</span>
      <div className="ui-mode-toggle__options" role="group" aria-label={t("uiMode.label")}>
        {options.map(({ value, labelKey, Icon }) => (
          <button
            key={value}
            type="button"
            className={`ui-mode-toggle__option ${mode === value ? "active" : ""}`}
            aria-pressed={mode === value}
            onClick={() => updateSetting("uiMode", value)}
          >
            <Icon size={15} />
            <span>{t(labelKey)}</span>
          </button>
        ))}
      </div>
      <p className="ui-mode-toggle__hint">
        {t(mode === "simple" ? "uiMode.hintSimple" : "uiMode.hintAdvanced")}
      </p>
    </div>
  );
};

export default UiModeToggle;
