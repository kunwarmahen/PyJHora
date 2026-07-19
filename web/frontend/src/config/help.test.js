import { HELP_SECTIONS, allHelpItemIds, filterHelp } from "./help";
import en from "../i18n/locales/en.json";

// The point of the structure/text split is that adding a question is one id
// here plus two strings there. These tests are what stop the two drifting.

describe("help outline integrity", () => {
  test("every question id has both a question and an answer in en.json", () => {
    const missing = allHelpItemIds().flatMap((id) => [
      ...(en.help.q[id] ? [] : [`help.q.${id}`]),
      ...(en.help.a[id] ? [] : [`help.a.${id}`]),
    ]);
    // A missing string would render as a raw key in a blank accordion row.
    expect(missing).toEqual([]);
  });

  test("no orphaned text — every string in help.q/help.a is used by a section", () => {
    const ids = new Set(allHelpItemIds());
    const orphans = [
      ...Object.keys(en.help.q).filter((id) => !ids.has(id)),
      ...Object.keys(en.help.a).filter((id) => !ids.has(id)),
    ];
    expect(orphans).toEqual([]);
  });

  test("every section has a title and blurb", () => {
    HELP_SECTIONS.forEach((s) => {
      expect(en.help.sections[s.id]?.title).toBeTruthy();
      expect(en.help.sections[s.id]?.blurb).toBeTruthy();
    });
  });

  test("question ids are unique across all sections", () => {
    const ids = allHelpItemIds();
    expect(new Set(ids).size).toBe(ids.length);
  });

  test("every `to` link is an absolute in-app path", () => {
    HELP_SECTIONS.flatMap((s) => s.items)
      .filter((i) => i.to)
      .forEach((i) => expect(i.to.startsWith("/")).toBe(true));
  });

  test("the getting-started section comes first", () => {
    // Someone who knows nothing should land on "what is this", not on a feature.
    expect(HELP_SECTIONS[0].id).toBe("start");
    expect(HELP_SECTIONS[0].items[0].id).toBe("whatIsThis");
  });
});

describe("filterHelp", () => {
  const text = (id) => `${en.help.q[id]} ${en.help.a[id]}`;

  test("an empty query returns everything untouched", () => {
    expect(filterHelp("", text)).toBe(HELP_SECTIONS);
    expect(filterHelp("   ", text)).toBe(HELP_SECTIONS);
  });

  test("matches on the words a reader actually sees, not on ids", () => {
    // "birth time" appears in the prose; no id contains that phrase.
    const hits = filterHelp("birth time", text).flatMap((s) => s.items.map((i) => i.id));
    expect(hits).toContain("whyBirthTime");
  });

  test("is case-insensitive", () => {
    const lower = filterHelp("nakshatra", text).flatMap((s) => s.items.map((i) => i.id));
    const upper = filterHelp("NAKSHATRA", text).flatMap((s) => s.items.map((i) => i.id));
    expect(upper).toEqual(lower);
    expect(lower.length).toBeGreaterThan(0);
  });

  test("sections with no surviving items drop out entirely", () => {
    const result = filterHelp("zzzznotathing", text);
    expect(result).toEqual([]);
  });

  test("tolerates missing text for an id without throwing", () => {
    expect(() => filterHelp("anything", () => undefined)).not.toThrow();
  });
});
