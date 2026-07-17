import React from "react";
import { useTranslation } from "react-i18next";
import { Sun, Moon, Monitor } from "lucide-react";
import { useSettings } from "../contexts/SettingsContext";
import { resolveTheme } from "../config/theme";

/**
 * Light / Dark / System, cycled from the page header.
 *
 * A cycle rather than a switch because the preference is three-way: a plain
 * toggle would have no way to express "System", and dropping System from the
 * header would strand it in Settings where nobody would find it.
 */
const ORDER = ["light", "dark", "system"];
const ICON = { light: Sun, dark: Moon, system: Monitor };

export const ThemeToggle = () => {
  const { settings, updateSetting } = useSettings();
  const { t } = useTranslation();
  const pref = settings.theme;
  const Icon = ICON[pref] || Monitor;
  const next = ORDER[(ORDER.indexOf(pref) + 1) % ORDER.length];

  // "System" alone doesn't say what you're looking at; name the outcome too.
  const label =
    pref === "system"
      ? t("settings.themeSystemResolved", {
          theme: t(`settings.theme_${resolveTheme("system")}`),
        })
      : t(`settings.theme_${pref}`);

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={() => updateSetting("theme", next)}
      title={t("settings.themeCycle", { theme: t(`settings.theme_${next}`) })}
      aria-label={t("settings.themeCycle", { theme: t(`settings.theme_${next}`) })}
    >
      <Icon size={16} />
      <span className="theme-toggle__label">{label}</span>
    </button>
  );
};

export default ThemeToggle;
