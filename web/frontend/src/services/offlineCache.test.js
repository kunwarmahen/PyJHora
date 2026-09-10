/**
 * §68.8 — what the offline cache will and will not keep.
 *
 * The IndexedDB plumbing is not worth mocking; the two rules that can silently
 * do damage are. Caching an AI reading would replay yesterday's answer as if it
 * were today's, and a key that ignores the request body would hand one profile's
 * chart to another.
 */
import { isCacheable, cacheKey } from "./offlineCache";

describe("what is cacheable", () => {
  it("keeps deterministic computations", () => {
    expect(isCacheable("post", "/api/astrology/birth-chart")).toBe(true);
    expect(isCacheable("post", "/api/astrology/divisional-chart")).toBe(true);
    expect(isCacheable("get", "/api/astrology/panchanga")).toBe(true);
    expect(isCacheable("get", "/api/user/charts")).toBe(true);
  });

  it("never keeps an AI reading", () => {
    // The rule is a suffix, so an endpoint added next year is covered too.
    expect(isCacheable("post", "/api/astrology/remedies-analysis")).toBe(false);
    expect(isCacheable("post", "/api/astrology/some-future-analysis")).toBe(false);
    expect(isCacheable("post", "/api/astrology/ask")).toBe(false);
    expect(isCacheable("post", "/api/astrology/predict")).toBe(false);
  });

  it("never keeps background jobs or rectification", () => {
    expect(isCacheable("post", "/api/astrology/life-report/start")).toBe(false);
    expect(isCacheable("get", "/api/astrology/life-report/job")).toBe(false);
    expect(isCacheable("post", "/api/astrology/rectify-birth-time")).toBe(false);
  });

  it("leaves auth, admin and writes alone", () => {
    expect(isCacheable("post", "/api/auth/login")).toBe(false);
    expect(isCacheable("get", "/api/admin/users")).toBe(false);
    expect(isCacheable("delete", "/api/user/charts")).toBe(false);
  });
});

describe("the cache key", () => {
  const chart = (name) => ({
    method: "post",
    url: "/api/astrology/birth-chart",
    data: { name, date_of_birth: "1990-01-01" },
    params: { ayanamsa: "TRUE_CITRA" },
  });

  it("separates two profiles posting to the same URL", () => {
    expect(cacheKey(chart("A"), "kunwar")).not.toEqual(cacheKey(chart("B"), "kunwar"));
  });

  it("separates two users on the same browser", () => {
    expect(cacheKey(chart("A"), "kunwar")).not.toEqual(cacheKey(chart("A"), "someone"));
  });

  it("ignores key order in the body, so a re-render is a cache hit", () => {
    const a = { ...chart("A"), data: { name: "A", date_of_birth: "1990-01-01" } };
    const b = { ...chart("A"), data: { date_of_birth: "1990-01-01", name: "A" } };
    expect(cacheKey(a, "kunwar")).toEqual(cacheKey(b, "kunwar"));
  });

  it("reads a body axios has already serialised", () => {
    const parsed = chart("A");
    const serialised = { ...parsed, data: JSON.stringify(parsed.data) };
    expect(cacheKey(serialised, "kunwar")).toEqual(cacheKey(parsed, "kunwar"));
  });

  it("separates two ayanamsas", () => {
    const lahiri = { ...chart("A"), params: { ayanamsa: "LAHIRI" } };
    expect(cacheKey(lahiri, "kunwar")).not.toEqual(cacheKey(chart("A"), "kunwar"));
  });
});
