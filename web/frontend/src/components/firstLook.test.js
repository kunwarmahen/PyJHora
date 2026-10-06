/**
 * The plain-words page never states what the birth time can't support (§76.3).
 * The backend flags it (get_first_look); this pins that the page listens.
 */
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react-dom/test-utils";
import "../i18n";
import { FirstLook } from "./FirstLook";

jest.mock("../contexts/SettingsContext", () => ({
  useSettings: () => ({ settings: { language: "en" } }),
}));

beforeAll(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
});

const CHAPTER = {
  maha: { lord: "Rahu", start_date: "2026-01-12", end_date: "2044-01-12" },
  antar: { lord: "Rahu", start_date: "2026-01-12", end_date: "2028-09-26" },
  next_antar: { lord: "Jupiter", start_date: "2028-09-26", end_date: "2031-02-17" },
};
const EXACT = {
  rising: { sign_num: 2, sign_name: "Taurus", degrees: 25.1, near_edge: false },
  moon: {
    sign_num: 5,
    sign_name: "Leo",
    nakshatra: "Magha",
    nakshatra_index: 10,
    pada: 1,
    sign_certain: true,
    star_certain: true,
  },
  chapter: { ...CHAPTER, approximate: false },
};
// 1976-06-04 with no time: the Moon went Cancer→Leo and Ashlesha→Magha that day.
const UNKNOWN = {
  rising: null,
  moon: {
    sign_num: 5,
    sign_name: "Leo",
    nakshatra: "Magha",
    nakshatra_index: 10,
    pada: 2,
    sign_certain: false,
    star_certain: false,
    day_range: {
      start: { sign_name: "Cancer", nakshatra: "Ashlesha" },
      end: { sign_name: "Leo", nakshatra: "Magha" },
    },
  },
  chapter: { ...CHAPTER, approximate: true },
};

const render = (data) => {
  const host = document.createElement("div");
  const root = createRoot(host);
  act(() => root.render(<FirstLook data={data} />));
  const text = host.textContent;
  act(() => root.unmount());
  return text;
};

describe("FirstLook", () => {
  it("states the signs, star and chapter for an exact time", () => {
    const text = render(EXACT);
    expect(text).toContain("Taurus");
    expect(text).toContain("Leo");
    expect(text).toContain("Magha");
    expect(text).toContain("Rahu period");
    expect(text).toContain("Jupiter");
  });

  it("names none of what an unknown time leaves open", () => {
    const text = render(UNKNOWN);
    expect(text).not.toContain("Taurus"); // no Rising sign
    expect(text).toContain("from Cancer to Leo"); // the Moon's two candidates, not one
    expect(text).toContain("from Ashlesha to Magha");
    // The dasha lord hangs off the star — no period may be named.
    expect(text).not.toContain("Rahu period");
    expect(text).not.toContain("Jupiter");
    expect(text).toContain("counted from your birth star");
  });
});
