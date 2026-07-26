/**
 * Who this browser's cached state belongs to.
 *
 * Settings, and the chart you were last reading, are cached in localStorage for
 * a fast first paint — but they belong to an ACCOUNT, not to a browser. Logout
 * clears the tokens and leaves all of it behind, so the next person to sign in
 * on the same machine inherited the previous user's settings, and
 * SettingsContext's "server has nothing yet, seed it from this device" step then
 * wrote them permanently onto that second account. That is how one user's Gemini
 * model id ended up being sent as another user's Ollama model.
 *
 * The reset is keyed on somebody else signing IN — not on the first person
 * signing out. Nobody should have to log out to keep their settings to
 * themselves, and a user whose session simply expired never gets the chance.
 *
 * Kept out of the contexts (which pull in axios via the api service, and with it
 * a module graph jest can't transform) so the rule stays directly unit-testable
 * — same reasoning as uiMode.js and startupProfile.js.
 */

export const PREFS_OWNER_STORAGE_KEY = "prefs_owner";

/**
 * Keys a purge must leave alone: the session being established (the tokens are
 * already stored by the time the profile loads — purging them logs the new user
 * straight back out) and the stamp itself.
 */
const NEVER_PURGE = new Set([PREFS_OWNER_STORAGE_KEY, "access_token", "refresh_token"]);

/**
 * The decision for this page session. Several contexts ask the same question
 * about the same login and must all get the same answer — whoever asked first
 * would otherwise stamp the browser and leave the rest seeing a cache that now
 * looks like their own.
 */
let claim = null;

/** Test seam: forget the memoised decision, as a fresh page load would. */
export const resetPrefsOwnerClaim = () => {
  claim = null;
};

/**
 * Stamp `username` as the owner of this browser's cached state.
 *
 * Returns true when the cache demonstrably belonged to somebody ELSE, meaning
 * the caller must drop whatever it restored and let this user fall back to the
 * defaults (i.e. whatever the server's own .env configures) until they choose
 * for themselves. Idempotent per login: repeat calls report the same verdict.
 *
 * An unstamped cache is grandfathered to the first user who claims it: that is
 * every install predating this stamp, whose cached settings really are theirs.
 */
export const claimPrefsOwner = (username) => {
  if (!username) return false;
  if (claim && claim.username === username) return claim.foreign;
  let previous = null;
  try {
    previous = localStorage.getItem(PREFS_OWNER_STORAGE_KEY);
    localStorage.setItem(PREFS_OWNER_STORAGE_KEY, username);
  } catch {
    claim = { username, foreign: false }; // no storage ⇒ nothing cached to leak
    return false;
  }
  claim = { username, foreign: !!previous && previous !== username };
  return claim.foreign;
};

/**
 * Drop every cached thing that belonged to the previous account.
 *
 * Deliberately a wipe with an exception list rather than a list of keys to
 * remove: pages cache what they like (the selected profile and its birth
 * details, view state, an AI model id), and a key added next year must not
 * quietly become the next thing to follow a user around. Nothing here is
 * unrecoverable — synced preferences come back from the server on login, and
 * everything else is a default.
 *
 * Returns the keys removed (for tests and logging).
 */
export const purgeCachedUserState = () => {
  let keys = [];
  try {
    keys = Object.keys(localStorage);
  } catch {
    return [];
  }
  const removed = keys.filter((k) => !NEVER_PURGE.has(k));
  removed.forEach((k) => {
    try {
      localStorage.removeItem(k);
    } catch {
      // ignore
    }
  });
  return removed;
};
