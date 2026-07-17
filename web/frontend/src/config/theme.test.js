import {
  applyTheme,
  readThemePref,
  resolveTheme,
  systemTheme,
  watchSystemTheme,
  THEME_DEFAULT,
  THEME_STORAGE_KEY,
} from "./theme";

/** Stand in for matchMedia, which jsdom does not implement. */
const mockMatchMedia = (dark) => {
  const listeners = new Set();
  const mq = {
    matches: dark,
    addEventListener: (_, fn) => listeners.add(fn),
    removeEventListener: (_, fn) => listeners.delete(fn),
    fire: (next) => {
      mq.matches = next;
      listeners.forEach((fn) => fn(mq));
    },
    listenerCount: () => listeners.size,
  };
  window.matchMedia = jest.fn().mockReturnValue(mq);
  return mq;
};

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  mockMatchMedia(false);
});

describe("theme preference", () => {
  it("defaults to system when unset or unrecognised", () => {
    expect(readThemePref()).toBe(THEME_DEFAULT);
    localStorage.setItem(THEME_STORAGE_KEY, "chartreuse");
    expect(readThemePref()).toBe(THEME_DEFAULT);
  });

  it("reads an explicit choice back", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "dark");
    expect(readThemePref()).toBe("dark");
  });

  it("never writes the resolved value back — system must stay system", () => {
    // Otherwise the preference freezes into whatever the OS was on first load
    // and silently stops tracking it.
    mockMatchMedia(true);
    resolveTheme("system");
    applyTheme("system");
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
  });
});

describe("resolveTheme", () => {
  it("passes an explicit choice through, ignoring the OS", () => {
    mockMatchMedia(true);
    expect(resolveTheme("light")).toBe("light");
    expect(resolveTheme("dark")).toBe("dark");
  });

  it("follows the OS on system", () => {
    mockMatchMedia(true);
    expect(resolveTheme("system")).toBe("dark");
    mockMatchMedia(false);
    expect(resolveTheme("system")).toBe("light");
  });

  it("falls back to light where matchMedia is unavailable", () => {
    delete window.matchMedia;
    expect(systemTheme()).toBe("light");
    expect(resolveTheme("system")).toBe("light");
  });
});

describe("applyTheme", () => {
  it("stamps the resolved theme, never the literal preference", () => {
    mockMatchMedia(true);
    applyTheme("system");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});

describe("watchSystemTheme", () => {
  it("fires on an OS flip and unsubscribes cleanly", () => {
    const mq = mockMatchMedia(false);
    const seen = [];
    const off = watchSystemTheme((t) => seen.push(t));
    mq.fire(true);
    expect(seen).toEqual(["dark"]);
    off();
    expect(mq.listenerCount()).toBe(0);
    mq.fire(false);
    expect(seen).toEqual(["dark"]);
  });
});

describe("the pre-paint script in index.html", () => {
  // It is duplicated from this module by necessity (nothing from the bundle
  // runs early enough), so the two can drift apart silently. Pin the contract.
  const fs = require("fs");
  const path = require("path");
  const html = fs.readFileSync(
    path.join(__dirname, "..", "..", "public", "index.html"),
    "utf8",
  );

  it("uses the same storage key and query as this module", () => {
    expect(html).toContain(`localStorage.getItem("${THEME_STORAGE_KEY}")`);
    expect(html).toContain("(prefers-color-scheme: dark)");
  });

  it("resolves system rather than stamping the stored literal", () => {
    // Stamping "system" would match no CSS selector and flash light at every
    // default-setting user on a dark machine.
    expect(html).toContain('setAttribute("data-theme", resolved)');
    expect(html).not.toContain('setAttribute("data-theme", pref)');
  });

  it("runs before the app mounts, or the flash it prevents comes back", () => {
    expect(html.indexOf("prefers-color-scheme")).toBeLessThan(html.indexOf('id="root"'));
  });
});
