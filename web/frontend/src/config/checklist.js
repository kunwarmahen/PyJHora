/**
 * The newcomer's first week (§76.4) — four things worth doing once, shown as a
 * dismissable card on the dashboard instead of a product tour.
 *
 * Progress is the synced `onboardingChecklist` preference (a comma list), so
 * ticking something on a phone ticks it on the laptop. Each item is ticked by
 * the page where it actually happens — never by visiting the card — so the card
 * reports what was done, not what was clicked:
 *
 *   chart   StartPage, once the plain-words reading has loaded
 *   ask     AskAstrologerPage, when a question is sent
 *   digest  SettingsPage, when the daily digest is on (toggled or already on)
 *   learn   LearnChartPage, when a quiz has been graded
 *
 * `dismissed` is stored in the same list, so "hide this" also follows the user.
 */
export const CHECKLIST = [
  { key: "chart", to: "/start" },
  { key: "ask", to: "/ask-astrologer" },
  { key: "digest", to: "/settings?tab=notifications" },
  { key: "learn", to: "/learn" },
];

const DISMISSED = "dismissed";
const KNOWN = new Set([...CHECKLIST.map((i) => i.key), DISMISSED]);

/** "chart,ask" → Set{"chart","ask"}; unknown words are dropped. */
export const parseChecklist = (value) =>
  new Set(
    String(value || "")
      .split(",")
      .map((s) => s.trim())
      .filter((s) => KNOWN.has(s))
  );

/** Set → canonical string (checklist order, dismissed last) so it diffs cleanly. */
export const serializeChecklist = (set) =>
  [...CHECKLIST.map((i) => i.key), DISMISSED].filter((k) => set.has(k)).join(",");

// Only newcomers see it: an account that has been around for months does not need
// to be told to look at its own chart, and the card appearing for everyone the
// day it shipped would read as nagging.
export const NEWCOMER_DAYS = 14;

/** Is an account created at `createdAt` (ISO string) still new at `now`? */
export const isNewcomer = (createdAt, now = new Date()) => {
  const t = Date.parse(createdAt || "");
  return Number.isFinite(t) && now.getTime() - t < NEWCOMER_DAYS * 24 * 60 * 60 * 1000;
};

/** Should the dashboard show the card? Not once dismissed, not once complete. */
export const checklistVisible = (set) =>
  !set.has(DISMISSED) && !CHECKLIST.every((i) => set.has(i.key));
