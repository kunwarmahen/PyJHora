import { SIGN_LABEL_DEFAULT, SIGN_LABEL_MODES, signLabelParts } from "./signLabel";
import { RASI_GLYPHS, RASI_NAMES } from "../constants/jyotish";

describe("signLabelParts", () => {
  it.each(SIGN_LABEL_MODES)("renders at least one part in %s mode", (mode) => {
    // The reason this is one 4-value setting and not three toggles: no reachable
    // state may leave a house with no sign label at all.
    const parts = signLabelParts(mode);
    expect(Object.values(parts).some(Boolean)).toBe(true);
  });

  it("maps each mode to exactly the parts it names", () => {
    expect(signLabelParts("number")).toEqual({ number: true, glyph: false, abbr: false });
    expect(signLabelParts("glyph")).toEqual({ number: false, glyph: true, abbr: false });
    expect(signLabelParts("number_glyph")).toEqual({ number: true, glyph: true, abbr: false });
    expect(signLabelParts("abbr")).toEqual({ number: false, glyph: false, abbr: true });
  });

  it("falls back to the default rather than blanking the chart", () => {
    // A junk value reaches here from localStorage, which any user can edit and
    // an older build may have written. Unlabelled houses is the worst outcome.
    [undefined, null, "", "house_number", "1"].forEach((junk) => {
      expect(signLabelParts(junk)).toEqual(signLabelParts(SIGN_LABEL_DEFAULT));
    });
  });
});

describe("RASI_GLYPHS", () => {
  it("has one glyph per sign", () => {
    expect(RASI_GLYPHS).toHaveLength(RASI_NAMES.length);
  });

  it("uses the zodiac block, not lookalikes from elsewhere", () => {
    RASI_GLYPHS.forEach((g, i) => {
      expect(g.codePointAt(0)).toBe(0x2648 + i); // U+2648 Aries … U+2653 Pisces
    });
  });

  it("pins every glyph to text presentation", () => {
    // Without the U+FE0E suffix these render as colour emoji badges wherever an
    // emoji font is installed — observed in Chromium on Linux, where the chart
    // labels came out as little coloured circles instead of inheriting the
    // label's colour. The selector is invisible, so nothing but a test notices
    // if a reformat or a careless edit drops it.
    RASI_GLYPHS.forEach((g) => {
      expect(Array.from(g)).toHaveLength(2);
      expect(g.codePointAt(1)).toBe(0xfe0e);
    });
  });
});
