/**
 * Who this browser's cached account settings belong to.
 *
 * The synced preferences (LLM provider/model, theme, view mode…) are cached in
 * localStorage for a fast first paint, but they are ACCOUNT settings — logout
 * clears the tokens and leaves the cache behind, so the next person to sign in
 * on the same browser inherited them, and SettingsContext's "server has nothing
 * yet, seed it from this device" step then wrote them permanently onto that
 * second account. That is how one user's Gemini model id ended up being sent as
 * another user's Ollama model.
 *
 * Kept out of SettingsContext (which pulls in axios via the api service, and
 * with it a module graph jest can't transform) so the rule stays directly
 * unit-testable — same reasoning as uiMode.js and startupProfile.js.
 */

export const PREFS_OWNER_STORAGE_KEY = "prefs_owner";

/**
 * Stamp `username` as the owner of this browser's synced-pref cache.
 *
 * Returns true when the cache demonstrably belonged to somebody ELSE, meaning
 * the caller must drop it and let this user fall back to the defaults (i.e.
 * whatever the server's own .env configures) until they choose for themselves.
 *
 * An unstamped cache is grandfathered to the first user who claims it: that is
 * every install predating this stamp, whose cached settings really are theirs.
 */
export const claimPrefsOwner = (username) => {
  if (!username) return false;
  let previous = null;
  try {
    previous = localStorage.getItem(PREFS_OWNER_STORAGE_KEY);
    localStorage.setItem(PREFS_OWNER_STORAGE_KEY, username);
  } catch {
    return false; // no storage ⇒ nothing cached, nothing to leak
  }
  return !!previous && previous !== username;
};
