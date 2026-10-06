import {
  FEATURES,
  FEATURE_GROUPS,
  visibleFeatures,
  groupedFeatures,
  featureForPath,
  isFeatureVisible,
  searchFeatures,
  FEATURE_SUBITEMS,
  featureForKey,
  HUBS,
  hubMembers,
  hubForPath,
  visibleHubMembers,
  navEntries,
} from "./features";
import en from "../i18n/locales/en.json";

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

// The dashboard launcher must find content that lives behind a tab or inside a
// long page, not just tile names — "yogas" once found nothing because Yogas &
// Doshas is a Birth Chart tab. Add a term here whenever someone reports a miss.
describe("dashboard search coverage", () => {
  const t = (key) => key.split(".").reduce((o, k) => (o ? o[k] : undefined), en) || "";
  const tiles = FEATURES.filter((f) => !f.navOnly);

  it.each([
    "yoga",
    "yogas",
    "raja yoga",
    "gajakesari",
    "doshas",
    "kaal sarp",
    "manglik",
    "aspects",
    "drishti",
    "divisional",
    "d10",
    "dasamsa",
    "d60",
    "navamsa",
    "panchanga",
    "nakshatra",
    "ashtakavarga",
    "sarvashtakavarga",
    "longevity",
    "avasthas",
    "combust",
    "friendship",
    "atmakaraka",
    "7th house",
    "shadbala",
    "vimsopaka",
    "kp horary",
    "mandi",
    "sudarshana",
    "kota",
    "marriage",
    "gemstone",
  ])("finds %s", (term) => {
    const { tiles: hits, subs } = searchFeatures(tiles, term, t);
    expect(hits.length + subs.length).toBeGreaterThan(0);
  });

  it("lands 'yogas' on the Yogas tab", () => {
    const { subs } = searchFeatures(tiles, "yogas", t);
    expect(subs.map((s) => s.to)).toContain("/birth-chart?tab=yogas");
  });

  it("gives every sub-item a real parent and an internal link", () => {
    FEATURE_SUBITEMS.forEach((s) => {
      expect(featureForKey(s.parent)).toBeDefined();
      expect(s.to.startsWith("/")).toBe(true);
    });
  });
});

// §79 — hubs collapse related pages into one entry. The ways that goes wrong are
// a hub nobody joins (an empty strip), a member naming a hub that doesn't exist
// (the page silently drops out of the drawer), and a page you can deep-link to
// that the strip doesn't show.
describe("hubs", () => {
  const lookup = (key) => key.split(".").reduce((o, k) => (o ? o[k] : undefined), en);

  it("every feature's hub exists, and every hub has at least two members", () => {
    const known = new Set(HUBS.map((h) => h.key));
    FEATURES.filter((f) => f.hub).forEach((f) => expect(known).toContain(f.hub));
    HUBS.forEach((h) => expect(hubMembers(h.key).length).toBeGreaterThanOrEqual(2));
  });

  it("members sit in their hub's section, so search results stay where they live", () => {
    HUBS.forEach((h) => hubMembers(h.key).forEach((m) => expect(m.group).toBe(h.group)));
  });

  it("every hub has a drawer label and a tile title + description", () => {
    HUBS.forEach((h) => {
      expect(lookup(`nav.hubs.${h.key}`)).toBeTruthy();
      expect(lookup(`dashboard.hubs.${h.key}.title`)).toBeTruthy();
      expect(lookup(`dashboard.hubs.${h.key}.description`)).toBeTruthy();
    });
  });

  it("lists each hub once and no member on its own", () => {
    ["simple", "advanced"].forEach((mode) => {
      const entries = navEntries(mode);
      const hubKeys = entries.filter((e) => e.isHub).map((e) => e.key);
      expect(new Set(hubKeys).size).toBe(hubKeys.length);
      entries.filter((e) => !e.isHub).forEach((e) => expect(e.hub).toBeUndefined());
    });
  });

  it("reaches every visible page either directly or through its hub's strip", () => {
    ["simple", "advanced"].forEach((mode) => {
      const reachable = new Set();
      navEntries(mode).forEach((e) => {
        reachable.add(e.path);
        if (e.isHub) visibleHubMembers(e.key, mode, e.path).forEach((m) => reachable.add(m.path));
      });
      visibleFeatures(mode).forEach((f) => expect(reachable).toContain(f.path));
    });
  });

  it("opens a hub on its first page the mode advertises", () => {
    const periods = (mode) => navEntries(mode).find((e) => e.key === "periods");
    expect(periods("simple").path).toBe("/daily-digest");
    // Reports leads with the Life Report, the one Essentials shows.
    expect(navEntries("simple").find((e) => e.key === "reports").path).toBe("/life-report");
    // An all-advanced hub is simply absent from Essentials.
    expect(navEntries("simple").find((e) => e.key === "systems")).toBeUndefined();
    expect(periods("advanced").members.length).toBe(5);
  });

  it("keeps a deep-linked advanced member in the strip even in Essentials", () => {
    const simple = visibleHubMembers("transits", "simple", "/transit").map((m) => m.path);
    expect(simple).toEqual(["/transit"]);
    const deep = visibleHubMembers("transits", "simple", "/gochara").map((m) => m.path);
    expect(deep).toEqual(["/transit", "/gochara"]);
  });

  it("resolves a route to its hub", () => {
    expect(hubForPath("/varshaphal").key).toBe("periods");
    expect(hubForPath("/muhurta")).toBeUndefined();
    expect(hubForPath("/nope")).toBeUndefined();
  });

  it("shrinks the drawer to well under the page count", () => {
    expect(navEntries("advanced").length).toBeLessThanOrEqual(20);
  });
});
