// The name tables are built by matching the backend's list to PyJHora's by POSITION
// (the two use different naming traditions, so there is no string to join on — see
// scripts/gen-name-locales.js). An off-by-one there would relabel every name with
// nothing appearing broken, so these anchors check known-correct pairs at the start,
// middle and end of each list rather than trusting the counts alone.

import { localizeName } from "./localizeName";

describe("localizeName", () => {
  describe("hi (from PyJHora's list_values_hi.txt)", () => {
    it.each([
      ["Aries", "मेष"],
      ["Cancer", "कर्क"],
      ["Pisces", "मीन"],
    ])("maps rasi %s", (en, hi) => {
      expect(localizeName(en, "rasi", "hi")).toBe(hi);
    });

    it.each([
      ["Ashwini", "अश्विनि"],
      ["Krittika", "कृत्तिका"],
      ["Magha", "मघा"],
      ["Revati", "रेवती"],
    ])("maps nakshatra %s", (en, hi) => {
      expect(localizeName(en, "nakshatra", "hi")).toBe(hi);
    });

    it.each([
      ["Sun", "सूर्य"],
      ["Jupiter", "बृहस्पति"],
      ["Ketu", "केतु"],
    ])("maps graha %s", (en, hi) => {
      expect(localizeName(en, "graha", "hi")).toBe(hi);
    });

    it("strips the astrological glyphs upstream bakes into its labels", () => {
      // list_values_hi.txt stores "♈︎मेष" and "सूर्य☉".
      expect(localizeName("Aries", "rasi", "hi")).not.toMatch(/[♈☉]/);
      expect(localizeName("Sun", "graha", "hi")).not.toMatch(/[♈☉]/);
    });
  });

  describe("sa (hand-authored)", () => {
    it.each([
      ["Aquarius", "कुम्भ"],
      ["Sagittarius", "धनुस्"],
    ])("uses Sanskrit spelling for rasi %s", (en, sa) => {
      expect(localizeName(en, "rasi", "sa")).toBe(sa);
    });

    it("uses Sanskrit spelling for grahas", () => {
      expect(localizeName("Moon", "graha", "sa")).toBe("चन्द्र");
      expect(localizeName("Moon", "graha", "hi")).toBe("चंद्रमा");
    });
  });

  describe("abbreviations", () => {
    it("returns the compact chart-cell form", () => {
      expect(localizeName("Sun", "graha", "hi", { abbr: true })).toBe("सू");
      expect(localizeName("Krittika", "nakshatra", "hi", { abbr: true })).toBe("कृत्त");
    });

    it("keeps colliding rasis distinguishable", () => {
      // मेष/मीन and वृषभ/वृश्चिक would collide at a single akshara.
      const abbr = (en) => localizeName(en, "rasi", "hi", { abbr: true });
      expect(abbr("Aries")).not.toBe(abbr("Pisces"));
      expect(abbr("Taurus")).not.toBe(abbr("Scorpio"));
    });
  });

  describe("fallbacks", () => {
    it("returns English unchanged for en", () => {
      expect(localizeName("Krittika", "nakshatra", "en")).toBe("Krittika");
    });

    it("returns the input for an unmapped name", () => {
      expect(localizeName("Abhijit", "nakshatra", "hi")).toBe("Abhijit");
    });

    it("returns the input for an unknown language or kind", () => {
      expect(localizeName("Aries", "rasi", "ta")).toBe("Aries");
      expect(localizeName("Aries", "tithi", "hi")).toBe("Aries");
    });

    it("handles region variants like hi-IN", () => {
      expect(localizeName("Aries", "rasi", "hi-IN")).toBe("मेष");
    });

    it("passes through empty and non-string input", () => {
      expect(localizeName("", "rasi", "hi")).toBe("");
      expect(localizeName(null, "rasi", "hi")).toBeNull();
      expect(localizeName(undefined, "rasi", "hi")).toBeUndefined();
    });

    it("tolerates surrounding whitespace", () => {
      expect(localizeName(" Aries ", "rasi", "hi")).toBe("मेष");
    });
  });
});
