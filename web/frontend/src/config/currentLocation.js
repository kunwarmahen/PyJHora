/**
 * "Where are you now?" — detecting that the answer changed, and deciding whether
 * to say anything about it.
 *
 * The rule is deliberately conservative. Detection **suggests**; the user
 * confirms. Silently adopting whatever the browser reports would mean a week in
 * London quietly rewrites someone's panchanga and moves their digest, with no
 * visible cause — and travel is common, while moving country is not.
 *
 * Kept out of the context (which pulls in axios via the api service, and with it
 * a module graph jest can't transform) so the rule stays directly unit-testable —
 * same reasoning as uiMode.js / signLabel.js / startupProfile.js.
 */

/** Zones the user has told us to stop asking about, per browser. */
const DISMISSED_KEY = "location_prompt_dismissed";

/** The browser's own IANA zone ("America/Chicago"), or null if it won't say. */
export const detectZone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
};

/** The browser's current UTC offset in hours (DST-aware, east-positive). */
export const detectOffsetHours = () => {
  try {
    // getTimezoneOffset is minutes WEST of UTC — inverted from how everyone
    // says it. India reports -330, meaning +5.5.
    return -new Date().getTimezoneOffset() / 60;
  } catch {
    return null;
  }
};

/**
 * The city a zone is named after ("America/Chicago" → "Chicago"), for labelling
 * the button — "I'm in Chicago" beats "I'm in America/Chicago".
 *
 * Display only. The server does this lookup again for real (and *verifies* it
 * against the coordinates) when saving; this must never be the thing that
 * decides what gets stored. Mirrors `timezones.representative_place`.
 */
export const zoneCity = (zone) => {
  if (!zone || !zone.includes("/")) return null;
  const [region, ...rest] = zone.split("/");
  if (["Etc", "SystemV", "US"].includes(region)) return null;
  return rest[rest.length - 1].replace(/_/g, " ").trim() || null;
};

export const dismissZone = (zone) => {
  if (!zone) return;
  try {
    const seen = new Set(JSON.parse(localStorage.getItem(DISMISSED_KEY) || "[]"));
    seen.add(zone);
    localStorage.setItem(DISMISSED_KEY, JSON.stringify([...seen]));
  } catch {
    // ignore quota / privacy-mode failures
  }
};

export const isZoneDismissed = (zone) => {
  if (!zone) return false;
  try {
    return JSON.parse(localStorage.getItem(DISMISSED_KEY) || "[]").includes(zone);
  } catch {
    return false;
  }
};

/**
 * Whether to suggest updating the current location, and why.
 *
 * Returns `{ kind, zone }` or null for "say nothing":
 *   - `"moved"`   — a location is set and the browser is somewhere else.
 *   - `"unset"`   — no location is set, and the browser's offset disagrees with
 *                   the birth profile's. This is the India-born/US-resident case
 *                   the whole feature exists for; it's the ONLY case where an
 *                   unset location is worth mentioning, because someone who
 *                   still lives where they were born needs nothing from us.
 *
 * `birthOffset` is the profile's stored float offset. Comparing offsets rather
 * than zones is forced: the birth profile has no zone name to compare against,
 * only a number. It's a coarser test — it can't tell Chicago from Mexico City,
 * and it goes quiet for an unset user during half of a DST year — but its job is
 * only to decide whether to *ask*, and the answer it gives is never stored.
 */
export const locationPrompt = ({ location, birthOffset, zone, offset } = {}) => {
  if (!zone) return null;
  if (isZoneDismissed(zone)) return null;

  if (location?.timezone) {
    return location.timezone === zone ? null : { kind: "moved", zone };
  }
  if (!Number.isFinite(birthOffset) || !Number.isFinite(offset)) return null;
  return offset === birthOffset ? null : { kind: "unset", zone };
};
