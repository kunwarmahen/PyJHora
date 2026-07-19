/**
 * Compact / Comfortable — how much room the UI takes (§15).
 *
 * The §15 pass tightened cards and tiles so 39 features stay browsable, but the
 * roomier scale is a legitimate preference (and easier on the eyes on a big
 * screen), so it stays available rather than being replaced outright.
 *
 * Both scales are token sets in App.css: `:root` holds compact, and
 * `:root[data-density="comfortable"]` restores the original spacing. Nothing
 * reads this module for layout — it only stamps the attribute, exactly like
 * theme.js stamps data-theme.
 *
 * Kept out of SettingsContext for the same reason as uiMode/theme: no axios in
 * the module graph, so the logic stays directly unit-testable.
 */

export const DENSITY_STORAGE_KEY = "density";
export const DENSITY_DEFAULT = "compact";
export const DENSITIES = ["compact", "comfortable"];

/** The stored preference, falling back to compact for anything unrecognised. */
export const readDensityPref = () => {
  try {
    const stored = localStorage.getItem(DENSITY_STORAGE_KEY);
    return DENSITIES.includes(stored) ? stored : DENSITY_DEFAULT;
  } catch {
    // Private mode / storage disabled — the default is still perfectly usable.
    return DENSITY_DEFAULT;
  }
};

/**
 * Stamp the choice on <html>.
 *
 * Compact is what `:root` already defines, so it carries no attribute at all —
 * that keeps the default free of a redundant selector and means a broken value
 * degrades to the default rather than to an undefined scale.
 */
export const applyDensity = (pref = readDensityPref()) => {
  if (typeof document === "undefined") return DENSITY_DEFAULT;
  const resolved = DENSITIES.includes(pref) ? pref : DENSITY_DEFAULT;
  if (resolved === "comfortable") {
    document.documentElement.setAttribute("data-density", "comfortable");
  } else {
    document.documentElement.removeAttribute("data-density");
  }
  return resolved;
};
