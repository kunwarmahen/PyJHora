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
      { id: "featVedicClock", to: "/vedic-clock" },
      { id: "featRectify", to: "/rectify" },
      { id: "featLearn", to: "/learn" },
      { id: "featJournal", to: "/journal" },
    ],
  },
  {
    id: "ai",
    items: [
      { id: "aiWhatIsIt", to: "/ask-astrologer" },
      { id: "aiWhatItSees" },
      { id: "aiModes" },
      { id: "aiWhichModel", to: "/settings" },
      { id: "aiAccurate" },
      { id: "aiHistory", to: "/history" },
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
