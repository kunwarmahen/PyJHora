/**
 * How a rasi is labelled inside a chart house.
 *
 * The numeral in a North Indian house is, by convention, the RASI number
 * (1 = Aries … 12 = Pisces) — the house is never numbered because the geometry
 * fixes it (top diamond = 1st house, always). We used to print the house number
 * there instead, which readers correctly read as a sign number and reported as
 * a bug. Hence: the numeral is the sign, and the only question left is how much
 * else to show alongside it.
 *
 * Kept out of SettingsContext (which pulls in axios via the api service, and
 * with it a module graph jest can't transform) so the mapping stays directly
 * unit-testable — same reasoning as uiMode.js.
 */

export const SIGN_LABEL_STORAGE_KEY = "sign_label";

/**
 * Number + glyph by default: the numeral satisfies the convention, and the
 * glyph makes it self-evidently a zodiac sign to a reader who hasn't memorised
 * the numbering. Neither depends on the UI language.
 */
export const SIGN_LABEL_DEFAULT = "number_glyph";

export const SIGN_LABEL_MODES = ["number", "glyph", "number_glyph", "abbr"];

/**
 * Which pieces a mode renders. One setting with four values rather than
 * independent number/glyph/abbr toggles: the toggles would allow "none", i.e.
 * a chart of unlabelled houses.
 */
const PARTS = {
  number: { number: true, glyph: false, abbr: false },
  glyph: { number: false, glyph: true, abbr: false },
  number_glyph: { number: true, glyph: true, abbr: false },
  abbr: { number: false, glyph: false, abbr: true },
};

/** Parts for `mode`, falling back to the default for anything unrecognised. */
export const signLabelParts = (mode) => PARTS[mode] || PARTS[SIGN_LABEL_DEFAULT];
