#!/usr/bin/env node
/**
 * Generates src/constants/nameLocales.generated.js — the English -> hi/sa lookup
 * tables for engine-returned names (rasis, nakshatras, grahas) and their chart
 * abbreviations.
 *
 * Run: node scripts/gen-name-locales.js   (or `npm run gen:names`)
 *
 * Hindi full names are read out of PyJHora's own src/jhora/lang/list_values_hi.txt so
 * they stay in sync with upstream. Everything upstream can't supply — all of Sanskrit,
 * and the rasi/graha abbreviations in both languages — is hand-authored in
 * scripts/name-locales.manual.json.
 *
 * WHY THIS IS GENERATED RATHER THAN HAND-WRITTEN
 * ---------------------------------------------
 * The tables are keyed by the backend's canonical English names, but they CANNOT be
 * built by matching English to English: PyJHora's list_values_en.txt uses the Tamil
 * naming tradition ("Karthigai", "Poosam", "Thiruvaathirai") while our backend uses
 * the Sanskrit one ("Krittika", "Pushya", "Ardra"). The two vocabularies share no
 * strings. The only correspondence is POSITIONAL — both lists are in canonical order,
 * so index i means the same nakshatra in either. That makes the mapping correct but
 * fragile: an off-by-one would silently relabel every name with nothing looking
 * broken, which is exactly why a script owns it and the canonical lists below are
 * asserted against the backend's.
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..", "..", "..");
const HI_LANG_FILE = path.join(ROOT, "src", "jhora", "lang", "list_values_hi.txt");
const MANUAL_FILE = path.join(__dirname, "name-locales.manual.json");
const OUT_FILE = path.resolve(__dirname, "..", "src", "constants", "nameLocales.generated.js");

// Canonical English keys. These MUST stay identical to the backend's tables in
// web/backend/astrology/engine.py (ZODIAC_NAMES, NAKSHATRA_NAMES, PLANET_NAMES) —
// they are the join key for every lookup at render time.
const EN_RASIS = [
  "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
  "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
];

const EN_NAKSHATRAS = [
  "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
  "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
  "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
  "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
  "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
];

const EN_GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"];

// English chart-cell abbreviations. These are canonical display data in their own right
// (constants/jyotish.js re-exports them, which is why they live here rather than there —
// one source of truth for names in every language).
const EN_RASIS_ABBR = ["Ar", "Ta", "Ge", "Cn", "Le", "Vi", "Li", "Sc", "Sg", "Cp", "Aq", "Pi"];
const EN_GRAHAS_ABBR = ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"];
const EN_NAKSHATRAS_ABBR = [
  "Asw", "Bha", "Kri", "Roh", "Mrig", "Ardr", "Puna", "Push", "Asre",
  "Magh", "PPha", "UPha", "Hast", "Chit", "Swat", "Visa", "Anu", "Jye",
  "Mool", "PSha", "USha", "Srav", "Dhan", "Sat", "PBha", "UBha", "Rev",
];

/** Strip the astrological glyphs upstream bakes into its labels ("♈︎मेष", "सूर्य☉"). */
function stripGlyphs(s) {
  return s
    .replace(/[☀-➿︎️]/g, "")
    .trim();
}

/** Pull one KEY=a,b,c list out of a list_values_*.txt file. */
function readList(text, key) {
  const line = text.split(/\r?\n/).find((l) => l.startsWith(`${key}=`));
  if (!line) throw new Error(`${key} not found in ${HI_LANG_FILE}`);
  return line.slice(key.length + 1).split(",").map(stripGlyphs);
}

/** Build {english: translated} for one kind, failing loudly on a length mismatch. */
function zip(kind, enNames, localized, lang) {
  if (localized.length < enNames.length) {
    throw new Error(
      `${lang}/${kind}: expected at least ${enNames.length} names, got ${localized.length}. ` +
      `Refusing to emit a table that would mis-key every lookup.`
    );
  }
  const out = {};
  enNames.forEach((en, i) => {
    const name = localized[i];
    if (!name) throw new Error(`${lang}/${kind}: empty name at index ${i} (English "${en}")`);
    out[en] = name;
  });
  return out;
}

const hiText = fs.readFileSync(HI_LANG_FILE, "utf8");
const manual = JSON.parse(fs.readFileSync(MANUAL_FILE, "utf8"));

// Upstream's planet list runs to 12 (it includes the outer planets) and its
// nakshatra list to 28 (it appends Abhijit); we key off our own 9 and 27, so the
// tails are simply not read.
const tables = {
  // `en` maps each canonical name to itself, so localizeName() needs no special case for
  // English and callers never have to fall back by hand — only the abbreviations differ.
  en: {
    rasis: zip("rasis", EN_RASIS, EN_RASIS, "en"),
    nakshatras: zip("nakshatras", EN_NAKSHATRAS, EN_NAKSHATRAS, "en"),
    grahas: zip("grahas", EN_GRAHAS, EN_GRAHAS, "en"),
    rasisAbbr: zip("rasisAbbr", EN_RASIS, EN_RASIS_ABBR, "en"),
    nakshatrasAbbr: zip("nakshatrasAbbr", EN_NAKSHATRAS, EN_NAKSHATRAS_ABBR, "en"),
    grahasAbbr: zip("grahasAbbr", EN_GRAHAS, EN_GRAHAS_ABBR, "en"),
  },
  hi: {
    rasis: zip("rasis", EN_RASIS, readList(hiText, "RAASI_LIST"), "hi"),
    nakshatras: zip("nakshatras", EN_NAKSHATRAS, readList(hiText, "NAKSHATRA_LIST"), "hi"),
    grahas: zip("grahas", EN_GRAHAS, readList(hiText, "PLANET_NAMES"), "hi"),
    // Upstream's short list covers nakshatras only; rasis/grahas come from manual.
    nakshatrasAbbr: zip("nakshatrasAbbr", EN_NAKSHATRAS, readList(hiText, "NAKSHATRA_SHORT_LIST"), "hi"),
    rasisAbbr: zip("rasisAbbr", EN_RASIS, manual.abbr.hi.rasis, "hi"),
    grahasAbbr: zip("grahasAbbr", EN_GRAHAS, manual.abbr.hi.grahas, "hi"),
  },
  sa: {
    rasis: zip("rasis", EN_RASIS, manual.sa.rasis, "sa"),
    nakshatras: zip("nakshatras", EN_NAKSHATRAS, manual.sa.nakshatras, "sa"),
    grahas: zip("grahas", EN_GRAHAS, manual.sa.grahas, "sa"),
    // No Sanskrit short list upstream either; reuse Hindi's nakshatra abbreviations,
    // which are the same aksharas, and take rasis/grahas from manual.
    nakshatrasAbbr: zip("nakshatrasAbbr", EN_NAKSHATRAS, readList(hiText, "NAKSHATRA_SHORT_LIST"), "sa"),
    rasisAbbr: zip("rasisAbbr", EN_RASIS, manual.abbr.sa.rasis, "sa"),
    grahasAbbr: zip("grahasAbbr", EN_GRAHAS, manual.abbr.sa.grahas, "sa"),
  },
};

const banner = `// @generated by scripts/gen-name-locales.js — DO NOT EDIT BY HAND.
// Hindi full names are derived from PyJHora's src/jhora/lang/list_values_hi.txt; all of
// Sanskrit and the rasi/graha abbreviations come from scripts/name-locales.manual.json.
// Re-run \`npm run gen:names\` after changing either.
//
// Keys are the backend's canonical English names (astrology/engine.py). A missing key
// is not an error — localizeName() falls back to the English input.
`;

// Canonical English names in engine order (0 = Aries / Ashwini / Sun). Exported so
// index-based callers (RASI_NAMES[sign - 1] and friends) have one source of truth.
const order = { rasis: EN_RASIS, nakshatras: EN_NAKSHATRAS, grahas: EN_GRAHAS };

fs.writeFileSync(
  OUT_FILE,
  `${banner}
export const NAME_ORDER = ${JSON.stringify(order, null, 2)};

const NAME_LOCALES = ${JSON.stringify(tables, null, 2)};

export default NAME_LOCALES;
`,
  "utf8"
);

console.log(`Wrote ${path.relative(process.cwd(), OUT_FILE)}`);
for (const [lang, kinds] of Object.entries(tables)) {
  const counts = Object.entries(kinds).map(([k, v]) => `${k}=${Object.keys(v).length}`).join(" ");
  console.log(`  ${lang}: ${counts}`);
}
