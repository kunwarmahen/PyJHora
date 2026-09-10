/**
 * §68.8 — the chart's text alternative.
 *
 * The kundali is the single most important thing in the app and, before this,
 * a screen reader announced it as "Rasi Chart, image" and stopped: `role="img"`
 * hides everything inside it, so the planets were unreachable. These assert the
 * label actually carries the chart.
 */
import { describeChart } from "./chartDescription";

// Stand-in for i18next's `t` — interpolation only, which is all this uses.
const t = (key, vars = {}) =>
  ({
    "chartA11y.ascendant": `Ascendant in ${vars.place}.`,
    "chartA11y.cell": `${vars.place}: ${vars.occupants}.`,
    "chartA11y.empty": `${vars.place}: empty.`,
  })[key] || key;

const cells = [
  { label: "Aries", items: ["Ascendant", "Sun", "Mercury"] },
  { label: "Taurus", items: [] },
  { label: "Gemini", items: ["Moon"] },
];

it("names the chart, the ascendant and every occupant", () => {
  const text = describeChart({
    title: "Rasi Chart",
    subtitle: "South Indian",
    ascendant: "Aries",
    cells,
    t,
  });
  expect(text).toBe(
    "Rasi Chart, South Indian. Ascendant in Aries. " +
      "Aries: Ascendant, Sun, Mercury. Taurus: empty. Gemini: Moon."
  );
});

it("says a house is empty rather than skipping it", () => {
  // Silence would read as "Taurus has something I failed to hear".
  const text = describeChart({ title: "D9", cells, t });
  expect(text).toContain("Taurus: empty.");
});

it("works without a lagna — the South grid is still correct without one", () => {
  const text = describeChart({ title: "D9", subtitle: "Navamsa", cells, t });
  expect(text.startsWith("D9, Navamsa.")).toBe(true);
  expect(text).not.toContain("Ascendant in");
});

it("holds every cell, so nothing is silently dropped", () => {
  const twelve = Array.from({ length: 12 }, (_, i) => ({ label: `Sign ${i + 1}`, items: [] }));
  const text = describeChart({ title: "Rasi", cells: twelve, t });
  twelve.forEach(({ label }) => expect(text).toContain(`${label}: empty.`));
});
