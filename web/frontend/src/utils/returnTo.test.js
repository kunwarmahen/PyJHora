import { returnHere, returnTarget } from "./returnTo";

const at = (url) => {
  delete window.location;
  window.location = new URL(`https://app.test${url}`);
};

describe("returnHere", () => {
  it("remembers the path and its query", () => {
    at("/transits?date=2026-09-09");
    expect(returnHere()).toEqual({ state: { returnTo: "/transits?date=2026-09-09" } });
  });

  it("drops the ?profile= deep link, which would re-select the old chart", () => {
    at("/dhasa?profile=abc123&level=2");
    expect(returnHere().state.returnTo).toBe("/dhasa?level=2");
  });
});

describe("returnTarget", () => {
  it("returns the remembered page", () => {
    expect(returnTarget({ returnTo: "/kp" })).toBe("/kp");
  });

  it("falls back to the dashboard when nobody said where they came from", () => {
    expect(returnTarget(undefined)).toBe("/dashboard");
    expect(returnTarget({})).toBe("/dashboard");
  });

  it("refuses another origin and the picker itself", () => {
    expect(returnTarget({ returnTo: "//evil.test/steal" })).toBe("/dashboard");
    expect(returnTarget({ returnTo: "https://evil.test" })).toBe("/dashboard");
    expect(returnTarget({ returnTo: "/profile-selection" })).toBe("/dashboard");
  });
});
