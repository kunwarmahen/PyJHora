/**
 * Essentials ("simple") vs Everything ("advanced") — the view mode, and the
 * rule for which one a user starts in.
 *
 * Kept out of SettingsContext (which pulls in axios via the api service, and
 * with it a module graph jest can't transform) so the one piece of logic here
 * that can actually hurt someone stays directly unit-testable.
 */

export const UI_MODE_STORAGE_KEY = "ui_mode";
export const UI_MODE_DEFAULT = "simple";
export const UI_MODES = ["simple", "advanced"];

// Any of these in localStorage means this browser used the app before the
// Essentials/Everything split existed — i.e. someone already at home in the full
// feature set, who would experience "simple" as their app losing pages.
const PRIOR_USE_KEYS = [
  "ayanamsa",
  "chartStyle",
  "ai_model",
  "ai_provider_type",
  "panchanga_system",
];

/**
 * The mode to start in when nothing has been chosen yet.
 *
 * New user → Essentials (the whole point of the feature). Existing user →
 * Everything, so the split never silently takes pages away from someone who was
 * already using them. "Existing" is evidenced by prior settings in this browser;
 * the login sync in SettingsContext covers the other case — an existing ACCOUNT
 * on a fresh browser, where localStorage is empty but the server already holds
 * preferences.
 *
 * The answer is WRITTEN BACK on first resolve, which is load-bearing rather than
 * an optimisation: the prior-use evidence is keys that normal use goes on to
 * create (AskAstrologerPage writes ai_model, and Ask AI is itself an Essentials
 * feature). Re-deriving on every load would therefore promote a new user to
 * Everything behind their back the moment they used the app. Decide once, record
 * it, and from then on only an explicit choice moves it.
 */
export const resolveUiMode = () => {
  try {
    const stored = localStorage.getItem(UI_MODE_STORAGE_KEY);
    if (UI_MODES.includes(stored)) return stored;
    const priorUse = PRIOR_USE_KEYS.some((k) => localStorage.getItem(k) !== null);
    const mode = priorUse ? "advanced" : UI_MODE_DEFAULT;
    localStorage.setItem(UI_MODE_STORAGE_KEY, mode);
    return mode;
  } catch {
    return UI_MODE_DEFAULT;
  }
};
