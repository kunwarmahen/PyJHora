import {
  visibleTabs,
  resolveActiveTab,
  shouldWriteTab,
  TAB_PARAM,
} from "./tabs";

const TABS = [
  { key: "chart", label: "Chart" },
  { key: "nakshatra", label: "Nakshatra & Lagna" },
  { key: "yogas", label: "Yogas & Doshas" },
  { key: "advanced", label: "Advanced", advanced: true },
];

describe("visibleTabs", () => {
  test("Everything mode shows every tab", () => {
    expect(visibleTabs(TABS, "advanced").map((t) => t.key)).toEqual([
      "chart",
      "nakshatra",
      "yogas",
      "advanced",
    ]);
  });

  test("Essentials mode hides advanced tabs", () => {
    expect(visibleTabs(TABS, "simple").map((t) => t.key)).toEqual([
      "chart",
      "nakshatra",
      "yogas",
    ]);
  });

  test("a deep-link to an advanced tab reveals it in Essentials mode", () => {
    // Deep-links must never dead-end — the whole point of rule 2.
    expect(visibleTabs(TABS, "simple", "advanced").map((t) => t.key)).toContain(
      "advanced"
    );
  });

  test("requesting a normal tab does not reveal advanced ones", () => {
    expect(visibleTabs(TABS, "simple", "yogas").map((t) => t.key)).not.toContain(
      "advanced"
    );
  });

  test("tolerates a missing or non-array tab list", () => {
    expect(visibleTabs(undefined, "simple")).toEqual([]);
    expect(visibleTabs(null, "advanced")).toEqual([]);
  });
});

describe("resolveActiveTab", () => {
  test("defaults to the first tab when the URL asks for nothing", () => {
    expect(resolveActiveTab(TABS, "advanced")).toBe("chart");
  });

  test("honours a valid requested tab", () => {
    expect(resolveActiveTab(TABS, "advanced", "yogas")).toBe("yogas");
  });

  test("falls back when the URL names a tab that does not exist", () => {
    // Stale bookmark or hand-edited link — land somewhere sensible, never blank.
    expect(resolveActiveTab(TABS, "advanced", "does-not-exist")).toBe("chart");
  });

  test("opens an advanced tab named in the URL even in Essentials mode", () => {
    expect(resolveActiveTab(TABS, "simple", "advanced")).toBe("advanced");
  });

  test("returns null when there are no tabs at all", () => {
    expect(resolveActiveTab([], "advanced")).toBeNull();
  });

  test("first visible tab in Essentials is still the first overall here", () => {
    expect(resolveActiveTab(TABS, "simple")).toBe("chart");
  });

  test("skips a leading advanced tab in Essentials mode", () => {
    const leadingAdvanced = [
      { key: "deep", label: "Deep", advanced: true },
      { key: "basic", label: "Basic" },
    ];
    expect(resolveActiveTab(leadingAdvanced, "simple")).toBe("basic");
    expect(resolveActiveTab(leadingAdvanced, "advanced")).toBe("deep");
  });
});

describe("shouldWriteTab", () => {
  test("writes when the user picks a tab on a URL that had none", () => {
    // The initial resolve never calls this; a real click should record itself.
    expect(shouldWriteTab(null, "chart")).toBe(true);
  });

  test("writes when the user actually changes tab", () => {
    expect(shouldWriteTab("chart", "yogas")).toBe(true);
  });

  test("does not rewrite the tab already in the URL", () => {
    expect(shouldWriteTab("yogas", "yogas")).toBe(false);
  });

  test("never writes an empty tab", () => {
    expect(shouldWriteTab("chart", null)).toBe(false);
    expect(shouldWriteTab("chart", undefined)).toBe(false);
  });
});

test("the URL parameter name is stable", () => {
  // Deep-links in AI readings and digests will hardcode this.
  expect(TAB_PARAM).toBe("tab");
});
