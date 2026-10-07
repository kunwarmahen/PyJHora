/**
 * The newcomer's first minute (§76): the checklist, the page hints, and the
 * landing-page handoff. Pure logic — the pages themselves are mounted by
 * pages/pages.smoke.test.js.
 */
import {
  CHECKLIST,
  NEWCOMER_DAYS,
  checklistVisible,
  isNewcomer,
  parseChecklist,
  serializeChecklist,
} from "./checklist";
import { firstSentence, hintIdFor, hintPath, hintsEnabled, parseSeen } from "./pageHints";
import { sanitizeHandoff } from "./previewHandoff";
import en from "../i18n/locales/en.json";
import hi from "../i18n/locales/hi.json";

const NOW = new Date("2026-10-06T12:00:00Z");
const daysAgo = (n) => new Date(NOW.getTime() - n * 86400000).toISOString();

describe("first-week checklist", () => {
  it("round-trips in a canonical order and drops unknown words", () => {
    const set = parseChecklist("learn, bogus,chart,dismissed");
    expect([...set].sort()).toEqual(["chart", "dismissed", "learn"]);
    expect(serializeChecklist(set)).toBe("chart,learn,dismissed");
    expect(parseChecklist("")).toEqual(new Set());
    expect(parseChecklist(undefined)).toEqual(new Set());
  });

  it("hides when dismissed or complete", () => {
    expect(checklistVisible(parseChecklist(""))).toBe(true);
    expect(checklistVisible(parseChecklist("chart,ask"))).toBe(true);
    expect(checklistVisible(parseChecklist("dismissed"))).toBe(false);
    expect(checklistVisible(parseChecklist(CHECKLIST.map((i) => i.key).join(",")))).toBe(false);
  });

  it("is for newcomers only", () => {
    expect(isNewcomer(daysAgo(1), NOW)).toBe(true);
    expect(isNewcomer(daysAgo(NEWCOMER_DAYS + 1), NOW)).toBe(false);
    expect(isNewcomer(undefined, NOW)).toBe(false);
    expect(isNewcomer("garbage", NOW)).toBe(false);
  });

  it("has a label for every item, and every item links somewhere real", () => {
    CHECKLIST.forEach(({ key, to }) => {
      expect(en.checklist.items[key]).toBeTruthy();
      expect(to.startsWith("/")).toBe(true);
    });
  });
});

describe("page hints", () => {
  it("normalises paths the way they are stored", () => {
    expect(hintPath("/transit/?tab=x#y")).toBe("/transit");
    expect(parseSeen("/a,/b, ,/c")).toEqual(new Set(["/a", "/b", "/c"]));
  });

  it("auto shows them to newcomers; on/off override", () => {
    expect(hintsEnabled("auto", daysAgo(2), NOW)).toBe(true);
    expect(hintsEnabled("auto", daysAgo(400), NOW)).toBe(false);
    expect(hintsEnabled("on", daysAgo(400), NOW)).toBe(true);
    expect(hintsEnabled("off", daysAgo(2), NOW)).toBe(false);
  });

  it("takes the first sentence of the page's own help answer", () => {
    const long = "This first sentence is comfortably long enough to stand on its own as a hint.";
    expect(firstSentence(`${long} Second one.`)).toBe(long);
    // Too short alone: the next sentence comes with it.
    expect(firstSentence("The best first stop. It explains four things.")).toBe(
      "The best first stop. It explains four things."
    );
    expect(firstSentence("No full stop")).toBe("No full stop");
    expect(firstSentence("")).toBe("");
    // A real page resolves to a real, non-empty answer.
    const id = hintIdFor("/start");
    expect(id).toBe("featStart");
    expect(firstSentence(en.help.a[id]).length).toBeGreaterThan(10);
  });

  it("ends a Hindi sentence at the danda", () => {
    const long =
      "यह पहला वाक्य अपने-आप में संकेत बनने के लिए पर्याप्त लंबा है, इसलिए यहीं रुकता है।";
    expect(firstSentence(`${long} दूसरा वाक्य।`)).toBe(long);
    // A hint is at most two sentences, so any longer Hindi answer is cut short.
    Object.values(hi.help.a)
      .filter((a) => (a.match(/।/g) || []).length > 2)
      .forEach((a) => expect(firstSentence(a).length).toBeLessThan(a.length));
  });
});

describe("landing-page handoff", () => {
  const good = {
    dob: "1990-01-15",
    tob: "14:30",
    place: "Chennai",
    latitude: 13.08,
    longitude: 80.27,
    timezone: 5.5,
    time_accuracy: "exact",
    name: "dropped",
  };

  it("keeps only the fields the welcome flow uses", () => {
    expect(sanitizeHandoff(good)).toEqual({
      dob: "1990-01-15",
      tob: "14:30",
      place: "Chennai",
      latitude: 13.08,
      longitude: 80.27,
      timezone: 5.5,
      time_accuracy: "exact",
    });
  });

  it("refuses an incomplete or malformed set", () => {
    expect(sanitizeHandoff({ ...good, dob: "15/01/1990" })).toBeNull();
    expect(sanitizeHandoff({ ...good, latitude: undefined })).toBeNull();
    expect(sanitizeHandoff(null)).toBeNull();
  });
});

describe("first-look tables", () => {
  it("has a sentence for every sign, star and dasha lord the payload can name", () => {
    for (let s = 1; s <= 12; s += 1) {
      expect(en.firstLook.rising[s]).toBeTruthy();
      expect(en.firstLook.moon[s]).toBeTruthy();
    }
    for (let n = 1; n <= 27; n += 1) {
      const star = en.firstLook.stars[n];
      expect(star.symbol && star.deity && star.theme).toBeTruthy();
    }
    ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"].forEach(
      (lord) => {
        expect(en.firstLook.chapter[lord]).toBeTruthy();
        expect(en.firstLook.chapterShort[lord]).toBeTruthy();
      }
    );
  });
});
