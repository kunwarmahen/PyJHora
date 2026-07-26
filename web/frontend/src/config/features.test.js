import {
  FEATURES,
  FEATURE_GROUPS,
  visibleFeatures,
  groupedFeatures,
  featureForPath,
  isFeatureVisible,
} from "./features";

describe("feature registry", () => {
  it("has a unique path and key per feature", () => {
    const paths = FEATURES.map((f) => f.path);
    const keys = FEATURES.map((f) => f.key);
    expect(new Set(paths).size).toBe(paths.length);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("gives every feature the fields the surfaces render", () => {
    FEATURES.forEach((f) => {
      expect(f.path.startsWith("/")).toBe(true);
      expect(typeof f.Icon).toBeDefined();
      expect(["simple", "advanced"]).toContain(f.tier);
      // Everything that becomes a dashboard tile needs a gradient; navOnly
      // entries (Dashboard, Settings) are drawer-only and don't.
      if (!f.navOnly) expect(f.gradient).toMatch(/^linear-gradient/);
    });
  });

  // A typo'd or invented group would silently vanish from both the dashboard
  // and the drawer: groupedFeatures only emits sections it knows about.
  it("puts every feature in a declared group", () => {
    const known = new Set(FEATURE_GROUPS.map((g) => g.key));
    FEATURES.forEach((f) => expect(known).toContain(f.group));
  });

  describe("groupedFeatures", () => {
    it("keeps every feature, in registry order, section by section", () => {
      const flat = groupedFeatures(FEATURES).flatMap((s) => s.features);
      expect(flat).toEqual(FEATURES);
    });

    it("emits sections in FEATURE_GROUPS order", () => {
      const keys = groupedFeatures(FEATURES).map((s) => s.key);
      expect(keys).toEqual(FEATURE_GROUPS.map((g) => g.key));
    });

    // Essentials advertises nothing from Calendar & Muhurta, and a search for
    // "dasha" empties most sections — a bare heading over no tiles is a bug.
    it("drops sections with nothing left in them", () => {
      const sections = groupedFeatures(visibleFeatures("simple"));
      sections.forEach((s) => expect(s.features.length).toBeGreaterThan(0));
      expect(sections.map((s) => s.key)).not.toContain("calendar");
      expect(groupedFeatures([])).toEqual([]);
    });
  });

  it("keeps the Essentials set to the agreed features", () => {
    expect(
      visibleFeatures("simple")
        .map((f) => f.path)
        .sort()
    ).toEqual(
      [
        "/ask-astrologer",
        "/birth-chart",
        "/compatibility",
        "/daily-digest",
        "/dashboard",
        "/dhasa",
        "/history",
        "/life-report",
        "/remedies",
        "/settings",
        "/transit",
      ].sort()
    );
  });

  it("shows everything in advanced mode", () => {
    expect(visibleFeatures("advanced")).toHaveLength(FEATURES.length);
    expect(visibleFeatures("advanced").length).toBeGreaterThan(visibleFeatures("simple").length);
  });

  it("resolves a route to its feature", () => {
    expect(featureForPath("/kp").key).toBe("kp");
    expect(featureForPath("/nope")).toBeUndefined();
  });

  describe("isFeatureVisible", () => {
    it("hides an advanced route only in simple mode", () => {
      expect(isFeatureVisible("/kp", "simple")).toBe(false);
      expect(isFeatureVisible("/kp", "advanced")).toBe(true);
    });

    it("always shows a simple route", () => {
      expect(isFeatureVisible("/birth-chart", "simple")).toBe(true);
      expect(isFeatureVisible("/birth-chart", "advanced")).toBe(true);
    });

    // Routes the registry deliberately omits (login, profile-selection,
    // /share/:token) must not be mistaken for hidden-advanced ones — that would
    // put an "advanced feature" banner on the login page.
    it("treats unregistered routes as visible", () => {
      expect(isFeatureVisible("/login", "simple")).toBe(true);
      expect(isFeatureVisible("/share/abc123", "simple")).toBe(true);
    });
  });
});
