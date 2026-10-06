/**
 * Mount every page (§68.3).
 *
 * Until this file no component had ever been rendered in a test — every suite
 * tested a pure config/util module — so a page that crashed on import, on a
 * missing field or on a failed request shipped green. This harness mounts each
 * page twice against the two ways a real request fails:
 *
 *   • "down"     — every call rejects with no response, as when the network or
 *                  the server is down.
 *   • "rejected" — every call rejects with a 400 and a `detail`, which is what
 *                  the routes send when a calculation fails.
 *
 * A page should say so (an error banner is fine); it may not throw. A "200 with
 * nothing in it" mode was tried first and dropped: the routes never send one
 * (`status != success` becomes a 4xx), so the crashes it found were the stub's.
 *
 * Pages are discovered from this directory, not listed, so a new page is covered
 * the moment it exists. The contexts are stubbed with a signed-in user, the
 * owner's profile selected and Everything mode on, so the advanced pages render
 * their real content rather than an "advanced" notice.
 */
import fs from "fs";
import path from "path";
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react-dom/test-utils";
import { MemoryRouter } from "react-router-dom";
import "../i18n";
import { FEATURES, hubForPath } from "../config/features";

// ── The stubbed world ───────────────────────────────────────────────────────

// "down" | "rejected" — read at call time by the API stub below.
let mockApiMode = "down";
// A page that refetches on every state change it causes never stops calling an
// instant stub, and the test would hang draining it. Past this many calls in one
// mount the stub stops answering and records which method looped, so the hang
// becomes a failure that names the culprit.
const mockCallLimit = 200;
let mockCalls = 0;
let mockLoop = null;

jest.mock("../services/api", () => {
  const reply = (name) => {
    mockCalls += 1;
    if (mockCalls > mockCallLimit) {
      mockLoop = mockLoop || name;
      return new Promise(() => {});
    }
    return mockApiMode === "down"
      ? Promise.reject(Object.assign(new Error("Network Error"), { response: undefined }))
      : Promise.reject(
          Object.assign(new Error("Request failed with status code 400"), {
            response: { status: 400, data: { detail: "Calculation failed" } },
          })
        );
  };
  // Any method of any service: a function returning the mode's reply. Cached per
  // name, so a method has one identity — a page that lists one in an effect's
  // dependencies must not see it change on every render. Plain functions, not
  // jest.fn(): CRA's `resetMocks` wipes a jest.fn's implementation before every
  // test, and the stub then returned undefined from the second page on.
  const service = (label) => {
    const fns = {};
    return new Proxy(
      {},
      {
        get: (_, key) => {
          if (key === "then" || typeof key === "symbol") return undefined;
          if (!fns[key]) fns[key] = () => reply(`${label}.${String(key)}`);
          return fns[key];
        },
      }
    );
  };
  const streamStub = () => ({ cancel: () => {}, done: reply("stream").catch(() => {}) });
  const named = {
    __esModule: true,
    default: service("api"),
    API_URL: "http://api.test",
    setTokens: () => {},
    getRefreshToken: () => null,
    clearTokens: () => {},
    streamAskQuestion: streamStub,
    resumeAskStream: streamStub,
  };
  // Every `fooService` export is stubbed by name, so a service added to api.js
  // later is covered without touching this file (onboardingService was missed
  // by the hand-kept list and failed StartPage with "reading 'firstLook'").
  const services = {};
  return new Proxy(named, {
    get: (target, key) => {
      if (key in target) return target[key];
      if (typeof key === "string" && key.endsWith("Service")) {
        if (!services[key]) services[key] = service(key);
        return services[key];
      }
      return undefined;
    },
  });
});

const mockProfile = {
  _id: "p1",
  profile_name: "Owner",
  is_default: true,
  birth_details: {
    name: "Owner",
    dob: "1976-06-04",
    tob: "05:45:02",
    place: "Shahgarh, India",
    latitude: 27.845278,
    longitude: 78.334167,
    timezone: 5.5,
  },
};

// Each context value is built ONCE, the way the real providers keep theirs
// stable between renders. A stub returning a fresh object per call made every
// effect that depends on `user` (AdminPage's guard) re-run forever, which hung
// the whole suite rather than failing it.
jest.mock("../contexts/AuthContext", () => {
  const value = {
    user: { username: "tester", name: "Tester", email: "t@example.com", is_admin: true },
    isLoading: false,
    error: null,
    login: () => {},
    loginWithGoogle: () => {},
    register: () => {},
    logout: () => {},
    reloadUser: () => {},
  };
  return { AuthProvider: ({ children }) => children, useAuth: () => value };
});

jest.mock("../contexts/ProfileContext", () => {
  const value = {
    selectedProfile: mockProfile,
    profiles: [mockProfile],
    loading: false,
    loadProfiles: () => Promise.resolve(),
    saveProfile: () => Promise.resolve(),
    updateProfile: () => Promise.resolve(),
    deleteProfile: () => Promise.resolve(),
    setDefaultProfile: () => Promise.resolve(),
    exportProfiles: () => {},
    importProfiles: () => {},
    selectProfile: () => {},
    clearProfile: () => {},
    resumeProfile: () => {},
  };
  return { ProfileProvider: ({ children }) => children, useProfile: () => value };
});

jest.mock("../contexts/SettingsContext", () => {
  const actual = jest.requireActual("../contexts/SettingsContext");
  const value = {
    settings: {
      language: "en",
      uiMode: "advanced",
      theme: "light",
      density: "comfortable",
      startupProfile: "resume",
      ayanamsa: "TRUE_CITRA",
      chartStyle: "north",
      signLabel: "number",
      panchangaSystem: "drik",
      praveshaBasis: "solar",
      varnadaMethod: "1",
      aiProviderType: "ollama",
      aiModel: "",
      aiBaseUrl: "",
      aiMode: "pass_all",
      aiMaxTokens: 0,
      aiShareBirthDate: "false",
      aiShareBirthTime: "false",
      aiShareBirthPlace: "false",
      onboardingChecklist: "",
      pageHints: "auto",
      hintsSeen: "",
    },
    updateSetting: () => {},
  };
  return { ...actual, SettingsProvider: ({ children }) => children, useSettings: () => value };
});

jest.mock("../contexts/LocationContext", () => {
  const value = {
    location: null,
    loaded: true,
    saveLocation: () => {},
    saveLocationFromZone: () => {},
    clearLocation: () => {},
  };
  return { LocationProvider: ({ children }) => children, useCurrentLocation: () => value };
});

// react-markdown and its remark plugins ship as ESM only, which CRA's Jest does
// not transform. The app reaches them through this one wrapper; plain text is
// all a mount test needs from it.
jest.mock("../components/Markdown", () => ({
  __esModule: true,
  default: ({ children }) => <div className="mock-markdown">{children}</div>,
}));

// ── Environment the browser would supply ─────────────────────────────────────

beforeAll(() => {
  global.IS_REACT_ACT_ENVIRONMENT = true;
  // Pages that fetch directly (map picker, almanac) go through the same modes.
  global.fetch = () => {
    mockCalls += 1;
    if (mockCalls > mockCallLimit) {
      mockLoop = mockLoop || "fetch";
      return new Promise(() => {});
    }
    return mockApiMode === "down"
      ? Promise.reject(new TypeError("Failed to fetch"))
      : Promise.resolve({
          ok: false,
          status: 400,
          json: () => Promise.resolve({ detail: "Calculation failed" }),
        });
  };
  window.scrollTo = () => {};
  Element.prototype.scrollIntoView = () => {};
  global.IntersectionObserver =
    global.IntersectionObserver ||
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
      takeRecords() {
        return [];
      }
    };
  window.matchMedia =
    window.matchMedia ||
    ((query) => ({
      matches: false,
      media: query,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
    }));
  global.ResizeObserver =
    global.ResizeObserver ||
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    };
});

// ── The pages ───────────────────────────────────────────────────────────────

// Every `*Page.js` here, and every component it exports whose name ends in
// "Page" (PeriodDigestPage exports the fortnightly and monthly variants).
const PAGE_FILES = fs
  .readdirSync(__dirname)
  .filter((f) => /Page\.js$/.test(f))
  .sort();

const pageCases = () =>
  PAGE_FILES.flatMap((file) => {
    // eslint-disable-next-line import/no-dynamic-require, global-require
    const mod = require(path.join(__dirname, file));
    return Object.entries(mod)
      .filter(([name, C]) => name.endsWith("Page") && typeof C === "function")
      .map(([name, C]) => ({ file, name, C }));
  });

// The route each page is mounted at: its registered path when it has one, so
// hub strips and help links resolve as they do in the app.
const KEY_BY_COMPONENT = {
  BirthChartPage: "/birth-chart",
  BhavaChartPage: "/bhava",
  NakshatraProfilePage: "/nakshatra",
  StrengthPage: "/strength",
  AdvancedPage: "/advanced",
  SensitivePointsPage: "/sensitive-points",
  DailyDigestPage: "/daily-digest",
  FortnightlyDigestPage: "/fortnightly-digest",
  MonthlyDigestPage: "/monthly-digest",
  VarshaphalPage: "/varshaphal",
  TithiPraveshaPage: "/tithi-pravesha",
  JaiminiPage: "/jaimini",
  KPPage: "/kp",
  NadiPage: "/nadi",
  BhriguMarkersPage: "/bhrigu-markers",
  SarvatobhadraPage: "/chakras",
  LifeReportPage: "/life-report",
  FullReportPage: "/report",
  PredictionsPage: "/predictions",
  DhasaPage: "/dhasa",
  TimelinePage: "/timeline",
  TransitPage: "/transit",
  GocharaPhalaPage: "/gochara",
  SadeSatiPage: "/sade-sati",
  EphemerisPage: "/ephemeris",
  AlmanacPage: "/almanac",
  VedicClockPage: "/vedic-clock",
  PanchaPakshiPage: "/pancha-pakshi",
  NowChartPage: "/now",
  MuhurtaPage: "/muhurta",
  CompatibilityPage: "/compatibility",
  ComparePage: "/compare",
  RemediesPage: "/remedies",
  PrashnaPage: "/prashna",
  HistoryPage: "/history",
  JournalPage: "/journal",
  LearnChartPage: "/learn",
  BirthTimeRectificationPage: "/rectify",
  SettingsPage: "/settings",
  DashboardPage: "/dashboard",
  AskAstrologerPage: "/ask-astrologer",
  StartPage: "/start",
  WelcomePage: "/welcome",
};

const flush = async () => {
  // Let mount effects fire, their (stubbed) requests settle, and the state
  // updates that follow render — a few macrotask turns covers chained awaits.
  for (let i = 0; i < 5; i += 1) {
    // eslint-disable-next-line no-await-in-loop
    await act(() => new Promise((r) => setTimeout(r, 0)));
  }
};

const mount = async (C, route) => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => {
    root.render(
      <MemoryRouter initialEntries={[route]}>
        <C />
      </MemoryRouter>
    );
  });
  await flush();
  return {
    host,
    unmount: () => {
      act(() => root.unmount());
      host.remove();
    },
  };
};

// React reports an error thrown during render through console.error before the
// root gives up; treat any such report as the failure it is.
const captureRenderErrors = () => {
  const errors = [];
  const spy = jest.spyOn(console, "error").mockImplementation((...args) => {
    const text = args.map((a) => (a && a.stack) || String(a)).join(" ");
    if (/The above error occurred|Uncaught|is not a function|Cannot read propert/i.test(text))
      errors.push(text.split("\n").slice(0, 4).join("\n"));
  });
  return { errors, restore: () => spy.mockRestore() };
};

const CASES = pageCases();

describe("every page mounts", () => {
  it("finds the pages", () => {
    // 51 routed pages share 50 files (PeriodDigestPage has two).
    expect(CASES.length).toBeGreaterThanOrEqual(50);
  });

  // The route table must know every page this harness mounts, or the hub/help
  // assertions below would silently test the wrong path.
  it("maps every registered feature to a mounted page", () => {
    const mounted = new Set(Object.values(KEY_BY_COMPONENT));
    FEATURES.forEach((f) => expect(mounted).toContain(f.path));
  });

  describe.each(["down", "rejected"])("with the API %s", (mode) => {
    it.each(CASES.map((c) => [c.name, c]))("%s", async (_name, { C, name }) => {
      mockApiMode = mode;
      mockCalls = 0;
      mockLoop = null;
      const route = KEY_BY_COMPONENT[name] || "/x";
      const { errors, restore } = captureRenderErrors();
      let view;
      try {
        view = await mount(C, route);
        expect(errors).toEqual([]);
        expect({ requestLoop: mockLoop }).toEqual({ requestLoop: null });
        expect(view.host.innerHTML.length).toBeGreaterThan(0);
      } finally {
        restore();
        if (view) view.unmount();
      }
    });
  });
});

// §79: a hub member must render its hub's strip — it comes from PageHeader, so a
// member page that builds its own header silently drops out of the hub.
describe("hub members show their hub strip", () => {
  const members = Object.entries(KEY_BY_COMPONENT).filter(([, p]) => hubForPath(p));
  it.each(members)("%s", async (name, route) => {
    mockApiMode = "rejected";
    mockCalls = 0;
    mockLoop = null;
    const { C } = CASES.find((c) => c.name === name);
    const view = await mount(C, route);
    try {
      const strip = view.host.querySelector("nav.hub-nav");
      expect(strip).not.toBeNull();
      expect(strip.querySelector('[aria-current="page"]').getAttribute("href")).toBe(route);
    } finally {
      view.unmount();
    }
  });
});
