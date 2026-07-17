/**
 * What happens to the profile picker on login: resume where you left off, or
 * always ask.
 *
 * Kept out of SettingsContext (which pulls in axios via the api service, and
 * with it a module graph jest can't transform) so the resolution rule stays
 * directly unit-testable — same reasoning as uiMode.js and signLabel.js.
 */

export const STARTUP_PROFILE_STORAGE_KEY = "startup_profile";

/**
 * Resume by default. Most people read one chart — their own — and the picker
 * was a click between them and it on every single login.
 */
export const STARTUP_PROFILE_DEFAULT = "resume";

export const STARTUP_PROFILE_MODES = ["resume", "ask"];

/**
 * Where ProfileContext caches the selected profile. Read here (rather than
 * imported from the context) to keep this module free of React.
 */
export const SELECTED_PROFILE_STORAGE_KEY = "selectedProfile";

/** The chosen mode, falling back to the default for anything unrecognised. */
export const readStartupProfileMode = () => {
  try {
    const stored = localStorage.getItem(STARTUP_PROFILE_STORAGE_KEY);
    return STARTUP_PROFILE_MODES.includes(stored) ? stored : STARTUP_PROFILE_DEFAULT;
  } catch {
    return STARTUP_PROFILE_DEFAULT;
  }
};

/** The id of the last profile selected on this device, or null. */
export const readLastProfileId = () => {
  try {
    const stored = localStorage.getItem(SELECTED_PROFILE_STORAGE_KEY);
    if (!stored) return null;
    return JSON.parse(stored)?._id ?? null;
  } catch {
    return null;
  }
};

/**
 * The profile to open on login, or null to show the picker.
 *
 * Precedence: the last-used profile → the default profile → the only profile
 * there is → the picker. That last case isn't in the precedence for its own
 * sake: with exactly one saved profile the picker can only be a click on the
 * one card, which is the friction this setting exists to remove.
 *
 * `profiles` must be the list just fetched from the server, and the return
 * value is an element OF that list — never the caller's cached copy. The cache
 * is a stale snapshot: the profile may have been renamed, edited, or deleted
 * from another device, and resuming into a chart that no longer exists (or
 * silently showing pre-edit birth details) is worse than showing the picker.
 * So `lastId` is only ever used to look up a fresh record.
 */
export const resolveStartupProfile = (profiles, { mode, lastId } = {}) => {
  if (mode === "ask") return null;
  const list = Array.isArray(profiles) ? profiles : [];
  if (list.length === 0) return null;
  const last = lastId ? list.find((p) => p._id === lastId) : null;
  if (last) return last;
  const preferred = list.find((p) => p.is_default);
  if (preferred) return preferred;
  return list.length === 1 ? list[0] : null;
};
