import {
  DENSITIES,
  DENSITY_DEFAULT,
  DENSITY_STORAGE_KEY,
  applyDensity,
  readDensityPref,
} from "./density";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-density");
});

describe("readDensityPref", () => {
  test("defaults to compact when nothing is stored", () => {
    expect(readDensityPref()).toBe("compact");
  });

  test("returns a stored preference", () => {
    localStorage.setItem(DENSITY_STORAGE_KEY, "comfortable");
    expect(readDensityPref()).toBe("comfortable");
  });

  test("ignores an unrecognised value", () => {
    localStorage.setItem(DENSITY_STORAGE_KEY, "enormous");
    expect(readDensityPref()).toBe(DENSITY_DEFAULT);
  });
});

describe("applyDensity", () => {
  test("comfortable stamps the attribute", () => {
    applyDensity("comfortable");
    expect(document.documentElement.getAttribute("data-density")).toBe("comfortable");
  });

  test("compact carries no attribute — it is what :root already defines", () => {
    applyDensity("comfortable");
    applyDensity("compact");
    expect(document.documentElement.getAttribute("data-density")).toBeNull();
  });

  test("a bad value degrades to the default rather than an undefined scale", () => {
    applyDensity("comfortable");
    expect(applyDensity("enormous")).toBe(DENSITY_DEFAULT);
    expect(document.documentElement.getAttribute("data-density")).toBeNull();
  });

  test("reads from storage when called with no argument", () => {
    localStorage.setItem(DENSITY_STORAGE_KEY, "comfortable");
    expect(applyDensity()).toBe("comfortable");
    expect(document.documentElement.getAttribute("data-density")).toBe("comfortable");
  });

  test("every listed density is accepted", () => {
    DENSITIES.forEach((d) => expect(applyDensity(d)).toBe(d));
  });
});
