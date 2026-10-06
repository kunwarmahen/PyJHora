import { CORRECTION_HEADER, splitCorrection } from "./claimCorrection";

const fs = require("fs");
const path = require("path");

// Verbatim output of backend `claim_check.annotation` appended to an answer.
const ANSWER =
  "Your Sun is strong.\n\n---\n\n**⚠ Checked against the computed chart — 1 statement does not match**\n\n- The reading says *“Sun is in the 10th house”* — in this chart, **Sun is in the 11th house (Virgo)**.\n\nThese were flagged automatically by comparing the reading with the computed chart. Where they disagree, the chart is right.";

describe("claim-check correction", () => {
  test("is lifted out of the answer so it can lead it", () => {
    const { body, correction } = splitCorrection(ANSWER);
    expect(body).toBe("Your Sun is strong.");
    expect(correction.startsWith(`**${CORRECTION_HEADER}`)).toBe(true);
    expect(correction).toMatch(/11th house \(Virgo\)/);
  });

  test("a clean answer, or a rule without the header, is left alone", () => {
    expect(splitCorrection("Plain.\n\n---\n\nMore.")).toEqual({
      body: "Plain.\n\n---\n\nMore.",
      correction: null,
    });
    expect(splitCorrection(undefined).correction).toBeNull();
  });

  test("the header matches the backend's", () => {
    const py = fs.readFileSync(path.join(__dirname, "../../../backend/claim_check.py"), "utf8");
    expect(py).toContain(`CORRECTION_HEADER = "${CORRECTION_HEADER}"`);
  });

  test("the shared Markdown wrapper renders it", () => {
    const src = fs.readFileSync(path.join(__dirname, "Markdown.js"), "utf8");
    expect(src).toMatch(/splitCorrection/);
  });
});
