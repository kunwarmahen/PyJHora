/**
 * A known chart's planets land in the right cells of both chart styles (§68.3).
 *
 * This is the guard §65/§66 wanted. The renderer once read the drawing position
 * out of a key called `house`, so for a while every chart put the Lagna's
 * occupants in "1" whatever the sign, and a D9 Sun sat in the 4th when it was in
 * the 12th. Nothing caught it because no test had ever mounted a chart.
 *
 * The chart below is deliberately hostile: every planet carries a `house` that
 * is WRONG for its sign, so a renderer that reads `house` instead of `sign_num`
 * puts every planet in the wrong cell and fails here.
 */
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react-dom/test-utils";
import "../i18n";
import { NorthIndianChart } from "./NorthIndianChart";
import { SouthIndianChart } from "./SouthIndianChart";

jest.mock("../contexts/SettingsContext", () => ({
  useSettings: () => ({ settings: { signLabel: "number", chartStyle: "north" } }),
}));

// Taurus Lagna (sign 2). Expected North house = sign counted from Taurus.
const LAGNA = { sign_num: 2, sign_name: "Taurus", degrees: 25.1, house: 1 };
const PLANETS = {
  Sun: { sign_num: 2, sign_name: "Taurus", degrees: 19.9, house: 7 }, //  1st
  Moon: { sign_num: 5, sign_name: "Leo", degrees: 8.2, house: 1 }, //     4th
  Saturn: { sign_num: 4, sign_name: "Cancer", degrees: 18.4, house: 9 }, // 3rd
  Jupiter: { sign_num: 1, sign_name: "Aries", degrees: 0.6, house: 2 }, //  12th
  Rahu: { sign_num: 7, sign_name: "Libra", degrees: 3.3, house: 11 }, //   6th
};
const ABBR = { Sun: "Su", Moon: "Mo", Saturn: "Sa", Jupiter: "Ju", Rahu: "Ra" };
const EXPECTED_HOUSE = { Sun: 1, Moon: 4, Saturn: 3, Jupiter: 12, Rahu: 6 };

beforeAll(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
});

const render = (el) => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  act(() => root.render(el));
  return {
    host,
    done: () => {
      act(() => root.unmount());
      host.remove();
    },
  };
};

// The chart abbreviations of every planet drawn inside `cell`.
const occupants = (cell) =>
  Object.entries(ABBR)
    .filter(([, abbr]) => (cell.textContent || "").includes(abbr))
    .map(([name]) => name)
    .sort();

describe("North Indian chart", () => {
  it("counts each planet's house from the Lagna's sign, never from `house`", () => {
    const { host, done } = render(<NorthIndianChart planets={PLANETS} lagna={LAGNA} />);
    try {
      for (let h = 1; h <= 12; h += 1) {
        const cell = host.querySelector(`g[data-house="${h}"]`);
        expect(cell).not.toBeNull();
        const want = Object.keys(EXPECTED_HOUSE)
          .filter((p) => EXPECTED_HOUSE[p] === h)
          .sort();
        expect([h, occupants(cell)]).toEqual([h, want]);
      }
    } finally {
      done();
    }
  });

  it("labels each house with the sign that sits there", () => {
    const { host, done } = render(<NorthIndianChart planets={PLANETS} lagna={LAGNA} />);
    try {
      // Taurus in the 1st, Aries in the 12th, Pisces in the 11th.
      expect(host.querySelector('g[data-house="1"]').getAttribute("data-sign")).toBe("2");
      expect(host.querySelector('g[data-house="12"]').getAttribute("data-sign")).toBe("1");
      expect(host.querySelector('g[data-house="11"]').getAttribute("data-sign")).toBe("12");
      // The Lagna marker is in the 1st house and nowhere else.
      const withAs = [...host.querySelectorAll("g[data-house]")].filter((g) =>
        g.textContent.includes("As")
      );
      expect(withAs.map((g) => g.getAttribute("data-house"))).toEqual(["1"]);
    } finally {
      done();
    }
  });
});

describe("South Indian chart", () => {
  it("puts each planet in its sign's fixed cell", () => {
    const { host, done } = render(<SouthIndianChart planets={PLANETS} lagna={LAGNA} />);
    try {
      for (let s = 1; s <= 12; s += 1) {
        const cell = host.querySelector(`[data-sign="${s}"]`);
        expect(cell).not.toBeNull();
        const want = Object.keys(PLANETS)
          .filter((p) => PLANETS[p].sign_num === s)
          .sort();
        expect([s, occupants(cell)]).toEqual([s, want]);
      }
      expect(host.querySelector('[data-sign="2"]').className).toContain("si-lagna");
    } finally {
      done();
    }
  });
});
