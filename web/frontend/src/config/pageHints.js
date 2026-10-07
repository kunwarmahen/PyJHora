import { helpAnchorForPath } from "./help";
import { isNewcomer } from "./checklist";

/**
 * One-line "What am I looking at?" hints (§76.5).
 *
 * No new copy per page: the hint is the first sentence of the page's own
 * Help/FAQ answer, found through the same route→entry map the "?" button uses
 * (help.js `helpAnchorForPath`). A page with no entry gets no hint.
 *
 * `pageHints` (synced): "auto" (default) shows them to accounts younger than
 * NEWCOMER_DAYS, so a long-time user isn't suddenly lectured; "on" / "off" is an
 * explicit choice from Settings. `hintsSeen` (synced) lists the paths whose hint
 * was dismissed — remembered per page, on every device.
 */

/** Paths as stored: no query/hash, no trailing slash. */
export const hintPath = (pathname) =>
  (pathname || "").replace(/[?#].*$/, "").replace(/\/+$/, "") || "/";

export const parseSeen = (value) =>
  new Set(
    String(value || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
  );

export const hintsEnabled = (mode, createdAt, now) =>
  mode === "on" || (mode !== "off" && isNewcomer(createdAt, now));

/**
 * The opening of a help answer — the first sentence, or the first two when the
 * first is too short to say anything on its own ("The best first stop." was the
 * whole hint for Start here until this learned to keep going).
 */
export const MIN_HINT_CHARS = 60;
export const firstSentence = (text) => {
  const s = String(text || "").trim();
  // "।" (danda) ends a Hindi sentence; without it a Hindi answer was one long "sentence".
  const sentences = s.match(/[^.!?।]+[.!?।]+(\s|$)/g);
  if (!sentences) return s;
  let out = sentences[0].trim();
  if (out.length < MIN_HINT_CHARS && sentences[1]) out = `${out} ${sentences[1].trim()}`;
  return out;
};

/** The help entry id a page's hint comes from, or null. */
export const hintIdFor = (pathname) => helpAnchorForPath(hintPath(pathname));
