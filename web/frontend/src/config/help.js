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

/**
 * Questions grouped by area. `to` turns an answer into a "take me there" link.
 * `keywords` are extra English search terms the answer doesn't say itself —
 * spellings (vimshottari/vimsottari) and the specific names a reader types
 * (gajakesari, d10) — so the search finds the answer that covers them.
 */
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
      // §79 hubs. No `to`: it answers "where is X" for every page at once, and
      // /dashboard is already dashboardLayout's.
      {
        id: "whereIsPage",
        keywords:
          "missing moved gone menu hub hubs group grouped find page where strip my chart your periods" +
          " other systems reports transits sky panchanga notebook",
      },
      { id: "essentialsVsEverything", to: "/settings" },
      {
        id: "languageAndTheme",
        to: "/settings",
        keywords: "language hindi sanskrit english translate dark mode light mode night theme",
      },
      // No `to`: offline is how the whole app behaves, not somewhere to go.
      { id: "offline" },
      { id: "accessibility" },
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
      {
        id: "whatIsVarga",
        to: "/birth-chart?tab=advanced",
        keywords:
          "divisional varga vargas shodasavarga d2 d3 d4 d7 d10 d12 d16 d20 d24 d27 d30 d40 d45 d60" +
          " hora drekkana saptamsa dasamsa dashamsa dwadasamsa trimsamsa shashtyamsa",
      },
      { id: "whatIsNakshatra", to: "/nakshatra" },
      {
        id: "yogaAndDosha",
        to: "/birth-chart?tab=yogas",
        keywords:
          "raja yoga rajayoga dhana yoga gajakesari pancha mahapurusha budhaditya neechabhanga viparita" +
          " kaal sarp kala sarpa kalasarpa mangal manglik kuja pitru guru chandal combinations",
      },
      { id: "whatIsArudha", to: "/transit" },
      { id: "retrograde" },
      {
        id: "whatIsAyanamsa",
        to: "/settings",
        keywords:
          "ayanamsa ayanamsha lahiri true chitra citra raman krishnamurti sidereal tropical" +
          " jagannatha hora jhora mean nodes true nodes rahu ketu different results",
      },
      {
        id: "conditionalDashas",
        to: "/dhasa",
        keywords:
          "yogini narayana kalachakra kaalachakra sudarshana sudarsana chara sthira drig trikona sudasa" +
          " shodasottari dwadasottari panchottari shatabdika shashtihayani dwisatpathi",
      },
      { id: "whatIsKaalaVela", to: "/muhurta" },
      { id: "personalMuhurta", to: "/muhurta" },
      { id: "whatIsLagnaShuddhi", to: "/muhurta" },
    ],
  },
  {
    id: "features",
    items: [
      // In hub order (§79, config/features.js HUBS) so the tour reads the way
      // the drawer does. Every page keeps its own entry — its "?" lands here,
      // and help.test.js fails if a feature is ever added without one.
      // ── My Chart ──
      {
        id: "featBirthChart",
        to: "/birth-chart",
        keywords: "kundali horoscope rasi d1 aspects aspect drishti graha drishti tabs",
      },
      { id: "featBhava", to: "/bhava" },
      {
        id: "featStrength",
        to: "/strength",
        keywords: "vimsopaka vimshopaka shadbala bhava bala ishta kashta",
      },
      {
        id: "featAdvanced",
        to: "/advanced",
        keywords:
          "deep dive ashtakavarga sarvashtakavarga bhinnashtakavarga bindu bindus longevity ayu ayurdaya" +
          " avastha avasthas planetary conditions combust combustion friendship friendships maitri",
      },
      { id: "featSensitivePoints", to: "/sensitive-points" },
      {
        id: "featSpecialPoints",
        to: "/sensitive-points?tab=special",
        keywords: "mandi maandi gulika upagraha indu lagna hora lagna ghati lagna",
      },
      // ── Your Periods ──
      { id: "featToday", to: "/daily-digest" },
      { id: "featFortnightly", to: "/fortnightly-digest" },
      { id: "featMonthly", to: "/monthly-digest" },
      {
        id: "featVarshaphal",
        to: "/varshaphal",
        keywords: "muntha tajaka solar return year lord varsha annual",
      },
      { id: "featTithiPravesha", to: "/tithi-pravesha" },
      // ── Other Systems ──
      {
        id: "featJaimini",
        to: "/jaimini",
        keywords: "chara karaka atmakaraka amatyakaraka darakaraka karakamsa swamsa",
      },
      {
        id: "featKp",
        to: "/kp",
        keywords: "krishnamurti sub lord significator ruling planets horary 249",
      },
      { id: "featNadi", to: "/nadi" },
      { id: "featBhrigu", to: "/bhrigu-markers" },
      {
        id: "featChakras",
        to: "/chakras",
        keywords: "kaala chakra kala chakra kota tripataki vedha",
      },
      // ── Reports ──
      { id: "featLifeReport", to: "/life-report" },
      { id: "featReport", to: "/report", keywords: "export download save pdf print" },
      {
        id: "featPredictions",
        to: "/predictions",
        keywords:
          "prediction predictions topic career job health relationships marriage focused reading",
      },
      // ── Dasha & Timeline ──
      {
        id: "featDasha",
        to: "/dhasa",
        keywords:
          "vimshottari vimsottari mahadasha antardasha bhukti pratyantardasha pratyantar sookshma",
      },
      { id: "featTimeline", to: "/timeline" },
      // ── Transits ──
      { id: "featTransit", to: "/transit" },
      { id: "featNakshatraGochara", to: "/transit" },
      { id: "featGochara", to: "/gochara" },
      { id: "featSadeSati", to: "/sade-sati" },
      { id: "featEphemeris", to: "/ephemeris" },
      // ── Sky & Panchanga ──
      { id: "featAlmanac", to: "/almanac" },
      { id: "featVedicClock", to: "/vedic-clock" },
      { id: "featPanchaPakshi", to: "/pancha-pakshi" },
      { id: "featNow", to: "/now" },
      // ── Standalone tools ──
      { id: "featMuhurta", to: "/muhurta" },
      // ── Relationships ──
      {
        id: "featCompatibility",
        to: "/compatibility",
        keywords:
          "marriage match guna milan ashtakoot dashakoota porutham mangal dosha manglik kuja 7th seventh house",
      },
      { id: "featCompare", to: "/compare" },
      // ── Remedies & practice ──
      { id: "featRemedies", to: "/remedies" },
      { id: "featPrashna", to: "/prashna" },
      { id: "featJournal", to: "/journal" },
      // ── Practice ──
      { id: "featLearn", to: "/learn" },
      { id: "featRectify", to: "/rectify" },
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
      { id: "aiCitations" },
      { id: "aiCorrectionNote" },
      { id: "aiHistory", to: "/history" },
      // Long answers + leaving the page (§77). No `to`: the pill it describes is
      // on every page, and /history is already aiHistory's.
      { id: "aiLongWait" },
      // No `to` on this one on purpose: `aiHistory` above already resolves
      // /history, and a second entry claiming the same path makes the match
      // ambiguous — which would leave the History page's "?" with nowhere to go.
      { id: "aiDigestHistory" },
      // "Did this land?" (§68.7) — no `to`, same reason as aiDigestHistory: the
      // control lives on /history, which aiHistory already claims.
      { id: "aiDidThisLand" },
      { id: "aiTrackRecord" },
      { id: "aiYourData", to: "/journal" },
      { id: "digestCautions", to: "/daily-digest" },
      { id: "digestTaraBala" },
      { id: "digestWindowOverlap" },
      { id: "digestReadingShape" },
      { id: "eventAlerts", to: "/timeline?tab=upcoming" },
    ],
  },
  {
    id: "privacy",
    items: [
      { id: "privWhatStored" },
      { id: "privSharing" },
      {
        id: "privAiProviders",
        to: "/settings?tab=ai",
        keywords:
          "gemini openai openrouter cloud hosted external send withheld redact anonymous birth date time place training",
      },
      { id: "privKeys", to: "/settings" },
      { id: "privEmails", to: "/settings" },
      { id: "privDelete", to: "/settings" },
      {
        id: "calendarFeed",
        to: "/settings",
        keywords: "calendar feed subscribe ical ics google calendar apple outlook",
      },
      {
        id: "apiAccess",
        to: "/settings",
        keywords: "api token tokens mcp claude desktop script developer programmatic",
      },
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

/** Split a query into lower-case words; every word must match somewhere. */
const queryTokens = (query) => (query || "").trim().toLowerCase().split(/\s+/).filter(Boolean);

/**
 * Filter the outline by a search string.
 *
 * `text(id)` resolves an id to its question + answer, so matching happens on
 * what the reader actually sees rather than on our internal ids, plus the
 * item's `keywords`. Each word of the query must appear, in any order ("raja
 * yoga" and "yoga raja" both work). Sections with no surviving items drop out
 * entirely.
 */
export const filterHelp = (query, text, sections = HELP_SECTIONS) => {
  const tokens = queryTokens(query);
  if (!tokens.length) return sections;
  return sections
    .map((s) => ({
      ...s,
      items: s.items.filter((i) => {
        const hay = `${text(i.id) || ""} ${i.keywords || ""}`.toLowerCase();
        return tokens.every((tok) => hay.includes(tok));
      }),
    }))
    .filter((s) => s.items.length > 0);
};

/** Glossary entries ([term, definition]) matching the query, same word rules. */
export const filterGlossary = (query, glossary) => {
  const entries = Object.entries(glossary);
  const tokens = queryTokens(query);
  if (!tokens.length) return entries;
  return entries.filter(([term, def]) => {
    const hay = `${term} ${def}`.toLowerCase();
    return tokens.every((tok) => hay.includes(tok));
  });
};
