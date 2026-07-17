/**
 * Light / Dark / System — the theme preference and how it resolves.
 *
 * Kept out of SettingsContext for the same reason as uiMode: no axios in the
 * module graph, so the logic stays directly unit-testable.
 *
 * The one rule worth stating: unlike resolveUiMode(), this NEVER writes the
 * resolved value back. "system" has to stay "system" in storage, or the
 * preference would silently freeze into whatever the OS happened to be on the
 * first load and stop tracking it.
 */

export const THEME_STORAGE_KEY = "theme";
export const THEME_DEFAULT = "system";
export const THEMES = ["light", "dark", "system"];

const DARK_QUERY = "(prefers-color-scheme: dark)";

/** The stored preference ("light" | "dark" | "system"). */
export const readThemePref = () => {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    return THEMES.includes(stored) ? stored : THEME_DEFAULT;
  } catch {
    return THEME_DEFAULT;
  }
};

/** What the OS currently asks for. Defaults to light where unsupported. */
export const systemTheme = () => {
  try {
    return window.matchMedia && window.matchMedia(DARK_QUERY).matches ? "dark" : "light";
  } catch {
    return "light";
  }
};

/** Preference -> the theme actually rendered ("light" | "dark"). */
export const resolveTheme = (pref = readThemePref()) =>
  pref === "system" ? systemTheme() : THEMES.includes(pref) ? pref : systemTheme();

/** Stamp the resolved theme on <html>, where the CSS selector reads it. */
export const applyTheme = (pref = readThemePref()) => {
  const resolved = resolveTheme(pref);
  try {
    document.documentElement.setAttribute("data-theme", resolved);
  } catch {
    // non-DOM environment; nothing to stamp
  }
  return resolved;
};

/**
 * Call fn when the OS theme flips. Only meaningful while the preference is
 * "system" — the caller owns that check, since it re-subscribes on change.
 * Returns an unsubscribe.
 */
export const watchSystemTheme = (fn) => {
  let mq;
  try {
    mq = window.matchMedia && window.matchMedia(DARK_QUERY);
  } catch {
    return () => {};
  }
  if (!mq) return () => {};
  const handler = () => fn(systemTheme());
  // Safari < 14 has no addEventListener on MediaQueryList.
  if (mq.addEventListener) {
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }
  mq.addListener(handler);
  return () => mq.removeListener(handler);
};
