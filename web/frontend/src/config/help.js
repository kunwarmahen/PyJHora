/**
 * The Help / FAQ outline (§14).
 *
 * Structure lives here; the words live in the `help.*` i18n block, keyed by the
 * ids below. That split is what keeps the page maintainable: adding a question
 * is one id here plus `help.q.<id>` / `help.a.<id>` in en.json, and hi/sa fall
 * back to English automatically until someone translates them.
 *
 * `help.test.js` fails if an id here has no text, so a half-added entry can't
 * ship as a blank accordion row.
 *
 * Written for someone who has never read a chart before: no assumed jargon, and
 * every term that must appear is explained where it appears.
 */

/** Questions grouped by area. `to` turns an answer into a "take me there" link. */
export const HELP_SECTIONS = [
  {
    id: "start",
    items: [
      { id: "whatIsThis" },
      { id: "whatIsChart" },
      { id: "whyBirthTime" },
      { id: "noBirthTime", to: "/rectify" },
      { id: "whereToStart", to: "/birth-chart" },
      { id: "dashboardLayout", to: "/dashboard" },
      { id: "essentialsVsEverything", to: "/settings" },
      { id: "believe" },
    ],
  },
  {
    id: "reading",
    items: [
      { id: "whatAmILookingAt" },
      { id: "northVsSouth", to: "/settings" },
      { id: "whatIsHouse" },
      { id: "whatIsSign" },
      { id: "rasiVsNavamsa" },
      { id: "whatIsNakshatra", to: "/nakshatra" },
      { id: "yogaAndDosha" },
      { id: "retrograde" },
      { id: "conditionalDashas", to: "/dhasa" },
      { id: "whatIsKaalaVela", to: "/muhurta" },
    ],
  },
  {
    id: "features",
    items: [
      { id: "featBirthChart", to: "/birth-chart" },
      { id: "featToday", to: "/daily-digest" },
      { id: "featDasha", to: "/dhasa" },
      { id: "featTransit", to: "/transit" },
      { id: "featCompatibility", to: "/compatibility" },
      { id: "featLifeReport", to: "/life-report" },
      { id: "featRemedies", to: "/remedies" },
      { id: "featVarshaphal", to: "/varshaphal" },
      { id: "featAlmanac", to: "/almanac" },
      { id: "featMuhurta", to: "/muhurta" },
      { id: "featPrashna", to: "/prashna" },
      { id: "featSensitivePoints", to: "/sensitive-points" },
      { id: "featSpecialPoints", to: "/sensitive-points?tab=special" },
      { id: "featVedicClock", to: "/vedic-clock" },
      { id: "featRectify", to: "/rectify" },
      { id: "featLearn", to: "/learn" },
      { id: "featJournal", to: "/journal" },
      // The rest of the feature set, so every page in the app has an entry its
      // "?" can land on. help.test.js fails if a feature is ever added without
      // one, which is what keeps this tour complete.
      { id: "featNow", to: "/now" },
      { id: "featTimeline", to: "/timeline" },
      { id: "featStrength", to: "/strength" },
      { id: "featSadeSati", to: "/sade-sati" },
      { id: "featCompare", to: "/compare" },
      { id: "featGochara", to: "/gochara" },
      { id: "featBhava", to: "/bhava" },
      { id: "featEphemeris", to: "/ephemeris" },
      { id: "featReport", to: "/report" },
      { id: "featFortnightly", to: "/fortnightly-digest" },
      { id: "featMonthly", to: "/monthly-digest" },
      { id: "featTithiPravesha", to: "/tithi-pravesha" },
      { id: "featBhrigu", to: "/bhrigu-markers" },
      { id: "featNadi", to: "/nadi" },
      { id: "featPanchaPakshi", to: "/pancha-pakshi" },
      { id: "featChakras", to: "/chakras" },
      { id: "featKp", to: "/kp" },
      { id: "featJaimini", to: "/jaimini" },
      { id: "featAdvanced", to: "/advanced" },
    ],
  },
  {
    id: "ai",
    items: [
      { id: "aiWhatIsIt", to: "/ask-astrologer" },
      { id: "aiWhatItSees" },
      { id: "aiModes" },
      { id: "aiWhichModel", to: "/settings" },
      { id: "aiUnavailable", to: "/settings" },
      { id: "aiAccurate" },
      { id: "aiHistory", to: "/history" },
      // No `to` on this one on purpose: `aiHistory` above already resolves
      // /history, and a second entry claiming the same path makes the match
      // ambiguous — which would leave the History page's "?" with nowhere to go.
      { id: "aiDigestHistory" },
      { id: "digestCautions", to: "/daily-digest" },
    ],
  },
  {
    id: "privacy",
    items: [
      { id: "privWhatStored" },
      { id: "privSharing" },
      { id: "privKeys", to: "/settings" },
      { id: "privEmails", to: "/settings" },
      { id: "privDelete", to: "/settings" },
    ],
  },
];

/** Every question id, flattened — used by the tests and the search index. */
export const allHelpItemIds = () => HELP_SECTIONS.flatMap((s) => s.items.map((i) => i.id));

/**
 * The help anchor for a page, so its "?" can open the answer about *that* page
 * instead of the top of the FAQ.
 *
 * Derived from the `to` links already in the outline rather than declared again
 * per page — one list to keep correct, and a new feature gets a contextual "?"
 * the moment it's added to the tour.
 *
 * Resolution order:
 *  1. The feature tour, which is the "what does this page do?" answer and so the
 *     right landing spot when someone is confused about the page they're on.
 *  2. Failing that, a match anywhere else in the outline — but only if exactly
 *     one entry links to that path. `/ask-astrologer` is explained once in the
 *     AI section, so it resolves; `/settings` is referenced six times across
 *     privacy, AI and getting-started, and picking one arbitrarily would be
 *     worse than not jumping at all, so it returns null.
 */
export const helpAnchorForPath = (pathname) => {
  if (!pathname) return null;
  // Ignore any trailing slash and query/hash noise from the router.
  const path = pathname.replace(/[?#].*$/, "").replace(/\/+$/, "") || "/";

  const tour = HELP_SECTIONS.find((s) => s.id === "features");
  const tourHit = tour?.items.find((i) => i.to === path);
  if (tourHit) return tourHit.id;

  const everywhere = HELP_SECTIONS.flatMap((s) => s.items).filter((i) => i.to === path);
  return everywhere.length === 1 ? everywhere[0].id : null;
};

/** `/help#featDasha` for a page with an entry, plain `/help` otherwise. */
export const helpLinkForPath = (pathname) => {
  const anchor = helpAnchorForPath(pathname);
  return anchor ? `/help#${anchor}` : "/help";
};

/**
 * Filter the outline by a search string.
 *
 * `text(id)` resolves an id to its question + answer, so matching happens on
 * what the reader actually sees rather than on our internal ids. Sections with
 * no surviving items drop out entirely.
 */
export const filterHelp = (query, text, sections = HELP_SECTIONS) => {
  const q = (query || "").trim().toLowerCase();
  if (!q) return sections;
  return sections
    .map((s) => ({
      ...s,
      items: s.items.filter((i) => (text(i.id) || "").toLowerCase().includes(q)),
    }))
    .filter((s) => s.items.length > 0);
};
